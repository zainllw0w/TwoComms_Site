"""ЭА.9 — рівень L3: детермінований відповідь без моделі.

Тести навмисно `SimpleTestCase`: `deterministic_outcome` не торкається БД, і це
частина контракту. Якщо колись знадобиться запит до БД, тест впаде на заборону
доступу — і це правильний сигнал, а не незручність: вихід, який читає БД, мусить
проходити окремий розбір (виходи 2 і 3 у плані саме тому й не включені).
"""
from unittest.mock import Mock

from django.test import SimpleTestCase

from management.services.ig_deterministic_l3 import (
    L3_TEXT_VERSION,
    DeterministicOutcome,
    deterministic_outcome,
)


def _client(lang="uk"):
    client = Mock()
    client.lang = lang
    client.igsid = "igsid-l3"
    return client


def _episode(terminal=False):
    episode = Mock()
    episode.is_terminal = terminal
    return episode


class ManagerRequestOutcomeTests(SimpleTestCase):
    """Вихід 1: запит менеджера — підтвердження + manager case."""

    def test_manager_request_is_recognised_in_three_languages(self):
        cases = (
            ("uk", "Хочу поговорити з менеджером"),
            ("ru", "Нужен менеджер"),
            ("en", "I need to talk to a manager"),
        )
        for lang, text in cases:
            with self.subTest(lang=lang):
                outcome = deterministic_outcome(text, _client(lang), _episode())
                self.assertIsInstance(outcome, DeterministicOutcome)
                self.assertEqual(outcome.outcome_code, "manager_request")
                self.assertTrue(outcome.manager_task_reason)

    def test_operator_and_human_wording_also_counts(self):
        for lang, text in (("uk", "Дайте оператора"), ("en", "talk to a human")):
            with self.subTest(lang=lang):
                outcome = deterministic_outcome(text, _client(lang), _episode())
                self.assertIsNotNone(outcome)
                self.assertEqual(outcome.outcome_code, "manager_request")

    def test_reason_carries_bounded_customer_text(self):
        """Причина несе текст клієнта, але обрізаний — це рядок для менеджера."""
        long_text = "Хочу менеджера " + "х" * 300
        outcome = deterministic_outcome(long_text, _client("uk"), _episode())
        self.assertIsNotNone(outcome)
        self.assertLess(len(outcome.manager_task_reason), 200)

    def test_confirmation_promises_no_deadline(self):
        """Текст не має обіцяти строк, якого ніхто не гарантував."""
        forbidden = (
            "протягом години", "в течение часа", "within an hour",
            "за 10 хвилин", "через 5 минут", "in 5 minutes",
            "сьогодні", "сегодня", "today", "завтра", "tomorrow",
        )
        for lang in ("uk", "ru", "en"):
            outcome = deterministic_outcome("менеджер", _client(lang), _episode())
            reply = outcome.reply.casefold()
            for phrase in forbidden:
                with self.subTest(lang=lang, phrase=phrase):
                    self.assertNotIn(phrase, reply)


class GreetingOutcomeTests(SimpleTestCase):
    """Вихід 4: привітання / прощання — короткий шаблон."""

    def test_greeting_returns_greeting_template(self):
        for lang, text in (("uk", "Привіт"), ("ru", "Привет"), ("en", "Hi")):
            with self.subTest(lang=lang):
                outcome = deterministic_outcome(text, _client(lang), _episode())
                self.assertIsNotNone(outcome)
                self.assertEqual(outcome.outcome_code, "greeting")
                self.assertIsNone(outcome.manager_task_reason)

    def test_thanks_and_farewell_return_goodbye_template(self):
        cases = (
            ("uk", "Дякую"), ("uk", "До побачення"),
            ("ru", "Спасибо"), ("en", "Thanks"), ("en", "Bye"),
        )
        for lang, text in cases:
            with self.subTest(lang=lang, text=text):
                outcome = deterministic_outcome(text, _client(lang), _episode())
                self.assertIsNotNone(outcome)
                self.assertEqual(outcome.outcome_code, "goodbye")

    def test_greeting_must_be_the_whole_message(self):
        """«Привіт, а є розмір M?» — це питання, а не привітання."""
        outcome = deterministic_outcome(
            "Привіт, а є розмір M?", _client("uk"), _episode()
        )
        self.assertIsNone(outcome)


class EscalationToL4Tests(SimpleTestCase):
    """Вихід 5: усе інше йде на L4, детермінованої відповіді немає."""

    def test_catalog_and_order_questions_escalate(self):
        cases = (
            ("uk", "Скільки коштує футболка?"),
            ("uk", "Чи є розмір L у наявності?"),
            ("uk", "Де моє замовлення?"),
            ("ru", "Как оплатить?"),
            ("ru", "Когда придет заказ?"),
            ("en", "Do you have size L?"),
            ("en", "Where is my order?"),
        )
        for lang, text in cases:
            with self.subTest(text=text):
                self.assertIsNone(
                    deterministic_outcome(text, _client(lang), _episode())
                )

    def test_availability_outcome_is_not_enabled_yet(self):
        """Вихід 2 свідомо вимкнений до Э3.7 — питання про наявність іде на L4.

        Це не прогалина в тестах, а закріплення рішення: відповідь про наявність
        без resolver-а варіанта (Э3.7) назвала б клієнту розмір, якого може не
        бути. Тест впаде, якщо хтось увімкне вихід 2 передчасно.
        """
        for text in ("Чи є худі в наявності?", "Есть ли в наличии XL?"):
            with self.subTest(text=text):
                self.assertIsNone(
                    deterministic_outcome(text, _client("uk"), _episode())
                )


class TerminalEpisodeTests(SimpleTestCase):
    """Закритий епізод не дає L3-відповіді: хід уже закритий один раз."""

    def test_terminal_episode_never_answers(self):
        for text in ("Привіт", "Хочу менеджера", "Дякую"):
            with self.subTest(text=text):
                self.assertIsNone(
                    deterministic_outcome(text, _client("uk"), _episode(terminal=True))
                )


class NoUnprovenClaimsTests(SimpleTestCase):
    """ADD-AGENT-007: жоден детермінований текст не утверджує факт із БД."""

    FORBIDDEN = (
        "в наявності", "немає в наявності", "в наличии", "нет в наличии",
        "in stock", "out of stock",
        "ціна", "цена", "price", "коштує", "стоит", "costs",
        "замовлення", "заказ", "order",
        "оплачено", "оплачен", "paid",
        "відправили", "отправили", "shipped",
    )

    def test_every_template_is_free_of_db_claims(self):
        triggers = ("Привіт", "Дякую", "Хочу менеджера", "До побачення")
        for lang in ("uk", "ru", "en"):
            for text in triggers:
                outcome = deterministic_outcome(text, _client(lang), _episode())
                if outcome is None:
                    continue
                reply = outcome.reply.casefold()
                for phrase in self.FORBIDDEN:
                    with self.subTest(lang=lang, text=text, phrase=phrase):
                        self.assertNotIn(phrase, reply)


class VersionedTextTests(SimpleTestCase):
    """Тексти лежать в одному версіонованому місці."""

    def test_version_is_present_and_dated(self):
        import re

        self.assertRegex(L3_TEXT_VERSION, r"^\d{4}-\d{2}-\d{2}\.\d+$")

    def test_unknown_language_falls_back_to_ukrainian(self):
        outcome = deterministic_outcome("Привіт", _client("de"), _episode())
        self.assertIsNotNone(outcome)
        self.assertEqual(outcome.outcome_code, "greeting")

    def test_missing_language_falls_back_to_ukrainian(self):
        client = Mock()
        client.lang = None
        client.igsid = "igsid-none"
        outcome = deterministic_outcome("Привіт", client, _episode())
        self.assertIsNotNone(outcome)
