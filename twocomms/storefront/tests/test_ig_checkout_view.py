import hashlib
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.core import signing
from django.urls import reverse
from django.utils import timezone

from management.models import (
    IgCheckoutAccessToken,
    IgCheckoutInventoryReservation,
    IgCheckoutProposal,
    IgCheckoutProposalItem,
    IgClient,
    IgDeal,
    InstagramBotSettings,
)
from management.services.ig_commercial_episodes import ensure_episode_for_deal
from orders.models import Order, PaymentAttempt
from orders.nova_poshta_checkout import build_city_choice_token, build_warehouse_choice_token
from storefront.models import Category, Product, PromoCode, PromoCodeGroup, PromoCodeUsage


class InstagramCheckoutViewTests(TestCase):
    def setUp(self):
        # Bearer-entry throttling is intentionally IP-scoped in production;
        # isolate the in-memory test cache so one class cannot consume another
        # test's request budget.
        cache.clear()
        self.profile = IgClient.get_or_create_for_sender("private-instagram-sender")
        self.profile.display_name = "Марія"
        self.profile.username = "private_handle"
        self.profile.save(update_fields=["display_name", "username", "updated_at"])
        self.bot_settings = InstagramBotSettings.load()
        self.bot_settings.is_enabled = True
        self.bot_settings.save(update_fields=["is_enabled", "updated_at"])
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
        self.assertContains(response, 'data-view-content-event-id=')
        self.assertContains(response, 'analytics-loader.js')
        self.assertContains(response, 'data-meta-pixel-id=')
        self.assertRegex(
            response.content.decode(),
            r'<input[^>]+name="email"',
        )
        self.assertNotRegex(
            response.content.decode(),
            r'<input[^>]+name="email"[^>]+\srequired(?:\s|=|>)',
        )
        self.assertContains(response, "instagram-checkout.css")
        self.assertContains(response, "instagram-checkout.js")

    def test_ready_page_names_monobank_in_protected_payment_copy_for_each_locale(self):
        expected_copy = {
            "uk": "Дані картки вводяться на захищеній сторінці Monobank",
            "ru": "Данные карты вводятся на защищенной странице Monobank",
            "en": "Card details are entered on Monobank&#x27;s secure page",
        }

        for locale, expected in expected_copy.items():
            with self.subTest(locale=locale):
                self.proposal.locale = locale
                self.proposal.save(update_fields=["locale", "updated_at"])

                response = self._open()

                self.assertContains(response, expected)

    def test_ready_page_marks_receipt_email_optional_for_each_locale(self):
        expected_copy = {
            "uk": ("Email для чека", "Необов'язково", "Якщо вкажете його"),
            "ru": ("Email для чека", "Необязательно", "Если укажете его"),
            "en": ("Email for receipt", "Not required", "If you enter it"),
        }

        for locale, expected in expected_copy.items():
            with self.subTest(locale=locale):
                self.proposal.locale = locale
                self.proposal.save(update_fields=["locale", "updated_at"])

                response = self._open()

                self.assertContains(response, expected[0])
                self.assertContains(response, expected[1], html=(locale == "uk"))
                self.assertContains(response, expected[2])
                self.assertNotRegex(
                    response.content.decode(),
                    r'<input[^>]+name="email"[^>]+\srequired(?:\s|=|>)',
                )
                self.assertContains(response, 'name="email"')
                self.assertContains(response, 'aria-required="false"')

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

    def test_existing_invoice_can_be_continued_from_forwarded_grant(self):
        attempt = self._attempt()
        attempt.invoice_url = "https://pay.example/existing-invoice"
        attempt.monobank_invoice_id = "existing-invoice"
        attempt.save(update_fields=["invoice_url", "monobank_invoice_id", "updated"])
        self.proposal.status = IgCheckoutProposal.Status.INVOICE_CREATED
        self.proposal.details_locked_at = timezone.now()
        self.proposal.payment_attempt = attempt
        self.proposal.save(update_fields=[
            "status", "details_locked_at", "payment_attempt", "updated_at",
        ])

        response = self._open()

        self.assertContains(response, 'data-payment-rail')
        self.assertContains(response, 'data-payment-continue')
        self.assertContains(response, 'data-payment-trust')
        self.assertContains(response, 'data-checkout-state-banner')
        self.assertContains(response, 'data-countdown')
        self.assertRegex(
            response.content.decode(),
            r'data-payment-amount[\s\S]*?1700\.00 UAH',
        )
        self.assertContains(response, attempt.invoice_url)
        self.assertNotContains(response, 'data-payment-submit')

    def test_clean_grant_tracks_pre_invoice_revision_without_404(self):
        self._open()
        self.proposal.revision += 1
        self.proposal.items_digest = hashlib.sha256(b"new-revision").hexdigest()
        self.proposal.save(update_fields=["revision", "items_digest", "updated_at"])

        response = self.client.get(
            reverse("ig_checkout_proposal", kwargs={"proposal_id": self.proposal.public_id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'data-proposal-revision="{self.proposal.revision}"')

    def test_invalid_token_rate_limit_bucket_does_not_depend_on_candidate_token(self):
        with patch("storefront.views.ig_checkout.cache") as checkout_cache:
            checkout_cache.add.return_value = True
            first = self.client.get(
                reverse("ig_checkout_token_entry", kwargs={"token": "invalid-token-one"})
            )
            second = self.client.get(
                reverse("ig_checkout_token_entry", kwargs={"token": "invalid-token-two"})
            )

        self.assertEqual(first.status_code, 410)
        self.assertEqual(second.status_code, 410)
        self.assertEqual(checkout_cache.add.call_count, 2)
        self.assertEqual(
            checkout_cache.add.call_args_list[0].args[0],
            checkout_cache.add.call_args_list[1].args[0],
        )

    @override_settings(
        SIMPLE_RATE_LIMIT_TRUSTED_PROXY_CIDRS=("127.0.0.0/8", "::1/128"),
    )
    def test_checkout_rate_limit_separates_clients_behind_trusted_proxy(self):
        from storefront.views.ig_checkout import _rate_limited

        factory = RequestFactory()
        first = factory.get(
            "/checkout/",
            REMOTE_ADDR="::1",
            HTTP_X_FORWARDED_FOR="198.51.100.10, 127.0.0.2",
        )
        second = factory.get(
            "/checkout/",
            REMOTE_ADDR="::1",
            HTTP_X_FORWARDED_FOR="198.51.100.11, 127.0.0.2",
        )

        with patch("storefront.views.ig_checkout.cache") as checkout_cache:
            checkout_cache.add.return_value = True
            self.assertFalse(_rate_limited(first, "submit", identity="proposal", limit=1, window=60))
            self.assertFalse(_rate_limited(second, "submit", identity="proposal", limit=1, window=60))

        first_key = checkout_cache.add.call_args_list[0].args[0]
        second_key = checkout_cache.add.call_args_list[1].args[0]
        self.assertNotEqual(first_key, second_key)

    def test_paid_browser_sees_verified_order_and_delivery_summary(self):
        order = Order.objects.create(
            full_name="Іван Петренко",
            phone="+380501112233",
            email="ivan.petrenko@example.com",
            city="Київ",
            np_office="Відділення №12",
            pay_type="online_full",
            payment_status="paid",
            total_sum=Decimal("1700.00"),
        )
        attempt = self._attempt(status=PaymentAttempt.Status.CONVERTED)
        attempt.order = order
        attempt.save(update_fields=["order", "updated"])
        self.proposal.payment_attempt = attempt
        self.proposal.status = IgCheckoutProposal.Status.PAID
        self.proposal.paid_at = timezone.now()
        self.proposal.save(update_fields=["payment_attempt", "status", "paid_at", "updated_at"])
        session = self.client.session
        session["ig_checkout_paid_attempt_id"] = attempt.pk
        session.save()

        response = self._open()

        self.assertContains(response, order.order_number)
        self.assertContains(response, order.city)
        self.assertContains(response, order.np_office)
        self.assertContains(response, 'data-paid-summary')
        self.assertContains(response, 'data-state-icon="success"')
        self.assertNotContains(response, 'data-state-icon="attention"')

    def test_non_payable_states_have_explicit_markers_and_no_payment_action(self):
        cases = (
            (IgCheckoutProposal.Status.DETAILS_LOCKED, "locked", "progress"),
            (IgCheckoutProposal.Status.INVOICE_CREATED, "pending", "progress"),
            (IgCheckoutProposal.Status.REVOKED, "unavailable", "attention"),
            (IgCheckoutProposal.Status.SUPERSEDED, "superseded", "attention"),
            (IgCheckoutProposal.Status.EXPIRED, "expired", "attention"),
            (IgCheckoutProposal.Status.CANCELLED, "cancellation_ambiguous", "attention"),
        )
        for status, public_state, state_icon in cases:
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
                self.assertContains(response, f'data-state-icon="{state_icon}"')
                self.assertNotContains(response, 'data-state-icon="success"')
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
        self.assertContains(response, "Not required")
        self.assertContains(response, "Copy link")
        self.assertNotContains(response, "Copy payment link")

    def test_checkout_language_switcher_keeps_clean_proposal_url_and_localizes_form(self):
        self._open()

        switched = self.client.get(
            f"{reverse('ig_checkout_proposal', kwargs={'proposal_id': self.proposal.public_id})}?lang=en"
        )

        self.assertEqual(switched.status_code, 200)
        self.assertContains(switched, '<html lang="en"', html=False)
        self.assertContains(switched, "Review your order")
        self.assertContains(switched, "?lang=en")
        self.assertContains(switched, "?lang=ru")
        self.assertContains(switched, "img/lang/ptn.png")
        self.assertNotContains(switched, "offer/a/")

    def test_invalid_checkout_language_falls_back_to_proposal_locale(self):
        self._open()

        response = self.client.get(
            f"{reverse('ig_checkout_proposal', kwargs={'proposal_id': self.proposal.public_id})}?lang=de"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<html lang="uk"', html=False)
        self.assertContains(response, "Перевірте замовлення")

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
        self.assertEqual(attempt.email, payload["email"])
        self.assertEqual(attempt.status, PaymentAttempt.Status.PROCESSING)
        self.assertEqual(attempt.gross_amount, Decimal("1900.00"))
        self.assertEqual(attempt.discount_amount, Decimal("200.00"))
        self.assertEqual(attempt.payable_amount, Decimal("1700.00"))
        self.assertEqual(attempt.invoice_expires_at, self.proposal.expires_at)
        self.assertEqual(attempt.invoice_payload["request"]["merchantPaymInfo"]["customerEmails"], [payload["email"]])
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.status, IgCheckoutProposal.Status.INVOICE_CREATED)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.stage, IgClient.Stage.PAYMENT_PENDING)

    def test_post_without_receipt_email_creates_invoice_and_persists_blank_email(self):
        raw, _token = IgCheckoutAccessToken.issue(proposal=self.proposal)
        entry = self.client.get(reverse("ig_checkout_token_entry", kwargs={"token": raw}))
        self.client.get(entry["Location"])
        payload = self._delivery_payload()
        payload.pop("email")
        with patch("storefront.views.monobank._monobank_api_request", return_value={
            "invoiceId": "ig-no-email", "pageUrl": "https://pay.example/ig-no-email",
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
        self.assertEqual(response["Location"], "https://pay.example/ig-no-email")
        provider.assert_called_once()
        attempt = PaymentAttempt.objects.get()
        self.assertEqual(attempt.email, "")
        self.assertNotIn(
            "customerEmails",
            attempt.invoice_payload["request"]["merchantPaymInfo"],
        )
        from storefront.views.monobank import _apply_payment_attempt_status

        order, created = _apply_payment_attempt_status(
            attempt,
            "success",
            payload={"status": "success", "paidAmount": 170000},
            source="test",
        )
        self.assertTrue(created)
        self.assertEqual(order.email, "")

    def test_post_with_whitespace_receipt_email_creates_invoice_without_customer_emails(self):
        raw, _token = IgCheckoutAccessToken.issue(proposal=self.proposal)
        entry = self.client.get(reverse("ig_checkout_token_entry", kwargs={"token": raw}))
        self.client.get(entry["Location"])
        payload = self._delivery_payload()
        payload["email"] = "   "

        with patch("storefront.views.monobank._monobank_api_request", return_value={
            "invoiceId": "ig-blank-email", "pageUrl": "https://pay.example/ig-blank-email",
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
        provider.assert_called_once()
        attempt = PaymentAttempt.objects.get()
        self.assertEqual(attempt.email, "")
        self.assertNotIn(
            "customerEmails",
            attempt.invoice_payload["request"]["merchantPaymInfo"],
        )

    def test_post_rejects_malformed_nonblank_email_before_provider_call(self):
        raw, _token = IgCheckoutAccessToken.issue(proposal=self.proposal)
        entry = self.client.get(reverse("ig_checkout_token_entry", kwargs={"token": raw}))
        self.client.get(entry["Location"])
        payload = self._delivery_payload()
        payload["email"] = "not-an-email"

        with patch("storefront.views.monobank._monobank_api_request") as provider:
            response = self.client.post(
                reverse("ig_checkout_proposal", kwargs={"proposal_id": self.proposal.public_id}),
                data=payload,
            )

        self.assertEqual(response.status_code, 400)
        provider.assert_not_called()
        self.assertIn("email", response.content.decode().lower())
        self.assertFalse(PaymentAttempt.objects.exists())

    def test_post_rejects_proposal_that_expires_after_page_was_opened(self):
        raw, _token = IgCheckoutAccessToken.issue(proposal=self.proposal)
        entry = self.client.get(reverse("ig_checkout_token_entry", kwargs={"token": raw}))
        self.client.get(entry["Location"])
        self.proposal.expires_at = timezone.now() - timedelta(seconds=1)
        self.proposal.save(update_fields=["expires_at", "updated_at"])

        with patch("storefront.views.monobank._monobank_api_request") as provider:
            response = self.client.post(
                reverse("ig_checkout_proposal", kwargs={"proposal_id": self.proposal.public_id}),
                data=self._delivery_payload(),
                HTTP_ACCEPT="application/json",
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "expired")
        provider.assert_not_called()
        self.assertFalse(PaymentAttempt.objects.exists())

    def test_post_blocks_catalog_drift_before_provider_call(self):
        from management.services.ig_checkout import create_or_update_proposal

        deal = IgDeal.objects.create(
            client=self.profile,
            status=IgDeal.Status.QUOTED,
            amount=Decimal("950.00"),
            requested_payment_amount=Decimal("950.00"),
        )
        proposal = create_or_update_proposal(
            client=self.profile,
            deal=deal,
            item_specs=[{"product_id": self.products[0].pk, "qty": 1, "size": "M"}],
            pay_type="online_full",
        )
        self.products[0].price = Decimal("1200.00")
        self.products[0].save(update_fields=["price"])
        raw, _token = IgCheckoutAccessToken.issue(proposal=proposal)
        entry = self.client.get(reverse("ig_checkout_token_entry", kwargs={"token": raw}))
        self.client.get(entry["Location"])
        with patch("storefront.views.monobank._monobank_api_request") as provider:
            response = self.client.post(
                reverse("ig_checkout_proposal", kwargs={"proposal_id": proposal.public_id}),
                data=self._delivery_payload(),
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("змінилися", response.content.decode())
        provider.assert_not_called()
        proposal.refresh_from_db()
        self.assertIsNone(proposal.payment_attempt_id)

    def test_json_submit_returns_dedup_event_ids_after_durable_invoice(self):
        raw, _token = IgCheckoutAccessToken.issue(proposal=self.proposal)
        entry = self.client.get(reverse("ig_checkout_token_entry", kwargs={"token": raw}))
        self.client.get(entry["Location"])
        with patch("storefront.views.monobank._monobank_api_request", return_value={
            "invoiceId": "ig-json-analytics", "pageUrl": "https://pay.example/ig-json-analytics",
        }), patch("orders.facebook_conversions_service.get_facebook_conversions_service") as fb, patch(
            "orders.telegram_notifications.TelegramNotifier.send_payment_attempt_notification",
            return_value=True,
        ):
            fb.return_value.send_add_payment_info_event.return_value = True
            response = self.client.post(
                reverse("ig_checkout_proposal", kwargs={"proposal_id": self.proposal.public_id}),
                data=self._delivery_payload(),
                HTTP_ACCEPT="application/json",
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["invoice_url"].startswith("https://pay.example/"))
        self.assertTrue(payload["add_payment_event_id"].startswith("attempt-"))
        self.assertEqual(len(payload["initiate_event_id"]), 40)
        attempt = PaymentAttempt.objects.get()
        self.assertEqual(
            attempt.tracking_payload["ig_checkout_grant_id"],
            self.client.session.get(f"ig_checkout_grant:{self.proposal.public_id}") and
            signing.loads(
                self.client.session[f"ig_checkout_grant:{self.proposal.public_id}"],
                salt="twocomms.instagram-checkout.grant.v1",
            )["grant_id"],
        )

    def test_status_endpoint_exposes_bounded_public_states(self):
        raw, _token = IgCheckoutAccessToken.issue(proposal=self.proposal)
        entry = self.client.get(reverse("ig_checkout_token_entry", kwargs={"token": raw}))
        self.client.get(entry["Location"])
        response = self.client.get(
            reverse("ig_checkout_status", kwargs={"proposal_id": self.proposal.public_id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(response.json()["state"], {"pending", "verified", "failed", "expired", "cancellation_ambiguous"})
        self.assertNotIn(response.json()["state"], {"ready", "locked", "superseded"})

    def test_status_endpoint_exposes_cancellation_ambiguity_without_payment_action(self):
        attempt = self._attempt(status=PaymentAttempt.Status.PROCESSING)
        attempt.event_state = {"invoice_creation_ambiguous": True}
        attempt.save(update_fields=["event_state", "updated"])
        self.proposal.status = IgCheckoutProposal.Status.DETAILS_LOCKED
        self.proposal.details_locked_at = timezone.now()
        self.proposal.payment_attempt = attempt
        self.proposal.save(update_fields=[
            "status", "details_locked_at", "payment_attempt", "updated_at",
        ])
        raw, _token = IgCheckoutAccessToken.issue(proposal=self.proposal)
        entry = self.client.get(reverse("ig_checkout_token_entry", kwargs={"token": raw}))
        self.client.get(entry["Location"])

        response = self.client.get(
            reverse("ig_checkout_status", kwargs={"proposal_id": self.proposal.public_id})
        )
        page = self.client.get(
            reverse("ig_checkout_proposal", kwargs={"proposal_id": self.proposal.public_id})
        )

        self.assertEqual(response.json()["state"], "cancellation_ambiguous")
        self.assertEqual(response.json()["ui_state"], "cancellation_ambiguous")
        self.assertContains(page, 'data-checkout-state="cancellation_ambiguous"')
        self.assertNotContains(page, "data-payment-submit")
        self.assertNotContains(page, "data-payment-continue")

    def test_anonymous_payer_cannot_use_account_scoped_promo(self):
        promo = PromoCode.objects.create(
            code="ACCOUNT100",
            discount_type="fixed",
            discount_value=Decimal("100.00"),
            one_time_per_user=True,
        )
        raw, _token = IgCheckoutAccessToken.issue(proposal=self.proposal)
        entry = self.client.get(reverse("ig_checkout_token_entry", kwargs={"token": raw}))
        self.client.get(entry["Location"])
        payload = self._delivery_payload()
        payload["promo_code"] = promo.code

        with patch("storefront.views.monobank._monobank_api_request") as provider:
            response = self.client.post(
                reverse("ig_checkout_proposal", kwargs={"proposal_id": self.proposal.public_id}),
                data=payload,
                HTTP_ACCEPT="application/json",
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "promo_requires_account")
        provider.assert_not_called()
        self.assertFalse(PaymentAttempt.objects.exists())

    def test_anonymous_payer_cannot_use_one_per_account_promo_group(self):
        group = PromoCodeGroup.objects.create(
            name="Account scoped IG group", one_per_account=True
        )
        promo = PromoCode.objects.create(
            code="GROUPACCOUNT100",
            discount_type="fixed",
            discount_value=Decimal("100.00"),
            one_time_per_user=False,
            group=group,
        )
        raw, _token = IgCheckoutAccessToken.issue(proposal=self.proposal)
        entry = self.client.get(reverse("ig_checkout_token_entry", kwargs={"token": raw}))
        self.client.get(entry["Location"])
        payload = self._delivery_payload()
        payload["promo_code"] = promo.code

        with patch("storefront.views.monobank._monobank_api_request") as provider:
            response = self.client.post(
                reverse("ig_checkout_proposal", kwargs={"proposal_id": self.proposal.public_id}),
                data=payload,
                HTTP_ACCEPT="application/json",
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "promo_requires_account")
        provider.assert_not_called()

    def test_authenticated_payer_uses_account_scoped_promo_only_once(self):
        user = get_user_model().objects.create_user(
            username="ig-promo-buyer",
            email="promo@example.com",
            password="test-password",
        )
        promo = PromoCode.objects.create(
            code="ONCE100",
            discount_type="fixed",
            discount_value=Decimal("100.00"),
            one_time_per_user=True,
        )
        self.client.force_login(user)
        raw, _token = IgCheckoutAccessToken.issue(proposal=self.proposal)
        entry = self.client.get(reverse("ig_checkout_token_entry", kwargs={"token": raw}))
        self.client.get(entry["Location"])
        payload = self._delivery_payload()
        payload["promo_code"] = promo.code

        with patch("storefront.views.monobank._monobank_api_request", return_value={
            "invoiceId": "ig-promo-invoice", "pageUrl": "https://pay.example/ig-promo",
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
        provider.assert_called_once()
        attempt = PaymentAttempt.objects.get()
        self.assertEqual(attempt.user_id, user.pk)
        self.assertEqual(attempt.payment_amount, Decimal("1600.00"))

        # A previous account-scoped usage must fail closed before any second
        # provider request; it can never become an unrestricted guest promo.
        second_deal = IgDeal.objects.create(
            client=self.profile,
            status=IgDeal.Status.QUOTED,
            amount=Decimal("950.00"),
            requested_payment_amount=Decimal("950.00"),
        )
        second_episode = ensure_episode_for_deal(second_deal)
        second_proposal = IgCheckoutProposal.objects.create_current(
            deal=second_deal,
            commercial_episode=second_episode,
            catalog_total=Decimal("950.00"),
            quoted_total=Decimal("950.00"),
            requested_payment_amount=Decimal("950.00"),
            items_digest=hashlib.sha256(b"second-promo-proposal").hexdigest(),
            allow_promo=True,
        )
        IgCheckoutProposalItem.objects.create(
            proposal=second_proposal,
            product=self.products[0],
            product_title=self.products[0].title,
            size="M",
            quantity=1,
            catalog_unit_price=Decimal("950.00"),
            catalog_line_total=Decimal("950.00"),
            quoted_unit_price=Decimal("950.00"),
            quoted_line_total=Decimal("950.00"),
            position=0,
        )
        PromoCodeUsage.objects.create(user=user, promo_code=promo)
        raw, _token = IgCheckoutAccessToken.issue(proposal=second_proposal)
        entry = self.client.get(reverse("ig_checkout_token_entry", kwargs={"token": raw}))
        self.client.get(entry["Location"])
        with patch("storefront.views.monobank._monobank_api_request") as second_provider:
            rejected = self.client.post(
                reverse("ig_checkout_proposal", kwargs={"proposal_id": second_proposal.public_id}),
                data=payload,
                HTTP_ACCEPT="application/json",
            )

        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(rejected.json()["error"], "promo_invalid")
        second_provider.assert_not_called()

    def test_authenticated_payer_cannot_reserve_two_codes_from_one_account_group(self):
        user = get_user_model().objects.create_user(
            username="ig-group-promo-buyer",
            email="group-promo@example.com",
            password="test-password",
        )
        group = PromoCodeGroup.objects.create(
            name="One active IG reservation", one_per_account=True
        )
        reserved_promo = PromoCode.objects.create(
            code="GROUPFIRST",
            discount_type="fixed",
            discount_value=Decimal("100.00"),
            group=group,
        )
        requested_promo = PromoCode.objects.create(
            code="GROUPSECOND",
            discount_type="fixed",
            discount_value=Decimal("100.00"),
            group=group,
        )
        reserved_attempt = self._attempt()
        reserved_attempt.user = user
        reserved_attempt.promo_code = reserved_promo
        reserved_attempt.event_state = {
            "promo_reservation": {
                "promo_id": reserved_promo.pk,
                "state": "reserved",
            }
        }
        reserved_attempt.save(update_fields=["user", "promo_code", "event_state", "updated"])

        self.client.force_login(user)
        raw, _token = IgCheckoutAccessToken.issue(proposal=self.proposal)
        entry = self.client.get(reverse("ig_checkout_token_entry", kwargs={"token": raw}))
        self.client.get(entry["Location"])
        payload = self._delivery_payload()
        payload["promo_code"] = requested_promo.code

        with patch("storefront.views.monobank._monobank_api_request") as provider:
            response = self.client.post(
                reverse("ig_checkout_proposal", kwargs={"proposal_id": self.proposal.public_id}),
                data=payload,
                HTTP_ACCEPT="application/json",
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "promo_invalid")
        provider.assert_not_called()
        self.assertEqual(PaymentAttempt.objects.count(), 1)

    def test_inactive_promo_group_is_rejected_for_assisted_checkout(self):
        group = PromoCodeGroup.objects.create(
            name="Inactive IG group", is_active=False, one_per_account=False
        )
        promo = PromoCode.objects.create(
            code="INACTIVEGROUP",
            discount_type="fixed",
            discount_value=Decimal("100.00"),
            group=group,
        )
        raw, _token = IgCheckoutAccessToken.issue(proposal=self.proposal)
        entry = self.client.get(reverse("ig_checkout_token_entry", kwargs={"token": raw}))
        self.client.get(entry["Location"])
        payload = self._delivery_payload()
        payload["promo_code"] = promo.code

        with patch("storefront.views.monobank._monobank_api_request") as provider:
            response = self.client.post(
                reverse("ig_checkout_proposal", kwargs={"proposal_id": self.proposal.public_id}),
                data=payload,
                HTTP_ACCEPT="application/json",
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "promo_invalid")
        provider.assert_not_called()

    def test_prepayment_proposal_uses_generic_payment_attempt_amount(self):
        self.proposal.pay_type = IgCheckoutProposal.PayType.PREPAYMENT
        self.proposal.requested_payment_amount = Decimal("600.00")
        self.proposal.save(update_fields=["pay_type", "requested_payment_amount", "updated_at"])
        raw, _token = IgCheckoutAccessToken.issue(proposal=self.proposal)
        entry = self.client.get(reverse("ig_checkout_token_entry", kwargs={"token": raw}))
        page = self.client.get(entry["Location"])
        self.assertContains(page, 'data-analytics-value="1700.00"')
        self.assertContains(page, "Сума до сплати зараз")
        self.assertContains(page, "600.00 UAH")
        with patch("storefront.views.monobank._monobank_api_request", return_value={
            "invoiceId": "ig-prepay-1", "pageUrl": "https://pay.example/ig-prepay-1",
        }) as provider, patch(
            "orders.facebook_conversions_service.get_facebook_conversions_service"
        ) as fb, patch(
            "orders.telegram_notifications.TelegramNotifier.send_payment_attempt_notification",
            return_value=True,
        ):
            fb.return_value.send_add_payment_info_event.return_value = True
            response = self.client.post(
                reverse("ig_checkout_proposal", kwargs={"proposal_id": self.proposal.public_id}),
                data=self._delivery_payload(),
            )

        self.assertEqual(response["Location"], "https://pay.example/ig-prepay-1")
        provider.assert_called_once()
        attempt = PaymentAttempt.objects.get(monobank_invoice_id="ig-prepay-1")
        self.assertEqual(attempt.pay_type, PaymentAttempt.PayType.PREPAYMENT)
        self.assertEqual(attempt.payment_amount, Decimal("600.00"))
        self.assertIn("Передоплата", attempt.invoice_payload["request"]["merchantPaymInfo"]["destination"])
        basket = attempt.invoice_payload["request"]["merchantPaymInfo"]["basketOrder"]
        self.assertEqual(
            sum(row["qty"] * row["sum"] for row in basket),
            attempt.invoice_payload["request"]["amount"],
        )
        self.assertEqual(
            IgCheckoutInventoryReservation.objects.filter(
                proposal=self.proposal,
                state=IgCheckoutInventoryReservation.State.ACTIVE,
            ).count(),
            2,
        )

    def test_provider_failure_is_ambiguous_and_does_not_unlock_recipient(self):
        raw, _token = IgCheckoutAccessToken.issue(proposal=self.proposal)
        entry = self.client.get(reverse("ig_checkout_token_entry", kwargs={"token": raw}))
        self.client.get(entry["Location"])
        self.client.cookies["_fbp"] = "fb.1.1700000000000.ambiguous"
        with patch(
            "storefront.views.monobank._monobank_api_request",
            side_effect=TimeoutError("provider timeout"),
        ) as provider:
            response = self.client.post(
                reverse("ig_checkout_proposal", kwargs={"proposal_id": self.proposal.public_id}),
                data=self._delivery_payload(),
                HTTP_USER_AGENT="Checkout Payer Browser",
                REMOTE_ADDR="198.51.100.42",
            )

        self.assertEqual(response.status_code, 400)
        provider.assert_called_once()
        attempt = PaymentAttempt.objects.get()
        self.assertEqual(attempt.status, PaymentAttempt.Status.PROCESSING)
        self.assertTrue((attempt.event_state or {}).get("invoice_creation_ambiguous"))
        self.assertEqual(attempt.tracking_payload.get("fbp"), "fb.1.1700000000000.ambiguous")
        self.assertEqual(
            attempt.tracking_payload.get("client_user_agent"),
            "Checkout Payer Browser",
        )
        self.assertEqual(
            attempt.tracking_payload.get("client_ip_address"),
            "198.51.100.42",
        )
        self.assertEqual(
            attempt.tracking_payload.get("add_payment_event_id"),
            attempt.add_payment_event_id,
        )
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.status, IgCheckoutProposal.Status.DETAILS_LOCKED)
        self.assertIsNotNone(self.proposal.payment_attempt_id)

    def test_expired_invoice_creation_lease_becomes_ambiguous_without_retry(self):
        attempt = self._attempt(status=PaymentAttempt.Status.PROCESSING)
        attempt.event_state = {
            "invoice_creation_lease": "stale-lease",
            "invoice_creation_lease_expires_at": (
                timezone.now() - timedelta(minutes=1)
            ).isoformat(),
        }
        attempt.save(update_fields=["event_state", "updated"])
        self.proposal.payment_attempt = attempt
        self.proposal.status = IgCheckoutProposal.Status.DETAILS_LOCKED
        self.proposal.details_locked_at = timezone.now() - timedelta(minutes=1)
        self.proposal.save(update_fields=[
            "payment_attempt", "status", "details_locked_at", "updated_at",
        ])
        raw, _token = IgCheckoutAccessToken.issue(proposal=self.proposal)
        entry = self.client.get(reverse("ig_checkout_token_entry", kwargs={"token": raw}))
        self.client.get(entry["Location"])

        with patch("storefront.views.monobank._monobank_api_request") as provider:
            response = self.client.post(
                reverse("ig_checkout_proposal", kwargs={"proposal_id": self.proposal.public_id}),
                data=self._delivery_payload(),
                HTTP_ACCEPT="application/json",
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "provider_ambiguous")
        provider.assert_not_called()
        attempt.refresh_from_db()
        self.assertTrue((attempt.event_state or {}).get("invoice_creation_ambiguous"))
        self.assertNotIn("invoice_creation_lease", attempt.event_state)
        self.assertEqual(attempt.status, PaymentAttempt.Status.PROCESSING)

    def test_deterministic_provider_configuration_failure_unlocks_checkout(self):
        from storefront.views.monobank import MonobankAPIError

        raw, _token = IgCheckoutAccessToken.issue(proposal=self.proposal)
        entry = self.client.get(reverse("ig_checkout_token_entry", kwargs={"token": raw}))
        self.client.get(entry["Location"])
        with patch(
            "storefront.views.monobank._monobank_api_request",
            side_effect=MonobankAPIError("token is not configured", ambiguous=False),
        ):
            response = self.client.post(
                reverse("ig_checkout_proposal", kwargs={"proposal_id": self.proposal.public_id}),
                data=self._delivery_payload(),
            )

        self.assertEqual(response.status_code, 400)
        attempt = PaymentAttempt.objects.get()
        self.assertEqual(attempt.status, PaymentAttempt.Status.FAILED)
        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.status, IgCheckoutProposal.Status.READY)
        self.assertIsNone(self.proposal.payment_attempt_id)
        self.assertFalse(
            IgCheckoutInventoryReservation.objects.filter(
                proposal=self.proposal,
                state=IgCheckoutInventoryReservation.State.ACTIVE,
            ).exists()
        )

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

    def test_forwarded_payer_cannot_overwrite_first_browser_attribution(self):
        raw, _token = IgCheckoutAccessToken.issue(proposal=self.proposal)
        entry = self.client.get(reverse("ig_checkout_token_entry", kwargs={"token": raw}))
        self.client.get(entry["Location"])
        payload = self._delivery_payload()
        self.client.cookies["_fbp"] = "fb.1.1700000000000.first"
        with patch(
            "storefront.views.monobank._monobank_api_request",
            return_value={"invoiceId": "ig-attribution-1", "pageUrl": "https://pay.example/ig-attribution-1"},
        ) as provider, patch(
            "orders.facebook_conversions_service.get_facebook_conversions_service"
        ) as fb, patch(
            "orders.telegram_notifications.TelegramNotifier.send_payment_attempt_notification",
            return_value=True,
        ):
            fb.return_value.send_add_payment_info_event.return_value = True
            first = self.client.post(
                reverse("ig_checkout_proposal", kwargs={"proposal_id": self.proposal.public_id}),
                data=payload,
                HTTP_USER_AGENT="First Payer Browser",
                REMOTE_ADDR="198.51.100.10",
            )
            attempt = PaymentAttempt.objects.get()
            first_tracking = dict(attempt.tracking_payload)

            self.client.cookies["_fbp"] = "fb.1.1700000000000.second"
            second = self.client.post(
                reverse("ig_checkout_proposal", kwargs={"proposal_id": self.proposal.public_id}),
                data=payload,
                HTTP_USER_AGENT="Forwarded Payer Browser",
                REMOTE_ADDR="198.51.100.11",
            )

        self.assertEqual(first["Location"], second["Location"])
        provider.assert_called_once()
        self.assertEqual(PaymentAttempt.objects.count(), 1)
        attempt.refresh_from_db()
        self.assertEqual(attempt.tracking_payload, first_tracking)
        self.assertEqual(attempt.tracking_payload["fbp"], "fb.1.1700000000000.first")
        self.assertEqual(attempt.tracking_payload["client_user_agent"], "First Payer Browser")
        self.assertEqual(attempt.tracking_payload["client_ip_address"], "198.51.100.10")

    def test_reused_invoice_retries_missing_add_payment_info_marker(self):
        raw, _token = IgCheckoutAccessToken.issue(proposal=self.proposal)
        entry = self.client.get(reverse("ig_checkout_token_entry", kwargs={"token": raw}))
        self.client.get(entry["Location"])
        payload = self._delivery_payload()
        with patch("storefront.views.monobank._monobank_api_request", return_value={
            "invoiceId": "ig-invoice-capi-retry",
            "pageUrl": "https://pay.example/ig-capi-retry",
        }) as provider, patch(
            "orders.facebook_conversions_service.get_facebook_conversions_service"
        ) as fb, patch(
            "orders.telegram_notifications.TelegramNotifier.send_payment_attempt_notification",
            return_value=True,
        ):
            fb.return_value.send_add_payment_info_event.side_effect = [False, True]
            first = self.client.post(
                reverse("ig_checkout_proposal", kwargs={"proposal_id": self.proposal.public_id}),
                data=payload,
            )
            second = self.client.post(
                reverse("ig_checkout_proposal", kwargs={"proposal_id": self.proposal.public_id}),
                data=payload,
            )

        self.assertEqual(first["Location"], second["Location"])
        provider.assert_called_once()
        self.assertEqual(fb.return_value.send_add_payment_info_event.call_count, 2)

    def test_pending_status_endpoint_requires_grant_and_exposes_no_pii(self):
        denied = self.client.get(
            reverse("ig_checkout_status", kwargs={"proposal_id": self.proposal.public_id})
        )
        self.assertEqual(denied.status_code, 404)

        self._open()
        attempt = self._attempt(status=PaymentAttempt.Status.PROCESSING)
        self.proposal.payment_attempt = attempt
        self.proposal.status = IgCheckoutProposal.Status.INVOICE_CREATED
        self.proposal.save(update_fields=["payment_attempt", "status", "updated_at"])

        response = self.client.get(
            reverse("ig_checkout_status", kwargs={"proposal_id": self.proposal.public_id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "pending")
        self.assertEqual(response.json()["revision"], self.proposal.revision)
        serialized = response.content.decode()
        self.assertNotIn(attempt.full_name, serialized)
        self.assertNotIn(attempt.phone, serialized)
        self.assertNotIn(attempt.email, serialized)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("private", response["Cache-Control"])

    def test_terminal_provider_failure_releases_invoice_inventory(self):
        raw, _token = IgCheckoutAccessToken.issue(proposal=self.proposal)
        entry = self.client.get(reverse("ig_checkout_token_entry", kwargs={"token": raw}))
        self.client.get(entry["Location"])
        with patch("storefront.views.monobank._monobank_api_request", return_value={
            "invoiceId": "ig-invoice-release", "pageUrl": "https://pay.example/ig-release",
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
        self.assertTrue(
            self.proposal.inventory_reservations.filter(
                state=IgCheckoutInventoryReservation.State.ACTIVE
            ).exists()
        )
        from storefront.views.monobank import _apply_payment_attempt_status

        _apply_payment_attempt_status(
            attempt,
            "failure",
            payload={"status": "failure", "invoiceId": attempt.monobank_invoice_id},
            source="test",
        )

        self.assertFalse(
            self.proposal.inventory_reservations.filter(
                state=IgCheckoutInventoryReservation.State.ACTIVE
            ).exists()
        )
        self.assertEqual(
            set(self.proposal.inventory_reservations.values_list("state", flat=True)),
            {IgCheckoutInventoryReservation.State.RELEASED},
        )

    def test_provider_terminal_truth_projects_cancellation_and_releases_promo_capacity(self):
        promo = PromoCode.objects.create(
            code="IGLAST",
            discount_type="percentage",
            discount_value=Decimal("10.00"),
            max_uses=1,
        )
        raw, _token = IgCheckoutAccessToken.issue(proposal=self.proposal)
        entry = self.client.get(reverse("ig_checkout_token_entry", kwargs={"token": raw}))
        self.client.get(entry["Location"])
        payload = self._delivery_payload()
        payload["promo_code"] = promo.code
        with patch("storefront.views.monobank._monobank_api_request", return_value={
            "invoiceId": "ig-invoice-terminal", "pageUrl": "https://pay.example/ig-terminal",
        }), patch(
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
        attempt = PaymentAttempt.objects.get()
        promo.refresh_from_db()
        self.assertEqual(promo.current_uses, 1)
        self.assertEqual(
            (attempt.event_state or {}).get("promo_reservation", {}).get("state"),
            "reserved",
        )

        from management.models import IgPaymentEvent, IgPaymentProjection
        from storefront.views.monobank import _apply_payment_attempt_status

        _apply_payment_attempt_status(
            attempt,
            "cancelled",
            payload={
                "status": "cancelled",
                "invoiceId": attempt.monobank_invoice_id,
                "reference": attempt.reference,
                "ccy": 980,
            },
            source="provider_pull",
        )

        attempt.refresh_from_db()
        promo.refresh_from_db()
        self.proposal.refresh_from_db()
        self.deal.refresh_from_db()
        event = IgPaymentEvent.objects.get(
            deal=self.deal,
            provider_status="cancelled",
        )
        projection = IgPaymentProjection.objects.get(deal=self.deal)
        self.assertEqual(attempt.status, PaymentAttempt.Status.CANCELLED)
        self.assertEqual(promo.current_uses, 0)
        self.assertEqual(
            (attempt.event_state or {}).get("promo_reservation", {}).get("state"),
            "released",
        )
        self.assertEqual(self.proposal.status, IgCheckoutProposal.Status.CANCELLED)
        self.assertEqual(self.proposal.provider_cancellation_event_id, event.pk)
        self.assertEqual(projection.truth, IgDeal.PaymentTruth.CANCELLED)
        self.assertEqual(projection.last_event_id, event.pk)
        self.assertEqual(self.deal.payment_truth, IgDeal.PaymentTruth.CANCELLED)
        self.assertTrue(self.proposal.has_provider_confirmed_cancellation())

        replacement = IgCheckoutProposal.objects.replace_current(
            deal=self.deal,
            catalog_total=Decimal("1700.00"),
            quoted_total=Decimal("1700.00"),
            requested_payment_amount=Decimal("1700.00"),
            items_digest=hashlib.sha256(b"provider-terminal-replacement").hexdigest(),
        )
        self.assertNotEqual(replacement.pk, self.proposal.pk)

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
        self.assertEqual(order.email, self._delivery_payload()["email"])
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
        with patch(
            "management.services.instagram_bot.send_text",
            return_value=(True, "", "", "test-meta-lifecycle-message"),
        ) as sender:
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
