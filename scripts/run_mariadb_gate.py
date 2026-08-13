#!/usr/bin/env python3
"""Run the Instagram bot's disposable MariaDB acceptance gate.

The runner owns only a generated schema/user.  It never accepts a schema or
user name from the caller and never falls back to SQLite or the application
database.  ``external`` is the CI service-container mode; ``native`` is a
strict adapter for a locally provisioned MariaDB server.
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from ipaddress import ip_address
from pathlib import Path
from typing import Callable, Mapping, TextIO


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUITE = "lifecycle"
SUITES = {
    "lifecycle": ("management.tests_ig_mariadb_lifecycle",),
    "checkout-concurrency": (
        "management.tests_ig_checkout_models."
        "IgCheckoutProposalConcurrencyTests."
        "test_concurrent_replacement_creation_serializes_on_deal",
    ),
}
SAFE_ENV_NAMES = {
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "VIRTUAL_ENV",
    "SYSTEMROOT",
}
PROVIDER_ENV_PREFIXES = (
    "TELEGRAM_",
    "MANAGER_TG_",
    "MANAGEMENT_TG_",
    "META_",
    "GEMINI_",
    "OPENAI_",
    "FACEBOOK_",
)
PRODUCTION_ENV_NAMES = {
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "DB_HOST",
    "DB_PORT",
    "DB_NAME_DTF",
    "DB_USER_DTF",
    "DB_PASSWORD_DTF",
    "DB_HOST_DTF",
    "DB_PORT_DTF",
}
MAX_FAILURE_SUMMARY_CHARS = 2048
MAX_FAILURE_LINE_CHARS = 500
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])")
_PHONE_RE = re.compile(r"(?<!\w)\+?\d[\d\s().-]{7,}\d(?!\w)")
_URL_CREDENTIALS_RE = re.compile(r"(?i)(://)[^\s/@:]+:[^\s/@]+@")
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(token|password|passwd|secret|authorization|api[_-]?key)"
    r"\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)
_TEST_RESULT_RE = re.compile(
    r"^(?:(?:ERROR|FAIL):\s+.+|Ran \d+ tests? in [0-9.]+s|"
    r"FAILED(?: \([^)]*\))?|OK(?: \([^)]*\))?)$"
)
_EXCEPTION_RE = re.compile(
    r"^((?:[A-Za-z_]\w*\.)*[A-Za-z_]\w*(?:Error|Exception|Failure)):(?:\s.*)?$"
)


class GateError(RuntimeError):
    """A failed gate, retaining both execution and cleanup errors."""

    def __init__(
        self,
        message: str,
        *,
        primary_error: BaseException | None = None,
        cleanup_error: BaseException | None = None,
        cleanup_errors: list[BaseException] | tuple[BaseException, ...] = (),
    ):
        self.cleanup_errors = tuple(
            cleanup_errors or (() if cleanup_error is None else (cleanup_error,))
        )
        self.cleanup_error = cleanup_error or (self.cleanup_errors[0] if self.cleanup_errors else None)
        if self.cleanup_errors:
            message = f"{message}: " + "; ".join(str(error) for error in self.cleanup_errors)
        super().__init__(message)
        self.primary_error = primary_error


def _sanitize_failure_line(line: str) -> str:
    line = _ANSI_ESCAPE_RE.sub("", line.strip())
    line = _URL_CREDENTIALS_RE.sub(r"\1[redacted]@", line)
    line = _BEARER_RE.sub("Bearer [redacted]", line)
    line = _SECRET_ASSIGNMENT_RE.sub(r"\1=[redacted]", line)
    line = _EMAIL_RE.sub("[redacted-email]", line)
    line = _PHONE_RE.sub("[redacted-phone]", line)
    return line[:MAX_FAILURE_LINE_CHARS]


def _failure_summary(*, suite: str, completed: subprocess.CompletedProcess) -> str:
    lines = [
        f"MariaDB gate child failed: suite={suite} exit={completed.returncode}"
    ]
    for raw_line in (completed.stderr or "").splitlines():
        candidate = _ANSI_ESCAPE_RE.sub("", raw_line.strip())
        exception_match = _EXCEPTION_RE.fullmatch(candidate)
        if exception_match:
            lines.append(f"{exception_match.group(1)}:")
        elif _TEST_RESULT_RE.fullmatch(candidate):
            lines.append(_sanitize_failure_line(candidate))
    summary = "\n".join(lines) + "\n"
    return summary[:MAX_FAILURE_SUMMARY_CHARS]


class AdminClient:
    """Small DB-admin protocol backed by the pinned PyMySQL dependency."""

    def __init__(self, *, host: str, port: str, user: str, password: str):
        self.host = host
        self.port = str(port)
        self.user = user
        self.password = password

    def _sql(self, statement: str) -> None:
        try:
            import pymysql
        except ImportError as exc:
            raise RuntimeError("PyMySQL is required for MariaDB admin operations") from exc
        connection = None
        try:
            connection = pymysql.connect(
                host=self.host,
                port=int(self.port),
                user=self.user,
                password=self.password,
                charset="utf8mb4",
                connect_timeout=10,
                read_timeout=30,
                write_timeout=30,
                autocommit=True,
            )
            with connection.cursor() as cursor:
                cursor.execute(statement)
        finally:
            if connection is not None:
                connection.close()

    def _query_one(self, statement: str):
        try:
            import pymysql
        except ImportError as exc:
            raise RuntimeError("PyMySQL is required for MariaDB admin operations") from exc
        connection = None
        try:
            connection = pymysql.connect(
                host=self.host,
                port=int(self.port),
                user=self.user,
                password=self.password,
                charset="utf8mb4",
                connect_timeout=10,
                read_timeout=30,
                write_timeout=30,
                autocommit=True,
            )
            with connection.cursor() as cursor:
                cursor.execute(statement)
                return cursor.fetchone()
        finally:
            if connection is not None:
                connection.close()

    def _query_all(self, statement: str) -> list[tuple]:
        try:
            import pymysql
        except ImportError as exc:
            raise RuntimeError("PyMySQL is required for MariaDB admin operations") from exc
        connection = None
        try:
            connection = pymysql.connect(
                host=self.host,
                port=int(self.port),
                user=self.user,
                password=self.password,
                charset="utf8mb4",
                connect_timeout=10,
                read_timeout=30,
                write_timeout=30,
                autocommit=True,
            )
            with connection.cursor() as cursor:
                cursor.execute(statement)
                return list(cursor.fetchall())
        finally:
            if connection is not None:
                connection.close()

    def server_identity(self) -> tuple[str, str]:
        version, version_comment = self._query_one(
            "SELECT VERSION(), @@version_comment"
        )
        return str(version), str(version_comment)

    def close(self) -> None:
        """Admin clients have no owned process; native servers override this."""

    def create_database(self, name: str) -> None:
        self._sql(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")

    def create_user(self, username: str, password: str) -> None:
        self._sql(f"CREATE USER '{username}'@'%' IDENTIFIED BY '{password}'")

    def grant_schema(self, username: str, database: str) -> None:
        self._sql(f"GRANT ALL PRIVILEGES ON `{database}`.* TO '{username}'@'%'")

    def ensure_namespace_absent(self, database: str, username: str) -> None:
        database_row = self._query_one(
            "SELECT COUNT(*) FROM information_schema.SCHEMATA "
            f"WHERE SCHEMA_NAME = '{database}'"
        )
        user_row = self._query_one(
            "SELECT COUNT(*) FROM mysql.user "
            f"WHERE User = '{username}'"
        )
        existing = []
        if database_row and database_row[0]:
            existing.append("database")
        if user_row and user_row[0]:
            existing.append("user")
        if existing:
            raise GateError(
                "Refusing MariaDB gate: generated "
                + " and ".join(existing)
                + " already exists"
            )

    def drop_user(self, username: str) -> None:
        # The gate creates only the `%` account.  Never delete a same-name
        # account created by another owner after the absence proof.
        self._sql(f"DROP USER IF EXISTS '{username}'@'%'")

    def drop_database(self, database: str) -> None:
        self._sql(f"DROP DATABASE IF EXISTS `{database}`")

    def verify_cleanup(self, database: str, username: str) -> tuple[bool, bool]:
        database_row = self._query_one(
            "SELECT COUNT(*) FROM information_schema.SCHEMATA "
            f"WHERE SCHEMA_NAME = '{database}'"
        )
        user_row = self._query_one(
            "SELECT COUNT(*) FROM mysql.user "
            f"WHERE User = '{username}'"
        )
        return bool(user_row[0]), bool(database_row[0])


def _generated_identifiers() -> tuple[str, str, str]:
    token = uuid.uuid4().hex[:12]
    return f"test_twocomms_ig_{token}", f"twc_ig_{token}", secrets.token_urlsafe(24)


def _canonical_host(value: str) -> str:
    host = (value or "").strip().lower().rstrip(".")
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    try:
        address = ip_address(host)
    except ValueError:
        address = None
    if address is not None:
        return "loopback" if address.is_loopback else address.compressed
    return "loopback" if host in {"localhost", "localhost.localdomain"} else host


def _is_loopback(value: str) -> bool:
    return _canonical_host(value) == "loopback"


def _production_hosts(source: Mapping[str, str]) -> set[str]:
    return {
        _canonical_host(source.get(host_name) or "localhost")
        for database_name, host_name in (
            ("DB_NAME", "DB_HOST"),
            ("DB_NAME_DTF", "DB_HOST_DTF"),
        )
        if (source.get(database_name) or "").strip()
    }


def _validate_target_host(source: Mapping[str, str], host: str) -> None:
    canonical = _canonical_host(host)
    if canonical in _production_hosts(source):
        raise GateError("Refusing MariaDB gate: target matches a configured production database host")
    if not _is_loopback(host) and source.get("TEST_MARIADB_REMOTE_ALLOWED") != "1":
        raise GateError(
            "MariaDB gate target is remote; set TEST_MARIADB_REMOTE_ALLOWED=1 explicitly"
        )


def _validate_entrypoint(project_root: Path) -> Path:
    manage_path = Path(project_root) / "twocomms" / "manage.py"
    if not manage_path.is_file():
        raise GateError(f"Django entrypoint is missing: {manage_path}")
    return manage_path


def _validate_server_identity(identity: tuple[str, str]) -> tuple[str, str]:
    version, version_comment = (str(value) for value in identity)
    lowered = f"{version} {version_comment}".lower()
    if "mariadb" not in lowered or not version.startswith("11.4"):
        raise GateError(
            "MariaDB 11.4 is required; received "
            f"version={version!r} comment={version_comment!r}"
        )
    return version, version_comment


def _process_environment(source: Mapping[str, str]) -> dict[str, str]:
    environment = {
        key: value
        for key, value in source.items()
        if key in SAFE_ENV_NAMES
        and key not in PRODUCTION_ENV_NAMES
        and not any(key.startswith(prefix) for prefix in PROVIDER_ENV_PREFIXES)
    }
    environment["PYTHONNOUSERSITE"] = "1"
    return environment


def _child_environment(
    source: Mapping[str, str], *, database: str, username: str, password: str,
    host: str, port: str,
) -> dict[str, str]:
    environment = _process_environment(source)
    environment.update({
        "SECRET_KEY": "test-secret-key-for-mariadb-gate",
        "TEST_MARIADB_NAME": database,
        "TEST_MARIADB_USER": username,
        "TEST_MARIADB_PASSWORD": password,
        "TEST_MARIADB_HOST": host,
        "TEST_MARIADB_PORT": str(port),
        "MANAGER_TG_BOT_TOKEN": "",
        "MANAGEMENT_TG_BOT_TOKEN": "",
        "TELEGRAM_BOT_TOKEN": "",
        "TELEGRAM_CHAT_ID": "",
        "TELEGRAM_ADMIN_ID": "",
    })
    if not _is_loopback(host) and source.get("TEST_MARIADB_REMOTE_ALLOWED") == "1":
        environment["TEST_MARIADB_REMOTE_ALLOWED"] = "1"
    return environment


def _command_runner(args: list[str], **kwargs):
    return subprocess.run(args, **kwargs)


def _validate_suite(suite: str) -> tuple[str, ...]:
    try:
        return SUITES[suite]
    except KeyError as exc:
        raise GateError(f"unsupported MariaDB suite: {suite}") from exc


class NativeMariaDb:
    """Own a temporary loopback MariaDB instance for the native mode."""

    def __init__(
        self,
        *,
        binaries: Mapping[str, str],
        command_runner: Callable[..., subprocess.CompletedProcess],
        environment: Mapping[str, str] | None = None,
        project_root: Path = PROJECT_ROOT,
    ):
        self._binaries = binaries
        self._command_runner = command_runner
        self._environment = dict(environment or _process_environment(os.environ))
        self._project_root = project_root
        self._tempdir = None
        self._process = None
        self.admin = None

    def start(self) -> "NativeMariaDb":
        try:
            self._tempdir = tempfile.TemporaryDirectory(prefix="twc-ig-mariadb-")
            data_dir = Path(self._tempdir.name) / "data"
            socket_path = Path(self._tempdir.name) / "mariadb.sock"
            data_dir.mkdir()
            initialized = self._command_runner(
                [
                    self._binaries["mariadb-install-db"],
                    "--no-defaults",
                    f"--datadir={data_dir}",
                    "--auth-root-authentication-method=normal",
                    "--skip-test-db",
                ],
                cwd=str(self._project_root), env=self._environment,
                capture_output=True, text=True, check=False, timeout=60,
            )
            if initialized.returncode:
                raise GateError(f"native MariaDB initialization failed ({initialized.returncode})")
            port = _free_port()
            log_path = Path(self._tempdir.name) / "mariadb.err"
            self._process = subprocess.Popen(
                [
                    self._binaries["mariadbd"], "--no-defaults", f"--datadir={data_dir}",
                    "--bind-address=127.0.0.1", f"--port={port}",
                    f"--socket={socket_path}", f"--log-error={log_path}",
                    "--skip-name-resolve",
                ],
                cwd=str(self._project_root), env=self._environment, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self.admin = AdminClient(host="127.0.0.1", port=str(port), user="root", password="")
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if self._process.poll() is not None:
                    raise GateError("native MariaDB server exited during startup")
                try:
                    self.admin._sql("SELECT 1")
                    return self
                except Exception:
                    time.sleep(0.2)
            raise GateError("native MariaDB server did not become ready within 30 seconds")
        except BaseException as primary_error:
            try:
                self.close()
            except BaseException as cleanup_error:
                raise GateError(
                    "native MariaDB startup failed and cleanup failed",
                    primary_error=primary_error,
                    cleanup_errors=[cleanup_error],
                ) from primary_error
            raise

    def __getattr__(self, name):
        return getattr(self.admin, name)

    def close(self) -> None:
        try:
            if self._process is not None and self._process.poll() is None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait(timeout=5)
        finally:
            if self._tempdir is not None:
                self._tempdir.cleanup()
                self._tempdir = None


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _native_admin(
    environ: Mapping[str, str],
    binaries: Mapping[str, str | None] | None = None,
    command_runner: Callable[..., subprocess.CompletedProcess] = _command_runner,
    project_root: Path = PROJECT_ROOT,
):
    supplied = binaries or {}
    required = {
        "mariadbd": supplied.get("mariadbd") or environ.get("MARIADB_SERVER_BIN"),
        "mariadb-install-db": supplied.get("mariadb-install-db") or environ.get("MARIADB_INSTALL_DB_BIN"),
    }
    if not required["mariadbd"] or not required["mariadb-install-db"]:
        import shutil
        path = environ.get("PATH")
        required["mariadbd"] = required["mariadbd"] or shutil.which("mariadbd", path=path)
        required["mariadb-install-db"] = required["mariadb-install-db"] or shutil.which(
            "mariadb-install-db", path=path
        )
    missing = [name for name, path in required.items() if not path]
    if missing:
        raise GateError("native MariaDB provisioning requires: " + ", ".join(missing))
    return NativeMariaDb(
        binaries=required,
        command_runner=command_runner,
        environment=_process_environment(environ),
        project_root=project_root,
    ).start()


def run_gate(
    *,
    server_mode: str,
    suite: str = DEFAULT_SUITE,
    admin: AdminClient | object | None = None,
    command_runner: Callable[..., subprocess.CompletedProcess] = _command_runner,
    environ: Mapping[str, str] | None = None,
    project_root: Path = PROJECT_ROOT,
    output: TextIO | None = None,
    native_binaries: Mapping[str, str | None] | None = None,
) -> dict[str, str]:
    source = dict(os.environ if environ is None else environ)
    output = output or sys.stdout
    modules = _validate_suite(suite)
    if server_mode not in {"external", "native"}:
        raise GateError(f"unsupported MariaDB server mode: {server_mode}")
    manage_path = _validate_entrypoint(project_root)
    database, username, password = _generated_identifiers()
    host = (source.get("MARIADB_HOST") or source.get("TEST_MARIADB_HOST") or "127.0.0.1").strip()
    port = (source.get("MARIADB_PORT") or source.get("TEST_MARIADB_PORT") or "3306").strip()
    _validate_target_host(source, host)
    if admin is None:
        if server_mode == "native":
            admin = _native_admin(
                source,
                native_binaries,
                command_runner,
                project_root=project_root,
            )
        else:
            admin_user = (source.get("MARIADB_ADMIN_USER") or "root").strip()
            admin_password = source.get("MARIADB_ADMIN_PASSWORD") or ""
            if not admin_password:
                raise GateError("external MariaDB mode requires MARIADB_ADMIN_PASSWORD")
            admin = AdminClient(
                host=host,
                port=port,
                user=admin_user,
                password=admin_password,
            )
    host = getattr(admin, "host", host)
    port = str(getattr(admin, "port", port))
    _validate_target_host(source, host)
    primary_error = None
    result = None
    cleanup_errors: list[BaseException] = []
    database_attempted = False
    user_attempted = False
    version = version_comment = ""
    try:
        try:
            version, version_comment = _validate_server_identity(admin.server_identity())
        except GateError:
            raise
        except BaseException as exc:
            raise GateError("MariaDB server identity query failed") from exc
        ensure_namespace_absent = getattr(admin, "ensure_namespace_absent", None)
        if ensure_namespace_absent is None:
            raise GateError("MariaDB admin client cannot prove generated namespace ownership")
        ensure_namespace_absent(database, username)
        # The absence proof establishes ownership before CREATE so an ambiguous
        # post-CREATE transport failure is still cleaned up safely.
        database_attempted = True
        user_attempted = True
        admin.create_database(database)
        admin.create_user(username, password)
        admin.grant_schema(username, database)
        child_env = _child_environment(
            source, database=database, username=username, password=password,
            host=host, port=port,
        )
        command = [
            sys.executable,
            str(manage_path),
            "test",
            *modules,
            "--settings=test_settings_mariadb",
            "--noinput",
            "--keepdb",
        ]
        completed = command_runner(
            command,
            cwd=str(project_root / "twocomms"),
            env=child_env,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode:
            output.write(_failure_summary(suite=suite, completed=completed))
            primary_error = RuntimeError(f"{suite} command failed ({completed.returncode})")
            raise primary_error
        result = {
            "status": "passed",
            "database": database,
            "suite": suite,
            "version": version,
            "version_comment": version_comment,
        }
    except BaseException as exc:
        primary_error = primary_error or exc
    finally:
        if user_attempted:
            try:
                admin.drop_user(username)
            except BaseException as exc:
                cleanup_errors.append(exc)
        if database_attempted:
            try:
                admin.drop_database(database)
            except BaseException as exc:
                cleanup_errors.append(exc)
        if (user_attempted or database_attempted) and hasattr(admin, "verify_cleanup"):
            try:
                user_exists, database_exists = admin.verify_cleanup(database, username)
                if user_exists or database_exists:
                    cleanup_errors.append(
                        RuntimeError(
                            "cleanup verification found residue: "
                            f"user={bool(user_exists)} database={bool(database_exists)}"
                        )
                    )
            except BaseException as exc:
                cleanup_errors.append(exc)
        close = getattr(admin, "close", None)
        if close:
            try:
                close()
            except BaseException as exc:
                cleanup_errors.append(exc)
        if cleanup_errors:
            if primary_error:
                raise GateError(
                    "MariaDB gate failed and cleanup failed",
                    primary_error=primary_error,
                    cleanup_errors=cleanup_errors,
                ) from primary_error
            raise GateError(
                "MariaDB gate cleanup failed", cleanup_errors=cleanup_errors
            ) from cleanup_errors[0]
    if primary_error:
        if isinstance(primary_error, GateError):
            raise primary_error
        raise GateError("MariaDB gate failed", primary_error=primary_error) from primary_error
    result["cleanup"] = "verified"
    output.write(
        f"MariaDB gate passed: mode={server_mode} suite={suite} "
        f"version={version} cleanup=verified\n"
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-mode", choices=("native", "external"), required=True)
    parser.add_argument("--suite", choices=tuple(SUITES), default=DEFAULT_SUITE)
    args = parser.parse_args(argv)
    try:
        run_gate(server_mode=args.server_mode, suite=args.suite)
    except GateError as exc:
        print(f"MariaDB gate failed: {exc}", file=sys.stderr)
        return 1
    except BaseException as exc:
        print(f"MariaDB gate failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
