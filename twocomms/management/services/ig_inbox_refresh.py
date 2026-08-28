"""Durable, history-only recovery of Meta-readable Instagram messages."""
from __future__ import annotations

import json
import secrets
import time
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from management.models import (
    IgClient,
    IgInboxRefreshItem,
    IgInboxRefreshRun,
    InstagramBotMessage,
    InstagramBotSettings,
)
from management.services import instagram_bot as bot
from management.services.bot_conversation_analysis import schedule_analysis


RUN_LEASE = timedelta(minutes=2)
ITEM_LEASE = timedelta(minutes=2)
MAX_ATTEMPTS = 5
MAX_DISCOVERY_PAGES = 5000
RETRY_DELAYS = (30, 120, 600, 1800, 3600)
ACTIVE_RUN_STATUSES = {
    IgInboxRefreshRun.Status.QUEUED,
    IgInboxRefreshRun.Status.DISCOVERING,
    IgInboxRefreshRun.Status.RUNNING,
    IgInboxRefreshRun.Status.CANCELLING,
}
TERMINAL_ITEM_STATUSES = {
    IgInboxRefreshItem.Status.DONE,
    IgInboxRefreshItem.Status.SKIPPED,
    IgInboxRefreshItem.Status.FAILED,
    IgInboxRefreshItem.Status.CANCELLED,
}


class RefreshIdentityError(ValueError):
    pass


def _floor_cutoff(value):
    return (value or timezone.now()).replace(microsecond=0)


def create_refresh_run(user, *, now=None):
    """Create one open run per provider owner without performing Meta I/O."""
    settings_obj = InstagramBotSettings.load()
    if bot.provider_transport(settings_obj) != bot.INSTAGRAM_LOGIN_TRANSPORT:
        raise ValueError("manual refresh requires Instagram Login transport")
    owner_id = bot._provider_owner_id(settings_obj)
    if not owner_id:
        raise ValueError("missing provider account id")
    cutoff = _floor_cutoff(now)
    with transaction.atomic():
        InstagramBotSettings.objects.select_for_update().get(pk=settings_obj.pk)
        existing = (
            IgInboxRefreshRun.objects.select_for_update()
            .filter(provider_owner_id=owner_id, open_slot=1)
            .order_by("-id")
            .first()
        )
        if existing:
            return existing, False
        try:
            with transaction.atomic():
                run = IgInboxRefreshRun.objects.create(
                    requested_by=user if getattr(user, "is_authenticated", False) else None,
                    provider_owner_id=owner_id,
                    transport=bot.INSTAGRAM_LOGIN_TRANSPORT,
                    recovery_cutoff=cutoff,
                    next_attempt_at=cutoff,
                )
        except IntegrityError:
            return (
                IgInboxRefreshRun.objects.get(provider_owner_id=owner_id, open_slot=1),
                False,
            )
    return run, True


def _item_totals(run):
    rows = {
        row["status"]: row["count"]
        for row in run.items.values("status").annotate(count=Count("id"))
    }
    sums = run.items.aggregate(
        messages_created=Sum("messages_created"),
        messages_existing=Sum("messages_existing"),
        messages_after_cutoff=Sum("messages_after_cutoff"),
    )
    total = sum(rows.values())
    terminal = sum(rows.get(status, 0) for status in TERMINAL_ITEM_STATUSES)
    return rows, sums, total, terminal


def serialize_refresh_run(run):
    if run is None:
        return None
    rows, sums, total, terminal = _item_totals(run)
    hidden_skipped = run.items.filter(
        status=IgInboxRefreshItem.Status.SKIPPED,
        skip_reason="client_hidden",
    ).count()
    return {
        "id": run.pk,
        "status": run.status,
        "provider_owner_id": run.provider_owner_id,
        "recovery_cutoff": run.recovery_cutoff.isoformat() if run.recovery_cutoff else None,
        "scope": "latest_available_messages",
        "scope_note": "Meta повертає до 20 останніх доступних повідомлень у кожній переписці.",
        "discovery_complete": bool(run.discovery_complete),
        "discovery_pages_seen": int(run.discovery_pages_seen or 0),
        "total": total,
        "terminal": terminal,
        "pending": rows.get(IgInboxRefreshItem.Status.PENDING, 0),
        "processing": rows.get(IgInboxRefreshItem.Status.PROCESSING, 0),
        "done": rows.get(IgInboxRefreshItem.Status.DONE, 0),
        "skipped": rows.get(IgInboxRefreshItem.Status.SKIPPED, 0),
        "hidden_skipped": hidden_skipped,
        "failed": rows.get(IgInboxRefreshItem.Status.FAILED, 0),
        "cancelled": rows.get(IgInboxRefreshItem.Status.CANCELLED, 0),
        "messages_created": int(sums.get("messages_created") or 0),
        "messages_existing": int(sums.get("messages_existing") or 0),
        "messages_after_cutoff": int(sums.get("messages_after_cutoff") or 0),
        "last_error": run.last_error,
        "cancel_requested_at": run.cancel_requested_at.isoformat() if run.cancel_requested_at else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


def latest_refresh_run():
    settings_obj = InstagramBotSettings.load()
    owner_id = bot._provider_owner_id(settings_obj)
    if not owner_id:
        return None
    return (
        IgInboxRefreshRun.objects.filter(provider_owner_id=owner_id)
        .order_by("-id")
        .first()
    )


def refresh_run_for_current_owner(run_id):
    settings_obj = InstagramBotSettings.load()
    owner_id = bot._provider_owner_id(settings_obj)
    if not owner_id:
        return None
    return IgInboxRefreshRun.objects.filter(
        pk=run_id,
        provider_owner_id=owner_id,
    ).first()


def request_refresh_cancel(run_id, *, now=None):
    now = now or timezone.now()
    settings_obj = InstagramBotSettings.load()
    owner_id = bot._provider_owner_id(settings_obj)
    if not owner_id:
        return None
    with transaction.atomic():
        run = IgInboxRefreshRun.objects.select_for_update().filter(
            pk=run_id,
            provider_owner_id=owner_id,
        ).first()
        if run is None or run.status not in ACTIVE_RUN_STATUSES:
            return run
        run.status = IgInboxRefreshRun.Status.CANCELLING
        run.cancel_requested_at = now
        run.save(update_fields=["status", "cancel_requested_at", "updated_at"])
        return run


def retry_refresh_failures(run_id, *, now=None):
    now = _floor_cutoff(now)
    settings_obj = InstagramBotSettings.load()
    owner_id = bot._provider_owner_id(settings_obj)
    if not owner_id:
        return None
    with transaction.atomic():
        run = IgInboxRefreshRun.objects.select_for_update().filter(
            pk=run_id,
            provider_owner_id=owner_id,
        ).first()
        if run is None or run.status not in {
            IgInboxRefreshRun.Status.COMPLETED_ERRORS,
            IgInboxRefreshRun.Status.FAILED,
        }:
            return run
        if IgInboxRefreshRun.objects.filter(
            provider_owner_id=run.provider_owner_id, open_slot=1
        ).exclude(pk=run.pk).exists():
            raise IntegrityError("another inbox refresh is active")
        run.items.filter(status=IgInboxRefreshItem.Status.FAILED).update(
            status=IgInboxRefreshItem.Status.PENDING,
            attempts=0,
            next_attempt_at=now,
            lease_token="",
            lease_until=None,
            last_error="",
            completed_at=None,
            updated_at=now,
        )
        run.status = (
            IgInboxRefreshRun.Status.RUNNING
            if run.discovery_complete
            else IgInboxRefreshRun.Status.DISCOVERING
        )
        run.open_slot = 1
        run.completed_at = None
        run.last_error = ""
        run.attempts = 0
        run.lease_token = ""
        run.lease_until = None
        run.next_attempt_at = now
        run.save(update_fields=[
            "status", "open_slot", "completed_at", "last_error",
            "attempts", "lease_token", "lease_until", "next_attempt_at", "updated_at",
        ])
        return run


def _retry_at(now, attempts):
    index = max(0, min(int(attempts or 1) - 1, len(RETRY_DELAYS) - 1))
    return now + timedelta(seconds=RETRY_DELAYS[index])


def _provider_http_code(fetched):
    try:
        code = int(fetched.get("http_code") or 0)
    except (TypeError, ValueError):
        code = 0
    if code:
        return code
    reason = str(fetched.get("reason") or "")
    if reason.startswith("http_"):
        try:
            return int(reason.split("_", 1)[1])
        except (TypeError, ValueError):
            pass
    return 0


def _is_transient_provider_failure(code, reason):
    return bool(
        code == -1
        or code == 429
        or code >= 500
        or reason in {"provider_network_error", "meta_rate_limit", "poll_budget"}
    )


def _cancel_open_run(now):
    with transaction.atomic():
        run = (
            IgInboxRefreshRun.objects.select_for_update()
            .filter(open_slot=1, status=IgInboxRefreshRun.Status.CANCELLING)
            .order_by("id")
            .first()
        )
        if run is None:
            return None
        run.items.filter(status__in=[
            IgInboxRefreshItem.Status.PENDING,
            IgInboxRefreshItem.Status.PROCESSING,
        ]).update(
            status=IgInboxRefreshItem.Status.CANCELLED,
            lease_token="",
            lease_until=None,
            completed_at=now,
            updated_at=now,
        )
        run.status = IgInboxRefreshRun.Status.CANCELLED
        run.open_slot = None
        run.lease_token = ""
        run.lease_until = None
        run.completed_at = now
        run.save(update_fields=[
            "status", "open_slot", "lease_token", "lease_until",
            "completed_at", "updated_at",
        ])
        return run


def _claim_discovery_run(now):
    with transaction.atomic():
        expired_runs = list(
            IgInboxRefreshRun.objects.select_for_update()
            .filter(
                open_slot=1,
                status=IgInboxRefreshRun.Status.DISCOVERING,
                lease_until__lte=now,
            )
            .exclude(lease_token="")
            .order_by("id")[:100]
        )
        for expired in expired_runs:
            attempts = int(expired.attempts or 0) + 1
            expired.attempts = attempts
            expired.lease_token = ""
            expired.lease_until = None
            expired.last_error = "discovery worker lease expired"
            fields = [
                "attempts", "lease_token", "lease_until", "last_error", "updated_at",
            ]
            if attempts >= MAX_ATTEMPTS:
                expired.status = IgInboxRefreshRun.Status.FAILED
                expired.open_slot = None
                expired.completed_at = now
                fields.extend(["status", "open_slot", "completed_at"])
            else:
                expired.next_attempt_at = _retry_at(now, attempts)
                fields.append("next_attempt_at")
            expired.save(update_fields=fields)
        run = (
            IgInboxRefreshRun.objects.select_for_update()
            .filter(
                open_slot=1,
                status__in=[
                    IgInboxRefreshRun.Status.QUEUED,
                    IgInboxRefreshRun.Status.DISCOVERING,
                ],
            )
            .filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
            .filter(Q(lease_until__isnull=True) | Q(lease_until__lte=now) | Q(lease_token=""))
            .order_by("id")
            .first()
        )
        if run is None:
            return None
        token = secrets.token_hex(16)
        run.status = IgInboxRefreshRun.Status.DISCOVERING
        run.lease_token = token
        run.lease_until = now + RUN_LEASE
        run.started_at = run.started_at or now
        run.save(update_fields=[
            "status", "lease_token", "lease_until", "started_at", "updated_at",
        ])
        run._claimed_lease_token = token
        return run


def _finish_run_failure(run, message, *, now, transient=False):
    token = run._claimed_lease_token
    with transaction.atomic():
        locked = IgInboxRefreshRun.objects.select_for_update().filter(
            pk=run.pk,
            lease_token=token,
            status=IgInboxRefreshRun.Status.DISCOVERING,
            cancel_requested_at__isnull=True,
        ).first()
        if locked is None:
            return
        attempts = int(locked.attempts or 0) + 1
        locked.attempts = attempts
        locked.last_error = str(message or "provider failure")[:1000]
        locked.lease_token = ""
        locked.lease_until = None
        fields = ["attempts", "last_error", "lease_token", "lease_until", "updated_at"]
        if transient and attempts < MAX_ATTEMPTS:
            locked.status = IgInboxRefreshRun.Status.DISCOVERING
            locked.next_attempt_at = _retry_at(now, attempts)
            fields.extend(["status", "next_attempt_at"])
        else:
            locked.status = IgInboxRefreshRun.Status.FAILED
            locked.open_slot = None
            locked.completed_at = now
            fields.extend(["status", "open_slot", "completed_at"])
        locked.save(update_fields=fields)


def _discover_one_page(run, *, now):
    if int(run.discovery_pages_seen or 0) >= MAX_DISCOVERY_PAGES:
        _finish_run_failure(run, "discovery page limit exceeded", now=now)
        return
    settings_obj = InstagramBotSettings.load()
    if (
        bot.provider_transport(settings_obj) != bot.INSTAGRAM_LOGIN_TRANSPORT
        or bot._provider_owner_id(settings_obj) != run.provider_owner_id
    ):
        _finish_run_failure(run, "provider owner or transport changed", now=now)
        return
    page_token = bot.get_page_token(settings_obj)
    if not page_token:
        _finish_run_failure(run, "missing provider token", now=now)
        return
    code, body = bot._provider_http(
        settings_obj,
        bot._conversation_discovery_url(settings_obj, run.discovery_cursor),
        token=page_token,
        timeout=bot.CONV_LIST_TIMEOUT,
    )
    if code != 200:
        reason = bot._classify_poll_provider_failure(code, body)
        _finish_run_failure(
            run,
            reason,
            now=now,
            transient=_is_transient_provider_failure(code, reason),
        )
        return
    try:
        conversations, next_cursor = bot._validate_conversation_discovery_page(
            json.loads(body), settings_obj
        )
    except Exception as exc:
        _finish_run_failure(run, f"malformed discovery: {exc}", now=now)
        return
    if next_cursor and next_cursor == run.discovery_cursor:
        _finish_run_failure(run, "repeated discovery cursor", now=now)
        return
    with transaction.atomic():
        locked = IgInboxRefreshRun.objects.select_for_update().filter(
            pk=run.pk,
            lease_token=run._claimed_lease_token,
            status=IgInboxRefreshRun.Status.DISCOVERING,
            cancel_requested_at__isnull=True,
        ).first()
        if locked is None:
            return
        for conversation in conversations:
            participant, exclusion = bot._conversation_participant_state(
                settings_obj, conversation
            )
            hidden_client = None
            if participant:
                hidden_client = IgClient.objects.filter(
                    igsid=participant, hidden_at__isnull=False
                ).only("id").first()
            status = IgInboxRefreshItem.Status.PENDING
            skip_reason = ""
            client_id = None
            if exclusion:
                status = IgInboxRefreshItem.Status.SKIPPED
                skip_reason = exclusion
            elif hidden_client:
                status = IgInboxRefreshItem.Status.SKIPPED
                skip_reason = "client_hidden"
                client_id = hidden_client.pk
            IgInboxRefreshItem.objects.get_or_create(
                run=locked,
                conversation_id=conversation["id"],
                defaults={
                    "participant_igsid": participant,
                    "client_id": client_id,
                    "provider_updated_at": bot._parse_ig_time(
                        conversation.get("updated_time") or ""
                    ),
                    "status": status,
                    "skip_reason": skip_reason,
                    "completed_at": now if status == IgInboxRefreshItem.Status.SKIPPED else None,
                    "next_attempt_at": now,
                },
            )
        pages_seen = int(locked.discovery_pages_seen or 0) + 1
        locked.discovery_cursor = next_cursor
        locked.discovery_pages_seen = pages_seen
        locked.discovery_complete = not bool(next_cursor)
        locked.status = (
            IgInboxRefreshRun.Status.DISCOVERING
            if next_cursor
            else IgInboxRefreshRun.Status.RUNNING
        )
        locked.next_attempt_at = now
        locked.attempts = 0
        locked.last_error = ""
        locked.lease_token = ""
        locked.lease_until = None
        locked.save(update_fields=[
            "discovery_cursor", "discovery_pages_seen", "discovery_complete",
            "status", "open_slot", "next_attempt_at", "attempts", "last_error",
            "lease_token", "lease_until", "completed_at", "updated_at",
        ])


def _claim_item(now):
    with transaction.atomic():
        expired_items = list(
            IgInboxRefreshItem.objects.select_for_update()
            .filter(
                status=IgInboxRefreshItem.Status.PROCESSING,
                lease_until__lte=now,
            )
            .exclude(lease_token="")
            .order_by("id")[:100]
        )
        for expired in expired_items:
            attempts = int(expired.attempts or 0) + 1
            expired.attempts = attempts
            expired.lease_token = ""
            expired.lease_until = None
            expired.last_error = "history worker lease expired"
            fields = [
                "attempts", "lease_token", "lease_until", "last_error", "updated_at",
            ]
            if attempts >= MAX_ATTEMPTS:
                expired.status = IgInboxRefreshItem.Status.FAILED
                expired.completed_at = now
                fields.extend(["status", "completed_at"])
            else:
                expired.status = IgInboxRefreshItem.Status.PENDING
                expired.next_attempt_at = _retry_at(now, attempts)
                fields.extend(["status", "next_attempt_at"])
            expired.save(update_fields=fields)
        item = (
            IgInboxRefreshItem.objects.select_for_update()
            .select_related("run")
            .filter(
                run__open_slot=1,
                run__status=IgInboxRefreshRun.Status.RUNNING,
                status=IgInboxRefreshItem.Status.PENDING,
            )
            .filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
            .filter(Q(lease_until__isnull=True) | Q(lease_until__lte=now) | Q(lease_token=""))
            .order_by("run_id", "id")
            .first()
        )
        if item is None:
            return None, False
        hidden = IgClient.objects.filter(
            igsid=item.participant_igsid, hidden_at__isnull=False
        ).only("id").first()
        if hidden:
            item.client_id = hidden.pk
            item.status = IgInboxRefreshItem.Status.SKIPPED
            item.skip_reason = "client_hidden"
            item.completed_at = now
            item.save(update_fields=[
                "client", "status", "skip_reason", "completed_at", "updated_at",
            ])
            return None, True
        token = secrets.token_hex(16)
        item.status = IgInboxRefreshItem.Status.PROCESSING
        item.lease_token = token
        item.lease_until = now + ITEM_LEASE
        item.started_at = item.started_at or now
        item.save(update_fields=[
            "status", "lease_token", "lease_until", "started_at", "updated_at",
        ])
        item._claimed_lease_token = token
        return item, True


def _finish_item_failure(item, message, *, now, transient=False, http_code=0):
    with transaction.atomic():
        locked = IgInboxRefreshItem.objects.select_for_update().filter(
            pk=item.pk,
            lease_token=item._claimed_lease_token,
            status=IgInboxRefreshItem.Status.PROCESSING,
        ).first()
        if locked is None:
            return
        attempts = int(locked.attempts or 0) + 1
        locked.attempts = attempts
        locked.last_error = str(message or "provider failure")[:1000]
        locked.provider_http_status = http_code if http_code > 0 else None
        locked.lease_token = ""
        locked.lease_until = None
        fields = [
            "attempts", "last_error", "provider_http_status", "lease_token",
            "lease_until", "updated_at",
        ]
        if transient and attempts < MAX_ATTEMPTS:
            locked.status = IgInboxRefreshItem.Status.PENDING
            locked.next_attempt_at = _retry_at(now, attempts)
            fields.extend(["status", "next_attempt_at"])
        else:
            locked.status = IgInboxRefreshItem.Status.FAILED
            locked.completed_at = now
            fields.extend(["status", "completed_at"])
        locked.save(update_fields=fields)


def _message_participants_valid(message, owner_id, participant_id):
    allowed = {owner_id, participant_id}
    if not owner_id or not participant_id or owner_id == participant_id:
        return False
    if not str(message.get("id") or "").strip():
        return False
    sender = str((message.get("from") or {}).get("id") or "").strip()
    if sender not in allowed:
        return False
    recipients = (message.get("to") or {}).get("data")
    if not isinstance(recipients, list) or not recipients:
        return False
    recipient_ids = [
        str((recipient or {}).get("id") or "").strip()
        for recipient in recipients
    ]
    return bool(
        all(recipient_id in allowed for recipient_id in recipient_ids)
        and (allowed - {sender}).intersection(recipient_ids)
    )


def _validate_existing_message(row, *, client, participant, role, provider_created_at):
    timestamp_mismatch = False
    if row.provider_created_at is not None and provider_created_at is not None:
        try:
            timestamp_mismatch = abs(
                (row.provider_created_at - provider_created_at).total_seconds()
            ) > 1
        except (TypeError, ValueError):
            timestamp_mismatch = True
    compatible_role = row.role == role or (
        role == InstagramBotMessage.Role.MANAGER
        and row.role == InstagramBotMessage.Role.MODEL
    )
    if (
        row.sender_id != participant
        or row.client_id not in {None, client.pk}
        or not compatible_role
        or timestamp_mismatch
    ):
        raise RefreshIdentityError(f"mid_identity_conflict:{row.mid}")
    update_fields = []
    if row.client_id is None:
        row.client = client
        update_fields.append("client")
    if row.provider_created_at is None and provider_created_at is not None:
        row.provider_created_at = provider_created_at
        update_fields.append("provider_created_at")
    if update_fields:
        row.save(update_fields=update_fields)


def _persist_history(item, fetched, settings_obj, *, now):
    raw_messages = list(fetched.get("messages") or [])
    owner_id = bot._provider_account_id(settings_obj)
    if any(
        not _message_participants_valid(message, owner_id, item.participant_igsid)
        for message in raw_messages
    ):
        _finish_item_failure(item, "ambiguous_message_participants", now=now)
        return
    parsed_messages = []
    for message in raw_messages:
        created_at = bot._parse_ig_time(message.get("created_time") or "")
        if created_at is None:
            _finish_item_failure(item, "malformed_message_time", now=now)
            return
        parsed_messages.append((created_at, message))
    parsed_messages.sort(
        key=lambda pair: (pair[0], str(pair[1].get("id") or "")),
        reverse=True,
    )
    parsed_messages = parsed_messages[:bot.POLL_INSTAGRAM_MESSAGE_LIMIT]
    eligible = []
    after_cutoff = 0
    for created_at, message in parsed_messages:
        if created_at > item.run.recovery_cutoff:
            after_cutoff += 1
            continue
        eligible.append((created_at, message))
    eligible.sort(key=lambda pair: (pair[0], str(pair[1].get("id") or "")))
    messages = [message for _created_at, message in parsed_messages]

    newest_row_id = 0
    try:
        with transaction.atomic():
            locked_run = IgInboxRefreshRun.objects.select_for_update().filter(
                pk=item.run_id,
                open_slot=1,
                status=IgInboxRefreshRun.Status.RUNNING,
                cancel_requested_at__isnull=True,
            ).first()
            locked_item = IgInboxRefreshItem.objects.select_for_update().filter(
                pk=item.pk,
                lease_token=item._claimed_lease_token,
                status=IgInboxRefreshItem.Status.PROCESSING,
            ).first()
            if locked_run is None or locked_item is None:
                return
            current_settings = InstagramBotSettings.objects.select_for_update().get(
                pk=settings_obj.pk
            )
            allowed_senders = bot.allowed_sender_ids(current_settings)
            sender_automation_allowed = bool(
                not allowed_senders
                or locked_item.participant_igsid in allowed_senders
            )
            client = IgClient.objects.select_for_update().filter(
                igsid=locked_item.participant_igsid
            ).first()
            if client and client.hidden_at:
                locked_item.client = client
                locked_item.status = IgInboxRefreshItem.Status.SKIPPED
                locked_item.skip_reason = "client_hidden"
                locked_item.lease_token = ""
                locked_item.lease_until = None
                locked_item.completed_at = now
                locked_item.save(update_fields=[
                    "client", "status", "skip_reason", "lease_token", "lease_until",
                    "completed_at", "updated_at",
                ])
                return
            if client is None:
                client = IgClient.get_or_create_for_sender(locked_item.participant_igsid)
                client = IgClient.objects.select_for_update().get(pk=client.pk)
            if client.hidden_at:
                locked_item.client = client
                locked_item.status = IgInboxRefreshItem.Status.SKIPPED
                locked_item.skip_reason = "client_hidden"
                locked_item.lease_token = ""
                locked_item.lease_until = None
                locked_item.completed_at = now
                locked_item.save(update_fields=[
                    "client", "status", "skip_reason", "lease_token", "lease_until",
                    "completed_at", "updated_at",
                ])
                return
            created_rows = []
            classification_rows = []
            existing_count = 0
            user_times = []
            for provider_created_at, message in eligible:
                sender = str((message.get("from") or {}).get("id") or "").strip()
                role = (
                    InstagramBotMessage.Role.USER
                    if sender == locked_item.participant_igsid
                    else InstagramBotMessage.Role.MANAGER
                )
                mid = str(message.get("id") or "").strip()
                existing = InstagramBotMessage.objects.select_for_update().filter(mid=mid).first()
                if existing:
                    _validate_existing_message(
                        existing,
                        client=client,
                        participant=locked_item.participant_igsid,
                        role=role,
                        provider_created_at=provider_created_at,
                    )
                    existing_count += 1
                    live_queue_row = bool(
                        existing.source == "webhook"
                        and existing.status in {
                            InstagramBotMessage.Status.PENDING,
                            InstagramBotMessage.Status.PROCESSING,
                        }
                    )
                    if not live_queue_row:
                        if sender_automation_allowed:
                            classification_rows.append(existing)
                        newest_row_id = max(newest_row_id, existing.pk)
                    continue
                text = str(message.get("message") or "").strip()
                attachments = bot._extract_media_urls(message)
                if not text and not attachments:
                    text = "(медіа)"
                row = InstagramBotMessage.objects.create(
                    sender_id=locked_item.participant_igsid,
                    client=client,
                    role=role,
                    text=text,
                    mid=mid,
                    status=InstagramBotMessage.Status.DONE,
                    source="manual_refresh",
                    attachments=json.dumps(attachments) if attachments else "",
                    attachment_media=bot._attachment_media_metadata(
                        attachments,
                        source="manual_refresh",
                    ),
                    provider_created_at=provider_created_at,
                    processed_at=now,
                )
                created_rows.append(row)
                if sender_automation_allowed:
                    classification_rows.append(row)
                newest_row_id = max(newest_row_id, row.pk)
                if role == InstagramBotMessage.Role.USER:
                    user_times.append(provider_created_at)
            if user_times:
                first_time = min(user_times)
                last_time = max(user_times)
                if not client.first_contact_at or first_time < client.first_contact_at:
                    client.first_contact_at = first_time
                if not client.last_message_at or last_time > client.last_message_at:
                    client.last_message_at = last_time
                # `user_times` уже отфильтрован по role=USER, поэтому это
                # корректный якорь окна Meta (Э2.6).
                if (
                    not client.last_user_message_at
                    or last_time > client.last_user_message_at
                ):
                    client.last_user_message_at = last_time
                client.save(update_fields=[
                    "first_contact_at",
                    "last_message_at",
                    "last_user_message_at",
                    "updated_at",
                ])

            from management.services import bot_followups, bot_sales_classifier

            for row in classification_rows:
                if row.role == InstagramBotMessage.Role.MODEL:
                    continue
                result = bot_sales_classifier.ensure_rule_classification(
                    client,
                    row,
                    operational_effects=False,
                ) or {}
                interaction_type = result.get("interaction_type")
                terminal_reasons = {
                    "explicit_no_buy": "explicit_no_buy",
                    "opt_out": "opt_out",
                    "spam_abuse": "spam_abuse",
                    "paid_order_waiting": "already_converted",
                }
                if interaction_type in terminal_reasons:
                    bot_followups.cancel_pending(
                        client, reason=terminal_reasons[interaction_type]
                    )

            reason = str(fetched.get("reason") or "")
            locked_item.client = client
            locked_item.status = IgInboxRefreshItem.Status.DONE
            locked_item.messages_seen = len(messages)
            locked_item.messages_created = len(created_rows)
            locked_item.messages_existing = existing_count
            locked_item.messages_after_cutoff = after_cutoff
            locked_item.analysis_watermark_message_id = newest_row_id
            locked_item.history_complete = bool(fetched.get("complete"))
            locked_item.truncated_reason = (
                "provider_latest_20_only" if reason == "instagram_latest_window" else ""
            )
            provider_code = _provider_http_code(fetched)
            locked_item.provider_http_status = provider_code if provider_code > 0 else None
            locked_item.lease_token = ""
            locked_item.lease_until = None
            locked_item.last_error = ""
            locked_item.completed_at = now
            locked_item.save(update_fields=[
                "client", "status", "messages_seen", "messages_created",
                "messages_existing", "messages_after_cutoff",
                "analysis_watermark_message_id", "history_complete", "truncated_reason",
                "provider_http_status", "lease_token", "lease_until", "last_error",
                "completed_at", "updated_at",
            ])

            if newest_row_id and sender_automation_allowed and not client.hidden_at:
                try:
                    newest = InstagramBotMessage.objects.get(pk=newest_row_id)
                    schedule_analysis(
                        client,
                        newest,
                        trigger="manual_refresh",
                        delay_seconds=0,
                    )
                except Exception as exc:
                    bot.log("warning", "inbox_refresh_analysis_schedule", repr(exc))
    except RefreshIdentityError as exc:
        _finish_item_failure(item, str(exc), now=now)
        return
    except Exception as exc:
        _finish_item_failure(item, f"projection_failed:{exc}", now=now, transient=True)
        return

def _process_one_item(item, *, now):
    settings_obj = InstagramBotSettings.load()
    if (
        bot.provider_transport(settings_obj) != bot.INSTAGRAM_LOGIN_TRANSPORT
        or bot._provider_owner_id(settings_obj) != item.run.provider_owner_id
    ):
        _finish_item_failure(item, "provider owner or transport changed", now=now)
        return
    if IgClient.objects.filter(
        igsid=item.participant_igsid, hidden_at__isnull=False
    ).exists():
        with transaction.atomic():
            locked = IgInboxRefreshItem.objects.select_for_update().filter(
                pk=item.pk, lease_token=item._claimed_lease_token
            ).first()
            if locked:
                locked.status = IgInboxRefreshItem.Status.SKIPPED
                locked.skip_reason = "client_hidden"
                locked.lease_token = ""
                locked.lease_until = None
                locked.completed_at = now
                locked.save(update_fields=[
                    "status", "skip_reason", "lease_token", "lease_until",
                    "completed_at", "updated_at",
                ])
        return
    page_token = bot.get_page_token(settings_obj)
    if not page_token:
        _finish_item_failure(item, "missing provider token", now=now)
        return
    fetched = bot._fetch_polled_conversation(
        settings_obj,
        item.conversation_id,
        page_token,
        cursor_at=None,
        cursor_id="",
        deadline=time.monotonic() + bot.POLL_MESSAGE_TIMEOUT,
        request_limit=1,
    )
    if not fetched.get("complete"):
        reason = str(fetched.get("reason") or "provider failure")
        code = _provider_http_code(fetched)
        _finish_item_failure(
            item,
            reason,
            now=now,
            transient=_is_transient_provider_failure(code, reason),
            http_code=code,
        )
        return
    _persist_history(item, fetched, settings_obj, now=now)


def _finalize_ready_run(now):
    with transaction.atomic():
        run = (
            IgInboxRefreshRun.objects.select_for_update()
            .filter(
                open_slot=1,
                status=IgInboxRefreshRun.Status.RUNNING,
                discovery_complete=True,
            )
            .order_by("id")
            .first()
        )
        if run is None or run.items.filter(status__in=[
            IgInboxRefreshItem.Status.PENDING,
            IgInboxRefreshItem.Status.PROCESSING,
        ]).exists():
            return None
        failed = run.items.filter(status=IgInboxRefreshItem.Status.FAILED).exists()
        run.status = (
            IgInboxRefreshRun.Status.COMPLETED_ERRORS
            if failed
            else IgInboxRefreshRun.Status.COMPLETED
        )
        run.open_slot = None
        run.completed_at = now
        run.save(update_fields=["status", "open_slot", "completed_at", "updated_at"])
        return run


def process_refresh_slice(*, now=None):
    """Perform at most one Meta GET and persist progress."""
    now = now or timezone.now()
    cancelled = _cancel_open_run(now)
    if cancelled:
        return {"worked": True, "phase": "cancel", "run_id": cancelled.pk}
    run = _claim_discovery_run(now)
    if run:
        _discover_one_page(run, now=now)
        return {"worked": True, "phase": "discovery", "run_id": run.pk}
    item, worked = _claim_item(now)
    if item:
        _process_one_item(item, now=now)
        return {
            "worked": True,
            "phase": "history",
            "run_id": item.run_id,
            "item_id": item.pk,
        }
    if worked:
        return {"worked": True, "phase": "skip"}
    finalized = _finalize_ready_run(now)
    if finalized:
        return {"worked": True, "phase": "finalize", "run_id": finalized.pk}
    return {"worked": False}
