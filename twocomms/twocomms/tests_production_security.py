import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase


STRONG_PREFIXED_SECRET = (
    "django-insecure-"
    "A1b2C3d4E5f6G7h8I9j0K!l@M#n$O%p^Q&r*S(t)U_v-W+x=Yz"
)


class ProductionSecuritySettingsTests(SimpleTestCase):
    @staticmethod
    def _run_python(code, **environment):
        django_root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env.update(
            {
                "DEBUG": "False",
                "DJANGO_ENV_FILE": os.devnull,
                "DJANGO_SETTINGS_MODULE": "twocomms.production_settings",
                "DB_ENGINE": "mysql",
                "DB_NAME": "contract_database",
                "DB_USER": "contract_user",
                "SECRET_KEY": STRONG_PREFIXED_SECRET,
            }
        )
        env.update(environment)
        return subprocess.run(
            [sys.executable, "-c", code],
            cwd=django_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    def test_proxy_https_redirect_contract_replaces_framework_warning(self):
        result = self._run_python(
            "import django; django.setup(); "
            "from django.conf import settings; "
            "from django.core.management import call_command; "
            "assert settings.SECURE_SSL_REDIRECT is False; "
            "call_command('check', '--deploy', '--tag', 'security')",
            SECURE_SSL_REDIRECT="False",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("security.W008", result.stdout + result.stderr)

    def test_proxy_https_redirect_contract_fails_closed_for_invalid_config(self):
        result = self._run_python(
            "from pathlib import Path; "
            "from tempfile import TemporaryDirectory; "
            "from twocomms.production_settings import "
            "_validate_proxy_https_redirect_config; "
            "temp = TemporaryDirectory(); "
            "path = Path(temp.name) / '.htaccess'; "
            "path.write_text('RewriteCond %{HTTPS} off\\n' "
            "'RewriteRule ^(.*)$ https://%{HTTP_HOST}%{REQUEST_URI} [L,R=301]\\n', "
            "encoding='utf-8'); "
            "_validate_proxy_https_redirect_config(path)",
            SECURE_SSL_REDIRECT="False",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("https redirect", result.stderr.lower())

    def test_weak_prefixed_secret_fails_closed_without_echoing_secret(self):
        weak_secret = "django-insecure-" + "a" * 48

        result = self._run_python(
            "from django.conf import settings; print(settings.SECRET_KEY)",
            SECRET_KEY=weak_secret,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("production secret key", result.stderr.lower())
        self.assertNotIn(weak_secret, result.stderr)
        self.assertNotIn(weak_secret, result.stdout)

    def test_security_middleware_redirects_all_direct_http_entrypoints(self):
        result = self._run_python(
            "import django; django.setup(); "
            "from django.http import HttpResponse; "
            "from django.middleware.security import SecurityMiddleware; "
            "from django.test import RequestFactory; "
            "middleware = SecurityMiddleware(lambda request: HttpResponse()); "
            "factory = RequestFactory(); "
            "hosts = ('twocomms.shop', 'management.twocomms.shop', "
            "'storage.twocomms.shop', 'fin.twocomms.shop'); "
            "paths = ('/sw.js', '/static/sw.js', '/tg-manager/webhook/callback/', "
            "'/bot/webhook/callback/'); "
            "responses = ((host, path, middleware.process_request("
            "factory.get(path, HTTP_HOST=host))) for host in hosts for path in paths); "
            "assert all(response.status_code == 301 and "
            "response['Location'] == f'https://{host}{path}' "
            "for host, path, response in responses)",
            SECURE_SSL_REDIRECT="True",
        )

        self.assertEqual(result.returncode, 0, result.stderr)

        # Post-deploy QA must repeat HTTP -> HTTPS 301 probes for the four
        # non-DTF vhosts above. DTF is explicitly outside this change.

    def test_strong_prefixed_secret_is_preserved_without_framework_warnings(self):
        result = self._run_python(
            "import django; django.setup(); "
            "from django.conf import settings; "
            "from django.core.management import call_command; "
            "assert settings.SECRET_KEY == __import__('os').environ['SECRET_KEY']; "
            "call_command('check', '--deploy', '--tag', 'security')",
            SECURE_SSL_REDIRECT="False",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("security.W008", result.stdout + result.stderr)
        self.assertNotIn("security.W009", result.stdout + result.stderr)
