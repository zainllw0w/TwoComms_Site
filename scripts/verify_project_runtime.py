#!/usr/bin/env python3
"""Fail unless the active interpreter matches the production runtime exactly."""

from __future__ import annotations

import importlib.metadata as metadata
import json
import platform
import sys
from collections.abc import Mapping


EXPECTED_VERSIONS = {
    "python": "3.14.6",
    "django": "6.1",
    "djangorestframework": "3.18.0",
    "mysqlclient": "2.2.8",
}


class RuntimeMismatch(RuntimeError):
    """Raised when the current process is not the supported project runtime."""


def validate_runtime(versions: Mapping[str, str]) -> dict[str, str]:
    normalized = {name: str(versions.get(name, "")) for name in EXPECTED_VERSIONS}
    mismatched = {
        name: {"expected": expected, "actual": normalized[name]}
        for name, expected in EXPECTED_VERSIONS.items()
        if normalized[name] != expected
    }
    if mismatched:
        names = ", ".join(sorted(mismatched))
        raise RuntimeMismatch(f"unsupported project runtime: {names}")
    return normalized


def current_versions() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "django": metadata.version("Django"),
        "djangorestframework": metadata.version("djangorestframework"),
        "mysqlclient": metadata.version("mysqlclient"),
    }


def main() -> int:
    payload = {
        "status": "failed",
        "implementation": platform.python_implementation(),
        **current_versions(),
    }
    try:
        if payload["implementation"] != "CPython":
            raise RuntimeMismatch("project runtime must use CPython")
        validate_runtime(payload)
    except (RuntimeMismatch, metadata.PackageNotFoundError):
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return 1
    payload["status"] = "ok"
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
