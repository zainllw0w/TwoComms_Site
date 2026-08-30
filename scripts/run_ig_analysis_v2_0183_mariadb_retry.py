#!/usr/bin/env python3
"""Kill/retry proof for Analysis V2 0183 on a guarded disposable MariaDB DB."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys


EXPECTED_SETTINGS = "test_settings_mariadb"
DISPOSABLE_NAME_RE = re.compile(r"^test_twocomms_[A-Za-z0-9_]+$")
KILL_EXIT_CODE = 97
TARGET = ("management", "0183_analysis_v2_result_proposals")
BEFORE = ("management", "0182_analysis_materiality_ledger")


def _arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-disposable", action="store_true")
    parser.add_argument("--phase", choices=("orchestrate", "kill"), default="orchestrate")
    return parser.parse_args()


def _setup(args):
    if not args.confirm_disposable:
        raise RuntimeError("--confirm-disposable is required")
    if os.environ.get("DJANGO_SETTINGS_MODULE") != EXPECTED_SETTINGS:
        raise RuntimeError("DJANGO_SETTINGS_MODULE must be test_settings_mariadb")
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

    schema_editor_class = connection.SchemaEditorClass
    original = schema_editor_class.create_model

    def kill_after_result(self, model):
        result = original(self, model)
        if model._meta.db_table == "management_igconversationanalysisresult":
            os._exit(KILL_EXIT_CODE)
        return result

    schema_editor_class.create_model = kill_after_result
    MigrationExecutor(connection).migrate([TARGET])
    raise RuntimeError("kill phase reached the end without interruption")


def _orchestrate(args):
    connection, database = _setup(args)
    from django.db import close_old_connections
    from django.db.migrations.executor import MigrationExecutor

    MigrationExecutor(connection).migrate([BEFORE])
    child = subprocess.run(
        [
            sys.executable,
            os.path.abspath(__file__),
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

    MigrationExecutor(resumed_connection).migrate([TARGET])
    tables = (
        "management_igconversationanalysisresult",
        "management_iganalysisproposal",
    )
    with resumed_connection.cursor() as cursor:
        cursor.execute(
            "SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN (%s)"
            % ", ".join(["%s"] * len(tables)),
            list(tables),
        )
        engines = {
            str(table): str(engine).upper()
            for table, engine in cursor.fetchall()
        }
        cursor.execute(
            "SELECT TRIGGER_NAME FROM information_schema.TRIGGERS "
            "WHERE TRIGGER_SCHEMA=DATABASE() AND TRIGGER_NAME IN (%s, %s, %s)",
            ["ig_anres_no_update", "ig_anres_no_delete", "ig_anprop_no_delete"],
        )
        triggers = sorted(str(row[0]) for row in cursor.fetchall())
    if set(engines) != set(tables) or set(engines.values()) != {"INNODB"}:
        raise RuntimeError(f"unexpected Analysis V2 engines: {engines}")
    if triggers != sorted([
        "ig_anres_no_update", "ig_anres_no_delete", "ig_anprop_no_delete",
    ]):
        raise RuntimeError(f"unexpected Analysis V2 triggers: {triggers}")
    print("IG_ANALYSIS_V2_0183_MARIADB_RETRY=" + json.dumps({
        "database": database,
        "kill_exit_code": child.returncode,
        "engines": engines,
        "triggers": triggers,
    }, sort_keys=True))


def main():
    args = _arguments()
    if args.phase == "kill":
        _kill_phase(args)
    else:
        _orchestrate(args)


if __name__ == "__main__":
    main()
