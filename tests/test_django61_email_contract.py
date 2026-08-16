"""Static and settings contracts for the Django 6.1 mailers migration."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "twocomms"
MAILER_ALIASES = ["default", "reports", "transactional"]
DEPRECATED_EMAIL_KWARGS = {
    "auth_password",
    "auth_user",
    "connection",
    "fail_silently",
}
EXPECTED_CALL_GRAPH = {
    ("twocomms/management/views.py", "commercial_offer_email"): "transactional",
    (
        "twocomms/management/views.py",
        "commercial_offer_email_resend_api",
    ): "transactional",
    (
        "twocomms/management/views.py",
        "commercial_offer_email_send_api",
    ): "transactional",
    (
        "twocomms/management/views.py",
        "commercial_offer_email_send_test_api",
    ): "transactional",
    ("twocomms/orders/email_receipt.py", "send_order_receipt_email"): "transactional",
    (
        "twocomms/orders/management/commands/recover_checkouts.py",
        "handle",
    ): "transactional",
    (
        "twocomms/storefront/management/commands/send_utm_report.py",
        "handle",
    ): "reports",
    ("twocomms/storefront/services/restock.py", "_send_email"): "transactional",
}
EMAIL_CONSTRUCTORS = {"EmailMessage", "EmailMultiAlternatives"}
DIRECT_SENDERS = {"mail_admins", "mail_managers", "send_mail", "send_mass_mail"}


def _call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _keyword_names(call: ast.Call) -> set[str]:
    return {keyword.arg for keyword in call.keywords if keyword.arg is not None}


def _using_alias(call: ast.Call) -> str | None:
    for keyword in call.keywords:
        if keyword.arg == "using" and isinstance(keyword.value, ast.Constant):
            return keyword.value.value
    return None


class _EmailInventoryVisitor(ast.NodeVisitor):
    def __init__(self, relative_path: str):
        self.relative_path = relative_path
        self.function_stack: list[str] = []
        self.call_sites: list[tuple[str, str]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node: ast.Call) -> None:
        if self.function_stack and _call_name(node) in EMAIL_CONSTRUCTORS | DIRECT_SENDERS:
            self.call_sites.append((self.relative_path, self.function_stack[-1]))
        self.generic_visit(node)


class EmailCallGraphContractTests(unittest.TestCase):
    def _production_python_files(self):
        for path in APP_ROOT.rglob("*.py"):
            relative_parts = {
                part.casefold()
                for part in path.relative_to(APP_ROOT).parts
            }
            if relative_parts & {"dtf", "migrations", "tests", "__pycache__"}:
                continue
            if path.name.casefold().startswith("test"):
                continue
            yield path

    def test_complete_non_dtf_call_graph_uses_explicit_mailer_aliases(self):
        inventory: list[tuple[str, str]] = []
        parsed: dict[str, ast.Module] = {}
        for path in self._production_python_files():
            relative_path = path.relative_to(ROOT).as_posix()
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            parsed[relative_path] = tree
            visitor = _EmailInventoryVisitor(relative_path)
            visitor.visit(tree)
            inventory.extend(visitor.call_sites)

        self.assertEqual(sorted(inventory), sorted(EXPECTED_CALL_GRAPH))

        for (relative_path, function_name), expected_alias in EXPECTED_CALL_GRAPH.items():
            functions = [
                node
                for node in ast.walk(parsed[relative_path])
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == function_name
            ]
            self.assertEqual(len(functions), 1, (relative_path, function_name))
            calls = [node for node in ast.walk(functions[0]) if isinstance(node, ast.Call)]
            entry_calls = [
                call
                for call in calls
                if _call_name(call) in EMAIL_CONSTRUCTORS | DIRECT_SENDERS
            ]
            self.assertEqual(len(entry_calls), 1, (relative_path, function_name))

            entry_call = entry_calls[0]
            if _call_name(entry_call) in DIRECT_SENDERS:
                delivery_call = entry_call
            else:
                send_calls = [call for call in calls if _call_name(call) == "send"]
                self.assertEqual(len(send_calls), 1, (relative_path, function_name))
                delivery_call = send_calls[0]

            self.assertEqual(
                _using_alias(delivery_call),
                expected_alias,
                (relative_path, function_name),
            )
            for call in (entry_call, delivery_call):
                self.assertFalse(
                    _keyword_names(call) & DEPRECATED_EMAIL_KWARGS,
                    (relative_path, function_name, _keyword_names(call)),
                )

    def test_example_port_587_declares_tls_and_disables_ssl(self):
        values = {}
        for raw_line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key] = value

        self.assertEqual(values["EMAIL_PORT"], "587")
        self.assertEqual(values["EMAIL_USE_TLS"].casefold(), "true")
        self.assertEqual(values["EMAIL_USE_SSL"].casefold(), "false")


class MailerSettingsContractTests(unittest.TestCase):
    def _run(self, statement: str, *, environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-Wa", "-c", statement],
            cwd=APP_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_no_network_profile_constructs_every_alias_without_mail_warnings(self):
        environment = os.environ.copy()
        environment.update(
            {
                "DJANGO_SETTINGS_MODULE": "test_settings_no_network_non_dtf",
                "PYTHONPATH": str(APP_ROOT),
                "SECRET_KEY": "mailers-no-network-contract",
            }
        )
        statement = """
import json
import django
django.setup()
from django.conf import settings
from django.core.checks import Tags, run_checks
from django.core.mail import mailers

payload = {
    "aliases": sorted(settings.MAILERS),
    "backends": {
        alias: mailers[alias].__class__.__module__ + "." + mailers[alias].__class__.__name__
        for alias in settings.MAILERS
    },
    "issues": [issue.id for issue in run_checks(tags=[Tags.mail])],
}
print(json.dumps(payload, sort_keys=True))
"""
        result = self._run(statement, environment=environment)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("The EMAIL_", result.stderr)
        self.assertNotIn("fail_silently", result.stderr)
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(payload["aliases"], MAILER_ALIASES)
        self.assertEqual(payload["issues"], [])
        self.assertTrue(
            all("locmem.EmailBackend" in backend for backend in payload["backends"].values())
        )

    def test_project_smtp_configuration_constructs_every_alias_and_passes_mail_e001(self):
        environment = os.environ.copy()
        environment.update(
            {
                "DEBUG": "False",
                "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
                "EMAIL_HOST": "smtp.example.invalid",
                "EMAIL_HOST_PASSWORD": "contract-password",
                "EMAIL_HOST_USER": "mailer@example.invalid",
                "EMAIL_PORT": "587",
                "EMAIL_TIMEOUT": "7",
                "EMAIL_USE_SSL": "False",
                "EMAIL_USE_TLS": "True",
                "PYTHONPATH": str(APP_ROOT),
                "SECRET_KEY": "mailers-smtp-contract",
            }
        )
        statement = """
import json
from twocomms import settings as project_settings
from django.conf import settings

settings.configure(
    DEFAULT_CHARSET="utf-8",
    MAILERS=project_settings.MAILERS,
    SECRET_KEY="mailers-smtp-contract",
)
import django
django.setup()
from django.core.checks import Tags, run_checks
from django.core.mail import mailers

connections = {alias: mailers[alias] for alias in settings.MAILERS}
payload = {
    "aliases": sorted(settings.MAILERS),
    "backends": {
        alias: connection.__class__.__module__ + "." + connection.__class__.__name__
        for alias, connection in connections.items()
    },
    "hosts": {alias: connection.host for alias, connection in connections.items()},
    "ports": {alias: connection.port for alias, connection in connections.items()},
    "tls": {alias: connection.use_tls for alias, connection in connections.items()},
    "ssl": {alias: connection.use_ssl for alias, connection in connections.items()},
    "issues": [
        issue.id
        for issue in run_checks(tags=[Tags.mail], include_deployment_checks=True)
    ],
}
print(json.dumps(payload, sort_keys=True))
"""
        result = self._run(statement, environment=environment)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(payload["aliases"], MAILER_ALIASES)
        self.assertEqual(payload["issues"], [])
        self.assertTrue(all("smtp.EmailBackend" in value for value in payload["backends"].values()))
        self.assertEqual(set(payload["hosts"].values()), {"smtp.example.invalid"})
        self.assertEqual(set(payload["ports"].values()), {587})
        self.assertEqual(set(payload["tls"].values()), {True})
        self.assertEqual(set(payload["ssl"].values()), {False})


if __name__ == "__main__":
    unittest.main()
