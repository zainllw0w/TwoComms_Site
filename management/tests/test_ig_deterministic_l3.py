"""
Tests for ЭА.9 L3 Deterministic Response Layer
"""

import pytest
from unittest.mock import Mock
from management.services.ig_deterministic_l3 import (
    deterministic_outcome,
    DeterministicOutcome,
    _is_manager_request,
    _is_greeting,
    _is_goodbye,
    _detect_language,
)


class TestLanguageDetection:
    """Test language detection."""

    def test_detect_ukrainian(self):
        assert _detect_language("Привіт, як справи?") == "uk"
        assert _detect_language("Дякую за допомогу") == "uk"

    def test_detect_russian(self):
        assert _detect_language("Привет, как дела?") == "ru"
        assert _detect_language("Спасибо за помощь") == "ru"

    def test_detect_english(self):
        assert _detect_language("Hello, how are you?") == "en"
        assert _detect_language("Thanks for help") == "en"

    def test_default_to_ukrainian(self):
        assert _detect_language("Незрозумілий текст") == "uk"


class TestPatternMatching:
    """Test pattern detection functions."""

    def test_manager_request_ukrainian(self):
        assert _is_manager_request("Хочу поговорити з менеджером")
        assert _is_manager_request("Передайте людині")
        assert _is_manager_request("Зв'яжіть з оператором")

    def test_manager_request_russian(self):
        assert _is_manager_request("Хочу поговорить с менеджером")
        assert _is_manager_request("Передайте человеку")
        assert _is_manager_request("Свяжите с оператором")

    def test_manager_request_english(self):
        assert _is_manager_request("I want to talk to a manager")
        assert _is_manager_request("Connect me to a human")
        assert _is_manager_request("Real person please")

    def test_not_manager_request(self):
        assert not _is_manager_request("Скільки коштує футболка?")
        assert not _is_manager_request("Які розміри є?")

    def test_greeting_detection(self):
        assert _is_greeting("Привіт")
        assert _is_greeting("Привет!")
        assert _is_greeting("Hello there")
        assert _is_greeting("Доброго дня")

    def test_not_greeting(self):
        assert not _is_greeting("Скільки коштує?")
        assert not _is_greeting("Хочу замовити")

    def test_goodbye_detection(self):
        assert _is_goodbye("Пока")
        assert _is_goodbye("До побачення")
        assert _is_goodbye("Дякую, все")
        assert _is_goodbye("Thanks, bye")

    def test_not_goodbye(self):
        assert not _is_goodbye("Покажіть футболки")
        assert not _is_goodbye("Скільки?")


class TestDeterministicOutcomes:
    """Test deterministic outcome classification."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = Mock(igsid=12345, username="testuser")
        self.episode = Mock(state="INCIDENT")

    def test_outcome_1_manager_request_ukrainian(self):
        """Manager request in Ukrainian returns confirmation."""
        result = deterministic_outcome(
            "Хочу поговорити з менеджером",
            self.client,
            self.episode,
        )
        assert result is not None
        assert isinstance(result, DeterministicOutcome)
        assert "менеджеру" in result.reply
        assert result.manager_task_reason == "customer_requested_human_agent"

    def test_outcome_1_manager_request_russian(self):
        """Manager request in Russian returns confirmation."""
        result = deterministic_outcome(
            "Хочу поговорить с менеджером",
            self.client,
            self.episode,
        )
        assert result is not None
        assert "менеджеру" in result.reply
        assert result.manager_task_reason == "customer_requested_human_agent"

    def test_outcome_1_manager_request_english(self):
        """Manager request in English returns confirmation."""
        result = deterministic_outcome(
            "I want to talk to a manager",
            self.client,
            self.episode,
        )
        assert result is not None
        assert "manager" in result.reply.lower()
        assert result.manager_task_reason == "customer_requested_human_agent"

    def test_outcome_4_greeting_ukrainian(self):
        """Greeting in Ukrainian returns greeting response."""
        result = deterministic_outcome(
            "Привіт",
            self.client,
            self.episode,
        )
        assert result is not None
        assert result.manager_task_reason is None
        assert len(result.reply) < 100  # Short template

    def test_outcome_4_greeting_russian(self):
        """Greeting in Russian returns greeting response."""
        result = deterministic_outcome(
            "Привет!",
            self.client,
            self.episode,
        )
        assert result is not None
        assert result.manager_task_reason is None

    def test_outcome_4_goodbye_ukrainian(self):
        """Goodbye in Ukrainian returns goodbye response."""
        result = deterministic_outcome(
            "Дякую, все",
            self.client,
            self.episode,
        )
        assert result is not None
        assert result.manager_task_reason is None

    def test_outcome_5_escalate_to_l4(self):
        """Non-deterministic turn returns None (escalate to L4)."""
        result = deterministic_outcome(
            "Скільки коштує футболка Харків?",
            self.client,
            self.episode,
        )
        assert result is None

    def test_outcome_5_product_question(self):
        """Product questions escalate to L4."""
        result = deterministic_outcome(
            "Які розміри є в наявності?",
            self.client,
            self.episode,
        )
        assert result is None

    def test_outcome_5_order_status(self):
        """Order status questions escalate to L4."""
        result = deterministic_outcome(
            "Коли прийде моє замовлення?",
            self.client,
            self.episode,
        )
        assert result is None


class TestNoProhibitedAssertions:
    """
    Test that deterministic responses never assert facts not in DB.
    Pattern from ADD-AGENT-007.
    """

    def setup_method(self):
        self.client = Mock(igsid=12345, username="testuser")
        self.episode = Mock(state="INCIDENT")

    def test_manager_confirmation_no_timeframe(self):
        """Manager confirmation doesn't promise response time."""
        result = deterministic_outcome(
            "Хочу менеджера",
            self.client,
            self.episode,
        )
        prohibited_phrases = [
            "протягом години",
            "в течение часа",
            "within an hour",
            "завтра",
            "tomorrow",
            "скоро",
            "soon",
            "через 10 хвилин",
        ]
        for phrase in prohibited_phrases:
            assert phrase not in result.reply.lower()

    def test_greeting_no_product_claims(self):
        """Greeting doesn't assert product availability."""
        result = deterministic_outcome(
            "Привіт",
            self.client,
            self.episode,
        )
        prohibited = [
            "є в наявності",
            "в наличии",
            "available",
            "розмір",
            "size",
        ]
        for phrase in prohibited:
            assert phrase not in result.reply.lower()

    def test_goodbye_no_order_claims(self):
        """Goodbye doesn't assert order status."""
        result = deterministic_outcome(
            "Дякую, все",
            self.client,
            self.episode,
        )
        prohibited = [
            "замовлення",
            "заказ",
            "order",
            "відправимо",
            "отправим",
            "ship",
        ]
        for phrase in prohibited:
            assert phrase not in result.reply.lower()


class TestFallbackToL4:
    """Test that complex cases escalate to L4 (return None)."""

    def setup_method(self):
        self.client = Mock(igsid=12345, username="testuser")
        self.episode = Mock(state="INCIDENT")

    def test_product_availability_requires_l4(self):
        """Product availability questions need model."""
        inputs = [
            "Чи є футболка Харків в розмірі M?",
            "Есть ли худи в наличии?",
            "Do you have size L?",
        ]
        for text in inputs:
            result = deterministic_outcome(text, self.client, self.episode)
            assert result is None, f"Should escalate: {text}"

    def test_order_status_requires_l4(self):
        """Order status questions need model."""
        inputs = [
            "Де моє замовлення?",
            "Когда придет заказ?",
            "Where is my order?",
        ]
        for text in inputs:
            result = deterministic_outcome(text, self.client, self.episode)
            assert result is None

    def test_complex_requests_require_l4(self):
        """Complex multi-part requests need model."""
        inputs = [
            "Хочу футболку Харків, розмір M, і ще худі",
            "Скільки коштує доставка в Львів?",
            "Can I change my order?",
        ]
        for text in inputs:
            result = deterministic_outcome(text, self.client, self.episode)
            assert result is None
