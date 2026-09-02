"""Тесты для детерминированного уровня L3 (ЭА.9)."""
import pytest
from unittest.mock import Mock

from management.services.ig_deterministic_l3 import (
    deterministic_outcome,
    DeterministicOutcome,
    L3_TEXT_VERSION,
)


@pytest.fixture
def mock_client_uk():
    """Клиент с украинским языком."""
    client = Mock()
    client.lang = "uk"
    client.igsid = "12345"
    return client


@pytest.fixture
def mock_client_ru():
    """Клиент с русским языком."""
    client = Mock()
    client.lang = "ru"
    client.igsid = "67890"
    return client


@pytest.fixture
def mock_client_en():
    """Клиент с английским языком."""
    client = Mock()
    client.lang = "en"
    client.igsid = "11111"
    return client


@pytest.fixture
def mock_episode_open():
    """Открытый эпизод (не terminal)."""
    episode = Mock()
    episode.is_terminal = False
    episode.state = "INCIDENT"
    return episode


@pytest.fixture
def mock_episode_terminal():
    """Закрытый эпизод (terminal)."""
    episode = Mock()
    episode.is_terminal = True
    episode.state = "RECOVERED"
    return episode


class TestManagerRequest:
    """Тесты для исхода 1: запрос менеджера."""

    def test_manager_request_uk_explicit(self, mock_client_uk, mock_episode_open):
        """UK: явный запрос менеджера."""
        outcome = deterministic_outcome("Хочу поговорити з менеджером", mock_client_uk, mock_episode_open)

        assert outcome is not None
        assert isinstance(outcome, DeterministicOutcome)
        assert "менеджеру" in outcome.reply.lower()
        assert outcome.manager_task_reason is not None
        assert "Client requested manager" in outcome.manager_task_reason
        assert outcome.outcome_code == "manager_request"

    def test_manager_request_ru_explicit(self, mock_client_ru, mock_episode_open):
        """RU: явный запрос менеджера."""
        outcome = deterministic_outcome("Нужен менеджер", mock_client_ru, mock_episode_open)

        assert outcome is not None
        assert "менеджеру" in outcome.reply.lower()
        assert outcome.manager_task_reason is not None
        assert outcome.outcome_code == "manager_request"

    def test_manager_request_en_explicit(self, mock_client_en, mock_episode_open):
        """EN: явный запрос менеджера."""
        outcome = deterministic_outcome("I need to talk to a manager", mock_client_en, mock_episode_open)

        assert outcome is not None
        assert "manager" in outcome.reply.lower()
        assert outcome.manager_task_reason is not None
        assert outcome.outcome_code == "manager_request"

    def test_manager_request_operator_uk(self, mock_client_uk, mock_episode_open):
        """UK: запрос оператора."""
        outcome = deterministic_outcome("Дайте оператора", mock_client_uk, mock_episode_open)

        assert outcome is not None
        assert outcome.manager_task_reason is not None
        assert outcome.outcome_code == "manager_request"

    def test_manager_request_human_en(self, mock_client_en, mock_episode_open):
        """EN: запрос человека."""
        outcome = deterministic_outcome("I want to talk to a real person", mock_client_en, mock_episode_open)

        assert outcome is not None
        assert outcome.manager_task_reason is not None
        assert outcome.outcome_code == "manager_request"


class TestGreeting:
    """Тесты для исхода 4: приветствие/прощание."""

    def test_greeting_uk_hello(self, mock_client_uk, mock_episode_open):
        """UK: приветствие."""
        outcome = deterministic_outcome("Привіт", mock_client_uk, mock_episode_open)

        assert outcome is not None
        assert isinstance(outcome, DeterministicOutcome)
        assert "привіт" in outcome.reply.lower() or "допомогти" in outcome.reply.lower()
        assert outcome.manager_task_reason is None
        assert outcome.outcome_code == "greeting"

    def test_greeting_ru_hello(self, mock_client_ru, mock_episode_open):
        """RU: приветствие."""
        outcome = deterministic_outcome("Привет", mock_client_ru, mock_episode_open)

        assert outcome is not None
        assert "привет" in outcome.reply.lower() or "помочь" in outcome.reply.lower()
        assert outcome.manager_task_reason is None
        assert outcome.outcome_code == "greeting"

    def test_greeting_en_hello(self, mock_client_en, mock_episode_open):
        """EN: приветствие."""
        outcome = deterministic_outcome("Hi", mock_client_en, mock_episode_open)

        assert outcome is not None
        assert "hi" in outcome.reply.lower() or "help" in outcome.reply.lower()
        assert outcome.manager_task_reason is None
        assert outcome.outcome_code == "greeting"

    def test_goodbye_uk_thanks(self, mock_client_uk, mock_episode_open):
        """UK: благодарность."""
        outcome = deterministic_outcome("Дякую", mock_client_uk, mock_episode_open)

        assert outcome is not None
        assert "дякую" in outcome.reply.lower() or "гарного" in outcome.reply.lower()
        assert outcome.manager_task_reason is None
        assert outcome.outcome_code == "goodbye"

    def test_goodbye_ru_thanks(self, mock_client_ru, mock_episode_open):
        """RU: благодарность."""
        outcome = deterministic_outcome("Спасибо", mock_client_ru, mock_episode_open)

        assert outcome is not None
        assert "спасибо" in outcome.reply.lower() or "хорошего" in outcome.reply.lower()
        assert outcome.manager_task_reason is None
        assert outcome.outcome_code == "goodbye"

    def test_goodbye_en_thanks(self, mock_client_en, mock_episode_open):
        """EN: благодарность."""
        outcome = deterministic_outcome("Thanks", mock_client_en, mock_episode_open)

        assert outcome is not None
        assert "thanks" in outcome.reply.lower() or "have a" in outcome.reply.lower()
        assert outcome.manager_task_reason is None
        assert outcome.outcome_code == "goodbye"

    def test_goodbye_uk_bye(self, mock_client_uk, mock_episode_open):
        """UK: прощание."""
        outcome = deterministic_outcome("До побачення", mock_client_uk, mock_episode_open)

        assert outcome is not None
        assert outcome.manager_task_reason is None
        assert outcome.outcome_code == "goodbye"


class TestFallback:
    """Тесты для исхода 5: эскалация на L4."""

    def test_product_question_no_l3(self, mock_client_uk, mock_episode_open):
        """Вопрос про товар → None (нужен Э3.7)."""
        outcome = deterministic_outcome("Скільки коштує футболка?", mock_client_uk, mock_episode_open)

        assert outcome is None

    def test_order_status_no_l3(self, mock_client_uk, mock_episode_open):
        """Вопрос про заказ → None (нужен Э3.7)."""
        outcome = deterministic_outcome("Де мій заказ?", mock_client_uk, mock_episode_open)

        assert outcome is None

    def test_complex_question_no_l3(self, mock_client_uk, mock_episode_open):
        """Сложный вопрос → None."""
        outcome = deterministic_outcome(
            "Чи можу я замовити дві футболки з різних розмірів?",
            mock_client_uk,
            mock_episode_open
        )

        assert outcome is None

    def test_payment_question_no_l3(self, mock_client_ru, mock_episode_open):
        """Вопрос про оплату → None."""
        outcome = deterministic_outcome("Как оплатить?", mock_client_ru, mock_episode_open)

        assert outcome is None


class TestTerminalEpisode:
    """Тесты для проверки terminal episode."""

    def test_terminal_episode_returns_none(self, mock_client_uk, mock_episode_terminal):
        """Terminal episode → всегда None."""
        outcome = deterministic_outcome("Привіт", mock_client_uk, mock_episode_terminal)
        assert outcome is None

    def test_terminal_episode_manager_request_returns_none(self, mock_client_uk, mock_episode_terminal):
        """Terminal episode + запрос менеджера → None."""
        outcome = deterministic_outcome("Хочу менеджера", mock_client_uk, mock_episode_terminal)
        assert outcome is None


class TestLanguageFallback:
    """Тесты для fallback языка."""

    def test_unknown_lang_fallback_uk(self, mock_episode_open):
        """Неизвестный язык → fallback uk."""
        client = Mock()
        client.lang = "de"
        client.igsid = "99999"

        outcome = deterministic_outcome("Привіт", client, mock_episode_open)
        # Должно работать как uk
        assert outcome is not None
        assert outcome.outcome_code == "greeting"

    def test_none_lang_fallback_uk(self, mock_episode_open):
        """None язык → fallback uk."""
        client = Mock()
        client.lang = None
        client.igsid = "88888"

        outcome = deterministic_outcome("Привіт", client, mock_episode_open)
        assert outcome is not None
        assert outcome.outcome_code == "greeting"


class TestNoForbiddenAssertions:
    """Тест на запрещённые побочные утверждения (по образцу ADD-AGENT-007)."""

    def test_no_product_claims_in_responses(self, mock_client_uk, mock_episode_open):
        """Ни один ответ не утверждает факты про товары без DB."""
        test_cases = [
            "Привіт",
            "Дякую",
            "Хочу менеджера",
            "До побачення",
        ]

        forbidden_keywords = [
            "в наявності", "є в наявності", "немає", "відсутній",
            "в наличии", "есть в наличии", "нет", "отсутствует",
            "in stock", "out of stock", "available", "unavailable",
            "ціна", "цена", "price", "коштує", "стоит", "costs",
        ]

        for text in test_cases:
            outcome = deterministic_outcome(text, mock_client_uk, mock_episode_open)
            if outcome is not None:
                reply_lower = outcome.reply.lower()
                for keyword in forbidden_keywords:
                    assert keyword not in reply_lower, \
                        f"Response contains forbidden product claim: {keyword} in {outcome.reply}"

    def test_no_order_claims_in_responses(self, mock_client_ru, mock_episode_open):
        """Ни один ответ не утверждает факты про заказы без DB."""
        test_cases = [
            "Привет",
            "Спасибо",
            "Нужен менеджер",
        ]

        forbidden_keywords = [
            "замовлення", "заказ", "order",
            "доставлен", "отправлен", "в пути",
            "delivered", "shipped", "in transit",
            "оплачен", "не оплачен", "paid", "unpaid",
        ]

        for text in test_cases:
            outcome = deterministic_outcome(text, mock_client_ru, mock_episode_open)
            if outcome is not None:
                reply_lower = outcome.reply.lower()
                for keyword in forbidden_keywords:
                    assert keyword not in reply_lower, \
                        f"Response contains forbidden order claim: {keyword} in {outcome.reply}"


class TestTextVersion:
    """Тест на версионирование текстов."""

    def test_text_version_exists(self):
        """Версия текстов задана."""
        assert L3_TEXT_VERSION is not None
        assert isinstance(L3_TEXT_VERSION, str)
        assert len(L3_TEXT_VERSION) > 0

    def test_text_version_format(self):
        """Версия в формате YYYY-MM-DD.N."""
        import re
        assert re.match(r'\d{4}-\d{2}-\d{2}\.\d+', L3_TEXT_VERSION), \
            f"Version format incorrect: {L3_TEXT_VERSION}"


class TestManagerTaskReason:
    """Тесты для manager_task_reason."""

    def test_manager_task_reason_contains_text(self, mock_client_uk, mock_episode_open):
        """manager_task_reason содержит текст клиента."""
        text = "Хочу поговорити з менеджером про заказ"
        outcome = deterministic_outcome(text, mock_client_uk, mock_episode_open)

        assert outcome is not None
        assert outcome.manager_task_reason is not None
        assert "Client requested manager" in outcome.manager_task_reason
        assert text[:100] in outcome.manager_task_reason

    def test_manager_task_reason_truncates_long_text(self, mock_client_uk, mock_episode_open):
        """manager_task_reason обрезает длинный текст."""
        long_text = "Хочу менеджера " + "x" * 200
        outcome = deterministic_outcome(long_text, mock_client_uk, mock_episode_open)

        assert outcome is not None
        assert outcome.manager_task_reason is not None
        assert len(outcome.manager_task_reason) < len(long_text) + 100  # reason не должен быть огромным
