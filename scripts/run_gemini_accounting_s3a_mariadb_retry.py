#!/usr/bin/env python3
"""Destructive kill/retry proof for a guarded disposable MariaDB database only.

Example (credentials intentionally omitted):

    DJANGO_SETTINGS_MODULE=test_settings_mariadb \
    TEST_MARIADB_NAME=test_twocomms_<unique> ... \
    "$TWC_PYTHON" scripts/run_gemini_accounting_s3a_mariadb_retry.py \
      --confirm-disposable
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[1]
PROJECT_ROOT = REPO_ROOT / "twocomms"


def _bootstrap_project() -> None:
    """Make Django settings importable from any caller cwd without PYTHONPATH."""
    project = str(PROJECT_ROOT)
    if project not in sys.path:
        sys.path.insert(0, project)
    os.chdir(PROJECT_ROOT)


_bootstrap_project()


EXPECTED_SETTINGS = "test_settings_mariadb"
DISPOSABLE_NAME_RE = re.compile(r"^test_twocomms_[A-Za-z0-9_]+$")
KILL_EXIT_CODE = 97


def _arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-disposable", action="store_true")
    parser.add_argument("--phase", choices=("orchestrate", "kill"), default="orchestrate")
    return parser.parse_args()


def _setup(args):
    if not args.confirm_disposable:
        raise RuntimeError("--confirm-disposable is required")
    if os.environ.get("DJANGO_SETTINGS_MODULE") != EXPECTED_SETTINGS:
        raise RuntimeError(
            "DJANGO_SETTINGS_MODULE must be test_settings_mariadb"
        )
    import django

    django.setup()
    from django.db import connection

    database = str(connection.settings_dict.get("NAME") or "")
    if connection.vendor != "mysql" or not DISPOSABLE_NAME_RE.fullmatch(database):
        raise RuntimeError("refusing non-disposable or non-MariaDB database")
    return connection, database


def _kill_phase(args):
    connection, _database = _setup(args)
    from django.db.migrations.executor import MigrationExecutor
    from management.migration_operations import IdempotentAddField

    original = IdempotentAddField.database_forwards
    counter = {"completed": 0}

    def kill_after_five(self, *operation_args, **operation_kwargs):
        result = original(self, *operation_args, **operation_kwargs)
        counter["completed"] += 1
        if counter["completed"] == 5:
            os._exit(KILL_EXIT_CODE)
        return result

    IdempotentAddField.database_forwards = kill_after_five
    MigrationExecutor(connection).migrate([
        ("management", "0179_gemini_accounting_v2_schema")
    ])
    raise RuntimeError("kill phase reached the end without interruption")


def _orchestrate(args):
    connection, database = _setup(args)
    from django.db import close_old_connections
    from django.db.migrations.executor import MigrationExecutor

    MigrationExecutor(connection).migrate([
        ("management", "0178_gemini_accounting_prerequisite_innodb")
    ])
    child = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--confirm-disposable",
            "--phase",
            "kill",
        ],
        env=os.environ.copy(),
        check=False,
        timeout=180,
    )
    if child.returncode != KILL_EXIT_CODE:
        raise RuntimeError(
            f"kill phase returned {child.returncode}, expected {KILL_EXIT_CODE}"
        )
    close_old_connections()
    from django.db import connection as resumed_connection

    executor = MigrationExecutor(resumed_connection)
    executor.migrate([("management", "0181_gemini_accounting_v2_innodb")])
    apps = MigrationExecutor(resumed_connection).loader.project_state([
        ("management", "0181_gemini_accounting_v2_innodb")
    ]).apps
    tables = (
        "management_geminiquotaprofile",
        "management_geminiquotastate",
        "management_geminirequest",
        "management_geminirequestattempt",
        "management_geminimodelquotausage",
    )
    with resumed_connection.cursor() as cursor:
        cursor.execute(
            "SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME IN (%s)"
            % ", ".join(["%s"] * len(tables)),
            list(tables),
        )
        engines = {str(table): str(engine).upper() for table, engine in cursor.fetchall()}
        request_constraints = resumed_connection.introspection.get_constraints(
            cursor,
            "management_geminirequest",
        )
    if set(engines) != set(tables) or set(engines.values()) != {"INNODB"}:
        raise RuntimeError(f"unexpected accounting engines: {engines}")
    source_lane_unique = request_constraints.get("gem_req_source_lane_uniq")
    if (
        source_lane_unique is None
        or not bool(source_lane_unique.get("unique"))
        or list(source_lane_unique.get("columns") or ())
        != ["source_message_id", "lane"]
    ):
        raise RuntimeError(
            "unexpected Gemini request source/lane unique constraint"
        )
    result = {
        "database": database,
        "kill_exit_code": child.returncode,
        "profiles": apps.get_model(
            "management", "GeminiQuotaProfile"
        ).objects.count(),
        "states": apps.get_model("management", "GeminiQuotaState").objects.count(),
        "requests": apps.get_model("management", "GeminiRequest").objects.count(),
        "engines": engines,
        "source_lane_unique": list(source_lane_unique.get("columns") or ()),
    }
    print("GEMINI_S3A_MARIADB_RETRY=" + json.dumps(result, sort_keys=True))


def main():
    args = _arguments()
    if args.phase == "kill":
        _kill_phase(args)
    else:
        _orchestrate(args)


if __name__ == "__main__":
    main()
