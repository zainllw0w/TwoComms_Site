import io
import json

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from management.ig_bot_models import IgClient, IgPaymentConfirmationReview, IgPaymentReviewDecision


class HistoricalInstagramResolutionCommandTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user(
            username="historical-resolution-command-actor",
            password="test-password",
            is_staff=True,
        )
        self.client = IgClient.get_or_create_for_sender("historical-resolution-command-client")
        self.known_review = IgPaymentConfirmationReview.objects.create(
            client=self.client,
            dedupe_key="historical-resolution-command-known",
        )
        self.unknown_review = IgPaymentConfirmationReview.objects.create(
            client=self.client,
            dedupe_key="historical-resolution-command-unknown",
        )

    def _call(self, *args):
        output = io.StringIO()
        call_command("resolve_historical_ig_sales", *args, stdout=output)
        return json.loads(output.getvalue())

    def test_command_dry_runs_explicit_ids_without_writing_then_applies_idempotently(self):
        common = (
            "--review-id", str(self.known_review.pk),
            "--review-id", str(self.unknown_review.pk),
            "--actor-id", str(self.actor.pk),
            "--outcome", "already_received",
            "--reason", "Historical sale confirmed by owner",
            "--paid-amount", f"{self.known_review.pk}=1760",
            "--amount-unrecoverable", str(self.unknown_review.pk),
        )
        preview = self._call(*common)
        self.assertTrue(preview["dry_run"])
        self.assertEqual([row["status"] for row in preview["results"]], ["eligible", "eligible"])
        self.assertFalse(IgPaymentReviewDecision.objects.filter(review=self.known_review).exists())

        applied = self._call(*common, "--apply")
        self.assertFalse(applied["dry_run"])
        self.assertEqual([row["status"] for row in applied["results"]], ["applied", "applied"])
        known_decision = IgPaymentReviewDecision.objects.get(review=self.known_review)
        unknown_decision = IgPaymentReviewDecision.objects.get(review=self.unknown_review)
        self.assertEqual(str(known_decision.confirmed_amount), "1760.00")
        self.assertIsNone(unknown_decision.confirmed_amount)

        replay = self._call(*common, "--apply")
        self.assertEqual([row["status"] for row in replay["results"]], ["skipped", "skipped"])
        self.assertEqual(IgPaymentReviewDecision.objects.filter(review=self.known_review).count(), 1)
        self.assertEqual(IgPaymentReviewDecision.objects.filter(review=self.unknown_review).count(), 1)

    def test_command_refuses_empty_ids_and_malformed_amount_mapping(self):
        with self.assertRaisesMessage(CommandError, "--review-id"):
            self._call(
                "--actor-id", str(self.actor.pk),
                "--outcome", "already_received",
                "--reason", "Historical sale confirmed by owner",
            )
        with self.assertRaisesMessage(CommandError, "REVIEW_ID=AMOUNT"):
            self._call(
                "--review-id", str(self.known_review.pk),
                "--actor-id", str(self.actor.pk),
                "--outcome", "already_received",
                "--reason", "Historical sale confirmed by owner",
                "--paid-amount", "broken",
            )
