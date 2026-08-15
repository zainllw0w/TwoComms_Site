from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase


class LifecycleFollowSnapshotTests(SimpleTestCase):
    def test_message_prefers_immutable_final_text_snapshot(self):
        from management.services.ig_lifecycle import _message

        event = SimpleNamespace(
            final_text="Оплату отримали. Будемо раді бачити вас серед підписників.",
            payload={"message_snapshot": "Оплату отримали."},
            kind="payment_verified",
            locale="uk",
            order=SimpleNamespace(order_number="T-1"),
        )

        self.assertEqual(_message(event), event.final_text)

    def test_materialize_payment_text_does_not_mutate_payload_and_rejects_other_kinds(self):
        from management.services.ig_lifecycle import materialize_lifecycle_follow_text

        payment = SimpleNamespace(
            pk=1,
            kind="payment_verified",
            final_text="",
            payload={"message_snapshot": "Оплату отримали."},
        )
        with patch(
            "management.services.ig_lifecycle._prepared_follow_text",
            return_value="Оплату отримали. Будемо раді бачити вас серед підписників.",
        ):
            text = materialize_lifecycle_follow_text(payment)
        self.assertIn("підписників", text)
        self.assertEqual(payment.payload, {"message_snapshot": "Оплату отримали."})

        review = SimpleNamespace(
            pk=2,
            kind="delivered_review_requested",
            final_text="",
            payload={"message_snapshot": "Дякуємо за відгук."},
        )
        self.assertEqual(materialize_lifecycle_follow_text(review), "Дякуємо за відгук.")
