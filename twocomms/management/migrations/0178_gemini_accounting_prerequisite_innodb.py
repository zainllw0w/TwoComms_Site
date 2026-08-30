from django.db import migrations


# These existing tables participate in the first V2 foreign keys. They must be
# transactional before the next migration attempts any FK DDL.
PREREQUISITE_TABLES = (
    "management_geminirequestattempt",
    "management_geminimodelquotausage",
)


def ensure_prerequisite_tables_innodb(apps, schema_editor):
    """Idempotently converge legacy lock participants before V2 FK creation.

    MariaDB ``ALTER TABLE`` implicitly commits. If deployment is interrupted
    after one table, Django does not record this migration; a retry is safe
    because already-converted tables are detected and skipped.
    """
    if schema_editor.connection.vendor != "mysql":
        return
    with schema_editor.connection.cursor() as cursor:
        for table in PREREQUISITE_TABLES:
            cursor.execute(
                "SELECT ENGINE FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
                [table],
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError(
                    f"required Gemini accounting prerequisite is missing: {table}"
                )
            if str(row[0] or "").upper() != "INNODB":
                schema_editor.execute(
                    f"ALTER TABLE {schema_editor.quote_name(table)} ENGINE=InnoDB"
                )


class Migration(migrations.Migration):
    # MariaDB ALTER TABLE implicitly commits. This migration contains no state
    # or FK DDL and is deliberately retry-idempotent.
    atomic = False

    dependencies = [
        ("management", "0177_gemini_adaptive_routing"),
    ]

    operations = [
        migrations.RunPython(
            ensure_prerequisite_tables_innodb,
            migrations.RunPython.noop,
        ),
    ]
