"""Manager-reviewed UGC rewards for assigned Instagram orders."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import string
import unicodedata
import re
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlsplit, urlunsplit

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from orders.fulfillment_truth import (
    nova_poshta_delivery_confirmed_at,
    nova_poshta_order_fulfillment_confirmed,
)


class UgcRewardConflict(ValueError):
    """The evidence cannot authorize a reward for this order."""


def _normalize_instagram_url(raw_url: str) -> str:
    value = str(raw_url or "").strip()
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme.lower() != "https" or not (
        host == "instagram.com" or host.endswith(".instagram.com")
    ):
        raise UgcRewardConflict("Потрібне HTTPS-посилання на Instagram.")
    if not parsed.path or parsed.path == "/":
        raise UgcRewardConflict("Посилання Instagram не містить публікацію або stories.")
    netloc = host
    if parsed.port:
        netloc = f"{host}:{parsed.port}"
    path = parsed.path.rstrip("/") + "/"
    return urlunsplit(("https", netloc, path, "", ""))


def _fingerprint(kind: str, value: str) -> str:
    return hashlib.sha256(f"{kind}:{value}".encode("utf-8")).hexdigest()


def _new_promo_code() -> str:
    from storefront.models import PromoCode

    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "UGC" + "".join(secrets.choice(alphabet) for _ in range(9))
        if not PromoCode.objects.filter(code=code).exists():
            return code


def reward_payload(reward) -> dict:
    order = getattr(reward, "order", None)
    reviewer = getattr(reward, "reviewed_by", None)
    return {
        "id": reward.pk,
        "client_id": reward.client_id,
        "order_id": reward.order_id,
        "order_number": (
            (order.order_number or str(order.pk)) if order is not None else ""
        ),
        "assignment_id": reward.assignment_id,
        "assignment_version": reward.assignment_version,
        "evidence_type": reward.evidence_type,
        "evidence_message_id": reward.evidence_message_id,
        "evidence_url": reward.evidence_url,
        "review_note": reward.review_note,
        "promo_code": reward.promo_code.code,
        "valid_until": (
            reward.promo_code.valid_until.isoformat()
            if reward.promo_code.valid_until
            else ""
        ),
        "reviewed_by": (
            (reviewer.get_full_name() or reviewer.get_username())
            if reviewer is not None
            else ""
        ),
        "reward_path": reward.reward_path,
        "decision_source": reward.decision_source,
        "assessment_id": reward.assessment_id,
        "assessment_generation": reward.assessment_generation_snapshot,
        "policy_version": reward.policy_version_snapshot,
        "provider_object_digest": reward.provider_object_digest_snapshot,
        "catalog_candidates": list(reward.catalog_candidates_snapshot or []),
        "issued_at": reward.issued_at.isoformat(),
        "reviewed_at": reward.reviewed_at.isoformat(),
        # An issued reward is deliberately never eligible for a second grant;
        # keep this explicit in every manager/API item so clients do not infer
        # eligibility from the presence of an order or a promo code.
        "reward_eligible": False,
        "eligibility_reason": "already_rewarded",
    }


def _normalize_igsid(value) -> str:
    """Return the only identity form allowed in a lifetime digest."""
    return unicodedata.normalize("NFKC", str(value or "")).strip().casefold()


_IDENTITY_KEY_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,24}$")


def _identity_hmac_keyring() -> tuple[tuple[str, bytes], ...]:
    """Return the active identity key followed by retained verification keys."""
    from django.conf import settings

    raw = getattr(settings, "IG_UGC_IDENTITY_HMAC_KEYRING", {})
    active_id = str(
        getattr(settings, "IG_UGC_IDENTITY_HMAC_ACTIVE_KEY_ID", "") or ""
    ).strip()
    if not isinstance(raw, dict) or not raw or active_id not in raw:
        raise UgcRewardConflict(
            "Не налаштовано versioned HMAC keyring для UGC lifetime identity."
        )
    normalized: dict[str, bytes] = {}
    for raw_key_id, raw_secret in raw.items():
        key_id = str(raw_key_id or "").strip()
        secret = str(raw_secret or "")
        if not _IDENTITY_KEY_ID_RE.fullmatch(key_id) or len(secret.encode("utf-8")) < 32:
            raise UgcRewardConflict("UGC identity HMAC keyring має невалідний ключ.")
        normalized[key_id] = secret.encode("utf-8")
    if active_id not in normalized:
        raise UgcRewardConflict("Активний UGC identity HMAC ключ невалідний.")
    ordered_ids = [active_id, *sorted(key_id for key_id in normalized if key_id != active_id)]
    return tuple((key_id, normalized[key_id]) for key_id in ordered_ids)


def _identity_digest_candidates(client) -> tuple[str, ...]:
    """Compute active and retained digests without persisting a raw IGSID."""
    normalized_igsid = _normalize_igsid(getattr(client, "igsid", ""))
    if not normalized_igsid:
        raise UgcRewardConflict("У клієнта відсутній Instagram identity.")
    material = f"instagram-ugc-lifetime:v1:{normalized_igsid}".encode("utf-8")
    return tuple(
        f"{key_id}:{hmac.new(secret, material, hashlib.sha256).hexdigest()}"
        for key_id, secret in _identity_hmac_keyring()
    )


def _identity_digest(client) -> str:
    """Return the active versioned digest used for newly created slots."""
    return _identity_digest_candidates(client)[0]


def _lifetime_slot_for_client(client):
    """Lock or create the one durable slot for a normalized Instagram identity.

    The client row is locked by callers before entering this helper.  The
    digest remains the cross-row identity boundary, so a privacy delete and a
    later client recreation cannot create a fresh lifetime grant.  The nested
    savepoint handles the unique-key race on MariaDB when two workers create a
    slot before either can observe the other's insert.
    """
    from management.ig_bot_models import IgUgcRewardLifetime

    digests = _identity_digest_candidates(client)
    digest = digests[0]
    matching_slots = list(
        IgUgcRewardLifetime.objects.select_for_update()
        .filter(identity_digest__in=digests)
        .order_by("id")[:2]
    )
    if len(matching_slots) > 1:
        raise UgcRewardConflict(
            "Для Instagram identity знайдено кілька lifetime slots після ротації ключа."
        )
    lifetime = matching_slots[0] if matching_slots else None
    if lifetime is None:
        # A release can encounter a lifetime row written by the old client-pk
        # digest implementation.  Rebind it to the stable digest only when
        # there is no already-consumed stable slot for this IGSID.
        legacy_slot = (
            IgUgcRewardLifetime.objects.select_for_update()
            .filter(client_id=client.pk)
            .first()
        )
        if legacy_slot is not None:
            try:
                with transaction.atomic():
                    legacy_slot.identity_digest = digest
                    legacy_slot.save(update_fields=["identity_digest", "updated_at"])
            except IntegrityError:
                lifetime = (
                    IgUgcRewardLifetime.objects.select_for_update()
                    .get(identity_digest=digest)
                )
            else:
                lifetime = legacy_slot
    if lifetime is None:
        try:
            with transaction.atomic():
                lifetime = IgUgcRewardLifetime.objects.create(
                    client_id=client.pk,
                    identity_digest=digest,
                )
        except IntegrityError:
            lifetime = (
                IgUgcRewardLifetime.objects.select_for_update()
                .get(identity_digest=digest)
            )
    elif lifetime.client_id != client.pk:
        # The row may have survived a privacy deletion.  Reattach only the
        # current non-sensitive client pointer; the consumed marker/reward is
        # authoritative and is never reset here.
        if lifetime.client_id is None:
            lifetime.client_id = client.pk
            lifetime.save(update_fields=["client", "updated_at"])
        else:
            raise UgcRewardConflict(
                "Instagram identity вже прив'язана до іншого lifetime slot owner."
            )
    return lifetime


def _legacy_reward_for_client(client, *, lock=False):
    """Preflight rows created before the lifetime slot existed.

    Multiple historical grants are an unresolved data conflict.  Selecting a
    winner would silently violate the one-lifetime invariant, so issuance
    fails closed and an operator can reconcile the duplicate explicitly.
    """
    from management.ig_bot_models import IgUgcReward

    queryset = IgUgcReward.objects.filter(client_id=client.pk)
    if lock:
        queryset = queryset.select_for_update()
    rows = list(queryset.order_by("issued_at", "id")[:2])
    if len(rows) > 1:
        raise UgcRewardConflict("Для Instagram identity знайдено кілька історичних UGC-нагород.")
    return rows[0] if rows else None


def _existing_lifetime_reward(lifetime):
    if not lifetime.reward_id:
        return None
    from management.ig_bot_models import IgUgcReward

    return (
        IgUgcReward.objects.select_related("promo_code", "order", "reviewed_by")
        .filter(pk=lifetime.reward_id)
        .first()
    )


def ugc_service_case_reason(client) -> str:
    """Return a durable suppression reason while the customer needs service.

    A post-sale case is authoritative when one is open.  If no case exists,
    the latest non-manager conversation analysis still protects an active
    complaint/return/exchange turn before a case row has been opened.
    """
    if not client or not getattr(client, "pk", None):
        return ""
    from management.ig_bot_models import IgConversationAnalysisSnapshot
    from management.services.ig_post_sale import open_service_case

    if open_service_case(client) is not None:
        return "service_case_open"
    interaction_types = IgConversationAnalysisSnapshot.InteractionType
    latest = (
        IgConversationAnalysisSnapshot.objects.filter(client_id=client.pk)
        .exclude(interaction_type=interaction_types.MANAGER_OBSERVATION)
        .order_by("-id")
        .values_list("interaction_type", flat=True)
        .first()
    )
    if latest in {
        interaction_types.SUPPORT_COMPLAINT,
        interaction_types.EXCHANGE_REQUEST,
        interaction_types.RETURN_REQUEST,
    }:
        return "service_case_open"
    return ""


def ugc_identity_already_rewarded(client) -> bool:
    """Return whether this identity has consumed its one lifetime UGC grant."""
    from management.ig_bot_models import IgUgcRewardLifetime

    digests = _identity_digest_candidates(client)
    lifetime = IgUgcRewardLifetime.objects.filter(identity_digest__in=digests).first()
    if lifetime is not None and (lifetime.reward_id or lifetime.consumed_at):
        return True
    client_id = getattr(client, "pk", None)
    if not client_id:
        return False
    if IgUgcRewardLifetime.objects.filter(client_id=client_id).exclude(
        identity_digest__in=digests,
    ).filter(Q(reward_id__isnull=False) | Q(consumed_at__isnull=False)).exists():
        return True
    return _legacy_reward_for_client(client) is not None


def ugc_reward_eligibility(client, *, assignments=None, now=None) -> tuple[bool, str]:
    """Return a manager-safe eligibility decision for the current identity."""
    from management.ig_bot_models import (
        IgOrderAssignment,
        IgUgcEvidenceAssessment,
        IgUgcRewardLifetime,
    )

    del now  # reserved for time-bounded policy extensions
    digests = _identity_digest_candidates(client)
    lifetime = IgUgcRewardLifetime.objects.filter(identity_digest__in=digests).first()
    if lifetime is not None and (lifetime.reward_id or lifetime.consumed_at):
        return False, "already_rewarded"
    if getattr(client, "pk", None) and IgUgcRewardLifetime.objects.filter(
        client_id=client.pk,
    ).exclude(identity_digest__in=digests).exists():
        return False, "already_rewarded"
    if getattr(client, "pk", None) and _legacy_reward_for_client(client) is not None:
        return False, "already_rewarded"
    service_reason = ugc_service_case_reason(client)
    if service_reason:
        return False, service_reason
    assessment = (
        IgUgcEvidenceAssessment.objects.filter(client_id=getattr(client, "pk", None))
        .order_by("-created_at", "-id")
        .first()
    )
    if assessment is not None and assessment.decision in {
        IgUgcEvidenceAssessment.Decision.QUALIFIED_AUTO,
        IgUgcEvidenceAssessment.Decision.MANAGER_APPROVED,
    }:
        try:
            from management.services.ig_ugc_assessment import validate_ugc_provenance

            validate_ugc_provenance(
                assessment=assessment,
                client=client,
                lock=False,
            )
        except Exception:
            return False, "assessment_provenance_invalid"
        return True, "qualified_assessment"
    if assignments is None:
        assignments = IgOrderAssignment.objects.filter(
            client_id=getattr(client, "pk", None),
            unassigned_at__isnull=True,
        ).select_related("order")
    if any(
        nova_poshta_order_fulfillment_confirmed(assignment.order)
        for assignment in assignments
    ):
        return True, "delivered_order_eligible"
    if assessment is None:
        return False, "awaiting_ugc_evidence"
    if assessment.decision == IgUgcEvidenceAssessment.Decision.NEEDS_MANAGER_REVIEW:
        return False, "manager_review_required"
    if assessment.decision == IgUgcEvidenceAssessment.Decision.PENDING:
        return False, "assessment_pending"
    if assessment.decision == IgUgcEvidenceAssessment.Decision.REJECTED:
        return False, "evidence_rejected"
    return False, "awaiting_ugc_evidence"


def _validate_external_assessment(*, assessment, client) -> None:
    """Keep the reward service fail-closed even when called outside the API.

    The assessment endpoint is not the trust boundary: workers, management
    commands, and future integrations can call this service directly.  A
    model-written ``qualified_auto`` row without provider identity must never
    be enough to mint a bearer code.
    """
    from management.services.ig_ugc_assessment import (
        UgcProvenanceError,
        validate_ugc_provenance,
    )

    try:
        validate_ugc_provenance(
            assessment=assessment,
            client=client,
            lock=True,
        )
    except UgcProvenanceError as exc:
        raise UgcRewardConflict("UGC не має достатньої provider provenance.") from exc


def _with_ugc_delivery(reward, created):
    """Keep the lifetime grant and its immutable customer outbox atomic."""
    queue_external_ugc_reward_delivery(reward)
    return reward, created


def _create_locked_ugc_grant(
    *,
    locked_client,
    lifetime,
    now,
    promo_description,
    reward_fields,
):
    """Create promo, reward, lifetime consumption, and outbox as one unit.

    Both external and delivered-order paths reach this factory only after
    locking the Instagram client and resolving the shared lifetime slot.
    Keeping the four durable records here prevents policy drift between paths.
    """
    from django.db import connection
    from management.ig_bot_models import IgUgcReward
    from storefront.models import PromoCode

    if not connection.in_atomic_block:
        raise RuntimeError("UGC grant factory requires an atomic transaction")
    if lifetime.reward_id or lifetime.consumed_at:
        raise UgcRewardConflict("Для цієї Instagram identity UGC-нагороду вже було видано.")
    promo = PromoCode.objects.create(
        code=_new_promo_code(),
        promo_type="regular",
        discount_type="percentage",
        discount_value=Decimal("10.00"),
        description=str(promo_description or "TwoComms UGC reward")[:255],
        max_uses=1,
        one_time_per_user=False,
        guest_redeemable=True,
        valid_from=now,
        valid_until=now + timedelta(days=90),
        is_active=True,
    )
    reward = IgUgcReward.objects.create(
        client_id=locked_client.pk,
        promo_code=promo,
        issued_at=now,
        reviewed_at=now,
        lifetime_slot_key=_identity_digest(locked_client),
        **reward_fields,
    )
    lifetime.reward = reward
    lifetime.consumed_at = now
    lifetime.save(update_fields=["reward", "consumed_at", "updated_at"])
    return _with_ugc_delivery(reward, True)


@transaction.atomic
def award_external_ugc_reward(*, client, assessment, actor=None, review_note=""):
    """Issue the single lifetime 10% bearer code for qualifying external UGC.

    No order, phone number, assignment, or TTN is fabricated.  A manager is
    required only when deterministic policy routed the assessment to review.
    """
    from management.ig_bot_models import IgUgcEvidenceAssessment, IgUgcReward

    client_pk = getattr(client, "pk", client)
    assessment = (
        IgUgcEvidenceAssessment.objects.select_for_update()
        .filter(pk=getattr(assessment, "pk", assessment), client_id=client_pk)
        .first()
    )
    if assessment is None:
        raise UgcRewardConflict("UGC-оцінку не знайдено.")
    if assessment.decision not in {
        IgUgcEvidenceAssessment.Decision.QUALIFIED_AUTO,
        IgUgcEvidenceAssessment.Decision.NEEDS_MANAGER_REVIEW,
        IgUgcEvidenceAssessment.Decision.MANAGER_APPROVED,
    }:
        raise UgcRewardConflict("Ця UGC-доказова база не дає права на нагороду.")
    _validate_external_assessment(assessment=assessment, client=client)
    is_authenticated = bool(actor is not None and getattr(actor, "is_authenticated", False))
    if assessment.decision in {
        IgUgcEvidenceAssessment.Decision.NEEDS_MANAGER_REVIEW,
        IgUgcEvidenceAssessment.Decision.MANAGER_APPROVED,
    } and not is_authenticated:
        raise UgcRewardConflict("Для підтвердження UGC потрібен авторизований менеджер.")

    manager_decision = assessment.decision in {
        IgUgcEvidenceAssessment.Decision.NEEDS_MANAGER_REVIEW,
        IgUgcEvidenceAssessment.Decision.MANAGER_APPROVED,
    }

    locked_client = type(client).objects.select_for_update().get(pk=client_pk)
    lifetime = _lifetime_slot_for_client(locked_client)
    existing = _existing_lifetime_reward(lifetime)
    if existing is not None:
        return _with_ugc_delivery(existing, False)
    if lifetime.consumed_at:
        raise UgcRewardConflict("Для цієї Instagram identity UGC-нагороду вже було видано.")
    service_reason = ugc_service_case_reason(locked_client)
    if service_reason:
        raise UgcRewardConflict(
            "UGC-нагороду тимчасово призупинено: активне звернення клієнта "
            f"({service_reason})."
        )
    legacy_reward = _legacy_reward_for_client(locked_client, lock=True)
    if legacy_reward is not None:
        lifetime.reward = legacy_reward
        lifetime.consumed_at = legacy_reward.issued_at or legacy_reward.created_at
        lifetime.save(update_fields=["reward", "consumed_at", "updated_at"])
        return _with_ugc_delivery(legacy_reward, False)

    now = timezone.now()
    return _create_locked_ugc_grant(
        locked_client=locked_client,
        lifetime=lifetime,
        now=now,
        promo_description="TwoComms UGC reward: 10% once, valid for 90 days",
        reward_fields={
            "order": None,
            "assignment": None,
            "assignment_version": 0,
            "evidence_type": IgUgcReward.EvidenceType.STORY_MENTION,
            "evidence_message_id": None,
            "evidence_url": "",
            "evidence_fingerprint": assessment.evidence_fingerprint,
            "review_note": str(review_note or "").strip()[:1000],
            "reviewed_by": (
                actor
                if manager_decision
                else None
            ),
            "reward_path": "external_ugc",
            "decision_source": (
                "manager"
                if manager_decision
                else "auto"
            ),
            "assessment": assessment,
            "assessment_generation_snapshot": assessment.generation,
            "policy_version_snapshot": assessment.policy_version,
            "provider_object_digest_snapshot": assessment.provider_object_digest or "",
            "catalog_candidates_snapshot": list(assessment.catalog_candidates or []),
        },
    )


def _ugc_expiry_label(promo) -> str:
    from zoneinfo import ZoneInfo

    try:
        return promo.valid_until.astimezone(ZoneInfo("Europe/Kyiv")).strftime("%d.%m.%Y")
    except Exception:
        return promo.valid_until.strftime("%d.%m.%Y") if promo.valid_until else ""


@transaction.atomic
def queue_external_ugc_reward_delivery(reward):
    """Create or recover the immutable customer-facing code message."""
    from management.ig_bot_models import IgUgcRewardDelivery

    reward = (
        type(reward).objects.select_for_update()
        .select_related("promo_code", "client")
        .get(pk=getattr(reward, "pk", reward))
    )
    expiry = _ugc_expiry_label(reward.promo_code)
    language = str(getattr(reward.client, "language", "uk") or "uk").casefold()
    if language.startswith("ru"):
        text = (
            f"Спасибо, что отметили TwoComms! Ваш персональный промокод на скидку 10%: "
            f"{reward.promo_code.code}. Он одноразовый, действует 90 дней и до {expiry}."
        )
    else:
        text = (
            f"Дякуємо, що відмітили TwoComms! Ваш персональний промокод на знижку 10%: "
            f"{reward.promo_code.code}. Він одноразовий, діє 90 днів і до {expiry}."
        )
    delivery, _created = IgUgcRewardDelivery.objects.get_or_create(
        reward=reward,
        defaults={
            "client_id": reward.client_id,
            "message_snapshot": text,
            "state": IgUgcRewardDelivery.State.PENDING,
        },
    )
    return delivery


UGC_DELIVERY_RESPONSE_WINDOW = timedelta(hours=23)
UGC_DELIVERY_RECHECK_DELAY = timedelta(hours=1)
UGC_DELIVERY_RETRY_BASE_DELAY = timedelta(minutes=5)
UGC_DELIVERY_MAX_ATTEMPTS = 3
UGC_DELIVERY_RETRYABLE_KINDS = frozenset({"retryable", "transient"})


def _ugc_delivery_retry_at(now, attempts: int):
    """Bound provider retry delay and leave terminal failures durable."""
    exponent = max(0, min(int(attempts or 1) - 1, 6))
    return now + UGC_DELIVERY_RETRY_BASE_DELAY * (2**exponent)


def _active_opt_out(client) -> bool:
    return bool(
        client
        and client.opted_out_at
        and (not client.opted_in_at or client.opted_out_at > client.opted_in_at)
    )


def _ugc_delivery_gate(*, settings_obj, client, now) -> tuple[bool, str]:
    """Revalidate all customer-send guards without performing provider I/O."""
    if client is None:
        return False, "client_missing"
    if not getattr(settings_obj, "is_enabled", False):
        return False, "global_reply_paused"
    if client.hidden_at:
        return False, "client_hidden"
    if client.is_blocked:
        return False, "client_blocked"
    if _active_opt_out(client):
        return False, "client_opted_out"
    if client.bot_paused:
        return False, "client_paused"
    if client.manager_takeover:
        return False, "manager_takeover"
    service_reason = ugc_service_case_reason(client)
    if service_reason:
        return False, service_reason
    delivery_status = str(getattr(client, "delivery_status", "") or "")
    if delivery_status in {
        "window_closed",
        "advanced_access",
        "message_request_check",
        "send_blocked",
    }:
        return False, f"meta_{delivery_status}"
    if not client.last_message_at or now > client.last_message_at + UGC_DELIVERY_RESPONSE_WINDOW:
        return False, "response_window_closed"
    return True, ""


def _set_ugc_delivery_waiting(delivery_id, *, token="", reason, now):
    from management.ig_bot_models import IgUgcRewardDelivery

    with transaction.atomic():
        row = IgUgcRewardDelivery.objects.select_for_update().get(pk=delivery_id)
        if token and row.lease_token != token:
            return "lease_lost"
        row.state = IgUgcRewardDelivery.State.WAITING_WINDOW
        row.due_at = now + UGC_DELIVERY_RECHECK_DELAY
        row.lease_token = ""
        row.lease_expires_at = None
        row.last_error = str(reason or "customer_send_not_allowed")[:500]
        row.save(update_fields=[
            "state", "due_at", "lease_token", "lease_expires_at",
            "last_error", "updated_at",
        ])
        return row.state


def process_external_ugc_reward_delivery(delivery_id: int, *, settings_obj=None):
    """Send one outbox row after fresh window and permission revalidation."""
    from management.ig_bot_models import IgClient, IgUgcRewardDelivery
    from management.services.ig_reply_boundary import (
        capture_reply_permission,
        customer_send_boundary,
    )
    from storefront.models import PromoCode

    if settings_obj is None:
        from management.models import InstagramBotSettings

        settings_obj = InstagramBotSettings.load()

    now = timezone.now()
    with transaction.atomic():
        delivery = (
            IgUgcRewardDelivery.objects.select_for_update()
            .select_related("reward")
            .get(pk=delivery_id)
        )
        if delivery.state in {
            IgUgcRewardDelivery.State.SENT,
            IgUgcRewardDelivery.State.AMBIGUOUS,
        } or (
            delivery.state == IgUgcRewardDelivery.State.FAILED
            and delivery.completed_at is not None
        ):
            return delivery.state
        if (
            delivery.state == IgUgcRewardDelivery.State.PROCESSING
            and delivery.lease_expires_at
            and delivery.lease_expires_at > now
        ):
            return "busy"
        if delivery.state == IgUgcRewardDelivery.State.PROCESSING:
            # PROCESSING is the durable provider-I/O marker. Meta has no
            # idempotency key for this send, so an expired lease is never
            # reclaimed automatically even when no receipt was persisted.
            delivery.state = IgUgcRewardDelivery.State.AMBIGUOUS
            delivery.lease_token = ""
            delivery.lease_expires_at = None
            delivery.last_error = "stale_processing_provider_outcome_unknown"
            delivery.save(update_fields=[
                "state",
                "lease_token",
                "lease_expires_at",
                "last_error",
                "updated_at",
            ])
            return delivery.state

        # A grant is consumed at issuance, but a delayed outbox must never
        # send a code after it has expired, been disabled, or exhausted its
        # one-use capacity.  Mark the existing delivery terminally and keep
        # the lifetime slot consumed; minting a replacement would violate the
        # one-reward invariant.
        promo = (
            PromoCode.objects.select_for_update()
            .filter(pk=delivery.reward.promo_code_id)
            .first()
        )
        promo_error = ""
        if promo is None:
            promo_error = "promo_missing"
        elif not promo.is_active:
            promo_error = "promo_inactive"
        elif promo.valid_until and now >= promo.valid_until:
            promo_error = "promo_expired"
        elif promo.valid_from and now < promo.valid_from:
            promo_error = "promo_not_live"
        elif promo.max_uses > 0 and promo.current_uses >= promo.max_uses:
            promo_error = "promo_exhausted"
        elif promo.group_id and promo.group and not promo.group.is_active:
            promo_error = "promo_group_inactive"
        elif not promo.is_guest_ugc_capability():
            promo_error = "promo_policy_invalid"
        if promo_error:
            delivery.state = IgUgcRewardDelivery.State.FAILED
            delivery.lease_token = ""
            delivery.lease_expires_at = None
            delivery.completed_at = now
            delivery.last_error = promo_error
            delivery.save(update_fields=[
                "state", "lease_token", "lease_expires_at", "last_error",
                "completed_at", "updated_at",
            ])
            return delivery.state

        client = (
            IgClient.objects.select_for_update()
            .filter(pk=delivery.client_id)
            .first()
        )
        allowed, reason = _ugc_delivery_gate(
            settings_obj=settings_obj,
            client=client,
            now=now,
        )
        permission = (
            capture_reply_permission(getattr(settings_obj, "pk", None), client.pk)
            if allowed and client is not None
            else None
        )
        if allowed and not permission:
            allowed = False
            reason = getattr(permission, "reason", "") or "customer_send_not_allowed"
        if not allowed:
            delivery.state = IgUgcRewardDelivery.State.WAITING_WINDOW
            delivery.due_at = now + UGC_DELIVERY_RECHECK_DELAY
            delivery.lease_token = ""
            delivery.lease_expires_at = None
            delivery.last_error = reason[:500]
            delivery.save(update_fields=[
                "state", "due_at", "lease_token", "lease_expires_at",
                "last_error", "updated_at",
            ])
            return delivery.state
        delivery.state = IgUgcRewardDelivery.State.PROCESSING
        delivery.attempts += 1
        delivery.completed_at = None
        delivery.lease_token = secrets.token_hex(16)
        delivery.lease_expires_at = now + timedelta(minutes=5)
        delivery.save(update_fields=[
            "state", "attempts", "lease_token", "lease_expires_at", "updated_at",
        ])
        token = delivery.lease_token
        text = delivery.message_snapshot
        client_id = client.pk
        recipient_id = client.igsid

    try:
        with customer_send_boundary(
            getattr(settings_obj, "pk", None),
            client_id,
            permission,
        ) as current_permission:
            fresh_client = IgClient.objects.filter(pk=client_id).first()
            fresh_now = timezone.now()
            allowed, reason = _ugc_delivery_gate(
                settings_obj=settings_obj,
                client=fresh_client,
                now=fresh_now,
            )
            if not current_permission:
                allowed = False
                reason = current_permission.reason or "customer_send_not_allowed"
            if not allowed:
                return _set_ugc_delivery_waiting(
                    delivery_id,
                    token=token,
                    reason=reason,
                    now=fresh_now,
                )

            from management.services.instagram_bot import send_text

            receipt = send_text(settings_obj, recipient_id, text, return_receipt=True)
        ok = bool(getattr(receipt, "ok", False))
        kind = str(getattr(receipt, "kind", "") or "")
        ids = list(getattr(receipt, "provider_message_ids", ()) or ())
    except Exception as exc:
        ok, kind, ids = False, "unknown", []
        error = str(exc)[:500]
    else:
        error = ""
    with transaction.atomic():
        row = IgUgcRewardDelivery.objects.select_for_update().get(pk=delivery_id)
        if row.lease_token != token:
            return "lease_lost"
        row.lease_token = ""
        row.lease_expires_at = None
        row.provider_message_ids = ids
        row.last_error = error or ("" if ok else kind[:500])
        completed_at = timezone.now()
        if ok and ids:
            row.state = IgUgcRewardDelivery.State.SENT
            row.completed_at = completed_at
        elif kind in {"unknown", "ambiguous"}:
            row.state = IgUgcRewardDelivery.State.AMBIGUOUS
            row.completed_at = completed_at
        elif kind in UGC_DELIVERY_RETRYABLE_KINDS and row.attempts < UGC_DELIVERY_MAX_ATTEMPTS:
            row.state = IgUgcRewardDelivery.State.FAILED
            row.completed_at = None
            row.due_at = _ugc_delivery_retry_at(completed_at, row.attempts)
        else:
            row.state = IgUgcRewardDelivery.State.FAILED
            row.completed_at = completed_at
        row.save(update_fields=[
            "state", "lease_token", "lease_expires_at", "provider_message_ids",
            "last_error", "completed_at", "due_at", "updated_at",
        ])
        return row.state


@transaction.atomic
def award_ugc_reward(
    *,
    client,
    order,
    actor,
    evidence_message_id=None,
    evidence_url="",
    review_note="",
):
    """Issue one 10% promo after a manager verifies one UGC proof."""

    from management.ig_bot_models import (
        IgClient,
        IgOrderAssignment,
        IgUgcReward,
    )
    from management.models import InstagramBotMessage
    from orders.models import Order
    from storefront.models import PromoCode

    message_id = str(evidence_message_id or "").strip()
    raw_url = str(evidence_url or "").strip()
    if bool(message_id) == bool(raw_url):
        raise UgcRewardConflict("Вкажіть одне підтвердження: повідомлення Direct або Instagram URL.")
    if actor is None or not getattr(actor, "is_authenticated", False):
        raise UgcRewardConflict("Потрібен авторизований менеджер.")

    locked_order = Order.objects.select_for_update().get(pk=getattr(order, "pk", order))
    assignment = (
        IgOrderAssignment.objects.select_for_update()
        .filter(
            order_id=locked_order.pk,
            client_id=getattr(client, "pk", client),
            unassigned_at__isnull=True,
        )
        .first()
    )
    if assignment is None:
        raise UgcRewardConflict("Замовлення не має поточної прив'язки до цього Instagram-клієнта.")
    if not nova_poshta_order_fulfillment_confirmed(locked_order):
        raise UgcRewardConflict(
            "Нагороду можна видати лише після підтвердженого отримання замовлення."
        )

    locked_client = IgClient.objects.select_for_update().get(pk=assignment.client_id)

    evidence_message = None
    normalized_url = ""
    if message_id:
        try:
            evidence_message = (
                InstagramBotMessage.objects.select_for_update()
                .get(pk=int(message_id))
            )
        except (InstagramBotMessage.DoesNotExist, TypeError, ValueError):
            raise UgcRewardConflict("Повідомлення Direct не знайдено.") from None
        if (
            evidence_message.client_id != assignment.client_id
            or evidence_message.role != InstagramBotMessage.Role.USER
        ):
            raise UgcRewardConflict("Доказом може бути лише повідомлення цього клієнта.")
        delivered_at = nova_poshta_delivery_confirmed_at(locked_order)
        evidence_at = evidence_message.provider_created_at
        if not delivered_at or not evidence_at or evidence_at < delivered_at:
            raise UgcRewardConflict(
                "Доказ Direct має бути створений після підтвердженого отримання замовлення."
            )
        evidence_type = IgUgcReward.EvidenceType.DIRECT_MESSAGE
        fingerprint = _fingerprint(evidence_type, str(evidence_message.pk))
    else:
        normalized_url = _normalize_instagram_url(raw_url)
        evidence_type = IgUgcReward.EvidenceType.INSTAGRAM_URL
        fingerprint = _fingerprint(evidence_type, normalized_url)

    existing = (
        IgUgcReward.objects.select_for_update()
        .select_related("order", "promo_code", "reviewed_by")
        .filter(order_id=locked_order.pk)
        .first()
    )
    if existing is not None:
        if existing.evidence_fingerprint != fingerprint:
            raise UgcRewardConflict("Для цього замовлення нагороду вже видано за іншим доказом.")
        lifetime = _lifetime_slot_for_client(locked_client)
        lifetime_reward = _existing_lifetime_reward(lifetime)
        if lifetime_reward is not None and lifetime_reward.pk != existing.pk:
            raise UgcRewardConflict("Для цієї Instagram identity вже існує інша UGC-нагорода.")
        if lifetime.consumed_at and lifetime_reward is None:
            raise UgcRewardConflict("Для цієї Instagram identity UGC-нагороду вже було видано.")
        if lifetime.reward_id is None:
            lifetime.reward = existing
            lifetime.consumed_at = existing.issued_at or existing.created_at
            lifetime.save(update_fields=["reward", "consumed_at", "updated_at"])
        return _with_ugc_delivery(existing, False)
    if IgUgcReward.objects.filter(evidence_fingerprint=fingerprint).exists():
        raise UgcRewardConflict("Цей доказ уже використано для іншої нагороди.")

    lifetime = _lifetime_slot_for_client(locked_client)
    existing_lifetime_reward = _existing_lifetime_reward(lifetime)
    if existing_lifetime_reward is not None:
        return _with_ugc_delivery(existing_lifetime_reward, False)
    if lifetime.consumed_at:
        raise UgcRewardConflict("Для цієї Instagram identity UGC-нагороду вже було видано.")
    legacy_reward = _legacy_reward_for_client(locked_client, lock=True)
    if legacy_reward is not None:
        lifetime.reward = legacy_reward
        lifetime.consumed_at = legacy_reward.issued_at or legacy_reward.created_at
        lifetime.save(update_fields=["reward", "consumed_at", "updated_at"])
        return _with_ugc_delivery(legacy_reward, False)

    now = timezone.now()
    return _create_locked_ugc_grant(
        locked_client=locked_client,
        lifetime=lifetime,
        now=now,
        promo_description=(
            f"UGC reward for Instagram order "
            f"{locked_order.order_number or locked_order.pk}"
        ),
        reward_fields={
            "order": locked_order,
            "assignment": assignment,
            "assignment_version": assignment.version,
            "evidence_type": evidence_type,
            "evidence_message": evidence_message,
            "evidence_url": normalized_url,
            "evidence_fingerprint": fingerprint,
            "review_note": str(review_note or "").strip()[:1000],
            "reviewed_by": actor,
            "reward_path": "delivered_order",
            "decision_source": "manager",
        },
    )
