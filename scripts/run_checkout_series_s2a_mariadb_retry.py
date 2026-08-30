#!/usr/bin/env python3
"""Kill/resume proof for orders.0058 on a guarded disposable MariaDB.

Example (credentials intentionally omitted)::

    DJANGO_SETTINGS_MODULE=test_settings_mariadb \
    TEST_MARIADB_NAME=test_twocomms_checkout_s2a_<unique> ... \
    TEST_REVIEW_WRITE_FREEZE_MARKER=/absolute/owned-0600-marker \
    "$TWC_PYTHON" scripts/run_checkout_series_s2a_mariadb_retry.py \
      --confirm-disposable

The caller owns database provisioning and cleanup. The script refuses any
non-test namespace and never contacts an external provider.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


EXPECTED_SETTINGS = "test_settings_mariadb"
DISPOSABLE_NAME_RE = re.compile(
    r"^test_twocomms_checkout_s2a_[A-Za-z0-9_]+$"
)
PREVIOUS = ("orders", "0057_paymentattempt_provider_recheck")
TARGET = ("orders", "0058_paymentattempt_checkout_series")
KILL_EXIT_CODE = 97
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = REPOSITORY_ROOT / "twocomms"
SERIES_COLUMNS = {
    "checkout_series_key",
    "checkout_generation",
    "checkout_winner_claimed",
}


def _arguments(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-disposable", action="store_true")
    parser.add_argument(
        "--phase",
        choices=("orchestrate", "kill"),
        default="orchestrate",
    )
    return parser.parse_args(argv)


def _validate_disposable_name(value: str) -> str:
    value = str(value or "").strip()
    if not DISPOSABLE_NAME_RE.fullmatch(value) or len(value) > 64:
        raise RuntimeError(
            "TEST_MARIADB_NAME must be a dedicated "
            "test_twocomms_checkout_s2a_<suffix> database"
        )
    return value


def _setup(args):
    if not args.confirm_disposable:
        raise RuntimeError("--confirm-disposable is required")
    if os.environ.get("DJANGO_SETTINGS_MODULE") != EXPECTED_SETTINGS:
        raise RuntimeError(
            f"DJANGO_SETTINGS_MODULE must be {EXPECTED_SETTINGS}"
        )
    _validate_disposable_name(os.environ.get("TEST_MARIADB_NAME"))
    os.chdir(PROJECT_ROOT)
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    import django

    django.setup()
    from django.db import connection

    database = _validate_disposable_name(connection.settings_dict.get("NAME"))
    if connection.vendor != "mysql":
        raise RuntimeError("checkout-series retry proof requires MariaDB/MySQL")
    return connection, database


def _columns(connection):
    with connection.cursor() as cursor:
        rows = connection.introspection.get_table_description(
            cursor,
            "orders_paymentattempt",
        )
    return {row.name for row in rows}


def _attempt_values(fingerprint, **values):
    return {
        "fingerprint": fingerprint,
        "full_name": "Schema Proof",
        "phone": "+380501112233",
        "city": "Kyiv",
        "np_office": "Branch 1",
        "pay_type": "online_full",
        **values,
    }


def _kill_phase(args):
    connection, _database = _setup(args)
    from django.db.migrations.executor import MigrationExecutor
    from management.migration_operations import IdempotentAddField

    original = IdempotentAddField.database_forwards
    counter = {"completed": 0}

    def interrupted(self, *operation_args, **operation_kwargs):
        result = original(self, *operation_args, **operation_kwargs)
        counter["completed"] += 1
        if counter["completed"] == 2:
            os._exit(KILL_EXIT_CODE)
        return result

    IdempotentAddField.database_forwards = interrupted
    MigrationExecutor(connection).migrate([TARGET])
    raise RuntimeError("kill phase reached migration completion")


def _expect_integrity_error(factory, description):
    from django.db import IntegrityError

    try:
        factory()
    except IntegrityError:
        return True
    raise RuntimeError(f"database accepted {description}")


def _expect_runtime_error(factory, description, expected_fragment):
    try:
        factory()
    except RuntimeError as exc:
        if expected_fragment not in str(exc):
            raise RuntimeError(
                f"schema validator rejected {description} for an unexpected "
                f"reason: {exc}"
            ) from exc
        return True
    raise RuntimeError(f"schema validator accepted {description}")


def _prove_malformed_schema_rejected(connection, migration, check_clause):
    """Mutate only the disposable schema, prove rejection, then restore it."""
    quote = connection.ops.quote_name
    table = quote(migration.TABLE)
    winner = quote("checkout_winner_claimed")
    check_name = quote(migration.CHECK_NAME)

    with connection.cursor() as cursor:
        cursor.execute(
            f"ALTER TABLE {table} ALTER COLUMN {winner} SET DEFAULT 1"
        )
    with connection.schema_editor() as editor:
        malformed_default_rejected = _expect_runtime_error(
            lambda: migration.validate_complete_schema(None, editor),
            "a malformed winner default",
            "has default",
        )
    with connection.cursor() as cursor:
        cursor.execute(
            f"ALTER TABLE {table} ALTER COLUMN {winner} SET DEFAULT 0"
        )

    with connection.cursor() as cursor:
        cursor.execute(f"ALTER TABLE {table} DROP CONSTRAINT {check_name}")
        cursor.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {check_name} CHECK ("
            f"({quote('checkout_series_key')} IS NULL AND "
            f"{quote('checkout_generation')} IS NULL AND "
            f"{quote('checkout_winner_claimed')} = 0) OR "
            f"({quote('checkout_series_key')} IS NOT NULL AND "
            f"{quote('checkout_generation')} IS NOT NULL AND "
            f"{quote('checkout_generation')} >= 0 AND "
            f"{quote('checkout_winner_claimed')} IN (0, 1)))"
        )
    with connection.schema_editor() as editor:
        malformed_check_rejected = _expect_runtime_error(
            lambda: migration.validate_complete_schema(None, editor),
            "a malformed same-name CHECK predicate",
            "normalized predicate",
        )
    with connection.cursor() as cursor:
        cursor.execute(f"ALTER TABLE {table} DROP CONSTRAINT {check_name}")
        cursor.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {check_name} "
            f"CHECK ({check_clause})"
        )
    with connection.schema_editor() as editor:
        migration.validate_complete_schema(None, editor)

    return malformed_default_rejected, malformed_check_rejected


def _orchestrate(args):
    connection, database = _setup(args)
    from django.db import close_old_connections
    from django.db.migrations.exceptions import IrreversibleError
    from django.db.migrations.executor import MigrationExecutor
    from django.db.migrations.recorder import MigrationRecorder
    from importlib import import_module

    executor = MigrationExecutor(connection)
    if TARGET in MigrationRecorder(connection).applied_migrations():
        raise RuntimeError("orders.0058 is already applied; use a fresh test DB")
    executor.migrate([PREVIOUS])
    previous_apps = MigrationExecutor(connection).loader.project_state([PREVIOUS]).apps
    HistoricalAttempt = previous_apps.get_model("orders", "PaymentAttempt")
    legacy = HistoricalAttempt.objects.create(**_attempt_values("1" * 64))
    close_old_connections()

    child = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--confirm-disposable",
            "--phase",
            "kill",
        ],
        cwd=PROJECT_ROOT,
        env=os.environ.copy(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        timeout=300,
        check=False,
    )
    if child.returncode != KILL_EXIT_CODE:
        raise RuntimeError(
            f"kill phase returned {child.returncode}, expected {KILL_EXIT_CODE}: "
            f"{child.stderr[-2000:]}"
        )

    close_old_connections()
    from django.db import connection as resumed

    partial_columns = sorted(_columns(resumed) & SERIES_COLUMNS)
    partial_recorded = TARGET in MigrationRecorder(resumed).applied_migrations()
    if partial_columns != ["checkout_generation", "checkout_series_key"]:
        raise RuntimeError(f"unexpected partial columns: {partial_columns}")
    if partial_recorded:
        raise RuntimeError("partial migration was recorded")

    MigrationExecutor(resumed).migrate([TARGET])
    MigrationExecutor(resumed).migrate([TARGET])
    migration = import_module("orders.migrations.0058_paymentattempt_checkout_series")
    with resumed.schema_editor() as editor:
        migration.validate_complete_schema(None, editor)
        migration.validate_complete_schema(None, editor)

    with resumed.cursor() as cursor:
        descriptions = {
            row.name: row
            for row in resumed.introspection.get_table_description(
                cursor,
                migration.TABLE,
            )
        }
        constraints = resumed.introspection.get_constraints(
            cursor,
            migration.TABLE,
        )
        cursor.execute(
            "SELECT ENGINE FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",
            [migration.TABLE],
        )
        engine = str(cursor.fetchone()[0]).upper()
        cursor.execute(
            "SELECT checkout_series_key, checkout_generation, "
            "checkout_winner_claimed FROM orders_paymentattempt WHERE id=%s",
            [legacy.pk],
        )
        legacy_shape = cursor.fetchone()

    with resumed.schema_editor() as editor:
        check_clause = migration._physical_check_clause(editor)

    for name in migration.INDEX_EXPECTATIONS:
        migration._validate_index(name, constraints[name])
    migration._validate_unique(constraints[migration.UNIQUE_NAME])
    with resumed.schema_editor() as editor:
        migration._validate_check(editor, constraints[migration.CHECK_NAME])
    physical_defaults = {
        name: migration._normalized_default(descriptions[name].default)
        for name in SERIES_COLUMNS
    }
    if engine != "INNODB":
        raise RuntimeError(f"unexpected engine {engine}")
    if not check_clause:
        raise RuntimeError("physical CHECK_CLAUSE missing")
    if legacy_shape != (None, None, 0):
        raise RuntimeError(f"legacy row was changed: {legacy_shape}")
    if physical_defaults != {
        "checkout_series_key": None,
        "checkout_generation": None,
        "checkout_winner_claimed": 0,
    }:
        raise RuntimeError(f"unexpected physical defaults: {physical_defaults}")

    (
        malformed_default_rejected,
        malformed_check_rejected,
    ) = _prove_malformed_schema_rejected(
        resumed,
        migration,
        check_clause,
    )

    from orders.models import PaymentAttempt

    valid = PaymentAttempt.objects.create(
        **_attempt_values(
            "2" * 64,
            checkout_series_key="a" * 64,
            checkout_generation=1,
            checkout_winner_claimed=True,
        )
    )
    invalid_shapes = (
        {"checkout_series_key": "b" * 64},
        {"checkout_generation": 1},
        {"checkout_winner_claimed": True},
        {"checkout_series_key": "", "checkout_generation": 1},
        {"checkout_series_key": "c" * 64, "checkout_generation": 0},
    )
    rejected = 0
    for index, values in enumerate(invalid_shapes, start=3):
        rejected += int(_expect_integrity_error(
            lambda index=index, values=values: PaymentAttempt.objects.create(
                **_attempt_values(str(index) * 64, **values)
            ),
            f"invalid checkout-series shape {values}",
        ))
    duplicate_rejected = _expect_integrity_error(
        lambda: PaymentAttempt.objects.create(
            **_attempt_values(
                "9" * 64,
                checkout_series_key=valid.checkout_series_key,
                checkout_generation=valid.checkout_generation,
            )
        ),
        "duplicate checkout-series generation",
    )

    migration_recorded = TARGET in MigrationRecorder(resumed).applied_migrations()
    if not migration_recorded:
        raise RuntimeError("orders.0058 migration row missing")
    try:
        MigrationExecutor(resumed).migrate([PREVIOUS])
    except IrreversibleError:
        reverse_refused = True
    else:
        raise RuntimeError("orders.0058 reverse unexpectedly succeeded")
    reverse_columns_preserved = SERIES_COLUMNS.issubset(_columns(resumed))
    reverse_record_preserved = TARGET in MigrationRecorder(resumed).applied_migrations()
    if not reverse_columns_preserved or not reverse_record_preserved:
        raise RuntimeError("irreversible guard ran after destructive reverse DDL")

    result = {
        "database": database,
        "kill_exit_code": child.returncode,
        "partial_columns": partial_columns,
        "partial_migration_recorded": partial_recorded,
        "all_columns_present": SERIES_COLUMNS.issubset(_columns(resumed)),
        "engine": engine,
        "physical_defaults": physical_defaults,
        "indexes": sorted(migration.INDEX_EXPECTATIONS),
        "unique": migration.UNIQUE_NAME,
        "check": migration.CHECK_NAME,
        "check_clause": migration._normalize_check_clause(check_clause),
        "legacy_shape": list(legacy_shape),
        "invalid_shapes_rejected": rejected,
        "duplicate_generation_rejected": duplicate_rejected,
        "malformed_default_rejected": malformed_default_rejected,
        "malformed_check_rejected": malformed_check_rejected,
        "write_freeze_marker_validated": True,
        "validator_passes": 2,
        "migration_recorded": migration_recorded,
        "reverse_refused": reverse_refused,
        "reverse_columns_preserved": reverse_columns_preserved,
        "reverse_record_preserved": reverse_record_preserved,
    }
    print("CHECKOUT_S2A_0058_PROOF=" + json.dumps(result, sort_keys=True))


def main(argv=None):
    args = _arguments(argv)
    if args.phase == "kill":
        _kill_phase(args)
    else:
        _orchestrate(args)


if __name__ == "__main__":
    main()
