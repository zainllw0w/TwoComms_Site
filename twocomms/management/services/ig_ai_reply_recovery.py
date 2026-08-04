"""Durable recovery for an unanswered Instagram AI turn.

This service intentionally has a smaller surface than the normal live-reply
worker.  It represents one source inbound and crosses Meta's non-idempotent
Send API at most once.  A provider receipt is therefore required before the
intent is considered delivered; every unconfirmed result goes to manual review
instead of being replayed.
"""
from __future__ import annotations

import secrets
from contextlib import contextmanager
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from management.models import (
    IgAiReplyRecoveryJob,
    IgClient,
    InstagramBotMessage,
    InstagramBotSettings,
)
from management.services.ig_reply_boundary import (
    capture_reply_permission,
    customer_send_boundary,
)
from management.services.instagram_bot import (
    _build_history,
    _extract_control,
    acquire_client_automation_lease,
    gemini_generate,
    release_client_automation_lease,
    send_text,
)


RESPONSE_WINDOW = timedelta(hours=23)
JOB_LEASE_DURATION = timedelta(minutes=5)
# ``send_text`` can split longer text into several Meta requests.  Recovery is
# deliberately one customer message and one non-idempotent Meta request.
MAX_RECOVERY_REPLY_CHARS = 1800

_TERMINAL_STATUSES = frozenset({
    IgAiReplyRecoveryJob.Status.SENT,
    IgAiReplyRecoveryJob.Status.CANCELLED,
    IgAiReplyRecoveryJob.Status.AMBIGUOUS,
    IgAiReplyRecoveryJob.Status.FAILED,
})


def _active_opt_out(client: IgClient | None) -> bool:
    return bool(
        client
        and client.opted_out_at
        and (not client.opted_in_at or client.opted_in_at < client.opted_out_at)
    )


def _source_event_at(source: InstagramBotMessage):
    return source.provider_created_at or source.created_at or timezone.now()


def _window_deadline(source: InstagramBotMessage, client: IgClient):
    anchor = client.last_message_at or _source_event_at(source)
    return anchor + RESPONSE_WINDOW if anchor else None


def _trim_draft(text: str) -> str:
    """Keep recovery to one Meta text request without silently making controls."""
    clean, _control = _extract_control(str(text or ""))
    clean = clean.strip()
    if len(clean) <= MAX_RECOVERY_REPLY_CHARS:
        return clean
    shortened = clean[: MAX_RECOVERY_REPLY_CHARS - 3].rsplit(" ", 1)[0].strip()
    return f"{shortened or clean[:MAX_RECOVERY_REPLY_CHARS - 3]}..."


def _guard_reason(
    job: IgAiReplyRecoveryJob,
    settings_obj: InstagramBotSettings,
    client: IgClient | None,
    source: InstagramBotMessage | None,
    *,
    now,
) -> str:
    """Return a durable-cancellation reason before generation or Meta I/O."""
    if not settings_obj or not settings_obj.is_enabled:
        return "global_reply_paused"
    if not client or not source or source.client_id != client.pk:
        return "source_or_client_missing"
    if source.role != InstagramBotMessage.Role.USER:
        return "source_not_inbound"
    if client.hidden_at:
        return "client_hidden"
    if client.is_blocked:
        return "client_blocked"
    if _active_opt_out(client):
        return "client_opted_out"
    if client.bot_paused:
        return "client_paused"
    if client.manager_takeover:
        return "manager_takeover"

    permission = capture_reply_permission(settings_obj.pk, client.pk)
    if not permission:
        return permission.reason or "customer_send_not_allowed"
    if (
        permission.settings_epoch != int(job.settings_permission_epoch or 0)
        or permission.client_epoch != int(job.client_permission_epoch or 0)
    ):
        return "permission_epoch_changed"

    from management.services.ig_funnel_reset import current_message_floor

    floor = int(current_message_floor(client) or 0)
    if source.pk < floor or floor != int(job.message_floor or 0):
        return "message_floor_changed"
    deadline = job.response_window_deadline or _window_deadline(source, client)
    if not deadline or now > deadline:
        return "response_window_closed"

    # A current inbound is a newer customer intent, so this recovery must not
    # race it.  A manager message is also authoritative ownership evidence.
    newer = InstagramBotMessage.objects.filter(
        client_id=client.pk,
        id__gt=source.pk,
        role__in=[InstagramBotMessage.Role.USER, InstagramBotMessage.Role.MANAGER],
    ).exists()
    if newer:
        return "newer_inbound_or_manager_reply"

    # A known outage holding reply is explicitly allowed.  Any other confirmed
    # bot answer makes the recovery stale.  The persisted recovery draft itself
    # is excluded so the final pre-send guard remains valid.
    existing_reply_ids = [
        value for value in (job.holding_message_id, job.reply_message_id) if value
    ]
    substantive = InstagramBotMessage.objects.filter(
        client_id=client.pk,
        role=InstagramBotMessage.Role.MODEL,
        id__gt=source.pk,
    ).exclude(pk__in=existing_reply_ids).filter(
        Q(provider_message_id__gt="") | Q(send_state="sent")
    ).exists()
    if substantive:
        return "substantive_bot_reply_exists"
    return ""


def schedule_recovery(
    source_message: InstagramBotMessage,
    *,
    holding_message: InstagramBotMessage | None = None,
) -> IgAiReplyRecoveryJob:
    """Create exactly one recovery intent for a failed customer inbound."""
    source_id = getattr(source_message, "pk", source_message)
    with transaction.atomic():
        source = (
            InstagramBotMessage.objects.select_for_update()
            .select_related("client")
            .filter(pk=source_id)
            .first()
        )
        if source is None:
            raise ValueError("Recovery source message does not exist")
        if source.role != InstagramBotMessage.Role.USER:
            raise ValueError("Recovery source must be an inbound user message")
        if not source.client_id:
            raise ValueError("Recovery source has no Instagram client")

        client = source.client
        permission = capture_reply_permission(InstagramBotSettings.load().pk, client.pk)
        from management.services.ig_funnel_reset import current_message_floor

        holding_id = getattr(holding_message, "pk", holding_message) or None
        if holding_id:
            holding = InstagramBotMessage.objects.filter(
                pk=holding_id,
                client_id=client.pk,
                role=InstagramBotMessage.Role.MODEL,
            ).first()
            if holding is None:
                raise ValueError("Recovery holding message is not a client model message")
        else:
            holding = None
        defaults = {
            "client": client,
            "holding_message": holding,
            "dedupe_key": f"ig-ai-recovery:{source.pk}",
            "settings_permission_epoch": int(permission.settings_epoch or 0),
            "client_permission_epoch": int(permission.client_epoch or 0),
            "message_floor": int(current_message_floor(client) or 0),
            "response_window_deadline": _window_deadline(source, client),
        }
        try:
            job, created = IgAiReplyRecoveryJob.objects.get_or_create(
                source_message=source,
                defaults=defaults,
            )
        except IntegrityError:
            # The one-to-one source constraint is the idempotency boundary.
            job = IgAiReplyRecoveryJob.objects.get(source_message=source)
            created = False
        if holding and not job.holding_message_id:
            job.holding_message = holding
            job.save(update_fields=["holding_message", "updated_at"])
        del created
        return job


def _claim_job(job_id: int) -> tuple[IgAiReplyRecoveryJob | None, str]:
    now = timezone.now()
    with transaction.atomic():
        job = (
            IgAiReplyRecoveryJob.objects.select_for_update()
            .select_related("source_message", "client", "holding_message", "reply_message")
            .filter(pk=job_id)
            .first()
        )
        if job is None or job.status in _TERMINAL_STATUSES:
            return job, ""
        if job.status == job.Status.SENDING:
            if job.lease_until and job.lease_until > now:
                return job, ""
            # A process died after it made the request durable but before it
            # wrote a provider ID.  Never replay an uncertain Meta send.
            job.status = job.Status.AMBIGUOUS
            job.last_error = "stale_sending_without_provider_receipt"
            job.lease_token = ""
            job.lease_until = None
            job.completed_at = now
            job.save(update_fields=[
                "status", "last_error", "lease_token", "lease_until",
                "completed_at", "updated_at",
            ])
            if job.reply_message_id:
                InstagramBotMessage.objects.filter(pk=job.reply_message_id).update(
                    status=InstagramBotMessage.Status.FAILED,
                    send_state="unknown",
                    send_completed_at=now,
                )
            return job, ""
        if (
            job.status == job.Status.PROCESSING
            and job.lease_until
            and job.lease_until > now
        ):
            return job, ""

        token = secrets.token_hex(16)
        job.status = job.Status.PROCESSING
        job.lease_token = token
        job.lease_until = now + JOB_LEASE_DURATION
        job.attempts = int(job.attempts or 0) + 1
        job.last_error = ""
        job.save(update_fields=[
            "status", "lease_token", "lease_until", "attempts", "last_error", "updated_at",
        ])
    return job, token


def _cancel_claim(job_id: int, token: str, reason: str) -> IgAiReplyRecoveryJob:
    with transaction.atomic():
        job = IgAiReplyRecoveryJob.objects.select_for_update().get(pk=job_id)
        if job.lease_token == token and job.status in {
            job.Status.PROCESSING,
            job.Status.SENDING,
        }:
            now = timezone.now()
            job.status = job.Status.CANCELLED
            job.last_error = reason[:1000]
            job.lease_token = ""
            job.lease_until = None
            job.completed_at = now
            job.save(update_fields=[
                "status", "last_error", "lease_token", "lease_until",
                "completed_at", "updated_at",
            ])
            if job.reply_message_id:
                InstagramBotMessage.objects.filter(pk=job.reply_message_id).update(
                    status=InstagramBotMessage.Status.DONE,
                    send_state="cancelled",
                    send_completed_at=now,
                )
        return job


def _release_for_retry(job_id: int, token: str, reason: str) -> IgAiReplyRecoveryJob:
    with transaction.atomic():
        job = IgAiReplyRecoveryJob.objects.select_for_update().get(pk=job_id)
        if job.lease_token == token and job.status == job.Status.PROCESSING:
            job.status = job.Status.PENDING
            job.last_error = reason[:1000]
            job.lease_token = ""
            job.lease_until = None
            job.save(update_fields=[
                "status", "last_error", "lease_token", "lease_until", "updated_at",
            ])
        return job


def _generate_recovery_draft(job: IgAiReplyRecoveryJob) -> str:
    """Generate a safe, substantive response for the original current turn."""
    settings_obj = InstagramBotSettings.load()
    history = _build_history(job.source_message.sender_id)
    draft = gemini_generate(
        settings_obj,
        history,
        client=job.client,
        turn_note=(
            "Відновлення відповіді після короткої технічної затримки. "
            "Почни з одного природного короткого вибачення, а далі одразу дай "
            "повну корисну відповідь на останнє запитання клієнта. Не згадуй "
            "ШІ, Gemini, API, ключі, внутрішні системи чи менеджера. Не додавай "
            "керуючих тегів, посилань на оплату, створення замовлення або інші "
            "незворотні дії. Відповідай мовою останнього повідомлення клієнта."
        ),
    )
    return _trim_draft(draft or "")


def _persist_draft(
    job_id: int,
    token: str,
    draft: str,
) -> tuple[IgAiReplyRecoveryJob, str]:
    """Persist the exact draft and history row before any Meta I/O."""
    with transaction.atomic():
        job = (
            IgAiReplyRecoveryJob.objects.select_for_update()
            .select_related("source_message", "client", "holding_message", "reply_message")
            .get(pk=job_id)
        )
        if job.lease_token != token or job.status != job.Status.PROCESSING:
            return job, "claim_lost"
        settings_obj = InstagramBotSettings.load()
        reason = _guard_reason(
            job, settings_obj, job.client, job.source_message, now=timezone.now()
        )
        if reason:
            return job, reason
        # A legacy/incomplete draft can be longer than a one-request recovery
        # permits.  Replace it with the already-normalized value before I/O.
        job.draft_text = draft
        if not job.reply_message_id:
            reply_message = InstagramBotMessage.objects.create(
                sender_id=job.source_message.sender_id,
                client_id=job.client_id,
                role=InstagramBotMessage.Role.MODEL,
                text=job.draft_text,
                status=InstagramBotMessage.Status.PROCESSING,
                source="ai_recovery",
                send_state="",
            )
            job.reply_message = reply_message
        elif job.reply_message.send_state in {"sending", "sent", "unknown"}:
            now = timezone.now()
            provider_id = str(job.reply_message.provider_message_id or "").strip()
            if job.reply_message.send_state == "sent" and provider_id:
                job.status = job.Status.SENT
                job.provider_message_id = provider_id[:255]
                job.last_error = ""
            else:
                # The history row says a prior worker already crossed, or may
                # have crossed, the provider boundary.  It must not be replayed.
                job.status = job.Status.AMBIGUOUS
                job.last_error = "reply_delivery_already_started"
            job.lease_token = ""
            job.lease_until = None
            job.completed_at = now
            job.save(update_fields=[
                "status", "provider_message_id", "last_error", "lease_token",
                "lease_until", "completed_at", "updated_at",
            ])
            return job, "terminalized_existing_delivery"
        job.save(update_fields=["draft_text", "reply_message", "updated_at"])
        return job, ""


@contextmanager
def _recovery_send_boundary(
    job_id: int,
    token: str,
    permission,
    *,
    mark_sending: bool,
):
    """Revalidate all recovery guards while holding the short Meta send lock."""
    with customer_send_boundary(permission.settings_id, permission.client_id, permission) as allowed:
        if not allowed:
            yield False
            return
        can_send = False
        with transaction.atomic():
            locked = (
                IgAiReplyRecoveryJob.objects.select_for_update()
                .select_related("source_message", "client", "holding_message", "reply_message")
                .get(pk=job_id)
            )
            expected_status = (
                locked.Status.PROCESSING if mark_sending else locked.Status.SENDING
            )
            if locked.lease_token == token and locked.status == expected_status:
                settings_obj = InstagramBotSettings.load()
                reason = _guard_reason(
                    locked,
                    settings_obj,
                    locked.client,
                    locked.source_message,
                    now=timezone.now(),
                )
                if not reason and locked.reply_message_id:
                    now = timezone.now()
                    if mark_sending:
                        locked.status = locked.Status.SENDING
                        locked.sending_started_at = now
                        locked.lease_until = now + JOB_LEASE_DURATION
                        locked.save(update_fields=[
                            "status", "sending_started_at", "lease_until", "updated_at",
                        ])
                        InstagramBotMessage.objects.filter(pk=locked.reply_message_id).update(
                            send_state="sending",
                            send_started_at=now,
                            send_completed_at=None,
                        )
                    can_send = True
        yield can_send


def _delivery_result(result) -> tuple[bool, str, str, str]:
    provider_message_id = str(getattr(result, "provider_message_id", "") or "").strip()
    if isinstance(result, tuple):
        if len(result) >= 4:
            ok, kind, hint, provider_message_id = result[:4]
        else:
            ok, kind, hint = result
    else:
        ok = bool(getattr(result, "ok", False))
        kind = str(getattr(result, "kind", "unknown") or "unknown")
        hint = str(getattr(result, "hint", "") or "")
    return bool(ok), str(kind or "unknown"), str(hint or ""), str(provider_message_id or "").strip()


def _finish_delivery(
    job_id: int,
    token: str,
    *,
    ok: bool,
    kind: str,
    hint: str,
    provider_message_id: str,
) -> IgAiReplyRecoveryJob:
    with transaction.atomic():
        job = IgAiReplyRecoveryJob.objects.select_for_update().get(pk=job_id)
        if job.lease_token != token or job.status != job.Status.SENDING:
            return job
        now = timezone.now()
        job.lease_token = ""
        job.lease_until = None
        job.completed_at = now
        reply_update = {
            "send_completed_at": now,
        }
        if ok and provider_message_id:
            job.status = job.Status.SENT
            job.provider_message_id = provider_message_id[:255]
            job.last_error = ""
            reply_update.update({
                "status": InstagramBotMessage.Status.DONE,
                "send_state": "sent",
                "provider_message_id": provider_message_id[:255],
            })
            client = IgClient.objects.select_for_update().get(pk=job.client_id)
            client.last_bot_reply_at = now
            client.save(update_fields=["last_bot_reply_at", "updated_at"])
        else:
            # Once the Send API was invoked, including HTTP 200 with no ID, we
            # cannot safely know whether Meta delivered the draft.  Do not retry.
            job.status = job.Status.AMBIGUOUS
            job.last_error = (
                "provider_message_id_missing" if ok else f"{kind}:{hint}"
            )[:1000]
            reply_update.update({
                "status": InstagramBotMessage.Status.FAILED,
                "send_state": "unknown",
            })
        job.save(update_fields=[
            "status", "provider_message_id", "last_error", "lease_token",
            "lease_until", "completed_at", "updated_at",
        ])
        if job.reply_message_id:
            InstagramBotMessage.objects.filter(pk=job.reply_message_id).update(**reply_update)
        return job


def process_recovery_job(job_id: int) -> IgAiReplyRecoveryJob | None:
    """Generate and send one guarded recovery reply, never replaying Meta I/O."""
    job, token = _claim_job(job_id)
    if job is None or not token:
        return job

    automation_token = ""
    try:
        settings_obj = InstagramBotSettings.load()
        reason = _guard_reason(
            job, settings_obj, job.client, job.source_message, now=timezone.now()
        )
        if reason:
            return _cancel_claim(job.pk, token, reason)

        _leased_client, automation_token = acquire_client_automation_lease(job.client_id)
        if not automation_token:
            return _release_for_retry(job.pk, token, "client_automation_busy")

        draft = _trim_draft(job.draft_text) if job.draft_text else _generate_recovery_draft(job)
        if not draft:
            return _release_for_retry(job.pk, token, "recovery_generation_failed")
        job, reason = _persist_draft(job.pk, token, draft)
        if reason:
            if reason in {
                "claim_lost", "terminalized_existing_delivery",
            }:
                return job
            return _cancel_claim(job.pk, token, reason)

        permission = capture_reply_permission(settings_obj.pk, job.client_id)
        # Make the outbound edge durable before calling Meta.  The boundary
        # inside ``send_text`` repeats the complete guard immediately before
        # the request, so a pause/newer message between the two is still safe.
        with _recovery_send_boundary(
            job.pk, token, permission, mark_sending=True
        ) as ready:
            if not ready:
                return _cancel_claim(job.pk, token, "permission_or_recovery_guard_changed")
        result = send_text(
            settings_obj,
            job.source_message.sender_id,
            job.draft_text,
            permission_boundary_factory=lambda: _recovery_send_boundary(
                job.pk, token, permission, mark_sending=False
            ),
            return_receipt=True,
        )
        ok, kind, hint, provider_message_id = _delivery_result(result)
        if kind == "cancelled":
            return _cancel_claim(job.pk, token, "permission_or_recovery_guard_changed")
        return _finish_delivery(
            job.pk,
            token,
            ok=ok,
            kind=kind,
            hint=hint,
            provider_message_id=provider_message_id,
        )
    except Exception as exc:  # noqa: BLE001 - provider boundary must be durable.
        # If the send boundary was crossed, an exception is indistinguishable
        # from a delivered request.  The current state tells us which side won.
        with transaction.atomic():
            current = IgAiReplyRecoveryJob.objects.select_for_update().get(pk=job.pk)
            crossed_meta_boundary = (
                current.lease_token == token and current.status == current.Status.SENDING
            )
        if crossed_meta_boundary:
            return _finish_delivery(
                job.pk,
                token,
                ok=False,
                kind="unknown",
                hint=repr(exc),
                provider_message_id="",
            )
        return _release_for_retry(job.pk, token, f"recovery_error:{exc!r}")
    finally:
        if automation_token:
            release_client_automation_lease(job.client_id, automation_token)
