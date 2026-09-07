"""Converge legacy transaction participants without rewriting application data."""
from django.db import migrations


TABLES = (
    "management_botdatadeletionrequest",
    "management_botinstruction",
    "management_botpolicypublication",
    "management_adminauditlog",
)
# Avoid unexpectedly copying a large legacy audit table during a live deploy.
MAX_CONVERSION_BYTES = 16 * 1024 * 1024


def ensure_transaction_engines(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT @@SESSION.lock_wait_timeout")
        original_timeout = int(cursor.fetchone()[0])
        try:
            cursor.execute("SET SESSION lock_wait_timeout = 10")
            for table in TABLES:
                cursor.execute(
                    "SELECT ENGINE, COALESCE(DATA_LENGTH, 0) + COALESCE(INDEX_LENGTH, 0) "
                    "FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",
                    [table],
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError(f"Required transaction participant missing: {table}")
                if str(row[0]).casefold() == "innodb":
                    continue
                if int(row[1]) > MAX_CONVERSION_BYTES:
                    raise RuntimeError(f"Transaction engine conversion needs size review: {table}")
                schema_editor.execute(
                    f"ALTER TABLE {schema_editor.quote_name(table)} ENGINE=InnoDB"
                )
                cursor.execute(
                    "SELECT ENGINE FROM information_schema.TABLES "
                    "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s", [table],
                )
                if str(cursor.fetchone()[0]).casefold() != "innodb":
                    raise RuntimeError(f"Transaction engine conversion unconfirmed: {table}")
        finally:
            cursor.execute("SET SESSION lock_wait_timeout = %s", [original_timeout])


class Migration(migrations.Migration):
    # MariaDB DDL implicitly commits; retries skip every converted table.
    atomic = False
    dependencies = [("management", "0200_revision_effect_projection")]
    operations = [
        migrations.RunPython(ensure_transaction_engines, migrations.RunPython.noop),
    ]
