"""ЭА.21 — ідемпотентний намір відправки і `UNKNOWN` замість повторної відправки.

**Що саме ламалось.** Правило проекту «не ретраїти Meta Send після неоднозначного
таймауту» вже було вірним, але трималось на послідовності перевірок у коді, а не
на обмеженні в БД. Якщо Meta прийняла запит, а відповідь до нас не дійшла,
повторна відправка створює ДРУГЕ реальне повідомлення клієнту — той самий видимий
спам, але з іншої причини. `07_…HANDOFF` окремо позначає, що провайдерські
дублікати при неоднозначних відправках **не перевірені**, тобто вважати їх
неможливими не можна.

**Що робить цей модуль.** Дає одну точку, яка заявляє намір відправки:

1. ключ будується детерміновано з ідентичності ходу/рядка і виду відправки;
2. він записується в ТІЙ САМІЙ умовній транзакції, що ставить
   `send_state="sending"`, тобто до першого зовнішнього I/O;
3. унікальність ключа в БД робить другу заявку фізично неможливою — і для
   другого воркера, і для тієї самої строки після рестарту процесу.

**Чому ключ у рядку, а не окрема таблиця.** Outbox-паттерн у проекті вже саме
такий: `IgAiReplyRecoveryJob` створює строку до запиту. Друга таблиця намірів
дала б другий джерело істини про те, чи відправлено — рівно те, чого забороняє
Э2.2B §4.2. Э2.2B розширює цей ключ revision-ом ходу.

**Сверка виконується ЧИТАННЯМ, не відправкою.** Поллінг діалогів уже зберігає
page-side повідомлення як рядки `MODEL`/`MANAGER` з `mid` і `provider_created_at`.
Тому щоб дізнатись, чи дійшла неоднозначна відправка, не потрібен жоден новий
провайдерський запит: достатньо локального читання того, що поллінг уже приніс.
"""
from __future__ import annotations

import hashlib
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from management.models import InstagramBotMessage

# Види відправки. Один хід може мати рівно один намір кожного виду — саме це
# дозволяє Э2.2B відправити stable ACK і пізніше substantive відповідь, не
# створивши двох substantive.
KIND_SUBSTANTIVE = "substantive"
KIND_ACK = "ack"
KIND_CORRECTIVE = "corrective"
KIND_HOLDING = "holding"
KIND_RECOVERY = "recovery"

# Скільки часу неоднозначна відправка чекає сверки, перш ніж стати
# `not_delivered`. Береться з запасом на затримку поллінга: поллінг ходить
# рідше, ніж живий цикл, і рання відмітка «не дійшло» була б брехнею.
RECONCILE_GRACE = timedelta(minutes=20)
RECONCILE_MAX_AGE = timedelta(hours=48)
# Провайдерський час page-side рядка може бути трохи раніше нашого локального
# `send_started_at` (різні годинники). Вікно свідомо асимметричне.
CLOCK_SKEW = timedelta(seconds=30)


def build_key(
    *,
    row=None,
    turn_id: int = 0,
    revision: int = 0,
    kind: str = KIND_SUBSTANTIVE,
) -> str:
    """Детермінований ключ наміру відправки.

    Хід — канонічна одиниця (Э0.6), тому ключ будується від нього, коли хід
    відомий. Рядок лишається fallback-ом для шляхів, у яких ходу немає
    (історичні рядки, службові відправки).
    """
    kind = str(kind or KIND_SUBSTANTIVE)[:16]
    try:
        turn_id = int(turn_id or 0)
        revision = int(revision or 0)
    except (TypeError, ValueError):
        turn_id, revision = 0, 0
    if turn_id:
        return f"t{turn_id}:r{revision}:{kind}"
    row_id = int(getattr(row, "pk", row) or 0)
    if not row_id:
        return ""
    return f"m{row_id}:{kind}"


def text_digest(text: str) -> str:
    """Короткий дайджест тексту для сверки без збереження самого тексту."""
    normalized = " ".join(str(text or "").split()).lower()
    if not normalized:
        return ""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def claim_send_intent(
    claim_queryset,
    row: InstagramBotMessage,
    *,
    kind: str = KIND_SUBSTANTIVE,
    turn_id: int = 0,
    revision: int = 0,
    now=None,
) -> tuple[str, int]:
    """Заявити намір відправки і перейти в `sending` одним умовним update.

    `claim_queryset` — вже звужений до саме цієї заявки воркера queryset (у
    проекті це `_own_processing_claim(row)`). Повертає `(ключ, оновлено)`.
    `оновлено == 0` означає, що заявку втрачено або намір уже заявлений — у
    жодному з цих випадків відправляти не можна.
    """
    now = now or timezone.now()
    key = build_key(row=row, turn_id=turn_id, revision=revision, kind=kind)
    fields = {
        "send_state": "sending",
        "send_started_at": now,
        "send_completed_at": None,
    }
    if key:
        fields["send_idempotency_key"] = key
    try:
        with transaction.atomic():
            updated = claim_queryset.update(**fields)
    except IntegrityError:
        # Ключ уже належить іншому рядку: намір заявлений раніше. Це штатний
        # результат `intent_already_claimed`, а не помилка — і саме він
        # забороняє другу відправку.
        return key, 0
    return key, int(updated)


def intent_owner(key: str) -> InstagramBotMessage | None:
    """Рядок, який уже тримає цей намір відправки."""
    if not key:
        return None
    return InstagramBotMessage.objects.filter(send_idempotency_key=key).first()


def _page_side_evidence(row: InstagramBotMessage, *, digest: str) -> InstagramBotMessage | None:
    """Локальний доказ того, що відповідь усе ж дійшла до діалогу.

    Доказ приносить поллінг: page-side повідомлення зберігається як рядок
    `MODEL`/`MANAGER` з `mid` і `provider_created_at`. Ніякого нового запиту до
    Meta тут немає — це вимога ЭА.21 «сверку виконувати читанням».
    """
    started = row.send_started_at
    if not started or not row.client_id:
        return None
    candidates = InstagramBotMessage.objects.filter(
        client_id=row.client_id,
        role__in=(InstagramBotMessage.Role.MODEL, InstagramBotMessage.Role.MANAGER),
        id__gt=row.pk,
    ).filter(mid__gt="").order_by("id")[:50]
    for candidate in candidates:
        observed_at = candidate.provider_created_at or candidate.created_at
        if observed_at and observed_at < started - CLOCK_SKEW:
            continue
        if digest and text_digest(candidate.text) != digest:
            continue
        return candidate
    return None


def reconcile_unknown_sends(*, now=None, limit: int = 100, apply: bool = False) -> dict:
    """Розв'язати неоднозначні відправки читанням; НІКОЛИ не відправляти повторно.

    Три можливих результати на рядок:

    * `resolved_sent` — знайдено page-side доказ, що повідомлення в діалозі;
    * `pending` — ще в межах grace-періоду, поллінг міг не дійти;
    * `not_delivered` — доказу немає довше `RECONCILE_MAX_AGE`. Це НЕ дозвіл
      відправити ще раз: рядок лишається терміналом і потребує людини.
    """
    now = now or timezone.now()
    rows = list(
        InstagramBotMessage.objects.filter(
            send_state="unknown",
            send_started_at__isnull=False,
            send_started_at__gte=now - RECONCILE_MAX_AGE * 4,
        ).order_by("send_started_at")[: max(1, int(limit))]
    )
    counts: dict = {}
    entries = []
    for row in rows:
        digest = text_digest(row.delivery_original_text or "")
        evidence = _page_side_evidence(row, digest=digest)
        age = now - row.send_started_at
        if evidence is not None:
            outcome = "resolved_sent"
        elif age < RECONCILE_GRACE:
            outcome = "pending"
        elif age >= RECONCILE_MAX_AGE:
            outcome = "not_delivered"
        else:
            outcome = "pending"
        counts[outcome] = counts.get(outcome, 0) + 1
        entries.append(
            {
                "row_id": row.pk,
                "client_id": row.client_id,
                "key": row.send_idempotency_key or "",
                "outcome": outcome,
                "evidence_id": getattr(evidence, "pk", None),
                "age_seconds": int(age.total_seconds()),
            }
        )
        if not apply or outcome == "pending":
            continue
        if outcome == "resolved_sent":
            InstagramBotMessage.objects.filter(pk=row.pk, send_state="unknown").update(
                send_state="sent",
                send_completed_at=(
                    evidence.provider_created_at or evidence.created_at or now
                ),
                delivery_failure_boundary="",
            )
        else:
            InstagramBotMessage.objects.filter(pk=row.pk, send_state="unknown").update(
                delivery_failure_boundary="unknown_not_delivered",
            )
    return {"scanned": len(rows), "counts": counts, "applied": bool(apply), "entries": entries}


def duplicate_outbound_report(*, window_seconds: int = 120, limit: int = 50) -> dict:
    """Чисельна перевірка історичних дублікатів (read-only, ЭА.21 крок 1).

    Питання джерела було відкритим: чи існують у клієнтів дві однакові вихідні
    строки з різними `provider_message_id` у межах секунд. Без числа не можна
    сказати, чи повторні відправки коли-небудь відбувались.
    """
    window = timedelta(seconds=max(1, int(window_seconds)))
    rows = list(
        InstagramBotMessage.objects.filter(
            role=InstagramBotMessage.Role.MODEL,
        )
        .exclude(text="")
        .order_by("client_id", "id")
        .values("id", "client_id", "text", "provider_message_id", "created_at")
    )
    seen: dict = {}
    pairs = []
    for row in rows:
        digest = text_digest(row["text"])
        if not digest:
            continue
        bucket = (row["client_id"], digest)
        previous = seen.get(bucket)
        if (
            previous
            and row["created_at"]
            and previous["created_at"]
            and row["created_at"] - previous["created_at"] <= window
            and str(row["provider_message_id"] or "")
            != str(previous["provider_message_id"] or "")
        ):
            pairs.append(
                {
                    "client_id": row["client_id"],
                    "first_id": previous["id"],
                    "second_id": row["id"],
                    "gap_seconds": int(
                        (row["created_at"] - previous["created_at"]).total_seconds()
                    ),
                }
            )
        seen[bucket] = row
    return {
        "outbound_scanned": len(rows),
        "window_seconds": int(window_seconds),
        "duplicate_pairs": len(pairs),
        "examples": pairs[: max(1, int(limit))],
    }
