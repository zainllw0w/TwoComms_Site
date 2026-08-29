"""Ждёт ли клиент ответа именно сейчас (ЭБ.1).

**Зачем отдельное понятие.** Техническое извинение оправдано только перед тем,
кто чего-то ждёт. До этого этапа роль «нужен ли этому ходу ответ» играла
`is_low_intent_turn()`, и она отвечала на другой вопрос — «пустая ли реплика».
Два вопроса разошлись на реальном случае: клиент сделал репост истории и отметил
бренд, а получил «Вибачте за технічну затримку». Разбор пути:

* репост приходит вложением без текста → `reaction_or_sticker` = True;
* но перед этим бот задавал вопрос → сработало исключение `_bot_asked_question`,
  написанное для «Добре» после «Який розмір?»;
* исключение сняло весь gate, и ход стал «требующим ответа» → техтекст.

Репост — не ответ на вопрос бота. И, что важнее, никто не делает репост, а потом
смотрит в Direct в ожидании квитанции: **благодарность за репост уместна и через
две минуты, а извинение за задержку — никогда**.

**Три разных признака, которые раньше были одним.**

``waiting``
    Клиент совершил действие, которое по обычной человеческой логике обязывает
    нас ответить, и обязательство ещё открыто. Только это даёт право на
    техническое сообщение.

``substantive_reply_owed``
    Мы должны содержательный ответ — возможно, позже. У репоста это True при
    ``waiting=False``: благодарность нужна, извинение — нет. У реакции 👍 оба
    False: там уместна тишина.

``actively_waiting``
    Клиент уже переспросил или написал повторно, не получив ответа. Это
    единственный случай, когда техническое сообщение уместно **без**
    подтверждённой деградации провайдера: человек явно ждёт и уже нервничает.

Разделение асимметрично по цене ошибки, и это осознанно. Лишняя тишина не стоит
ничего: путь восстановления (`ig_ai_reply_recovery`) доставит настоящий ответ
позже и **без** извинения. Лишнее извинение — это ровно тот спам, из-за которого
этап и появился. Поэтому по умолчанию молчим.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

# Реплики, которыми клиент подтверждает получение и закрывает тему.
_ACK_RE = re.compile(
    r"^(?:добре|добра|ок(?:ей)?|okay|ok|k|гаразд|ясно|зрозуміло|понял|поняла|"
    r"понятно|дякую|дяк|спасибо|спасиб|thanks|thank you|thx|ty|супер|класно|"
    r"класс|норм|нормально|прийняв|принял|зрозумів|зрозуміла|good|nice)"
    r"[\s!.,)👍👌🙏❤️🔥😊🙂]*$",
    re.IGNORECASE | re.UNICODE,
)
# Только эмодзи и пунктуация. Цифры сознательно НЕ включены: «5» может быть
# ответом на вопрос о количестве.
_EMOJI_ONLY_RE = re.compile(r"^(?:(?![\d\w])[\s\W])+$", re.UNICODE)
# Прямые признаки того, что человек уже ждёт ответа и заметил тишину.
_RE_ASK_RE = re.compile(
    r"(?:ну\s*що|ну\s*как|алло|ало|агов|є\s*хтось|есть\s*кто|ти\s*тут|ты\s*там|"
    r"чекаю|жду|ждём|ждем|відповідь|ответьте|відповідайте|hello\?|"
    r"\?\?|уже\s*давно|довго|долго)",
    re.IGNORECASE | re.UNICODE,
)
# Вложения, которые не являются обращением к нам: реакция, стикер, репост
# истории, упоминание в истории, шер поста. Клиент их отправляет «в нашу
# сторону», а не «нам с вопросом».
_NON_REQUEST_MEDIA = frozenset({
    "story_mention",
    "story",
    "story_reply",
    "share",
    "ig_post",
    "ig_reel",
    "reel",
    "reaction",
    "sticker",
    "like",
})


@dataclass(frozen=True)
class ReplyExpectation:
    """Ожидание ответа со стабильным кодом причины (нужен для метрики)."""

    waiting: bool
    substantive_reply_owed: bool
    actively_waiting: bool
    reason: str


def _text(row) -> str:
    return str(getattr(row, "text", "") or "").strip()


def _media_kinds(row) -> set[str]:
    """Типы вложений хода по данным провайдера, а не по догадке.

    `attachment_media` заполняется при захвате медиа и содержит `media_type`
    провайдера. Если его ещё нет (захват не успел), возвращаем пустое множество —
    и тогда решает наличие сырых `attachments`.
    """
    kinds: set[str] = set()
    for item in getattr(row, "attachment_media", None) or []:
        if isinstance(item, dict):
            kind = str(item.get("media_type") or "").strip().lower()
            if kind:
                kinds.add(kind)
    return kinds


def _has_attachment(row) -> bool:
    raw = str(getattr(row, "attachments", "") or "").strip()
    if raw and raw not in {"[]", "{}"}:
        try:
            return bool(json.loads(raw))
        except (TypeError, ValueError):
            return True
    return bool(_media_kinds(row))


def _explicit_request(text: str) -> bool:
    """Сигналы, которые ВСЕГДА обязывают ответить."""
    if "?" in text:
        return True
    from management.services.bot_sales_classifier import (
        CONTACT_HANDOVER_RE,
        DELIVERY_RE,
        OPT_OUT_RE,
        ORDER_STATUS_RE,
        PAYMENT_RE,
        PRICE_RE,
        PRODUCT_RE,
        SIZE_RE,
        SUPPORT_RE,
    )

    return any(
        pattern.search(text)
        for pattern in (
            SUPPORT_RE, PAYMENT_RE, ORDER_STATUS_RE, OPT_OUT_RE, PRICE_RE,
            DELIVERY_RE, PRODUCT_RE, SIZE_RE, CONTACT_HANDOVER_RE,
        )
    )


def _unanswered_customer_messages(row) -> list[str]:
    """Реплики клиента после нашего последнего исходящего, кроме текущей.

    Одна и та же выборка отвечает на два вопроса: «клиент писал повторно, не
    получив ответа» и «был ли среди тех реплик вопрос».
    """
    from management.models import InstagramBotMessage

    client_id = getattr(row, "client_id", None)
    row_id = getattr(row, "pk", None)
    if not client_id or not row_id:
        return []
    last_outgoing = (
        InstagramBotMessage.objects.filter(
            client_id=client_id,
            role__in=(
                InstagramBotMessage.Role.MODEL,
                InstagramBotMessage.Role.MANAGER,
            ),
            id__lt=row_id,
        )
        .order_by("-id")
        .values_list("id", flat=True)
        .first()
    ) or 0
    return [
        str(text or "")
        for text in InstagramBotMessage.objects.filter(
            client_id=client_id,
            role=InstagramBotMessage.Role.USER,
            id__gt=last_outgoing,
            id__lt=row_id,
        )
        .order_by("id")
        .values_list("text", flat=True)[:20]
    ]


def _bot_asked_question(row) -> bool:
    from management.models import InstagramBotMessage

    client_id = getattr(row, "client_id", None)
    row_id = getattr(row, "pk", None)
    if not client_id or not row_id:
        return False
    last_outgoing_text = (
        InstagramBotMessage.objects.filter(
            client_id=client_id,
            role__in=(
                InstagramBotMessage.Role.MODEL,
                InstagramBotMessage.Role.MANAGER,
            ),
            id__lt=row_id,
        )
        .order_by("-id")
        .values_list("text", flat=True)
        .first()
    ) or ""
    return "?" in str(last_outgoing_text)


def classify(row, *, ugc_turn: bool = False, logical_turn_id: str = "") -> ReplyExpectation:
    """Ждёт ли клиент ответа на этот ход — и ждёт ли он его активно.

    Порядок проверок — от самого надёжного признака к самому слабому. Явный
    запрос (вопрос, цена, размер, оплата, «де замовлення», скарга, менеджер)
    сильнее любого признака формы: клиент, который прислал фото и спросил цену,
    ждёт ответа независимо от вложения.
    """
    text = _text(row)
    unanswered = _unanswered_customer_messages(row)
    actively_waiting = bool(
        _RE_ASK_RE.search(text)
        or any(item.strip() for item in unanswered)
    )

    def result(waiting: bool, owed: bool, reason: str) -> ReplyExpectation:
        return ReplyExpectation(
            waiting=waiting,
            substantive_reply_owed=owed,
            actively_waiting=actively_waiting and waiting,
            reason=reason,
        )

    if _explicit_request(text):
        return result(True, True, "explicit_request")

    # Репост/упоминание в истории. Содержательный ответ мы должны — благодарность
    # и разбор изображения, — но клиент его не ждёт, поэтому извинение за
    # задержку здесь вредно в любой момент времени.
    if ugc_turn:
        return result(False, True, "ugc_turn")

    media = _media_kinds(row)
    if not text and _has_attachment(row):
        if media and media <= _NON_REQUEST_MEDIA:
            # Реакция, стикер, шер: ответа никто не ждёт, содержательного долга
            # тоже нет. Тишина здесь — правильный исход.
            return result(False, False, "reaction_only")
        if not media:
            # Медиа ещё не классифицировано провайдером: считаем, что клиент
            # что-то показал и ждёт реакции. Ошибка в эту сторону безопаснее.
            return result(True, True, "media_without_text")
        # Фото/видео/файл: клиент показал нам что-то и ждёт ответа.
        return result(True, True, "media_without_text")

    if text:
        short_ack = len(text) <= 24 and bool(_ACK_RE.match(text))
        emoji_only = len(text) <= 12 and bool(_EMOJI_ONLY_RE.match(text))
        if short_ack or emoji_only:
            # «Добре» после нашего вопроса — это ответ, а не завершение темы:
            # придушив его, мы потеряли бы ход клиента. Исключение действует
            # только для текста и НЕ распространяется на вложения: репост после
            # нашего вопроса ответом не является.
            if _bot_asked_question(row) or any("?" in item for item in unanswered):
                return result(True, True, "answer_to_bot_question")
            return result(False, False, "short_ack" if short_ack else "emoji_only")
        return result(True, True, "customer_message")

    # Ни текста, ни вложения: обычно системный/пустой ход.
    return result(False, False, "empty_turn")


def is_low_intent_text_turn(row, *, logical_turn_id: str = "") -> bool:
    """Совместимость: «пустая реплика», как это понимал `is_low_intent_turn`."""
    expectation = classify(row, logical_turn_id=logical_turn_id)
    return expectation.reason in {"short_ack", "emoji_only", "reaction_only"}
