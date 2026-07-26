"""
Вкладка «Бот» (адміністратори + обмежений Meta reviewer).

UI зі станом агента (запущено/зупинено, очікує повідомлення), кнопками
Start/Stop, вибором джерела ключів і онлайн-консоллю подій.
"""
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.db import transaction
from django.db.models import Count, Exists, F, OuterRef, Prefetch, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import secrets
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

from .bot_access import is_meta_bot_reviewer
from .models import (
    IgBotNotification,
    IgBotNotificationAudit,
    IgClient,
    IgDeal,
    IgPaymentProjection,
    InstagramBotLog,
    InstagramBotSettings,
)
from .services import instagram_bot as bot
from .services.bot_payment_truth import (
    annotate_verified_payment,
    latest_payment_projection,
    latest_legacy_payment_truth_deal,
    latest_verified_payment_deal,
    verified_payment_q,
)


def _is_admin(user) -> bool:
    return bool(user.is_authenticated and (user.is_staff or user.is_superuser))


def _can_use_bot(user) -> bool:
    return _is_admin(user) or is_meta_bot_reviewer(user)


def _is_reviewer_only(user) -> bool:
    return is_meta_bot_reviewer(user) and not _is_admin(user)


def privacy_policy(request):
    response = render(request, "management/privacy_policy.html")
    response["Cache-Control"] = "public, max-age=300"
    return response


def terms_of_service(request):
    response = render(request, "management/terms_of_service.html")
    response["Cache-Control"] = "public, max-age=300"
    return response


def data_deletion(request):
    response = render(request, "management/data_deletion.html")
    response["Cache-Control"] = "public, max-age=300"
    return response


def data_deletion_status(request, confirmation_code):
    from .models import BotDataDeletionRequest

    deletion_request = BotDataDeletionRequest.objects.filter(
        confirmation_code=confirmation_code
    ).first()
    response = render(
        request,
        "management/data_deletion_status.html",
        {
            "deletion_request": deletion_request,
            "confirmation_code": confirmation_code,
        },
        status=200 if deletion_request else 404,
    )
    response["Cache-Control"] = "public, max-age=300"
    return response


def _normalize_deletion_identifier(value: str) -> str:
    ident = (value or "").strip()
    if not ident:
        return ""
    ident = ident.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    match = re.search(r"(?:instagram\.com|instagr\.am)/([^/?#]+)", ident, re.I)
    if match:
        ident = match.group(1)
    ident = ident.strip().lstrip("@").lower()
    return ident


def _new_deletion_code() -> str:
    return secrets.token_hex(8).upper()


def _delete_direct_bot_records(identifier: str) -> dict:
    from .models import (
        BotDataDeletionRequest,
        IgClient,
        InstagramBotLog,
        InstagramBotMessage,
        InstagramBotProcessedMessage,
        InstagramBotRawEvent,
    )

    normalized = _normalize_deletion_identifier(identifier)
    result = {
        "normalized_identifier": normalized,
        "status": BotDataDeletionRequest.Status.NO_MATCH,
        "clients": 0,
        "messages": 0,
        "raw_events": 0,
        "logs": 0,
        "detail": "",
    }
    if not normalized:
        result["detail"] = "Empty identifier."
        return result

    with transaction.atomic():
        clients = list(
            IgClient.objects.filter(
                Q(igsid__iexact=normalized)
                | Q(username__iexact=normalized)
                | Q(display_name__iexact=normalized)
                | Q(phone_normalized__iexact=normalized)
            )
        )
        sender_ids = {normalized}
        sender_ids.update(c.igsid for c in clients if c.igsid)
        mids = list(
            InstagramBotMessage.objects.filter(
                Q(sender_id__in=sender_ids) | Q(client__in=clients)
            ).exclude(mid__isnull=True).values_list("mid", flat=True)
        )
        messages_count, _ = InstagramBotMessage.objects.filter(
            Q(sender_id__in=sender_ids) | Q(client__in=clients)
        ).delete()
        raw_events_count, _ = InstagramBotRawEvent.objects.filter(sender_id__in=sender_ids).delete()
        logs_count, _ = InstagramBotLog.objects.filter(detail__icontains=normalized).delete()
        if mids:
            InstagramBotProcessedMessage.objects.filter(mid__in=mids).delete()
        # Attribution rows are append-only and already contain only a
        # non-reversible identity digest; no mutable profile snapshot is kept.
        clients_count = len(clients)
        IgClient.objects.filter(id__in=[c.id for c in clients]).delete()

    result.update({
        "status": (
            BotDataDeletionRequest.Status.COMPLETED
            if any([clients_count, messages_count, raw_events_count, logs_count])
            else BotDataDeletionRequest.Status.NO_MATCH
        ),
        "clients": clients_count,
        "messages": messages_count,
        "raw_events": raw_events_count,
        "logs": logs_count,
        "detail": (
            "Matching DIRECT_BOT records were deleted or anonymized."
            if any([clients_count, messages_count, raw_events_count, logs_count])
            else "No matching DIRECT_BOT records were found for the supplied identifier."
        ),
    })
    return result


@require_POST
def data_deletion_submit(request):
    from .models import BotDataDeletionRequest

    identifier = (request.POST.get("identifier") or "").strip()
    deletion = _delete_direct_bot_records(identifier)
    deletion_request = BotDataDeletionRequest.objects.create(
        confirmation_code=_new_deletion_code(),
        source=BotDataDeletionRequest.Source.MANUAL_FORM,
        identifier=identifier[:255],
        normalized_identifier=deletion["normalized_identifier"][:255],
        status=deletion["status"],
        deleted_clients_count=deletion["clients"],
        deleted_messages_count=deletion["messages"],
        deleted_raw_events_count=deletion["raw_events"],
        deleted_logs_count=deletion["logs"],
        detail=deletion["detail"],
    )
    deletion_request.mark_completed()
    return redirect("management_data_deletion_status", confirmation_code=deletion_request.confirmation_code)


def _base64_url_decode(value: str) -> bytes:
    value += "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode(value.encode("utf-8"))


def _parse_meta_signed_request(signed_request: str) -> dict:
    if not signed_request or "." not in signed_request:
        return {}
    encoded_sig, encoded_payload = signed_request.split(".", 1)
    if not encoded_sig or not encoded_payload:
        return {}

    app_secret = (
        os.environ.get("IG_APP_SECRET")
        or os.environ.get("FACEBOOK_APP_SECRET")
        or getattr(settings, "IG_APP_SECRET", "")
        or getattr(settings, "FACEBOOK_APP_SECRET", "")
    )
    # This callback is public and can create compliance/audit records.  Never
    # accept an unsigned request when the production secret is missing.
    if not app_secret:
        return {}

    try:
        expected = hmac.new(
            app_secret.encode("utf-8"),
            msg=encoded_payload.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(_base64_url_decode(encoded_sig), expected):
            return {}
        payload = json.loads(_base64_url_decode(encoded_payload).decode("utf-8"))
    except (
        ValueError,
        TypeError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        binascii.Error,
    ):
        return {}
    return payload if isinstance(payload, dict) else {}


@csrf_exempt
@require_POST
def data_deletion_callback(request):
    from .models import BotDataDeletionRequest

    payload = _parse_meta_signed_request(request.POST.get("signed_request") or "")
    if not payload:
        return JsonResponse({"error": "Invalid signed_request."}, status=400)
    meta_user_id = str(payload.get("user_id") or "")
    deletion_request = BotDataDeletionRequest.objects.create(
        confirmation_code=_new_deletion_code(),
        source=BotDataDeletionRequest.Source.META_CALLBACK,
        identifier=meta_user_id[:255],
        normalized_identifier=meta_user_id[:255],
        meta_user_id=meta_user_id[:128],
        status=BotDataDeletionRequest.Status.NO_MATCH,
        detail=(
            "Meta deletion callback received. DIRECT_BOT stores Instagram Direct sender "
            "identifiers; no matching local Instagram conversation records were found for "
            "the supplied Meta app-scoped user id."
        ),
    )
    deletion_request.mark_completed(status=BotDataDeletionRequest.Status.NO_MATCH)
    status_url = request.build_absolute_uri(
        reverse("management_data_deletion_status", args=[deletion_request.confirmation_code])
    )
    return JsonResponse({
        "url": status_url,
        "confirmation_code": deletion_request.confirmation_code,
    })


def app_review_info(request):
    response = render(request, "management/app_review_info.html")
    response["Cache-Control"] = "public, max-age=300"
    return response


def _require_admin_json(request):
    if not _is_admin(request.user):
        return JsonResponse({"success": False, "error": "Доступ лише для адміністраторів."}, status=403)
    return None


def _require_bot_json(request):
    if not _can_use_bot(request.user):
        return JsonResponse({"success": False, "error": "Доступ лише до вкладки бота."}, status=403)
    return None


def _log_items(limit: int = 80):
    rows = InstagramBotLog.objects.all()[:limit]
    return [
        {
            "id": r.id,
            "level": r.level,
            "event": r.event,
            "detail": r.detail,
            "time": r.created_at.strftime("%H:%M:%S"),
            "date": r.created_at.strftime("%d.%m.%Y"),
        }
        for r in rows
    ]


@login_required(login_url="management_login")
def bot_dashboard(request):
    if not _can_use_bot(request.user):
        return redirect("management_home")
    settings_obj = InstagramBotSettings.load()
    reviewer_mode = _is_reviewer_only(request.user)
    return render(
        request,
        "management/bot.html",
        {
            "settings": settings_obj,
            "status": bot.status_snapshot(),
            "log_items": _log_items(),
            "cred_env": InstagramBotSettings.CredSource.ENV,
            "cred_custom": InstagramBotSettings.CredSource.CUSTOM,
            "has_custom_direct_token": bool(settings_obj.custom_direct_token),
            "has_custom_gemini_key": bool(settings_obj.custom_gemini_key),
            "meta_bot_reviewer_mode": reviewer_mode,
        },
    )


@login_required(login_url="management_login")
@require_POST
def bot_start_api(request):
    blocked = _require_bot_json(request)
    if blocked:
        return blocked
    bot.start_bot()
    return JsonResponse({"success": True, "status": bot.status_snapshot()})


@login_required(login_url="management_login")
@require_POST
def bot_stop_api(request):
    blocked = _require_bot_json(request)
    if blocked:
        return blocked
    bot.stop_bot()
    return JsonResponse({"success": True, "status": bot.status_snapshot()})


@login_required(login_url="management_login")
@require_GET
def bot_status_api(request):
    blocked = _require_bot_json(request)
    if blocked:
        return blocked
    try:
        after_id = int(request.GET.get("after_id") or 0)
    except (TypeError, ValueError):
        after_id = 0

    rows = InstagramBotLog.objects.all()
    if after_id:
        rows = rows.filter(id__gt=after_id)
    rows = list(rows[:120])
    rows.reverse()  # від старіших до новіших для дозапису в консоль
    items = [
        {
            "id": r.id,
            "level": r.level,
            "event": r.event,
            "detail": r.detail,
            "time": r.created_at.strftime("%H:%M:%S"),
        }
        for r in rows
    ]
    return JsonResponse({"success": True, "status": bot.status_snapshot(), "log": items})


def _notification_preview(value, limit=280):
    return bot._redact_secret_text(str(value or "")).replace("\n", " ")[:limit]


_NOTIFICATION_STATUS_LABELS = {
    IgBotNotification.Status.UNKNOWN: "Результат доставки невідомий",
    IgBotNotification.Status.DEAD_LETTER: "Спроби вичерпано",
}
_NOTIFICATION_EVENT_LABELS = {
    "takeover": "Менеджер підключився",
    "payment": "Оплата",
    "payment_link": "Посилання на оплату",
    "shipment": "Відправлення",
    "shipment_human_review": "Потрібна ручна перевірка відправлення",
    "payment_reversed_review": "Перевірка повернення або скасування оплати",
    "payment_confirmation_review": "Потрібно підтвердити оплату клієнта",
    "delivery_block": "Доставка повідомлення заблокована",
    "ai_unavailable": "ШІ тимчасово недоступний",
    "spam": "Антиспам",
    "generic": "Системне сповіщення",
}
_NOTIFICATION_FAILURE_LABELS = {
    "ambiguous_transport": "Невідомий результат мережевого запиту",
    "ambiguous_stale_sending": "Відправлення перервано до фіксації результату",
    "ambiguous_provider_response": "Неможливо прочитати відповідь Telegram",
    "retry_exhausted": "Вичерпано автоматичні спроби",
    "provider_permanent": "Telegram відхилив повідомлення",
    "configuration": "Не налаштовано Telegram",
    "rate_limited": "Telegram обмежив частоту запитів",
}


@login_required(login_url="management_login")
@require_GET
def bot_notification_review_api(request):
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    rows = IgBotNotification.objects.filter(
        status__in=[IgBotNotification.Status.UNKNOWN, IgBotNotification.Status.DEAD_LETTER]
    ).select_related("client").order_by("created_at", "id")[:100]
    items = []
    for row in rows:
        payload = row.payload if isinstance(row.payload, dict) else {}
        items.append({
            "id": row.id,
            "event_type": row.event_type,
            "client_id": row.client_id,
            "client": (row.client.display_name or row.client.username or row.client.igsid) if row.client else "",
            "status": row.status,
            "status_label": _NOTIFICATION_STATUS_LABELS.get(row.status, "Потрібна ручна перевірка"),
            "event_label": _NOTIFICATION_EVENT_LABELS.get(row.event_type, "Системне сповіщення"),
            "attempts": row.attempts,
            "failure_kind": row.failure_kind,
            "failure_label": _NOTIFICATION_FAILURE_LABELS.get(row.failure_kind, "Потрібна ручна перевірка"),
            "error": _notification_preview(row.last_error),
            "text_preview": _notification_preview(payload.get("text")),
            "created_at": row.created_at.isoformat(),
            "last_attempt_at": row.last_attempt_at.isoformat() if row.last_attempt_at else "",
        })
    return JsonResponse({"success": True, "items": items, "count": len(items)})


@login_required(login_url="management_login")
@require_POST
def bot_notification_review_action_api(request, notification_id):
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    action = (request.POST.get("action") or "").strip()
    if action not in {"resolve", "requeue"}:
        return JsonResponse({"success": False, "error": "Невідома дія."}, status=400)
    note = (request.POST.get("note") or "").strip()[:500]
    with transaction.atomic():
        row = IgBotNotification.objects.select_for_update().filter(pk=notification_id).first()
        if not row:
            return JsonResponse({"success": False, "error": "Сповіщення не знайдено."}, status=404)
        if row.status not in {IgBotNotification.Status.UNKNOWN, IgBotNotification.Status.DEAD_LETTER}:
            return JsonResponse(
                {"success": False, "error": "Сповіщення вже опрацьоване або виконується."},
                status=409,
            )
        old_status = row.status
        if action == "resolve":
            row.status = IgBotNotification.Status.RESOLVED
            row.next_attempt_at = None
            row.failure_kind = "operator_resolved"
        else:
            row.status = IgBotNotification.Status.PENDING
            row.next_attempt_at = timezone.now()
            row.attempts = 0
            row.failure_kind = "operator_requeued"
        row.save(update_fields=[
            "status", "next_attempt_at", "attempts", "failure_kind", "updated_at",
        ])
        IgBotNotificationAudit.objects.create(
            notification=row,
            actor=request.user,
            action=action,
            from_status=old_status,
            to_status=row.status,
            note=note,
        )
    bot.log(
        "warning" if action == "requeue" else "info",
        "notification_operator_action",
        f"notification={row.id}; action={action}; actor={request.user.pk}",
    )
    return JsonResponse({"success": True, "id": row.id, "status": row.status})


@login_required(login_url="management_login")
@require_GET
def bot_payment_reviews_api(request):
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    from .ig_bot_models import IgPaymentConfirmationReview
    from management.services.ig_payment_review import payment_review_order_url

    selected_id = (request.GET.get("id") or request.GET.get("payment_review") or "").strip()
    rows_qs = IgPaymentConfirmationReview.objects.filter(
        client__hidden_at__isnull=True,
    ).select_related("client", "deal", "deal__payment_projection", "order").prefetch_related(
        "decisions__actor"
    )
    if selected_id.isdigit():
        rows_qs = rows_qs.filter(pk=int(selected_id))
    else:
        rows_qs = rows_qs.filter(status=IgPaymentConfirmationReview.Status.PENDING)
    rows = rows_qs.order_by("created_at", "id")[:100]
    items = []
    for row in rows:
        evidence = row.evidence if isinstance(row.evidence, dict) else {}
        client = row.client
        draft = evidence.get("order_draft") if isinstance(evidence.get("order_draft"), dict) else {}
        decisions = [_payment_review_decision_payload(item) for item in row.decisions.all()]
        latest_decision = decisions[0] if decisions else {}
        items.append({
            "id": row.id,
            "client_id": row.client_id,
            "client": client.display_name or client.username or client.igsid,
            "status": row.status,
            "status_label": row.get_status_display(),
            "selected": selected_id.isdigit() and row.pk == int(selected_id),
            "created_at": row.created_at.isoformat(),
            "evidence": evidence.get("messages", [])[-8:],
            "media": evidence.get("media", []),
            "catalog_match": evidence.get("catalog_match", {}),
            "catalog_matches": evidence.get("catalog_matches", []),
            "deal": evidence.get("deal", {}),
            "order_draft": draft,
            "uncertainty_reasons": draft.get("uncertainty_reasons", []),
            "quoted_total": draft.get("quoted_total", ""),
            "manual_payment_truth": latest_decision.get("decision", ""),
            "provider_payment_truth": _payment_review_truth_payload(row)["provider_truth"],
            "latest_decision": latest_decision,
            "decisions": decisions,
            "confirm_url": reverse("management_bot_payment_review_action_api", args=[row.id]),
            "order_url": _existing_order_admin_url(row.order_id) if row.order_id else "",
            "create_order_url": (
                _payment_review_order_link(row, payment_review_order_url)
                if not row.order_id
                else ""
            ),
            "needs_order_resolution": bool(
                row.status == row.Status.CONFIRMED and not row.order_id
            ),
            "order_id": row.order_id,
            "order_number": row.order.order_number if row.order_id else "",
        })
    return JsonResponse({"success": True, "items": items, "count": len(items)})


def _payment_review_order_link(review, create_url_factory):
    """Link to the existing order when present, otherwise to the create form."""
    if review.order_id:
        return _existing_order_admin_url(review.order_id)
    if (
        review.status == review.Status.CONFIRMED
        and _latest_payment_review_decision(review)
        and _latest_payment_review_decision(review).decision == "manager_verified"
    ):
        return create_url_factory(review.id)
    return ""


def _existing_order_admin_url(order_id):
    """Return the staff order editor URL used by the custom admin panel."""
    try:
        path = reverse("admin_panel", urlconf="twocomms.urls")
    except Exception:
        return ""
    base = (getattr(settings, "SITE_BASE_URL", "") or "https://twocomms.shop").rstrip("/")
    return f"{base}{path}?section=orders&edit_order={int(order_id)}"


def _payment_review_decision_payload(decision) -> dict:
    if not decision:
        return {}
    actor = getattr(decision, "actor", None)
    return {
        "id": decision.pk,
        "decision": decision.decision,
        "decision_label": decision.get_decision_display(),
        "verification_source": decision.verification_source,
        "verification_scope": decision.verification_scope,
        "confirmed_amount": (
            f"{decision.confirmed_amount:.2f}"
            if decision.confirmed_amount is not None
            else ""
        ),
        "currency": decision.currency or "UAH",
        "amount_source": decision.amount_source or "",
        "amount_evidence_message_ids": decision.amount_evidence_message_ids or [],
        "reason_code": decision.reason_code,
        "reason_text": decision.reason_text,
        "actor_id": decision.actor_id,
        "actor": getattr(actor, "get_username", lambda: "")(),
        "actor_source": decision.actor_source,
        "actor_external_id": decision.actor_external_id,
        "actor_label": decision.actor_label,
        "evidence_watermark_message_id": decision.evidence_watermark_message_id,
        "review_status_before": decision.review_status_before,
        "review_status_after": decision.review_status_after,
        "stage_before": decision.stage_before,
        "stage_after": decision.stage_after,
        "created_at": decision.created_at.isoformat(),
    }


def _latest_payment_review_decision(review):
    workspace_decisions = getattr(review, "_workspace_decisions", None)
    if workspace_decisions is not None:
        return workspace_decisions[0] if workspace_decisions else None
    prefetched = getattr(review, "_prefetched_objects_cache", {}).get("decisions")
    if prefetched is not None:
        return prefetched[0] if prefetched else None
    return review.decisions.select_related("actor").order_by("-id").first()


def _payment_review_decisions(review) -> list:
    workspace_decisions = getattr(review, "_workspace_decisions", None)
    if workspace_decisions is not None:
        return workspace_decisions
    prefetched = getattr(review, "_prefetched_objects_cache", {}).get("decisions")
    if prefetched is not None:
        return list(prefetched)
    return list(review.decisions.select_related("actor").order_by("-id")[:20])


def _payment_review_workspace_queryset():
    from .ig_bot_models import (
        IgOrderAttribution,
        IgPaymentConfirmationReview,
        IgPaymentReviewDecision,
    )

    return IgPaymentConfirmationReview.objects.select_related(
        "client", "deal", "deal__payment_projection", "order",
    ).prefetch_related(
        Prefetch(
            "decisions",
            queryset=IgPaymentReviewDecision.objects.select_related("actor").order_by("-id")[:20],
            to_attr="_workspace_decisions",
        ),
        Prefetch(
            "order_attributions",
            queryset=IgOrderAttribution.objects.select_related(
                "order", "deal", "deal__payment_projection", "client",
            ).order_by("-id")[:1],
            to_attr="_workspace_attributions",
        ),
    )


def _order_attribution_workspace_queryset():
    from .ig_bot_models import IgOrderAttribution

    return IgOrderAttribution.objects.select_related(
        "client", "order", "deal", "deal__payment_projection", "payment_review",
    )


def _orders_workspace_url(*, view="all", review_id=None, client_id=None) -> str:
    base = (getattr(settings, "MANAGEMENT_BASE_URL", "") or "https://management.twocomms.shop").rstrip("/")
    params = ["section=orders", f"view={view}"]
    if review_id:
        params.append(f"review={int(review_id)}")
    if client_id:
        params.append(f"client_id={int(client_id)}")
    return f"{base}/bot/?{'&'.join(params)}"


def _payment_review_truth_payload(review, decision=None) -> dict:
    from management.services.ig_payment_review import payment_confirmation_candidate
    from management.services.ig_commercial_episodes import payment_truth_snapshot

    decision = decision or _latest_payment_review_decision(review)
    payload = payment_truth_snapshot(
        deal=review.deal if review.deal_id else None,
        review=review,
        order=review.order if review.order_id else None,
        decision=decision,
    )
    payload.update({
        "provider_source": (
            "provider_projection" if payload.get("projection_id") else "none"
        ),
        "verification_source": payload.get("manager_source", ""),
        "verification_scope": payload.get("manager_scope", ""),
        "confirmation_candidate": payment_confirmation_candidate(review),
    })
    return payload


def _bounded_text(value, limit: int) -> str:
    if value is None or isinstance(value, (dict, list, tuple, set)) or isinstance(value, bool):
        return ""
    return str(value).strip()[:limit]


def _bounded_int(value, *, minimum=0, maximum=None):
    if value is None or isinstance(value, (dict, list, tuple, set, bool)):
        return None
    try:
        result = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    if result < minimum or (maximum is not None and result > maximum):
        return None
    return result


def _bounded_int_list(value, *, limit=20) -> list[int]:
    if not isinstance(value, list):
        return []
    result = []
    for raw in value:
        item = _bounded_int(raw)
        if item is None:
            continue
        result.append(item)
        if len(result) >= limit:
            break
    return result


def _bounded_scalar_map(value, *, limit=20) -> dict:
    if not isinstance(value, dict):
        return {}
    result = {}
    for raw_key, raw_value in value.items():
        key = _bounded_text(raw_key, 64)
        scalar = _bounded_text(raw_value, 240)
        if not key or not scalar:
            continue
        result[key] = scalar
        if len(result) >= limit:
            break
    return result


def _review_media_groups(evidence: dict) -> dict:
    groups = {"receipts": [], "products": [], "custom_print": [], "unknown": []}
    rows = evidence.get("media", []) if isinstance(evidence, dict) else []
    for raw in (rows[:80] if isinstance(rows, list) else []):
        if not isinstance(raw, dict):
            continue
        item = {}
        role = _bounded_text(raw.get("role"), 32).lower()
        if role:
            item["role"] = role
        for key in ("message_id", "source_message_id", "product_id"):
            value = _bounded_int(raw.get(key))
            if value is not None:
                item[key] = value
        product_title = _bounded_text(raw.get("product_title"), 240)
        if product_title:
            item["product_title"] = product_title
        confidence = _bounded_text(raw.get("confidence"), 40)
        if confidence:
            item["confidence"] = confidence
        for key in ("url", "local_url"):
            safe_url = _safe_media_url(raw.get(key))
            if safe_url:
                item[key] = safe_url
        safe_product_url = _safe_storefront_url(raw.get("product_url"))
        if safe_product_url:
            item["product_url"] = safe_product_url
        group_role = role or "other"
        if group_role in {"receipt", "payment_candidate"}:
            groups["receipts"].append(item)
        elif group_role in {"product", "purchase_candidate", "interest"}:
            groups["products"].append(item)
        elif group_role in {"custom_reference", "custom_print", "custom_candidate"}:
            groups["custom_print"].append(item)
        else:
            groups["unknown"].append(item)
    return {key: values[:20] for key, values in groups.items()}


def _safe_relative_url(value: str) -> str:
    value = _bounded_text(value, 1200)
    if value.startswith("/") and not value.startswith("//") and "\\" not in value:
        return value
    return ""


def _safe_media_url(value) -> str:
    value = _bounded_text(value, 1200)
    relative = _safe_relative_url(value)
    if relative:
        return relative
    try:
        parsed = urlsplit(value)
    except ValueError:
        return ""
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return ""
    return value


def _safe_storefront_url(value) -> str:
    value = _bounded_text(value, 1200)
    relative = _safe_relative_url(value)
    if relative:
        base = (getattr(settings, "SITE_BASE_URL", "") or "https://twocomms.shop").rstrip("/")
        return f"{base}{relative}"[:1200]
    try:
        parsed = urlsplit(value)
        configured_host = urlsplit(
            getattr(settings, "SITE_BASE_URL", "") or "https://twocomms.shop"
        ).hostname
    except ValueError:
        return ""
    trusted_hosts = {"twocomms.shop", "www.twocomms.shop"}
    if configured_host:
        trusted_hosts.add(configured_host.lower())
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.hostname.lower() not in trusted_hosts
        or parsed.username
        or parsed.password
    ):
        return ""
    return value


def _catalog_workspace_candidate(raw: dict) -> dict:
    if not isinstance(raw, dict):
        return {}
    item = {}
    for key in ("product_id", "color_variant_id"):
        value = _bounded_int(raw.get(key))
        if value is not None:
            item[key] = value
    for key, limit in (
        ("status", 40),
        ("title", 240),
        ("slug", 180),
        ("catalog_price", 40),
        ("confidence", 40),
        ("reason", 240),
    ):
        value = _bounded_text(raw.get(key), limit)
        if value:
            item[key] = value
    for key in ("url", "product_url"):
        safe_url = _safe_storefront_url(raw.get(key))
        if safe_url:
            item[key] = safe_url
    for key in ("source_media_indexes", "source_message_ids"):
        values = _bounded_int_list(raw.get(key))
        if values:
            item[key] = values
    variants = []
    raw_variants = raw.get("variant_candidates")
    for raw_variant in (raw_variants[:20] if isinstance(raw_variants, list) else []):
        if not isinstance(raw_variant, dict):
            continue
        variant = {}
        variant_id = _bounded_int(raw_variant.get("id"))
        if variant_id is not None:
            variant["id"] = variant_id
        for key in ("color", "sku"):
            value = _bounded_text(raw_variant.get(key), 80)
            if value:
                variant[key] = value
        if variant:
            variants.append(variant)
    if variants:
        item["variant_candidates"] = variants
    return item


def _catalog_workspace_candidates(evidence: dict) -> list:
    rows = evidence.get("catalog_matches", []) if isinstance(evidence, dict) else []
    result = []
    for raw in (rows[:20] if isinstance(rows, list) else []):
        if not isinstance(raw, dict):
            continue
        item = _catalog_workspace_candidate(raw)
        if item:
            result.append(item)
    return result


def _draft_workspace_items(raw_items) -> list:
    result = []
    for raw in (raw_items[:20] if isinstance(raw_items, list) else []):
        if not isinstance(raw, dict):
            continue
        item = {}
        for key in ("product_id", "color_variant_id", "source_message_id"):
            value = _bounded_int(raw.get(key))
            if value is not None:
                item[key] = value
        qty = _bounded_int(raw.get("qty"), minimum=1, maximum=999)
        if qty is not None:
            item["qty"] = qty
        for key, limit in (
            ("title", 240),
            ("size", 40),
            ("fit", 40),
            ("fit_option_code", 80),
            ("fit_option_label", 160),
            ("unit_price", 40),
            ("line_total", 40),
            ("price_source", 80),
        ):
            value = _bounded_text(raw.get(key), limit)
            if value:
                item[key] = value
        evidence_ids = _bounded_int_list(raw.get("price_evidence_message_ids"))
        if evidence_ids:
            item["price_evidence_message_ids"] = evidence_ids
        for key in ("option_values", "option_labels"):
            values = _bounded_scalar_map(raw.get(key))
            if values:
                item[key] = values
        catalog = _catalog_workspace_candidate(raw.get("catalog"))
        if catalog:
            item["catalog"] = catalog
        if item:
            result.append(item)
    return result


def _draft_workspace_delivery(raw_delivery) -> dict:
    if not isinstance(raw_delivery, dict):
        return {}
    result = {}
    for key, limit in (
        ("full_name", 180),
        ("phone", 40),
        ("email", 254),
        ("city", 120),
        ("office", 180),
        ("address", 240),
        ("np_settlement_ref", 64),
        ("np_city_ref", 64),
        ("np_warehouse_ref", 64),
    ):
        value = _bounded_text(raw_delivery.get(key), limit)
        if value:
            result[key] = value
    return result


def _draft_workspace_reasons(raw_reasons) -> list[str]:
    if not isinstance(raw_reasons, list):
        return []
    result = []
    for raw in raw_reasons:
        reason = _bounded_text(raw, 240)
        if reason:
            result.append(reason)
        if len(result) >= 20:
            break
    return result


def _amount_workspace_evidence(evidence) -> list[dict]:
    if not isinstance(evidence, dict):
        return []
    result = []
    for raw in evidence.get("amount_evidence") or []:
        if not isinstance(raw, dict):
            continue
        message_id = _bounded_int(raw.get("message_id"))
        amount = _bounded_text(raw.get("amount"), 40)
        if not message_id or not amount:
            continue
        result.append({
            "message_id": message_id,
            "amount": amount,
            "kind": _bounded_text(raw.get("kind"), 40),
            "role": _bounded_text(raw.get("role"), 24),
            "quote": _bounded_text(raw.get("quote"), 300),
        })
        if len(result) >= 20:
            break
    return result


def _order_workspace_order_payload(order) -> dict:
    if not order:
        return {}
    from management.services.ig_order_amounts import order_amounts

    amounts = order_amounts(order)
    return {
        "id": order.pk,
        "number": order.order_number,
        "status": order.status,
        "status_label": order.get_status_display(),
        "payment_status": order.payment_status,
        "payment_status_label": order.get_payment_status_display(),
        "amount": f"{amounts['payable']:.2f}",
        "subtotal": f"{amounts['subtotal']:.2f}",
        "discount_amount": f"{amounts['discount']:.2f}",
        "sale_source": order.sale_source,
        "tracking_number": order.tracking_number or "",
        "url": _existing_order_admin_url(order.pk),
    }


def _post_sale_case_payload(case) -> dict:
    order = case.order if case.order_id else None
    return {
        "id": case.pk,
        "case_type": case.case_type,
        "case_type_label": case.get_case_type_display(),
        "status": case.status,
        "status_label": case.get_status_display(),
        "needs_action": case.status in {"needs_details", "open"},
        "order": (_order_workspace_order_payload(order) if order else None),
        "commercial_episode_id": case.commercial_episode_id,
        "source_message_id": case.source_message_id,
        "evidence_message_ids": list(case.evidence_message_ids or [])[:20],
        "source_item_title": case.source_item_title,
        "source_fit": case.source_fit,
        "source_size": case.source_size,
        "requested_fit": case.requested_fit,
        "requested_size": case.requested_size,
        "reason": case.reason,
        "manager_note": case.manager_note,
        "created_at": case.created_at.isoformat(),
        "updated_at": case.updated_at.isoformat(),
        "resolved_at": case.resolved_at.isoformat() if case.resolved_at else "",
        "action_url": reverse(
            "management_bot_post_sale_case_api",
            args=[case.client_id, case.pk],
        ),
    }


def _post_sale_workspace_payload(client) -> dict:
    from .ig_bot_models import IgOrderAttribution, IgPostSaleCase

    cases = list(
        IgPostSaleCase.objects.filter(client=client)
        .select_related("order", "commercial_episode", "source_message")
        .order_by("-updated_at", "-id")[:20]
    )
    attributions = list(
        IgOrderAttribution.objects.filter(client=client)
        .select_related("order")
        .order_by("-created_at", "-id")[:30]
    )
    seen = set()
    choices = []
    for attribution in attributions:
        if attribution.order_id in seen:
            continue
        seen.add(attribution.order_id)
        choices.append(_order_workspace_order_payload(attribution.order))
    actionable = {IgPostSaleCase.Status.NEEDS_DETAILS, IgPostSaleCase.Status.OPEN}
    return {
        "action_count": sum(case.status in actionable for case in cases),
        "items": [_post_sale_case_payload(case) for case in cases],
        "order_choices": choices,
    }


def _order_attribution_workspace_payload(attribution) -> dict:
    order = getattr(attribution, "order", None)
    deal = getattr(attribution, "deal", None)
    projection = None
    if deal:
        try:
            projection = deal.payment_projection
        except IgPaymentProjection.DoesNotExist:
            projection = None
    provider_source = attribution.payment_source if attribution.payment_source.startswith("provider_") else "none"
    provider_truth = projection.truth if projection else IgDeal.PaymentTruth.UNVERIFIED
    if (
        attribution.payment_source == "provider_projection"
        and provider_truth == IgDeal.PaymentTruth.UNVERIFIED
    ):
        provider_truth = IgDeal.PaymentTruth.CONFIRMED
    manager_truth = (
        "manager_verified"
        if attribution.payment_source == "manager_verified"
        else ""
    )
    if attribution.creation_mode == "linked_existing":
        approval_state = "linked_existing"
    elif attribution.creation_mode == "manager_review":
        approval_state = "created_new"
    else:
        approval_state = "confirmed"
    client = attribution.client
    items = _draft_workspace_items(attribution.item_provenance)
    from management.services.ig_order_amounts import order_amounts

    order_payment_total = order_amounts(order)["payable"]
    return {
        "id": f"order-{order.pk}",
        "card_key": f"order:{order.pk}",
        "attribution_id": attribution.pk,
        "review_id": attribution.payment_review_id,
        "client": {
            "id": client.pk,
            "name": client.display_name or client.username or client.igsid,
            "username": client.username or "",
            "igsid": client.igsid,
            "avatar": client.avatar_local or client.profile_pic_url or "",
        },
        "approval": {
            "state": approval_state,
            "status": "confirmed",
            "status_label": "Підтверджено",
            "needs_action": False,
            "can_confirm": False,
            "can_reject": False,
            "can_link_existing": False,
            "can_create": False,
            "action_url": "",
            "create_order_url": "",
            "link_existing": {},
        },
        "draft": {
            "items": items,
            "quoted_total": (
                str(attribution.negotiated_total)
                if attribution.negotiated_total is not None
                else f"{order_payment_total:.2f}"
            ),
            "packaging_preference": "",
            "delivery": {},
            "uncertainty_reasons": [],
            "catalog_candidates": [],
        },
        "media": {"receipts": [], "products": [], "custom_print": [], "unknown": []},
        "payment": {
            "order_subtotal": f"{order_amounts(order)['subtotal']:.2f}",
            "order_discount_amount": f"{order_amounts(order)['discount']:.2f}",
            "order_total": f"{order_payment_total:.2f}",
            "provider_truth": provider_truth,
            "provider_source": provider_source,
            "manager_truth": manager_truth,
            "verification_source": "manager" if manager_truth else "",
            "verification_scope": "",
            "authoritative_for_fulfillment": bool(
                manager_truth == "manager_verified"
                or provider_truth in {
                    IgDeal.PaymentTruth.CONFIRMED,
                    IgDeal.PaymentTruth.PARTIALLY_REFUNDED,
                }
            ),
        },
        "order": _order_workspace_order_payload(order),
        "fulfillment": {
            "deal_id": attribution.deal_id,
            "delivery_status": getattr(deal, "delivery_status", "") if deal else "",
            "delivery_status_label": (
                deal.get_delivery_status_display()
                if deal and deal.delivery_status
                else ""
            ),
            "delivery_error": getattr(deal, "delivery_error", "") if deal else "",
            "has_validated_refs": bool(
                (deal and deal.np_settlement_ref and deal.np_city_ref and deal.np_warehouse_ref)
                or (order and order.np_settlement_ref and order.np_city_ref and order.np_warehouse_ref)
            ),
        },
        "decision": {},
        "decision_history": [],
        "order_url": _existing_order_admin_url(order.pk),
        "workspace_url": _orders_workspace_url(
            view="confirmed",
            client_id=client.pk,
        ),
        "origin": {
            "creation_mode": attribution.creation_mode,
            "creation_mode_label": attribution.get_creation_mode_display(),
            "payment_source": attribution.payment_source,
            "payment_source_label": attribution.get_payment_source_display(),
            "price_source": attribution.price_source,
        },
        "created_at": attribution.created_at.isoformat(),
        "updated_at": attribution.created_at.isoformat(),
    }


def _payment_review_workspace_payload(review) -> dict:
    from management.services.ig_payment_review import payment_review_order_url
    from management.services.ig_payment_review import reconcile_duplicate_payment_review

    canonical_review = reconcile_duplicate_payment_review(review)
    if canonical_review and review.status == review.Status.SUPERSEDED:
        # The reconciliation writes the order pointer; keep this response
        # object coherent without a second query in the hot payload path.
        if canonical_review.order_id and not review.order_id:
            review.order_id = canonical_review.order_id
        review.superseded_by = canonical_review

    evidence = review.evidence if isinstance(review.evidence, dict) else {}
    draft = evidence.get("order_draft") if isinstance(evidence.get("order_draft"), dict) else {}
    decisions = _payment_review_decisions(review)
    decision = decisions[0] if decisions else None
    payment = _payment_review_truth_payload(review, decision)
    order = getattr(review, "order", None) if review.order_id else None
    deal = getattr(review, "deal", None) if review.deal_id else None
    attributions = getattr(review, "_workspace_attributions", None)
    if attributions is None:
        attributions = list(review.order_attributions.select_related("order").order_by("-id")[:1])
    attribution = attributions[0] if attributions else None
    status = review.status
    if status == review.Status.SUPERSEDED:
        approval_state = "superseded"
    elif status == review.Status.CONFIRMED and payment["needs_reconciliation"]:
        approval_state = "payment_reconciliation"
    elif review.order_id:
        if attribution and attribution.creation_mode == "linked_existing":
            approval_state = "linked_existing"
        elif attribution and attribution.creation_mode in {"manager_review", "provider_auto"}:
            approval_state = "created_new"
        else:
            approval_state = "order_created"
    elif status == review.Status.CONFIRMED:
        approval_state = "needs_order_resolution"
    elif status == review.Status.CANCELLED:
        approval_state = "rejected"
    else:
        approval_state = "pending"
    action_url = reverse("management_bot_payment_review_action_api", args=[review.pk])
    create_order_url = _payment_review_order_link(review, payment_review_order_url)
    order_url = _existing_order_admin_url(review.order_id) if review.order_id else ""
    needs_order_resolution = bool(
        status == review.Status.CONFIRMED
        and not review.order_id
        and payment["authoritative_for_fulfillment"]
    )
    needs_amount_clarification = bool(
        status == review.Status.CONFIRMED
        and not review.order_id
        and not payment["needs_reconciliation"]
        and not payment["authoritative_for_fulfillment"]
        and decision
        and decision.decision == "manager_verified"
    )
    if needs_amount_clarification:
        approval_state = "amount_clarification"
    return {
        "id": review.pk,
        "card_key": f"review:{review.pk}",
        "review_id": review.pk,
        "client": {
            "id": review.client_id,
            "name": review.client.display_name or review.client.username or review.client.igsid,
            "username": review.client.username or "",
            "igsid": review.client.igsid,
            "avatar": review.client.avatar_local or review.client.profile_pic_url or "",
        },
        "approval": {
            "state": approval_state,
            "status": status,
            "status_label": review.get_status_display(),
            "needs_action": (
                status == review.Status.PENDING
                or needs_order_resolution
                or needs_amount_clarification
                or payment["needs_reconciliation"]
            ),
            "can_confirm": status == review.Status.PENDING,
            "can_reject": status == review.Status.PENDING,
            "can_link_existing": needs_order_resolution,
            "can_create": needs_order_resolution,
            "can_clarify_amount": needs_amount_clarification,
            "superseded_by_review_id": review.superseded_by_id if status == review.Status.SUPERSEDED else None,
            "action_url": action_url,
            "create_order_url": create_order_url if needs_order_resolution else "",
            "link_existing": {
                "action": "link_order",
                "action_url": action_url if needs_order_resolution else "",
                "requires_exact_order_identifier": True,
            },
        },
        "draft": {
            "items": _draft_workspace_items(draft.get("items")),
            "quoted_total": _bounded_text(draft.get("quoted_total"), 40),
            "packaging_preference": _bounded_text(
                draft.get("packaging_preference"), 160,
            ),
            "delivery": _draft_workspace_delivery(draft.get("delivery")),
            "uncertainty_reasons": _draft_workspace_reasons(
                draft.get("uncertainty_reasons"),
            ),
            "catalog_candidates": _catalog_workspace_candidates(evidence),
            "amount_evidence": _amount_workspace_evidence(evidence),
        },
        "media": _review_media_groups(evidence),
        "payment": payment,
        "fulfillment": {
            "deal_id": review.deal_id,
            "delivery_status": getattr(deal, "delivery_status", "") if deal else "",
            "delivery_status_label": deal.get_delivery_status_display() if deal and deal.delivery_status else "",
            "delivery_error": getattr(deal, "delivery_error", "") if deal else "",
            "has_validated_refs": bool(
                deal
                and deal.np_settlement_ref
                and deal.np_city_ref
                and deal.np_warehouse_ref
            ),
        },
        "decision": _payment_review_decision_payload(decision),
        "decision_history": [_payment_review_decision_payload(item) for item in decisions[:20]],
        "order": _order_workspace_order_payload(order),
        "order_url": order_url,
        "workspace_url": _orders_workspace_url(
            view=(
                "action"
                if status == review.Status.PENDING
                or needs_order_resolution
                or needs_amount_clarification
                or payment["needs_reconciliation"]
                else "confirmed"
            ),
            review_id=review.pk,
        ),
        "origin": {
            "creation_mode": attribution.creation_mode if attribution else "",
            "creation_mode_label": attribution.get_creation_mode_display() if attribution else "",
            "payment_source": attribution.payment_source if attribution else "",
            "payment_source_label": attribution.get_payment_source_display() if attribution else "",
            "price_source": attribution.price_source if attribution else "",
        },
        "created_at": review.created_at.isoformat(),
        "updated_at": review.updated_at.isoformat(),
    }


def _canonical_order_workspace_cards(review_rows, attribution_rows, *, limit=100) -> list:
    review_cards = [_payment_review_workspace_payload(row) for row in review_rows]
    represented_order_ids = {
        item["order"].get("id")
        for item in review_cards
        if item.get("order") and item["order"].get("id")
    }
    attribution_cards = [
        _order_attribution_workspace_payload(row)
        for row in attribution_rows
        if row.order_id not in represented_order_ids
    ]
    cards = review_cards + attribution_cards
    cards.sort(key=lambda item: (item.get("created_at", ""), str(item.get("id", ""))), reverse=True)
    return cards[:limit]


@login_required(login_url="management_login")
@require_GET
def bot_orders_workspace_api(request):
    """Bounded source of truth for the dedicated ``Замовлення`` workspace."""
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    from .ig_bot_models import IgPaymentConfirmationReview

    view = (request.GET.get("view") or "action").strip().lower()
    if view not in {"action", "confirmed", "all"}:
        view = "action"
    try:
        client_id = int(request.GET.get("client_id") or 0)
    except (TypeError, ValueError):
        client_id = 0
    try:
        limit = max(1, min(int(request.GET.get("limit") or 50), 100))
    except (TypeError, ValueError):
        limit = 50
    try:
        selected_review_id = int(
            request.GET.get("review")
            or request.GET.get("payment_review")
            or 0
        )
    except (TypeError, ValueError):
        selected_review_id = 0

    base = _payment_review_workspace_queryset().filter(
        client__hidden_at__isnull=True,
    )
    from management.services.ig_payment_review import reconcile_duplicate_payment_review

    # Reconcile legacy watermark duplicates before calculating badges/counts;
    # otherwise the same receipt remains a false second manager task.
    duplicate_candidates = base.filter(
        status=IgPaymentConfirmationReview.Status.CONFIRMED,
        order_id__isnull=True,
    )
    for duplicate_review in duplicate_candidates:
        reconcile_duplicate_payment_review(duplicate_review)
    attribution_base = _order_attribution_workspace_queryset().filter(
        client__hidden_at__isnull=True,
    )
    if client_id:
        base = base.filter(client_id=client_id)
        attribution_base = attribution_base.filter(client_id=client_id)
    reconciliation_review_ids = [
        row.pk
        for row in list(base)
        if row.status == IgPaymentConfirmationReview.Status.CONFIRMED
        and _payment_review_truth_payload(row)["needs_reconciliation"]
    ]
    represented_order_ids = base.exclude(order_id__isnull=True).values("order_id")
    attribution_base = attribution_base.exclude(
        order_id__in=Subquery(represented_order_ids)
    )
    attributed_count = attribution_base.count()
    action_filter = (
        Q(status=IgPaymentConfirmationReview.Status.PENDING)
        | Q(
            status=IgPaymentConfirmationReview.Status.CONFIRMED,
            order_id__isnull=True,
        )
        | Q(pk__in=reconciliation_review_ids)
    )
    counts = {
        "action": base.filter(action_filter).count(),
        "confirmed": (
            base.filter(status=IgPaymentConfirmationReview.Status.CONFIRMED).count()
            + attributed_count
        ),
        "all": base.count() + attributed_count,
    }
    attribution_rows = []
    if selected_review_id:
        rows = base.filter(pk=selected_review_id)
    elif view == "action":
        rows = base.filter(action_filter)
    elif view == "confirmed":
        rows = base.filter(status=IgPaymentConfirmationReview.Status.CONFIRMED)
        attribution_rows = list(attribution_base.order_by("-created_at", "-id")[:limit])
    else:
        rows = base
        attribution_rows = list(attribution_base.order_by("-created_at", "-id")[:limit])
    review_rows = list(rows.order_by("-created_at", "-id")[:limit])
    items = _canonical_order_workspace_cards(
        review_rows,
        attribution_rows,
        limit=limit,
    )
    return JsonResponse({
        "success": True,
        "section": "orders",
        "view": view,
        "selected_review_id": selected_review_id or None,
        "counts": counts,
        "items": items,
    })


@login_required(login_url="management_login")
@require_GET
def bot_order_candidates_api(request):
    """Compact, searchable staff selector for linking an existing order."""
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    from orders.models import Order

    try:
        client_id = int(request.GET.get("client_id") or 0)
    except (TypeError, ValueError):
        client_id = 0
    if not client_id:
        return JsonResponse(
            {"success": False, "error": "Потрібен Instagram-клієнт."},
            status=400,
        )
    client = IgClient.objects.filter(pk=client_id).first()
    if not client or client.hidden_at:
        return JsonResponse(
            {"success": False, "error": "Instagram-клієнта не знайдено."},
            status=404,
        )
    try:
        review_id = int(request.GET.get("review_id") or 0)
    except (TypeError, ValueError):
        review_id = 0
    review = None
    if review_id:
        from .ig_bot_models import IgPaymentConfirmationReview
        from management.services.ig_order_links import authoritative_manager_decision

        review = IgPaymentConfirmationReview.objects.select_related("client").filter(
            pk=review_id,
            client=client,
        ).first()
        if not review:
            return JsonResponse(
                {"success": False, "error": "Перевірку оплати для цього клієнта не знайдено."},
                status=404,
            )
        from management.services.ig_payment_review import reconcile_duplicate_payment_review

        reconcile_duplicate_payment_review(review)
        if not authoritative_manager_decision(review) and not (
            review.status == review.Status.SUPERSEDED and review.order_id
        ):
            return JsonResponse(
                {"success": False, "error": "Спочатку потрібне підтверджене рішення менеджера."},
                status=409,
            )
    q = str(request.GET.get("q") or "").strip()[:120]
    try:
        limit = max(1, min(int(request.GET.get("limit") or 20), 40))
    except (TypeError, ValueError):
        limit = 20

    queryset = Order.objects.select_related(
        "instagram_attribution",
        "instagram_attribution__client",
    ).prefetch_related("items").order_by("-created", "-id")
    if q:
        queryset = queryset.filter(
            Q(order_number__icontains=q)
            | Q(tracking_number__icontains=q)
            | Q(full_name__icontains=q)
            | Q(phone__icontains=q)
            | Q(items__title__icontains=q)
            | Q(items__product__title__icontains=q)
        ).distinct()
    rows = list(queryset[:limit])
    items = []
    from management.services.ig_order_links import order_link_override_requirements
    from management.services.ig_order_amounts import order_amounts

    for order in rows:
        amounts = order_amounts(order)
        try:
            attribution = order.instagram_attribution
        except Exception:
            attribution = None
        blocked_reason = ""
        if order.status == "cancelled":
            blocked_reason = "cancelled"
        elif attribution and attribution.client_id != client.pk:
            blocked_reason = "owned_by_other_client"
        if not blocked_reason:
            from .ig_bot_models import (
                IgCommercialEpisode,
                IgDeal,
                IgPaymentConfirmationReview,
            )

            deal_owners = set(
                IgDeal.objects.filter(order=order).values_list("client_id", flat=True)
            )
            review_owners = set(
                IgPaymentConfirmationReview.objects.filter(order=order).values_list(
                    "client_id", flat=True
                )
            )
            episode_owners = set(
                IgCommercialEpisode.objects.filter(intended_order=order).values_list(
                    "client_id", flat=True
                )
            )
            all_owners = deal_owners | review_owners | episode_owners
            if any(owner_id != client.pk for owner_id in all_owners):
                blocked_reason = "owned_by_other_client"
            elif review and review.status == IgPaymentConfirmationReview.Status.SUPERSEDED and review.order_id == order.pk:
                blocked_reason = "already_linked_payment"
            elif review and IgCommercialEpisode.objects.filter(
                intended_order=order
            ).exclude(primary_payment_review=review).exists():
                blocked_reason = "owned_by_other_episode"
        override_conflicts = []
        allowed_override_codes = []
        if review and not blocked_reason:
            try:
                requirements = order_link_override_requirements(review, order)
            except ValueError:
                blocked_reason = "review_not_confirmed"
            else:
                override_conflicts = requirements["conflicts"]
                allowed_override_codes = requirements["allowed_codes"]
        elif order.status in {"ship", "done"}:
            override_conflicts = ["terminal_order"]
            allowed_override_codes = ["historical_fulfilled_order", "historical_import"]
        items.append({
            "id": order.pk,
            "number": order.order_number,
            "created_at": order.created.isoformat() if order.created else "",
            "client_name": order.full_name,
            "phone_masked": (
                ("***" + str(order.phone)[-4:]) if order.phone else ""
            ),
            "items": [
                {
                    "title": item.title,
                    "size": item.size or "",
                    "qty": item.qty,
                    "unit_price": f"{item.unit_price:.2f}",
                    "line_total": f"{item.line_total:.2f}",
                }
                for item in list(order.items.all())[:8]
            ],
            "amount": f"{amounts['payable']:.2f}",
            "subtotal": f"{amounts['subtotal']:.2f}",
            "discount_amount": f"{amounts['discount']:.2f}",
            "payment_status": order.payment_status,
            "payment_status_label": order.get_payment_status_display(),
            "status": order.status,
            "status_label": order.get_status_display(),
            "tracking_number": order.tracking_number or "",
            "shipment_status": order.shipment_status or "",
            "source": order.source,
            "sale_source": order.sale_source,
            "selectable": not blocked_reason,
            "blocked_reason": blocked_reason,
            "blocked_reason_label": {
                "already_linked_payment": "Ця оплата вже прив'язана до цього замовлення",
                "owned_by_other_episode": "Замовлення належить іншому циклу клієнта",
                "owned_by_other_client": "Замовлення вже прив'язане до іншого клієнта",
                "cancelled": "Замовлення скасоване",
            }.get(blocked_reason, ""),
            "requires_override": bool(override_conflicts),
            "override_conflicts": override_conflicts,
            "allowed_override_codes": allowed_override_codes,
            "linked_client_id": attribution.client_id if attribution else None,
            "admin_url": _existing_order_admin_url(order.pk),
        })
    return JsonResponse({
        "success": True,
        "client_id": client.pk,
        "review_id": review.pk if review else None,
        "query": q,
        "items": items,
        "limit": limit,
    })


@login_required(login_url="management_login")
@require_POST
def bot_payment_review_action_api(request, review_id):
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    from .ig_bot_models import IgPaymentConfirmationReview
    from management.services.ig_payment_review import (
        payment_review_order_url,
        reconcile_duplicate_payment_review,
        record_review_decision,
    )

    action = (request.POST.get("action") or "").strip().lower()
    verification_scope = (request.POST.get("verification_scope") or "").strip()
    review = IgPaymentConfirmationReview.objects.select_related(
        "client", "deal", "deal__payment_projection", "order"
    ).filter(pk=review_id).first()
    if not review:
        return JsonResponse({"success": False, "error": "Перевірку оплати не знайдено."}, status=404)
    if review.client.hidden_at:
        return JsonResponse({"success": False, "error": "Прихований клієнт виключений з операцій."}, status=409)
    canonical_review = reconcile_duplicate_payment_review(review)
    if (
        review.status == IgPaymentConfirmationReview.Status.SUPERSEDED
        and review.order_id
        and action in {"link_order", "confirm", "manager_verify", "clarify_amount"}
    ):
        order = review.order
        return JsonResponse({
            "success": True,
            "id": review.id,
            "status": review.status,
            "status_label": review.get_status_display(),
            "canonical_review_id": canonical_review.pk if canonical_review else review.superseded_by_id,
            "idempotent_replay": True,
            "next_action": "order_linked",
            "order_id": order.pk,
            "order_number": order.order_number,
            "order_url": _existing_order_admin_url(order.pk),
            "order_resolution": {
                "required": False,
                "link_existing": {"action": "", "action_url": ""},
                "create_new": {"url": "", "editable": False},
            },
        })
    if action == "link_order":
        from management.services.ig_order_links import link_existing_order_to_review

        try:
            order = link_existing_order_to_review(
                review,
                order_identifier=request.POST.get("order_identifier"),
                actor=request.user,
                override_code=request.POST.get("override_code", ""),
                override_reason=request.POST.get("override_reason", ""),
            )
        except ValueError as exc:
            return JsonResponse({"success": False, "error": str(exc)}, status=409)
        return JsonResponse({
            "success": True,
            "id": review.id,
            "status": review.status,
            "next_action": "order_linked",
            "order_id": order.pk,
            "order_number": order.order_number,
            "order_url": _existing_order_admin_url(order.pk),
        })
    clarify_amount = action == "clarify_amount"
    if action in {"confirm", "manager_verify", "clarify_amount"}:
        decision_name = "manager_verified"
        reason_code = ""
        reason_text = ""
    elif action in {"cancel", "manager_reject"}:
        decision_name = "manager_rejected"
        reason_code = (request.POST.get("reason_code") or "").strip()
        reason_text = (
            request.POST.get("reason_text") or request.POST.get("reason") or ""
        ).strip()
        if not reason_code:
            return JsonResponse({
                "success": False,
                "error": "Причина відхилення обов'язкова.",
            }, status=400)
    else:
        return JsonResponse({"success": False, "error": "Невідома дія."}, status=400)
    try:
        review = record_review_decision(
            review,
            actor=request.user,
            decision=decision_name,
            verification_scope=verification_scope,
            confirmed_amount=request.POST.get("confirmed_amount"),
            reason_code=reason_code,
            reason_text=reason_text,
            allow_amount_clarification=clarify_amount,
        )
    except ValueError as exc:
        error = str(exc)
        conflict = bool(
            review.client.hidden_at
            or "журналу рішення" in error
            or "вже містить точну суму" in error
            or "замовлення вже прив’язано" in error
        )
        return JsonResponse({"success": False, "error": error}, status=409 if conflict else 400)
    decision = _latest_payment_review_decision(review)
    decision_payload = _payment_review_decision_payload(decision)
    payment_payload = _payment_review_truth_payload(review, decision)
    if decision and decision.decision != decision_name:
        return JsonResponse({
            "success": False,
            "error": "Перевірку вже завершено іншим рішенням.",
            "status": review.status,
            "current_decision": decision.decision,
            "decision": decision_payload,
            "payment": payment_payload,
        }, status=409)
    notification = IgBotNotification.objects.filter(dedupe_key=review.dedupe_key).first()
    if notification:
        if notification.status == IgBotNotification.Status.SENT:
            notification.status = IgBotNotification.Status.RESOLVED
            notification.failure_kind = "payment_review_" + review.status
        notification.payload = {
            **(notification.payload if isinstance(notification.payload, dict) else {}),
            "review_status": review.status,
            "actor_id": request.user.pk,
            "manager_payment_truth": payment_payload["manager_truth"],
            "verification_source": payment_payload["verification_source"],
            "decision_reason_code": decision_payload.get("reason_code", ""),
            "decision_reason_text": decision_payload.get("reason_text", ""),
        }
        notification.save(update_fields=["status", "failure_kind", "payload", "updated_at"])
    bot.log(
        "warning" if review.status == IgPaymentConfirmationReview.Status.CANCELLED else "info",
        "payment_review_operator_action",
        f"review={review.id}; status={review.status}; actor={request.user.pk}",
    )
    needs_order_resolution = bool(
        review.status == IgPaymentConfirmationReview.Status.CONFIRMED
        and not review.order_id
        and payment_payload["authoritative_for_fulfillment"]
    )
    create_order_url = (
        _payment_review_order_link(review, payment_review_order_url)
        if needs_order_resolution
        else ""
    )
    return JsonResponse({
        "success": True,
        "id": review.id,
        "status": review.status,
        "status_label": review.get_status_display(),
        "payment": payment_payload,
        "decision": decision_payload,
        "idempotent_replay": not bool(getattr(review, "_transitioned", False)),
        "next_action": (
            "resolve_order"
            if needs_order_resolution
            else "reconcile_payment"
            if payment_payload["needs_reconciliation"]
            else "review_conversation"
        ),
        "order_url": _existing_order_admin_url(review.order_id) if review.order_id else "",
        "order_resolution": {
            "required": needs_order_resolution,
            "link_existing": {
                "action": "link_order",
                "action_url": (
                    reverse(
                        "management_bot_payment_review_action_api",
                        args=[review.pk],
                    )
                    if needs_order_resolution
                    else ""
                ),
                "requires_exact_order_identifier": True,
            },
            "create_new": {
                "url": create_order_url,
                "editable": True,
            },
        },
    })


@login_required(login_url="management_login")
@require_POST
def bot_settings_save_api(request):
    blocked = _require_bot_json(request)
    if blocked:
        return blocked
    s = InstagramBotSettings.load()

    reviewer_mode = _is_reviewer_only(request.user)
    if not reviewer_mode:
        direct_source = (request.POST.get("direct_source") or "").strip()
        if direct_source in InstagramBotSettings.CredSource.values:
            s.direct_source = direct_source
        gemini_source = (request.POST.get("gemini_source") or "").strip()
        if gemini_source in InstagramBotSettings.CredSource.values:
            s.gemini_source = gemini_source

        if "custom_direct_token" in request.POST:
            value = (request.POST.get("custom_direct_token") or "").strip()
            if value:
                s.custom_direct_token = value
        if _truthy(request.POST.get("clear_custom_direct_token")):
            s.custom_direct_token = ""
        if "custom_gemini_key" in request.POST:
            value = (request.POST.get("custom_gemini_key") or "").strip()
            if value:
                s.custom_gemini_key = value
        if _truthy(request.POST.get("clear_custom_gemini_key")):
            s.custom_gemini_key = ""

        trigger = (request.POST.get("trigger_text") or "").strip()
        if trigger:
            s.trigger_text = trigger[:255]
        reply = (request.POST.get("reply_text") or "").strip()
        if reply:
            s.reply_text = reply[:1000]

    # AI-режим / модель / правило / білий список.
    s.ai_enabled = (request.POST.get("ai_enabled") or "").strip() in {"1", "true", "on", "yes"}
    s.receive_via_poll = (request.POST.get("receive_via_poll") or "").strip() in {"1", "true", "on", "yes"}
    if not reviewer_mode:
        s.meta_feedback_enabled = _truthy(request.POST.get("meta_feedback_enabled"))
        if "meta_feedback_test_event_code" in request.POST:
            s.meta_feedback_test_event_code = (request.POST.get("meta_feedback_test_event_code") or "")[:120]
    model = (request.POST.get("gemini_model") or "").strip()
    if model:
        from management.services.gemini_keys import is_allowed_chat_model

        if not is_allowed_chat_model(model):
            return JsonResponse({"success": False, "error": "Недозволена модель Gemini."}, status=400)
        s.gemini_model = model[:80]
    if "system_prompt" in request.POST:
        if not reviewer_mode:
            s.system_prompt = (request.POST.get("system_prompt") or "").strip()
    if "knowledge_base" in request.POST:
        if not reviewer_mode:
            s.knowledge_base = (request.POST.get("knowledge_base") or "").strip()
    if "allowed_senders" in request.POST:
        if not reviewer_mode:
            s.allowed_senders = (request.POST.get("allowed_senders") or "").strip()

    if not reviewer_mode:
        try:
            interval = int(request.POST.get("poll_interval_seconds") or s.poll_interval_seconds)
            s.poll_interval_seconds = max(2, min(60, interval))
        except (TypeError, ValueError):
            pass

    s.save()
    # Скинути кеш токена/кулдаун, щоб новий токен підхопився одразу.
    try:
        from django.core.cache import cache
        cache.delete("ig_bot_page_token")
        cache.delete("ig_bot_pt_cooldown")
        cache.delete("ig_bot_ll_user_token")
        cache.delete("ig_bot_pt_errsig")
    except Exception:
        pass
    bot.log(
        "info",
        "settings_saved",
        f"ai={s.ai_enabled}, model={s.gemini_model}, direct={s.direct_source}, gemini={s.gemini_source}",
    )
    return JsonResponse({"success": True, "status": bot.status_snapshot()})


# ---------------------------------------------------------------------------
# Вкладка «Клиенти» — CRM IG-клієнтів (Task 13)
# ---------------------------------------------------------------------------
def _interaction_tone(interaction_type: str) -> str:
    from .ig_bot_models import IgConversationAnalysisSnapshot

    types = IgConversationAnalysisSnapshot.InteractionType
    if interaction_type == types.SUPPORT_COMPLAINT:
        return "support"
    if interaction_type in {types.WHOLESALE_B2B, types.COLLABORATION}:
        return "business"
    if interaction_type in {types.HIGH_INTENT, types.PAYMENT_PENDING}:
        return "intent"
    if interaction_type == types.PAID_ORDER_WAITING:
        return "success"
    if interaction_type in {types.EXPLICIT_NO_BUY, types.OPT_OUT, types.SPAM_ABUSE}:
        return "negative"
    return "neutral"


def _group_signal_rows(rows) -> list[dict]:
    """Collapse repeated event rows into an auditable per-type summary."""
    from .ig_bot_models import IgConversationSignal

    labels = dict(IgConversationSignal.Type.choices)
    grouped = {}
    for raw in rows or ():
        signal_type = str(raw.get("type") or "unknown")
        time_value = str(raw.get("time") or "")
        current = grouped.get(signal_type)
        if current is None:
            current = {
                "type": signal_type,
                "type_label": str(labels.get(signal_type, "Інший сигнал")),
                "count": 0,
                "latest_time": "",
                "latest_value": "",
                "latest_confidence": "",
            }
            grouped[signal_type] = current
        current["count"] += 1
        if time_value >= current["latest_time"]:
            current["latest_time"] = time_value
            current["latest_value"] = str(raw.get("value") or "")
            current["latest_confidence"] = str(raw.get("confidence") or "")
    return sorted(
        grouped.values(),
        key=lambda item: (-int(item["count"]), item["type"]),
    )


def _with_latest_interaction(queryset):
    from .ig_bot_models import (
        IgConversationAnalysisSnapshot,
        IgPaymentConfirmationReview,
        IgPostSaleCase,
    )
    from .models import InstagramBotMessage

    latest = IgConversationAnalysisSnapshot.objects.filter(
        client_id=OuterRef("pk")
    ).order_by("-id")
    latest_customer = latest.exclude(
        interaction_type=IgConversationAnalysisSnapshot.InteractionType.MANAGER_OBSERVATION
    )
    latest_message = InstagramBotMessage.objects.filter(
        client_id=OuterRef("pk")
    ).order_by("-id")
    action_review = IgPaymentConfirmationReview.objects.filter(
        client_id=OuterRef("pk")
    ).filter(
        Q(status=IgPaymentConfirmationReview.Status.PENDING)
        | Q(
            status=IgPaymentConfirmationReview.Status.CONFIRMED,
            order_id__isnull=True,
        )
    ).exclude(status=IgPaymentConfirmationReview.Status.SUPERSEDED)
    action_post_sale = IgPostSaleCase.objects.filter(
        client_id=OuterRef("pk"),
        status__in=[IgPostSaleCase.Status.NEEDS_DETAILS, IgPostSaleCase.Status.OPEN],
    )
    return queryset.annotate(
        latest_interaction_type=Coalesce(
            Subquery(latest_customer.values("interaction_type")[:1]),
            Subquery(latest.values("interaction_type")[:1]),
            Value(""),
        ),
        latest_conversation_message_id=Coalesce(
            Subquery(latest_message.values("id")[:1]),
            Value(0),
        ),
        has_manager_action=Exists(action_review) | Exists(action_post_sale),
    )


def _client_potential_payload(c, latest_analysis, *, latest_message_id=None) -> dict:
    """Evidence-bound purchase potential, independent from payment/order truth."""
    from .ig_bot_models import IgClient, IgConversationAnalysisSnapshot

    current_episode = getattr(c, "current_commercial_episode", None)
    current_episode_id = getattr(c, "current_commercial_episode_id", None)
    latest_message_id = int(
        latest_message_id
        if latest_message_id is not None
        else getattr(c, "latest_conversation_message_id", 0)
        or 0
    )
    label_by_band = {
        "cold": "Холодний",
        "exploring": "Вивчає варіанти",
        "qualified": "Кваліфікований інтерес",
        "high_intent": "Високий намір",
        "checkout": "Готовий оформлювати",
        "lost": "Втрачений",
        "opted_out": "Відмовився від повідомлень",
        "spam": "Спам",
        "unknown": "Ще не оцінено",
    }
    active_opt_out = bool(
        c.opted_out_at
        and (not c.opted_in_at or c.opted_in_at < c.opted_out_at)
    )
    policy_band = ""
    policy_source = ""
    if c.stage == IgClient.Stage.SPAM or (
        latest_analysis
        and latest_analysis.interaction_type
        == IgConversationAnalysisSnapshot.InteractionType.SPAM_ABUSE
    ):
        policy_band, policy_source = "spam", "communication_policy"
    elif active_opt_out:
        policy_band, policy_source = "opted_out", "opt_out_policy"
    elif c.lost_reason:
        policy_band, policy_source = "lost", "client_stage"
    elif c.stage == IgClient.Stage.COLD:
        policy_band, policy_source = "cold", "client_stage"

    evidence = latest_analysis.evidence if latest_analysis else []
    if not isinstance(evidence, list):
        evidence = []
    evidence = evidence[:20]
    evidence_message_ids = []
    for item in evidence:
        if not isinstance(item, dict):
            continue
        try:
            message_id = int(item.get("message_id") or 0)
        except (TypeError, ValueError):
            continue
        if message_id and message_id not in evidence_message_ids:
            evidence_message_ids.append(message_id)

    if policy_band:
        return {
            "state": "policy",
            "band": policy_band,
            "label": label_by_band[policy_band],
            "probability": None,
            "confidence": None,
            "source": policy_source,
            "scope": "client_policy",
            "episode_id": current_episode_id,
            "current_episode_id": current_episode_id,
            "watermark_message_id": 0,
            "latest_message_id": latest_message_id,
            "analyzed_at": "",
            "fresh": True,
            "model": "",
            "prompt_version": "",
            "rules_version": "",
            "interaction_type": (
                latest_analysis.interaction_type if latest_analysis else ""
            ),
            "interaction_label": (
                latest_analysis.get_interaction_type_display()
                if latest_analysis
                else "Не визначено"
            ),
            "evidence": evidence,
            "evidence_message_ids": evidence_message_ids,
            "uncertainties": [],
        }

    if not latest_analysis:
        return {
            "state": "unknown",
            "band": "unknown",
            "label": label_by_band["unknown"],
            "probability": None,
            "confidence": None,
            "source": "none",
            "scope": "unknown",
            "episode_id": None,
            "current_episode_id": current_episode_id,
            "watermark_message_id": 0,
            "latest_message_id": latest_message_id,
            "analyzed_at": "",
            "fresh": False,
            "model": "",
            "prompt_version": "",
            "rules_version": "",
            "interaction_type": "unknown",
            "interaction_label": "Не визначено",
            "evidence": [],
            "evidence_message_ids": [],
            "uncertainties": ["analysis_missing"],
        }

    watermark = int(latest_analysis.last_analyzed_message_id or 0)
    episode_id = latest_analysis.commercial_episode_id
    boundary = int(getattr(current_episode, "opened_watermark_message_id", 0) or 0)
    matches_episode = bool(
        not current_episode_id
        or (episode_id and episode_id == current_episode_id)
        or (not episode_id and boundary == 0)
    )
    fresh = bool(
        watermark >= latest_message_id
        and matches_episode
        and (not boundary or watermark >= boundary)
    )
    state = "current" if fresh else "stale"
    scope = (
        "current_episode"
        if current_episode_id and episode_id == current_episode_id
        else "conversation"
        if not current_episode_id
        else "historical_episode"
    )
    band = latest_analysis.score_band
    if band == IgConversationAnalysisSnapshot.Band.PAID:
        band = IgConversationAnalysisSnapshot.Band.CHECKOUT
    if band not in label_by_band:
        band = "unknown"
    return {
        "state": state,
        "band": band,
        "label": label_by_band[band],
        "probability": str(latest_analysis.purchase_probability),
        "confidence": str(latest_analysis.confidence),
        "source": "conversation_analysis",
        "scope": scope,
        "episode_id": episode_id,
        "current_episode_id": current_episode_id,
        "watermark_message_id": watermark,
        "latest_message_id": latest_message_id,
        "analyzed_at": latest_analysis.analyzed_at.isoformat(),
        "fresh": fresh,
        "model": latest_analysis.analysis_model,
        "prompt_version": latest_analysis.analysis_prompt_version,
        "rules_version": latest_analysis.rules_version,
        "interaction_type": latest_analysis.interaction_type,
        "interaction_label": latest_analysis.get_interaction_type_display(),
        "evidence": evidence,
        "evidence_message_ids": evidence_message_ids,
        "uncertainties": (
            latest_analysis.uncertainties
            if isinstance(latest_analysis.uncertainties, list)
            else []
        )[:20],
    }


def _client_card(c) -> dict:
    from .ig_bot_models import IgConversationAnalysisSnapshot

    product = getattr(c, "current_product", None)
    next_followup = getattr(c, "next_followup_at", None)
    latest_analysis = getattr(c, "_latest_customer_analysis", None)
    if isinstance(latest_analysis, (list, tuple)):
        latest_analysis = latest_analysis[0] if latest_analysis else None
    if latest_analysis is None:
        try:
            latest_analysis = c.analysis_snapshots.exclude(
                interaction_type=IgConversationAnalysisSnapshot.InteractionType.MANAGER_OBSERVATION
            ).order_by("-id").first()
        except Exception:
            latest_analysis = None
    if latest_analysis is None:
        latest_analysis = getattr(c, "_latest_analysis", None)
        if isinstance(latest_analysis, (list, tuple)):
            latest_analysis = latest_analysis[0] if latest_analysis else None
    if latest_analysis is None:
        try:
            latest_analysis = c.analysis_snapshots.order_by("-id").first()
        except Exception:
            latest_analysis = None
    payment_status = ""
    try:
        verified_deal = latest_verified_payment_deal(c)
        truth_projection = latest_payment_projection(c)
        truth_deal = (
            truth_projection.deal
            if truth_projection
            else (latest_legacy_payment_truth_deal(c) or verified_deal)
        )
        payment_status = (
            truth_projection.truth
            if truth_projection
            else (
                truth_deal.payment_truth
                if truth_deal and truth_deal.payment_truth != IgDeal.PaymentTruth.UNVERIFIED
                else (truth_deal.payment_status if truth_deal else "unpaid")
            )
        )
    except Exception:
        verified_deal = None
        truth_projection = None
        truth_deal = None
    has_verified_payment = bool(verified_deal)
    payment_truth = (
        truth_projection.truth
        if truth_projection
        else (
            truth_deal.payment_truth
            if truth_deal and truth_deal.payment_truth != IgDeal.PaymentTruth.UNVERIFIED
            else (IgDeal.PaymentTruth.CONFIRMED if has_verified_payment else IgDeal.PaymentTruth.UNVERIFIED)
        )
    )
    hard_stages = {IgClient.Stage.PAID, IgClient.Stage.ORDER_CREATED, IgClient.Stage.DONE}
    displayed_stage = c.stage
    displayed_stage_label = c.get_stage_display()
    if c.stage in hard_stages and not has_verified_payment:
        if payment_truth in {IgDeal.PaymentTruth.REFUNDED, IgDeal.PaymentTruth.REVERSED}:
            displayed_stage = "payment_reversed"
            displayed_stage_label = "Оплату повернено / скасовано"
        else:
            displayed_stage = "unverified"
            displayed_stage_label = "Потребує звірки оплати"
    active_opt_out = bool(
        c.opted_out_at
        and (not c.opted_in_at or c.opted_in_at < c.opted_out_at)
    )
    interaction_type = latest_analysis.interaction_type if latest_analysis else ""
    potential = _client_potential_payload(c, latest_analysis)
    return {
        "id": c.id,
        "igsid": c.igsid,
        "username": c.username,
        "name": c.display_name or c.username or c.igsid,
        "avatar": c.avatar_local or c.profile_pic_url,
        "stage": displayed_stage,
        "stage_raw": c.stage,
        "stage_label": displayed_stage_label,
        "last_message_at": c.last_message_at.isoformat() if c.last_message_at else "",
        "purchases": c.purchases_count,
        "total_spent": str(c.total_spent),
        "bot_paused": c.bot_paused,
        "opted_out": active_opt_out,
        "opted_out_at": c.opted_out_at.isoformat() if c.opted_out_at else "",
        "manager_takeover": c.manager_takeover,
        "spam_strikes": c.spam_strikes,
        "ad_title": c.ad_title,
        "ad_id": c.ad_id,
        "ad_ref": c.ad_ref,
        "language": c.language,
        "intent": c.intent,
        "buying_readiness": c.buying_readiness,
        "analysis_band": latest_analysis.score_band if latest_analysis else "",
        "analysis_band_label": latest_analysis.get_score_band_display() if latest_analysis else "",
        "interaction_type": interaction_type,
        "interaction_type_label": latest_analysis.get_interaction_type_display() if latest_analysis else "Не визначено",
        "interaction_tone": _interaction_tone(interaction_type),
        "analysis_probability": str(latest_analysis.purchase_probability) if latest_analysis else "",
        "analysis_confidence": str(latest_analysis.confidence) if latest_analysis else "",
        "analysis_evidence": latest_analysis.evidence if latest_analysis else [],
        "analysis_uncertainties": latest_analysis.uncertainties if latest_analysis else [],
        "analysis_at": latest_analysis.analyzed_at.isoformat() if latest_analysis else "",
        "potential": potential,
        "manager_action_required": bool(getattr(c, "has_manager_action", False)),
        "intent_label": c.get_intent_display(),
        "primary_objection": c.primary_objection,
        "primary_objection_label": c.get_primary_objection_display(),
        "lost_reason": c.lost_reason,
        "hidden": bool(c.hidden_at),
        "hidden_reason": c.hidden_reason,
        "current_product_id": c.current_product_id,
        "current_product_title": getattr(product, "title", "") if product else "",
        "current_size": c.current_size,
        "current_color": c.current_color,
        "current_qty": c.current_qty,
        "product_confidence": str(c.current_product_confidence),
        "next_followup_at": next_followup.isoformat() if next_followup else "",
        "followup_level": c.followup_level,
        "discount_offered_percent": c.discount_offered_percent,
        "payment_status": payment_status,
        "payment_truth": payment_truth,
        "delivery_status": c.delivery_status,
        "delivery_status_label": c.get_delivery_status_display() if c.delivery_status else "",
        "delivery_error": c.delivery_error,
        "delivery_failed_at": c.delivery_failed_at.isoformat() if c.delivery_failed_at else "",
    }


@login_required(login_url="management_login")
@require_GET
def bot_clients_api(request):
    blocked = _require_bot_json(request)
    if blocked:
        return blocked
    from django.db.models import Q

    from .models import IgClient, IgDeal

    view = (request.GET.get("view") or "active").strip().lower()
    from django.db.models import Prefetch
    from .ig_bot_models import IgConversationAnalysisSnapshot

    qs = _with_latest_interaction(annotate_verified_payment(
        IgClient.objects.select_related("current_product", "current_commercial_episode").prefetch_related(
        Prefetch(
            "analysis_snapshots",
            queryset=IgConversationAnalysisSnapshot.objects.select_related("commercial_episode").exclude(
                interaction_type=IgConversationAnalysisSnapshot.InteractionType.MANAGER_OBSERVATION
            ).order_by("-id")[:1],
            to_attr="_latest_customer_analysis",
        ),
        Prefetch(
            "analysis_snapshots",
            queryset=IgConversationAnalysisSnapshot.objects.select_related("commercial_episode").order_by("-id")[:1],
            to_attr="_latest_analysis",
        ),
        Prefetch(
            "deals",
            queryset=IgDeal.objects.filter(verified_payment_q()).order_by("-paid_at", "-id"),
            to_attr="_verified_payment_deals",
        ),
        Prefetch(
            "payment_projections",
            queryset=IgPaymentProjection.objects.select_related("deal").order_by("-updated_at", "-id"),
            to_attr="_payment_projections",
        ),
        ).all()
    ))
    unfiltered_qs = qs
    if view in {"hidden"}:
        qs = qs.filter(hidden_at__isnull=False)
    else:
        qs = qs.filter(hidden_at__isnull=True)
    if view in {"spam", "cold", "spam-cold", "spam_cold"}:
        qs = qs.filter(Q(stage__in=[IgClient.Stage.SPAM, IgClient.Stage.COLD]) | Q(spam_strikes__gt=0))
    elif view == "paid":
        qs = qs.filter(has_verified_payment=True)
    elif view == "due":
        qs = qs.filter(followup_tasks__status="pending", followup_tasks__due_at__lte=timezone.now()).distinct()
    elif view == "ads":
        qs = qs.filter(Q(ad_id__gt="") | Q(ad_ref__gt="") | Q(ad_title__gt=""))
    elif view in {"delivery-blocked", "delivery_blocked"}:
        qs = qs.filter(delivery_status__gt="")
    elif view in {"complaints", "support"}:
        qs = qs.filter(
            latest_interaction_type=IgConversationAnalysisSnapshot.InteractionType.SUPPORT_COMPLAINT
        )
    elif view == "wholesale":
        qs = qs.filter(
            latest_interaction_type=IgConversationAnalysisSnapshot.InteractionType.WHOLESALE_B2B
        )
    elif view == "collaboration":
        qs = qs.filter(
            latest_interaction_type=IgConversationAnalysisSnapshot.InteractionType.COLLABORATION
        )
    elif view in {"reactions", "community"}:
        qs = qs.filter(latest_interaction_type__in=[
            IgConversationAnalysisSnapshot.InteractionType.REACTION_ONLY,
            IgConversationAnalysisSnapshot.InteractionType.COMMUNITY_CASUAL,
        ])
    elif view == "active":
        qs = qs.exclude(stage__in=[IgClient.Stage.SPAM, IgClient.Stage.COLD])
        qs = qs.filter(has_verified_payment=False)
    qs = qs.order_by("-last_message_at", "-id")
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(username__icontains=q)
            | Q(display_name__icontains=q)
            | Q(igsid__icontains=q)
            | Q(phone__icontains=q)
        )
    total = qs.count()
    clients = list(qs[:200])
    try:
        requested_client_id = int(request.GET.get("client_id") or 0)
    except (TypeError, ValueError):
        requested_client_id = 0
    if requested_client_id and all(c.pk != requested_client_id for c in clients):
        requested_client = unfiltered_qs.filter(pk=requested_client_id).first()
        if requested_client:
            clients.insert(0, requested_client)
    rows = [_client_card(c) for c in clients]
    return JsonResponse({"success": True, "clients": rows, "total": total})


@login_required(login_url="management_login")
@require_GET
def bot_client_detail_api(request, client_id):
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    from .models import IgClient
    from .ig_bot_models import (
        IgConversationAnalysisSnapshot,
        IgPaymentConfirmationReview,
        IgPaymentReviewDecision,
    )
    from management.services.ig_commercial_episodes import client_episode_payload

    c = IgClient.objects.select_related(
        "current_product", "current_commercial_episode"
    ).filter(id=client_id).first()
    if not c:
        return JsonResponse({"success": False, "error": "Клієнта не знайдено."}, status=404)

    try:
        after_id = int(request.GET.get("after_id") or 0)
    except (TypeError, ValueError):
        after_id = 0

    if after_id:
        msg_rows = list(c.messages.filter(id__gt=after_id).order_by("id")[:100])
    else:
        # Останні 300 (а не найстаріші) у хронологічному порядку — для live chat.
        msg_rows = list(c.messages.order_by("-id")[:300])
        msg_rows.reverse()
    media_evidence = (c.sales_context or {}).get("_media_evidence", []) if isinstance(c.sales_context, dict) else []
    media_by_message = {}
    for evidence in media_evidence if isinstance(media_evidence, list) else []:
        if not isinstance(evidence, dict):
            continue
        try:
            source_id = int(evidence.get("source_message_id"))
        except (TypeError, ValueError):
            continue
        media_by_message.setdefault(source_id, []).append({
            "url": _safe_media_url(evidence.get("url")),
            "role": str(evidence.get("role") or "other")[:32],
            "intent": str(evidence.get("intent") or "unknown")[:40],
        })
    messages = [
        {
            "id": m.id,
            "role": m.role,
            "text": m.text,
            "attachments": m.attachments or "",
            "media": media_by_message.get(m.id, []),
            "time": m.created_at.isoformat() if m.created_at else "",
        }
        for m in msg_rows
    ]
    last_message_id = msg_rows[-1].id if msg_rows else after_id

    # Інкрементальний режим (live chat): лише нові повідомлення + прапори стану,
    # без важких events/deals/funnel — щоб не вантажити сервер на кожному поллі.
    if after_id:
        return JsonResponse({
            "success": True,
            "messages": messages,
            "last_message_id": last_message_id,
            "bot_paused": c.bot_paused,
            "manager_takeover": c.manager_takeover,
            "stage": c.stage,
            "stage_label": c.get_stage_display(),
        })

    events = [
        {
            "from": e.from_stage,
            "to": e.to_stage,
            "reason": e.reason,
            "time": e.created_at.isoformat() if e.created_at else "",
        }
        for e in c.stage_events.all()[:50]
    ]
    signal_rows = [
        {
            "type": s.signal_type,
            "confidence": str(s.confidence),
            "value": s.value,
            "time": s.created_at.isoformat() if s.created_at else "",
        }
        for s in c.conversation_signals.all().order_by("-created_at", "-id")[:120]
    ]
    signals = _group_signal_rows(signal_rows)
    followups = [
        {
            "id": f.id,
            "kind": f.kind,
            "status": f.status,
            "reason": f.reason,
            "discount_percent": f.discount_percent,
            "due_at": f.due_at.isoformat() if f.due_at else "",
            "meta_window_deadline": f.meta_window_deadline.isoformat() if f.meta_window_deadline else "",
            "skip_reason": f.skip_reason,
        }
        for f in c.followup_tasks.all()[:50]
    ]
    deal_rows = list(c.deals.select_related("payment_projection", "order").all()[:20])
    deals = [
        {
            "id": d.id,
            "status": d.status,
            "amount": str(d.amount),
            "pay_type": d.pay_type,
            "payment_status": d.payment_status,
            "invoice_url": d.invoice_url,
            "order_id": d.order_id,
        }
        for d in deal_rows
    ]
    review_base = _payment_review_workspace_queryset().filter(client=c)
    from management.services.ig_payment_review import reconcile_duplicate_payment_review

    for duplicate_review in review_base.filter(
        status=IgPaymentConfirmationReview.Status.CONFIRMED,
        order_id__isnull=True,
    ):
        reconcile_duplicate_payment_review(duplicate_review)
    review_base = _payment_review_workspace_queryset().filter(client=c)
    review_counts = review_base.aggregate(
        total=Count("id"),
        pending=Count(
            "id",
            filter=Q(status=IgPaymentConfirmationReview.Status.PENDING),
        ),
        confirmed=Count(
            "id",
            filter=Q(status=IgPaymentConfirmationReview.Status.CONFIRMED),
        ),
        rejected=Count(
            "id",
            filter=Q(status=IgPaymentConfirmationReview.Status.CANCELLED),
        ),
        order_resolution=Count(
            "id",
            filter=Q(
                status=IgPaymentConfirmationReview.Status.CONFIRMED,
                order_id__isnull=True,
            ),
        ),
    )
    actionable_review_row = review_base.filter(
        Q(status=IgPaymentConfirmationReview.Status.PENDING)
        | Q(
            status=IgPaymentConfirmationReview.Status.CONFIRMED,
            order_id__isnull=True,
        )
    ).order_by("-created_at", "-id").first()
    review_rows = list(review_base.order_by("-created_at", "-id")[:20])
    review_payloads = [_payment_review_workspace_payload(row) for row in review_rows]
    active_review = None
    if actionable_review_row is not None:
        active_review = next(
            (
                item for item in review_payloads
                if item["review_id"] == actionable_review_row.pk
            ),
            None,
        )
        if active_review is None:
            active_review = _payment_review_workspace_payload(actionable_review_row)
    attribution_base = _order_attribution_workspace_queryset().filter(
        client=c,
    ).exclude(
        order_id__in=Subquery(
            review_base.exclude(order_id__isnull=True).values("order_id")
        )
    )
    attribution_total = attribution_base.count()
    attribution_rows = list(attribution_base.order_by("-created_at", "-id")[:20])
    order_cards = _canonical_order_workspace_cards(
        review_rows,
        attribution_rows,
        limit=20,
    )
    card = _client_card(c)
    card.update({
        "memory": c.memory_summary,
        "phone": c.phone,
        "ad_source": c.ad_source,
        "ad_id": c.ad_id,
        "first_contact_at": c.first_contact_at.isoformat() if c.first_contact_at else "",
        "sales_context": c.sales_context,
        "hidden": bool(c.hidden_at),
        "hidden_reason": c.hidden_reason,
    })
    automation_owner = "manager" if c.manager_takeover or c.bot_paused else "bot"
    latest_projection = c.payment_projections.select_related("deal").order_by(
        "-updated_at", "-id",
    ).first()
    latest_manager_decision = IgPaymentReviewDecision.objects.filter(
        client=c,
    ).select_related("actor").order_by("-id").first()
    provider_truth = (
        latest_projection.truth
        if latest_projection
        else card.get("payment_truth", IgDeal.PaymentTruth.UNVERIFIED)
    )
    manager_truth = latest_manager_decision.decision if latest_manager_decision else ""
    payment_workspace = {
        "provider_truth": provider_truth,
        "provider_source": "provider_projection" if latest_projection else "client_payment_summary",
        "provider_deal_id": latest_projection.deal_id if latest_projection else None,
        "manager_truth": manager_truth,
        "verification_source": (
            latest_manager_decision.verification_source
            if latest_manager_decision
            else ""
        ),
        "verification_scope": (
            latest_manager_decision.verification_scope
            if latest_manager_decision
            else ""
        ),
        "manager_decision": _payment_review_decision_payload(latest_manager_decision),
        "authoritative_for_fulfillment": bool(
            manager_truth == "manager_verified"
            or provider_truth in {
                IgDeal.PaymentTruth.CONFIRMED,
                IgDeal.PaymentTruth.PARTIALLY_REFUNDED,
            }
        ),
    }
    current_deal = next(
        (deal for deal in deal_rows if deal.status != IgDeal.Status.CANCELLED),
        deal_rows[0] if deal_rows else None,
    )
    fulfillment_workspace = {
        "deal_id": current_deal.pk if current_deal else None,
        "delivery_status": current_deal.delivery_status if current_deal else "",
        "delivery_status_label": (
            current_deal.get_delivery_status_display()
            if current_deal and current_deal.delivery_status
            else ""
        ),
        "delivery_error": current_deal.delivery_error if current_deal else "",
        "has_validated_refs": bool(
            current_deal
            and current_deal.np_settlement_ref
            and current_deal.np_city_ref
            and current_deal.np_warehouse_ref
        ),
        "current_episode_source": "latest_non_cancelled_deal" if current_deal else "none",
    }
    episodes = client_episode_payload(c)
    physical_order_count = episodes["physical_order_count"]
    potential = _client_potential_payload(
        c,
        c.analysis_snapshots.select_related("commercial_episode")
        .exclude(
            interaction_type=IgConversationAnalysisSnapshot.InteractionType.MANAGER_OBSERVATION
        )
        .order_by("-id")
        .first(),
        latest_message_id=last_message_id,
    )
    return JsonResponse({
        "success": True,
        "client": card,
        "messages": messages,
        "last_message_id": last_message_id,
        "events": events,
        "signals": signals,
        "signal_event_count": len(signal_rows),
        "followups": followups,
        "deals": deals,
        "funnel": c.funnel_progress(),
        "automation": {
            "owner": automation_owner,
            "bot_paused": c.bot_paused,
            "paused_reason": c.paused_reason,
            "paused_at": c.paused_at.isoformat() if c.paused_at else "",
            "manager_takeover": c.manager_takeover,
            "opted_out": card.get("opted_out", False),
            "opted_out_at": card.get("opted_out_at", ""),
            "reply_permission_epoch": c.reply_permission_epoch,
        },
        "interaction": {
            "stage": card["stage"],
            "stage_raw": card["stage_raw"],
            "stage_label": card["stage_label"],
            "intent": card["intent"],
            "intent_label": card["intent_label"],
            "buying_readiness": card["buying_readiness"],
            "interaction_type": card["interaction_type"],
            "interaction_type_label": card["interaction_type_label"],
            "analysis_band": card["analysis_band"],
            "analysis_band_label": card["analysis_band_label"],
            "analysis_confidence": card["analysis_confidence"],
            "analysis_evidence": (
                card["analysis_evidence"][:20]
                if isinstance(card["analysis_evidence"], list)
                else []
            ),
            "analysis_uncertainties": (
                card["analysis_uncertainties"][:20]
                if isinstance(card["analysis_uncertainties"], list)
                else []
            ),
            "last_manager_message_at": (
                c.last_manager_message_at.isoformat()
                if c.last_manager_message_at
                else ""
            ),
        },
        "potential": potential,
        "commercial_episodes": episodes,
        "payment": payment_workspace,
        "fulfillment": fulfillment_workspace,
        "review": {
            "pending_count": review_counts["pending"],
            "confirmed_count": review_counts["confirmed"],
            "rejected_count": review_counts["rejected"],
            "order_resolution_count": review_counts["order_resolution"],
            "total_count": review_counts["total"],
            "active": active_review,
            "history": review_payloads,
            "queue_url": reverse("management_bot_orders_workspace_api"),
        },
        "orders": {
            "count": physical_order_count,
            "physical_count": physical_order_count,
            "review_count": review_counts["total"],
            "attribution_count": attribution_total,
            "items": order_cards,
            "queue_url": _orders_workspace_url(view="all", client_id=c.pk),
        },
        "post_sale": _post_sale_workspace_payload(c),
        "patterns": {
            "source": "legacy_signal_groups",
            "event_count": len(signal_rows),
            "groups": signals,
            "bounded": True,
        },
    })


@login_required(login_url="management_login")
@require_POST
def bot_post_sale_case_api(request, client_id, case_id):
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    from .ig_bot_models import IgCommercialEpisode, IgOrderAttribution, IgPostSaleCase

    with transaction.atomic():
        case = (
            IgPostSaleCase.objects.select_for_update()
            .select_related("client", "order")
            .filter(pk=case_id, client_id=client_id)
            .first()
        )
        if not case:
            return JsonResponse({"success": False, "error": "Звернення не знайдено."}, status=404)

        order_value = str(request.POST.get("order_id") or "").strip()
        if order_value:
            try:
                order_id = int(order_value)
            except (TypeError, ValueError):
                return JsonResponse({"success": False, "error": "Некоректне замовлення."}, status=400)
            attribution = (
                IgOrderAttribution.objects.select_related("order")
                .filter(client_id=client_id, order_id=order_id)
                .first()
            )
            if not attribution:
                return JsonResponse({
                    "success": False,
                    "error": "Це замовлення не прив’язане до Instagram-клієнта.",
                }, status=400)
            case.order = attribution.order
            case.commercial_episode = (
                IgCommercialEpisode.objects.filter(order_attribution=attribution).first()
                or IgCommercialEpisode.objects.filter(intended_order_id=order_id).first()
            )

        case_type = str(request.POST.get("case_type") or case.case_type).strip()
        valid_types = {value for value, _label in IgPostSaleCase.CaseType.choices}
        if case_type not in valid_types:
            return JsonResponse({"success": False, "error": "Некоректний тип звернення."}, status=400)
        status = str(request.POST.get("status") or case.status).strip()
        valid_statuses = {value for value, _label in IgPostSaleCase.Status.choices}
        if status not in valid_statuses:
            return JsonResponse({"success": False, "error": "Некоректний статус звернення."}, status=400)
        if status != IgPostSaleCase.Status.NEEDS_DETAILS and not case.order_id:
            return JsonResponse({
                "success": False,
                "error": "Спочатку оберіть замовлення цього клієнта.",
            }, status=400)

        case.case_type = case_type
        case.status = status
        for field, limit in (
            ("source_item_title", 255), ("source_fit", 64),
            ("source_size", 32), ("requested_fit", 64),
            ("requested_size", 32), ("manager_note", 4000),
        ):
            if field in request.POST:
                setattr(case, field, str(request.POST.get(field) or "").strip()[:limit])
        terminal = {
            IgPostSaleCase.Status.COMPLETED, IgPostSaleCase.Status.REJECTED,
            IgPostSaleCase.Status.CANCELLED,
        }
        case.resolved_at = timezone.now() if status in terminal else None
        case.save()

    return JsonResponse({
        "success": True,
        "case": _post_sale_case_payload(case),
        "post_sale": _post_sale_workspace_payload(case.client),
    })


@login_required(login_url="management_login")
@require_POST
def bot_client_pause_api(request, client_id):
    """Зупинити бота для клієнта (менеджер бере діалог на себе)."""
    blocked = _require_bot_json(request)
    if blocked:
        return blocked
    from django.utils import timezone

    from .models import IgClient, InstagramBotMessage
    from .services import bot_followups
    from .services.ig_reply_boundary import pause_reply_boundary

    with pause_reply_boundary():
        with transaction.atomic():
            c = IgClient.objects.select_for_update().filter(id=client_id).first()
            if not c:
                return JsonResponse({"success": False, "error": "Клієнта не знайдено."}, status=404)
            now = timezone.now()
            c.bot_paused = True
            c.reply_permission_epoch = int(c.reply_permission_epoch or 0) + 1
            c.paused_reason = "manual"
            c.paused_at = now
            c.save(update_fields=[
                "bot_paused", "reply_permission_epoch", "paused_reason", "paused_at", "updated_at",
            ])
            bot_followups.cancel_pending(c, reason="manual_pause")
            InstagramBotMessage.objects.filter(
                client=c,
                role=InstagramBotMessage.Role.USER,
                status__in=[
                    InstagramBotMessage.Status.PENDING,
                    InstagramBotMessage.Status.PROCESSING,
                ],
            ).exclude(send_state="sending").update(
                status=InstagramBotMessage.Status.DONE,
                processed_at=now,
                processing_started_at=None,
            )
    return JsonResponse({"success": True, "bot_paused": True})


@login_required(login_url="management_login")
@require_POST
def bot_client_resume_api(request, client_id):
    """Повернути бота клієнту (зняти паузу/перехоплення)."""
    blocked = _require_bot_json(request)
    if blocked:
        return blocked
    from django.utils import timezone

    from .models import IgClient
    from .services.ig_reply_boundary import pause_reply_boundary

    with pause_reply_boundary():
        with transaction.atomic():
            c = IgClient.objects.select_for_update().filter(id=client_id).first()
            if not c:
                return JsonResponse({"success": False, "error": "Клієнта не знайдено."}, status=404)
            active_opt_out = bool(
                c.opted_out_at
                and (not c.opted_in_at or c.opted_in_at < c.opted_out_at)
            )
            if active_opt_out and request.POST.get("confirm_opt_in") not in {"1", "true"}:
                return JsonResponse({
                    "success": False,
                    "error": (
                        "Клієнт відмовився від автоматичних повідомлень. "
                        "Потрібне окреме підтвердження ручної згоди."
                    ),
                    "requires_opt_in_confirmation": True,
                }, status=409)
            c.bot_paused = False
            c.manager_takeover = False
            c.reply_permission_epoch = int(c.reply_permission_epoch or 0) + 1
            c.paused_reason = ""
            update_fields = [
                "bot_paused", "manager_takeover", "reply_permission_epoch",
                "paused_reason", "updated_at",
            ]
            if active_opt_out:
                c.opted_in_at = timezone.now()
                c.opted_in_by = request.user
                update_fields.extend(["opted_in_at", "opted_in_by"])
            c.save(update_fields=update_fields)
            if active_opt_out:
                bot.log(
                    "warning",
                    "manual_opt_in",
                    f"client={c.pk}; user={request.user.pk}; explicit consent confirmed",
                )
    return JsonResponse({"success": True, "bot_paused": False})


@login_required(login_url="management_login")
@require_POST
def bot_client_hide_api(request, client_id):
    blocked = _require_bot_json(request)
    if blocked:
        return blocked
    from django.utils import timezone

    from .models import IgClient, InstagramBotMessage
    from .services import bot_followups

    with transaction.atomic():
        c = IgClient.objects.select_for_update().filter(id=client_id).first()
        if not c:
            return JsonResponse({"success": False, "error": "Клієнта не знайдено."}, status=404)
        now = timezone.now()
        if bot.client_automation_busy(c, now=now):
            return JsonResponse({
                "success": False,
                "retryable": True,
                "error": "Бот завершує поточну відповідь. Зачекайте кілька секунд і повторіть приховування.",
            }, status=409)
        # Прострочена lease не є активною автоматизацією і не повинна заважати
        # модерації після аварійного завершення worker-а.
        c.automation_lease_token = ""
        c.automation_lease_until = None
        c.hidden_at = now
        c.reply_permission_epoch = int(c.reply_permission_epoch or 0) + 1
        c.hidden_reason = (request.POST.get("reason") or "manual")[:255]
        c.save(update_fields=[
            "automation_lease_token", "automation_lease_until",
            "hidden_at", "reply_permission_epoch", "hidden_reason", "updated_at",
        ])
        cancelled_followups = bot_followups.cancel_pending(c, reason="hidden")
        # Не залишаємо legacy pending rows, які могли потрапити в чергу до
        # натискання Hide: після успішного Hide вони не мають чекати worker-а.
        cancelled_messages = InstagramBotMessage.objects.filter(
            client=c,
            role=InstagramBotMessage.Role.USER,
            status__in=[
                InstagramBotMessage.Status.PENDING,
                InstagramBotMessage.Status.PROCESSING,
            ],
        ).update(
            status=InstagramBotMessage.Status.DONE,
            processed_at=now,
            processing_started_at=None,
        )
    return JsonResponse({
        "success": True,
        "hidden": True,
        "automation_disabled": True,
        "cancelled_followups": cancelled_followups,
        "cancelled_messages": cancelled_messages,
        "message": "Клієнта приховано: бот не оброблятиме його повідомлення, а статистика не враховуватиме цей діалог.",
    })


@login_required(login_url="management_login")
@require_POST
def bot_client_unhide_api(request, client_id):
    blocked = _require_bot_json(request)
    if blocked:
        return blocked
    from .models import IgClient

    with transaction.atomic():
        c = IgClient.objects.select_for_update().filter(id=client_id).first()
        if not c:
            return JsonResponse({"success": False, "error": "Клієнта не знайдено."}, status=404)
        c.hidden_at = None
        c.reply_permission_epoch = int(c.reply_permission_epoch or 0) + 1
        c.hidden_reason = ""
        c.save(update_fields=[
            "hidden_at", "reply_permission_epoch", "hidden_reason", "updated_at",
        ])
    return JsonResponse({
        "success": True,
        "hidden": False,
        "message": "Клієнта повернено до активного списку.",
    })


@login_required(login_url="management_login")
@require_POST
def bot_client_mark_lost_api(request, client_id):
    blocked = _require_bot_json(request)
    if blocked:
        return blocked
    from .models import IgClient
    from .services import bot_followups

    c = IgClient.objects.filter(id=client_id).first()
    if not c:
        return JsonResponse({"success": False, "error": "Клієнта не знайдено."}, status=404)
    c.lost_reason = (request.POST.get("reason") or "manual_lost")[:64]
    c.primary_objection = IgClient.Objection.NO_BUY
    c.set_stage(IgClient.Stage.COLD, reason=c.lost_reason)
    c.save(update_fields=["lost_reason", "primary_objection", "updated_at"])
    bot_followups.cancel_pending(c, reason="lost")
    return JsonResponse({"success": True, "stage": c.stage, "lost_reason": c.lost_reason})


@login_required(login_url="management_login")
@require_GET
def bot_stats_api(request):
    blocked = _require_bot_json(request)
    if blocked:
        return blocked
    from datetime import timedelta

    from .models import IgClient, IgConversationSignal, IgDeal, IgFollowUpTask

    try:
        range_days = int(request.GET.get("days") or 0)
    except (TypeError, ValueError):
        range_days = 0
    if range_days not in {0, 1, 7, 30}:
        range_days = 0
    since = None
    if range_days == 1:
        local_now = timezone.localtime()
        since = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif range_days:
        since = timezone.now() - timedelta(days=range_days)

    active_clients = _with_latest_interaction(annotate_verified_payment(
        IgClient.objects.filter(hidden_at__isnull=True)
    ))
    if since:
        active_clients = active_clients.filter(
            Q(last_message_at__gte=since)
            | Q(last_message_at__isnull=True, created_at__gte=since)
        )
    conversations = active_clients.count()
    from .ig_bot_models import IgConversationAnalysisSnapshot

    interaction_labels = dict(IgConversationAnalysisSnapshot.InteractionType.choices)
    interaction_counts = [
        {
            "type": row["latest_interaction_type"],
            "label": str(interaction_labels.get(row["latest_interaction_type"], "Не визначено")),
            "count": row["count"],
        }
        for row in active_clients.exclude(latest_interaction_type__isnull=True)
        .exclude(latest_interaction_type="")
        .values("latest_interaction_type")
        .annotate(count=Count("id"))
        .order_by("-count", "latest_interaction_type")
    ]
    stage_counts = {}
    for row in active_clients.values("stage", "has_verified_payment").annotate(
        count=Count("id")
    ).order_by():
        stage = row["stage"]
        if stage in {IgClient.Stage.PAID, IgClient.Stage.ORDER_CREATED, IgClient.Stage.DONE} and not row["has_verified_payment"]:
            stage = "unverified"
        stage_counts[stage] = stage_counts.get(stage, 0) + row["count"]
    signal_qs = IgConversationSignal.objects.filter(client__hidden_at__isnull=True)
    if since:
        signal_qs = signal_qs.filter(created_at__gte=since)
    signals = {
        row["signal_type"]: row["count"]
        for row in signal_qs.values("signal_type").annotate(count=Count("id")).order_by()
    }
    objections = {
        row["primary_objection"]: row["count"]
        for row in active_clients.exclude(primary_objection=IgClient.Objection.NONE)
        .values("primary_objection").annotate(count=Count("id")).order_by()
    }
    # Keep signal names too; the frontend can show both high-level client state
    # and granular event breakdown.
    objections.update({k: v for k, v in signals.items() if "objection" in k or k in {"no_reply", "lost"}})
    product_interest = [
        {
            "product_id": row["current_product_id"],
            "product_title": row["current_product__title"] or "",
            "count": row["count"],
        }
        for row in active_clients.exclude(current_product__isnull=True)
        .values("current_product_id", "current_product__title").annotate(count=Count("id"))
        .order_by("-count")[:25]
    ]
    payment_event_filter = verified_payment_q("deals__")
    if since:
        payment_event_filter &= (
            Q(deals__payment_projection__paid_at__gte=since)
            | Q(deals__payment_projection__isnull=True, deals__paid_at__gte=since)
        )
    revenue_filter = payment_event_filter
    payment_deals = IgDeal.objects.all()
    if since:
        payment_deals = payment_deals.filter(
            Q(payment_projection__paid_at__gte=since)
            | Q(payment_projection__isnull=True, paid_at__gte=since)
        )
    active_clients = annotate_verified_payment(
        active_clients,
        alias="paid_in_range",
        deal_queryset=payment_deals,
    )
    followup_payment_filter = verified_payment_q("client__deals__")
    if since:
        followup_payment_filter &= (
            Q(client__deals__payment_projection__paid_at__gte=since)
            | Q(client__deals__payment_projection__isnull=True, client__deals__paid_at__gte=since)
        )
    ad_rows = []
    for row in (
        active_clients.exclude(Q(ad_id="") & Q(ad_ref="") & Q(ad_title=""))
        .values("ad_id", "ad_ref", "ad_title")
        .annotate(
            chats=Count("id", distinct=True),
            paid=Count(
                "id",
                filter=payment_event_filter,
                distinct=True,
            ),
            revenue=Sum(
                F("deals__payment_projection__gross_amount")
                - F("deals__payment_projection__refunded_amount"),
                filter=revenue_filter,
            ),
        )
        .order_by("-chats")[:50]
    ):
        ad_rows.append({
            "ad_id": row["ad_id"],
            "ad_ref": row["ad_ref"],
            "ad_title": row["ad_title"],
            "chats": row["chats"],
            "paid": row["paid"],
            "revenue": str(row["revenue"] or 0),
        })
    totals = {
        "conversations": conversations,
        "qualified": active_clients.filter(buying_readiness__gte=40).count(),
        "product_matched": active_clients.filter(current_product__isnull=False).count(),
        "checkout_or_payment": active_clients.filter(stage__in=[IgClient.Stage.CHECKOUT, IgClient.Stage.PAYMENT_PENDING]).count(),
        "paid": active_clients.filter(paid_in_range=True).count(),
        "hidden": IgClient.objects.filter(hidden_at__isnull=False).count(),
        "pending_followups": IgFollowUpTask.objects.filter(status=IgFollowUpTask.Status.PENDING, client__hidden_at__isnull=True).count(),
        "followup_recoveries": IgFollowUpTask.objects.filter(status=IgFollowUpTask.Status.SENT, client__hidden_at__isnull=True).filter(followup_payment_filter).distinct().count(),
        "discount_conversions": active_clients.filter(discount_offered_percent__gt=0, paid_in_range=True).count(),
        "manager_takeovers": active_clients.filter(manager_takeover=True).count(),
        "custom_print_handoffs": active_clients.filter(intent=IgClient.Intent.CUSTOM_PRINT, stage=IgClient.Stage.LEAD_TO_MANAGER).count(),
    }
    return JsonResponse({
        "success": True,
        "range_days": range_days,
        "range_from": since.isoformat() if since else "",
        "totals": totals,
        "stages": stage_counts,
        "interactions": interaction_counts,
        "objections": objections,
        "signals": signals,
        "products": product_interest,
        "ads": ad_rows,
    })


# ---------------------------------------------------------------------------
# Інструкції / швидкі посилання / реклама — CRUD у вкладці «Бот» (Task 23)
# ---------------------------------------------------------------------------
def _truthy(v) -> bool:
    return str(v or "").strip().lower() in {"1", "true", "on", "yes"}


@login_required(login_url="management_login")
@require_GET
def bot_kb_api(request):
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    from .models import BotAdCampaign, BotInstruction, BotQuickLink

    instructions = [
        {"id": i.id, "title": i.title, "body": i.body, "intent_tags": i.intent_tags,
         "is_active": i.is_active, "priority": i.priority}
        for i in BotInstruction.objects.all().order_by("priority", "id")[:300]
    ]
    quick_links = [
        {"id": q.id, "kind": q.kind, "label": q.label, "url": q.url,
         "garment_type": q.garment_type, "trigger_keywords": q.trigger_keywords,
         "is_active": q.is_active, "order": q.order}
        for q in BotQuickLink.objects.all().order_by("order", "id")[:300]
    ]
    ad_campaigns = [
        {"id": a.id, "ad_id": a.ad_id, "ref": a.ref, "title": a.title, "theme": a.theme,
         "landing_note": a.landing_note, "is_active": a.is_active}
        for a in BotAdCampaign.objects.all().order_by("-id")[:300]
    ]
    return JsonResponse({
        "success": True,
        "instructions": instructions,
        "quick_links": quick_links,
        "ad_campaigns": ad_campaigns,
    })


@login_required(login_url="management_login")
@require_POST
def bot_kb_save_api(request):
    blocked = _require_admin_json(request)
    if blocked:
        return blocked
    from .models import BotAdCampaign, BotInstruction, BotQuickLink

    kind = (request.POST.get("type") or "").strip()
    op = (request.POST.get("op") or "save").strip()
    obj_id = request.POST.get("id") or None

    model = {
        "instruction": BotInstruction,
        "quicklink": BotQuickLink,
        "adcampaign": BotAdCampaign,
    }.get(kind)
    if not model:
        return JsonResponse({"success": False, "error": "Невідомий тип."}, status=400)

    if op == "delete":
        if obj_id:
            model.objects.filter(id=obj_id).delete()
        return JsonResponse({"success": True})

    obj = model.objects.filter(id=obj_id).first() if obj_id else model()
    p = request.POST
    if kind == "instruction":
        obj.title = (p.get("title") or "")[:200]
        obj.body = p.get("body") or ""
        obj.intent_tags = (p.get("intent_tags") or "")[:400]
        obj.is_active = _truthy(p.get("is_active", "1"))
        try:
            obj.priority = int(p.get("priority") or 100)
        except (TypeError, ValueError):
            obj.priority = 100
    elif kind == "quicklink":
        obj.kind = (p.get("kind") or "other")[:20]
        obj.label = (p.get("label") or "")[:200]
        obj.url = (p.get("url") or "")[:600]
        obj.garment_type = (p.get("garment_type") or "")[:40]
        obj.trigger_keywords = (p.get("trigger_keywords") or "")[:400]
        obj.is_active = _truthy(p.get("is_active", "1"))
        try:
            obj.order = int(p.get("order") or 100)
        except (TypeError, ValueError):
            obj.order = 100
    else:  # adcampaign
        obj.ad_id = (p.get("ad_id") or "")[:64]
        obj.ref = (p.get("ref") or "")[:255]
        obj.title = (p.get("title") or "")[:255]
        obj.theme = (p.get("theme") or "")[:120]
        obj.landing_note = p.get("landing_note") or ""
        obj.is_active = _truthy(p.get("is_active", "1"))
    obj.save()
    return JsonResponse({"success": True, "id": obj.id})
