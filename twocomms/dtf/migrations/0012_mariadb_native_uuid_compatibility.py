from django.db import migrations


TABLE_NAME = "dtf_dtfbuildersession"
COLUMN_NAME = "session_id"
UUID_TEXT_PATTERN = (
    "^([0-9A-Fa-f]{32}|"
    "[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-"
    "[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12})$"
)


def _is_dtf_mariadb(connection):
    return (
        connection.alias == "dtf"
        and connection.vendor == "mysql"
        and bool(getattr(connection, "mysql_is_mariadb", False))
    )


def _column_metadata(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE "
            "FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s",
            [TABLE_NAME, COLUMN_NAME],
        )
        row = cursor.fetchone()
    if row is None:
        raise RuntimeError(f"required UUID column is missing: {TABLE_NAME}.{COLUMN_NAME}")
    return str(row[0]).lower(), row[1], str(row[2]).upper()


def _invalid_uuid_value_count(connection):
    quote = connection.ops.quote_name
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT COUNT(*) FROM {quote(TABLE_NAME)} "
            f"WHERE {quote(COLUMN_NAME)} IS NOT NULL "
            f"AND CAST({quote(COLUMN_NAME)} AS CHAR) NOT REGEXP %s",
            [UUID_TEXT_PATTERN],
        )
        return int(cursor.fetchone()[0])


def convert_legacy_dtf_uuid_column(apps, schema_editor):
    connection = schema_editor.connection
    if not _is_dtf_mariadb(connection):
        return

    data_type, max_length, nullable = _column_metadata(connection)
    if data_type == "uuid":
        return
    if data_type != "char" or int(max_length or 0) != 32:
        raise RuntimeError(
            "unexpected DTF session UUID column type: "
            f"{data_type}({max_length})"
        )
    invalid_rows = _invalid_uuid_value_count(connection)
    if invalid_rows:
        raise RuntimeError(f"invalid DTF session UUID values: {invalid_rows} row(s)")

    quote = connection.ops.quote_name
    null_sql = "NULL" if nullable == "YES" else "NOT NULL"
    schema_editor.execute(
        f"ALTER TABLE {quote(TABLE_NAME)} "
        f"MODIFY COLUMN {quote(COLUMN_NAME)} UUID {null_sql}"
    )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("dtf", "0011_alter_dtforder_order_type"),
    ]

    operations = [
        migrations.RunPython(
            convert_legacy_dtf_uuid_column,
            migrations.RunPython.noop,
        ),
    ]
