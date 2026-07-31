import hashlib
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from management.models import (
    IgCheckoutAccessToken,
    IgCheckoutProposal,
    IgCheckoutProposalItem,
    IgClient,
    IgDeal,
)
from management.services.ig_commercial_episodes import ensure_episode_for_deal
from orders.models import PaymentAttempt
from orders.nova_poshta_checkout import build_city_choice_token, build_warehouse_choice_token
from storefront.models import Category, Product


class InstagramCheckoutViewTests(TestCase):
    def setUp(self):
        self.profile = IgClient.get_or_create_for_sender("private-instagram-sender")
        self.profile.display_name = "Марія"
        self.profile.username = "private_handle"
        self.profile.save(update_fields=["display_name", "username", "updated_at"])
        self.deal = IgDeal.objects.create(
            client=self.profile,
            status=IgDeal.Status.QUOTED,
            amount=Decimal("1900.00"),
            requested_payment_amount=Decimal("1700.00"),
        )
        self.episode = ensure_episode_for_deal(self.deal)
        category = Category.objects.create(name="IG checkout category", slug="ig-checkout-category")
        self.products = [
            Product.objects.create(
                title="Футболка Київ", slug="ig-kyiv-shirt", category=category,
                price=950, status="published",
            ),
            Product.objects.create(
                title="Футболка Харків", slug="ig-kharkiv-shirt", category=category,
                price=950, status="published",
            ),
        ]
        self.proposal = IgCheckoutProposal.objects.create_current(
            deal=self.deal,
            commercial_episode=self.episode,
            catalog_total=Decimal("1900.00"),
            negotiated_discount=Decimal("200.00"),
            quoted_total=Decimal("1700.00"),
            requested_payment_amount=Decimal("1700.00"),
            items_digest=hashlib.sha256(b"view-test").hexdigest(),
            allow_promo=True,
        )
        IgCheckoutProposalItem.objects.create(
            proposal=self.proposal,
            product=self.products[0],
            product_title="Футболка Київ",
            image_url="/media/catalog/kyiv-shirt.webp",
            color_code="#2255AA",
            color_label="Синій",
            size="M",
            fit_code="classic",
            fit_label="Класичний",
            quantity=1,
            catalog_unit_price=Decimal("950.00"),
            catalog_line_total=Decimal("950.00"),
            quoted_unit_price=Decimal("950.00"),
            quoted_line_total=Decimal("950.00"),
            position=0,
        )
        IgCheckoutProposalItem.objects.create(
            proposal=self.proposal,
            product=self.products[1],
            product_title="Футболка Харків",
            image_url="",
            color_code="#111111",
            color_label="Чорний",
            size="L",
            fit_code="oversize",
            fit_label="Оверсайз",
            quantity=1,
            catalog_unit_price=Decimal("950.00"),
            catalog_line_total=Decimal("950.00"),
            quoted_unit_price=Decimal("950.00"),
            quoted_line_total=Decimal("950.00"),
            position=1,
        )

    def _open(self):
        raw, _token = IgCheckoutAccessToken.issue(proposal=self.proposal)
        response = self.client.get(
            reverse("ig_checkout_token_entry", kwargs={"token": raw})
        )
        return self.client.get(response["Location"])

    def _attempt(self, *, status=PaymentAttempt.Status.PROCESSING):
        return PaymentAttempt.objects.create(
            fingerprint=hashlib.sha256(f"view-attempt:{self.proposal.pk}:{status}".encode()).hexdigest(),
            full_name="Іван Петренко",
            phone="+380501112233",
            email="ivan.petrenko@example.com",
            city="Київ",
            np_office="Відділення №12",
            np_settlement_ref="settlement-ref",
            np_city_ref="city-ref",
            np_warehouse_ref="warehouse-ref",
            pay_type=PaymentAttempt.PayType.ONLINE_FULL,
            status=status,
            cart_snapshot={"items": []},
            gross_amount=Decimal("1900.00"),
            discount_amount=Decimal("200.00"),
            payable_amount=Decimal("1700.00"),
            payment_amount=Decimal("1700.00"),
        )

    def _delivery_payload(self):
        return {
            "full_name": "Іван Петренко",
            "phone": "+380501112233",
            "email": "ivan.petrenko@example.com",
            "city": "Київ",
            "np_settlement_ref": "settlement-ref",
            "np_city_ref": "city-ref",
            "np_city_token": build_city_choice_token({
                "label": "Київ", "settlement_ref": "settlement-ref", "city_ref": "city-ref",
            }),
            "np_office": "Відділення №12",
            "np_warehouse_ref": "warehouse-ref",
            "np_warehouse_token": build_warehouse_choice_token({
                "label": "Відділення №12", "ref": "warehouse-ref", "kind": "branch", "city_ref": "city-ref",
            }),
        }

    def test_ready_page_renders_exact_products_and_delivery_form_without_instagram_pii(self):
        response = self._open()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Футболка Київ")
        self.assertContains(response, "Футболка Харків")
        self.assertContains(response, "Класичний")
        self.assertContains(response, "Оверсайз")
        self.assertContains(response, "Синій")
        self.assertContains(response, "Чорний")
        self.assertContains(response, "Марія")
        self.assertContains(response, "1700.00")
        self.assertContains(response, 'name="full_name"')
        self.assertContains(response, 'name="phone"')
        self.assertContains(response, 'name="email"')
        self.assertContains(response, 'name="np_city_token"')
        self.assertContains(response, 'name="np_warehouse_token"')
        self.assertContains(response, 'data-payment-submit')
        self.assertNotContains(response, self.profile.igsid)
        self.assertNotContains(response, self.profile.username)
        self.assertNotRegex(
            response.content.decode(),
            r'<input[^>]+name="email"[^>]+required',
        )
        self.assertContains(response, "instagram-checkout.css")
        self.assertContains(response, "instagram-checkout.js")

    def test_locked_page_masks_recipient_and_suppresses_edit_form(self):
        attempt = self._attempt()
        self.proposal.status = IgCheckoutProposal.Status.DETAILS_LOCKED
        self.proposal.details_locked_at = timezone.now()
        self.proposal.payment_attempt = attempt
        self.proposal.save(update_fields=[
            "status", "details_locked_at", "payment_attempt", "updated_at",
        ])

        response = self._open()

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Іван Петренко")
        self.assertNotContains(response, "+380501112233")
        self.assertNotContains(response, "ivan.petrenko@example.com")
        self.assertContains(response, "2233")
        self.assertContains(response, "example.com")
        self.assertNotContains(response, 'name="full_name"')
        self.assertNotContains(response, 'data-payment-submit')

    def test_non_payable_states_have_explicit_markers_and_no_payment_action(self):
        cases = (
            (IgCheckoutProposal.Status.INVOICE_CREATED, "pending"),
            (IgCheckoutProposal.Status.REVOKED, "unavailable"),
            (IgCheckoutProposal.Status.SUPERSEDED, "superseded"),
            (IgCheckoutProposal.Status.EXPIRED, "expired"),
            (IgCheckoutProposal.Status.CANCELLED, "cancellation_ambiguous"),
        )
        for status, public_state in cases:
            with self.subTest(status=status):
                self.proposal.status = status
                if status == IgCheckoutProposal.Status.SUPERSEDED:
                    replacement_deal = IgDeal.objects.create(
                        client=self.profile,
                        status=IgDeal.Status.QUOTED,
                        amount=Decimal("1700.00"),
                        requested_payment_amount=Decimal("1700.00"),
                    )
                    replacement_episode = ensure_episode_for_deal(replacement_deal)
                    replacement = IgCheckoutProposal.objects.create_current(
                        deal=replacement_deal,
                        commercial_episode=replacement_episode,
                        catalog_total=Decimal("1700.00"),
                        quoted_total=Decimal("1700.00"),
                        requested_payment_amount=Decimal("1700.00"),
                        items_digest=hashlib.sha256(b"replacement").hexdigest(),
                    )
                    self.proposal.superseded_by = replacement
                self.proposal.save()
                response = self._open()
                self.assertContains(response, f'data-checkout-state="{public_state}"')
                self.assertNotContains(response, 'data-payment-submit')

                self.proposal.refresh_from_db()
                if status == IgCheckoutProposal.Status.SUPERSEDED:
                    self.proposal.superseded_by = None
                self.proposal.status = IgCheckoutProposal.Status.VIEWED
                self.proposal.save()

    def test_english_locale_uses_english_checkout_copy(self):
        self.proposal.locale = "en"
        self.proposal.save(update_fields=["locale", "updated_at"])

        response = self._open()

        self.assertContains(response, "Review your order")
        self.assertContains(response, "Email for receipt")
        self.assertContains(response, "Copy link")
        self.assertNotContains(response, "Copy payment link")

    def test_post_creates_one_standard_attempt_from_frozen_proposal(self):
        raw, _token = IgCheckoutAccessToken.issue(proposal=self.proposal)
        entry = self.client.get(reverse("ig_checkout_token_entry", kwargs={"token": raw}))
        self.client.get(entry["Location"])
        payload = self._delivery_payload()
        with patch("storefront.views.monobank._monobank_api_request", return_value={
            "invoiceId": "ig-invoice-1", "pageUrl": "https://pay.example/ig-1",
        }) as provider, patch(
            "orders.facebook_conversions_service.get_facebook_conversions_service"
        ) as fb, patch(
            "orders.telegram_notifications.TelegramNotifier.send_payment_attempt_notification",
            return_value=True,
        ):
            fb.return_value.send_add_payment_info_event.return_value = True
            response = self.client.post(
                reverse("ig_checkout_proposal", kwargs={"proposal_id": self.proposal.public_id}),
                data=payload,
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://pay.example/ig-1")
        provider.assert_called_once()
        attempt = PaymentAttempt.objects.get()
        self.assertEqual(attempt.status, PaymentAttempt.Status.PROCESSING)
        self.assertEqual(attempt.gross_amount, Decimal("1900.00"))
        self.assertEqual(attempt.discount_amount, Decimal("200.00"))
        self.assertEqual(attempt.payable_amount, Decimal("1700.00"))
        self.assertEqual(attempt.invoice_payload["request"]["merchantPaymInfo"]["customerEmails"], [payload["email"]])
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.status, IgCheckoutProposal.Status.INVOICE_CREATED)

    def test_repeated_post_reuses_invoice_without_second_provider_call(self):
        raw, _token = IgCheckoutAccessToken.issue(proposal=self.proposal)
        entry = self.client.get(reverse("ig_checkout_token_entry", kwargs={"token": raw}))
        self.client.get(entry["Location"])
        payload = self._delivery_payload()
        with patch("storefront.views.monobank._monobank_api_request", return_value={
            "invoiceId": "ig-invoice-2", "pageUrl": "https://pay.example/ig-2",
        }) as provider, patch(
            "orders.facebook_conversions_service.get_facebook_conversions_service"
        ) as fb, patch(
            "orders.telegram_notifications.TelegramNotifier.send_payment_attempt_notification",
            return_value=True,
        ):
            fb.return_value.send_add_payment_info_event.return_value = True
            first = self.client.post(
                reverse("ig_checkout_proposal", kwargs={"proposal_id": self.proposal.public_id}),
                data=payload,
            )
            second = self.client.post(
                reverse("ig_checkout_proposal", kwargs={"proposal_id": self.proposal.public_id}),
                data=payload,
            )

        self.assertEqual(first["Location"], second["Location"])
        self.assertEqual(provider.call_count, 1)
        self.assertEqual(PaymentAttempt.objects.count(), 1)

    def test_verified_attempt_binds_order_and_lifecycle_event(self):
        raw, _token = IgCheckoutAccessToken.issue(proposal=self.proposal)
        entry = self.client.get(reverse("ig_checkout_token_entry", kwargs={"token": raw}))
        self.client.get(entry["Location"])
        with patch("storefront.views.monobank._monobank_api_request", return_value={
            "invoiceId": "ig-invoice-3", "pageUrl": "https://pay.example/ig-3",
        }), patch(
            "orders.facebook_conversions_service.get_facebook_conversions_service"
        ) as fb, patch(
            "orders.telegram_notifications.TelegramNotifier.send_payment_attempt_notification",
            return_value=True,
        ):
            fb.return_value.send_add_payment_info_event.return_value = True
            self.client.post(
                reverse("ig_checkout_proposal", kwargs={"proposal_id": self.proposal.public_id}),
                data=self._delivery_payload(),
            )
        attempt = PaymentAttempt.objects.get()
        from storefront.views.monobank import _apply_payment_attempt_status
        order, created = _apply_payment_attempt_status(
            attempt, "success", payload={"status": "success", "paidAmount": 170000}, source="test"
        )

        self.assertTrue(created)
        self.assertIsNotNone(order)
        self.proposal.refresh_from_db()
        self.deal.refresh_from_db()
        self.assertEqual(self.proposal.status, IgCheckoutProposal.Status.PAID)
        self.assertEqual(self.deal.order_id, order.pk)
        self.assertEqual(self.deal.status, IgDeal.Status.ORDER_CREATED)
        self.assertEqual(order.instagram_attribution.client_id, self.profile.pk)
        self.assertEqual(order.instagram_lifecycle_events.count(), 1)

    def test_lifecycle_dispatch_sends_payment_and_ttn_once_in_response_window(self):
        raw, _token = IgCheckoutAccessToken.issue(proposal=self.proposal)
        entry = self.client.get(reverse("ig_checkout_token_entry", kwargs={"token": raw}))
        self.client.get(entry["Location"])
        with patch("storefront.views.monobank._monobank_api_request", return_value={
            "invoiceId": "ig-invoice-lifecycle", "pageUrl": "https://pay.example/ig-lifecycle",
        }), patch("orders.facebook_conversions_service.get_facebook_conversions_service") as fb, patch(
            "orders.telegram_notifications.TelegramNotifier.send_payment_attempt_notification",
            return_value=True,
        ):
            fb.return_value.send_add_payment_info_event.return_value = True
            self.client.post(
                reverse("ig_checkout_proposal", kwargs={"proposal_id": self.proposal.public_id}),
                data=self._delivery_payload(),
            )
        attempt = PaymentAttempt.objects.get()
        from storefront.views.monobank import _apply_payment_attempt_status
        order, _created = _apply_payment_attempt_status(
            attempt, "success", payload={"status": "success", "paidAmount": 170000}, source="test"
        )
        self.profile.last_message_at = timezone.now()
        self.profile.save(update_fields=["last_message_at", "updated_at"])
        from management.ig_bot_models import IgLifecycleEvent
        from management.services.ig_lifecycle import dispatch_lifecycle_event
        from orders.nova_poshta_service import NovaPoshtaService
        from orders.status_management import apply_order_status_update
        with patch("management.services.instagram_bot.send_text", return_value=(True, "", "")) as sender:
            payment_event = IgLifecycleEvent.objects.get(kind=IgLifecycleEvent.Kind.PAYMENT_VERIFIED)
            self.assertEqual(dispatch_lifecycle_event(payment_event.pk), IgLifecycleEvent.State.SENT)

            # The production management transition emits TTN only after the
            # order row commits, and repeated saves with the same TTN are no-ops.
            with self.captureOnCommitCallbacks(execute=True):
                apply_order_status_update(
                    order,
                    status="ship",
                    tracking_number="20450012345678",
                )
            self.assertEqual(sender.call_count, 2)
            self.assertEqual(
                IgLifecycleEvent.objects.filter(
                    order=order, kind=IgLifecycleEvent.Kind.TTN_CREATED
                ).count(),
                1,
            )
            with self.captureOnCommitCallbacks(execute=True):
                apply_order_status_update(
                    order,
                    status="ship",
                    tracking_number="20450012345678",
                )
            self.assertEqual(sender.call_count, 2)

            order.refresh_from_db()
            service = NovaPoshtaService()
            self.assertEqual(order.tracking_number, "20450012345678")
            with patch.object(
                service,
                "get_tracking_info",
                return_value={
                    "Number": "20450012345678",
                    "Status": "Відправлення отримано",
                    "StatusCode": 9,
                    "StatusDescription": "одержувачем",
                },
            ), patch.object(service, "_send_delivery_notification"), patch.object(
                service, "_send_admin_delivery_notification"
            ), patch.object(service, "_record_purchase_action"):
                self.assertTrue(service.update_order_tracking_status(order))
                self.assertFalse(service.update_order_tracking_status(order))

        self.assertEqual(sender.call_count, 3)
        self.assertEqual(
            IgLifecycleEvent.objects.filter(order=order, kind=IgLifecycleEvent.Kind.TTN_CREATED).count(),
            1,
        )
        self.assertEqual(
            IgLifecycleEvent.objects.filter(
                order=order,
                kind=IgLifecycleEvent.Kind.DELIVERED_REVIEW_REQUESTED,
            ).count(),
            1,
        )

    def test_lifecycle_outside_response_window_is_waiting_window(self):
        from datetime import timedelta
        from management.ig_bot_models import IgLifecycleEvent
        from management.services.ig_lifecycle import dispatch_lifecycle_event, ensure_lifecycle_event
        from orders.models import Order

        order = Order.objects.create(
            full_name="Іван Петренко", phone="+380501112233", city="Київ",
            np_office="Відділення №12", pay_type="online_full", payment_status="paid",
            total_sum=Decimal("1700.00"), status="ship", tracking_number="20450012345678",
        )
        attempt = self._attempt(status=PaymentAttempt.Status.CONVERTED)
        attempt.order = order
        attempt.save(update_fields=["order", "updated"])
        self.proposal.payment_attempt = attempt
        self.proposal.status = IgCheckoutProposal.Status.PAID
        self.proposal.paid_at = timezone.now()
        self.proposal.save(update_fields=["payment_attempt", "status", "paid_at", "updated_at"])
        from management.services.ig_order_links import create_order_attribution
        create_order_attribution(
            order, client=self.profile, deal=self.deal,
            creation_mode="provider_auto", payment_source="provider_attempt",
        )
        self.profile.last_message_at = timezone.now() - timedelta(hours=30)
        self.profile.save(update_fields=["last_message_at", "updated_at"])
        event, _created = ensure_lifecycle_event(
            order,
            IgLifecycleEvent.Kind.TTN_CREATED,
            payload={"tracking_number": order.tracking_number, "order_number": order.order_number},
        )
        with patch("management.services.instagram_bot.notify_manager") as notify:
            self.assertEqual(dispatch_lifecycle_event(event.pk), IgLifecycleEvent.State.WAITING_WINDOW)
        notify.assert_called_once()
