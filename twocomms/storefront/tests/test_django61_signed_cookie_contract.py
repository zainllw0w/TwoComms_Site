"""Executable compatibility matrix for Django 6.1 signed-cookie salts."""

from __future__ import annotations

import ast
from collections import Counter
from importlib import import_module
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.messages import constants
from django.contrib.messages.storage.base import Message
from django.contrib.messages.storage.cookie import CookieStorage
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core import signing
from django.core.cache import caches
from django.http import HttpRequest, HttpResponse
from django.test import SimpleTestCase, TestCase


ROOT = Path(__file__).resolve().parents[3]
APP_ROOT = ROOT / "twocomms"

SIGNING_APIS = {
    "Signer",
    "TimestampSigner",
    "dumps",
    "get_cookie_signer",
    "get_signed_cookie",
    "loads",
    "set_signed_cookie",
}

EXPECTED_CUSTOM_SIGNING_CALLS = Counter(
    {
        (
            "twocomms/management/bot_views.py",
            "_manual_order_url_for_client",
            "dumps",
            "'storefront.manual-order.ig-client'",
        ): 1,
        (
            "twocomms/management/email_templates/twocomms_cp.py",
            "_cp_wrap_click",
            "dumps",
            "'cp.click'",
        ): 1,
        (
            "twocomms/management/views.py",
            "_resolve_profile_from_start_payload",
            "Signer",
            "'management.bot.bind'",
        ): 1,
        (
            "twocomms/management/views.py",
            "cp_sign_click_url",
            "dumps",
            "_CP_CLICK_SALT",
        ): 1,
        (
            "twocomms/management/views.py",
            "cp_track_click",
            "loads",
            "_CP_CLICK_SALT",
        ): 1,
        (
            "twocomms/orders/nova_poshta_checkout.py",
            "build_city_choice_token",
            "dumps",
            "CITY_TOKEN_SALT",
        ): 1,
        (
            "twocomms/orders/nova_poshta_checkout.py",
            "build_warehouse_choice_token",
            "dumps",
            "WAREHOUSE_TOKEN_SALT",
        ): 1,
        (
            "twocomms/orders/nova_poshta_checkout.py",
            "resolve_delivery_selection",
            "loads",
            "CITY_TOKEN_SALT",
        ): 1,
        (
            "twocomms/orders/nova_poshta_checkout.py",
            "resolve_delivery_selection",
            "loads",
            "WAREHOUSE_TOKEN_SALT",
        ): 1,
        (
            "twocomms/orders/telegram_status_links.py",
            "build_order_action_token",
            "TimestampSigner",
            "SIGNER_SALT",
        ): 1,
        (
            "twocomms/orders/telegram_status_links.py",
            "verify_order_action_token",
            "TimestampSigner",
            "SIGNER_SALT",
        ): 1,
        (
            "twocomms/storefront/views/ig_checkout.py",
            "_save_grant",
            "dumps",
            "GRANT_SALT",
        ): 1,
        (
            "twocomms/storefront/views/ig_checkout.py",
            "_load_grant",
            "loads",
            "GRANT_SALT",
        ): 1,
        (
            "twocomms/storefront/views/ig_checkout.py",
            "_load_grant",
            "dumps",
            "GRANT_SALT",
        ): 1,
        (
            "twocomms/storefront/views/manual_orders.py",
            "_resolve_ig_client_context",
            "loads",
            "IG_MANUAL_CONTEXT_SALT",
        ): 1,
        (
            "twocomms/storefront/views/manual_orders.py",
            "_form_context",
            "dumps",
            "IG_MANUAL_CONTEXT_SALT",
        ): 1,
        (
            "twocomms/storefront/views/qr.py",
            "_promo_from_cookie",
            "loads",
            "QR_COOKIE_SALT",
        ): 1,
        (
            "twocomms/storefront/views/qr.py",
            "qr_thanks",
            "dumps",
            "QR_COOKIE_SALT",
        ): 1,
        (
            "twocomms/twocomms/middleware.py",
            "build_social_auth_state_cookie",
            "dumps",
            "SOCIAL_AUTH_STATE_COOKIE_SALT",
        ): 1,
        (
            "twocomms/twocomms/middleware.py",
            "process_request",
            "loads",
            "SOCIAL_AUTH_STATE_COOKIE_SALT",
        ): 1,
    }
)

OBJECT_FORMATS = (
    (
        "social-auth-state cookie",
        "twocomms.social-auth-state.v1",
        {"backend": "google-oauth2", "state": "state-1"},
        False,
    ),
    ("commercial-offer click", "cp.click", "https://twocomms.shop/", False),
    (
        "manual Instagram order context",
        "storefront.manual-order.ig-client",
        {"client_id": 17},
        False,
    ),
    (
        "Nova Poshta city choice",
        "orders.nova_poshta.city_choice",
        {"label": "Kyiv", "city_ref": "city-1"},
        True,
    ),
    (
        "Nova Poshta warehouse choice",
        "orders.nova_poshta.warehouse_choice",
        {"label": "Warehouse 1", "ref": "warehouse-1"},
        True,
    ),
    (
        "Instagram checkout grant",
        "twocomms.instagram-checkout.grant.v1",
        {"proposal_id": "proposal-1", "revision": 1},
        True,
    ),
    ("QR promo cookie payload", "twc.qr.promo", "PROMO-1", False),
)


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return None


class _SigningInventoryVisitor(ast.NodeVisitor):
    def __init__(self, relative_path: str, tree: ast.Module):
        self.relative_path = relative_path
        self.function_stack: list[str] = []
        self.module_aliases = {"django.core.signing"}
        self.direct_aliases: dict[str, str] = {}
        self.calls: Counter[tuple[str, str, str, str]] = Counter()
        self._collect_imports(tree)

    def _collect_imports(self, tree: ast.Module) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "django.core.signing":
                        self.module_aliases.add(alias.asname or alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module == "django.core":
                    for alias in node.names:
                        if alias.name == "signing":
                            self.module_aliases.add(alias.asname or alias.name)
                elif node.module == "django.core.signing":
                    for alias in node.names:
                        if alias.name in SIGNING_APIS:
                            self.direct_aliases[alias.asname or alias.name] = alias.name

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node: ast.Call) -> None:
        operation = None
        dotted = _dotted_name(node.func)
        if isinstance(node.func, ast.Name):
            operation = self.direct_aliases.get(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            owner = _dotted_name(node.func.value)
            if owner in self.module_aliases and node.func.attr in SIGNING_APIS:
                operation = node.func.attr
            elif dotted in {
                "django.core.signing." + api for api in SIGNING_APIS
            }:
                operation = node.func.attr
            elif node.func.attr in {"get_signed_cookie", "set_signed_cookie"}:
                operation = node.func.attr

        if operation:
            salt = ""
            for keyword in node.keywords:
                if keyword.arg == "salt":
                    salt = ast.unparse(keyword.value)
                    break
            function_name = self.function_stack[-1] if self.function_stack else "<module>"
            self.calls[(self.relative_path, function_name, operation, salt)] += 1
        self.generic_visit(node)


class Django61SignedCookieMatrixTests(SimpleTestCase):
    def test_project_uses_django_default_for_legacy_salt_fallback(self):
        from twocomms import settings as project_settings

        self.assertNotIn(
            "SIGNED_COOKIE_LEGACY_SALT_FALLBACK",
            vars(project_settings),
        )
        self.assertIs(settings.SIGNED_COOKIE_LEGACY_SALT_FALLBACK, False)

    def test_complete_non_dtf_custom_signing_inventory_has_no_http_cookie_api(self):
        actual: Counter[tuple[str, str, str, str]] = Counter()
        for path in APP_ROOT.rglob("*.py"):
            relative_parts = {
                part.casefold() for part in path.relative_to(APP_ROOT).parts
            }
            if relative_parts & {"dtf", "migrations", "tests", "__pycache__"}:
                continue
            if path.name.casefold().startswith("test"):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            visitor = _SigningInventoryVisitor(path.relative_to(ROOT).as_posix(), tree)
            visitor.visit(tree)
            actual.update(visitor.calls)

        self.assertEqual(actual, EXPECTED_CUSTOM_SIGNING_CALLS)
        self.assertFalse(
            {call[2] for call in actual} & {"get_signed_cookie", "set_signed_cookie"}
        )

    def test_all_custom_salted_formats_bypass_http_cookie_salt_derivation(self):
        with patch(
            "django.core.signing._unsign_cookie",
            side_effect=AssertionError("custom signing must not use HTTP cookie salts"),
        ):
            for label, salt, payload, compress in OBJECT_FORMATS:
                with self.subTest(label=label):
                    token = signing.dumps(payload, salt=salt, compress=compress)
                    self.assertEqual(signing.loads(token, salt=salt), payload)

            legacy_bind = signing.Signer(salt="management.bot.bind")
            self.assertEqual(legacy_bind.unsign(legacy_bind.sign("17-code")), "17-code")

            action_link = signing.TimestampSigner(
                salt="orders.telegram-action-link"
            )
            self.assertEqual(
                action_link.unsign(action_link.sign("17:ship"), max_age=60),
                "17:ship",
            )

    def test_cookie_messages_use_their_own_stable_signer(self):
        self.assertEqual(
            settings.MESSAGE_STORAGE,
            "django.contrib.messages.storage.fallback.FallbackStorage",
        )
        self.assertIs(FallbackStorage.storage_classes[0], CookieStorage)
        storage = CookieStorage(HttpRequest())
        self.assertEqual(storage.signer.salt, CookieStorage.key_salt)
        encoded = storage._encode([Message(constants.INFO, "Saved")])

        with patch(
            "django.core.signing._unsign_cookie",
            side_effect=AssertionError("message cookies do not use HTTP cookie salts"),
        ):
            decoded = storage._decode(encoded)

        self.assertEqual([message.message for message in decoded], ["Saved"])

    def test_http_signed_cookie_rejects_legacy_salt_and_accepts_v2(self):
        cookie_name = "contract_cookie"
        purpose_salt = "purpose"
        response = HttpResponse()
        response.set_signed_cookie(cookie_name, "current", salt=purpose_salt)

        request = HttpRequest()
        request.COOKIES[cookie_name] = response.cookies[cookie_name].value
        self.assertEqual(
            request.get_signed_cookie(cookie_name, salt=purpose_salt),
            "current",
        )

        legacy_signer = signing.get_cookie_signer(
            salt=f"{cookie_name}{purpose_salt}"
        )
        legacy_value = legacy_signer.sign("legacy")
        self.assertEqual(legacy_signer.unsign(legacy_value), "legacy")
        request.COOKIES[cookie_name] = legacy_value

        with self.assertRaises(signing.BadSignature):
            request.get_signed_cookie(cookie_name, salt=purpose_salt)


class CachedDbSessionSaltIsolationTests(TestCase):
    def test_cached_db_session_cookie_is_an_opaque_server_side_key(self):
        self.assertEqual(
            settings.SESSION_ENGINE,
            "django.contrib.sessions.backends.cached_db",
        )
        engine = import_module(settings.SESSION_ENGINE)
        session = engine.SessionStore()
        session["cart"] = {"sku": "tee-1", "quantity": 2}
        session.save()
        session_key = session.session_key
        caches["default"].delete(session.cache_key)

        with patch(
            "django.core.signing._unsign_cookie",
            side_effect=AssertionError("cached_db sessions do not use signed cookies"),
        ):
            restored = engine.SessionStore(session_key=session_key)
            self.assertEqual(
                restored["cart"],
                {"sku": "tee-1", "quantity": 2},
            )

        self.assertNotIn(":", session_key)
