from django.db import migrations


TABLE_NAME = "storefront_promocodegroup"


def _table_engine(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT ENGINE FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
            [TABLE_NAME],
        )
        row = cursor.fetchone()
    return str(row[0]).upper() if row and row[0] else ""


def ensure_promocodegroup_innodb(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "mysql":
        return
    if _table_engine(connection) != "INNODB":
        table = connection.ops.quote_name(TABLE_NAME)
        schema_editor.execute(f"ALTER TABLE {table} ENGINE=InnoDB")
    engine = _table_engine(connection)
    if engine != "INNODB":
        raise RuntimeError(
            f"{TABLE_NAME} must use InnoDB for atomic promo reservations; got {engine or 'missing'}"
        )


class Migration(migrations.Migration):
    dependencies = [
        ("storefront", "0086_marketplace_feed_profiles"),
    ]

    operations = [
        migrations.RunPython(
            ensure_promocodegroup_innodb,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
