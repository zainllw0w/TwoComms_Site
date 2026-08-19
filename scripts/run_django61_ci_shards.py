#!/usr/bin/env python3
"""Run the reviewed Django 6.1 policy-test shards concurrently."""

from __future__ import annotations

import argparse
import concurrent.futures
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence, TextIO

import django


ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "twocomms"
EXPECTED_PYTHON = "3.14.6"
EXPECTED_DJANGO = "6.1"
DEFAULT_JOBS = 2

# Keep these shards explicit. Each module is no-network and uses only
# process-local state or TemporaryDirectory-managed filesystem state.
STABLE_SHARDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "django-compatibility",
        ("tests.test_django61_compatibility",),
    ),
    (
        "policy-contracts",
        (
            "tests.test_django61_stage0_tooling",
            "tests.test_django61_warning_prerequisites",
            "tests.test_ig_baseline_runner",
            "tests.test_requirements_contract",
            "tests.test_verify_locked_requirements",
        ),
    ),
)

_PRODUCTION_ENV_NAMES = {"DATABASE_URL", "DJANGO_ENV_FILE"}
_PROVIDER_ENV_PREFIXES = (
    "BINOTEL_",
    "CELERY_",
    "DB_",
    "FACEBOOK_",
    "GEMINI_",
    "GOOGLE_",
    "MANAGEMENT_TG_",
    "MANAGER_TG_",
    "META_",
    "MONOBANK_",
    "NOVA_POSHTA_",
    "OPENAI_",
    "REDIS_",
    "TELEGRAM_",
    "TIKTOK_",
)


@dataclass(frozen=True)
class ShardResult:
    name: str
    returncode: int
    stdout: str
    stderr: str
    elapsed_seconds: float


def validate_runtime() -> None:
    python_version = platform.python_version()
    django_version = django.get_version()
    if python_version != EXPECTED_PYTHON or django_version != EXPECTED_DJANGO:
        raise RuntimeError(
            "runtime_mismatch: "
            f"python={python_version} django={django_version} "
            f"expected_python={EXPECTED_PYTHON} expected_django={EXPECTED_DJANGO}"
        )


def build_environment(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    environment = dict(os.environ if environ is None else environ)
    for name in tuple(environment):
        if name in _PRODUCTION_ENV_NAMES or name.startswith(_PROVIDER_ENV_PREFIXES):
            environment.pop(name, None)

    existing_pythonpath = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(APP_ROOT), existing_pythonpath) if part
    )
    environment.update(
        {
            "DJANGO_SETTINGS_MODULE": "test_settings_no_network_non_dtf",
            "SECRET_KEY": "django61-ci-stable-shards",
            "TEST_NETWORK_POLICY": "deny-external",
        }
    )
    return environment


def build_command(
    modules: Sequence[str],
    *,
    python: str = sys.executable,
    verbosity: int = 1,
) -> list[str]:
    if not modules:
        raise ValueError("A CI shard must contain at least one test module")
    if any("dtf" in module.casefold() for module in modules):
        raise ValueError("DTF tests are outside the Django 6.1 stable-shard scope")
    return [
        python,
        "-m",
        "unittest",
        *modules,
        f"-{'v' * verbosity}" if verbosity else "-q",
    ]


def _run_one(
    shard: tuple[str, tuple[str, ...]],
    *,
    python: str,
    verbosity: int,
    environment: Mapping[str, str],
    command_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> ShardResult:
    name, modules = shard
    started = time.monotonic()
    completed = command_runner(
        build_command(modules, python=python, verbosity=verbosity),
        cwd=ROOT,
        env=dict(environment),
        capture_output=True,
        text=True,
        check=False,
    )
    return ShardResult(
        name=name,
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
        elapsed_seconds=time.monotonic() - started,
    )


def run_shards(
    *,
    jobs: int = DEFAULT_JOBS,
    python: str = sys.executable,
    verbosity: int = 1,
    environment: Mapping[str, str] | None = None,
    command_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    output: TextIO = sys.stdout,
) -> int:
    if jobs < 1 or jobs > len(STABLE_SHARDS):
        raise ValueError(f"jobs must be between 1 and {len(STABLE_SHARDS)}")

    child_environment = build_environment(environment)
    started = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as executor:
        futures = [
            executor.submit(
                _run_one,
                shard,
                python=python,
                verbosity=verbosity,
                environment=child_environment,
                command_runner=command_runner,
            )
            for shard in STABLE_SHARDS
        ]
        results = [future.result() for future in futures]

    for result in results:
        output.write(
            f"[{result.name}] exit={result.returncode} "
            f"elapsed={result.elapsed_seconds:.3f}s\n"
        )
        if result.stdout:
            output.write(result.stdout)
            if not result.stdout.endswith("\n"):
                output.write("\n")
        if result.stderr:
            output.write(result.stderr)
            if not result.stderr.endswith("\n"):
                output.write("\n")

    failed = [result.name for result in results if result.returncode]
    output.write(
        "Django 6.1 CI shards: "
        f"status={'failed' if failed else 'passed'} "
        f"jobs={jobs} shards={len(results)} "
        f"elapsed={time.monotonic() - started:.3f}s"
    )
    if failed:
        output.write(f" failed={','.join(failed)}")
    output.write("\n")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--jobs",
        type=int,
        choices=range(1, len(STABLE_SHARDS) + 1),
        default=DEFAULT_JOBS,
    )
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--verbosity", type=int, choices=range(0, 4), default=1)
    args = parser.parse_args(argv)
    try:
        validate_runtime()
        return run_shards(
            jobs=args.jobs,
            python=args.python,
            verbosity=args.verbosity,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Django 6.1 CI shards failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
