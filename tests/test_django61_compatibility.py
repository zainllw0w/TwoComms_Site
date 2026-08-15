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
    def _run_django_import(self, statement: str) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["DJANGO_SETTINGS_MODULE"] = "test_settings"
        environment["SECRET_KEY"] = "codex-django-upgrade-test"
        return subprocess.run(
            [sys.executable, "-c", f"import django; django.setup(); {statement}"],
            cwd=DJANGO_ROOT,
            env=environment,
            capture_output=True,
            text=True,
        )

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


if __name__ == "__main__":
    unittest.main()
