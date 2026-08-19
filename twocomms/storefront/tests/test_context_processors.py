from types import SimpleNamespace

from django.conf import settings
from django.contrib.sessions.backends.db import SessionStore
from django.test import SimpleTestCase

from storefront.context_processors import user_state_hint
from storefront.custom_print_config import SESSION_CUSTOM_CART_KEY


class UserStateHintTests(SimpleTestCase):
    def test_custom_print_cart_marks_cart_badge_as_syncable(self):
        session = SessionStore()
        session[SESSION_CUSTOM_CART_KEY] = {
            "custom:77": {
                "lead_id": 77,
                "quantity": 1,
                "final_total": 1800,
            }
        }
        request = SimpleNamespace(
            session=session,
            user=SimpleNamespace(is_authenticated=False),
        )

        payload = user_state_hint(request)

        self.assertTrue(payload["sync_cart_badge"])


class StorefrontLocaleContractConfigurationTests(SimpleTestCase):
    def test_storefront_locale_contract_context_processor_is_registered(self):
        context_processors = settings.TEMPLATES[0]["OPTIONS"]["context_processors"]

        self.assertIn(
            "storefront.context_processors.storefront_locale_contract",
            context_processors,
        )
