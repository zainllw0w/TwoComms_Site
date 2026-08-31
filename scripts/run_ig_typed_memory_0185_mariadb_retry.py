#!/usr/bin/env python3
"""Arbitrary-DDL kill/resume proof for Typed Memory V2 migration 0185."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1] / "twocomms"
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


EXPECTED_SETTINGS = "test_settings_mariadb"
DISPOSABLE_NAME_RE = re.compile(r"^test_twocomms_[A-Za-z0-9_]+$")
KILL_EXIT_CODE = 97
BEFORE = ("management", "0184_assisted_checkout_generation_v2")
TARGET = ("management", "0185_typed_memory_v2")


def _arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-disposable", action="store_true")
    parser.add_argument("--phase", choices=("orchestrate", "kill"), default="orchestrate")
    parser.add_argument("--kill-after", type=int, default=5)
    return parser.parse_args()


def _setup(args):
    if not args.confirm_disposable:
        raise RuntimeError("--confirm-disposable is required")
    if os.environ.get("DJANGO_SETTINGS_MODULE") != EXPECTED_SETTINGS:
        raise RuntimeError("DJANGO_SETTINGS_MODULE must be test_settings_mariadb")
    if args.kill_after < 1:
        raise RuntimeError("--kill-after must be positive")
    import django

    django.setup()
    from django.db import connection

    database = str(connection.settings_dict.get("NAME") or "")
    if connection.vendor != "mysql" or not DISPOSABLE_NAME_RE.fullmatch(database):
        raise RuntimeError("refusing non-disposable or non-MariaDB database")
    return connection, database


def _kill(args):
    connection, _database = _setup(args)
    from django.db.migrations.executor import MigrationExecutor

    schema_editor_class = connection.SchemaEditorClass
    original = schema_editor_class.execute
    counter = {"value": 0}

    def interrupted(self, sql, params=()):
        result = original(self, sql, params)
        counter["value"] += 1
        if counter["value"] == args.kill_after:
            os._exit(KILL_EXIT_CODE)
        return result

    schema_editor_class.execute = interrupted
    MigrationExecutor(connection).migrate([TARGET])
    raise RuntimeError(
        f"kill point {args.kill_after} exceeds executed DDL count {counter['value']}"
    )


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
            "--phase", "kill",
            "--kill-after", str(args.kill_after),
        ],
        env=os.environ.copy(),
        check=False,
        timeout=240,
    )
    if child.returncode != KILL_EXIT_CODE:
        raise RuntimeError(
            f"kill phase returned {child.returncode}, expected {KILL_EXIT_CODE}"
        )
    close_old_connections()
    from django.db import connection as resumed

    MigrationExecutor(resumed).migrate([TARGET])
    tables = (
        "management_igmemoryfact",
        "management_igmemoryfactevidence",
        "management_igmemoryhead",
    )
    with resumed.cursor() as cursor:
        cursor.execute(
            "SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN (%s)"
            % ", ".join(["%s"] * len(tables)),
            list(tables),
        )
        engines = {str(table): str(engine).upper() for table, engine in cursor.fetchall()}
        cursor.execute(
            "SELECT TRIGGER_NAME FROM information_schema.TRIGGERS "
            "WHERE TRIGGER_SCHEMA=DATABASE() AND TRIGGER_NAME LIKE 'ig_mem%'"
        )
        triggers = sorted(str(row[0]) for row in cursor.fetchall())
        cursor.execute(
            "SELECT TRIGGER_NAME FROM information_schema.TRIGGERS "
            "WHERE TRIGGER_SCHEMA=DATABASE() AND TRIGGER_NAME IN "
            "('ig_anres_insert_guard','ig_anres_no_delete','ig_anprop_no_delete','ig_mat_no_delete')"
        )
        retired = [str(row[0]) for row in cursor.fetchall()]
    if set(engines) != set(tables) or set(engines.values()) != {"INNODB"}:
        raise RuntimeError(f"unexpected typed-memory engines: {engines}")
    if len(triggers) < 9 or retired:
        raise RuntimeError(
            f"typed-memory trigger contract incomplete: triggers={triggers}, retired={retired}"
        )
    report = {
        "database": database,
        "kill_after": args.kill_after,
        "engines": engines,
        "trigger_count": len(triggers),
        "migration": TARGET[1],
    }
    print("TYPED_MEMORY_0185_RETRY=" + json.dumps(report, sort_keys=True))


def main():
    args = _arguments()
    if args.phase == "kill":
        _kill(args)
    else:
        _orchestrate(args)


if __name__ == "__main__":
    main()
