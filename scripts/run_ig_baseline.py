#!/usr/bin/env python3
"""Run the deterministic, no-network Instagram-management baseline."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = REPO_ROOT / "twocomms"
SETTINGS = "test_settings_no_network"
SENSITIVE_ENV_MARKERS = (
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "DATABASE_URL",
    "DB_",
    "API_KEY",
    "ACCESS_KEY",
    "ACCESS_TOKEN",
    "PRIVATE_KEY",
    "CREDENTIAL",
)
SENSITIVE_ENV_EXCEPTIONS = {"PYTHONHASHSEED"}
COMMAND_TIMEOUT_SECONDS = 30 * 60
GATES = (
    (
        "management-tests",
        (
            "{python}",
            "manage.py",
            "test",
            "management.tests_test_settings_mariadb",
            "management.tests_ig_production_contract",
            "management.tests_ig_engine_health",
            "management.tests_ig_webhook_security",
            "management.tests_ig_live_reply_priority",
            "management.tests_ig_conversation_analysis_jobs",
            "management.tests_ig_followup_delivery_fsm",
            "management.tests_telephony_call.AdminCallReviewTest",
            "--settings=test_settings_no_network",
            "--noinput",
        ),
    ),
    (
        "check",
        ("{python}", "manage.py", "check", "--settings=test_settings_no_network"),
    ),
    (
        "migration-drift",
        (
            "{python}",
            "manage.py",
            "makemigrations",
            "--check",
            "--dry-run",
            "--settings=test_settings_no_network",
        ),
    ),
    ("compileall", ("{python}", "-m", "compileall", "-q", "management")),
    ("diff-check", ("git", "diff", "--check")),
)


def _safe_environment() -> dict[str, str]:
    environment = {
        name: value
        for name, value in os.environ.items()
        if name not in {"DJANGO_ENV_FILE", "DJANGO_SETTINGS_MODULE"}
        and name not in SENSITIVE_ENV_EXCEPTIONS
        and not any(marker in name.upper() for marker in SENSITIVE_ENV_MARKERS)
    }
    environment["SECRET_KEY"] = "test-secret-key-for-no-network-profile"
    environment["DJANGO_ENV"] = "development"
    environment["DJANGO_SETTINGS_MODULE"] = SETTINGS
    environment["PYTHONPATH"] = os.pathsep.join(
        path for path in (str(APP_ROOT), environment.get("PYTHONPATH", "")) if path
    )
    return environment


def _render_command(template: tuple[str, ...], python: str) -> list[str]:
    return [python if item == "{python}" else item for item in template]


def _summarize_output(stdout: str, stderr: str) -> dict[str, int]:
    import re

    rendered = f"{stdout}\n{stderr}"
    summary = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    match = re.search(r"Ran (\d+) tests?", rendered)
    if match:
        summary["tests"] = int(match.group(1))
    for key, pattern in (
        ("failures", r"failures=(\d+)"),
        ("errors", r"errors=(\d+)"),
        ("skipped", r"skipped=(\d+)"),
    ):
        match = re.search(pattern, rendered)
        if match:
            summary[key] = int(match.group(1))
    # Django's unittest runner writes the final summary to stderr when
    # verbosity is enabled; the combined stream above keeps evidence stable
    # across Python/Django runner implementations.
    return summary


def run_baseline(*, python: str, evidence_path: Path) -> int:
    started = time.monotonic()
    gates: list[dict[str, object]] = []
    status = "passed"
    failed_gate = ""
    environment = _safe_environment()

    for name, template in GATES:
        gate_started = time.monotonic()
        command = _render_command(template, python)
        gate_timeout = False
        try:
            completed = subprocess.run(
                command,
                cwd=APP_ROOT,
                env=environment,
                capture_output=True,
                text=True,
                timeout=COMMAND_TIMEOUT_SECONDS,
                check=False,
            )
            returncode = completed.returncode
            summary = _summarize_output(completed.stdout, completed.stderr)
        except subprocess.TimeoutExpired:
            returncode = 124
            summary = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
            gate_timeout = True
        gate = {
            "name": name,
            "returncode": int(returncode),
            "duration_seconds": round(time.monotonic() - gate_started, 3),
            **summary,
        }
        if gate_timeout:
            gate["timeout_seconds"] = COMMAND_TIMEOUT_SECONDS
        gates.append(gate)
        if returncode:
            status = "failed"
            failed_gate = name
            break

    payload: dict[str, object] = {
        "version": 1,
        "status": status,
        "repo_sha": _repo_sha(),
        "python": str(Path(python).resolve()),
        "settings": SETTINGS,
        "cwd": str(APP_ROOT),
        "database": "sqlite3",
        "network_policy": "deny-external",
        "gates": gates,
        "duration_seconds": round(time.monotonic() - started, 3),
    }
    if failed_gate:
        payload["failed_gate"] = failed_gate
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = evidence_path.with_name(f".{evidence_path.name}.tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    os.replace(temporary, evidence_path)
    print(json.dumps({"status": status, "failed_gate": failed_gate}, sort_keys=True))
    return 1 if failed_gate else 0


def _repo_sha() -> str:
    try:
        result = subprocess.run(
            ("git", "rev-parse", "HEAD"),
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        return run_baseline(python=args.python, evidence_path=args.evidence)
    except Exception as exc:
        print(f"baseline runner failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
