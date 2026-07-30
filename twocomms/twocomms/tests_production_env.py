from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase


class ProductionEnvironmentLoadingTests(SimpleTestCase):
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
