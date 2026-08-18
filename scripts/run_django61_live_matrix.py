#!/usr/bin/env python3
"""Run sanitized production preflight and post-deploy checks."""

from __future__ import annotations

import argparse
import io
import json
import os
import platform
import re
import subprocess
import sys
from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = REPO_ROOT / "twocomms"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import verify_project_runtime


USER_AGENT = "TwoCommsReleaseBot/1.0"
HTTP_TIMEOUT_SECONDS = 15
HTTP_WORKERS = 4
HEALTH_BODY_LIMIT = 16 * 1024
ALLOWED_HTTP_HOSTS = frozenset(
    {
        "twocomms.shop",
        "management.twocomms.shop",
        "fin.twocomms.shop",
        "storage.twocomms.shop",
    }
)
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
EXPECTED_MAX_CONNECTIONS = 150
EXPECTED_MAX_USER_CONNECTIONS = 20
CONNECTION_GATE_SQL = """
SELECT @@character_set_database,
    @@collation_database,
    @@character_set_connection,
    @@character_set_client,
    @@character_set_results,
    @@collation_connection,
    @@default_storage_engine,
    @@max_connections,
    @@max_user_connections
"""


class MatrixFailure(RuntimeError):
    """A release check failed with a stable, non-sensitive code."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class HttpProbe:
    name: str
    url: str
    expected_status: int
    json_status: str | None = None
    location_path: str | None = None


HTTP_PROBES = (
    HttpProbe(
        "storefront-health",
        "https://twocomms.shop/healthz/",
        200,
        json_status="ok",
    ),
    HttpProbe("storefront-home", "https://twocomms.shop/", 200),
    HttpProbe("storefront-catalog", "https://twocomms.shop/catalog/", 200),
    HttpProbe("storefront-cart", "https://twocomms.shop/cart/", 200),
    HttpProbe(
        "management-login",
        "https://management.twocomms.shop/login/",
        200,
    ),
    HttpProbe(
        "management-bot-health",
        "https://management.twocomms.shop/bot/health/",
        200,
        json_status="ok",
    ),
    HttpProbe("finance-login", "https://fin.twocomms.shop/login/", 200),
    HttpProbe(
        "finance-health",
        "https://fin.twocomms.shop/health/",
        302,
        location_path="/login/",
    ),
    HttpProbe("storage-login", "https://storage.twocomms.shop/login/", 200),
    HttpProbe(
        "storage-home",
        "https://storage.twocomms.shop/",
        302,
        location_path="/login/",
    ),
)


class NoRedirectHandler(HTTPRedirectHandler):
    """Return redirect responses to the caller instead of following them."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _command_output(command: Iterable[str]) -> str:
    try:
        completed = subprocess.run(
            tuple(command),
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MatrixFailure("command_failed") from exc
    if completed.returncode:
        raise MatrixFailure("command_failed")
    return completed.stdout.strip()


def git_snapshot(
    *,
    phase: str,
    expected_sha: str | None = None,
    command_output: Callable[[Iterable[str]], str] = _command_output,
) -> dict[str, object]:
    sha = command_output(("git", "rev-parse", "HEAD")).strip()
    branch = command_output(("git", "branch", "--show-current")).strip()
    tracked_status = command_output(
        ("git", "status", "--porcelain=v1", "--untracked-files=no")
    ).strip()

    if not SHA_PATTERN.fullmatch(sha):
        raise MatrixFailure("git_sha_invalid")
    if branch != "main":
        raise MatrixFailure("git_branch_invalid")
    if tracked_status:
        raise MatrixFailure("git_tracked_tree_dirty")

    snapshot: dict[str, object] = {
        "sha": sha,
        "branch": branch,
        "tracked_clean": True,
    }
    if phase == "post-deploy":
        if expected_sha is None or not SHA_PATTERN.fullmatch(expected_sha):
            raise MatrixFailure("git_expected_sha_invalid")
        origin_main = command_output(
            ("git", "rev-parse", "refs/remotes/origin/main")
        ).strip()
        if sha != expected_sha or origin_main != expected_sha:
            raise MatrixFailure("git_revision_mismatch")
        snapshot["origin_main"] = origin_main
    elif phase != "preflight":
        raise MatrixFailure("phase_invalid")
    return snapshot


def runtime_snapshot(*, verifier=verify_project_runtime) -> dict[str, str]:
    if platform.python_implementation() != "CPython":
        raise MatrixFailure("runtime_mismatch")
    try:
        versions = verifier.current_versions()
        exact = verifier.validate_runtime(versions)
    except Exception as exc:
        raise MatrixFailure("runtime_mismatch") from exc
    return {"implementation": "CPython", **exact}


def ensure_only_default_alias(opened_aliases: Iterable[str]) -> list[str]:
    aliases = sorted({str(alias) for alias in opened_aliases})
    if any(alias != "default" for alias in aliases):
        raise MatrixFailure("database_alias_violation")
    return aliases


def default_database_snapshot(*, connections_registry=None) -> dict[str, str]:
    if connections_registry is None:
        from django.db import connections as connections_registry

    connection = connections_registry["default"]
    if connection.vendor != "mysql":
        raise MatrixFailure("database_backend_invalid")
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            row = cursor.fetchone()
    except Exception as exc:
        raise MatrixFailure("database_unavailable") from exc
    raw_version = str(row[0]) if row else ""
    match = re.search(r"(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)", raw_version)
    if "mariadb" not in raw_version.casefold() or match is None:
        raise MatrixFailure("database_server_invalid")
    version_tuple = tuple(int(match.group(name)) for name in ("major", "minor", "patch"))
    if version_tuple < (10, 11, 0):
        raise MatrixFailure("database_version_unsupported")
    return {
        "alias": "default",
        "server": "MariaDB",
        "version": ".".join(str(part) for part in version_tuple),
    }


def connection_gate_snapshot(
    connection,
    *,
    expected_max_connections: int = EXPECTED_MAX_CONNECTIONS,
    expected_max_user_connections: int = EXPECTED_MAX_USER_CONNECTIONS,
) -> dict[str, object]:
    """Validate the read-only MariaDB connection policy used by production.

    The probe deliberately performs one ``SELECT`` only. It does not issue
    DDL, migration commands, writes, or global/session ``SET`` statements.
    """

    settings = getattr(connection, "settings_dict", None)
    if not isinstance(settings, Mapping):
        raise MatrixFailure("database_connection_config_invalid")
    if settings.get("ENGINE") != "django.db.backends.mysql":
        raise MatrixFailure("database_backend_invalid")

    conn_max_age = settings.get("CONN_MAX_AGE")
    if isinstance(conn_max_age, bool) or conn_max_age != 0:
        raise MatrixFailure("database_conn_max_age_invalid")
    if settings.get("CONN_HEALTH_CHECKS") is not True:
        raise MatrixFailure("database_health_checks_invalid")

    options = settings.get("OPTIONS")
    if not isinstance(options, Mapping):
        raise MatrixFailure("database_charset_config_invalid")
    if str(options.get("charset", "")).casefold() != "utf8mb4":
        raise MatrixFailure("database_charset_config_invalid")
    init_command = str(options.get("init_command", ""))
    if not re.search(
        r"\bdefault_storage_engine\s*=\s*['\"]?innodb\b",
        init_command,
        flags=re.IGNORECASE,
    ):
        raise MatrixFailure("database_storage_engine_config_invalid")

    try:
        with connection.cursor() as cursor:
            cursor.execute(CONNECTION_GATE_SQL)
            row = cursor.fetchone()
    except Exception as exc:
        raise MatrixFailure("database_connection_gate_failed") from exc

    if not isinstance(row, (tuple, list)) or len(row) != 9:
        raise MatrixFailure("database_connection_gate_invalid")
    (
        schema_charset,
        schema_collation,
        session_charset,
        client_charset,
        results_charset,
        session_collation,
        storage_engine,
        max_connections,
        max_user_connections,
    ) = row
    charset_values = (
        schema_charset,
        session_charset,
        client_charset,
        results_charset,
    )
    if any(str(value).casefold() != "utf8mb4" for value in charset_values):
        raise MatrixFailure("database_charset_invalid")
    if any(
        not str(value).casefold().startswith("utf8mb4_")
        for value in (schema_collation, session_collation)
    ):
        raise MatrixFailure("database_charset_invalid")
    if str(storage_engine).casefold() != "innodb":
        raise MatrixFailure("database_storage_engine_invalid")

    try:
        max_user_connections = int(max_user_connections)
        max_connections = int(max_connections)
    except (TypeError, ValueError) as exc:
        raise MatrixFailure("database_connection_budget_invalid") from exc
    if (
        not isinstance(expected_max_connections, int)
        or isinstance(expected_max_connections, bool)
        or expected_max_connections <= 0
        or max_connections != expected_max_connections
        or not isinstance(expected_max_user_connections, int)
        or isinstance(expected_max_user_connections, bool)
        or expected_max_user_connections <= 0
        or max_user_connections != expected_max_user_connections
    ):
        raise MatrixFailure("database_connection_budget_invalid")
    if max_user_connections > max_connections:
        raise MatrixFailure("database_connection_budget_invalid")
    return {
        "conn_max_age": 0,
        "conn_health_checks": True,
        "charset": "utf8mb4",
        "schema_charset": "utf8mb4",
        "schema_collation": str(schema_collation),
        "session_charset": "utf8mb4",
        "client_charset": "utf8mb4",
        "results_charset": "utf8mb4",
        "session_collation": str(session_collation),
        "storage_engine": "InnoDB",
        "max_connections": max_connections,
        "max_user_connections": max_user_connections,
        "status": "ok",
    }


def django_database_check(*, call_command_func=None) -> dict[str, str]:
    if call_command_func is None:
        from django.core.management import call_command as call_command_func

    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        call_command_func(
            "check",
            databases=["default"],
            fail_level="ERROR",
            verbosity=0,
            stdout=stdout,
            stderr=stderr,
        )
    except Exception as exc:
        raise MatrixFailure("django_database_check_failed") from exc
    return {"alias": "default", "status": "ok"}


def pending_non_dtf_migrations(connection, *, executor_factory=None) -> list[str]:
    if executor_factory is None:
        from django.db.migrations.executor import MigrationExecutor

        executor_factory = MigrationExecutor
    try:
        executor = executor_factory(connection)
        targets = [
            node
            for node in executor.loader.graph.leaf_nodes()
            if str(node[0]).casefold() != "dtf"
        ]
        plan = executor.migration_plan(targets)
    except Exception as exc:
        raise MatrixFailure("migration_plan_failed") from exc
    return sorted(
        {
            f"{migration.app_label}.{migration.name}"
            for migration, _backwards in plan
            if str(migration.app_label).casefold() != "dtf"
        }
    )


def migration_snapshot(connection, *, executor_factory=None) -> dict[str, object]:
    pending = pending_non_dtf_migrations(
        connection, executor_factory=executor_factory
    )
    if pending:
        raise MatrixFailure("pending_non_dtf_migrations")
    return {"pending": 0, "scope": "non-dtf", "status": "ok"}


def passenger_snapshot(
    *, command_output: Callable[[Iterable[str]], str] = _command_output
) -> dict[str, object]:
    output = command_output(("ps", "-u", str(os.getuid()), "-o", "comm="))
    process_count = sum(
        1 for line in output.splitlines() if Path(line.strip()).name == "lswsgi"
    )
    if process_count < 1:
        raise MatrixFailure("passenger_process_missing")
    return {"lswsgi_processes": process_count, "status": "ok"}


def validate_http_probes(probes: Iterable[HttpProbe]) -> None:
    for probe in probes:
        parsed = urlsplit(probe.url)
        hostname = (parsed.hostname or "").casefold()
        if (
            "dtf" in hostname
            or hostname not in ALLOWED_HTTP_HOSTS
            or parsed.scheme != "https"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
        ):
            raise MatrixFailure("http_host_forbidden")


def _open_http(request: Request, timeout: int):
    opener = build_opener(NoRedirectHandler())
    try:
        return opener.open(request, timeout=timeout)
    except HTTPError as response:
        return response


def probe_http_route(
    probe: HttpProbe,
    *,
    open_http: Callable[[Request, int], Any] = _open_http,
) -> dict[str, object]:
    validate_http_probes((probe,))
    request = Request(probe.url, headers={"User-Agent": USER_AGENT}, method="GET")
    try:
        response_context = open_http(request, HTTP_TIMEOUT_SECONDS)
        with response_context as response:
            status_code = int(getattr(response, "status", getattr(response, "code", 0)))
            if status_code != probe.expected_status:
                raise MatrixFailure("http_status_invalid")
            if probe.location_path is not None:
                location = response.headers.get("Location", "")
                parsed_location = urlsplit(location)
                source_host = (urlsplit(probe.url).hostname or "").casefold()
                target_host = (parsed_location.hostname or source_host).casefold()
                if (
                    parsed_location.path != probe.location_path
                    or target_host != source_host
                    or parsed_location.scheme not in ("", "https")
                    or parsed_location.port not in (None, 443)
                ):
                    raise MatrixFailure("http_redirect_invalid")
            if probe.json_status is not None:
                raw_body = response.read(HEALTH_BODY_LIMIT + 1)
                if len(raw_body) > HEALTH_BODY_LIMIT:
                    raise MatrixFailure("http_health_invalid")
                try:
                    health = json.loads(raw_body.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise MatrixFailure("http_health_invalid") from exc
                if not isinstance(health, dict) or health.get("status") != probe.json_status:
                    raise MatrixFailure("http_health_invalid")
    except MatrixFailure:
        raise
    except Exception as exc:
        raise MatrixFailure("http_request_failed") from exc
    return {"name": probe.name, "status": "ok", "status_code": status_code}


def probe_non_dtf_routes(
    *,
    probes: tuple[HttpProbe, ...] = HTTP_PROBES,
    worker: Callable[[HttpProbe], dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    validate_http_probes(probes)
    probe_worker = worker or probe_http_route
    with ThreadPoolExecutor(max_workers=HTTP_WORKERS) as executor:
        futures = [executor.submit(probe_worker, probe) for probe in probes]
        return [future.result() for future in futures]


@contextmanager
def django_default_alias_guard():
    if str(APP_ROOT) not in sys.path:
        sys.path.insert(0, str(APP_ROOT))

    from django.db.backends.signals import connection_created

    opened_aliases: set[str] = set()

    def track_alias(*, connection, **_kwargs):
        opened_aliases.add(str(connection.alias))

    dispatch_uid = "twocomms-django61-live-matrix-alias-guard"
    connection_created.connect(track_alias, dispatch_uid=dispatch_uid, weak=False)
    try:
        from manage import _ensure_env_file

        _ensure_env_file()
        if "DJANGO_SETTINGS_MODULE" not in os.environ:
            env_file = Path(os.environ.get("DJANGO_ENV_FILE", "")).name
            is_production = (
                env_file == ".env.production"
                or os.environ.get("DJANGO_ENV", "").casefold() == "production"
            )
            os.environ["DJANGO_SETTINGS_MODULE"] = (
                "twocomms.production_settings" if is_production else "twocomms.settings"
            )

        import django

        django.setup()
        from django.conf import settings

        if settings.SETTINGS_MODULE != "twocomms.production_settings":
            raise MatrixFailure("django_settings_invalid")
        ensure_only_default_alias(opened_aliases)
        yield opened_aliases
    finally:
        connection_created.disconnect(dispatch_uid=dispatch_uid)


def run_server_matrix(*, phase: str, expected_sha: str | None = None) -> dict[str, object]:
    git = git_snapshot(phase=phase, expected_sha=expected_sha)
    runtime = runtime_snapshot()
    with django_default_alias_guard() as opened_aliases:
        from django.db import connections

        database = default_database_snapshot(connections_registry=connections)
        connection_gate = connection_gate_snapshot(connections["default"])
        check = django_database_check()
        migrations = migration_snapshot(connections["default"])
        aliases = ensure_only_default_alias(opened_aliases)
        if aliases != ["default"]:
            raise MatrixFailure("database_default_not_opened")
    passenger = passenger_snapshot()
    return {
        "version": 1,
        "status": "ok",
        "mode": "server",
        "phase": phase,
        "dtf_scope": "excluded",
        "git": git,
        "runtime": runtime,
        "database": database,
        "connection_gate": connection_gate,
        "database_check": check,
        "migrations": migrations,
        "opened_database_aliases": aliases,
        "passenger": passenger,
    }


def run_http_matrix(*, phase: str) -> dict[str, object]:
    return {
        "version": 1,
        "status": "ok",
        "mode": "http",
        "phase": phase,
        "dtf_scope": "excluded",
        "user_agent": USER_AGENT,
        "probes": probe_non_dtf_routes(),
    }


FORBIDDEN_OUTPUT_KEYS = frozenset(
    {
        "body",
        "api_key",
        "access_key",
        "cookie",
        "cookies",
        "credential",
        "credentials",
        "dsn",
        "env",
        "environment",
        "error",
        "exception",
        "executable",
        "header",
        "headers",
        "host",
        "options",
        "password",
        "private_key",
        "raw_exception",
        "secret",
        "secret_key",
        "token",
        "traceback",
        "user",
    }
)
SAFE_DATABASE_KEYS = frozenset({"alias", "server", "status", "version", "vendor"})
SENSITIVE_OUTPUT_KEY_MARKERS = ("cookie", "credential", "password", "secret", "token")
PRIVATE_DATABASE_KEYS = frozenset(
    {
        "database_host",
        "database_name",
        "database_url",
        "database_user",
        "db_host",
        "db_name",
        "db_url",
        "db_user",
    }
)


def _sanitized_value(value: Any, *, parent_key: str = "") -> Any:
    if isinstance(value, BaseException):
        return None
    if isinstance(value, Mapping):
        clean: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            normalized = key.casefold()
            if (
                normalized in FORBIDDEN_OUTPUT_KEYS
                or normalized in PRIVATE_DATABASE_KEYS
                or any(marker in normalized for marker in SENSITIVE_OUTPUT_KEY_MARKERS)
            ):
                continue
            if parent_key == "database" and normalized not in SAFE_DATABASE_KEYS:
                continue
            sanitized = _sanitized_value(raw_value, parent_key=normalized)
            if sanitized is not None:
                clean[key] = sanitized
        return clean
    if isinstance(value, (list, tuple)):
        return [
            sanitized
            for item in value
            if (sanitized := _sanitized_value(item, parent_key=parent_key)) is not None
        ]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return None


def sanitized_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    sanitized = _sanitized_value(payload)
    return sanitized if isinstance(sanitized, dict) else {}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)
    server = subparsers.add_parser("server", help="Check production server state")
    server.add_argument("--phase", choices=("preflight", "post-deploy"), required=True)
    server.add_argument("--expected-sha")
    http = subparsers.add_parser("http", help="Check public non-DTF routes")
    http.add_argument("--phase", choices=("preflight", "post-deploy"), required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.mode == "server":
            payload = run_server_matrix(
                phase=args.phase,
                expected_sha=args.expected_sha,
            )
        else:
            payload = run_http_matrix(phase=args.phase)
    except MatrixFailure as exc:
        payload = {
            "version": 1,
            "status": "failed",
            "mode": args.mode,
            "phase": args.phase,
            "failed_check": exc.code,
        }
        returncode = 1
    except BaseException:
        payload = {
            "version": 1,
            "status": "failed",
            "mode": args.mode,
            "phase": args.phase,
            "failed_check": "internal_error",
        }
        returncode = 1
    else:
        returncode = 0
    print(json.dumps(sanitized_payload(payload), sort_keys=True, separators=(",", ":")))
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
