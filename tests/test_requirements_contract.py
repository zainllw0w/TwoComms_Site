"""Policy tests for the immutable Python 3.14 dependency contract."""

from __future__ import annotations

import re
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IN_PATH = ROOT / "twocomms" / "requirements.in"
LOCK_PATH = ROOT / "twocomms" / "requirements.lock"
COMPAT_PATH = ROOT / "twocomms" / "requirements.txt"
COMPILE_PATH = ROOT / "scripts" / "compile_requirements.sh"
HTTP_ECE_BUILDER_PATH = ROOT / "scripts" / "build_http_ece_wheel.py"


# These are the project's direct requirements.  Resolver-owned transitive
# packages (currently cffi and pycparser) deliberately do not belong here.
EXPECTED_DIRECT = {
    "django": "6.1",
    "asgiref": "3.9.1",
    "sqlparse": "0.5.3",
    "pillow": "11.3.0",
    "mysqlclient": "2.2.8",
    "cryptography": "50.0.0",
    "bleach": "6.3.0",
    "typing-extensions": "4.15.0",
    "django-compressor": "4.6.0",
    "rcssmin": "1.2.2",
    "rjsmin": "1.2.5",
    "django-redis": "5.4.0",
    "redis": "5.2.1",
    "hiredis": "3.3.1",
    "django-mathfilters": "1.0.0",
    "python-dotenv": "1.0.1",
    "social-auth-app-django": "5.6.0",
    "django-modeltranslation": "0.20.3",
    "whitenoise": "6.7.0",
    "requests": "2.32.5",
    "google-analytics-data": "0.22.0",
    "google-auth": "2.52.0",
    "phonenumbers": "9.0.12",
    "pywebpush": "2.3.0",
    "openai": "2.30.0",
    "markdown": "3.8.2",
    "openpyxl": "3.1.2",
    "python-docx": "1.1.0",
    "djangorestframework": "3.18.0",
    "drf-spectacular": "0.27.2",
    "django-ratelimit": "4.1.0",
    "facebook-business": "25.0.3",
    "capi-param-builder-python": "1.3.0",
    "coverage": "7.13.5",
    "pyjwt": "2.13.0",
}


_REQ_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9_.-]*)\s*==\s*([^\s\\;#]+)")
_HASH_RE = re.compile(r"--hash=sha256:[0-9a-f]{64}\b")


def _normalized(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _requirements(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        match = _REQ_RE.match(line)
        if match:
            result[_normalized(match.group(1))] = match.group(2)
    return result


class RequirementsContractTests(unittest.TestCase):
    def test_direct_runtime_requirements_are_exactly_pinned(self):
        requirements = _requirements(IN_PATH.read_text(encoding="utf-8"))
        self.assertEqual(requirements, EXPECTED_DIRECT)

    def test_required_security_and_api_packages_have_pins(self):
        requirements = _requirements(IN_PATH.read_text(encoding="utf-8"))
        self.assertEqual(requirements["google-analytics-data"], "0.22.0")
        self.assertEqual(requirements["google-auth"], "2.52.0")
        self.assertEqual(requirements["openai"], "2.30.0")
        self.assertEqual(requirements["pyjwt"], "2.13.0")
        self.assertGreaterEqual(tuple(map(int, requirements["cryptography"].split("."))), (50, 0, 0))

    def test_resolver_owned_transitives_and_unused_timezone_are_not_direct(self):
        requirements = _requirements(IN_PATH.read_text(encoding="utf-8"))
        self.assertNotIn("cffi", requirements)
        self.assertNotIn("pycparser", requirements)
        self.assertNotIn("pytz", requirements)

    def test_compatibility_requirements_delegates_only_to_lock(self):
        self.assertEqual(COMPAT_PATH.read_text(encoding="utf-8"), "-r requirements.lock\n")

    def test_lock_has_hashes_for_every_direct_requirement(self):
        lock_text = LOCK_PATH.read_text(encoding="utf-8")
        lock_requirements = _requirements(lock_text)
        for name, version in EXPECTED_DIRECT.items():
            self.assertEqual(lock_requirements.get(name), version, name)
        self.assertGreaterEqual(len(_HASH_RE.findall(lock_text)), len(lock_requirements))
        for block in re.split(r"\n(?=[A-Za-z0-9][A-Za-z0-9_.-]*==)", lock_text):
            if _REQ_RE.match(block):
                self.assertRegex(block, _HASH_RE, block.splitlines()[0])

    def test_compile_script_is_executable_and_fail_closed(self):
        mode = COMPILE_PATH.stat().st_mode
        self.assertTrue(mode & stat.S_IXUSR, "compile script must be executable")
        script = COMPILE_PATH.read_text(encoding="utf-8")
        for marker in (
            "uv 0.12.2",
            "--python-version 3.14.6",
            "--python-platform x86_64-manylinux_2_28",
            "--only-binary :all:",
            "--no-binary http-ece",
            "--no-binary mysqlclient",
            "--generate-hashes",
            "--resolution highest",
            "--exclude-newer 2026-08-07T00:00:00Z",
            "--exclude-newer-package djangorestframework=2026-08-08T00:00:00Z",
            "--no-emit-index-url",
            "mktemp",
            "mv",
        ):
            self.assertIn(marker, script)

    def test_compile_script_builds_http_ece_before_publishing_lock(self):
        script = COMPILE_PATH.read_text(encoding="utf-8")
        self.assertIn("HTTP_ECE_SDIST", script)
        self.assertIn("build_http_ece_wheel.py", script)
        self.assertIn("--wheel-dir", script)
        self.assertIn("--lock", script)
        self.assertIn("--source-date-epoch 315532800", script)
        self.assertLess(script.index("build_http_ece_wheel.py"), script.index("mv -f"))
        self.assertTrue(HTTP_ECE_BUILDER_PATH.is_file())

    def test_compile_is_byte_identical_from_clean_copies(self):
        """The resolver must receive a stable repo-relative input path."""

        fake_uv = """#!/bin/sh
set -eu
if [ "$1" = "--version" ]; then
    printf 'uv 0.12.2\\n'
    exit 0
fi
output=''
input=''
while [ "$#" -gt 0 ]; do
    if [ "$1" = "--output-file" ]; then
        output="$2"
        shift 2
        continue
    fi
    case "$1" in
        *.in) input="$1" ;;
    esac
    shift
done
printf '# -r %s\\nhttp-ece==1.2.1 \\\\\\n    --hash=sha256:%064d\\n' "$input" 0 > "$output"
"""
        fake_builder = """#!/usr/bin/env python3
raise SystemExit(0)
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outputs = []
            for index in ("one", "two"):
                copy = root / index
                (copy / "scripts").mkdir(parents=True)
                (copy / "twocomms").mkdir()
                shutil.copy2(COMPILE_PATH, copy / "scripts" / "compile_requirements.sh")
                (copy / "scripts" / "build_http_ece_wheel.py").write_text(
                    fake_builder, encoding="utf-8"
                )
                (copy / "scripts" / "build_http_ece_wheel.py").chmod(0o755)
                (copy / "twocomms" / "requirements.in").write_text(
                    "http-ece==1.2.1\\n", encoding="utf-8"
                )
                bin_dir = copy / "bin"
                bin_dir.mkdir()
                (bin_dir / "uv").write_text(fake_uv, encoding="utf-8")
                (bin_dir / "uv").chmod(0o755)
                compile_env = os.environ.copy()
                compile_env.update(
                    {
                        "PATH": f"{bin_dir}:{compile_env['PATH']}",
                        "UV_BIN": "uv",
                        "PYTHON_BIN": shutil.which("python3") or "python3",
                    }
                )
                result = subprocess.run(
                    ["sh", "scripts/compile_requirements.sh"],
                    cwd=copy,
                    env=compile_env,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                outputs.append((copy / "twocomms" / "requirements.lock").read_bytes())

            self.assertEqual(outputs[0], outputs[1])
            self.assertIn(b"# -r twocomms/requirements.in\n", outputs[0])
            self.assertNotIn(str(root).encode(), outputs[0])


if __name__ == "__main__":
    unittest.main()
