from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency during bootstrap
    def load_dotenv(*args, **kwargs):
        return False


_DEFAULT_SQL_MODE = (
    "STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ZERO_DATE,"
    "NO_ZERO_IN_DATE,NO_ENGINE_SUBSTITUTION"
)


def load_environment(base_dir: Path | None = None) -> Path | None:
    """
    Load the first available env file so every entrypoint resolves configuration
    the same way in local shells, Passenger and one-off management commands.
    """
    base_dir = base_dir or Path(__file__).resolve().parent.parent

    candidates: list[Path] = []

    explicit_env = os.environ.get("DJANGO_ENV_FILE")
    if explicit_env:
        env_path = Path(explicit_env).expanduser()
        if not env_path.is_absolute():
            env_path = base_dir / env_path
        candidates.append(env_path)

    for candidate in (base_dir / ".env.production", base_dir / ".env"):
        if candidate not in candidates:
            candidates.append(candidate)

    for candidate in candidates:
        if candidate.exists():
            os.environ["DJANGO_ENV_FILE"] = str(candidate)
            load_dotenv(candidate)
            return candidate
    return None


def configure_django(
    default_settings_module: str = "twocomms.settings",
    *,
    base_dir: Path | None = None,
) -> str:
    load_environment(base_dir=base_dir)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", default_settings_module)
    return os.environ["DJANGO_SETTINGS_MODULE"]


def install_mysql_driver() -> str | None:
    """
    Django 6 requires mysqlclient for MySQL/MariaDB connections.
    Keep bootstrap silent for SQLite-only environments, but fail fast with a
    clear error when MySQL is configured and mysqlclient is unavailable.
    """
    try:
        import MySQLdb  # noqa: F401
    except Exception:
        if any(os.environ.get(key) for key in ("DB_NAME", "DB_NAME_DTF")):
            raise RuntimeError(
                "mysqlclient>=2.2.1 is required for Django 6 with MySQL/MariaDB. "
                "Install mysqlclient in the active environment before starting Django."
            )
        return None
    return "mysqlclient"


def _db_env(name: str, *, suffix: str = "", default: str = "") -> str:
    if suffix:
        value = os.environ.get(f"{name}{suffix}")
        if value not in (None, ""):
            return value
    return os.environ.get(name, default)


def _db_int(name: str, *, suffix: str = "", default: int) -> int:
    raw = _db_env(name, suffix=suffix, default=str(default))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _build_mysql_options(*, suffix: str = "") -> dict:
    options = {
        "charset": "utf8mb4",
        "use_unicode": True,
        "init_command": "SET NAMES 'utf8mb4' COLLATE 'utf8mb4_unicode_ci'",
        "connect_timeout": _db_int("DB_CONNECT_TIMEOUT", suffix=suffix, default=10),
        "read_timeout": _db_int("DB_READ_TIMEOUT", suffix=suffix, default=30),
        "write_timeout": _db_int("DB_WRITE_TIMEOUT", suffix=suffix, default=30),
        "sql_mode": _db_env("DB_SQL_MODE", suffix=suffix, default=_DEFAULT_SQL_MODE),
    }

    ssl = {}
    ca = _db_env("DB_SSL_CA", suffix=suffix)
    cert = _db_env("DB_SSL_CERT", suffix=suffix)
    key = _db_env("DB_SSL_KEY", suffix=suffix)
    if ca:
        ssl["ca"] = ca
    if cert:
        ssl["cert"] = cert
    if key:
        ssl["key"] = key
    if ssl:
        options["ssl"] = ssl

    return options


def _build_mysql_database(*, suffix: str = "") -> dict | None:
    name = _db_env("DB_NAME", suffix=suffix)
    user = _db_env("DB_USER", suffix=suffix)
    if not name or not user:
        return None

    return {
        "ENGINE": "django.db.backends.mysql",
        "NAME": name,
        "USER": user,
        "PASSWORD": _db_env("DB_PASSWORD", suffix=suffix),
        "HOST": _db_env("DB_HOST", suffix=suffix, default="localhost"),
        "PORT": _db_env("DB_PORT", suffix=suffix, default="3306"),
        "CONN_MAX_AGE": _db_int("DB_CONN_MAX_AGE", suffix=suffix, default=300),
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": _build_mysql_options(suffix=suffix),
    }


def build_database_settings(*, base_dir: Path, debug: bool) -> tuple[dict, list[str]]:
    """
    Shared DB builder for local/dev/prod entrypoints.
    Production is MySQL/MariaDB only. Local development still falls back to SQLite.
    """
    del debug  # kept for a stable call signature across settings modules

    databases = {}
    default_db = _build_mysql_database()
    if default_db:
        databases["default"] = default_db
    else:
        databases["default"] = {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": base_dir / "db.sqlite3",
        }

    routers: list[str] = []
    dtf_name = _db_env("DB_NAME", suffix="_DTF").strip()
    if dtf_name:
        dtf_db = _build_mysql_database(suffix="_DTF")
        if dtf_db:
            databases["dtf"] = dtf_db
        else:
            sqlite_name = Path(dtf_name) if dtf_name.endswith(".sqlite3") else Path("db_dtf.sqlite3")
            if not sqlite_name.is_absolute():
                sqlite_name = base_dir / sqlite_name
            databases["dtf"] = {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": sqlite_name,
            }
        routers = ["twocomms.db_routers.DtfDatabaseRouter"]

    return databases, routers
