"""План доставки відповіді: явний исход замість молчаливого усечення (Э2.1).

`_split_for_send(text, limit=950, max_chunks=4)` завершував цикл по вичерпанню
ліміту чанків і повертав тільки створені чанки — **залишок відкидався без
слідів**, а `send_text()` рахував це повною доставкою. Арифметика: 4×950 = 3800
байт ≈ 1900 кириличних символів, тоді як `ig_response_control` дозволяє 4000
символів. Розрив двократний.

Що втрачається першим — **кінець** відповіді. А структура відповіді ставить у
кінець найважливіше для дії: посилання, суму, питання-CTA. Тобто усічення
систематично з'їдало саме те, що рухає угоду, і при цьому звітувало `sent`.

Тому тут два правила:

1. Ніякого молчаливого усічення. Исход завжди явний: `complete`,
   `intentionally_summarized` або `truncated_before_send`.
2. Якщо текст не влазить — стискаємо ДЕТЕРМІНОВАНО, зберігаючи хвіст
   (посилання, суми, CTA), а не відрізаємо його.

Окремо: URL ніколи не розривається. Стара межа різу відкочувалась до пробілу,
але умова `brk > int(cut * 0.5)` допускала жорсткий розріз, якщо межі в
останній половині чанка не було. Довгий URL без пробілів — рівно такий випадок,
а бита ссылка виглядає як несправність магазину.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

DEFAULT_LIMIT = 950
DEFAULT_MAX_CHUNKS = 4

COMPLETE = "complete"
SUMMARIZED = "intentionally_summarized"
TRUNCATED = "truncated_before_send"

_URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>]+", re.IGNORECASE)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+|\n+")
# Речення, які несуть дію: посилання, сума, номер замовлення, ТТН, розмір.
_ACTIONABLE_RE = re.compile(
    r"(?:https?://|www\.|\d{3,}|\bгрн\b|\bUAH\b|\bTWC[A-Z0-9-]{4,}\b|\?)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DeliveryPlan:
    """Точний план відправки, побудований ДО provider I/O."""

    chunks: tuple
    outcome: str
    original_bytes: int
    planned_bytes: int
    dropped_bytes: int
    reason: str = ""

    @property
    def deliverable(self) -> bool:
        """Чи можна взагалі відправляти цей план клієнту."""
        return bool(self.chunks) and self.outcome != TRUNCATED

    @property
    def complete(self) -> bool:
        return self.outcome == COMPLETE


def _byte_length(value: str) -> int:
    return len(value.encode("utf-8"))


def _atoms(text: str) -> list:
    """Розбити текст на атоми, де URL — неподільний атом.

    Пакування по атомах — єдиний спосіб гарантувати, що межа чанка ніколи не
    пройде посередині посилання.
    """
    atoms: list = []
    cursor = 0
    for match in _URL_RE.finditer(text):
        before = text[cursor:match.start()]
        if before:
            atoms.extend(_whitespace_atoms(before))
        atoms.append(match.group(0))
        cursor = match.end()
    tail = text[cursor:]
    if tail:
        atoms.extend(_whitespace_atoms(tail))
    return atoms


def _whitespace_atoms(text: str) -> list:
    parts = re.split(r"(\s+)", text)
    return [part for part in parts if part]


def split_url_safe(
    text: str,
    *,
    limit: int = DEFAULT_LIMIT,
    max_chunks: int = DEFAULT_MAX_CHUNKS,
) -> tuple:
    """Спакувати текст у чанки ≤limit байт, не розриваючи URL.

    Повертає (чанки, залишок). Непорожній залишок означає, що текст не влазить —
    викликаючий шар зобов'язаний зробити з цього явний исход, а не проігнорувати.
    """
    clean = (text or "").strip()
    if not clean:
        return (), ""
    atoms = _atoms(clean)
    chunks: list = []
    current = ""
    index = 0
    while index < len(atoms) and len(chunks) < max_chunks:
        atom = atoms[index]
        candidate = current + atom
        if _byte_length(candidate.strip()) <= limit:
            current = candidate
            index += 1
            continue
        if current.strip():
            chunks.append(current.strip())
            current = ""
            continue
        # Один атом сам довший за ліміт. Це або гігантський URL (розривати
        # заборонено), або суцільне слово без пробілів.
        if _URL_RE.fullmatch(atom.strip()):
            return tuple(chunks), "".join(atoms[index:])
        hard = _hard_cut(atom, limit)
        chunks.append(hard.strip())
        atoms[index] = atom[len(hard):]
        if not atoms[index]:
            index += 1
    if current.strip() and len(chunks) < max_chunks:
        chunks.append(current.strip())
        current = ""
    rest = (current + "".join(atoms[index:])).strip()
    return tuple(chunk for chunk in chunks if chunk), rest


def _hard_cut(atom: str, limit: int) -> str:
    cut = min(len(atom), limit)
    while cut > 0 and _byte_length(atom[:cut]) > limit:
        cut -= 1
    return atom[:cut] or atom[:1]


def _normalize(sentence: str) -> str:
    folded = unicodedata.normalize("NFKC", sentence).casefold()
    return re.sub(r"[\s\W]+", " ", folded).strip()


def compact_for_delivery(text: str, *, limit: int, max_chunks: int) -> tuple:
    """Детерміноване стискання, що зберігає хвіст відповіді.

    Порядок: зняти дубльовані речення → лишити перше речення (контекст) і
    максимум хвостових речень, що влазять (посилання, сума, CTA живуть у кінці).
    Повертає (текст, чи стало коротше).
    """
    sentences = [part.strip() for part in _SENTENCE_SPLIT_RE.split(text) if part.strip()]
    if len(sentences) <= 1:
        return text, False

    seen: set = set()
    deduped: list = []
    for sentence in sentences:
        key = _normalize(sentence)
        if key and key in seen:
            continue
        seen.add(key)
        deduped.append(sentence)
    candidate = " ".join(deduped)
    if not split_url_safe(candidate, limit=limit, max_chunks=max_chunks)[1]:
        return candidate, len(deduped) < len(sentences)

    head = deduped[0]
    tail: list = []
    for sentence in reversed(deduped[1:]):
        attempt = " ".join([head, *reversed([*tail, sentence])])
        if split_url_safe(attempt, limit=limit, max_chunks=max_chunks)[1]:
            # Речення з дією не викидаємо тихо: якщо воно не влазить разом з
            # головою, краще пожертвувати головою, ніж посиланням чи сумою.
            if _ACTIONABLE_RE.search(sentence) and not tail:
                head = ""
                continue
            break
        tail.append(sentence)
    kept = [part for part in (head, *reversed(tail)) if part]
    return " ".join(kept), True


def build_delivery_plan(
    text: str,
    *,
    limit: int = DEFAULT_LIMIT,
    max_chunks: int = DEFAULT_MAX_CHUNKS,
) -> DeliveryPlan:
    """Порахувати точний план доставки з явним исходом."""
    clean = (text or "").strip()
    original_bytes = _byte_length(clean)
    if not clean:
        return DeliveryPlan((), TRUNCATED, 0, 0, 0, "empty_reply")

    chunks, rest = split_url_safe(clean, limit=limit, max_chunks=max_chunks)
    if not rest:
        planned = sum(_byte_length(chunk) for chunk in chunks)
        return DeliveryPlan(chunks, COMPLETE, original_bytes, planned, 0)

    compacted, changed = compact_for_delivery(clean, limit=limit, max_chunks=max_chunks)
    if changed:
        chunks, rest = split_url_safe(compacted, limit=limit, max_chunks=max_chunks)
        if not rest and chunks:
            planned = sum(_byte_length(chunk) for chunk in chunks)
            return DeliveryPlan(
                chunks,
                SUMMARIZED,
                original_bytes,
                planned,
                max(0, original_bytes - _byte_length(compacted)),
                "compacted_preserving_tail",
            )

    # Сжата форма теж не влазить. Це НЕ доставка: викликаючий шар зобов'язаний
    # передати менеджеру або надіслати карточку, але не половину фрази.
    planned = sum(_byte_length(chunk) for chunk in chunks)
    return DeliveryPlan(
        chunks,
        TRUNCATED,
        original_bytes,
        planned,
        max(0, original_bytes - planned),
        "reply_exceeds_transport_budget",
    )
