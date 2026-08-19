import json
import inspect
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.messages import get_messages
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils.translation import override

from orders.models import Order, OrderItem, PaymentAttempt
from orders.nova_poshta_checkout import build_city_choice_token, build_warehouse_choice_token
from storefront.models import Category, Product


class MonobankReturnLocaleTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Locale test", slug="locale-test")
        self.product = Product.objects.create(
            title="Locale test product",
            slug="locale-test-product",
            category=self.category,
            price=100,
        )

    def _delivery_tokens(self):
        return {
            "np_city_token": build_city_choice_token({
                "label": "м. Київ, Київ",
                "settlement_ref": "settlement-ref",
                "city_ref": "city-ref",
            }),
            "np_warehouse_token": build_warehouse_choice_token({
                "label": "Відділення №1, Київ",
                "ref": "warehouse-ref",
                "kind": "branch",
                "city_ref": "city-ref",
            }),
        }

    def _set_cart(self):
        session = self.client.session
        session["cart"] = {
            "line-1": {"product_id": self.product.id, "qty": 1, "size": "M"},
        }
        session.save()

    def _checkout_payload(self):
        payload = {
            "full_name": "Locale Buyer",
            "phone": "+380991234567",
            "pay_type": "online_full",
        }
        payload.update(self._delivery_tokens())
        return payload

    def test_invoice_redirect_url_is_locale_prefixed_but_webhook_is_not(self):
        for language in ("uk", "en", "ru"):
            request = RequestFactory().post(
                reverse("monobank_create_invoice"),
                data=json.dumps(self._checkout_payload()),
                content_type="application/json",
                secure=True,
            )
            SessionMiddleware(lambda req: None).process_request(request)
            request.session["cart"] = {
                "line-1": {"product_id": self.product.id, "qty": 1, "size": "M"},
            }
            request.session.save()
            request.user = AnonymousUser()
            request.LANGUAGE_CODE = language
            with self.subTest(language=language), override(language), patch(
                "storefront.views.monobank._monobank_api_request",
                return_value={
                    "invoiceId": f"invoice-{language}",
                    "pageUrl": f"https://pay.example/{language}",
                },
            ), patch("storefront.views.monobank.get_facebook_conversions_service", return_value=Mock()), patch(
                "storefront.views.monobank.record_initiate_checkout"
            ), patch("storefront.views.monobank.link_order_to_utm"):
                from storefront.views.monobank import monobank_create_invoice

                response = monobank_create_invoice(request)
                expected_return = request.build_absolute_uri(reverse("monobank_return"))

            self.assertEqual(response.status_code, 200, response.content.decode())
            self.assertTrue(json.loads(response.content)["success"])
            captured = PaymentAttempt.objects.get(monobank_invoice_id=f"invoice-{language}").invoice_payload["request"]
            self.assertEqual(captured["redirectUrl"], expected_return)
            self.assertEqual(
                captured["webHookUrl"],
                request.build_absolute_uri("/payments/monobank/webhook/"),
            )
            PaymentAttempt.objects.all().delete()

    def test_missing_payment_reference_message_is_localized(self):
        expected = {
            "uk": "Замовлення не знайдено. Спробуйте ще раз.",
            "en": "Order not found. Please try again.",
            "ru": "Заказ не найден. Попробуйте ещё раз.",
        }
        for language, message in expected.items():
            client = Client()
            with self.subTest(language=language), override(language):
                response = client.get(reverse("monobank_return"), secure=True)

            with override(language):
                expected_cart = reverse("cart")
            self.assertRedirects(response, expected_cart, fetch_redirect_response=False)
            self.assertEqual([str(item) for item in get_messages(response.wsgi_request)], [message])

    def test_unconfirmed_payment_message_is_localized(self):
        expected = {
            "uk": "Платіж ще не підтверджено. Спробуйте ще раз після завершення оплати.",
            "en": "The payment hasn't been confirmed yet. Please try again once the payment is complete.",
            "ru": "Платёж пока не подтверждён. Повторите попытку после завершения оплаты.",
        }
        for language, message in expected.items():
            client = Client()
            attempt = Mock(monobank_invoice_id="return-locale-invoice")
            attempt.instagram_checkout_proposal = None
            with self.subTest(language=language), override(language), patch(
                "storefront.views.monobank._get_payment_attempt_by_refs",
                return_value=attempt,
            ), patch(
                "storefront.views.monobank._request_owns_payment_attempt", return_value=True
            ), patch(
                "storefront.views.monobank._resolve_attempt_invoice_status",
                return_value=(None, {}),
            ):
                response = client.get(
                    reverse("monobank_return"),
                    {"attemptId": "owned-attempt"},
                    secure=True,
                )

            with override(language):
                expected_cart = reverse("cart")
            self.assertRedirects(response, expected_cart, fetch_redirect_response=False)
            self.assertEqual([str(item) for item in get_messages(response.wsgi_request)], [message])

    def test_legacy_checkout_payload_localizes_return_url_but_not_webhook_url(self):
        order = Order.objects.create(
            full_name="Legacy buyer",
            phone="+380991234567",
            city="Kyiv",
            np_office="Branch 1",
            pay_type="online_full",
            status="new",
            payment_status="unpaid",
            total_sum=Decimal("100"),
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            title=self.product.title,
            size="M",
            qty=1,
            unit_price=Decimal("100"),
            line_total=Decimal("100"),
        )
        from storefront import views as storefront_views

        storefront_views._load_legacy_views(force=True)
        legacy_globals = inspect.unwrap(storefront_views.monobank_create_checkout).__globals__
        build_payload = legacy_globals["_build_monobank_checkout_payload"]
        request = self.client.get(reverse("cart"), secure=True).wsgi_request

        for language in ("uk", "en", "ru"):
            with self.subTest(language=language), override(language):
                request.LANGUAGE_CODE = language
                payload = build_payload(
                    order,
                    Decimal("100"),
                    1,
                    request,
                    items=list(order.items.all()),
                )
                expected_return = request.build_absolute_uri(reverse("monobank_return")).replace(
                    "http://", "https://", 1
                )
            self.assertEqual(payload["return_url"], expected_return)
            self.assertEqual(
                payload["callback_url"],
                request.build_absolute_uri("/payments/monobank/webhook/").replace(
                    "http://", "https://", 1
                ),
            )

    def test_return_status_messages_are_localized_for_all_retail_branches(self):
        branches = {
            "success": {
                "uk": "Оплата успішно пройшла!",
                "en": "Payment completed successfully!",
                "ru": "Оплата прошла успешно!",
            },
            "processing": {
                "uk": "Платіж обробляється. Ми повідомимо, щойно отримаємо підтвердження.",
                "en": "Payment is being processed. We will notify you as soon as it is confirmed.",
                "ru": "Платёж обрабатывается. Мы сообщим, как только получим подтверждение.",
            },
            "failure": {
                "uk": "Платіж не пройшов. Спробуйте ще раз або оберіть інший спосіб оплати.",
                "en": "The payment did not go through. Try again or choose another payment method.",
                "ru": "Платёж не прошёл. Попробуйте ещё раз или выберите другой способ оплаты.",
            },
        }
        order = Order.objects.create(
            full_name="Status buyer",
            phone="+380991234567",
            city="Kyiv",
            np_office="Branch 1",
            pay_type="online_full",
            status="new",
            payment_status="unpaid",
            total_sum=Decimal("100"),
            payment_invoice_id="status-locale-invoice",
        )
        for status, messages_by_language in branches.items():
            for language, message in messages_by_language.items():
                client = Client()
                session = client.session
                session["monobank_invoice_id"] = order.payment_invoice_id
                session["monobank_pending_order_id"] = order.id
                session.save()
                with self.subTest(status=status, language=language), override(language), patch(
                    "storefront.views.monobank._resolve_retail_invoice_status",
                    return_value=(status, {"status": status}),
                ), patch(
                    "storefront.views.monobank._apply_monobank_status",
                    return_value=status,
                ):
                    response = client.get(
                        reverse("monobank_return"),
                        {"invoiceId": order.payment_invoice_id},
                        secure=True,
                    )
                self.assertEqual([str(item) for item in get_messages(response.wsgi_request)], [message])

    def test_attempt_ownership_error_message_is_localized(self):
        expected = {
            "uk": "Платіж не знайдено. Спробуйте ще раз.",
            "en": "Payment not found. Please try again.",
            "ru": "Платёж не найден. Попробуйте ещё раз.",
        }
        for language, message in expected.items():
            client = Client()
            with self.subTest(language=language), override(language), patch(
                "storefront.views.monobank._get_payment_attempt_by_refs",
                return_value=Mock(),
            ), patch("storefront.views.monobank._request_owns_payment_attempt", return_value=False):
                response = client.get(
                    reverse("monobank_return"),
                    {"attemptId": "foreign-attempt"},
                    secure=True,
                )
            self.assertEqual([str(item) for item in get_messages(response.wsgi_request)], [message])
