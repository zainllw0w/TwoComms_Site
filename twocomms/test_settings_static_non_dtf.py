"""Production-like static/compressor settings in a disposable directory."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from test_settings_no_network_non_dtf import *  # noqa: F401,F403


_raw_static_root = (os.environ.get("TWC_TEST_STATIC_ROOT") or "").strip()
if not _raw_static_root:
    raise ImproperlyConfigured("TWC_TEST_STATIC_ROOT is required")
STATIC_ROOT = Path(_raw_static_root).expanduser().resolve()
if not STATIC_ROOT.is_absolute() or STATIC_ROOT == Path("/"):
    raise ImproperlyConfigured("TWC_TEST_STATIC_ROOT must be an absolute directory")
if STATIC_ROOT == BASE_DIR or BASE_DIR in STATIC_ROOT.parents:
    raise ImproperlyConfigured("TWC_TEST_STATIC_ROOT must be outside the repository")

DEBUG = False
STATIC_URL = "/static/"
COMPRESS_ROOT = STATIC_ROOT
COMPRESS_URL = STATIC_URL
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True
COMPRESS_CSS_HASHING_METHOD = "content"
COMPRESS_JS_HASHING_METHOD = "content"
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    "compressor.finders.CompressorFinder",
]
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
WHITENOISE_USE_FINDERS = False
WHITENOISE_AUTOREFRESH = False
TEST_STATIC_PIPELINE = "production-like-non-dtf"
