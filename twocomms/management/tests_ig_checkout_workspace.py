import hashlib
from pathlib import Path
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from management.bot_access import META_REVIEWER_GROUP_NAME
from management.ig_bot_models import (
    IgCheckoutAccessToken,
    IgCheckoutProposal,
    IgCheckoutProposalItem,
    IgCheckoutRevision,
    IgLifecycleEvent,
    IgOrderAttribution,
)
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
from management.services.instagram_bot import ProviderDeliveryReceipt
from orders.models import Order, PaymentAttempt
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
        self.assertEqual(item["delivery"]["office"], "В*** №***")
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

    def test_elapsed_ready_proposal_is_excluded_from_awaiting_and_counted_as_expired(self):
        self.proposal.expires_at = timezone.now() - timedelta(minutes=1)
        self.proposal.save(update_fields=["expires_at", "updated_at"])

        awaiting = self.client.get(reverse("management_bot_checkout_proposals_api"))
        expired = self.client.get(
            reverse("management_bot_checkout_proposals_api"),
            {"state": "expired"},
        )

        self.assertEqual(awaiting.status_code, 200)
        self.assertEqual(awaiting.json()["count"], 0)
        self.assertEqual(awaiting.json()["items"], [])
        self.assertEqual(awaiting.json()["counts"]["awaiting_payment"], 0)
        self.assertEqual(awaiting.json()["counts"]["expired"], 1)
        self.assertEqual(expired.status_code, 200)
        self.assertEqual(expired.json()["count"], 1)
        item = expired.json()["items"][0]
        self.assertEqual(item["state"], IgCheckoutProposal.Status.EXPIRED)
        self.assertEqual(item["state_label"], "Протерміновано")

    def test_workspace_filters_and_counts_ready_paid_and_expired(self):
        second_deal = IgDeal.objects.create(
            client=self.profile,
            status=IgDeal.Status.QUOTED,
            amount=Decimal("950.00"),
            requested_payment_amount=Decimal("950.00"),
        )
        second_episode = ensure_episode_for_deal(second_deal)
        paid = IgCheckoutProposal.objects.create_current(
            deal=second_deal,
            commercial_episode=second_episode,
            catalog_total=Decimal("950.00"),
            quoted_total=Decimal("950.00"),
            requested_payment_amount=Decimal("950.00"),
            items_digest=hashlib.sha256(b"workspace-paid").hexdigest(),
        )
        order = Order.objects.create(
            full_name="Марія Покупець",
            phone="+380501112233",
            email="maria@example.com",
            city="Харків",
            np_office="Відділення №4",
            pay_type="online_full",
            payment_status="paid",
            total_sum=Decimal("950.00"),
        )
        attempt = PaymentAttempt.objects.create(
            fingerprint=hashlib.sha256(b"workspace-paid-attempt").hexdigest(),
            full_name="Марія Покупець",
            phone="+380501112233",
            email="maria@example.com",
            city="Харків",
            np_office="Відділення №4",
            pay_type=PaymentAttempt.PayType.ONLINE_FULL,
            status=PaymentAttempt.Status.CONVERTED,
            order=order,
            cart_snapshot={"items": []},
            gross_amount=Decimal("950.00"),
            payable_amount=Decimal("950.00"),
            payment_amount=Decimal("950.00"),
        )
        paid.payment_attempt = attempt
        paid.paid_at = timezone.now()
        paid.status = IgCheckoutProposal.Status.PAID
        paid.save(update_fields=["payment_attempt", "paid_at", "status", "updated_at"])

        response = self.client.get(
            reverse("management_bot_checkout_proposals_api"),
            {"state": "ready"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["public_id"], str(self.proposal.public_id))
        self.assertEqual(payload["counts"]["ready"], 1)
        self.assertEqual(payload["counts"]["paid"], 1)
        self.assertEqual(payload["counts"]["expired"], 0)

    def test_location_masking_does_not_expose_any_raw_address_token(self):
        attempt = PaymentAttempt.objects.create(
            fingerprint=hashlib.sha256(b"workspace-address-mask").hexdigest(),
            full_name="Марія Покупець",
            phone="+380501112233",
            email="maria@example.com",
            city="Київ Печерський",
            np_office="вул. Хрещатик 1",
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

        item = self.client.get(reverse("management_bot_checkout_proposals_api")).json()["items"][0]

        self.assertEqual(item["delivery"]["city"], "К*** П***")
        self.assertEqual(item["delivery"]["office"], "в*** Х*** ***")
        masked = " ".join(item["delivery"].values())
        for raw_token in ("Київ", "Печерський", "вул.", "Хрещатик", "1"):
            self.assertNotIn(raw_token, masked)

    def test_action_capabilities_match_payable_provider_cancellation_gate(self):
        attempt = PaymentAttempt.objects.create(
            fingerprint=hashlib.sha256(b"workspace-capabilities").hexdigest(),
            full_name="Марія Покупець",
            phone="+380501112233",
            email="maria@example.com",
            city="Харків",
            np_office="Відділення №4",
            pay_type=PaymentAttempt.PayType.ONLINE_FULL,
            status=PaymentAttempt.Status.PROCESSING,
            invoice_url="https://pay.example/invoice",
            cart_snapshot={"items": []},
            gross_amount=Decimal("950.00"),
            payable_amount=Decimal("950.00"),
            payment_amount=Decimal("950.00"),
        )
        self.proposal.payment_attempt = attempt
        self.proposal.status = IgCheckoutProposal.Status.DETAILS_LOCKED
        self.proposal.details_locked_at = timezone.now()
        self.proposal.save(update_fields=["payment_attempt", "status", "details_locked_at", "updated_at"])

        item = self.client.get(reverse("management_bot_checkout_proposals_api")).json()["items"][0]

        self.assertTrue(item["actions"]["can_copy_token"])
        self.assertTrue(item["actions"]["can_resend"])
        self.assertFalse(item["actions"]["can_revoke"])
        self.assertEqual(item["actions"]["revoke_blocked_reason"], "provider_cancellation_required")

    def test_terminal_and_elapsed_proposals_expose_no_customer_link_actions(self):
        for status in (
            IgCheckoutProposal.Status.CANCELLED,
            IgCheckoutProposal.Status.EXPIRED,
            IgCheckoutProposal.Status.REVOKED,
        ):
            with self.subTest(status=status):
                self.proposal.status = status
                self.proposal.save(update_fields=["status", "updated_at"])

                item = self.client.get(
                    reverse("management_bot_checkout_proposal_preview_api", kwargs={"proposal_id": self.proposal.public_id})
                ).json()["proposal"]

                self.assertFalse(item["actions"]["can_copy_token"])
                self.assertFalse(item["actions"]["can_resend"])
                self.assertFalse(item["actions"]["can_revoke"])
                self.assertEqual(item["actions"]["revoke_blocked_reason"], "")

                resend = self.client.post(
                    reverse("management_bot_checkout_proposal_action_api", kwargs={"proposal_id": self.proposal.public_id}),
                    {"action": "resend"},
                )
                self.assertEqual(resend.status_code, 409)
                self.assertEqual(resend.json()["error"], "unavailable")

                revoke = self.client.post(
                    reverse("management_bot_checkout_proposal_action_api", kwargs={"proposal_id": self.proposal.public_id}),
                    {"action": "revoke"},
                )
                if status == IgCheckoutProposal.Status.REVOKED:
                    self.assertEqual(revoke.status_code, 200)
                else:
                    self.assertEqual(revoke.status_code, 409)
                    self.assertEqual(revoke.json()["error"], "unavailable")

    def test_preview_returns_full_revision_invoice_delivery_items_and_history(self):
        IgCheckoutRevision.objects.create(
            proposal=self.proposal,
            revision=1,
            digest=self.proposal.items_digest,
            snapshot={"items": [{"sku": "WS-TEE-M"}]},
            source=IgCheckoutRevision.Source.BOT_CREATE,
        )
        attempt = PaymentAttempt.objects.create(
            fingerprint=hashlib.sha256(b"workspace-preview").hexdigest(),
            full_name="Марія Покупець",
            phone="+380501112233",
            email="maria@example.com",
            city="Харків",
            np_office="Відділення №4",
            pay_type=PaymentAttempt.PayType.ONLINE_FULL,
            status=PaymentAttempt.Status.PROCESSING,
            reference="IG-PREVIEW-1",
            invoice_url="https://pay.example/invoice",
            cart_snapshot={"items": []},
            gross_amount=Decimal("950.00"),
            payable_amount=Decimal("950.00"),
            payment_amount=Decimal("950.00"),
        )
        self.proposal.payment_attempt = attempt
        self.proposal.status = IgCheckoutProposal.Status.INVOICE_CREATED
        self.proposal.details_locked_at = timezone.now()
        self.proposal.save(update_fields=["payment_attempt", "status", "details_locked_at", "updated_at"])

        response = self.client.get(
            reverse(
                "management_bot_checkout_proposal_preview_api",
                kwargs={"proposal_id": self.proposal.public_id},
            )
        )

        self.assertEqual(response.status_code, 200)
        proposal = response.json()["proposal"]
        self.assertEqual(proposal["revision"], 1)
        self.assertEqual(proposal["items"][0]["sku"], "WS-TEE-M")
        self.assertEqual(proposal["invoice"]["reference"], "IG-PREVIEW-1")
        self.assertEqual(proposal["delivery"]["city"], "Х***")
        self.assertEqual(proposal["history"]["revisions"][0]["source"], "bot_create")
        self.assertEqual(proposal["history"]["lifecycle"], [])

    def test_preview_exposes_only_classified_lifecycle_failure_details(self):
        order = Order.objects.create(
            full_name="Марія Покупець",
            phone="+380501112233",
            email="maria@example.com",
            city="Харків",
            np_office="Відділення №4",
            pay_type="online_full",
            payment_status="paid",
            total_sum=Decimal("950.00"),
        )
        attempt = PaymentAttempt.objects.create(
            fingerprint=hashlib.sha256(b"workspace-lifecycle-preview").hexdigest(),
            full_name=order.full_name,
            phone=order.phone,
            email=order.email,
            city=order.city,
            np_office=order.np_office,
            pay_type=PaymentAttempt.PayType.ONLINE_FULL,
            status=PaymentAttempt.Status.CONVERTED,
            cart_snapshot={"items": []},
            gross_amount=order.total_sum,
            payable_amount=order.total_sum,
            payment_amount=order.total_sum,
            order=order,
        )
        self.proposal.payment_attempt = attempt
        self.proposal.save(update_fields=["payment_attempt", "updated_at"])
        attribution = IgOrderAttribution.objects.create(
            order=order,
            client=self.profile,
            deal=self.deal,
            creation_mode="provider_auto",
            payment_source="provider_attempt",
        )
        IgLifecycleEvent.objects.create(
            event_key=f"payment_verified:{order.pk}",
            kind=IgLifecycleEvent.Kind.PAYMENT_VERIFIED,
            client=self.profile,
            deal=self.deal,
            proposal=self.proposal,
            order=order,
            commercial_episode=self.episode,
            attribution=attribution,
            state=IgLifecycleEvent.State.FAILED,
            provider_message_id="provider-secret-message-id",
            last_error="RuntimeError('https://graph.facebook.com/path?access_token=secret')",
        )

        response = self.client.get(
            reverse(
                "management_bot_checkout_proposal_preview_api",
                kwargs={"proposal_id": self.proposal.public_id},
            )
        )

        self.assertEqual(response.status_code, 200)
        lifecycle = response.json()["proposal"]["history"]["lifecycle"][0]
        self.assertEqual(lifecycle.get("error_code"), "delivery_failed")
        self.assertTrue(lifecycle.get("has_provider_receipt"))
        serialized = response.content.decode()
        self.assertNotIn("provider-secret-message-id", serialized)
        self.assertNotIn("access_token", serialized)
        self.assertNotIn("graph.facebook.com", serialized)

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
        with patch(
            "management.services.instagram_bot.send_text",
            return_value=ProviderDeliveryReceipt(True, "", "", "checkout-resend"),
        ), patch(
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
        preview = self.client.get(
            reverse(
                "management_bot_checkout_proposal_preview_api",
                kwargs={"proposal_id": self.proposal.public_id},
            )
        ).json()["proposal"]

        self.assertFalse(preview["actions"]["can_resend"])
        self.assertEqual(
            preview["actions"]["resend_blocked_reason"],
            "response_window_closed",
        )

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

    def test_meta_reviewer_cannot_read_or_mutate_checkout_workspace(self):
        reviewer = get_user_model().objects.create_user(username="checkout-meta-reviewer", password="secret")
        group, _created = Group.objects.get_or_create(name=META_REVIEWER_GROUP_NAME)
        reviewer.groups.add(group)
        self.client.force_login(reviewer)

        list_response = self.client.get(reverse("management_bot_checkout_proposals_api"))
        preview_response = self.client.get(
            reverse(
                "management_bot_checkout_proposal_preview_api",
                kwargs={"proposal_id": self.proposal.public_id},
            )
        )
        action_response = self.client.post(
            reverse(
                "management_bot_checkout_proposal_action_api",
                kwargs={"proposal_id": self.proposal.public_id},
            ),
            {"action": "copy_token"},
        )

        self.assertEqual(list_response.status_code, 403)
        self.assertEqual(preview_response.status_code, 403)
        self.assertEqual(action_response.status_code, 403)

    def test_management_bot_exposes_checkout_proposal_workspace(self):
        response = self.client.get(reverse("management_bot"))

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('id="bot-checkout-list"', body)
        self.assertIn('id="bot-checkout-preview"', body)
        self.assertIn("/bot/api/checkout-proposals/", body)
        self.assertIn("/bot/api/checkout-proposals/00000000-0000-0000-0000-000000000000/action/", body)
        self.assertIn('data-checkout-state="ready"', body)
        self.assertIn('data-checkout-state="paid"', body)
        self.assertIn('data-checkout-state="expired"', body)
        self.assertIn("const previewUrl=proposalId=>", body)
        self.assertIn("await fetch(previewUrl", body)
        self.assertIn("can_resend", body)
        self.assertIn("restoreCheckoutFocus", body)
        self.assertIn("cancelled:'Скасовано'", body)
        self.assertIn(
            "document.querySelectorAll('.bot-checkout-filter[data-checkout-state]')",
            body,
        )
        self.assertNotIn("document.querySelectorAll('[data-checkout-state]')", body)
        self.assertIn("listEl.querySelector('.bot-checkout-row')", body)
        self.assertIn("refreshEl.focus()", body)

    def test_workspace_actions_use_one_shared_capability_gate(self):
        source = Path(__file__).with_name("bot_views.py").read_text(encoding="utf-8")

        self.assertIn("def _checkout_proposal_action_capabilities", source)
        self.assertIn(
            "capabilities = _checkout_proposal_action_capabilities(proposal, now=now)",
            source,
        )
        self.assertIn('if not capabilities["can_copy_token"]', source)
        self.assertIn('if not capabilities["can_resend"]', source)
        self.assertIn('if not capabilities["can_revoke"]', source)
