"""Одне вибачення на логічний хід, а не одне на кожен шар коду (ЭА.6).

`_ensure_recovery_apology()` додавав локалізований префікс-вибачення, якщо в
тексті не було вузького точного стему. Prompt відновлення ОКРЕМО вимагав почати
з короткого вибачення. Результат у production (рядок 2738):

    «Вибачте за технічну затримку. Вибачте за затримку з відповіддю! …»

Модель вибачилась сама, а код додав друге вибачення, бо не впізнав інше
формулювання. Тут зібрана вся семантика вибачення в одному місці: і розпізнавання,
і зняття, і додавання. Правило пріоритету:

* holding уже доставлений → recovery НЕ містить вибачення взагалі
  (провідне вибачення знімається з draft, своє не додається);
* holding не доставлявся → допускається РІВНО ОДНЕ вибачення (модельне АБО
  додане, не обидва).
"""
from __future__ import annotations

import re
import unicodedata

APOLOGY_UK = "Вибачте за технічну затримку."
APOLOGY_RU = "Извините за техническую задержку."
APOLOGY_EN = "Sorry for the technical delay."

APOLOGY_BY_LANGUAGE = {
    "uk": APOLOGY_UK,
    "ru": APOLOGY_RU,
    "en": APOLOGY_EN,
}

# Семантичні варіанти вибачення: «вибачте», «перепрошую», «просимо вибачення»,
# «извините», «прошу прощения», «sorry», «apologies», «my apologies», «pardon».
_APOLOGY_OPENER = (
    r"(?:вибач\w*|перепрош\w*|прос(?:имо|ю)\s+вибачен\w*|"
    r"извин\w*|прош(?:у|аю)\s+прощен\w*|приноси\w*\s+извинен\w*|"
    r"sorry|apolog\w*|pardon)"
)
# Слова про очікування: затримка, очікування, чекати, задержка, ожидание, delay,
# waiting. Самé слово «затримка» БЕЗ вибачення не робить текст вибаченням —
# інакше змістовна відповідь «є затримка на складі» різалась би як вибачення.
_DELAY_WORD = (
    r"(?:затримк\w*|затримал\w*|очікув\w*|чекат\w*|чекан\w*|"
    r"задержк\w*|задержал\w*|ожидан\w*|"
    r"delay\w*|wait\w*|late|holdup|hold-up)"
)

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")
_LEADING_NOISE_RE = re.compile(r"^[\s\W\d]{0,12}", re.UNICODE)


def _normalize(text: str) -> str:
    """Нормалізація перед перевіркою: регістр, пунктуація, пробіли, емодзі."""
    folded = unicodedata.normalize("NFKC", str(text or "")).casefold()
    folded = folded.replace("’", "'").replace("ʼ", "'")
    return re.sub(r"\s+", " ", folded).strip()


def _opener_is_leading(normalized_sentence: str) -> bool:
    """Вибачення має стояти на початку речення, а не будь-де в тексті."""
    head = _LEADING_NOISE_RE.sub("", normalized_sentence)
    words = head.split(" ")[:3]
    return bool(re.match(rf"^{_APOLOGY_OPENER}", " ".join(words) or ""))


def is_apology_sentence(sentence: str) -> bool:
    normalized = _normalize(sentence)
    if not normalized:
        return False
    if not _opener_is_leading(normalized):
        return False
    if re.search(_DELAY_WORD, normalized):
        return True
    # Коротке самостійне вибачення без слова про затримку теж є вибаченням.
    return len(normalized.split(" ")) <= 6


def contains_apology(text: str) -> bool:
    """Чи є вибачення на початку тексту (перші два речення)."""
    sentences = _SENTENCE_SPLIT_RE.split(str(text or "").strip())
    return any(is_apology_sentence(sentence) for sentence in sentences[:2])


def count_apologies(text: str) -> int:
    sentences = _SENTENCE_SPLIT_RE.split(str(text or "").strip())
    return sum(1 for sentence in sentences if is_apology_sentence(sentence))


def strip_leading_apology(text: str) -> str:
    """Зняти провідні вибачення, не перетворюючи відповідь на обрубок.

    Якщо після зняття не залишається змістовного тексту, повертається
    оригінал: краще одне вибачення, ніж порожнє повідомлення клієнту.
    """
    clean = str(text or "").strip()
    if not clean:
        return ""
    sentences = _SENTENCE_SPLIT_RE.split(clean)
    index = 0
    while index < len(sentences) and is_apology_sentence(sentences[index]):
        index += 1
    if not index:
        return clean
    remainder = " ".join(part.strip() for part in sentences[index:]).strip()
    if len(remainder) < 12:
        # Вибачення в середині першого речення: спробувати зняти лише зачин,
        # а не все речення, щоб не втратити зміст.
        trimmed = _strip_inline_apology(clean)
        return trimmed if len(trimmed) >= 12 else clean
    return remainder


_INLINE_APOLOGY_RE = re.compile(
    rf"^[\s\W\d]{{0,12}}{_APOLOGY_OPENER}(?:[^.!?…]{{0,60}}?{_DELAY_WORD})?[\s,;:!—-]*",
    re.I | re.UNICODE,
)


def _strip_inline_apology(text: str) -> str:
    stripped = _INLINE_APOLOGY_RE.sub("", str(text or "").strip(), count=1).strip()
    if not stripped:
        return str(text or "").strip()
    return stripped[0].upper() + stripped[1:] if stripped[:1].islower() else stripped


def apply_apology_policy(
    draft: str,
    *,
    language: str = "uk",
    apology_already_delivered: bool,
) -> tuple[str, int]:
    """Привести draft до правила «сума вибачень у ході ≤ 1».

    Повертає (текст, число вибачень у ЦЬОМУ тексті).
    """
    clean = str(draft or "").strip()
    if not clean:
        return "", 0
    if apology_already_delivered:
        # holding уже витратив єдине вибачення ходу.
        return strip_leading_apology(clean), 0
    if contains_apology(clean):
        # Модель вибачилась сама — друге вибачення не додаємо. Якщо вибачень
        # кілька, залишаємо одне.
        if count_apologies(clean) > 1:
            without = strip_leading_apology(clean)
            prefix = APOLOGY_BY_LANGUAGE.get(language, APOLOGY_UK)
            return f"{prefix} {without}".strip(), 1
        return clean, 1
    prefix = APOLOGY_BY_LANGUAGE.get(language, APOLOGY_UK)
    return f"{prefix} {clean}".strip(), 1
