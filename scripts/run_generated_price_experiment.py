#!/usr/bin/env python3
"""Run DJ6-ORM-013 against an owned, disposable MariaDB 11.4.12 schema.

The experiment never reads application ``DB_*`` settings and never accepts a
remote database. It starts an isolated native MariaDB process on loopback,
creates a random schema/user, exercises a temporary Django model, and removes
the complete namespace before exiting.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Mapping

from django.db import models
from django.db.models import Case, F, Func, Value, When
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import Cast, Coalesce


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_mariadb_gate import _native_admin
TABLE_NAME = "dj6_generated_price_probe"
INDEX_NAME = "dj6_gprice_final_idx"
CONTRACT_PRICES = (1, 99, 100, 999, 1090, 1091, 2_147_483_647)
CONTRACT_DISCOUNTS = (0, 1, 33, 100)
_SAFE_ENVIRONMENT_NAMES = {
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "TMPDIR",
    "VIRTUAL_ENV",
    "SYSTEMROOT",
}


class ExperimentError(RuntimeError):
    """A fail-closed experiment contract violation."""


class MariaDBIntegerDivision(Func):
    """Render MariaDB's truncating ``DIV`` operator for generated columns."""

    template = "(%(expressions)s)"
    arg_joiner = " DIV "
    arity = 2


def current_product_final_price(price: int, discount_percent: int | None) -> int:
    """Mirror the current ``Product.final_price`` integer contract."""
    if discount_percent and discount_percent > 0:
        return int(price * (100 - discount_percent) / 100)
    return price


def decimal_final_price(price: int, discount_percent: int | None) -> int:
    """Compute the same contract without binary floating-point arithmetic."""
    if discount_percent and discount_percent > 0:
        return int(
            Decimal(price)
            * Decimal(100 - discount_percent)
            / Decimal(100)
        )
    return price


def generated_price_expression():
    """Return the proposed persisted generated-column expression."""
    integer_numerator = ExpressionWrapper(
        F("price")
        * (
            Value(100, output_field=models.IntegerField())
            - Coalesce(
                F("discount_percent"),
                Value(0, output_field=models.IntegerField()),
                output_field=models.IntegerField(),
            )
        ),
        output_field=models.BigIntegerField(),
    )
    return MariaDBIntegerDivision(
        integer_numerator,
        Value(100, output_field=models.IntegerField()),
        output_field=models.PositiveIntegerField(),
    )


def current_catalog_annotation_expression():
    """Mirror the existing catalog price-sort SQL expression for parity proof."""
    discounted_price = Cast(
        F("price")
        * (Value(100) - F("discount_percent"))
        / Value(100),
        output_field=models.IntegerField(),
    )
    return Case(
        When(discount_percent__gt=0, then=discounted_price),
        default=F("price"),
        output_field=models.IntegerField(),
    )


def current_serializer_fallback(price: int, discount_percent: int | None) -> int:
    """Mirror ``RelatedProductSerializer.get_final_price()`` fallback math."""
    if discount_percent and discount_percent > 0:
        return int(price * (1 - discount_percent / 100))
    return price


def sanitized_native_environment(source: Mapping[str, str]) -> dict[str, str]:
    """Keep only process basics; never forward DB, DTF, provider, or app secrets."""
    environment = {
        name: value
        for name, value in source.items()
        if name in _SAFE_ENVIRONMENT_NAMES
    }
    environment["PYTHONNOUSERSITE"] = "1"
    return environment


def resolve_native_binaries(binary_dir: Path) -> dict[str, str]:
    """Resolve both required executables from one explicit directory."""
    resolved = {}
    for name in ("mariadbd", "mariadb-install-db"):
        candidate = binary_dir / name
        if not candidate.is_file() or not os.access(candidate, os.X_OK):
            raise ExperimentError(
                f"native MariaDB experiment requires executable {name} in "
                "--mariadb-bin-dir"
            )
        resolved[name] = str(candidate)
    return resolved


def validate_index_plan(row: Mapping[str, object]) -> dict[str, object]:
    """Require MariaDB to choose the generated-column index without filesort."""
    key = str(row.get("key") or "")
    access_type = str(row.get("type") or "").lower()
    extra = str(row.get("Extra") or "")
    if key != INDEX_NAME or access_type not in {"ref", "range", "index"}:
        raise ExperimentError("generated price index is not selected by EXPLAIN")
    if "filesort" in extra.casefold():
        raise ExperimentError("generated price index plan still requires filesort")
    return {
        "key": key,
        "access_type": access_type,
        "estimated_rows": int(row.get("rows") or 0),
        "extra": extra,
    }


def _generated_identifiers() -> tuple[str, str, str]:
    token = uuid.uuid4().hex[:12]
    return (
        f"test_twocomms_gprice_{token}",
        f"twc_gp_{token}",
        secrets.token_urlsafe(24),
    )


def _configure_django(
    *, database: str, username: str, password: str, host: str, port: str
) -> None:
    environment = sanitized_native_environment(os.environ)
    environment.update(
        {
            "DJANGO_SETTINGS_MODULE": "test_settings_mariadb",
            "SECRET_KEY": "disposable-generated-price-experiment",
            "TEST_MARIADB_NAME": database,
            "TEST_MARIADB_USER": username,
            "TEST_MARIADB_PASSWORD": password,
            "TEST_MARIADB_HOST": host,
            "TEST_MARIADB_PORT": str(port),
        }
    )
    os.environ.clear()
    os.environ.update(environment)
    twocomms_root = str(PROJECT_ROOT / "twocomms")
    if twocomms_root not in sys.path:
        sys.path.insert(0, twocomms_root)

    import django

    django.setup()


def _build_probe_model():
    class GeneratedPriceProbe(models.Model):
        price = models.PositiveIntegerField()
        discount_percent = models.PositiveSmallIntegerField(null=True)
        final_price_generated = models.GeneratedField(
            expression=generated_price_expression(),
            output_field=models.PositiveIntegerField(),
            db_persist=True,
        )

        class Meta:
            app_label = "generated_price_experiment"
            db_table = TABLE_NAME
            indexes = [
                models.Index(fields=["final_price_generated"], name=INDEX_NAME)
            ]

    return GeneratedPriceProbe


def _row_as_dict(cursor, row) -> dict[str, object]:
    return {
        str(description[0]): value
        for description, value in zip(cursor.description, row, strict=True)
    }


def _verify_schema(connection) -> dict[str, object]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT ENGINE FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
            [TABLE_NAME],
        )
        engine_row = cursor.fetchone()
        if not engine_row or str(engine_row[0]).casefold() != "innodb":
            raise ExperimentError("disposable generated-price table is not InnoDB")

        cursor.execute(f"SHOW CREATE TABLE `{TABLE_NAME}`")
        create_row = cursor.fetchone()
        create_sql = "" if not create_row else str(create_row[1])
        normalized = " ".join(create_sql.casefold().split())
        required_fragments = (
            "generated always as",
            "coalesce(",
            " div ",
            INDEX_NAME.casefold(),
        )
        if not all(fragment in normalized for fragment in required_fragments):
            raise ExperimentError("SHOW CREATE TABLE lacks generated-column proof")
        if "persistent" not in normalized and "stored" not in normalized:
            raise ExperimentError("generated price column is not persisted")

    return {
        "engine": "InnoDB",
        "persisted": True,
        "integer_division_expression": True,
        "index": INDEX_NAME,
    }


def _verify_parity(Probe) -> dict[str, object]:
    from storefront.models import Product

    contract_rows = [
        Probe(price=price, discount_percent=discount)
        for price in CONTRACT_PRICES
        for discount in CONTRACT_DISCOUNTS
    ]
    contract_rows.append(Probe(price=1090, discount_percent=None))
    Probe.objects.bulk_create(contract_rows)

    checked = 0
    annotation_mismatches = []
    queryset = Probe.objects.annotate(
        catalog_annotation_price=current_catalog_annotation_expression()
    ).order_by("price", "discount_percent")
    for row in queryset:
        product_value = Product(
            price=row.price,
            discount_percent=row.discount_percent,
        ).final_price
        decimal_value = decimal_final_price(row.price, row.discount_percent)
        serializer_value = current_serializer_fallback(
            row.price, row.discount_percent
        )
        values = {
            "product": int(product_value),
            "decimal": int(decimal_value),
            "serializer": int(serializer_value),
            "catalog_annotation": int(row.catalog_annotation_price),
            "generated": int(row.final_price_generated),
        }
        canonical_values = {
            values["product"],
            values["decimal"],
            values["serializer"],
            values["generated"],
        }
        if len(canonical_values) != 1:
            raise ExperimentError(
                "price parity failed for "
                f"price={row.price} discount={row.discount_percent} values={values}"
            )
        if values["catalog_annotation"] != values["generated"]:
            annotation_mismatches.append(
                {
                    "price": int(row.price),
                    "discount": row.discount_percent,
                    "catalog_annotation": values["catalog_annotation"],
                    "canonical": values["generated"],
                }
            )
        checked += 1

    return {
        "rows": checked,
        "prices": list(CONTRACT_PRICES),
        "discounts": list(CONTRACT_DISCOUNTS),
        "null_discount": "passed",
        "canonical_sources_parity": "passed",
        "legacy_catalog_annotation_parity": (
            "passed" if not annotation_mismatches else "failed"
        ),
        "legacy_catalog_annotation_mismatches": annotation_mismatches,
        "sources": [
            "Product.final_price",
            "Decimal",
            "catalog Cast annotation",
            "serializer fallback",
            "GeneratedField",
        ],
    }


def _verify_refresh_and_deferred(Probe, connection) -> dict[str, object]:
    from django.test.utils import CaptureQueriesContext

    instance = Probe.objects.create(price=1090, discount_percent=33)
    expected_before = decimal_final_price(1090, 33)
    expected_after = decimal_final_price(1100, 33)
    create_returned = int(instance.final_price_generated) == expected_before
    if not create_returned:
        raise ExperimentError("MariaDB INSERT did not return the generated field")

    instance.price = 1100
    instance.save(update_fields=["price"])
    value_after_update = int(instance.final_price_generated)
    update_returned = value_after_update == expected_after
    stale_after_update = value_after_update == expected_before
    if not (update_returned or stale_after_update):
        raise ExperimentError("generated-field update returned an unexpected value")

    instance.refresh_from_db(fields=["final_price_generated"])
    if int(instance.final_price_generated) != expected_after:
        raise ExperimentError("refresh_from_db did not load generated price")

    deferred = Probe.objects.only("id", "price").get(pk=instance.pk)
    before_access = sorted(deferred.get_deferred_fields())
    if "final_price_generated" not in before_access:
        raise ExperimentError("only() did not defer the generated price")
    with CaptureQueriesContext(connection) as queries:
        deferred_value = deferred.final_price_generated
    if int(deferred_value) != expected_after or len(queries) != 1:
        raise ExperimentError("deferred generated price did not load in one query")

    return {
        "insert_returned": True,
        "update_returned_immediately": update_returned,
        "update_instance_stale_until_refresh": stale_after_update,
        "refresh_from_db": "passed",
        "deferred_fields_before_access": before_access,
        "deferred_access_queries": len(queries),
    }


def _verify_index_plan(Probe, connection) -> dict[str, object]:
    scale_rows = [
        (10_000 + offset * 7, 33)
        for offset in range(4096)
    ]
    with connection.cursor() as cursor:
        cursor.executemany(
            f"INSERT INTO `{TABLE_NAME}` (`price`, `discount_percent`) "
            "VALUES (%s, %s)",
            scale_rows,
        )
        cursor.execute(f"ANALYZE TABLE `{TABLE_NAME}`")
        cursor.fetchall()
        cursor.execute(
            f"EXPLAIN SELECT `id` FROM `{TABLE_NAME}` "
            "WHERE `final_price_generated` BETWEEN 6700 AND 6710 "
            "ORDER BY `final_price_generated`"
        )
        range_plan = validate_index_plan(_row_as_dict(cursor, cursor.fetchone()))
        cursor.execute(
            f"EXPLAIN SELECT `id` FROM `{TABLE_NAME}` "
            "ORDER BY `final_price_generated` LIMIT 20"
        )
        order_plan = validate_index_plan(_row_as_dict(cursor, cursor.fetchone()))

    return {
        "rows_loaded": Probe.objects.count(),
        "range_filter": range_plan,
        "order_limit": order_plan,
    }


def _run_django_probe() -> dict[str, object]:
    import django
    import sys as runtime_sys
    from django.db import connection

    if runtime_sys.version_info[:3] != (3, 14, 6) or django.get_version() != "6.1":
        raise ExperimentError("experiment requires CPython 3.14.6 and Django 6.1")
    if connection.vendor != "mysql" or not connection.mysql_is_mariadb:
        raise ExperimentError("experiment requires the Django MariaDB backend")
    server_version = str(connection.mysql_server_info)
    if not server_version.startswith("11.4.12-MariaDB"):
        raise ExperimentError("experiment requires MariaDB 11.4.12")
    if not connection.features.supports_stored_generated_columns:
        raise ExperimentError("backend does not support stored generated columns")

    Probe = _build_probe_model()
    table_created = False
    try:
        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(Probe)
        table_created = True
        return {
            "runtime": {
                "python": ".".join(str(part) for part in runtime_sys.version_info[:3]),
                "django": django.get_version(),
                "mariadb": server_version,
                "insert_returning": connection.features.can_return_columns_from_insert,
            },
            "schema": _verify_schema(connection),
            "parity": _verify_parity(Probe),
            "refresh_and_deferred": _verify_refresh_and_deferred(Probe, connection),
            "index_plan": _verify_index_plan(Probe, connection),
        }
    finally:
        if table_created:
            with connection.schema_editor() as schema_editor:
                schema_editor.delete_model(Probe)
        connection.close()


def run_native_experiment(binary_dir: Path) -> dict[str, object]:
    binaries = resolve_native_binaries(binary_dir)
    source_environment = sanitized_native_environment(os.environ)
    admin = None
    database = username = password = None
    database_created = user_created = False
    cleanup_errors = []
    result = None
    primary_error = None
    try:
        admin = _native_admin(
            source_environment,
            binaries=binaries,
            project_root=PROJECT_ROOT,
        )
        version, comment = admin.server_identity()
        if not version.startswith("11.4.12-MariaDB"):
            raise ExperimentError("native server must be MariaDB 11.4.12")
        database, username, password = _generated_identifiers()
        admin.ensure_namespace_absent(database, username)
        admin.create_database(database)
        database_created = True
        admin.create_user(username, password)
        user_created = True
        admin.grant_schema(username, database)
        _configure_django(
            database=database,
            username=username,
            password=password,
            host=admin.host,
            port=admin.port,
        )
        result = _run_django_probe()
        legacy_annotation_ok = (
            result["parity"]["legacy_catalog_annotation_parity"] == "passed"
        )
        result.update(
            {
                "status": "passed",
                "decision": (
                    "GO for migration design; NO production DDL in this change"
                    if legacy_annotation_ok
                    else "NO-GO for production adoption: legacy catalog annotation diverges"
                ),
                "server_comment": comment,
            }
        )
    except BaseException as exc:
        primary_error = exc
    finally:
        if admin is not None:
            if user_created:
                try:
                    admin.drop_user(username)
                except BaseException as exc:
                    cleanup_errors.append(exc)
            if database_created:
                try:
                    admin.drop_database(database)
                except BaseException as exc:
                    cleanup_errors.append(exc)
            if database and username and not cleanup_errors:
                try:
                    user_exists, database_exists = admin.verify_cleanup(
                        database, username
                    )
                    if user_exists or database_exists:
                        cleanup_errors.append(
                            ExperimentError("disposable namespace cleanup was incomplete")
                        )
                except BaseException as exc:
                    cleanup_errors.append(exc)
            try:
                admin.close()
            except BaseException as exc:
                cleanup_errors.append(exc)

    if primary_error is not None:
        raise ExperimentError("generated price experiment failed") from primary_error
    if cleanup_errors:
        raise ExperimentError("generated price experiment cleanup failed") from cleanup_errors[0]
    if result is None:
        raise ExperimentError("generated price experiment produced no result")
    result["cleanup"] = "schema+user+datadir removed"
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mariadb-bin-dir",
        type=Path,
        required=True,
        help="Directory containing MariaDB 11.4.12 mariadbd and mariadb-install-db",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        result = run_native_experiment(args.mariadb_bin_dir)
    except ExperimentError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
