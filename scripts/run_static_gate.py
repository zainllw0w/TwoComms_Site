#!/usr/bin/env python3
"""Exercise the production-like WhiteNoise and offline-compressor pipeline."""

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


def _environment(static_root: Path) -> dict[str, str]:
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
            "SECRET_KEY": "static-gate",
            "DJANGO_SETTINGS_MODULE": "test_settings_static_non_dtf",
            "TWC_TEST_STATIC_ROOT": str(static_root),
            "PYTHONPATH": str(APP_ROOT),
        }
    )
    return environment


def _run(command: list[str], *, environment: dict[str, str]) -> None:
    completed = subprocess.run(
        command,
        cwd=APP_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=20 * 60,
        check=False,
    )
    if completed.returncode:
        print(f"{completed.stdout}\n{completed.stderr}"[-10000:], file=sys.stderr)
        raise RuntimeError(f"static gate command failed: {command[2]}")


def _validate_render_probe_payload(payload: dict[str, object]) -> dict[str, int]:
    static_urls = int(payload.get("rendered_static_urls", 0))
    compressor_urls = int(payload.get("rendered_compressor_urls", 0))
    missing_assets = payload.get("missing_assets")
    if (
        static_urls < 1
        or compressor_urls < 1
        or not isinstance(missing_assets, list)
        or missing_assets
    ):
        raise RuntimeError("rendered static asset validation failed")
    return {
        "rendered_static_urls": static_urls,
        "rendered_compressor_urls": compressor_urls,
    }


def _render_probe(
    *, python: str, environment: dict[str, str]
) -> dict[str, int]:
    probe = r'''import json
import re
from pathlib import Path
from urllib.parse import urlsplit

import django

django.setup()
from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.template.loader import get_template

rendered = get_template("base.html").render({"is_home": False})
static_urls = [
    staticfiles_storage.url(path)
    for path in ("css/support-hub.css", "css/language-suggestion.css")
]
compressor_urls = sorted(
    set(re.findall(r'["\'](/static/CACHE/[^"\']+)["\']', rendered))
)
all_urls = [*static_urls, *compressor_urls]
missing = []
for url in all_urls:
    relative = urlsplit(url).path.removeprefix(settings.STATIC_URL).lstrip("/")
    if not relative or not (Path(settings.STATIC_ROOT) / relative).is_file():
        missing.append(relative or "invalid")
missing.extend(url for url in static_urls if url not in rendered)
print(json.dumps({
    "rendered_static_urls": sum(url in rendered for url in static_urls),
    "rendered_compressor_urls": len(compressor_urls),
    "missing_assets": missing,
}, sort_keys=True))
'''
    completed = subprocess.run(
        [python, "-c", probe],
        cwd=APP_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=5 * 60,
        check=False,
    )
    if completed.returncode:
        print(f"{completed.stdout}\n{completed.stderr}"[-10000:], file=sys.stderr)
        raise RuntimeError("static template render probe failed")
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise RuntimeError("static template render probe emitted invalid evidence") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("static template render probe emitted invalid evidence")
    return _validate_render_probe_payload(payload)


def run_gate(*, python: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="twocomms-static-") as directory:
        static_root = Path(directory).resolve()
        environment = _environment(static_root)
        _run(
            [
                python,
                "manage.py",
                "collectstatic",
                "--noinput",
                "--clear",
                "--verbosity=0",
                "--settings=test_settings_static_non_dtf",
            ],
            environment=environment,
        )
        _run(
            [
                python,
                "manage.py",
                "compress",
                "--force",
                "--verbosity=0",
                "--settings=test_settings_static_non_dtf",
            ],
            environment=environment,
        )

        static_manifest_path = static_root / "staticfiles.json"
        compressor_manifest_path = static_root / "CACHE" / "manifest.json"
        static_manifest = json.loads(static_manifest_path.read_text(encoding="utf-8"))
        compressor_manifest = json.loads(
            compressor_manifest_path.read_text(encoding="utf-8")
        )
        if not isinstance(static_manifest, dict) or not static_manifest.get("paths"):
            raise RuntimeError("WhiteNoise staticfiles manifest is empty")
        if not isinstance(compressor_manifest, dict) or not compressor_manifest:
            raise RuntimeError("django-compressor offline manifest is empty")
        render_evidence = _render_probe(python=python, environment=environment)
        asset_count = sum(path.is_file() for path in static_root.rglob("*"))
        return {
            "status": "ok",
            "settings": "test_settings_static_non_dtf",
            "dtf_scope": "excluded",
            "static_manifest_entries": len(static_manifest["paths"]),
            "compressor_manifest_entries": len(compressor_manifest),
            "asset_files": asset_count,
            **render_evidence,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        payload = run_gate(python=args.python)
    except BaseException as exc:
        payload = {"status": "failed", "error": type(exc).__name__}
        exit_code = 1
    else:
        exit_code = 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    args.output.chmod(0o600)
    print(json.dumps(payload, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
