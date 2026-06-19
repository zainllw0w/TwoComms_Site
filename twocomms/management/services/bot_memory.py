"""
Пам'ять діалогу IG-бота: rolling summary + ретеншн.

Ідея: щоб модель «пам'ятала» клієнта довго й дешево, ми періодично стискаємо
історію у компактний memory_summary (management-модель), а в контекст даємо
summary + свіже вікно останніх повідомлень. Так навіть інша модель (через ліміти)
підхоплює суть діалогу. Картки, неактивні понад RETENTION_DAYS, чистяться.
"""
from __future__ import annotations

import datetime

from django.utils import timezone

from management.models import IgClient, InstagramBotMessage
from management.services.call_ai_analysis import gemini_generate_text

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
            "maxOutputTokens": 400,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }


def update_client_memory(client: IgClient) -> bool:
    """Перегенеровує memory_summary з історії. False, якщо немає що стискати або
    модель не відповіла."""
    transcript = _transcript(client)
    if not transcript.strip():
        return False
    try:
        out = gemini_generate_text(build_summary_payload(transcript), role="management")
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
    count = InstagramBotMessage.objects.filter(client=client).count()
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
