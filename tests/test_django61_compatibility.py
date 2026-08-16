"""Regression tests for application imports under Django 6.1."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DJANGO_ROOT = ROOT / "twocomms"


class Django61CompatibilityTests(unittest.TestCase):
    def _run_django_script(self, script: str) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["DJANGO_SETTINGS_MODULE"] = "test_settings_no_network_non_dtf"
        environment["SECRET_KEY"] = "codex-django-upgrade-test"
        return subprocess.run(
            [
                sys.executable,
                "-c",
                f"import django; django.setup();\n{script}",
            ],
            cwd=DJANGO_ROOT,
            env=environment,
            capture_output=True,
            text=True,
        )

    def _run_django_import(self, statement: str) -> subprocess.CompletedProcess[str]:
        return self._run_django_script(statement)

    def test_running_runtime_is_exact_django_61(self):
        result = self._run_django_import(
            "import platform; "
            "assert platform.python_version() == '3.14.6'; "
            "assert django.get_version() == '6.1'"
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_review_models_import_with_django_61(self):
        result = self._run_django_import(
            "from reviews.models import ReviewVote; "
            "assert any(c.name == 'rev_vote_user_or_anon_required' for c in ReviewVote._meta.constraints)"
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_drf_router_import_with_django_61(self):
        result = self._run_django_import("from rest_framework.routers import DefaultRouter")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_django_admin_filters_do_not_shadow_storefront_filters(self):
        result = self._run_django_import(
            "from django.template import Context, engines; "
            "engine = engines['django'].engine; "
            "assert {'to_object_display_value', 'truncated_unordered_list'} <= "
            "set(engine.template_libraries['admin_filters'].filters); "
            "assert 'storefront_filters' in engine.template_libraries; "
            "template = engine.from_string('{% load storefront_filters %}'"
            " '{{ value|get_item:\"key\" }}'); "
            "assert template.render(Context({'value': {'key': 'ok'}})) == 'ok'"
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_mysql_backend_uses_official_django61_driver(self):
        requirements = (DJANGO_ROOT / "requirements.in").read_text(encoding="utf-8")
        self.assertRegex(requirements, r"(?m)^mysqlclient==2\.2\.[1-9][0-9]*\s*$")
        self.assertNotRegex(requirements, r"(?m)^PyMySQL==")

        for settings_path in (
            DJANGO_ROOT / "twocomms" / "settings.py",
            DJANGO_ROOT / "twocomms" / "production_settings.py",
            DJANGO_ROOT / "twocomms" / "__init__.py",
        ):
            source = settings_path.read_text(encoding="utf-8")
            self.assertNotIn("install_as_MySQLdb", source, settings_path.name)

        result = self._run_django_import(
            "import MySQLdb; "
            "assert tuple(MySQLdb.version_info) >= (2, 2, 1)"
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def _assert_integration_import(self, statement: str) -> None:
        result = self._run_django_import(statement)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_django_compressor_imports_with_django_61(self):
        self._assert_integration_import("import compressor; assert compressor")

    def test_django_redis_imports_with_django_61(self):
        self._assert_integration_import("import django_redis; assert django_redis")

    def test_django_redis_backend_constructs_lazily_without_connection(self):
        result = self._run_django_script(
            """
from django.core.cache import caches
from django.test import override_settings
from django_redis.cache import RedisCache
from django_redis.client import DefaultClient

cache_settings = {
    "django61_contract": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://redis.example.invalid:6379/7",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "IGNORE_EXCEPTIONS": True,
        },
    },
}
with override_settings(CACHES=cache_settings):
    backend = caches["django61_contract"]
    client = backend.client
    assert isinstance(backend, RedisCache)
    assert isinstance(client, DefaultClient)
    assert client._server == ["redis://redis.example.invalid:6379/7"]
    assert client._clients == [None]
"""
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_django_ratelimit_imports_with_django_61(self):
        self._assert_integration_import(
            "from django_ratelimit.decorators import ratelimit; assert ratelimit"
        )

    def test_django_ratelimit_enforces_post_limit_without_network(self):
        result = self._run_django_script(
            """
from django.conf import settings
from django.core.cache import cache
from django.test import RequestFactory
from accounts.ajax_auth_views import ajax_login

assert settings.CACHES["default"]["BACKEND"].endswith("LocMemCache")
cache.clear()
factory = RequestFactory()
responses = []
last_request = None
for _ in range(11):
    last_request = factory.post(
        "/accounts/ajax/login/",
        {},
        REMOTE_ADDR="203.0.113.44",
    )
    responses.append(ajax_login(last_request).status_code)
assert responses[:10] == [200] * 10, responses
assert responses[10] == 429, responses
assert getattr(last_request, "limited", False) is True
"""
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_drf_spectacular_imports_with_django_61(self):
        self._assert_integration_import(
            "import drf_spectacular; assert drf_spectacular"
        )

    def test_drf_spectacular_builds_non_dtf_schema_with_44_operations(self):
        result = self._run_django_script(
            """
from drf_spectacular.generators import SchemaGenerator

schema = SchemaGenerator(urlconf="twocomms.urls").get_schema(
    request=None,
    public=True,
)
paths = schema["paths"]
operation_names = {"get", "put", "post", "patch", "delete", "head", "options", "trace"}
operations = sum(
    sum(method in operation_names for method in path_item)
    for path_item in paths.values()
)
assert len(paths) == 44, len(paths)
assert operations == 44, operations
assert all("dtf" not in path.casefold() for path in paths), paths
"""
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_social_auth_app_django_imports_with_django_61(self):
        self._assert_integration_import(
            "import social_django; assert social_django"
        )

    def test_social_auth_urls_and_callback_surface_without_provider_call(self):
        result = self._run_django_script(
            """
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from django.urls import resolve, reverse

assert "social_core.backends.google.GoogleOAuth2" in settings.AUTHENTICATION_BACKENDS
backend_kwargs = {"backend": "google-oauth2"}
expected_urls = {
    "social:begin": "/oauth/login/google-oauth2/",
    "social:complete": "/oauth/complete/google-oauth2/",
    "social_fallback:begin": "/social/login/google-oauth2/",
    "social_fallback:complete": "/social/complete/google-oauth2/",
}
for view_name, expected_url in expected_urls.items():
    assert reverse(view_name, kwargs=backend_kwargs) == expected_url

factory = RequestFactory()
session = {}
begin_path = reverse("social:begin", kwargs={"backend": "google-oauth2"})
begin_request = factory.get(begin_path)
begin_request.user = AnonymousUser()
begin_request.session = session
begin_match = resolve(begin_path)
begin_response = begin_match.func(begin_request, **begin_match.kwargs)
assert begin_response.status_code == 302
assert begin_response["Location"].startswith("https://accounts.google.com/")
state = session["google-oauth2_state"]

complete_path = reverse("social:complete", kwargs={"backend": "google-oauth2"})
complete_request = factory.get(
    complete_path,
    {"state": state, "code": "offline-contract"},
)
complete_request.user = AnonymousUser()
complete_request.session = session
complete_match = resolve(complete_path)
with patch(
    "social_core.backends.google.GoogleOAuth2.auth_complete",
    return_value=None,
) as provider_call:
    complete_response = complete_match.func(
        complete_request,
        **complete_match.kwargs,
    )
assert complete_response.status_code == 302
assert complete_response["Location"] == "/login/"
assert provider_call.call_count == 1
"""
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_whitenoise_imports_with_django_61(self):
        self._assert_integration_import("import whitenoise; assert whitenoise")

    def test_mathfilters_template_library_renders(self):
        result = self._run_django_import(
            "from django.template import Context, engines; "
            "template = engines['django'].engine.from_string("
            "'{% load mathfilters %}{{ left|mul:right }}'); "
            "assert template.render(Context({'left': 6, 'right': 7})) == '42'"
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_default_mailer_uses_django_61_mailers_api(self):
        result = self._run_django_import(
            "from django.conf import settings; from django.core.mail import mailers; "
            "assert sorted(settings.MAILERS) == ['default', 'reports', 'transactional']; "
            "assert all(mailers[alias].__class__.__name__ == 'EmailBackend' "
            "for alias in settings.MAILERS)"
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
