from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "scripts" / "run_ig_baseline.py"
APP_ROOT = REPO_ROOT / "twocomms"


class BaselineRunnerContractTests(unittest.TestCase):
    def _run(self, *args: str, cwd: Path | None = None, env: dict[str, str] | None = None):
        child_env = dict(os.environ)
        child_env.update(env or {})
        return subprocess.run(
            [sys.executable, str(RUNNER), *args],
            cwd=cwd or REPO_ROOT,
            env=child_env,
            capture_output=True,
            text=True,
            check=False,
        )

    @staticmethod
    def _fake_python(
        directory: Path,
        *,
        fail_tests: bool = False,
        summary_on_stderr: bool = False,
    ) -> Path:
        executable = directory / "fake-python"
        if fail_tests:
            body = (
                "#!/bin/sh\n"
                "case \"$*\" in\n"
                "  *'manage.py test'*) echo 'Ran 7 tests in 0.01s'; exit 1 ;;\n"
                "  *) echo SHOULD_NOT_RUN >&2; exit 9 ;;\n"
                "esac\n"
            )
        else:
            if summary_on_stderr:
                output = (
                    "echo 'Ran 7 tests in 0.01s' >&2\n"
                    "echo 'OK (skipped=1)' >&2"
                )
            else:
                output = "echo 'Ran 7 tests in 0.01s'\necho 'OK (skipped=1)'"
            body = f"#!/bin/sh\n{output}\n"
        executable.write_text(body, encoding="utf-8")
        executable.chmod(0o755)
        return executable

    def test_runner_resolves_repo_from_its_file_from_two_cwds(self):
        for cwd in (REPO_ROOT, Path(tempfile.gettempdir())):
            with self.subTest(cwd=cwd), tempfile.TemporaryDirectory() as directory:
                evidence = Path(directory) / "evidence.json"
                result = self._run(
                    "--python",
                    str(self._fake_python(Path(directory))),
                    "--evidence",
                    str(evidence),
                    cwd=cwd,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                payload = json.loads(evidence.read_text(encoding="utf-8"))
                self.assertEqual(payload["cwd"], str(APP_ROOT))

    def test_runner_supplies_only_a_nonproduction_structural_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory) / "evidence.json"
            result = self._run(
                "--python",
                str(self._fake_python(Path(directory))),
                "--evidence",
                str(evidence),
                env={
                    "SECRET_KEY": "production-secret",
                    "DATABASE_URL": "mysql://prod:secret@example.invalid/prod",
                    "TELEGRAM_BOT_TOKEN": "prod-token",
                    "DJANGO_ENV_FILE": "/tmp/production.env",
                },
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(evidence.read_text(encoding="utf-8"))
            rendered = json.dumps(payload, sort_keys=True)
            self.assertNotIn("production-secret", rendered)
            self.assertNotIn("prod-token", rendered)
            self.assertNotIn("mysql://", rendered)
            self.assertEqual(payload["settings"], "test_settings_no_network_non_dtf")
            self.assertEqual(payload["network_policy"], "deny-external")

    def test_runner_rejects_unmocked_external_network(self):
        with tempfile.TemporaryDirectory() as directory:
            probe = Path(directory) / "probe.py"
            probe.write_text(
                "import socket\n"
                "socket.create_connection(('198.51.100.1', 9), timeout=1)\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import sys; sys.path.insert(0, %r); "
                        "import test_settings_no_network; exec(compile(open(%r).read(), %r, 'exec'))"
                    ) % (str(APP_ROOT), str(probe), str(probe)),
                ],
                cwd=directory,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("external network", result.stderr.lower())

    def test_network_profile_rejects_external_udp(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import sys,socket; sys.path.insert(0, %r); "
                    "import test_settings_no_network; "
                    "socket.socket(socket.AF_INET,socket.SOCK_DGRAM).sendto(b'x',('198.51.100.1',9))"
                ) % str(APP_ROOT),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("external network", result.stderr.lower())

    def test_network_profile_rejects_three_argument_udp_sendto(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import sys,socket; sys.path.insert(0, %r); "
                    "import test_settings_no_network; "
                    "socket.socket(socket.AF_INET,socket.SOCK_DGRAM).sendto("
                    "b'x',0,('198.51.100.1',9))"
                ) % str(APP_ROOT),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("external network", result.stderr.lower())

    def test_network_profile_rejects_direct_hostname_resolution(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import sys,socket; sys.path.insert(0, %r); "
                    "import test_settings_no_network; "
                    "socket.gethostbyname('provider.example.invalid')"
                ) % str(APP_ROOT),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("external network", result.stderr.lower())

    def test_migration_gate_uses_real_non_dtf_migration_profile(self):
        source = RUNNER.read_text(encoding="utf-8")
        self.assertIn("test_settings_migrations_non_dtf", source)
        self.assertIn("--database=default", source)
        self.assertNotIn('"--settings=test_settings_no_network",', source)

    def test_runner_emits_sanitized_machine_readable_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory) / "evidence.json"
            result = self._run(
                "--python",
                str(self._fake_python(Path(directory))),
                "--evidence",
                str(evidence),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(evidence.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "passed")
            self.assertIsInstance(payload["gates"], list)
            self.assertTrue(payload["gates"])
            self.assertEqual(payload["gates"][0]["tests"], 7)
            self.assertEqual(payload["gates"][0]["skipped"], 1)
            self.assertNotIn("stdout", payload)
            self.assertNotIn("stderr", payload)
            self.assertEqual(evidence.stat().st_mode & 0o777, 0o600)
            self.assertIn("status", result.stdout)

    def test_runner_summarizes_django_result_written_to_stderr(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory) / "evidence.json"
            result = self._run(
                "--python",
                str(self._fake_python(Path(directory), summary_on_stderr=True)),
                "--evidence",
                str(evidence),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(evidence.read_text(encoding="utf-8"))
            self.assertEqual(payload["gates"][0]["tests"], 7)
            self.assertEqual(payload["gates"][0]["skipped"], 1)

    def test_runner_stops_on_first_failed_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory) / "evidence.json"
            result = self._run(
                "--python",
                str(self._fake_python(Path(directory), fail_tests=True)),
                "--evidence",
                str(evidence),
            )
            self.assertEqual(result.returncode, 1)
            payload = json.loads(evidence.read_text(encoding="utf-8"))
            self.assertEqual(payload["failed_gate"], "management-tests")
            self.assertEqual(len(payload["gates"]), 1)


if __name__ == "__main__":
    unittest.main()
