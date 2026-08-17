import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase


class ProductionEnvironmentLoadingTests(SimpleTestCase):
    @staticmethod
    def _load_production_static_settings(static_root):
        django_root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env.update(
            {
                "DJANGO_SETTINGS_MODULE": "twocomms.production_settings",
                "SECRET_KEY": "test-secret",
                "TWC_RELEASE_STATIC_ROOT": static_root,
                "DB_ENGINE": "mysql",
                "DB_NAME": "test_database",
                "DB_USER": "test_user",
            }
        )
        env.pop("DJANGO_ENV_FILE", None)
        return subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from django.conf import settings; "
                    "print(settings.STATIC_ROOT); "
                    "print(settings.COMPRESS_ROOT)"
                ),
            ],
            cwd=django_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    def test_cpanel_environment_wins_over_env_file(self):
        settings_path = Path(__file__).with_name("production_settings.py")
        bootstrap = settings_path.read_text(encoding="utf-8").split(
            "from .settings import *",
            1,
        )[0]

        with TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env.production"
            env_path.write_text(
                "IG_APP_SECRET=secret-from-file\n"
                "ENV_FILE_ONLY=loaded-from-file\n",
                encoding="utf-8",
            )
            with patch.dict(
                "os.environ",
                {
                    "DJANGO_ENV_FILE": str(env_path),
                    "IG_APP_SECRET": "secret-from-cpanel",
                    "DB_ENGINE": "mysql",
                    "DB_NAME": "test_database",
                    "DB_USER": "test_user",
                },
                clear=True,
            ):
                exec(
                    compile(bootstrap, str(settings_path), "exec"),
                    {"__file__": str(settings_path)},
                )

                self.assertEqual(
                    __import__("os").environ["IG_APP_SECRET"],
                    "secret-from-cpanel",
                )
                self.assertEqual(
                    __import__("os").environ["ENV_FILE_ONLY"],
                    "loaded-from-file",
                )

    def test_release_static_root_is_shared_by_collectstatic_and_compressor(self):
        static_root = (
            "/home/qlknpodo/TWC/TwoComms_Site/releases/static/"
            + "a" * 40
        )

        result = self._load_production_static_settings(static_root)

        self.assertEqual(result.returncode, 0, result.stderr)
        resolved_static_root = Path(static_root).resolve()
        self.assertEqual(
            [Path(value) for value in result.stdout.splitlines()],
            [resolved_static_root, resolved_static_root],
        )

    def test_release_static_root_rejects_unsafe_paths(self):
        for unsafe_root in (
            "releases/static/" + "a" * 40,
            "/tmp/not-a-release/" + "a" * 40,
            "/home/qlknpodo/TWC/TwoComms_Site/releases/static/not-a-sha",
        ):
            with self.subTest(unsafe_root=unsafe_root):
                result = self._load_production_static_settings(unsafe_root)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("TWC_RELEASE_STATIC_ROOT", result.stderr)

    def test_selected_production_env_without_database_fails_closed(self):
        django_root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env.production"
            env_path.write_text("SECRET_KEY=test-secret\n", encoding="utf-8")
            env = os.environ.copy()
            env.update(
                {
                    "DJANGO_SETTINGS_MODULE": "twocomms.production_settings",
                    "DJANGO_ENV": "production",
                    "DJANGO_ENV_FILE": str(env_path),
                    "SECRET_KEY": "test-secret",
                }
            )
            for key in (
                "DB_ENGINE",
                "DB_NAME",
                "DB_USER",
                "DB_PASSWORD",
                "DB_HOST",
                "DB_PORT",
            ):
                env.pop(key, None)

            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "from django.conf import settings; "
                        "print(settings.DATABASES['default']['ENGINE'])"
                    ),
                ],
                cwd=django_root,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("production database", result.stderr.lower())

    def test_production_settings_module_without_env_file_fails_closed(self):
        django_root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env.update(
            {
                "DJANGO_SETTINGS_MODULE": "twocomms.production_settings",
                "DJANGO_ENV_FILE": str(django_root / "missing-production.env"),
                "SECRET_KEY": "test-secret",
            }
        )
        env.pop("DJANGO_ENV", None)
        for key in ("DB_ENGINE", "DB_NAME", "DB_USER"):
            env.pop(key, None)

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from django.conf import settings; "
                    "print(settings.DATABASES['default']['ENGINE'])"
                ),
            ],
            cwd=django_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("production database", result.stderr.lower())

    def test_production_sqlite_engine_is_rejected_even_with_database_names(self):
        django_root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env.production"
            env_path.write_text(
                "DB_ENGINE=sqlite\nDB_NAME=/tmp/production.sqlite3\nDB_USER=ignored\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env.update(
                {
                    "DJANGO_SETTINGS_MODULE": "twocomms.production_settings",
                    "DJANGO_ENV": "production",
                    "DJANGO_ENV_FILE": str(env_path),
                    "SECRET_KEY": "test-secret",
                }
            )
            for key in ("DB_ENGINE", "DB_NAME", "DB_USER"):
                env.pop(key, None)

            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "from django.conf import settings; "
                        "print(settings.DATABASES['default']['ENGINE'])"
                    ),
                ],
                cwd=django_root,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("mysql", result.stderr.lower())

    def test_base_settings_module_in_production_fails_closed(self):
        django_root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env.update(
            {
                "DJANGO_SETTINGS_MODULE": "twocomms.settings",
                "DJANGO_ENV": "production",
                "SECRET_KEY": "test-secret",
            }
        )
        for key in ("DB_ENGINE", "DB_NAME", "DB_USER"):
            env.pop(key, None)

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from django.conf import settings; "
                    "print(settings.DATABASES['default']['ENGINE'])"
                ),
            ],
            cwd=django_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("production database", result.stderr.lower())
