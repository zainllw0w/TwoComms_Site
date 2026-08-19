#!/usr/bin/env python3
"""Run a programmatic, local-only MariaDB MyISAM -> InnoDB canary.

This module deliberately has no destructive CLI.  Callers must provide a
connection factory from an already-approved local disposable MariaDB runtime.
The canary never accepts a production endpoint, user database name, or Django
database alias.  It creates a random database, records a logical shadow-table
backup, times the engine conversion, verifies the converted data, restores the
pre-conversion table from the backup, and drops the disposable database.
"""

from __future__ import annotations

import hashlib
import ipaddress
import math
import re
import secrets
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SHA256_DIGEST = re.compile(r"^[0-9a-f]{64}$")
MAX_ROWS = 5_000
DISPOSABLE_INNODB_CANARY_INTERLOCK = "DJ6-INNODB-CANARY-MARIADB-LOCAL-ONLY-v1"
PREFLIGHT_SCOPE = "disposable_non-DTF_canary_only"
SAFE_ROLLBACK_STRATEGIES = {
    "maintenance_window",
    "dual_write",
    "replica_switchover",
    "reverse_sync",
}


def _quote_identifier(value: str) -> str:
    if not SAFE_IDENTIFIER.fullmatch(value):
        raise ValueError(f"unsafe SQL identifier: {value!r}")
    return f"`{value}`"


def _require_mapping(
    parent: Mapping[str, Any], field: str, *, message: str
) -> Mapping[str, Any]:
    value = parent.get(field)
    if not isinstance(value, Mapping):
        raise RuntimeError(message)
    return value


def _require_nonnegative_int(value: Any, *, message: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise RuntimeError(message)
    return value


def _require_positive_seconds(value: Any, *, message: str) -> float:
    if isinstance(value, bool):
        raise RuntimeError(message)
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(message) from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise RuntimeError(message)
    return parsed


def _require_sha256(value: Any, *, message: str) -> str:
    digest = str(value or "").strip().casefold()
    if not SHA256_DIGEST.fullmatch(digest):
        raise RuntimeError(message)
    return digest


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_pre_ddl_preflight(
    preflight: Mapping[str, Any] | None, *, expected_rows: int
) -> dict[str, Any]:
    """Validate offline evidence before a connection or DDL can be attempted."""

    if not isinstance(preflight, Mapping):
        raise RuntimeError("InnoDB canary preflight evidence missing")
    schema = preflight.get("schema")
    if (
        not isinstance(schema, int)
        or isinstance(schema, bool)
        or schema != 1
        or preflight.get("scope") != PREFLIGHT_SCOPE
    ):
        raise RuntimeError("InnoDB canary preflight scope is invalid")

    candidate = _require_mapping(
        preflight, "candidate", message="InnoDB canary row/index contract missing"
    )
    table = str(candidate.get("table") or "").strip()
    if (
        not SAFE_IDENTIFIER.fullmatch(table)
        or table.casefold() == "dtf"
        or table.casefold().startswith("dtf_")
    ):
        raise RuntimeError("InnoDB canary candidate must be a non-DTF table")
    if str(candidate.get("source_engine") or "").casefold() != "myisam":
        raise RuntimeError("InnoDB canary source engine contract requires MyISAM")
    if str(candidate.get("target_engine") or "").casefold() != "innodb":
        raise RuntimeError("InnoDB canary target engine contract requires InnoDB")
    candidate_rows = _require_nonnegative_int(
        candidate.get("exact_rows"), message="InnoDB canary row contract is invalid"
    )
    if candidate_rows != expected_rows:
        raise RuntimeError("InnoDB canary row contract does not match requested rows")
    if candidate.get("index_inventory_complete") is not True:
        raise RuntimeError("InnoDB canary index inventory is incomplete")
    index_count = _require_nonnegative_int(
        candidate.get("index_count"), message="InnoDB canary index contract is invalid"
    )
    if index_count < 1:
        raise RuntimeError("InnoDB canary index contract is invalid")
    index_sha256 = _require_sha256(
        candidate.get("index_sha256"),
        message="InnoDB canary index contract is invalid",
    )
    if candidate.get("fulltext_inventory_complete") is not True:
        raise RuntimeError("InnoDB canary FULLTEXT inventory is incomplete")
    fulltext_indexes = _require_nonnegative_int(
        candidate.get("fulltext_indexes"),
        message="InnoDB canary FULLTEXT inventory is invalid",
    )
    if fulltext_indexes:
        raise RuntimeError("InnoDB canary candidate has unsupported FULLTEXT indexes")

    writer_audit = _require_mapping(
        preflight, "writer_audit", message="InnoDB canary writer audit missing"
    )
    if writer_audit.get("complete") is not True:
        raise RuntimeError("InnoDB canary writer audit is incomplete")
    active_writers = _require_nonnegative_int(
        writer_audit.get("active_writers"),
        message="InnoDB canary active writers evidence is invalid",
    )
    if active_writers:
        raise RuntimeError("InnoDB canary active writers must be zero")

    orphan_scan = _require_mapping(
        preflight, "orphan_scan", message="InnoDB canary orphan scan missing"
    )
    if orphan_scan.get("complete") is not True:
        raise RuntimeError("InnoDB canary orphan scan is incomplete")
    orphan_count = _require_nonnegative_int(
        orphan_scan.get("orphan_count"),
        message="InnoDB canary orphan evidence is invalid",
    )
    if orphan_count:
        raise RuntimeError("InnoDB canary orphans must be zero")

    backup = _require_mapping(
        preflight, "backup", message="InnoDB canary backup evidence missing"
    )
    if backup.get("verified") is not True:
        raise RuntimeError("InnoDB canary backup verification is missing")
    artifact_path = Path(str(backup.get("artifact_path") or "")).expanduser()
    if (
        not artifact_path.is_absolute()
        or artifact_path.is_symlink()
        or not artifact_path.is_file()
    ):
        raise RuntimeError("InnoDB canary backup artifact is missing or unsafe")
    artifact_size = _require_nonnegative_int(
        backup.get("size_bytes"), message="InnoDB canary backup size is invalid"
    )
    if artifact_size < 1 or artifact_path.stat().st_size != artifact_size:
        raise RuntimeError("InnoDB canary backup size does not match artifact")
    backup_sha256 = _require_sha256(
        backup.get("sha256"), message="InnoDB canary backup SHA-256 is invalid"
    )
    if _file_sha256(artifact_path) != backup_sha256:
        raise RuntimeError("InnoDB canary backup SHA-256 does not match artifact")
    backup_rows = _require_nonnegative_int(
        backup.get("rows"), message="InnoDB canary backup row contract is invalid"
    )
    backup_index_sha256 = _require_sha256(
        backup.get("index_sha256"),
        message="InnoDB canary backup index contract is invalid",
    )
    if backup_rows != candidate_rows:
        raise RuntimeError("InnoDB canary backup row contract does not match candidate")
    if backup_index_sha256 != index_sha256:
        raise RuntimeError("InnoDB canary backup index contract does not match candidate")

    rehearsal = _require_mapping(
        preflight, "rehearsal", message="InnoDB canary rehearsal timing missing"
    )
    if rehearsal.get("measured") is not True:
        raise RuntimeError("InnoDB canary rehearsal timing is not measured")
    approved_max_seconds = _require_positive_seconds(
        rehearsal.get("approved_max_seconds"),
        message="InnoDB canary approved timing limit is invalid",
    )
    conversion_seconds = _require_positive_seconds(
        rehearsal.get("conversion_seconds"),
        message="InnoDB canary conversion rehearsal timing is invalid",
    )
    rollback_seconds = _require_positive_seconds(
        rehearsal.get("rollback_seconds"),
        message="InnoDB canary rollback rehearsal timing is invalid",
    )
    if (
        conversion_seconds > approved_max_seconds
        or rollback_seconds > approved_max_seconds
    ):
        raise RuntimeError("InnoDB canary rehearsal exceeds approved timing limit")

    rollback = _require_mapping(
        preflight, "rollback", message="InnoDB canary rollback rehearsal missing"
    )
    if rollback.get("rehearsed") is not True or rollback.get("verified") is not True:
        raise RuntimeError("InnoDB canary rollback rehearsal is not verified")
    if rollback.get("write_loss_safe") is not True:
        raise RuntimeError("InnoDB canary rollback is not write-loss-safe")
    strategy = str(rollback.get("strategy") or "").strip()
    if strategy not in SAFE_ROLLBACK_STRATEGIES:
        raise RuntimeError("InnoDB canary rollback strategy is unsafe")
    if strategy == "maintenance_window":
        if rollback.get("write_freeze_verified") is not True:
            raise RuntimeError("InnoDB canary rollback write freeze is unverified")
    elif rollback.get("reverse_sync_verified") is not True:
        raise RuntimeError("InnoDB canary rollback reverse sync is unverified")
    restored_rows = _require_nonnegative_int(
        rollback.get("restored_rows"),
        message="InnoDB canary rollback row contract is invalid",
    )
    if restored_rows != candidate_rows:
        raise RuntimeError("InnoDB canary rollback row contract does not match candidate")
    restored_index_sha256 = _require_sha256(
        rollback.get("restored_index_sha256"),
        message="InnoDB canary rollback index contract is invalid",
    )
    if restored_index_sha256 != index_sha256:
        raise RuntimeError("InnoDB canary rollback index contract does not match candidate")
    rollback_backup_sha256 = _require_sha256(
        rollback.get("backup_sha256"),
        message="InnoDB canary rollback backup contract is invalid",
    )
    if rollback_backup_sha256 != backup_sha256:
        raise RuntimeError("InnoDB canary rollback backup contract does not match artifact")

    return {
        "status": "verified",
        "candidate": table,
        "rows": candidate_rows,
        "index_count": index_count,
        "index_sha256": index_sha256,
        "fulltext_indexes": 0,
        "active_writers": 0,
        "orphans": 0,
        "backup": {"size_bytes": artifact_size, "sha256": backup_sha256},
        "rehearsal": {
            "conversion_seconds": conversion_seconds,
            "rollback_seconds": rollback_seconds,
            "approved_max_seconds": approved_max_seconds,
        },
        "rollback": {"strategy": strategy, "write_loss_safe": True},
    }


def validate_disposable_endpoint(
    *, host: str | None, unix_socket: str | None, database_alias: str | None
) -> None:
    """Fail closed unless the caller explicitly targets a named temp endpoint."""

    if str(database_alias or "").strip().casefold() != "default":
        raise ValueError("InnoDB canary requires the default disposable alias")
    normalized_host = (host or "").strip().lower()
    if unix_socket:
        if normalized_host and normalized_host not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("InnoDB canary requires local MariaDB")
        socket_path = Path(unix_socket).expanduser()
        if not socket_path.is_absolute():
            raise ValueError("InnoDB canary requires an absolute temporary socket")
        resolved_socket = socket_path.resolve(strict=False)
        temp_roots = {
            Path(tempfile.gettempdir()).resolve(),
            Path("/tmp").resolve(),
            Path("/private/tmp").resolve(),
        }
        if not any(
            resolved_socket == root or root in resolved_socket.parents
            for root in temp_roots
        ):
            raise ValueError("InnoDB canary requires a temporary socket")
        marker_parts = {"twc-dj61", "django61", "stage5", "disposable"}
        if not any(
            any(marker in part.casefold() for marker in marker_parts)
            for part in resolved_socket.parts
        ):
            raise ValueError("InnoDB canary requires a named temporary socket")
        return
    if not normalized_host:
        raise ValueError("InnoDB canary requires a socket or loopback host")
    if normalized_host == "localhost":
        return
    try:
        address = ipaddress.ip_address(normalized_host)
    except ValueError as exc:
        raise ValueError("InnoDB canary requires local MariaDB") from exc
    if not address.is_loopback:
        raise ValueError("InnoDB canary requires local MariaDB")


def validate_disposable_connection_contract(
    *,
    interlock: str | None,
    host: str | None,
    unix_socket: str | None,
    database_alias: str | None,
    connection_identity: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Validate the proof required before any destructive canary SQL."""

    if interlock != DISPOSABLE_INNODB_CANARY_INTERLOCK:
        raise RuntimeError("InnoDB canary interlock missing")
    validate_disposable_endpoint(
        host=host, unix_socket=unix_socket, database_alias=database_alias
    )
    if not isinstance(connection_identity, Mapping):
        raise RuntimeError("InnoDB canary connection identity missing")
    identity = dict(connection_identity)
    if str(identity.get("environment") or "").casefold() != "disposable":
        raise RuntimeError("InnoDB canary identity is not disposable")
    if str(identity.get("database_role") or "").casefold() != "temporary":
        raise RuntimeError("InnoDB canary identity is not temporary")
    if str(identity.get("server_vendor") or "").casefold() not in {
        "mariadb",
        "mysql",
    }:
        raise RuntimeError("InnoDB canary identity requires MariaDB")
    if not str(identity.get("server_hostname") or "").strip():
        raise RuntimeError("InnoDB canary server identity missing")
    try:
        server_port = int(identity.get("server_port", 0))
    except (TypeError, ValueError) as exc:
        raise RuntimeError("InnoDB canary server port missing") from exc
    if server_port <= 0:
        raise RuntimeError("InnoDB canary server port missing")
    if not unix_socket and server_port == 3306:
        raise RuntimeError("InnoDB canary requires a dedicated disposable port")
    database_user = str(identity.get("db_user") or "").strip()
    if not database_user.startswith("twc_dj61_disposable_"):
        raise RuntimeError("InnoDB canary requires a disposable database user")
    return identity


def verify_disposable_connection_identity(
    connection: Any, expected: Mapping[str, Any]
) -> None:
    """Verify the opened MariaDB identity before CREATE/DROP is permitted."""

    with connection.cursor() as cursor:
        _execute(
            cursor,
            "SELECT VERSION(), @@hostname, @@port, CURRENT_USER(), DATABASE()",
        )
        row = cursor.fetchone()
    if not row or len(row) < 5:
        raise RuntimeError("InnoDB canary connection identity unavailable")
    version, hostname, port, current_user = (str(value or "") for value in row[:4])
    selected_database = row[4]
    if selected_database not in (None, ""):
        raise RuntimeError("InnoDB canary admin connection selects a database")
    if "mariadb" not in version.casefold():
        raise RuntimeError("InnoDB canary requires MariaDB connection")
    if hostname.strip() != str(expected["server_hostname"]).strip():
        raise RuntimeError("InnoDB canary server hostname mismatch")
    try:
        actual_port = int(port)
        expected_port = int(expected["server_port"])
    except (TypeError, ValueError) as exc:
        raise RuntimeError("InnoDB canary server port invalid") from exc
    if actual_port != expected_port:
        raise RuntimeError("InnoDB canary server port mismatch")
    expected_user = str(expected["db_user"]).strip()
    if current_user.split("@", 1)[0] != expected_user:
        raise RuntimeError("InnoDB canary database user mismatch")


def _execute(cursor: Any, sql: str, params: Sequence[Any] = ()) -> None:
    cursor.execute(sql, params)


def _fetchone(cursor: Any, sql: str, params: Sequence[Any] = ()) -> Any:
    _execute(cursor, sql, params)
    return cursor.fetchone()


def _table_engine(cursor: Any, database: str, table: str) -> str | None:
    row = _fetchone(
        cursor,
        "SELECT ENGINE FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
        (database, table),
    )
    return str(row[0]) if row else None


def _table_count(cursor: Any, table: str) -> int:
    row = _fetchone(cursor, f"SELECT COUNT(*) FROM {_quote_identifier(table)}")
    return int(row[0]) if row else 0


def _table_digest(cursor: Any, table: str) -> str:
    _execute(cursor, f"SELECT id, payload FROM {_quote_identifier(table)} ORDER BY id")
    digest = hashlib.sha256()
    for row in cursor.fetchall():
        digest.update(f"{row[0]}\0{row[1]}\n".encode("utf-8"))
    return digest.hexdigest()


def _require_mariadb_and_innodb(connection: Any) -> str:
    if getattr(connection, "vendor", "mysql") != "mysql":
        raise RuntimeError("InnoDB canary requires MariaDB/MySQL DB-API connection")
    with connection.cursor() as cursor:
        version_row = _fetchone(cursor, "SELECT VERSION()")
        version = str(version_row[0]) if version_row else ""
        if "mariadb" not in version.casefold():
            raise RuntimeError(f"InnoDB canary requires MariaDB, got {version}")
        _execute(cursor, "SHOW ENGINES")
        engines = cursor.fetchall()
    innodb = next(
        (row for row in engines if str(row[0]).casefold() == "innodb"), None
    )
    if innodb is None or str(innodb[1]).casefold() in {"no", "disabled"}:
        raise RuntimeError("MariaDB InnoDB engine is unavailable")
    return version


def run_disposable_innodb_canary(
    connection_factory: Callable[[str | None], Any],
    *,
    host: str | None = "127.0.0.1",
    unix_socket: str | None = None,
    database_alias: str = "default",
    rows: int = 250,
    allow_disposable: bool = False,
    disposable_interlock: str | None = None,
    connection_identity: Mapping[str, Any] | None = None,
    preflight: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute and verify the disposable conversion/backup/rollback rehearsal.

    ``allow_disposable`` and ``disposable_interlock`` are explicit safety
    interlocks.  A false value, incomplete pre-DDL evidence, an incomplete
    endpoint/identity proof, a non-MariaDB connection, or missing InnoDB
    support fails before any connection is opened or database is created.
    """

    if not allow_disposable:
        raise ValueError("InnoDB canary requires allow_disposable=True")
    if (
        not isinstance(rows, int)
        or isinstance(rows, bool)
        or rows < 1
        or rows > MAX_ROWS
    ):
        raise ValueError(f"rows must be between 1 and {MAX_ROWS}")
    identity = validate_disposable_connection_contract(
        interlock=disposable_interlock,
        host=host,
        unix_socket=unix_socket,
        database_alias=database_alias,
        connection_identity=connection_identity,
    )
    preflight_report = validate_pre_ddl_preflight(preflight, expected_rows=rows)

    admin = connection_factory(None)
    try:
        verify_disposable_connection_identity(admin, identity)
    except Exception:
        try:
            admin.close()
        except Exception:
            pass
        raise
    database = f"twc_dj61_innodb_canary_{secrets.token_hex(6)}"
    source_table = "stage5_canary_source"
    backup_table = "stage5_canary_backup"
    connection = None
    cleanup_error: Exception | None = None
    try:
        version = _require_mariadb_and_innodb(admin)
        with admin.cursor() as cursor:
            _execute(
                cursor,
                f"CREATE DATABASE {_quote_identifier(database)} "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
            )
            admin.commit()

        connection = connection_factory(database)
        if getattr(connection, "vendor", "mysql") != "mysql":
            raise RuntimeError("disposable connection is not MariaDB/MySQL")
        with connection.cursor() as cursor:
            _execute(cursor, f"USE {_quote_identifier(database)}")
            _execute(
                cursor,
                f"CREATE TABLE {_quote_identifier(source_table)} ("
                "id INT PRIMARY KEY, payload VARCHAR(64) NOT NULL) ENGINE=MyISAM",
            )
            values = [(index, f"payload-{index:05d}") for index in range(1, rows + 1)]
            cursor.executemany(
                f"INSERT INTO {_quote_identifier(source_table)} (id, payload) "
                "VALUES (%s, %s)",
                values,
            )
            connection.commit()
            source_before = {
                "engine": _table_engine(cursor, database, source_table),
                "rows": _table_count(cursor, source_table),
                "sha256": _table_digest(cursor, source_table),
            }
            if source_before["engine"] != "MyISAM":
                raise RuntimeError("canary source table was not created as MyISAM")
            backup_started = time.perf_counter()
            _execute(
                cursor,
                f"CREATE TABLE {_quote_identifier(backup_table)} "
                f"LIKE {_quote_identifier(source_table)}",
            )
            _execute(
                cursor,
                f"INSERT INTO {_quote_identifier(backup_table)} "
                f"SELECT * FROM {_quote_identifier(source_table)}",
            )
            connection.commit()
            backup = {
                "method": "logical_shadow_table",
                "table": backup_table,
                "engine": _table_engine(cursor, database, backup_table),
                "rows": _table_count(cursor, backup_table),
                "sha256": _table_digest(cursor, backup_table),
            }
            backup["seconds"] = round(time.perf_counter() - backup_started, 6)
            backup["verified"] = (
                backup["engine"] == source_before["engine"]
                and backup["rows"] == source_before["rows"]
                and backup["sha256"] == source_before["sha256"]
            )
            if not backup["verified"]:
                raise RuntimeError("logical shadow backup verification failed")

            conversion_started = time.perf_counter()
            _execute(
                cursor,
                f"ALTER TABLE {_quote_identifier(source_table)} ENGINE=InnoDB",
            )
            connection.commit()
            conversion_seconds = round(time.perf_counter() - conversion_started, 6)
            converted = {
                "engine": _table_engine(cursor, database, source_table),
                "rows": _table_count(cursor, source_table),
                "sha256": _table_digest(cursor, source_table),
            }
            if converted["engine"] != "InnoDB":
                raise RuntimeError("engine conversion did not produce InnoDB")
            if converted["rows"] != source_before["rows"] or converted["sha256"] != source_before["sha256"]:
                raise RuntimeError("engine conversion changed canary data")

            rollback_started = time.perf_counter()
            _execute(cursor, f"DROP TABLE {_quote_identifier(source_table)}")
            _execute(
                cursor,
                f"RENAME TABLE {_quote_identifier(backup_table)} "
                f"TO {_quote_identifier(source_table)}",
            )
            connection.commit()
            rollback_seconds = round(time.perf_counter() - rollback_started, 6)
            restored = {
                "engine": _table_engine(cursor, database, source_table),
                "rows": _table_count(cursor, source_table),
                "sha256": _table_digest(cursor, source_table),
            }
            rollback_verified = restored == source_before
            if not rollback_verified:
                raise RuntimeError("backup rollback verification failed")

        return {
            "schema": 1,
            "status": "passed",
            "preflight": preflight_report,
            "version": version,
            "database": database,
            "rows": rows,
            "source_before": source_before,
            "backup": backup,
            "conversion": {"to_engine": converted["engine"], "seconds": conversion_seconds},
            "rollback": {"restored": restored, "seconds": rollback_seconds, "verified": True},
            "cleanup_verified": True,
            "scope": "disposable_non-DTF_canary_only",
        }
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception as exc:  # pragma: no cover - defensive cleanup
                cleanup_error = exc
        try:
            with admin.cursor() as cursor:
                _execute(cursor, f"DROP DATABASE IF EXISTS {_quote_identifier(database)}")
                admin.commit()
                remaining = _fetchone(
                    cursor,
                    "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA "
                    "WHERE SCHEMA_NAME=%s",
                    (database,),
                )
                if remaining is not None:
                    raise RuntimeError("generated disposable database still exists")
        except Exception as exc:
            cleanup_error = cleanup_error or exc
        try:
            admin.close()
        except Exception as exc:  # pragma: no cover - defensive cleanup
            cleanup_error = cleanup_error or exc
        if cleanup_error is not None:
            raise RuntimeError("disposable InnoDB canary cleanup failed") from cleanup_error
