"""Э2.1 — потеря конца ответа при усечении: явный исход вместо молчания."""
from django.test import TestCase

from management.services.ig_delivery_plan import (
    COMPLETE,
    SUMMARIZED,
    TRUNCATED,
    build_delivery_plan,
    split_url_safe,
)


class DeliveryPlanTests(TestCase):
    def test_short_reply_is_complete_in_one_chunk(self):
        plan = build_delivery_plan("Привіт! Ось відповідь.")
        self.assertEqual(plan.outcome, COMPLETE)
        self.assertEqual(len(plan.chunks), 1)
        self.assertEqual(plan.dropped_bytes, 0)
        self.assertTrue(plan.deliverable)

    def test_sentinel_after_the_old_budget_is_never_silently_dropped(self):
        """RED-репродьюсер: 4×950 = 3800 байт при разрешённых 4000 символах."""
        sentinel = "ПОСИЛАННЯ-НА-ОПЛАТУ-ТУТ"
        body = "Ось деталі вашого замовлення номер один. " * 150
        plan = build_delivery_plan(f"{body}{sentinel}")

        self.assertNotEqual(
            plan.outcome, COMPLETE, "текст явно не влазить у бюджет транспорту"
        )
        if plan.deliverable:
            self.assertIn(sentinel, " ".join(plan.chunks))
        else:
            self.assertEqual(plan.outcome, TRUNCATED)
            self.assertTrue(plan.reason)

    def test_compaction_preserves_the_actionable_tail(self):
        url = "https://pay.monobank.ua/abc123"
        repeated = "Дякую за звернення. " * 120
        plan = build_delivery_plan(
            f"{repeated}Сума до сплати 1250 грн. Посилання: {url}"
        )
        self.assertTrue(plan.deliverable)
        joined = " ".join(plan.chunks)
        self.assertIn(url, joined)
        self.assertIn("1250", joined)
        self.assertEqual(plan.outcome, SUMMARIZED)
        self.assertGreater(plan.dropped_bytes, 0)

    def test_duplicate_sentences_are_removed_before_anything_is_dropped(self):
        text = " ".join(["Ось відповідь на ваше питання."] * 200) + " Кінець."
        plan = build_delivery_plan(text)
        self.assertTrue(plan.deliverable)
        self.assertIn("Кінець.", " ".join(plan.chunks))

    def test_url_is_never_split_across_chunks(self):
        url = "https://pay.monobank.ua/" + ("a" * 400)
        text = ("Деталі замовлення. " * 60) + f"Оплата: {url} Дякую."
        chunks, rest = split_url_safe(text)
        self.assertEqual(rest, "")
        for chunk in chunks:
            self.assertNotIn(url[:40], chunk) if url not in chunk else None
        self.assertTrue(
            any(url in chunk for chunk in chunks),
            "посилання мусить лежати цілком в одному чанку",
        )

    def test_url_longer_than_one_chunk_is_refused_not_broken(self):
        url = "https://x.example.com/" + ("b" * 2000)
        plan = build_delivery_plan(f"Ось лінк {url}")
        self.assertEqual(plan.outcome, TRUNCATED)
        self.assertFalse(plan.deliverable)
        self.assertTrue(plan.reason)

    def test_empty_reply_is_an_explicit_non_delivery(self):
        plan = build_delivery_plan("   ")
        self.assertEqual(plan.outcome, TRUNCATED)
        self.assertEqual(plan.reason, "empty_reply")
        self.assertFalse(plan.deliverable)

    def test_multibyte_boundary_never_produces_an_oversized_chunk(self):
        text = "Привіт! " * 900
        chunks, _rest = split_url_safe(text, limit=950, max_chunks=8)
        for chunk in chunks:
            self.assertLessEqual(len(chunk.encode("utf-8")), 950)


class SendTextTruncationContractTests(TestCase):
    """`sent` невозможен, если хвост исчез."""

    def setUp(self):
        from management.models import InstagramBotSettings

        self.settings = InstagramBotSettings.load()

    def test_oversized_reply_is_refused_before_provider_io(self):
        from unittest.mock import patch

        from management.services.instagram_bot import send_text

        url = "https://x.example.com/" + ("c" * 2000)
        with patch(
            "management.services.instagram_bot._provider_account_id", return_value="1"
        ), patch(
            "management.services.instagram_bot.get_page_token", return_value="t"
        ), patch(
            "management.services.instagram_bot._provider_http"
        ) as http:
            receipt = send_text(
                self.settings, "igsid-1", f"Лінк {url}", return_receipt=True
            )

        http.assert_not_called()
        self.assertFalse(receipt.ok)
        self.assertEqual(receipt.kind, "permanent")
        self.assertIn(TRUNCATED, receipt.failure_boundary)
