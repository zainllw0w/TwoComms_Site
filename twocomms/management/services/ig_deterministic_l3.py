"""Детерминированный уровень L3 для Instagram-бота (ЭА.9).

Между «модель ответила» и «извините за задержку» необходим промежуточный уровень для
ходов, которые не требуют модели. Это **не** мини-бот и не rule-based диалог, а узкий
набор исходов, каждый из которых доказуемо корректен без модели.

Честная граница:
- Исход 1: запрос менеджера → подтверждение + manager case
- Исход 4: приветствие/прощание → шаблонный ответ
- Исход 5: все остальное → None (эскалация на L4)
- Исходы 2 и 3 (каталог, заказы) требуют Э3.7 resolver и пока не включены

Вызывается только при открытом инциденте. При успехе закрывает ход: episode → RECOVERED.
"""
from dataclasses import dataclass
from typing import Optional
import re

from management.ig_bot_models import IgClient


# Версия текстов L3 — инкремент при изменении любого шаблона
L3_TEXT_VERSION = "2026-09-02.1"


@dataclass(frozen=True)
class DeterministicOutcome:
    """Результат детерминированного L3-ответа."""

    reply: str  # Текст ответа клиенту
    manager_task_reason: Optional[str] = None  # Если не None — создать manager task
    outcome_code: str = ""  # Код исхода для телеметрии


# Паттерны для определения интентов (fail-closed: только очевидные случаи)
_MANAGER_REQUEST_PATTERNS_UK = [
    r'\bменеджер',
    r'\bз\s*менеджером',
    r'\bоператор',
    r'\bз\s*людиною',
    r'\bживої?\s+людин',
    r'\bпередайте\s+(менеджеру|оператору)',
]

_MANAGER_REQUEST_PATTERNS_RU = [
    r'\bменеджер',
    r'\bс\s*менеджером',
    r'\bоператор',
    r'\bс\s*человеком',
    r'\bживого?\s+человек',
    r'\bпередайте\s+(менеджеру|оператору)',
]

_MANAGER_REQUEST_PATTERNS_EN = [
    r'\bmanager\b',
    r'\boperator\b',
    r'\bhuman\b',
    r'\breal\s+person',
    r'\btalk\s+to\s+(manager|operator|human)',
]

_GREETING_PATTERNS_UK = [
    r'^(привіт|доброго?\s+(дня|ранку|вечора)|здрастуйте|вітаю)[\s!.?]*$',
    r'^(дякую|спасибі|дяка)[\s!.?]*$',
    r'^(до\s*побачення|бувай|пока)[\s!.?]*$',
]

_GREETING_PATTERNS_RU = [
    r'^(привет|доброго?\s+(дня|утра|вечера)|здравствуйте)[\s!.?]*$',
    r'^(спасибо|благодарю)[\s!.?]*$',
    r'^(до\s*свидания|пока)[\s!.?]*$',
]

_GREETING_PATTERNS_EN = [
    r'^(hi|hello|hey|good\s+(morning|afternoon|evening))[\s!.?]*$',
    r'^(thanks?|thank\s+you)[\s!.?]*$',
    r'^(bye|goodbye|see\s+you)[\s!.?]*$',
]


def _normalize_text(text: str) -> str:
    """Нормализация для pattern matching: lowercase, лишние пробелы."""
    return re.sub(r'\s+', ' ', text.lower().strip())


def _match_any_pattern(text: str, patterns: list[str]) -> bool:
    """Проверка текста на совпадение с любым паттерном."""
    normalized = _normalize_text(text)
    return any(re.search(pattern, normalized, re.IGNORECASE) for pattern in patterns)


def _detect_manager_request(text: str, lang: str) -> bool:
    """Детектор запиту менеджера (fail-closed: тільки явні згадки).

    Намір шукається за паттернами ВСІХ мов, а не лише мови з профілю клієнта.
    Причина конкретна: `client.lang` — це мова, якою ми ВІДПОВІДАЄМО, і вона
    береться з попередніх ходів або з профілю. Клієнт пише тією мовою, якою
    хоче, незалежно від цього значення. Якщо звіряти намір лише з мовою профілю,
    то клієнт із `lang="en"`, який написав «менеджер», не отримає L3 взагалі —
    саме той випадок, для якого L3 і потрібен.
    """
    return _match_any_pattern(
        text,
        _MANAGER_REQUEST_PATTERNS_UK
        + _MANAGER_REQUEST_PATTERNS_RU
        + _MANAGER_REQUEST_PATTERNS_EN,
    )


def _detect_greeting(text: str, lang: str) -> bool:
    """Детектор привітання/прощання (fail-closed: тільки короткі шаблони).

    Паттерни прив'язані до ^ і $, тому «Привіт, а є розмір M?» приві­танням не
    вважається — це питання, і воно мусить піти на L4. Мова, як і у
    `_detect_manager_request`, не обмежує пошук наміру.
    """
    return _match_any_pattern(
        text,
        _GREETING_PATTERNS_UK + _GREETING_PATTERNS_RU + _GREETING_PATTERNS_EN,
    )


# Версионированные тексты ответов
_TEMPLATES = {
    "manager_request": {
        "uk": "Зрозуміло, передаю запит менеджеру. Відповідь надійде найближчим часом.",
        "ru": "Понятно, передаю запрос менеджеру. Ответ поступит в ближайшее время.",
        "en": "Understood, forwarding your request to a manager. You'll receive a response shortly.",
    },
    "greeting": {
        "uk": "Привіт! Чим можу допомогти?",
        "ru": "Привет! Чем могу помочь?",
        "en": "Hi! How can I help you?",
    },
    "goodbye": {
        "uk": "Дякую за звернення! Гарного дня!",
        "ru": "Спасибо за обращение! Хорошего дня!",
        "en": "Thanks for reaching out! Have a great day!",
    },
}


def deterministic_outcome(
    text: str,
    client: IgClient,
    episode: Optional[object] = None,
) -> Optional[DeterministicOutcome]:
    """Определить детерминированный исход для текста клиента.

    Вызывается только при открытом инциденте (episode существует и не terminal).
    Возвращает None если детерминированный ответ невозможен → эскалация на L4.

    Args:
        text: Текст сообщения клиента
        client: IgClient instance
        episode: IgClientDegradationEpisode (опционально, для проверки)

    Returns:
        DeterministicOutcome если ответ возможен без модели, иначе None
    """
    if episode is not None and hasattr(episode, 'is_terminal'):
        if episode.is_terminal:
            return None

    lang = getattr(client, 'lang', 'uk') or 'uk'
    if lang not in ('uk', 'ru', 'en'):
        lang = 'uk'

    # Исход 1: запрос менеджера
    if _detect_manager_request(text, lang):
        reply = _TEMPLATES["manager_request"].get(lang, _TEMPLATES["manager_request"]["uk"])
        return DeterministicOutcome(
            reply=reply,
            manager_task_reason=f"Client requested manager (L3): {text[:100]}",
            outcome_code="manager_request",
        )

    # Исход 4: приветствие/прощание
    if _detect_greeting(text, lang):
        normalized = _normalize_text(text)
        is_goodbye = any(word in normalized for word in [
            'дякую', 'спасибо', 'thanks', 'thank',
            'побачення', 'свидания', 'goodbye', 'bye', 'пока', 'бувай'
        ])

        template_key = "goodbye" if is_goodbye else "greeting"
        reply = _TEMPLATES[template_key].get(lang, _TEMPLATES[template_key]["uk"])
        return DeterministicOutcome(
            reply=reply,
            manager_task_reason=None,
            outcome_code=template_key,
        )

    # Исход 5: все остальное → None (эскалация на L4)
    return None
