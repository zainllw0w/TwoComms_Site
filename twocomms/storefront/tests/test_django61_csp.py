import re
from pathlib import Path

from django.contrib.auth.models import AnonymousUser
from django.conf import settings
from django.http import HttpResponse
from django.middleware.csp import ContentSecurityPolicyMiddleware
from django.template import engines
from django.test import RequestFactory, SimpleTestCase
from django.utils.csp import CSP

from twocomms.middleware import SecurityHeadersMiddleware


class Django61CSPTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @staticmethod
    def render_response(request):
        template = engines["django"].from_string(
            "<script{% csp_nonce_attr %}>window.test = true;</script>"
        )
        return HttpResponse(template.render({}, request=request))

    def middleware_response(self, host):
        request = self.factory.get("/", HTTP_HOST=host)
        request.user = AnonymousUser()
        legacy_headers = SecurityHeadersMiddleware(self.render_response)
        django_csp = ContentSecurityPolicyMiddleware(legacy_headers)
        return django_csp(request)

    def test_builtin_django_csp_is_report_only_and_uses_template_nonce(self):
        response = self.middleware_response("twocomms.shop")

        self.assertNotIn("Content-Security-Policy", response)
        policy = response["Content-Security-Policy-Report-Only"]
        nonce = re.search(r"'nonce-([^']+)'", policy).group(1)

        self.assertIn(f'nonce="{nonce}"', response.content.decode())
        self.assertIn("report-uri /csp-report/", policy)
        self.assertIn("https://*.google.com.ua", policy)
        self.assertIn("'unsafe-inline'", policy)
        self.assertIn("'unsafe-eval'", policy)
        self.assertEqual(settings.SECURE_CSP, {})
        self.assertIn(CSP.NONCE, settings.SECURE_CSP_REPORT_ONLY["script-src"])

    def test_dtf_host_is_outside_the_csp_rollout(self):
        response = self.middleware_response("dtf.twocomms.shop")

        self.assertEqual(
            response["Content-Security-Policy"],
            settings.CONTENT_SECURITY_POLICY,
        )
        self.assertNotIn("Content-Security-Policy-Report-Only", response)

    def test_common_base_inline_scripts_use_the_django_nonce_tag(self):
        template_path = (
            Path(settings.BASE_DIR)
            / "twocomms_django_theme"
            / "templates"
            / "base.html"
        )
        source = template_path.read_text(encoding="utf-8")
        inline_script_tags = [
            match.group(0)
            for match in re.finditer(r"<script[^>]*>", source)
            if " src=" not in match.group(0)
        ]

        self.assertGreater(len(inline_script_tags), 0)
        self.assertEqual(
            [tag for tag in inline_script_tags if "{% csp_nonce_attr %}" not in tag],
            [],
        )
