import json

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from management.services.ig_engine_health import (
    IG_RUNTIME_TABLES,
    model_table_by_name,
    runtime_table_gaps,
    select_for_update_sites,
)


class Command(BaseCommand):
    help = (
        "Read-only audit of transactional storage engines for IG runtime tables. "
        "Candidate set выводится из Django model metadata, поэтому отчёт не может "
        "быть формально зелёным из-за таблицы, забытой в константе."
    )

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", dest="as_json")
        parser.add_argument(
            "--fail-on-gap",
            action="store_true",
            help="Ненулевой код возврата, если найден не-InnoDB или пробел в константе.",
        )

    def handle(self, *args, **options):
        gaps = runtime_table_gaps()
        lock_sites = select_for_update_sites()
        table_by_model = model_table_by_name()
        # `lock contract` опирается на найденные места вызова `select_for_update`,
        # а не на предположение: иначе колонка ничего не доказывает.
        locked_tables = {}
        for model_name, files in lock_sites.items():
            table = table_by_model.get(model_name)
            if table:
                locked_tables[table] = files

        rows = []
        if connection.vendor == "mysql":
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES "
                    "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ("
                    + ",".join(["%s"] * len(IG_RUNTIME_TABLES))
                    + ") ORDER BY TABLE_NAME",
                    list(IG_RUNTIME_TABLES),
                )
                actual = {name: engine for name, engine in cursor.fetchall()}
            for table in IG_RUNTIME_TABLES:
                engine = actual.get(table, "missing")
                rows.append({
                    "table": table,
                    "engine": engine,
                    "used_by": list(locked_tables.get(table, ())),
                    "lock_contract": "row_lock" if table in locked_tables else "none_found",
                    "healthy": str(engine).lower() == "innodb",
                })
        else:
            for table in IG_RUNTIME_TABLES:
                rows.append({
                    "table": table,
                    "engine": connection.vendor,
                    "used_by": list(locked_tables.get(table, ())),
                    "lock_contract": "row_lock" if table in locked_tables else "none_found",
                    "healthy": True,
                })

        unhealthy = [row for row in rows if not row["healthy"]]
        report = {
            "read_only": True,
            "vendor": connection.vendor,
            "required_engine": "InnoDB" if connection.vendor == "mysql" else connection.vendor,
            "table_count": len(rows),
            "unhealthy_count": len(unhealthy),
            "locked_table_count": len(locked_tables),
            "completeness": gaps,
            "lock_scan_note": (
                "Статический скан выражений Model.objects...select_for_update(); "
                "косвенные пути через переменные он не покрывает."
            ),
            "tables": rows,
        }
        if options["as_json"]:
            self.stdout.write(json.dumps(report, ensure_ascii=False, sort_keys=True))
        else:
            self.stdout.write(f"vendor          : {report['vendor']}")
            self.stdout.write(f"required engine : {report['required_engine']}")
            self.stdout.write(f"tables audited  : {report['table_count']}")
            self.stdout.write(f"non-InnoDB      : {report['unhealthy_count']}")
            self.stdout.write(
                "completeness    : candidates="
                f"{gaps['candidate_count']} declared={gaps['declared_count']} "
                f"missing={len(gaps['missing_from_constant'])} "
                f"unknown={len(gaps['declared_but_unknown'])}"
            )
            if gaps["missing_from_constant"]:
                self.stdout.write(
                    "  missing from constant: "
                    + ", ".join(gaps["missing_from_constant"])
                )
            if gaps["declared_but_unknown"]:
                self.stdout.write(
                    "  declared but not a model table: "
                    + ", ".join(gaps["declared_but_unknown"])
                )
            self.stdout.write(
                f"row-locked      : {report['locked_table_count']} tables with a "
                "found select_for_update site"
            )
            for row in unhealthy:
                self.stdout.write(
                    f"  UNHEALTHY {row['table']}: engine={row['engine']} "
                    f"lock={row['lock_contract']}"
                )
            if not unhealthy:
                self.stdout.write("all audited tables satisfy the engine contract")

        if options["fail_on_gap"] and (
            unhealthy or gaps["missing_from_constant"] or gaps["declared_but_unknown"]
        ):
            raise CommandError(
                "engine audit found a non-InnoDB table or an incomplete table list"
            )
