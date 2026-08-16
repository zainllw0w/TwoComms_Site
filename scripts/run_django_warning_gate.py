#!/usr/bin/env python3
"""Run focused Django 7 deprecation checks and reject unknown warnings."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "twocomms"
WARNING_NAMES = (
    "RemovedInDjango70Warning",
    "DeprecationWarning",
    "PendingDeprecationWarning",
)
VENDOR_ALLOWLIST: dict[str, dict[str, str]] = {}


def classify_warning_lines(lines: list[str]) -> dict[str, list[str]]:
    warnings = [
        line.strip()
        for line in lines
        if any(f"{warning_name}:" in line for warning_name in WARNING_NAMES)
    ]
    return {
        "allowed": [],
        "blocked": warnings,
    }


def _safe_environment() -> dict[str, str]:
    blocked_markers = (
        "TOKEN",
        "SECRET",
        "PASSWORD",
        "DATABASE_URL",
        "DB_",
        "API_KEY",
        "ACCESS_KEY",
        "CREDENTIAL",
    )
    environment = {
        name: value
        for name, value in os.environ.items()
        if not any(marker in name.upper() for marker in blocked_markers)
        and name not in {"DJANGO_SETTINGS_MODULE", "DJANGO_ENV_FILE"}
    }
    environment.update(
        {
            "SECRET_KEY": "django-warning-gate",
            "DJANGO_SETTINGS_MODULE": "test_settings_no_network_non_dtf",
            "PYTHONPATH": os.pathsep.join((str(APP_ROOT), str(ROOT))),
            "PYTHONWARNINGS": "always",
        }
    )
    return environment


def run_gate(*, python: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as directory:
        command_evidence = Path(directory) / "commands.json"
        commands = (
            (
                "check",
                [
                    python,
                    "manage.py",
                    "check",
                    "--database=default",
                    "--settings=test_settings_no_network_non_dtf",
                ],
                APP_ROOT,
            ),
            (
                "commands",
                [
                    python,
                    str(ROOT / "scripts" / "check_management_commands.py"),
                    "--output",
                    str(command_evidence),
                ],
                ROOT,
            ),
            (
                "compatibility-tests",
                [
                    python,
                    "-m",
                    "unittest",
                    "tests.test_django61_compatibility",
                    "tests.test_django61_warning_prerequisites",
                    "-v",
                ],
                ROOT,
            ),
        )
        results = []
        warning_lines = []
        failed_commands = []
        for name, command, cwd in commands:
            completed = subprocess.run(
                command,
                cwd=cwd,
                env=_safe_environment(),
                capture_output=True,
                text=True,
                timeout=15 * 60,
                check=False,
            )
            combined = f"{completed.stdout}\n{completed.stderr}"
            warning_lines.extend(combined.splitlines())
            results.append({"name": name, "returncode": completed.returncode})
            if completed.returncode:
                failed_commands.append(name)
                print(combined[-8000:], file=sys.stderr)

    classified = classify_warning_lines(warning_lines)
    for line in classified["blocked"]:
        print(line, file=sys.stderr)
    status = "ok" if not failed_commands and not classified["blocked"] else "failed"
    return {
        "status": status,
        "commands": results,
        "failed_commands": failed_commands,
        "blocked_warning_count": len(classified["blocked"]),
        "allowed_vendor_warning_count": len(classified["allowed"]),
        "vendor_allowlist": VENDOR_ALLOWLIST,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    payload = run_gate(python=args.python)
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        args.output.chmod(0o600)
    print(rendered, end="")
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
