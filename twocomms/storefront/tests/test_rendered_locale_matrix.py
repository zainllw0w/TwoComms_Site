"""Rendered locale contracts for indexable standard catalog and PDP pages.

The matrix grows one verified surface at a time.  It deliberately checks
named buyer-visible values and link ownership rather than treating every
shared brand name or proper noun as a translation defect.
"""

from __future__ import annotations

import json
import re
from unittest.mock import patch

from django.core.cache import cache, caches
from django.test import TestCase
from django.utils import translation

from productcolors.models import Color, ProductColorVariant
from storefront.models import Category, Product, ProductFAQ


class RenderedLocaleMatrixTests(TestCase):
    """Prevent indexable RU/EN standard pages from publishing UK fallbacks."""

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            name="Футболки",
            name_ru="Футболки",
            name_en="T-shirts",
            slug="locale-matrix-tees",
            is_active=True,
        )
        cls.product = Product.objects.create(
            title="Українська футболка",
            title_ru="Русская футболка",
            title_en="English T-shirt",
            slug="locale-matrix-tee",
            category=cls.category,
            price=900,
            status="published",
            seo_title_ru="Русская футболка TwoComms",
            seo_title_en="English T-shirt TwoComms",
            seo_description_ru="Русское описание футболки TwoComms.",
            seo_description_en="English TwoComms T-shirt description.",
            full_description_ru="Русское описание товара для повседневной носки.",
            full_description_en="English product description for everyday wear.",
        )
        ProductFAQ.objects.create(
            product=cls.product,
            question="Як підібрати розмір?",
            answer="Скористайтеся розмірною сіткою.",
            question_ru="Как выбрать размер?",
            answer_ru="Воспользуйтесь размерной сеткой.",
            question_en="How do I choose a size?",
            answer_en="Use the size chart.",
            is_active=True,
        )
        color = Color.objects.create(name="Чорний", primary_hex="#000000")
        ProductColorVariant.objects.create(
            product=cls.product,
            color=color,
            is_default=True,
            order=0,
        )

    def setUp(self):
        super().setUp()
        previous_language = translation.get_language() or "uk"
        self.addCleanup(translation.activate, previous_language)
        cache.clear()
        caches["fragments"].clear()
        for target in (
            "storefront.signals.generate_google_merchant_feed_task.apply_async",
            "storefront.signals.enqueue_indexnow_urls",
        ):
            patcher = patch(target)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _product_seo_landing(self, body: str) -> str:
        match = re.search(
            r'<section class="product-seo-landing".*?</section>',
            body,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(match)
        return match.group(0)

    def _json_ld_node(self, body: str, schema_type: str) -> dict:
        for payload in re.findall(
            r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
            body,
            flags=re.DOTALL,
        ):
            data = json.loads(payload)
            candidates = data if isinstance(data, list) else [data]
            for candidate in candidates:
                if (
                    isinstance(candidate, dict)
                    and (
                        candidate.get("@type") == schema_type
                        or schema_type in (candidate.get("@type") or [])
                    )
                ):
                    return candidate
        self.fail(f"No {schema_type} JSON-LD node found")

    def test_standard_catalog_and_pdp_shared_shell_is_locale_owned(self):
        matrix = {
            "ru": {
                "paths": (
                    "/ru/catalog/",
                    "/ru/product/locale-matrix-tee/",
                ),
                "content_language": "ru",
                "required": (
                    "Войти через Telegram",
                    "Авторизуйтесь, чтобы накапливать баллы и не вводить данные каждый раз",
                    "Подтверждение Telegram",
                    "Нажмите «Открыть бота TwoComms» и поделитесь номером — дальше мы всё сделаем сами.",
                    "Нажмите «Открыть бота TwoComms» — мы перенаправим вас в Telegram.",
                    "В боте нажмите «📱 Поделиться номером» (это кнопка под полем ввода).",
                    "Вернитесь сюда — мы всё завершим автоматически.",
                    "Открыть бота TwoComms",
                    "Мы сохраним ваш номер только для связи. Без рассылок и передачи третьим лицам.",
                    "Ожидаем ваш контакт в боте…",
                    "В открытом Telegram-боте нажмите кнопку «📱 Поделиться номером».",
                    "Открыть бота ещё раз",
                    "Если бот не открылся — скопируйте ссылку:",
                    "Скопировать ссылку",
                    "Telegram подтверждён!",
                    "Готово",
                    "Сессия завершилась",
                    "Попробуйте ещё раз — новая сессия будет действовать 5 минут.",
                    "Попробовать ещё раз",
                ),
            },
            "en": {
                "paths": (
                    "/en/catalog/",
                    "/en/product/locale-matrix-tee/",
                ),
                "content_language": "en",
                "required": (
                    "Sign in with Telegram",
                    "Sign in to collect points and avoid entering your details each time",
                    "Telegram verification",
                    "Open the TwoComms bot and share your phone number — we will handle the rest.",
                    "Open the TwoComms bot — we will redirect you to Telegram.",
                    "In the bot, tap “📱 Share phone number” (the button below the message field).",
                    "Return here — we will finish everything automatically.",
                    "Open the TwoComms bot",
                    "We will save your number only to contact you. No marketing messages or third-party sharing.",
                    "Waiting for your contact in the bot…",
                    "In the Telegram bot, tap “📱 Share phone number”.",
                    "Open the bot again",
                    "If the bot did not open, copy the link:",
                    "Copy link",
                    "Telegram verified!",
                    "Done",
                    "Session expired",
                    "Try again — the new session will remain active for 5 minutes.",
                    "Try again",
                ),
            },
        }
        ukrainian_markers = (
            "Увійти через Telegram",
            "Авторизуйтесь, щоб накопичувати бали та не вводити дані щоразу",
            "Підтвердження Telegram",
            "Натисніть «Відкрити бота TwoComms» і поділіться номером — далі ми все зробимо самі.",
            "Очікуємо ваш контакт у боті…",
            "Telegram підтверджено!",
            "Сесія завершилась",
        )

        for locale, expected in matrix.items():
            for path in expected["paths"]:
                with self.subTest(locale=locale, path=path):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(
                        response.headers.get("Content-Language"),
                        expected["content_language"],
                    )
                    body = response.content.decode("utf-8")
                    for value in expected["required"]:
                        self.assertIn(value, body)
                    for marker in ukrainian_markers:
                        self.assertNotIn(marker, body)

    def test_standard_root_catalog_filters_and_organization_slogan_are_locale_owned(self):
        matrix = {
            "ru": {
                "path": "/ru/catalog/",
                "filters": (
                    "Наличие и сортировка",
                    "Только в наличии",
                    "Порядок товаров",
                    "Рекомендуемые",
                    "Сначала дешевле",
                    "Сначала дороже",
                    "Закрыть фильтры",
                ),
                "slogan": (
                    "Не точка, а продолжение. Украинский streetwear из Харькова."
                ),
            },
            "en": {
                "path": "/en/catalog/",
                "filters": (
                    "Availability and sorting",
                    "In stock only",
                    "Product order",
                    "Recommended",
                    "Price: low to high",
                    "Price: high to low",
                    "Close filters",
                ),
                "slogan": (
                    "Not a full stop, but a continuation. Ukrainian streetwear from Kharkiv."
                ),
            },
        }
        ukrainian_filters = (
            "Наявність і сортування",
            "Тільки в наявності",
            "Порядок товарів",
            "Рекомендовані",
            "Від дешевих",
            "Від дорогих",
            "Закрити фільтри",
        )

        for locale, expected in matrix.items():
            with self.subTest(locale=locale):
                response = self.client.get(expected["path"])
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "index, follow")
                body = response.content.decode("utf-8")
                for value in expected["filters"]:
                    self.assertIn(value, body)
                for marker in ukrainian_filters:
                    self.assertNotIn(marker, body)

                schema = self._json_ld_node(body, "Organization")
                self.assertEqual(
                    schema["@id"],
                    "https://twocomms.shop/#organization",
                )
                self.assertEqual(schema["name"], "TwoComms")
                self.assertEqual(schema["slogan"], expected["slogan"])
                self.assertNotIn("Не крапка, а продовження", schema["slogan"])

    def test_standard_pdp_founder_schema_is_locale_owned(self):
        matrix = {
            "ru": {
                "path": "/ru/product/locale-matrix-tee/",
                "job_title": "Основатель TwoComms",
                "description": (
                    "Основатель украинского streetwear-бренда TwoComms из "
                    "Харькова, боевой ветеран."
                ),
            },
            "en": {
                "path": "/en/product/locale-matrix-tee/",
                "job_title": "Founder of TwoComms",
                "description": (
                    "Founder of the Ukrainian streetwear brand TwoComms from "
                    "Kharkiv; a combat veteran."
                ),
            },
        }

        for locale, expected in matrix.items():
            with self.subTest(locale=locale):
                response = self.client.get(expected["path"])
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "index, follow")
                schema = self._json_ld_node(
                    response.content.decode("utf-8"),
                    "Person",
                )

                self.assertEqual(schema["jobTitle"], expected["job_title"])
                self.assertEqual(schema["description"], expected["description"])
                self.assertNotIn("Засновник українського", schema["description"])

    def test_standard_pdp_gallery_exposes_locale_owned_js_labels(self):
        matrix = {
            "ru": {
                "path": "/ru/product/locale-matrix-tee/",
                "region": "Позиция в галерее",
                "status": "Фото {position} из {total}",
                "thumbnail": "Фото товара {position}",
                "initial_status": "Фото 1 из 1",
            },
            "en": {
                "path": "/en/product/locale-matrix-tee/",
                "region": "Gallery position",
                "status": "Photo {position} of {total}",
                "thumbnail": "Product photo {position}",
                "initial_status": "Photo 1 of 1",
            },
        }

        for locale, expected in matrix.items():
            with self.subTest(locale=locale):
                response = self.client.get(expected["path"])
                self.assertEqual(response.status_code, 200)
                body = response.content.decode("utf-8")
                self.assertIn(
                    f'aria-label="{expected["region"]}"',
                    body,
                )
                self.assertIn(
                    f'data-gallery-status-template="{expected["status"]}"',
                    body,
                )
                self.assertIn(
                    f'data-gallery-thumbnail-template="{expected["thumbnail"]}"',
                    body,
                )
                self.assertIn(
                    'product-detail.js?v=20260813-gallery-i18n-v1',
                    body,
                )
                self.assertIn(
                    f'data-gallery-status role="status" aria-live="polite" '
                    f'aria-atomic="true">{expected["initial_status"]}</span>',
                    body,
                )
                self.assertNotIn('aria-label="Позиція у галереї"', body)

    def test_standard_pdp_shared_merchandising_shell_is_locale_owned(self):
        matrix = {
            "ru": {
                "path": "/ru/product/locale-matrix-tee/",
                "context": "Контекст модели",
                "custom_title": "Хочешь этот принт иначе?",
                "custom_copy": (
                    "Сделай похожий вариант на другом цвете, основе или добавь "
                    "свой знак в кастомной DTF-печати."
                ),
                "custom_action": "Создать свой вариант",
            },
            "en": {
                "path": "/en/product/locale-matrix-tee/",
                "context": "Model context",
                "custom_title": "Want this print in a different version?",
                "custom_copy": (
                    "Make a similar version on another color or base, or add "
                    "your own mark with custom DTF printing."
                ),
                "custom_action": "Create your own version",
            },
        }

        ukrainian_markers = (
            "Контекст моделі",
            "Хочеш цей принт інакше?",
            "Зроби схожий варіант на іншому кольорі, основі або додай свій знак у кастомному DTF-друці.",
            "Створити свій варіант",
        )

        for locale, expected in matrix.items():
            with self.subTest(locale=locale):
                response = self.client.get(expected["path"])
                self.assertEqual(response.status_code, 200)
                body = response.content.decode("utf-8")
                for value in (
                    expected["context"],
                    expected["custom_title"],
                    expected["custom_copy"],
                    expected["custom_action"],
                ):
                    self.assertIn(value, body)
                for marker in ukrainian_markers:
                    self.assertNotIn(marker, body)

    def test_standard_pdp_restock_and_status_ui_is_locale_owned(self):
        matrix = {
            "ru": {
                "path": "/ru/product/locale-matrix-tee/",
                "required": (
                    "Сообщить, когда размер S появится",
                    "Сейчас все размеры распроданы",
                    "Выберите нужный размер в заявке, и мы сообщим, когда он появится.",
                    "Уведомить о наличии",
                    "Варианты временно недоступны",
                    "Обновите страницу немного позже или напишите нам, и мы поможем с выбором.",
                    "Выберите удобный канал. Мы напишем только один раз, когда нужная конфигурация появится.",
                    "Товар",
                    "Опции",
                    "Канал уведомления",
                    "Звонок",
                    "Как к вам обращаться",
                    "Telegram подключится через бота после подтверждения номера.",
                    "Уведомить меня",
                ),
            },
            "en": {
                "path": "/en/product/locale-matrix-tee/",
                "required": (
                    "Notify me when size S is available",
                    "All sizes are currently sold out",
                    "Choose the size you need in the request, and we will let you know when it is available.",
                    "Notify me when available",
                    "Options are temporarily unavailable",
                    "Refresh the page a little later or message us for help choosing.",
                    "Choose a convenient channel. We will contact you only once when the selected configuration is available.",
                    "Product",
                    "Options",
                    "Notification channel",
                    "Call",
                    "How should we address you?",
                    "Telegram will be connected through the bot after phone number verification.",
                    "Notify me",
                ),
            },
        }
        ukrainian_markers = (
            "Повідомити, коли розмір S з'явиться",
            "Наразі всі розміри розібрано",
            "Оберіть потрібний розмір у заявці, і ми повідомимо про його появу.",
            "Повідомити про наявність",
            "Варіанти тимчасово недоступні",
            "Оновіть сторінку трохи пізніше або напишіть нам для підбору.",
            "Оберіть зручний канал. Ми напишемо лише один раз, коли потрібна конфігурація з'явиться.",
            "Канал сповіщення",
            "Як до вас звертатися",
            "Telegram прив'яжеться через бота з підтвердженням номера.",
            "Повідомити мене",
        )

        for locale, expected in matrix.items():
            with self.subTest(locale=locale):
                response = self.client.get(expected["path"])
                self.assertEqual(response.status_code, 200)
                body = response.content.decode("utf-8")
                for value in expected["required"]:
                    self.assertIn(value, body)
                for marker in ukrainian_markers:
                    self.assertNotIn(marker, body)

    def test_standard_pdp_editorial_links_use_locale_owned_labels_and_urls(self):
        matrix = {
            "ru": {
                "path": "/ru/product/locale-matrix-tee/",
                "prefix": "/ru",
                "required": (
                    "Топ-запросы для этой модели",
                    "Разделы каталога",
                    "Доставка и оплата",
                    "Размерная сетка",
                    "Уход за одеждой",
                    "Возврат и обмен",
                    "О бренде TwoComms",
                ),
            },
            "en": {
                "path": "/en/product/locale-matrix-tee/",
                "prefix": "/en",
                "required": (
                    "Top queries for this model",
                    "Catalog sections",
                    "Delivery &amp; payment",
                    "Size chart",
                    "Garment care",
                    "Returns &amp; exchanges",
                    "About TwoComms brand",
                ),
            },
        }

        for locale, expectations in matrix.items():
            with self.subTest(locale=locale):
                response = self.client.get(expectations["path"])
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "index, follow")
                rail = self._product_seo_landing(
                    response.content.decode("utf-8")
                )

                for value in expectations["required"]:
                    self.assertIn(value, rail)
                for route in (
                    "delivery",
                    "rozmirna-sitka",
                    "doglyad-za-odyagom",
                    "povernennya-ta-obmin",
                    "pro-brand",
                ):
                    self.assertIn(
                        f'href="{expectations["prefix"]}/{route}/"',
                        rail,
                    )

                for ukrainian in (
                    "Розділи каталогу",
                    "Доставка Новою Поштою",
                    "Розмірна сітка та посадка",
                    "Повернення за 14 днів",
                    "Замовити кастомний DTF-друк",
                ):
                    self.assertNotIn(ukrainian, rail)

                self.assertNotIn("?color=", rail)
                self.assertNotIn(
                    f'{expectations["prefix"]}/catalog/theme/',
                    rail,
                )
