#!/usr/bin/env python3
"""Build sanitized coverage counts for the active non-DTF Django surface."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "twocomms"


def _is_non_dtf(path: Path) -> bool:
    try:
        parts = path.relative_to(ROOT).parts
    except ValueError:
        parts = path.parts
    normalized = tuple(part.casefold() for part in parts)
    return "dtf" not in normalized and normalized[-1] != "urls_dtf.py"


def _count_urls(patterns) -> int:
    from django.urls import URLResolver

    count = 0
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            count += _count_urls(pattern.url_patterns)
        else:
            count += 1
    return count


def _repo_sha() -> str:
    completed = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def build_inventory() -> dict[str, object]:
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(APP_ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "test_settings_no_network_non_dtf")
    os.environ.setdefault("SECRET_KEY", "non-dtf-inventory")

    import django

    django.setup()
    from django.apps import apps
    from django.urls import get_resolver
    from scripts.check_management_commands import discover_command_modules

    app_names = [config.name for config in apps.get_app_configs()]
    files = list(APP_ROOT.rglob("*"))
    counts = {
        "models": len(list(apps.get_models())),
        "url_patterns": _count_urls(get_resolver().url_patterns),
        "templates": sum(
            path.is_file() and path.suffix == ".html" and _is_non_dtf(path)
            for path in files
        ),
        "python_files": sum(
            path.is_file() and path.suffix == ".py" and _is_non_dtf(path)
            for path in files
        ),
        "javascript_files": sum(
            path.is_file() and path.suffix == ".js" and _is_non_dtf(path)
            for path in files
        ),
        "management_commands": len(discover_command_modules()),
    }
    return {
        "status": "ok",
        "repo_sha": _repo_sha(),
        "settings": "test_settings_no_network_non_dtf",
        "dtf_scope": "excluded",
        "dtf_app_loaded": "dtf" in app_names or "dtf.apps.DtfConfig" in app_names,
        "counts": counts,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    payload = build_inventory()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    args.output.chmod(0o600)
    print(json.dumps({"status": payload["status"], "counts": payload["counts"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
