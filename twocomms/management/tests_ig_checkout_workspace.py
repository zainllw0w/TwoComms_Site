import hashlib
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from management.ig_bot_models import IgCheckoutAccessToken, IgCheckoutProposal, IgCheckoutProposalItem
from management.models import (
    AdminAuditLog,
    IgCheckoutInventoryReservation,
    IgClient,
    IgDeal,
    IgFollowUpTask,
    InstagramBotSettings,
)
from management.services.bot_followups import process_due_followups
from management.services.ig_commercial_episodes import ensure_episode_for_deal
from orders.models import PaymentAttempt
from storefront.models import Category, Product


@override_settings(ROOT_URLCONF="twocomms.urls_management")
class InstagramCheckoutWorkspaceTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="checkout-staff", password="secret", is_staff=True
        )
        self.client.force_login(self.staff)
        self.profile = IgClient.get_or_create_for_sender("workspace-sender")
        self.profile.display_name = "Марія Покупець"
        self.profile.username = "maria_workspace"
        self.profile.save(update_fields=["display_name", "username", "updated_at"])
        self.bot_settings = InstagramBotSettings.load()
        self.bot_settings.is_enabled = True
        self.bot_settings.save(update_fields=["is_enabled", "updated_at"])
        self.deal = IgDeal.objects.create(
            client=self.profile,
            status=IgDeal.Status.QUOTED,
            amount=Decimal("950.00"),
            requested_payment_amount=Decimal("950.00"),
        )
        self.episode = ensure_episode_for_deal(self.deal)
        category = Category.objects.create(name="Workspace", slug="workspace")
        product = Product.objects.create(
            title="Workspace tee", slug="workspace-tee", category=category,
            price=950, status="published",
        )
        self.proposal = IgCheckoutProposal.objects.create_current(
            deal=self.deal,
            commercial_episode=self.episode,
            catalog_total=Decimal("950.00"),
            quoted_total=Decimal("950.00"),
            requested_payment_amount=Decimal("950.00"),
            items_digest=hashlib.sha256(b"workspace").hexdigest(),
        )
        IgCheckoutProposalItem.objects.create(
            proposal=self.proposal,
            product=product,
            product_title=product.title,
            sku="WS-TEE-M",
            size="M",
            fit_code="classic",
            fit_label="Класичний",
            quantity=1,
            catalog_unit_price=Decimal("950.00"),
            catalog_line_total=Decimal("950.00"),
            quoted_unit_price=Decimal("950.00"),
            quoted_line_total=Decimal("950.00"),
        )

    def test_awaiting_api_masks_pii_and_never_returns_bearer(self):
        attempt = PaymentAttempt.objects.create(
            fingerprint=hashlib.sha256(b"workspace-attempt").hexdigest(),
            full_name="Марія Покупець",
            phone="+380501112233",
            email="maria@example.com",
            city="Харків",
            np_office="Відділення №4",
            pay_type=PaymentAttempt.PayType.ONLINE_FULL,
            cart_snapshot={"items": []},
            gross_amount=Decimal("950.00"),
            payable_amount=Decimal("950.00"),
            payment_amount=Decimal("950.00"),
        )
        self.proposal.payment_attempt = attempt
        self.proposal.status = IgCheckoutProposal.Status.DETAILS_LOCKED
        self.proposal.details_locked_at = timezone.now()
        self.proposal.save(update_fields=["payment_attempt", "status", "details_locked_at", "updated_at"])
        response = self.client.get(reverse("management_bot_checkout_proposals_api"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        item = payload["items"][0]
        self.assertEqual(item["delivery"]["phone"], "+380 ** *** ** 2233")
        self.assertEqual(item["delivery"]["recipient"], "М*** П***")
        self.assertEqual(item["delivery"]["email"], "m***@example.com")
        self.assertEqual(item["delivery"]["city"], "Х***")
        self.assertEqual(item["delivery"]["office"], "В*** №4")
        self.assertEqual(item["client"]["label"], f"IG client #{self.profile.pk}")
        self.assertNotIn("token_digest", str(payload))
        self.assertNotIn("ivan", str(payload).lower())

    def test_copy_token_is_explicit_and_digest_only_is_persisted(self):
        response = self.client.post(
            reverse("management_bot_checkout_proposal_action_api", kwargs={"proposal_id": self.proposal.public_id}),
            {"action": "copy_token"},
        )
        self.assertEqual(response.status_code, 200)
        url = response.json()["url"]
        raw_token = url.rstrip("/").rsplit("/", 1)[-1]
        self.assertTrue(raw_token)
        self.assertFalse(IgCheckoutAccessToken.objects.get(proposal=self.proposal).token_digest == raw_token)
        self.assertEqual(IgCheckoutAccessToken.objects.filter(proposal=self.proposal).count(), 1)

    def test_expired_workspace_state_uses_expired_label(self):
        self.proposal.expires_at = timezone.now() - timedelta(minutes=1)
        self.proposal.save(update_fields=["expires_at", "updated_at"])

        response = self.client.get(reverse("management_bot_checkout_proposals_api"))

        self.assertEqual(response.status_code, 200)
        item = response.json()["items"][0]
        self.assertEqual(item["state"], IgCheckoutProposal.Status.EXPIRED)
        self.assertEqual(item["state_label"], "Протерміновано")

    def test_resend_worker_delivers_within_latest_inbound_window(self):
        now = timezone.now()
        self.profile.last_message_at = now - timedelta(hours=1)
        self.profile.save(update_fields=["last_message_at", "updated_at"])
        response = self.client.post(
            reverse("management_bot_checkout_proposal_action_api", kwargs={"proposal_id": self.proposal.public_id}),
            {"action": "resend"},
        )
        self.assertEqual(response.status_code, 200)
        task = IgFollowUpTask.objects.get(pk=response.json()["task_id"])
        self.assertEqual(task.meta_window_deadline, self.profile.last_message_at + timedelta(hours=23))
        # The action timestamps the task inside the POST, so use the persisted
        # due time instead of the pre-request clock sample. This keeps the
        # worker contract deterministic at microsecond resolution.
        with patch("management.services.instagram_bot.send_text", return_value=(True, "", "")), patch(
            "management.services.bot_followups.next_allowed_send_at", return_value=task.due_at
        ):
            processed = process_due_followups(now=task.due_at)
        task.refresh_from_db()
        self.assertEqual(processed, 1)
        self.assertEqual(task.status, IgFollowUpTask.Status.SENT)

    def test_revoke_writes_one_manager_audit_and_replay_is_idempotent(self):
        url = reverse(
            "management_bot_checkout_proposal_action_api",
            kwargs={"proposal_id": self.proposal.public_id},
        )

        first = self.client.post(url, {"action": "revoke"})
        second = self.client.post(url, {"action": "revoke"})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(
            AdminAuditLog.objects.filter(
                action="ig_checkout.revoke",
                entity_type="IgCheckoutProposal",
                entity_id=str(self.proposal.public_id),
            ).count(),
            1,
        )

    def test_revoke_clears_pointer_releases_inventory_and_cancels_payment_reminder(self):
        reservation = IgCheckoutInventoryReservation.objects.create(
            proposal=self.proposal,
            item=self.proposal.items.get(),
            product=self.proposal.items.get().product,
            quantity=1,
            reservation_fingerprint=hashlib.sha256(b"workspace-revoke-reservation").hexdigest(),
            expires_at=timezone.now() + timedelta(hours=1),
        )
        payment_task = IgFollowUpTask.objects.create(
            client=self.profile,
            deal=self.deal,
            due_at=timezone.now(),
            kind=IgFollowUpTask.Kind.PAYMENT,
            reason=f"ig_checkout_resend:{self.proposal.public_id}",
            message_text="https://twocomms.shop/offer/a/dead-token/",
        )
        qualification_task = IgFollowUpTask.objects.create(
            client=self.profile,
            deal=self.deal,
            due_at=timezone.now() + timedelta(hours=1),
            kind=IgFollowUpTask.Kind.QUALIFICATION,
            reason="qualification_unanswered",
        )

        response = self.client.post(
            reverse(
                "management_bot_checkout_proposal_action_api",
                kwargs={"proposal_id": self.proposal.public_id},
            ),
            {"action": "revoke"},
        )

        self.assertEqual(response.status_code, 200)
        self.proposal.refresh_from_db()
        self.deal.refresh_from_db()
        reservation.refresh_from_db()
        payment_task.refresh_from_db()
        qualification_task.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.proposal.status, IgCheckoutProposal.Status.REVOKED)
        self.assertIsNone(self.deal.active_checkout_proposal_id)
        self.assertEqual(reservation.state, IgCheckoutInventoryReservation.State.RELEASED)
        self.assertEqual(reservation.release_reason, "proposal_revoked")
        self.assertEqual(payment_task.status, IgFollowUpTask.Status.CANCELLED)
        self.assertEqual(payment_task.skip_reason, "proposal_revoked")
        self.assertEqual(qualification_task.status, IgFollowUpTask.Status.PENDING)
        self.assertEqual(self.profile.next_followup_at, qualification_task.due_at)

    def test_resend_uses_current_meta_window_and_is_not_immediately_skipped(self):
        self.profile.last_message_at = timezone.now()
        self.profile.save(update_fields=["last_message_at", "updated_at"])
        response = self.client.post(
            reverse("management_bot_checkout_proposal_action_api", kwargs={"proposal_id": self.proposal.public_id}),
            {"action": "resend"},
        )
        self.assertEqual(response.status_code, 200)
        task = self.deal.followup_tasks.get(reason=f"ig_checkout_resend:{self.proposal.public_id}")
        self.assertEqual(task.status, task.Status.PENDING)
        self.assertGreater(task.meta_window_deadline, timezone.now())

    def test_resend_refuses_closed_meta_window(self):
        self.profile.last_message_at = timezone.now() - timedelta(hours=24)
        self.profile.save(update_fields=["last_message_at", "updated_at"])
        response = self.client.post(
            reverse("management_bot_checkout_proposal_action_api", kwargs={"proposal_id": self.proposal.public_id}),
            {"action": "resend"},
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"], "response_window_closed")

    def test_revoke_refuses_payable_invoice_without_provider_cancellation(self):
        attempt = PaymentAttempt.objects.create(
            fingerprint=hashlib.sha256(b"workspace-invoice").hexdigest(),
            full_name="Марія Покупець", phone="+380501112233", email="maria@example.com",
            city="Харків", np_office="Відділення №4", pay_type=PaymentAttempt.PayType.ONLINE_FULL,
            status=PaymentAttempt.Status.PROCESSING, invoice_url="https://pay.example/invoice",
            cart_snapshot={"items": []}, gross_amount=Decimal("950.00"),
            payable_amount=Decimal("950.00"), payment_amount=Decimal("950.00"),
        )
        self.proposal.payment_attempt = attempt
        self.proposal.status = IgCheckoutProposal.Status.INVOICE_CREATED
        self.proposal.save(update_fields=["payment_attempt", "status", "updated_at"])
        response = self.client.post(
            reverse("management_bot_checkout_proposal_action_api", kwargs={"proposal_id": self.proposal.public_id}),
            {"action": "revoke"},
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"], "provider_cancellation_required")

    def test_non_staff_cannot_read_workspace(self):
        self.client.logout()
        response = self.client.get(reverse("management_bot_checkout_proposals_api"))
        self.assertIn(response.status_code, {302, 403})

    def test_management_bot_exposes_checkout_proposal_workspace(self):
        response = self.client.get(reverse("management_bot"))

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('id="bot-checkout-list"', body)
        self.assertIn('id="bot-checkout-preview"', body)
        self.assertIn("/bot/api/checkout-proposals/", body)
        self.assertIn("/bot/api/checkout-proposals/00000000-0000-0000-0000-000000000000/action/", body)
