"""Locale contract tests for cart, mini-cart and payment entry points."""

from __future__ import annotations

import json
import inspect
import re
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings
from django.urls import NoReverseMatch, reverse
from django.utils.translation import override

from orders.models import PaymentAttempt
from storefront.context_processors import storefront_locale_contract
from storefront.models import Category, Product
from storefront.services.cart_locale import build_cart_locale_config
from storefront.views.monobank import _capi_checkout_source_url


class CartLocaleContractTests(TestCase):
    CART_JS_FILES = (
        "twocomms_django_theme/static/js/main.js",
        "twocomms_django_theme/static/js/modules/cart.js",
        "twocomms_django_theme/static/js/modules/checkout-mono.js",
        "twocomms_django_theme/static/js/ui-fallback.js",
    )

    def _request(self, language):
        request = HttpRequest()
        request.method = "GET"
        request.path = "/"
        request.LANGUAGE_CODE = language
        request.user = AnonymousUser()
        request.session = self.client.session
        return request

    def test_cart_config_is_separate_from_metadata_contract_and_has_prefixed_urls(self):
        with override("ru"):
            context = storefront_locale_contract(self._request("ru"))

        metadata = context["storefront_locale_contract"]
        config = context["cart_locale_config"]
        self.assertEqual(metadata, {
            "language": "ru",
            "intlLocale": "ru-UA",
            "currency": {"code": "UAH", "suffix": "грн"},
        })
        self.assertEqual(config["intlLocale"], "ru-UA")
        self.assertEqual(config["currency"]["suffix"], "грн")
        self.assertTrue(config["urls"]["items"].startswith("/ru/"))
        self.assertTrue(config["urls"]["summary"].startswith("/ru/"))
        self.assertTrue(config["urls"]["mini"].startswith("/ru/"))
        self.assertTrue(config["urls"]["invoice"].startswith("/ru/"))
        self.assertTrue(config["urls"]["quickInvoice"].startswith("/ru/"))
        self.assertTrue(config["urls"]["remove"].startswith("/ru/"))
        self.assertTrue(config["urls"]["customRemove"].startswith("/ru/"))
        self.assertIn("emptyCart", config["strings"])
        self.assertIn("paymentCta", config["strings"])
        self.assertIn("color", config["strings"])

    def test_base_exposes_cart_config_on_non_cart_pages(self):
        with override("en"):
            context = storefront_locale_contract(self._request("en"))
            rendered = render_to_string("base.html", context)

        self.assertIn('id="cart-locale-config"', rendered)
        self.assertNotIn('id="storefront-locale-contract"', rendered.split('id="cart-locale-config"', 1)[1])
        self.assertIn("/en/cart/items/", rendered)

    def test_cart_ssr_uses_locale_prefixed_urls_and_no_root_update_endpoint(self):
        for language in ("en", "ru"):
            with self.subTest(language=language), override(language):
                response = self.client.get(reverse("cart"))

            self.assertEqual(response.status_code, 200)
            content = response.content.decode("utf-8")
            self.assertIn(f'data-cart-update-url="/{language}/cart/update/"', content)
            self.assertNotIn("fetch('/cart/update/'", content)
            self.assertNotIn('fetch("/cart/update/"', content)

    def test_cart_locale_config_exposes_locale_prefixed_update_url(self):
        for language in ("en", "ru"):
            with self.subTest(language=language), override(language):
                context = storefront_locale_contract(self._request(language))

            self.assertEqual(context["cart_locale_config"]["urls"]["update"], f"/{language}/cart/update/")

    def test_cart_locale_config_never_exposes_blank_urls(self):
        expected_prefixes = {
            "uk": "/",
            "en": "/en/",
            "ru": "/ru/",
        }
        for language, prefix in expected_prefixes.items():
            with self.subTest(language=language), patch(
                "storefront.services.cart_locale.reverse", side_effect=NoReverseMatch
            ):
                config = build_cart_locale_config(language)
            self.assertTrue(config["urls"])
            self.assertTrue(all(value.startswith(prefix) for value in config["urls"].values()))
            self.assertTrue(all(value for value in config["urls"].values()))
            if language == "uk":
                self.assertTrue(all(not value.startswith("/uk/") for value in config["urls"].values()))
                self.assertEqual(config["urls"]["cart"], "/cart/")
            else:
                self.assertTrue(all(value.startswith(prefix) for value in config["urls"].values()))

    def test_cart_copy_is_localized_for_russian_and_english(self):
        for language, expected in (
            ("ru", "Корзина пуста"),
            ("en", "Cart is empty"),
        ):
            with self.subTest(language=language), override(language):
                context = storefront_locale_contract(self._request(language))
            self.assertEqual(context["cart_locale_config"]["language"], language)
            self.assertEqual(context["cart_locale_config"]["strings"]["emptyCart"], expected)
            self.assertNotEqual(context["cart_locale_config"]["strings"]["paymentError"], "Не вдалося створити платіж. Спробуйте ще раз.")

    def test_cart_runtime_payload_has_reviewed_english_and_russian_copy(self):
        expected = {
            "en": {
                "discount": "Discount",
                "promoRetryLimit": "Too many attempts. Try again in a minute.",
                "invalidDelivery": "Choose a city and delivery point from the Nova Poshta list.",
                "contactError": "Error: {message}",
            },
            "ru": {
                "itemProductAlt": "Изделие TwoComms",
                "fit": "Тип посадки",
                "perItem": "шт.",
                "giftText": "Подарочная упаковка + промокод на 10%",
                "discount": "Скидка",
                "promoRetryLimit": "Слишком много попыток. Повторите через минуту.",
                "invalidDelivery": "Выберите город и пункт доставки из списка Новой почты.",
                "contactError": "Ошибка: {message}",
            },
        }
        for language, strings in expected.items():
            with self.subTest(language=language):
                self.assertEqual(
                    {key: build_cart_locale_config(language)["strings"][key] for key in strings},
                    strings,
                )

    def test_empty_monobank_checkout_returns_stable_localized_error_without_attempt(self):
        with override("en"):
            response = self.client.post(
                reverse("monobank_create_invoice"),
                data=json.dumps({}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["success"], False)
        self.assertEqual(payload["error_code"], "cart_empty")
        self.assertNotIn("Кошик", payload["error"])
        self.assertFalse(PaymentAttempt.objects.exists())

    def test_capi_checkout_source_url_fallback_keeps_active_locale(self):
        request = RequestFactory().post(
            "/ru/cart/monobank/create-invoice/",
            HTTP_HOST="testserver",
            secure=True,
        )
        with override("ru"):
            source_url = _capi_checkout_source_url(request)

        self.assertEqual(source_url, "https://testserver/ru/cart/")

    def test_quick_invoice_route_dispatches_json_and_keeps_locale(self):
        expected = {
            "en": "Your cart is empty. Add products before paying.",
            "ru": "Корзина пуста. Добавьте товары перед оплатой.",
        }
        for language, message in expected.items():
            with self.subTest(language=language), override(language):
                response = self.client.post(
                    reverse("monobank_quick_invoice"),
                    data=json.dumps({}),
                    content_type="application/json",
                )

            self.assertEqual(response.status_code, 400)
            self.assertEqual(response["Content-Type"].split(";", 1)[0], "application/json")
            self.assertEqual(
                response.json(),
                {
                    "success": False,
                    "error_code": "cart_empty",
                    "error": message,
                },
            )

    def test_quick_invoice_provider_failure_is_localized_and_safe(self):
        category = Category.objects.create(name="Quick invoice test", slug="quick-invoice-test")
        product = Product.objects.create(
            title="Quick invoice product",
            slug="quick-invoice-product",
            category=category,
            price=100,
        )
        session = self.client.session
        session["cart"] = {
            "quick-line": {"product_id": product.id, "qty": 1, "size": "M"},
        }
        session.save()

        from storefront import views as storefront_views

        storefront_views._load_legacy_views(force=True)
        legacy_handler = storefront_views.monobank_create_checkout
        legacy_globals = inspect.unwrap(legacy_handler).__globals__
        legacy_error = legacy_globals["MonobankAPIError"]

        def provider_failure(*args, **kwargs):
            raise legacy_error("provider-secret-diagnostic")

        payload = {
            "full_name": "Guest User",
            "phone": "+380991234567",
            "city": "Kyiv",
            "np_office": "Branch 1",
            "pay_type": "full",
        }
        for language, expected in (
            ("en", "Could not create the payment. Please try again."),
            ("ru", "Не удалось создать платёж. Попробуйте ещё раз."),
        ):
            with self.subTest(language=language), override(language), patch.dict(
                legacy_globals, {"_monobank_api_request": provider_failure}
            ), patch.object(storefront_views, "_load_legacy_views", return_value=None):
                response = self.client.post(
                    reverse("monobank_quick_invoice"),
                    data=json.dumps(payload),
                    content_type="application/json",
                    secure=True,
                )

            self.assertEqual(response.status_code, 502)
            self.assertEqual(response.json()["success"], False)
            self.assertEqual(response.json()["error_code"], "provider_error")
            self.assertEqual(response.json()["error"], expected)
            self.assertNotIn("provider-secret-diagnostic", response.content.decode("utf-8"))

    def test_quick_invoice_unexpected_failure_keeps_legacy_200_contract(self):
        from storefront import views as storefront_views

        storefront_views._load_legacy_views(force=True)
        legacy_handler = storefront_views.monobank_create_checkout
        legacy_globals = inspect.unwrap(legacy_handler).__globals__
        with patch.dict(legacy_globals, {"_create_or_update_monobank_order": lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("secret diagnostic"))}), patch.object(
            storefront_views, "_load_legacy_views", return_value=None
        ):
            with override("en"):
                response = self.client.post(
                    reverse("monobank_quick_invoice"),
                    data=json.dumps({"full_name": "Guest User", "phone": "+380991234567", "city": "Kyiv", "np_office": "Branch 1", "pay_type": "full"}),
                    content_type="application/json",
                )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["error_code"], "checkout_error")
        self.assertEqual(response.json()["error"], "Could not create the order.")
        self.assertNotIn("secret diagnostic", response.content.decode("utf-8"))

    def test_cart_javascript_requires_server_owned_copy_and_locale_urls(self):
        project_root = Path(__file__).resolve().parents[2]
        configured_strings = set(build_cart_locale_config("en")["strings"])
        referenced_strings = set()

        for relative_path in self.CART_JS_FILES:
            source = (project_root / relative_path).read_text(encoding="utf-8")
            with self.subTest(path=relative_path):
                self.assertNotIn("(key, fallback)", source)

            referenced_strings.update(
                re.findall(
                    r"(?:cartText|cartLocaleText|cartInterpolate)\(\s*['\"]([^'\"]+)['\"]",
                    source,
                )
            )

        self.assertEqual(referenced_strings - configured_strings, set())
