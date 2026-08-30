from django.db import migrations


GEMINI_ACCOUNTING_TABLES = (
    "management_geminiquotaprofile",
    "management_geminiquotastate",
    "management_geminirequest",
    "management_geminirequestattempt",
    "management_geminimodelquotausage",
)


def ensure_gemini_accounting_tables_innodb(apps, schema_editor):
    """Idempotently converge every V2 lock participant after schema/seed."""
    if schema_editor.connection.vendor != "mysql":
        return
    with schema_editor.connection.cursor() as cursor:
        for table in GEMINI_ACCOUNTING_TABLES:
            cursor.execute(
                "SELECT ENGINE FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
                [table],
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError(
                    f"required Gemini accounting table is missing: {table}"
                )
            if str(row[0] or "").upper() != "INNODB":
                schema_editor.execute(
                    f"ALTER TABLE {schema_editor.quote_name(table)} ENGINE=InnoDB"
                )


class Migration(migrations.Migration):
    # ALTER TABLE issues an implicit commit on MariaDB. Keep it out of the
    # atomic schema/profile migration so a failed engine conversion is visible
    # and safely retryable: completed ALTERs are skipped on the next run.
    atomic = False

    dependencies = [
        ("management", "0180_seed_gemini_quota_profiles"),
    ]

    operations = [
        migrations.RunPython(
            ensure_gemini_accounting_tables_innodb,
            migrations.RunPython.noop,
        ),
    ]
