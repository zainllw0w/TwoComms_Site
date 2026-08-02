"""Журнал вибору: з чого на що клієнт перейшов і **чому**.

Прямий запит заказника: «був такий товар, однак його немає — і воронка має це
запам'ятати, що людина з цього товару перейшла на інший, і перейшла з такої-то
причини». Далі це має впливати на те, що бот говорить: якщо клієнт уже другий
раз натикається на відсутність, доречно вибачитись і покликати менеджера, а не
бадро запропонувати третій варіант.

Чому саме журнал, а не поле в картці. Поле відповідає на «де ми зараз», а
питання заказника інше: «як ми тут опинились». Дві заміни товару через
відсутність і дві заміни через смак клієнта дають однакове поточне значення
`current_product_id`, але вимагають зовсім різної реакції.

Чому причина приходить від виклику, а не з тексту. Це головне архітектурне
рішення модуля. Спокуса — розпізнавати причину регексом по повідомленню
клієнта, і саме на цьому весь день ламався бот: детермінований шар вгадував
замість того, щоб користуватись фактами, які вже має. Тут навпаки: причину
називає той шар, який її знає достовірно —
`ig_checkout_readiness` знає, що розмір вимкнений; резолвер URL знає, що товар
знято з публікації; карусель знає, що клієнт обрав другу позицію.

Чому агрегати рахуються, а не зберігаються. F-DATA-014 уже показала ціну
дубльованого джерела істини: у `purchases_count`/`total_spent` було два
письменники з різними одиницями. Тому лічильники тертя тут — похідні від
журналу, і розійтися з ним не можуть за побудовою.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

JOURNAL_CONTEXT_KEY = "product_journal"
# Довжина журналу. Достатньо, щоб побачити картину діалогу, і мало, щоб не
# розпухав `sales_context`: він читається на кожному повідомленні.
JOURNAL_LIMIT = 12


class SwitchReason:
    """Чому клієнт пішов із попереднього товару.

    Значення навмисно описують **подію**, а не емоцію: емоцію ми не знаємо, а
    подію знає конкретний шар коду.
    """

    OUT_OF_STOCK = "out_of_stock"          # потрібного розміру/варіанта немає
    NOT_PUBLISHED = "not_published"        # товар знято з публікації
    CUSTOMER_LINK = "customer_link"        # клієнт надіслав посилання на інший товар
    CUSTOMER_CHOICE = "customer_choice"    # клієнт назвав інший товар словами
    PHOTO_PICK = "photo_pick"             # обрав позицію з надісланих фото
    VISION_MATCH = "vision_match"          # розпізнано з фото клієнта
    MANAGER = "manager"                    # менеджер перепривʼязав вручну
    UNKNOWN = "unknown"

    ALL = frozenset({
        OUT_OF_STOCK, NOT_PUBLISHED, CUSTOMER_LINK, CUSTOMER_CHOICE,
        PHOTO_PICK, VISION_MATCH, MANAGER, UNKNOWN,
    })

    # Причини «не змогли продати те, що людина хотіла». Саме вони створюють
    # тертя і саме їх треба рахувати окремо: решта — нормальний вибір.
    FRICTION = frozenset({OUT_OF_STOCK, NOT_PUBLISHED})


_REASON_LABELS = {
    SwitchReason.OUT_OF_STOCK: "потрібного варіанта не було в наявності",
    SwitchReason.NOT_PUBLISHED: "товар знято з продажу",
    SwitchReason.CUSTOMER_LINK: "клієнт надіслав посилання на інший товар",
    SwitchReason.CUSTOMER_CHOICE: "клієнт сам обрав інший товар",
    SwitchReason.PHOTO_PICK: "клієнт обрав із надісланих фото",
    SwitchReason.VISION_MATCH: "розпізнано з фото клієнта",
    SwitchReason.MANAGER: "менеджер змінив товар вручну",
    SwitchReason.UNKNOWN: "причина не зафіксована",
}


@dataclass(frozen=True)
class FrictionSummary:
    """Скільки разів і чому клієнту не вдалося купити те, що він хотів."""

    switches: int = 0
    friction_switches: int = 0
    consecutive_friction: int = 0
    last_reason: str = ""
    last_rejected_title: str = ""
    escalate: bool = False


# Після двох підряд відмов по наявності далі пробувати «ще варіант» — це вже
# не сервіс, а вигадування роботи для клієнта. Два, а не три: третя спроба
# коштує довіри дорожче, ніж одне вибачення й передача менеджеру.
FRICTION_ESCALATION_THRESHOLD = 2


def _entries(client) -> list[dict]:
    context = getattr(client, "sales_context", None)
    if not isinstance(context, dict):
        return []
    raw = context.get(JOURNAL_CONTEXT_KEY)
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def record_product_switch(
    client,
    *,
    from_product_id=None,
    to_product_id=None,
    reason: str = SwitchReason.UNKNOWN,
    from_title: str = "",
    to_title: str = "",
    detail: str = "",
) -> dict | None:
    """Зафіксувати перехід між товарами. Повертає записаний рядок або None.

    Ідемпотентність по сусідньому запису: повторний виклик з тією ж парою
    товарів і причиною не дублює рядок. Реальна зміна товару приходить одним
    шляхом (`pin_product`), але той самий хід може бути перечитаний повторно
    при ретраї webhook, і журнал не має від цього роздуватись.
    """
    if not getattr(client, "pk", None):
        return None
    try:
        from_product_id = int(from_product_id) if from_product_id else None
        to_product_id = int(to_product_id) if to_product_id else None
    except (TypeError, ValueError):
        return None
    if not to_product_id or from_product_id == to_product_id:
        return None
    if reason not in SwitchReason.ALL:
        reason = SwitchReason.UNKNOWN

    from django.utils import timezone

    entry = {
        "at": timezone.now().isoformat(),
        "from_product_id": from_product_id,
        "to_product_id": to_product_id,
        "reason": reason,
        "from_title": str(from_title or "")[:120],
        "to_title": str(to_title or "")[:120],
    }
    if detail:
        entry["detail"] = str(detail)[:200]

    entries = _entries(client)
    if entries:
        last = entries[-1]
        same = (
            last.get("from_product_id") == from_product_id
            and last.get("to_product_id") == to_product_id
            and last.get("reason") == reason
        )
        if same:
            return None
    entries.append(entry)
    entries = entries[-JOURNAL_LIMIT:]

    try:
        context = dict(getattr(client, "sales_context", {}) or {})
        context[JOURNAL_CONTEXT_KEY] = entries
        client.sales_context = context
        client.save(update_fields=["sales_context", "updated_at"])
    except Exception as exc:  # noqa: BLE001 - журнал не має ламати діалог
        logger.warning("ig funnel journal write failed for %s: %r", client.pk, exc)
        return None
    return entry


STOCK_GAP_CONTEXT_KEY = "_stock_gap"


def remember_stock_gap(client, *, product_id, size: str = "", published: bool = True) -> None:
    """Запам'ятати, що на цьому товарі клієнт уперся у відсутність.

    Викликається тим шаром, який справді це знає — розрахунком готовності
    замовлення. Далі, коли товар зміниться, причина переходу візьметься звідси,
    а не з вгадування по тексту. Мітка живе до наступної зміни товару.
    """
    if not getattr(client, "pk", None) or not product_id:
        return
    from django.utils import timezone

    try:
        context = dict(getattr(client, "sales_context", {}) or {})
        context[STOCK_GAP_CONTEXT_KEY] = {
            "product_id": int(product_id),
            "size": str(size or "")[:16],
            "published": bool(published),
            "at": timezone.now().isoformat(),
        }
        client.sales_context = context
        client.save(update_fields=["sales_context", "updated_at"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("ig stock gap mark failed for %s: %r", getattr(client, "pk", None), exc)


def resolve_switch_reason(client, previous_product_id) -> str:
    """Причина переходу, якщо її можна дізнатись із зафіксованих фактів.

    Порожній рядок означає «фактів немає» — тоді причину називає той, хто
    викликав `pin_product`, і ми не вигадуємо за нього.
    """
    context = getattr(client, "sales_context", None)
    if not isinstance(context, dict) or not previous_product_id:
        return ""
    gap = context.get(STOCK_GAP_CONTEXT_KEY)
    if not isinstance(gap, dict):
        return ""
    try:
        if int(gap.get("product_id") or 0) != int(previous_product_id):
            return ""
    except (TypeError, ValueError):
        return ""
    return SwitchReason.NOT_PUBLISHED if not gap.get("published", True) else SwitchReason.OUT_OF_STOCK


def clear_stock_gap(client) -> None:
    """Прибрати мітку відсутності, коли вона більше не актуальна."""
    context = getattr(client, "sales_context", None)
    if not isinstance(context, dict) or STOCK_GAP_CONTEXT_KEY not in context:
        return
    try:
        fresh = dict(context)
        fresh.pop(STOCK_GAP_CONTEXT_KEY, None)
        client.sales_context = fresh
        client.save(update_fields=["sales_context", "updated_at"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("ig stock gap clear failed: %r", exc)


def friction_summary(client) -> FrictionSummary:
    """Порахувати тертя з журналу.

    `consecutive_friction` рахується з кінця й обривається на першій причині,
    яка тертям не є. Це важливо: клієнт, у якого колись не було розміру, а потім
    він спокійно обрав інший товар за смаком, більше не «проблемний». Інакше
    через місяць кожен другий діалог виглядав би як скарга.
    """
    entries = _entries(client)
    if not entries:
        return FrictionSummary()

    friction_total = sum(
        1 for item in entries if str(item.get("reason")) in SwitchReason.FRICTION
    )
    consecutive = 0
    for item in reversed(entries):
        if str(item.get("reason")) in SwitchReason.FRICTION:
            consecutive += 1
        else:
            break
    last = entries[-1]
    return FrictionSummary(
        switches=len(entries),
        friction_switches=friction_total,
        consecutive_friction=consecutive,
        last_reason=str(last.get("reason") or ""),
        last_rejected_title=str(last.get("from_title") or ""),
        escalate=consecutive >= FRICTION_ESCALATION_THRESHOLD,
    )


def journal_prompt_note(client) -> str:
    """Службовий блок для промпта: як клієнт дійшов до поточного товару.

    Свідомо короткий. У промпті вже ~38 000 символів, і сенс цього блоку не в
    повній історії, а в одному факті: чи були відмови по наявності й скільки
    підряд. Порожній журнал не виводиться взагалі, щоб не займати бюджет.
    """
    entries = _entries(client)
    if not entries:
        return ""
    summary = friction_summary(client)
    lines = ["[ІСТОРІЯ ВИБОРУ ТОВАРУ — службове, клієнту не переказуй]"]
    for item in entries[-3:]:
        reason = _REASON_LABELS.get(str(item.get("reason")), str(item.get("reason")))
        source = item.get("from_title") or (
            f"id={item.get('from_product_id')}" if item.get("from_product_id") else "—"
        )
        target = item.get("to_title") or f"id={item.get('to_product_id')}"
        lines.append(f"  {source} → {target}: {reason}")

    if summary.escalate:
        lines.append(
            f"УВАГА: клієнт {summary.consecutive_friction} рази підряд не отримав те, "
            "що хотів, саме через наявність. Це вже не звичайний підбір. "
            "Визнай це своїми словами й коротко вибачся, не виправдовуйся довго; "
            "не пропонуй наступний варіант «навмання» — або назви те, що точно є, "
            "або скажи, що передаєш питання менеджеру, і додай [MANAGER]."
        )
    elif summary.friction_switches:
        lines.append(
            "Клієнт уже стикався з відсутністю потрібного варіанта. Пропонуй лише те, "
            "що є в наявності за каталогом, і не повертайся до товару, який не вийшло "
            "продати, поки клієнт сам про нього не спитає."
        )
    else:
        lines.append(
            "Заміни товару були за вибором клієнта, не через нашу відсутність — "
            "тримайся поточного товару й не згадуй попередні, поки не спитають."
        )
    return "\n".join(lines)
