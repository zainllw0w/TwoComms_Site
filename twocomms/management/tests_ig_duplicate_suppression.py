"""Тести на Э-DUP: той самий текст або медіа двічі = production-дефект."""
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from management.models import IgClient, InstagramBotMessage
from management.services.instagram_bot import (
    _identical_media_recently_sent,
    _recent_identical_reply_exists,
    _reply_without_unproven_claims,
)


class DuplicateReplySuppressionTests(TestCase):
    """Production 28.08: клієнт отримав однакову відповідь двічі підряд."""

    def setUp(self):
        self.client = IgClient.get_or_create_for_sender("dup-text-sender")
        self.row = InstagramBotMessage.objects.create(
            sender_id="dup-text-sender",
            client=self.client,
            role=InstagramBotMessage.Role.USER,
            text="want kharkiv tee",
        )

    def test_identical_text_sent_minutes_ago_is_detected(self):
        InstagramBotMessage.objects.create(
            sender_id=self.row.sender_id,
            client=self.client,
            role=InstagramBotMessage.Role.MODEL,
            text="Ось підходящі футболки: ...",
            provider_message_id="m1",
            created_at=timezone.now() - timedelta(minutes=3),
        )
        self.assertTrue(
            _recent_identical_reply_exists(self.row, "Ось підходящі футболки: ...")
        )

    def test_identical_text_is_normalized_before_comparison(self):
        InstagramBotMessage.objects.create(
            sender_id=self.row.sender_id,
            client=self.client,
            role=InstagramBotMessage.Role.MODEL,
            text="Ось   підходящі\n\nфутболки",
            provider_message_id="m2",
        )
        self.assertTrue(
            _recent_identical_reply_exists(self.row, "ось підходящі футболки")
        )

    def test_different_text_is_not_a_duplicate(self):
        InstagramBotMessage.objects.create(
            sender_id=self.row.sender_id,
            client=self.client,
            role=InstagramBotMessage.Role.MODEL,
            text="Ось підходящі футболки: А, Б",
            provider_message_id="m3",
        )
        self.assertFalse(
            _recent_identical_reply_exists(self.row, "Ось підходящі футболки: В")
        )

    def test_old_duplicate_beyond_window_is_not_flagged(self):
        old = InstagramBotMessage.objects.create(
            sender_id=self.row.sender_id,
            client=self.client,
            role=InstagramBotMessage.Role.MODEL,
            text="same",
            provider_message_id="m4",
        )
        # `created_at` is auto_now_add, so it must be moved with an UPDATE.
        InstagramBotMessage.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(minutes=20)
        )
        self.assertFalse(_recent_identical_reply_exists(self.row, "same"))


class DuplicateMediaSuppressionTests(TestCase):
    """Production 28.08: клієнт двічі отримав ті самі три фото."""

    def setUp(self):
        self.client = IgClient.get_or_create_for_sender("dup-media-sender")
        self.row = InstagramBotMessage.objects.create(
            sender_id="dup-media-sender",
            client=self.client,
            role=InstagramBotMessage.Role.USER,
            text="kharkiv",
        )

    def _selection(self, product_ids):
        return MagicMock(
            items=tuple(
                MagicMock(product_id=pid, title=f"Product {pid}")
                for pid in product_ids
            )
        )

    def test_identical_media_set_sent_recently_is_detected(self):
        InstagramBotMessage.objects.create(
            sender_id=self.row.sender_id,
            client=self.client,
            role=InstagramBotMessage.Role.MODEL,
            source="catalog_media",
            text="Product 7",
            provider_message_id="m1",
        )
        InstagramBotMessage.objects.create(
            sender_id=self.row.sender_id,
            client=self.client,
            role=InstagramBotMessage.Role.MODEL,
            source="catalog_media",
            text="Product 9",
            provider_message_id="m2",
        )
        selection = self._selection([7, 9])
        self.assertTrue(_identical_media_recently_sent(self.row, selection))

    def test_partially_matching_media_is_not_flagged(self):
        InstagramBotMessage.objects.create(
            sender_id=self.row.sender_id,
            client=self.client,
            role=InstagramBotMessage.Role.MODEL,
            source="catalog_media",
            text="Product 7",
            provider_message_id="m3",
        )
        selection = self._selection([7, 11])
        self.assertFalse(_identical_media_recently_sent(self.row, selection))


class UnprovenClaimStrippingTests(TestCase):
    """Замінити весь текст технічною фразою → прибрати тільки недоказане."""

    def test_sentence_with_unproven_stock_claim_is_removed(self):
        reply = "Ось три моделі. Футболка А є в наявності. Розмір?"
        result = _reply_without_unproven_claims(reply, ["stock"], locale="uk")
        self.assertNotIn("є в наявності", result)
        self.assertIn("три моделі", result)
        self.assertIn("Розмір", result)

    def test_fully_stripped_reply_keeps_only_the_honest_replacement(self):
        """Нічого змістовного не лишилось — але й технічної фрази теж немає."""
        reply = "Цей товар є в наявності."
        result = _reply_without_unproven_claims(reply, ["stock"], locale="uk")
        self.assertNotIn("є в наявності", result)
        self.assertIn("уточнюю", result.lower())
        # Головне: жодної згадки внутрішніх механізмів і жодної обіцянки,
        # яку ніхто не виконає.
        self.assertNotIn("системн", result.lower())
        self.assertNotIn("уточню відповідь", result.lower())

    def test_reply_with_no_salvageable_text_and_no_replacement_gets_a_question(self):
        result = _reply_without_unproven_claims("Ок.", ["consent"], locale="uk")
        self.assertIn("Підтвердження ще не зафіксовано", result)

    def test_replacement_for_each_failure_kind_is_appended(self):
        reply = "Дякую!"
        result = _reply_without_unproven_claims(reply, ["payment", "stock"], locale="uk")
        self.assertIn("Оплату ще не бачу", result)
        self.assertIn("Наявність", result)

    def test_no_claim_failures_returns_reply_unchanged(self):
        reply = "Ось підходящі моделі."
        result = _reply_without_unproven_claims(reply, [], locale="uk")
        self.assertEqual(result, reply)
