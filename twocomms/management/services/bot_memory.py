"""
Пам'ять діалогу IG-бота: rolling summary + ретеншн.

Ідея: щоб модель «пам'ятала» клієнта довго й дешево, ми періодично стискаємо
історію у компактний memory_summary (management-модель), а в контекст даємо
summary + свіже вікно останніх повідомлень. Так навіть інша модель (через ліміти)
підхоплює суть діалогу. Картки, неактивні понад RETENTION_DAYS, чистяться.
"""
from __future__ import annotations

import datetime
import hashlib

from django.utils import timezone

from management.models import IgClient, InstagramBotMessage
from management.services.call_ai_analysis import gemini_generate_text
from management.services.ig_funnel_reset import current_message_floor

RECENT_WINDOW = 10          # скільки останніх реплік даємо дослівно
TRANSCRIPT_LIMIT = 60       # скільки реплік беремо для стиснення в summary
MEMORY_EVERY = 8            # кожні N повідомлень оновлюємо пам'ять
RETENTION_DAYS = 180        # 6 місяців від останнього повідомлення

SUMMARY_INSTRUCTION = (
    "Стисни діалог менеджера-бота з клієнтом у компактну пам'ять українською "
    "(до 120 слів). Зафіксуй: що хоче клієнт, які товари/ціни/розміри обговорювали, "
    "домовленості, заперечення, поточний етап, важливі факти (ім'я, місто, телефон, "
    "відділення — якщо були). Тільки суть, без вступів і без вигадок."
)


def memory_note(client: IgClient) -> str | None:
    """Підказка-пам'ять для system_instruction (None, якщо порожня)."""
    summary = (client.memory_summary or "").strip()
    if not summary:
        return None
    return "[ПАМ'ЯТЬ ПРО КЛІЄНТА] " + summary


def _transcript(client: IgClient, limit: int = TRANSCRIPT_LIMIT) -> str:
    rows = list(
        InstagramBotMessage.objects.filter(client=client)
        .filter(id__gte=current_message_floor(client))
        .exclude(status=InstagramBotMessage.Status.FAILED)
        .order_by("-id")[:limit]
    )
    rows.reverse()
    lines = []
    for r in rows:
        t = (r.text or "").strip()
        if not t:
            continue
        who = "Клієнт" if r.role == InstagramBotMessage.Role.USER else "Бот"
        lines.append(f"{who}: {t}")
    return "\n".join(lines)


def build_summary_payload(transcript: str) -> dict:
    return {
        "contents": [
            {"role": "user", "parts": [{"text": SUMMARY_INSTRUCTION + "\n\nДІАЛОГ:\n" + transcript}]}
        ],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 4096,
        },
    }


def update_client_memory(client: IgClient) -> bool:
    """Перегенеровує memory_summary з історії. False, якщо немає що стискати або
    модель не відповіла."""
    transcript = _transcript(client)
    if not transcript.strip():
        return False
    try:
        out = gemini_generate_text(
            build_summary_payload(transcript),
            role="management",
            reasoning_task="memory_summary",
        )
    except Exception:
        return False
    summary = (out.get("parsed") or "").strip()
    if not summary:
        return False
    client.memory_summary = summary[:4000]
    client.memory_updated_at = timezone.now()
    client.save(update_fields=["memory_summary", "memory_updated_at", "updated_at"])
    return True


def maybe_update_memory(client: IgClient, every: int = MEMORY_EVERY) -> bool:
    """Оновлює пам'ять, коли к-сть повідомлень кратна `every` (дешева евристика)."""
    count = InstagramBotMessage.objects.filter(
        client=client,
        id__gte=current_message_floor(client),
    ).count()
    if count and every and count % every == 0:
        return update_client_memory(client)
    return False


def purge_stale_clients(days: int = RETENTION_DAYS) -> int:
    """Видаляє картки клієнтів, неактивні понад `days` (каскадом — їх повідомлення).
    Повертає к-сть видалених карток."""
    cutoff = timezone.now() - datetime.timedelta(days=days)
    qs = IgClient.objects.filter(last_message_at__isnull=False, last_message_at__lt=cutoff)
    count = qs.count()
    if count:
        qs.delete()
    return count


def order_status_note(client, reference: str = "") -> str | None:
    """Stored status for one exact order, or an explicit ambiguity guard."""
    try:
        from management.services.ig_commercial_episodes import (
            OrderResolutionError,
            _client_order_queryset,
            resolve_client_order,
        )

        if reference:
            order = resolve_client_order(client, reference).order
            from management.ig_bot_models import IgFollowUpTask

            IgFollowUpTask.objects.filter(
                client=client,
                kind=IgFollowUpTask.Kind.MANAGER_TASK,
                status__in=(
                    IgFollowUpTask.Status.PENDING,
                    IgFollowUpTask.Status.SKIPPED,
                ),
                reason__startswith="ambiguous_order_status",
            ).update(
                status=IgFollowUpTask.Status.CANCELLED,
                skip_reason="exact_order_reference_received",
                updated_at=timezone.now(),
            )
        else:
            orders = list(_client_order_queryset(client).order_by("-created", "-id")[:6])
            if not orders:
                return None
            if len(orders) > 1:
                from management.ig_bot_models import IgFollowUpTask

                episode_id = int(client.current_commercial_episode_id or 0)
                fingerprint = hashlib.sha256(
                    ":".join(str(item.pk) for item in sorted(orders, key=lambda row: row.pk)).encode()
                ).hexdigest()[:16]
                reason = f"ambiguous_order_status:e{episode_id}:{fingerprint}"
                message_text = (
                    "У клієнта кілька замовлень. Уточніть точний номер "
                    "замовлення або ТТН перед відповіддю про доставку."
                )
                task, _created = IgFollowUpTask.objects.get_or_create(
                    client=client,
                    kind=IgFollowUpTask.Kind.MANAGER_TASK,
                    reason=reason,
                    defaults={
                        "due_at": timezone.now(),
                        # This is operator work, never an automatic customer send.
                        "status": IgFollowUpTask.Status.SKIPPED,
                        "skip_reason": "human_agent_required",
                        "message_text": message_text,
                    },
                )
                changed = []
                if task.status != IgFollowUpTask.Status.SKIPPED:
                    task.status = IgFollowUpTask.Status.SKIPPED
                    changed.append("status")
                if task.skip_reason != "human_agent_required":
                    task.skip_reason = "human_agent_required"
                    changed.append("skip_reason")
                if task.message_text != message_text:
                    task.message_text = message_text
                    changed.append("message_text")
                if changed:
                    changed.append("updated_at")
                    task.save(update_fields=changed)
                try:
                    from management.services.instagram_bot import notify_manager

                    client_label = client.username or client.display_name or client.igsid
                    notify_manager(
                        f"🧭 IG: у {client_label} кілька замовлень. "
                        "Перед відповіддю про статус потрібен точний номер замовлення або ТТН.",
                        dedupe_key=reason,
                        event_type="ambiguous_order_status",
                        client=client,
                    )
                except Exception:
                    pass
                choices = ", ".join(
                    f"№{item.order_number} ({item.get_status_display()})"
                    for item in orders[:5]
                )
                return (
                    f"у клієнта кілька замовлень: {choices}. Не вгадуй потрібне; "
                    "попроси точний номер замовлення або ТТН"
                )
            order = orders[0]
    except OrderResolutionError as exc:
        return f"замовлення не визначено: {exc}. Попроси точний номер або ТТН"
    except Exception:
        return None
    status_map = {
        "new": "прийнято, в обробці",
        "prep": "готується до відправлення",
        "ship": "відправлено",
        "done": "отримано",
        "cancelled": "скасовано",
    }
    st = status_map.get(order.status, order.status or "в обробці")
    msg = f"у клієнта вже є замовлення №{order.order_number} — статус: {st}"
    if order.tracking_number:
        msg += f", ТТН {order.tracking_number}"
    msg += " (про статус/доставку відповідай по цих даних, не вигадуй)"
    return msg


def client_context_note(client) -> str | None:
    """Компактний контекст клієнта для швидкої орієнтації бота: атрибуція реклами
    (з мапінгом на товар/тему), статус постійного клієнта і статус останнього
    замовлення. Дає змогу одразу вести по суті, а не питати «дайте фото»."""
    parts = []
    try:
        from management.models import BotAdCampaign

        camp = None
        if client.ad_id or client.ad_ref:
            camp = BotAdCampaign.match(ad_id=client.ad_id or None, ref=client.ad_ref or None)
        if camp and camp.product_id:
            p = camp.product
            try:
                price = int(getattr(p, "final_price", None) or p.price)
            except Exception:
                price = getattr(p, "price", "")
            title = camp.title or client.ad_title or "реклама"
            parts.append(
                f"клієнт прийшов з реклами «{title}» — його найімовірніше цікавить "
                f"«{p.title}» (довідкова каталожна ціна {price} грн, "
                f"https://twocomms.shop/product/{p.slug}/); це не погоджена сума "
                "поточного замовлення; "
                f"веди одразу по суті, не починай з «надішліть фото»"
            )
        elif camp and camp.theme:
            parts.append(f"клієнт з реклами «{camp.title or client.ad_title}», тема: {camp.theme}")
        elif client.ad_title:
            parts.append(f"клієнт прийшов з реклами: «{client.ad_title}»")
    except Exception:
        pass
    if (client.purchases_count or 0) > 0:
        parts.append(
            f"постійний клієнт (покупок: {client.purchases_count}) — спілкуйся тепло, як зі "
            f"знайомим; якщо хоче ще товар, це нова покупка/нове замовлення — допоможи обрати заново"
        )
    try:
        from management.services.ig_commercial_episodes import client_payment_truth_state

        payment = client_payment_truth_state(client).get("current_payment_truth") or {}
        if payment and (payment.get("deal_id") or payment.get("review_id") or payment.get("order_id")):
            total = payment.get("order_total") or "невідома"
            requested = payment.get("requested_payment_amount") or "0.00"
            provider = payment.get("provider_confirmed_amount") or "0.00"
            manager = payment.get("manager_confirmed_amount") or "0.00"
            confirmed = payment.get("confirmed_paid_amount") or "не визначено"
            remaining = payment.get("remaining_amount") or "не визначено"
            parts.append(
                "ПОТОЧНА КОМЕРЦІЙНА ІСТИНА (вища за історичну пам'ять): "
                f"погоджена вартість {total} {payment.get('currency') or 'UAH'} "
                f"[джерело: {payment.get('order_total_source') or 'unknown'}]; "
                f"зараз запитано {requested} [джерело: "
                f"{payment.get('requested_payment_source') or 'unknown'}]; "
                f"Monobank фактично підтвердив {provider}; менеджер підтвердив {manager} "
                f"[джерело суми: {payment.get('manager_amount_source') or 'none'}]; "
                f"ефективно підтверджено {confirmed}, залишок {remaining}, "
                f"звірка: {payment.get('reconciliation_state') or 'unverified'}. "
                "Не замінюй ці суми ціною з реклами, каталогу, старого замовлення "
                "чи історичної пам'яті"
            )
    except Exception:
        pass
    try:
        on = order_status_note(client)
        if on:
            parts.append(on)
    except Exception:
        pass
    if not parts:
        return None
    return "[КОНТЕКСТ КЛІЄНТА] " + "; ".join(parts) + "."


# IMP-030. Профиль живёт под служебным ключом: соглашение в `sales_context` уже
# существует (`_provenance`, `_media_evidence`, `_media_catalog_match`), а
# бизнес-ключи там без подчёркивания (`size`, `color`, `gift`).
PROFILE_KEY = "_profile"
PROFILE_OBJECTION_LIMIT = 12


def update_client_profile(client) -> dict:
    """Maintain a structured client profile inside the existing `sales_context`.

    The plan framed this as replacing the free-text rolling summary. Measurement
    says there is nothing to replace: `memory_summary` is filled for **1 client
    out of 289**, because `maybe_update_memory` only runs after the bot
    successfully sends a reply — and it has sent 20 replies in total. So this is
    the first memory the system has, not a substitute for an existing one.

    Deliberately narrow. Half of the originally proposed schema would duplicate
    existing columns (`current_size`, `language`, `purchases_count`), and a
    duplicate is a second source of truth waiting to disagree. What is genuinely
    absent is the **history of objections** — `primary_objection` is a single
    overwritten field — and structured delivery data.
    """
    if not client or not getattr(client, "pk", None):
        return {}
    context = client.sales_context if isinstance(client.sales_context, dict) else {}
    profile = context.get(PROFILE_KEY)
    if not isinstance(profile, dict):
        profile = {}

    profile["fit"] = {
        "size": str(client.current_size or ""),
        "color": str(client.current_color or ""),
    }
    profile["comms"] = {"lang": str(client.language or "uk")}
    profile["history"] = {
        "purchases": int(getattr(client, "purchases_count", 0) or 0),
        "total_spent": str(getattr(client, "total_spent", "") or "0"),
    }

    objections = profile.get("objections")
    if not isinstance(objections, list):
        objections = []
    current = str(client.primary_objection or "")
    from management.models import IgClient as _IgClient

    if current and current != _IgClient.Objection.NONE:
        if not any(
            isinstance(row, dict) and row.get("type") == current for row in objections
        ):
            from django.utils import timezone as _tz

            objections.append({"type": current, "at": _tz.now().isoformat()})
    profile["objections"] = objections[-PROFILE_OBJECTION_LIMIT:]

    context[PROFILE_KEY] = profile
    client.sales_context = context
    client.__class__.objects.filter(pk=client.pk).update(sales_context=context)
    return profile


def preserved_profile(client) -> dict:
    """Profile part of `sales_context`, meant to survive a funnel reset.

    `reset_funnel` blanks the whole `sales_context`, which is right for inferred
    state but wrong for confirmed facts: a size the customer stated and an
    objection they voiced did not stop being true because an operator restarted
    the funnel.
    """
    context = getattr(client, "sales_context", None)
    if not isinstance(context, dict):
        return {}
    profile = context.get(PROFILE_KEY)
    return {PROFILE_KEY: profile} if isinstance(profile, dict) else {}
