#!/usr/bin/env python3
"""Exercise the produced mysqlclient wheel against a real MariaDB service."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Callable, Iterable, Mapping


EXPECTED_FIELD_TYPES = [253, 253, 253, 246, 253]
EXPECTED_SIGNED_FIELD_TYPE = 3
EXPECTED_UNICODE_VALUE = bytes.fromhex(
    "556e69636f64653a20d09fd180d0b8d0b2d196d18220ed959ceab5adec96b4"
).decode("utf-8")
EXPECTED_DECIMAL_VALUE = Decimal("1234567890.123456")
MAX_PROBE_ITERATIONS = 1000
PROBE_SQL = """
SELECT VERSION(),
    @@sql_mode,
    @@default_storage_engine,
    CAST(1234567890.123456 AS DECIMAL(20, 6)) AS decimal_probe,
    CONVERT(0x556e69636f64653a20d09fd180d0b8d0b2d196d18220ed959ceab5adec96b4 USING utf8mb4) AS string_probe
"""
SIGNED_PROBE_SQL = "SELECT CAST(-42 AS SIGNED) AS signed_probe"
_BUNDLED_NAME_RE = re.compile(r"^mysqlclient\.libs/libmariadb-[0-9a-f]+\.so\.3$")


class WheelRuntimeError(RuntimeError):
    """The produced mysqlclient wheel cannot safely talk to MariaDB."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_clean_loader_environment(environment: Mapping[str, str] | None = None) -> None:
    environment = environment if environment is not None else os.environ
    if str(environment.get("LD_PRELOAD") or "").strip():
        raise WheelRuntimeError("LD_PRELOAD must be unset for the bundled connector gate")


def _loaded_library_paths() -> set[Path]:
    maps = Path("/proc/self/maps")
    if not maps.is_file():
        raise WheelRuntimeError("process maps are unavailable")
    loaded: set[Path] = set()
    try:
        lines = maps.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        raise WheelRuntimeError("process maps cannot be read") from exc
    for line in lines:
        path = line.rsplit(maxsplit=1)[-1]
        if path.startswith("/"):
            loaded.add(Path(path.removesuffix(" (deleted)")).resolve())
    return loaded


def _read_elf_soname(path: Path) -> str:
    try:
        result = subprocess.run(
            ["readelf", "-d", os.fspath(path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise WheelRuntimeError(f"cannot inspect bundled library SONAME: {path}") from exc
    for line in result.stdout.splitlines():
        if "(SONAME)" in line:
            match = re.search(r"\[([^]]+)\]", line)
            if match:
                return match.group(1)
    raise WheelRuntimeError(f"bundled library has no SONAME: {path}")


def verify_loaded_library(
    evidence: Mapping[str, object],
    *,
    loaded_libraries: Iterable[Path] | None = None,
    soname_reader: Callable[[Path], str] | None = None,
) -> dict[str, str]:
    name = str(evidence.get("mysqlclient_bundled_library_name") or "")
    expected_hash = str(evidence.get("mysqlclient_bundled_library_sha256") or "")
    expected_soname = str(evidence.get("mysqlclient_bundled_library_soname") or "")
    if not _BUNDLED_NAME_RE.fullmatch(name):
        raise WheelRuntimeError("builder evidence has an invalid bundled library name")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        raise WheelRuntimeError("builder evidence has an invalid bundled library hash")
    if not re.fullmatch(r"libmariadb-[0-9a-f]+\.so\.3", expected_soname):
        raise WheelRuntimeError("builder evidence has an invalid bundled library SONAME")
    expected_path = Path(name)
    loaded = {
        Path(path).resolve()
        for path in (loaded_libraries if loaded_libraries is not None else _loaded_library_paths())
    }
    candidates = {
        path
        for path in loaded
        if path.name == expected_path.name and path.parent.name == expected_path.parent.name
    }
    if len(candidates) != 1:
        raise WheelRuntimeError("bundled MariaDB library is not uniquely loaded")
    library = next(iter(candidates))
    if not library.is_file() or sha256(library) != expected_hash:
        raise WheelRuntimeError("loaded bundled MariaDB library hash mismatch")
    reader = soname_reader or _read_elf_soname
    actual_soname = reader(library)
    if actual_soname != expected_soname:
        raise WheelRuntimeError("loaded bundled MariaDB library SONAME mismatch")
    return {
        "library_path": os.fspath(library),
        "library_sha256": expected_hash,
        "library_soname": actual_soname,
    }


def _field_types(description: Iterable[object]) -> list[int]:
    try:
        return [int(field[1]) for field in description]  # type: ignore[index]
    except (IndexError, TypeError, ValueError) as exc:
        raise WheelRuntimeError("MariaDB field metadata is unreadable") from exc


def verify_typed_connection(
    connection,
    *,
    expected_server_version: str,
    iterations: int = 100,
) -> dict[str, object]:
    if not isinstance(iterations, int) or isinstance(iterations, bool) or not (
        1 <= iterations <= MAX_PROBE_ITERATIONS
    ):
        raise WheelRuntimeError(
            f"probe iterations must be between 1 and {MAX_PROBE_ITERATIONS}"
        )
    if not expected_server_version.strip():
        raise WheelRuntimeError("expected MariaDB server version is required")
    field_types: list[int] = []
    version = ""
    for _ in range(iterations):
        try:
            with connection.cursor() as cursor:
                cursor.execute(PROBE_SQL)
                row = cursor.fetchone()
                description = tuple(cursor.description or ())
        except Exception as exc:
            raise WheelRuntimeError(
                f"typed MariaDB query failed with {type(exc).__name__}"
            ) from exc
        if not isinstance(row, (tuple, list)) or len(row) != 5 or len(description) != 5:
            raise WheelRuntimeError("typed MariaDB query returned an invalid shape")
        field_types = _field_types(description)
        if field_types != EXPECTED_FIELD_TYPES:
            raise WheelRuntimeError("MariaDB field metadata is corrupted")
        version, sql_mode, storage_engine, decimal_value, string_value = row
        version = str(version)
        if not version.startswith(expected_server_version):
            raise WheelRuntimeError("MariaDB server version does not match the gate")
        strict_modes = {item.strip().upper() for item in str(sql_mode).split(",")}
        if not strict_modes.intersection({"STRICT_TRANS_TABLES", "STRICT_ALL_TABLES"}):
            raise WheelRuntimeError("MariaDB SQL mode is not strict")
        if (
            str(storage_engine).upper() not in {"INNODB", "XTRADB"}
            or decimal_value != EXPECTED_DECIMAL_VALUE
            or string_value != EXPECTED_UNICODE_VALUE
        ):
            raise WheelRuntimeError("typed MariaDB values are corrupted")
        try:
            with connection.cursor() as cursor:
                cursor.execute(SIGNED_PROBE_SQL)
                signed_row = cursor.fetchone()
                signed_description = tuple(cursor.description or ())
        except Exception as exc:
            raise WheelRuntimeError(
                f"signed MariaDB query failed with {type(exc).__name__}"
            ) from exc
        if (
            not isinstance(signed_row, (tuple, list))
            or len(signed_row) != 1
            or len(signed_description) != 1
            or _field_types(signed_description) != [EXPECTED_SIGNED_FIELD_TYPE]
            or signed_row[0] != -42
        ):
            raise WheelRuntimeError("signed MariaDB value metadata is corrupted")
    return {
        "field_types": field_types,
        "signed_field_type": EXPECTED_SIGNED_FIELD_TYPE,
        "iterations": iterations,
        "sql_mode_strict": True,
        "version": version,
    }


def _load_evidence(path: Path) -> dict[str, object]:
    try:
        evidence = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise WheelRuntimeError("builder evidence cannot be read") from exc
    if not isinstance(evidence, dict):
        raise WheelRuntimeError("builder evidence must be an object")
    return evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--expected-server-version", required=True)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--host", default=os.environ.get("MYSQLCLIENT_GATE_HOST", "mariadb"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("MYSQLCLIENT_GATE_PORT", "3306")))
    parser.add_argument("--user", default=os.environ.get("MYSQLCLIENT_GATE_USER", "wheelhouse"))
    parser.add_argument("--password", default=os.environ.get("MYSQLCLIENT_GATE_PASSWORD", "wheelhouse"))
    parser.add_argument("--database", default=os.environ.get("MYSQLCLIENT_GATE_DATABASE", "wheelhouse"))
    args = parser.parse_args(argv)
    try:
        require_clean_loader_environment()
        evidence = _load_evidence(args.evidence)
        import MySQLdb

        connection = MySQLdb.connect(
            host=args.host,
            port=args.port,
            user=args.user,
            passwd=args.password,
            db=args.database,
            charset="utf8mb4",
            use_unicode=True,
        )
        try:
            typed = verify_typed_connection(
                connection,
                expected_server_version=args.expected_server_version,
                iterations=args.iterations,
            )
            loaded = verify_loaded_library(evidence)
        finally:
            connection.close()
        print(
            json.dumps(
                {**loaded, **typed},
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0
    except ImportError as exc:
        print(f"mysqlclient wheel runtime gate cannot import MySQLdb: {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError, WheelRuntimeError) as exc:
        print(f"mysqlclient wheel runtime gate failed: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(
            f"mysqlclient wheel runtime gate failed with {type(exc).__name__}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
