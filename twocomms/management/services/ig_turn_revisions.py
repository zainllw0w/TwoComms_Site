"""Dormant immutable bundle revisions for B03.2/B03.3.

This module has no send or business-effect integration.  Ingress/worker/outbox
callers are wired only after the final B03.4/B03.5 CAS boundaries exist.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Mapping

from django.db import transaction
from django.utils import timezone

from management.models import (
    IgClient,
    IgCustomerTurn,
    IgCustomerTurnRevision,
    IgTurnMessage,
    IgTurnRevisionSource,
    InstagramBotMessage,
)


QUIET_SECONDS = 1.5
QUIET_CAP_SECONDS = 4.0
OVERALL_DEADLINE_SECONDS = 45.0
MEDIA_PREPARE_BUDGET_SECONDS = 10.0
SEND_RESERVE_SECONDS = 5.0
PREPARATION_LEASE_SECONDS = 15.0
EXECUTION_LEASE_SECONDS = 180.0
MAX_SOURCES = 32
MAX_TEXT_CHARS = 64_000
MAX_MEDIA_PARTS = 64
MAX_PARTS_PER_SOURCE = 8
SNAPSHOT_VERSION = "ig-turn-bundle-v1"

_PENDING_MEDIA_STATES = frozenset({
    "", "discovered", "pending", "preparing", "acquiring", "fetching",
    "capturing", "retryable",
})
_OWNED_MEDIA_STATES = frozenset({"owned", "captured"})
_SEALED_FAILURE_REASONS = {
    "expired": "source_expired",
    "deleted": "source_deleted",
    "unsupported": "unsupported_media",
    "permanent_failure": "capture_failed",
    "failed": "capture_failed",
    "unavailable": "capture_unavailable",
}
_ALLOWED_MEDIA_FIELDS = (
    "source_part_id", "original_index", "identity_origin", "type", "role",
    "provider_object_id",
)
_ALLOWED_REFERRAL_FIELDS = ("ref", "ad_id", "source", "type")


@dataclass(frozen=True)
class RevisionBuildResult:
    revision: IgCustomerTurnRevision | None
    created: bool
    successor_required: bool = False
    reason: str = ""


@dataclass(frozen=True)
class RevisionClaim:
    revision: IgCustomerTurnRevision | None
    token: str = ""
    media_prepare_deadline: object | None = None
    reason: str = ""


@dataclass(frozen=True)
class RevisionSealResult:
    revision: IgCustomerTurnRevision | None
    sealed: bool
    reason: str = ""


def _canonical(value) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _digest(value) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _aware(value, *, fallback=None):
    value = value or fallback or timezone.now()
    if timezone.is_naive(value):
        raise ValueError("revision timestamps must be timezone-aware")
    return value


def _discovered_media(message) -> list[dict]:
    from management.services.ig_media_manifest import normalize_attachment_media

    raw = normalize_attachment_media(
        message.attachment_media if isinstance(message.attachment_media, list) else [],
        message_scope=message.pk,
    )
    output = []
    for index, item in enumerate(raw):
        part = {
            "source_part_id": str(item["source_part_id"])[:64],
            "original_index": int(item["original_index"]),
            "identity_origin": str(item.get("identity_origin") or "")[:32],
            "type": str(item.get("type") or item.get("media_type") or "unknown")[:32],
            "role": str(item.get("role") or "attachment")[:48],
            "provider_object_id": str(
                item.get("provider_object_id")
                or item.get("object_id")
                or item.get("asset_id")
                or ""
            )[:255],
        }
        output.append(part)
    return output


def _safe_referral(value) -> dict:
    if not isinstance(value, Mapping):
        return {}
    output = {
        key: str(value.get(key) or "")[:255]
        for key in _ALLOWED_REFERRAL_FIELDS
        if str(value.get(key) or "").strip()
    }
    output["source_digest"] = _digest(dict(value))
    return output


def _source_payload(message, *, metadata=None, previous=None, ordinal: int) -> dict:
    metadata = dict(metadata or {})
    namespace = str(
        metadata.get("source_namespace")
        or getattr(message, "provider_namespace", "")
        or getattr(previous, "source_namespace", "")
        or ""
    )[:128]
    referral = (
        _safe_referral(metadata.get("referral"))
        if "referral" in metadata
        else copy.deepcopy(getattr(previous, "referral", {}) or {})
    )
    media = _discovered_media(message)
    text = str(message.text or "")
    payload = {
        "message_id": int(message.pk),
        "ordinal": int(ordinal),
        "role": str(message.role or "")[:8],
        "source_namespace": namespace,
        "provider_message_id": str(message.mid or "")[:255],
        "synthetic_event_key": str(message.synthetic_event_key or "")[:64],
        "text": text,
        "provider_created_at": (
            message.provider_created_at.isoformat()
            if message.provider_created_at else ""
        ),
        "reply_to_provider_message_id": str(
            message.reply_to_provider_message_id or ""
        )[:255],
        "quick_reply_payload": str(message.quick_reply_payload or "")[:1000],
        "referral": referral,
        "discovered_media": media,
        "text_chars": len(text),
        "media_part_count": len(media),
    }
    payload["source_digest"] = _digest(payload)
    return payload


def _overflow_reason(payloads: list[dict]) -> str:
    if len(payloads) > MAX_SOURCES:
        return "source_count_exceeded"
    if any(item["media_part_count"] > MAX_PARTS_PER_SOURCE for item in payloads):
        return "source_media_parts_exceeded"
    if sum(item["text_chars"] for item in payloads) > MAX_TEXT_CHARS:
        return "text_chars_exceeded"
    if sum(item["media_part_count"] for item in payloads) > MAX_MEDIA_PARTS:
        return "media_parts_exceeded"
    return ""


def prospective_overflow_reason(
    source_messages: Iterable[InstagramBotMessage],
) -> str:
    """Check whole-source capacity before a caller writes turn membership."""
    payloads = [
        _source_payload(message, ordinal=index)
        for index, message in enumerate(source_messages or (), start=1)
    ]
    return _overflow_reason(payloads)


def _create_source_rows(revision, payloads: list[dict]) -> None:
    IgTurnRevisionSource.objects.bulk_create([
        IgTurnRevisionSource(
            revision=revision,
            message_id=item["message_id"],
            ordinal=item["ordinal"],
            role=item["role"],
            source_namespace=item["source_namespace"],
            provider_message_id=item["provider_message_id"],
            synthetic_event_key=item["synthetic_event_key"],
            text=item["text"],
            provider_created_at=(
                datetime.fromisoformat(item["provider_created_at"])
                if item["provider_created_at"] else None
            ),
            reply_to_provider_message_id=item["reply_to_provider_message_id"],
            quick_reply_payload=item["quick_reply_payload"],
            referral=item["referral"],
            discovered_media=item["discovered_media"],
            text_chars=item["text_chars"],
            media_part_count=item["media_part_count"],
            source_digest=item["source_digest"],
        )
        for item in payloads
    ])


def create_collecting_revision(
    turn: IgCustomerTurn | int,
    source_messages: Iterable[InstagramBotMessage],
    *,
    source_metadata: Mapping[int, Mapping] | None = None,
    now=None,
    bypass_quiet: bool = False,
    overall_deadline=None,
) -> RevisionBuildResult:
    """Create the next client-head revision without changing turn membership."""
    turn_id = int(getattr(turn, "pk", turn) or 0)
    messages = list(source_messages or ())
    if not turn_id or not messages:
        return RevisionBuildResult(None, False, reason="sources_missing")
    if any(not getattr(message, "pk", None) for message in messages):
        return RevisionBuildResult(None, False, reason="source_unsaved")
    if len({message.pk for message in messages}) != len(messages):
        return RevisionBuildResult(None, False, reason="source_duplicate")
    metadata = dict(source_metadata or {})
    now = _aware(now)

    with transaction.atomic():
        locked_turn = IgCustomerTurn.objects.select_related("client").get(pk=turn_id)
        client = IgClient.objects.select_for_update().get(pk=locked_turn.client_id)
        if any(message.client_id != client.pk for message in messages):
            return RevisionBuildResult(None, False, reason="source_client_mismatch")
        memberships = {
            row.message_id: row.role
            for row in IgTurnMessage.objects.filter(
                turn_id=locked_turn.pk,
                message_id__in=[message.pk for message in messages],
            ).only("message_id", "role")
        }
        if set(memberships) != {message.pk for message in messages}:
            return RevisionBuildResult(None, False, reason="source_turn_mismatch")
        if any(
            str(memberships[message.pk] or "") != str(message.role or "")
            for message in messages
        ):
            return RevisionBuildResult(None, False, reason="source_role_mismatch")
        head = (
            IgCustomerTurnRevision.objects.select_for_update()
            .filter(client_id=client.pk, active_slot=1)
            .first()
        )
        latest_number = int(
            IgCustomerTurnRevision.objects.filter(client_id=client.pk)
            .order_by("-revision")
            .values_list("revision", flat=True)
            .first()
            or 0
        )
        previous_by_message = {}
        if head is not None:
            previous_by_message = {
                row.message_id: row
                for row in head.sources.all().order_by("ordinal", "id")
            }
        payloads = [
            _source_payload(
                message,
                metadata=metadata.get(message.pk),
                previous=previous_by_message.get(message.pk),
                ordinal=index,
            )
            for index, message in enumerate(messages, start=1)
        ]
        overflow_reason = _overflow_reason(payloads)
        same_collecting_turn = bool(
            head is not None
            and head.turn_id == locked_turn.pk
            and head.state in {
                IgCustomerTurnRevision.State.COLLECTING,
                IgCustomerTurnRevision.State.PREPARING,
            }
        )
        quiet_started_at = head.quiet_started_at if same_collecting_turn else now
        quiet_cap_at = (
            head.quiet_cap_at
            if same_collecting_turn
            else quiet_started_at + timedelta(seconds=QUIET_CAP_SECONDS)
        )
        inherited_overall = (
            head.overall_deadline
            if same_collecting_turn and head.overall_deadline > now
            else None
        )
        requested_overall = (
            _aware(overall_deadline) if overall_deadline is not None else None
        )
        overall = inherited_overall or requested_overall or (
            now + timedelta(seconds=OVERALL_DEADLINE_SECONDS)
        )
        quiet_deadline = now if bypass_quiet else min(
            now + timedelta(seconds=QUIET_SECONDS), quiet_cap_at, overall
        )

        if head is not None:
            head.active_slot = None
            update_fields = ["active_slot", "updated_at"]
            if head.state in {
                IgCustomerTurnRevision.State.COLLECTING,
                IgCustomerTurnRevision.State.PREPARING,
                IgCustomerTurnRevision.State.SEALED,
            }:
                head.state = IgCustomerTurnRevision.State.SUPERSEDED
                head.claim_token = ""
                head.lease_until = None
                update_fields.extend(["state", "claim_token", "lease_until"])
            head.save(update_fields=update_fields)

        revision = IgCustomerTurnRevision.objects.create(
            client=client,
            turn=locked_turn,
            parent=head,
            revision=latest_number + 1,
            active_slot=1,
            state=(
                IgCustomerTurnRevision.State.OVERFLOW
                if overflow_reason else IgCustomerTurnRevision.State.COLLECTING
            ),
            quiet_started_at=quiet_started_at,
            quiet_deadline=quiet_deadline,
            quiet_cap_at=quiet_cap_at,
            overall_deadline=overall,
            source_count=len(payloads),
            text_chars=sum(item["text_chars"] for item in payloads),
            media_part_count=sum(item["media_part_count"] for item in payloads),
            permission_epoch=int(client.reply_permission_epoch or 0),
            erasure_started_at_snapshot=client.privacy_erasure_started_at,
            overflow=(
                {
                    "reason": overflow_reason,
                    "source_message_ids": [item["message_id"] for item in payloads],
                    "source_count": len(payloads),
                    "text_chars": sum(item["text_chars"] for item in payloads),
                    "media_part_count": sum(
                        item["media_part_count"] for item in payloads
                    ),
                    "successor_required": True,
                }
                if overflow_reason else {}
            ),
        )
        if overflow_reason:
            return RevisionBuildResult(
                revision, True, successor_required=True, reason=overflow_reason
            )
        _create_source_rows(revision, payloads)
        return RevisionBuildResult(revision, True, reason="created")


def claim_revision_preparation(revision_id: int, *, now=None) -> RevisionClaim:
    """CAS one due collecting revision or reclaim an expired preparation lease."""
    now = _aware(now)
    with transaction.atomic():
        revision = IgCustomerTurnRevision.objects.select_for_update().filter(
            pk=revision_id, active_slot=1
        ).first()
        if revision is None:
            return RevisionClaim(None, reason="not_current")
        turn_terminal = IgCustomerTurn.objects.filter(pk=revision.turn_id).values(
            "claim_state", "terminal_reason"
        ).first()
        if turn_terminal and (
            turn_terminal["claim_state"]
            in {
                IgCustomerTurn.ClaimState.PROCESSED,
                IgCustomerTurn.ClaimState.SUPERSEDED,
            }
            or str(turn_terminal["terminal_reason"] or "")
        ):
            return RevisionClaim(revision, reason="legacy_turn_terminal")
        reclaim = bool(
            revision.state == revision.State.PREPARING
            and revision.lease_until
            and revision.lease_until <= now
        )
        if revision.state != revision.State.COLLECTING and not reclaim:
            return RevisionClaim(revision, reason="not_collecting")
        if revision.state == revision.State.COLLECTING and revision.quiet_deadline > now:
            return RevisionClaim(revision, reason="quiet_window")
        reserve_boundary = revision.overall_deadline - timedelta(
            seconds=SEND_RESERVE_SECONDS
        )
        media_deadline = min(
            now + timedelta(seconds=MEDIA_PREPARE_BUDGET_SECONDS),
            reserve_boundary,
        )
        if media_deadline < now:
            media_deadline = now
        token = secrets.token_hex(16)
        revision.state = revision.State.PREPARING
        revision.claim_token = token
        revision.claimed_at = now
        revision.media_prepare_deadline = media_deadline
        revision.lease_until = min(
            now + timedelta(seconds=PREPARATION_LEASE_SECONDS),
            revision.overall_deadline,
        )
        revision.save(update_fields=[
            "state", "claim_token", "claimed_at", "media_prepare_deadline",
            "lease_until", "updated_at",
        ])
        return RevisionClaim(revision, token, media_deadline, "claimed")


def _capture_state(item: Mapping) -> str:
    return str(item.get("capture_state") or item.get("status") or "").casefold()


def _sealed_media_parts(
    source,
    message,
    *,
    deadline_reached: bool,
    current_client_owner_valid: bool,
) -> tuple[list[dict], bool]:
    from management.services.ig_media_manifest import normalize_attachment_media
    from management.services.ig_media_url_policy import (
        SUPPORTED_INLINE_AUDIO_MIMES,
        SUPPORTED_INLINE_IMAGE_MIMES,
    )

    current = normalize_attachment_media(
        message.attachment_media if isinstance(message.attachment_media, list) else [],
        message_scope=message.pk,
    )
    current_by_id = {
        str(item.get("source_part_id") or ""): item
        for item in current if isinstance(item, Mapping) and item.get("source_part_id")
    }
    discovered = list(source.discovered_media or [])
    discovered_ids = {
        str(item.get("source_part_id") or "")
        for item in discovered if isinstance(item, Mapping)
    }
    if len(current) > len(discovered) or set(current_by_id) - discovered_ids:
        raise ValueError("source_media_changed")
    output = []
    has_pending = False
    for discovered_item in discovered:
        part_id = str(discovered_item.get("source_part_id") or "")
        item = current_by_id.get(part_id, {})
        state = _capture_state(item)
        retry_pending = bool(
            item.get("capture_retryable") is True
            and item.get("capture_terminal") is not True
        )
        if state in _OWNED_MEDIA_STATES:
            content_hash = str(item.get("content_hash") or "").casefold()
            mime = str(item.get("mime") or "")[:100]
            try:
                byte_length = max(0, int(item.get("bytes") or 0))
            except (TypeError, ValueError):
                byte_length = 0
            storage_name = str(item.get("storage_name") or "").strip()
            if (
                storage_name
                and byte_length > 0
                and mime.casefold() in (
                    SUPPORTED_INLINE_IMAGE_MIMES | SUPPORTED_INLINE_AUDIO_MIMES
                )
                and re.fullmatch(r"[0-9a-f]{64}", content_hash)
                and item.get("private_storage") is True
                and current_client_owner_valid
                and message.private_media_state
                == InstagramBotMessage.PrivateMediaState.ACTIVE
            ):
                outcome = "owned"
                reason = ""
            else:
                outcome = "unavailable"
                reason = "owned_evidence_invalid"
        elif (
            state in _PENDING_MEDIA_STATES
            and item.get("capture_terminal") is not True
        ) or retry_pending:
            has_pending = not deadline_reached or has_pending
            outcome = "unavailable" if deadline_reached else "pending"
            reason = "media_prepare_deadline" if deadline_reached else "capture_pending"
        else:
            outcome = "unavailable"
            failure_class = str(
                item.get("capture_failure_class")
                or item.get("failure_class")
                or ""
            ).casefold()
            if failure_class == "expired":
                reason = "source_expired"
            elif failure_class == "permanent":
                reason = "capture_failed"
            else:
                reason = _SEALED_FAILURE_REASONS.get(
                    state, "capture_unavailable"
                )
        part = {
            **{key: discovered_item.get(key) for key in _ALLOWED_MEDIA_FIELDS},
            "capture_outcome": outcome,
            "reason": reason,
            "owner_ref": {
                "message_id": source.message_id,
                "source_part_id": part_id,
            },
        }
        if outcome == "owned":
            part.update({
                "mime": mime,
                "bytes": byte_length,
                "content_hash": content_hash,
            })
        output.append(part)
    return output, has_pending


def seal_revision(revision_id: int, token: str, *, now=None) -> RevisionSealResult:
    """Write the bundle snapshot exactly once after media completion/deadline."""
    now = _aware(now)
    revision = IgCustomerTurnRevision.objects.filter(pk=revision_id).first()
    if revision is None:
        return RevisionSealResult(None, False, "missing")
    if revision.state in {revision.State.SEALED, revision.State.CLAIMED}:
        return RevisionSealResult(revision, True, "already_sealed")
    if (
        revision.state != revision.State.PREPARING
        or not token
        or revision.claim_token != token
        or revision.active_slot != 1
    ):
        return RevisionSealResult(revision, False, "claim_lost")
    media_deadline = revision.media_prepare_deadline or now
    deadline_reached = now >= media_deadline
    sources = list(
        revision.sources.select_related("message").order_by("ordinal", "id")
    )
    if len(sources) != revision.source_count:
        return RevisionSealResult(revision, False, "source_set_changed")
    snapshot_sources = []
    any_pending = False
    current_owner_igsid = IgClient.objects.filter(
        pk=revision.client_id,
        hidden_at__isnull=True,
        is_blocked=False,
        privacy_erasure_started_at__isnull=True,
    ).values_list("igsid", flat=True).first()
    current_client_owner_valid = bool(
        current_owner_igsid and revision.erasure_started_at_snapshot is None
    )
    try:
        for source in sources:
            message_owner_valid = bool(
                current_client_owner_valid
                and source.message.client_id == revision.client_id
                and source.message.role == InstagramBotMessage.Role.USER
                and source.message.source == "webhook"
                and str(source.message.sender_id or "") == current_owner_igsid
            )
            media, pending = _sealed_media_parts(
                source,
                source.message,
                deadline_reached=deadline_reached,
                current_client_owner_valid=message_owner_valid,
            )
            any_pending = any_pending or pending
            snapshot_sources.append({
                "revision_source_id": source.pk,
                "message_id": source.message_id,
                "ordinal": source.ordinal,
                "role": source.role,
                "source_namespace": source.source_namespace,
                "provider_message_id": source.provider_message_id,
                "synthetic_event_key": source.synthetic_event_key,
                "text": source.text,
                "provider_created_at": (
                    source.provider_created_at.isoformat()
                    if source.provider_created_at else ""
                ),
                "reply_to_provider_message_id": source.reply_to_provider_message_id,
                "quick_reply_payload": source.quick_reply_payload,
                "referral": source.referral,
                "source_digest": source.source_digest,
                "media_parts": media,
            })
    except (TypeError, ValueError):
        return RevisionSealResult(revision, False, "source_media_changed")
    if any_pending and not deadline_reached:
        return RevisionSealResult(revision, False, "media_pending")
    snapshot = {
        "version": SNAPSHOT_VERSION,
        "client_revision": revision.revision,
        "turn_id": revision.turn_id,
        "permission_epoch": revision.permission_epoch,
        "erasure_started_at": (
            revision.erasure_started_at_snapshot.isoformat()
            if revision.erasure_started_at_snapshot else ""
        ),
        "sources": snapshot_sources,
        "coverage": {
            "source_count": len(snapshot_sources),
            "text_chars": sum(len(item["text"]) for item in snapshot_sources),
            "media_part_count": sum(
                len(item["media_parts"]) for item in snapshot_sources
            ),
            "owned_media_parts": sum(
                part["capture_outcome"] == "owned"
                for item in snapshot_sources for part in item["media_parts"]
            ),
            "unavailable_media_parts": sum(
                part["capture_outcome"] == "unavailable"
                for item in snapshot_sources for part in item["media_parts"]
            ),
        },
    }
    digest = _digest(snapshot)
    with transaction.atomic():
        locked = IgCustomerTurnRevision.objects.select_for_update().filter(
            pk=revision_id
        ).first()
        if (
            locked is None
            or locked.active_slot != 1
            or locked.state != locked.State.PREPARING
            or locked.claim_token != token
        ):
            return RevisionSealResult(locked, False, "claim_lost")
        locked.bundle_snapshot = snapshot
        locked.snapshot_digest = digest
        locked.sealed_at = now
        locked.state = locked.State.SEALED
        locked.claim_token = ""
        locked.claimed_at = None
        locked.lease_until = None
        locked.save(update_fields=[
            "bundle_snapshot", "snapshot_digest", "sealed_at", "state",
            "claim_token", "claimed_at", "lease_until", "updated_at",
        ])
        return RevisionSealResult(locked, True, "sealed")


def claim_sealed_revision(revision_id: int, *, now=None) -> RevisionClaim:
    """Claim one current sealed revision; effects still require B03.4/B03.5."""
    now = _aware(now)
    token = secrets.token_hex(16)
    lease_until = now + timedelta(seconds=EXECUTION_LEASE_SECONDS)
    claimed = IgCustomerTurnRevision.objects.filter(
        pk=revision_id,
        active_slot=1,
        state=IgCustomerTurnRevision.State.SEALED,
        snapshot_digest__gt="",
    ).exclude(
        turn__claim_state__in=(
            IgCustomerTurn.ClaimState.PROCESSED,
            IgCustomerTurn.ClaimState.SUPERSEDED,
        )
    ).exclude(turn__terminal_reason__gt="").update(
        state=IgCustomerTurnRevision.State.CLAIMED,
        claim_token=token,
        claimed_at=now,
        lease_until=lease_until,
        updated_at=now,
    )
    revision = IgCustomerTurnRevision.objects.filter(pk=revision_id).first()
    return RevisionClaim(
        revision,
        token if claimed == 1 else "",
        reason="claimed" if claimed == 1 else "claim_conflict",
    )


def terminalize_legacy_shadow_revision(
    turn: IgCustomerTurn | int,
    *,
    reason: str,
    now=None,
) -> bool:
    """Retire a definite old-engine result without inventing a sealed bundle.

    The finite reason remains on ``IgCustomerTurn.terminal_reason``.  UNKNOWN
    or provider-started sources stay non-completed, but the terminal turn fence
    above still prevents a later revision claimant from replaying them.
    """
    turn_id = int(getattr(turn, "pk", turn) or 0)
    reason = str(reason or "")
    definite_reasons = {
        IgCustomerTurn.TerminalReason.REPLIED,
        IgCustomerTurn.TerminalReason.NO_REPLY_NEEDED,
        IgCustomerTurn.TerminalReason.FAILED,
    }
    if not turn_id or reason not in definite_reasons:
        return False
    now = _aware(now)
    with transaction.atomic():
        revision = (
            IgCustomerTurnRevision.objects.select_for_update()
            .filter(turn_id=turn_id, active_slot=1)
            .first()
        )
        if revision is None or revision.state not in {
            revision.State.COLLECTING,
            revision.State.PREPARING,
            revision.State.SEALED,
        }:
            return False
        turn_row = IgCustomerTurn.objects.filter(pk=turn_id).values(
            "claim_state", "terminal_reason"
        ).first()
        if not turn_row or (
            turn_row["claim_state"] != IgCustomerTurn.ClaimState.PROCESSED
            or str(turn_row["terminal_reason"] or "") != reason
        ):
            return False
        sources = list(
            revision.sources.values_list(
                "message__status", "message__send_state"
            )
        )
        if len(sources) != revision.source_count or not sources:
            return False
        terminal_statuses = {
            InstagramBotMessage.Status.DONE,
            InstagramBotMessage.Status.FAILED,
        }
        uncertain_sends = {"sending", "unknown", "ambiguous"}
        if any(
            status not in terminal_statuses or str(send_state or "") in uncertain_sends
            for status, send_state in sources
        ):
            return False
        revision.state = revision.State.PROCESSED
        revision.processed_at = now
        revision.claim_token = ""
        revision.claimed_at = None
        revision.lease_until = None
        revision.save(update_fields=[
            "state", "processed_at", "claim_token", "claimed_at",
            "lease_until", "updated_at",
        ])
        return True


def revision_claim_is_current(revision_id: int, token: str) -> bool:
    """Read-only CAS predicate for the later B03.4 final boundary."""
    if not token:
        return False
    return IgCustomerTurnRevision.objects.filter(
        pk=revision_id,
        active_slot=1,
        state=IgCustomerTurnRevision.State.CLAIMED,
        claim_token=token,
        lease_until__gt=timezone.now(),
    ).exists()


def current_revision_for_turn(
    turn: IgCustomerTurn | int,
) -> IgCustomerTurnRevision | None:
    """Return this turn's active client head for future claim/collection."""
    turn_id = int(getattr(turn, "pk", turn) or 0)
    if not turn_id:
        return None
    return IgCustomerTurnRevision.objects.filter(
        turn_id=turn_id, active_slot=1
    ).order_by("-revision").first()


def replay_snapshot(revision_id: int) -> dict | None:
    """Return a digest-verified copy; never reconstruct from mutable messages."""
    revision = IgCustomerTurnRevision.objects.filter(
        pk=revision_id, snapshot_digest__gt=""
    ).only("bundle_snapshot", "snapshot_digest").first()
    if revision is None or _digest(revision.bundle_snapshot) != revision.snapshot_digest:
        return None
    return copy.deepcopy(revision.bundle_snapshot)


__all__ = [
    "MAX_MEDIA_PARTS", "MAX_SOURCES", "MAX_TEXT_CHARS",
    "RevisionBuildResult", "RevisionClaim", "RevisionSealResult",
    "claim_revision_preparation", "claim_sealed_revision",
    "create_collecting_revision", "current_revision_for_turn",
    "prospective_overflow_reason", "replay_snapshot",
    "revision_claim_is_current", "seal_revision",
    "terminalize_legacy_shadow_revision",
]
