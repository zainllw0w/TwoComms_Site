from pathlib import Path
from tempfile import TemporaryDirectory

import django
from django.apps import apps
from django.test import SimpleTestCase

from twocomms import settings as project_settings


class EnsureCompressOfflineTests(SimpleTestCase):
    def test_empty_manifest_disables_offline_compression(self):
        with TemporaryDirectory() as temp_dir:
            static_root = Path(temp_dir)
            manifest_path = static_root / "CACHE" / "manifest.json"
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text("{}", encoding="utf-8")

            original_static_root = project_settings.STATIC_ROOT
            project_settings.STATIC_ROOT = static_root
            try:
                with self.assertWarns(RuntimeWarning):
                    enabled = project_settings.ensure_compress_offline(True)
            finally:
                project_settings.STATIC_ROOT = original_static_root

        self.assertFalse(enabled)


class StorefrontViewExportsTests(SimpleTestCase):
    def test_llms_full_txt_is_exported_for_root_urlconf(self):
        if not apps.ready:
            django.setup()

        from storefront import views as storefront_views

        self.assertTrue(hasattr(storefront_views, "llms_full_txt"))
