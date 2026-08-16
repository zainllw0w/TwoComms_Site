#!/usr/bin/env python3
"""Run the project suite through explicit non-DTF Django test labels."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "twocomms"

# Every app is expanded into test modules so the SQLite suite can exclude
# modules that require a disposable MariaDB server.
TEST_APP_PACKAGES = (
    "accounts",
    "finance",
    "management",
    "orders",
    "product_catalog",
    "productcolors",
    "reviews",
    "storefront",
    "warehouse",
)
MARIADB_ONLY_TEST_MODULES = frozenset(
    {
        "management.tests_ig_mariadb_follow_ugc",
        "management.tests_ig_mariadb_lifecycle",
        "management.tests_test_settings_mariadb",
        "warehouse.tests.test_mariadb_uuid_compatibility",
    }
)
PROJECT_TEST_MODULES = (
    "twocomms.tests_error_views",
    "twocomms.tests_middleware",
    "twocomms.tests_rate_limit_middleware",
    "twocomms.tests_log_handlers",
    "twocomms.tests_production_env",
)


def discover_non_dtf_test_labels() -> tuple[str, ...]:
    labels = set(PROJECT_TEST_MODULES)
    for package in TEST_APP_PACKAGES:
        package_path = APP_ROOT / package
        for path in sorted(package_path.rglob("test*.py")):
            if path.name == "__init__.py":
                continue
            module = ".".join(path.relative_to(APP_ROOT).with_suffix("").parts)
            if module not in MARIADB_ONLY_TEST_MODULES:
                labels.add(module)
    return tuple(sorted(labels))


# Passing module labels prevents root-level unittest discovery from importing
# excluded subdomain tests or test-settings modules.
NON_DTF_TEST_LABELS = discover_non_dtf_test_labels()


def build_command(*, python: str, settings: str, verbosity: int = 1) -> list[str]:
    return [
        python,
        str(APP_ROOT / "manage.py"),
        "test",
        *NON_DTF_TEST_LABELS,
        f"--settings={settings}",
        "--noinput",
        "-v",
        str(verbosity),
    ]


def run_suite(
    *,
    python: str,
    settings: str,
    output: Path | None = None,
    pythonpath_prefix: str | None = None,
    verbosity: int = 1,
) -> int:
    environment = os.environ.copy()
    environment["DJANGO_SETTINGS_MODULE"] = settings
    environment["SECRET_KEY"] = "non-dtf-suite-runner"
    if pythonpath_prefix:
        current = environment.get("PYTHONPATH", "")
        environment["PYTHONPATH"] = os.pathsep.join(
            part for part in (pythonpath_prefix, current) if part
        )
    completed = subprocess.run(
        build_command(python=python, settings=settings, verbosity=verbosity),
        cwd=APP_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    rendered = f"{completed.stdout}\n{completed.stderr}"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--settings", default="test_settings_no_network_non_dtf")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pythonpath-prefix")
    parser.add_argument("--verbosity", type=int, default=1)
    args = parser.parse_args(argv)
    return run_suite(
        python=args.python,
        settings=args.settings,
        output=args.output,
        pythonpath_prefix=args.pythonpath_prefix,
        verbosity=args.verbosity,
    )


if __name__ == "__main__":
    raise SystemExit(main())
