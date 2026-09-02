"""
ЭА.9 — L3 Deterministic Response Layer

Детерминированные ответы без вызова модели при открытом инциденте провайдера.
Closed list: только исходы, которые доказуемо корректны без модели.

Outcomes:
1. Manager request → confirmation + manager task
4. Greeting/goodbye → short template
5. Everything else → None (escalate to L4)

Skipped (require Э3.7 resolver):
2. Product availability
3. Order status
"""

from dataclasses import dataclass
from typing import Optional
import re


@dataclass(frozen=True)
class DeterministicOutcome:
    """Result of L3 deterministic classification."""
    reply: str
    manager_task_reason: Optional[str] = None


# Versioned texts for deterministic responses
TEXTS = {
    'uk': {
        'manager_request_confirmation': (
            'Зрозуміло, передам менеджеру. '
            'Відповімо, як тільки хтось з команди побачить повідомлення.'
        ),
        'greeting': 'Привіт! Чим можу допомогти?',
        'goodbye': 'Гарного дня! Пишіть, якщо щось знадобиться.',
    },
    'ru': {
        'manager_request_confirmation': (
            'Понятно, передам менеджеру. '
            'Ответим, как только кто-то из команды увидит сообщение.'
        ),
        'greeting': 'Привет! Чем могу помочь?',
        'goodbye': 'Хорошего дня! Пишите, если что-то понадобится.',
    },
    'en': {
        'manager_request_confirmation': (
            'Got it, I will pass this to a manager. '
            'We will reply as soon as someone from the team sees the message.'
        ),
        'greeting': 'Hi! How can I help?',
        'goodbye': 'Have a great day! Write if you need anything.',
    },
}


def _detect_language(text: str) -> str:
    """Detect language from text. Default to 'uk'."""
    # Simple heuristic: Ukrainian uses 'і', Russian uses 'ы'
    if 'і' in text.lower() or any(w in text.lower() for w in ['привіт', 'дякую', 'будь ласка']):
        return 'uk'
    if 'ы' in text.lower() or any(w in text.lower() for w in ['привет', 'спасибо', 'пожалуйста']):
        return 'ru'
    if any(w in text.lower() for w in ['hello', 'thanks', 'please', 'hi']):
        return 'en'
    return 'uk'


def _is_manager_request(text: str) -> bool:
    """Detect request for human manager."""
    patterns = [
        r'\bменеджер',
        r'\bлюдин',
        r'\bоператор',
        r'\bсотрудник',
        r'\bчеловек',
        r'\bmanager\b',
        r'\bhuman\b',
        r'\breal person\b',
    ]
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in patterns)


def _is_greeting(text: str) -> bool:
    """Detect greeting."""
    greetings = [
        'привіт', 'привет', 'здравствуй', 'вітаю',
        'hello', 'hi', 'hey', 'доброго дня', 'добрый день',
    ]
    text_lower = text.lower().strip()
    # Match if text starts with greeting or is just greeting
    return any(text_lower.startswith(g) or text_lower == g for g in greetings)


def _is_goodbye(text: str) -> bool:
    """Detect goodbye."""
    goodbyes = [
        'пока', 'до побачення', 'до свидания', 'прощай',
        'bye', 'goodbye', 'see you', 'дякую', 'спасибо', 'thanks',
    ]
    text_lower = text.lower().strip()
    return any(g in text_lower for g in goodbyes)


def deterministic_outcome(
    text: str,
    client,
    episode,
) -> Optional[DeterministicOutcome]:
    """
    Classify turn and return deterministic outcome if possible.

    Returns None if turn requires model (escalate to L4).

    Args:
        text: Customer message text
        client: IgClient instance
        episode: IgClientDegradationEpisode instance (may be None)

    Returns:
        DeterministicOutcome if deterministic response possible, else None
    """
    lang = _detect_language(text)
    texts = TEXTS.get(lang, TEXTS['uk'])

    # Outcome 1: Manager request
    if _is_manager_request(text):
        return DeterministicOutcome(
            reply=texts['manager_request_confirmation'],
            manager_task_reason='customer_requested_human_agent',
        )

    # Outcome 4: Greeting
    if _is_greeting(text):
        return DeterministicOutcome(reply=texts['greeting'])

    # Outcome 4: Goodbye
    if _is_goodbye(text):
        return DeterministicOutcome(reply=texts['goodbye'])

    # Outcome 5: Everything else → escalate to L4
    return None
