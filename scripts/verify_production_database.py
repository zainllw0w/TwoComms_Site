#!/usr/bin/env python3
"""Fail closed unless production uses one bundled MariaDB provider."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import re
import sys
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Mapping


EXPECTED_FIELD_TYPES = [253, 253, 253, 246, 253]
MAX_PROBE_ITERATIONS = 1000
_BUNDLED_PROVIDER_RE = re.compile(r"libmariadb-[0-9a-f]+\.so\.3$")
PROBE_SQL = """
SELECT VERSION(),
    @@sql_mode,
    @@default_storage_engine,
    CAST(123.45 AS DECIMAL(10, 2)) AS decimal_probe,
    CAST('probe' AS CHAR(16)) AS string_probe
"""


class DatabaseProbeError(RuntimeError):
    """The runtime cannot safely use the authoritative production database."""


def _loaded_library_paths() -> set[Path]:
    maps = Path("/proc/self/maps")
    if not maps.is_file():
        raise DatabaseProbeError("loaded MariaDB libraries cannot be inspected")
    loaded = set()
    try:
        lines = maps.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        raise DatabaseProbeError("loaded MariaDB libraries cannot be inspected") from exc
    for line in lines:
        path = line.rsplit(maxsplit=1)[-1]
        if path.startswith("/"):
            loaded.add(Path(path.removesuffix(" (deleted)")).resolve())
    return loaded


def _verify_provider_record(provider: Path) -> str:
    site_packages = provider.parent.parent
    records = [
        path
        for path in site_packages.glob("mysqlclient-*.dist-info/RECORD")
        if path.is_file() and not path.is_symlink()
    ]
    if len(records) != 1:
        raise DatabaseProbeError(
            "bundled mysqlclient MariaDB library has no unique wheel RECORD"
        )
    relative_provider = provider.relative_to(site_packages).as_posix()
    try:
        with records[0].open(encoding="utf-8", newline="") as handle:
            rows = [row for row in csv.reader(handle) if row and row[0] == relative_provider]
    except (OSError, UnicodeError, csv.Error) as exc:
        raise DatabaseProbeError("mysqlclient wheel RECORD is unreadable") from exc
    if len(rows) != 1 or len(rows[0]) != 3:
        raise DatabaseProbeError(
            "bundled MariaDB library is missing from mysqlclient wheel RECORD"
        )
    recorded_hash = rows[0][1]
    recorded_size = rows[0][2]
    if not recorded_hash.startswith("sha256=") or not recorded_size.isdigit():
        raise DatabaseProbeError("mysqlclient wheel RECORD metadata is invalid")
    try:
        digest = hashlib.sha256(provider.read_bytes()).digest()
    except OSError as exc:
        raise DatabaseProbeError("bundled MariaDB library cannot be hashed") from exc
    encoded_digest = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    if (
        recorded_hash.removeprefix("sha256=") != encoded_digest
        or int(recorded_size) != provider.stat().st_size
    ):
        raise DatabaseProbeError("bundled MariaDB library does not match wheel RECORD")
    return digest.hex()


def _bundled_provider(loaded: Iterable[Path]) -> tuple[Path, str]:
    """Require one wheel-local Connector/C and reject a second provider."""

    resolved = {Path(path).resolve() for path in loaded}
    bundled = {
        path
        for path in resolved
        if path.parent.name == "mysqlclient.libs"
        and _BUNDLED_PROVIDER_RE.fullmatch(path.name)
    }
    if len(bundled) != 1:
        raise DatabaseProbeError(
            "production must load exactly one bundled mysqlclient MariaDB library"
        )
    mariadb = {path for path in resolved if "libmariadb" in path.name}
    if mariadb != bundled:
        raise DatabaseProbeError(
            "production has multiple MariaDB library providers loaded"
        )
    provider = next(iter(bundled))
    if not provider.is_file():
        raise DatabaseProbeError("bundled mysqlclient MariaDB library is missing")
    return provider, _verify_provider_record(provider)


def verify_connection(
    connection,
    *,
    environment: Mapping[str, str] | None = None,
    loaded_libraries: Iterable[Path] | None = None,
    iterations: int = 1,
) -> dict[str, object]:
    if not isinstance(iterations, int) or isinstance(iterations, bool) or not (
        1 <= iterations <= MAX_PROBE_ITERATIONS
    ):
        raise DatabaseProbeError(
            f"probe iterations must be between 1 and {MAX_PROBE_ITERATIONS}"
        )
    environment = environment if environment is not None else os.environ
    if str(environment.get("LD_PRELOAD") or "").strip():
        raise DatabaseProbeError(
            "LD_PRELOAD must be unset when using the bundled MariaDB library"
        )
    provided_loaded = (
        {Path(path).resolve() for path in loaded_libraries}
        if loaded_libraries is not None
        else None
    )
    provider = None
    provider_sha256 = ""

    engine = str(connection.settings_dict.get("ENGINE") or "")
    if engine != "django.db.backends.mysql":
        raise DatabaseProbeError("production database must use the Django MySQL backend")

    for _ in range(iterations):
        try:
            with connection.cursor() as cursor:
                cursor.execute(PROBE_SQL)
                row = cursor.fetchone()
                description = tuple(cursor.description or ())
        except Exception as exc:
            raise DatabaseProbeError(
                f"typed MariaDB query failed with {type(exc).__name__}"
            ) from exc

        # The MySQL backend imports its C extension lazily. Inspect the loader
        # only after the first successful cursor has forced that import.
        if provider is None:
            provider, provider_sha256 = _bundled_provider(
                provided_loaded if provided_loaded is not None else _loaded_library_paths()
            )

        if not isinstance(row, (tuple, list)) or len(row) != 5 or len(description) != 5:
            raise DatabaseProbeError("typed MariaDB query returned an invalid shape")
        try:
            field_types = [int(field[1]) for field in description]
        except (IndexError, TypeError, ValueError) as exc:
            raise DatabaseProbeError("MariaDB field metadata is unreadable") from exc
        if field_types != EXPECTED_FIELD_TYPES:
            raise DatabaseProbeError("MariaDB field metadata is corrupted")

        version, sql_mode, storage_engine, decimal_value, string_value = row
        if "mariadb" not in str(version).lower():
            raise DatabaseProbeError("production database did not report MariaDB")
        strict_modes = {item.strip().upper() for item in str(sql_mode).split(",")}
        if not strict_modes.intersection({"STRICT_TRANS_TABLES", "STRICT_ALL_TABLES"}):
            raise DatabaseProbeError("production MariaDB SQL mode is not strict")
        if str(storage_engine).strip().lower() != "innodb":
            raise DatabaseProbeError("production MariaDB storage engine is not InnoDB")
        if decimal_value != Decimal("123.45") or string_value != "probe":
            raise DatabaseProbeError("typed MariaDB values are corrupted")

    return {
        "engine": engine,
        "field_types": field_types,
        "iterations": iterations,
        "mariadb_provider": str(provider),
        "mariadb_provider_sha256": provider_sha256,
        "storage_engine": str(storage_engine),
        "sql_mode_strict": True,
        "version": str(version),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--settings",
        default="twocomms.production_settings",
    )
    parser.add_argument("--iterations", type=int, default=100)
    args = parser.parse_args(argv)

    project_root = Path(__file__).resolve().parents[1] / "twocomms"
    sys.path.insert(0, os.fspath(project_root))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", args.settings)

    try:
        import django

        django.setup()
        from django.db import connection

        result = verify_connection(
            connection,
            iterations=args.iterations,
        )
    except DatabaseProbeError as exc:
        print(f"production database probe failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
