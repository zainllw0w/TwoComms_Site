"""Production settings must be selected by every deployed Django entrypoint."""

from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class WsgiEntrypointContractTests(unittest.TestCase):
    def test_wsgi_and_asgi_select_production_settings(self):
        for name in ("wsgi.py", "asgi.py"):
            with self.subTest(name=name):
                source = (
                    REPO_ROOT / "twocomms" / "twocomms" / name
                ).read_text(encoding="utf-8")
                self.assertIn(
                    "twocomms.production_settings",
                    source,
                    f"{name} must never fall back to SQLite-capable base settings",
                )

