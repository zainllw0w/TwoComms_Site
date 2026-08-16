from django.db import migrations


LEGACY_UUID_COLUMNS = (
    ("dtf_dtfbuildersession", "session_id"),
    ("storefront_pushnotificationdelivery", "event_token"),
    ("management_commercialofferemaillog", "track_token"),
    ("warehouse_writeoffrequest", "token"),
)

WAREHOUSE_TABLES = (
    "warehouse_consumablecategory",
    "warehouse_consumableitem",
    "warehouse_print",
    "warehouse_print_default_products",
    "warehouse_print_garment_colors",
    "warehouse_printcategory",
    "warehouse_printcolorvariant",
    "warehouse_printcolorvariant_colors",
    "warehouse_stockitem",
    "warehouse_stockmovement",
    "warehouse_storagecategory",
    "warehouse_storagesubcategory",
    "warehouse_storagesubcategory_colors",
    "warehouse_warehousesettings",
    "warehouse_writeoffrequest",
)

_UUID_TEXT_PATTERN = (
    "^([0-9A-Fa-f]{32}|"
    "[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-"
    "[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12})$"
)


def _is_mariadb(connection):
    return connection.vendor == "mysql" and bool(
        getattr(connection, "mysql_is_mariadb", False)
    )


def _uuid_column_metadata(connection, table_name, column_name):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE "
            "FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s",
            [table_name, column_name],
        )
        row = cursor.fetchone()
    if row is None:
        raise RuntimeError(
            f"required UUID column is missing: {table_name}.{column_name}"
        )
    return str(row[0]).lower(), row[1], str(row[2]).upper()


def _invalid_uuid_value_count(connection, table_name, column_name):
    quote = connection.ops.quote_name
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT COUNT(*) FROM {quote(table_name)} "
            f"WHERE {quote(column_name)} IS NOT NULL "
            f"AND CAST({quote(column_name)} AS CHAR) NOT REGEXP %s",
            [_UUID_TEXT_PATTERN],
        )
        return int(cursor.fetchone()[0])


def _prepare_uuid_conversion(connection):
    if not _is_mariadb(connection):
        return []

    planned = []
    for table_name, column_name in LEGACY_UUID_COLUMNS:
        data_type, max_length, nullable = _uuid_column_metadata(
            connection,
            table_name,
            column_name,
        )
        if data_type == "uuid":
            continue
        if data_type != "char" or int(max_length or 0) != 32:
            raise RuntimeError(
                "unexpected legacy UUID column type: "
                f"{table_name}.{column_name} is {data_type}({max_length})"
            )
        invalid_rows = _invalid_uuid_value_count(
            connection,
            table_name,
            column_name,
        )
        if invalid_rows:
            raise RuntimeError(
                "invalid legacy UUID values: "
                f"{table_name}.{column_name} has {invalid_rows} invalid row(s)"
            )
        planned.append((table_name, column_name, nullable))
    return planned


def _apply_uuid_conversion(schema_editor, planned):
    quote = schema_editor.connection.ops.quote_name
    for table_name, column_name, nullable in planned:
        null_sql = "NULL" if nullable == "YES" else "NOT NULL"
        schema_editor.execute(
            f"ALTER TABLE {quote(table_name)} "
            f"MODIFY COLUMN {quote(column_name)} UUID {null_sql}"
        )


def convert_legacy_mariadb_uuid_column(schema_editor, table_name, column_name):
    connection = schema_editor.connection
    if not _is_mariadb(connection):
        return
    metadata = _uuid_column_metadata(connection, table_name, column_name)
    data_type, max_length, nullable = metadata
    if data_type == "uuid":
        return
    if data_type != "char" or int(max_length or 0) != 32:
        raise RuntimeError(
            "unexpected legacy UUID column type: "
            f"{table_name}.{column_name} is {data_type}({max_length})"
        )
    invalid_rows = _invalid_uuid_value_count(connection, table_name, column_name)
    if invalid_rows:
        raise RuntimeError(
            "invalid legacy UUID values: "
            f"{table_name}.{column_name} has {invalid_rows} invalid row(s)"
        )
    _apply_uuid_conversion(schema_editor, [(table_name, column_name, nullable)])


def convert_legacy_mariadb_uuid_columns(apps, schema_editor):
    planned = _prepare_uuid_conversion(schema_editor.connection)
    _apply_uuid_conversion(schema_editor, planned)


def _table_engine(connection, table_name):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT ENGINE FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",
            [table_name],
        )
        row = cursor.fetchone()
    if row is None:
        raise RuntimeError(f"required warehouse table is missing: {table_name}")
    return str(row[0] or "").lower()


def _prepare_warehouse_engine_conversion(connection):
    if connection.vendor != "mysql":
        return []
    return [
        table_name
        for table_name in WAREHOUSE_TABLES
        if _table_engine(connection, table_name) != "innodb"
    ]


def ensure_table_innodb(schema_editor, table_name):
    connection = schema_editor.connection
    if connection.vendor != "mysql":
        return
    if _table_engine(connection, table_name) != "innodb":
        quote = connection.ops.quote_name
        schema_editor.execute(f"ALTER TABLE {quote(table_name)} ENGINE=InnoDB")
    engine = _table_engine(connection, table_name)
    if engine != "innodb":
        raise RuntimeError(
            f"{table_name} must use InnoDB for transactional writes; got {engine}"
        )


def _apply_warehouse_engine_conversion(schema_editor, planned):
    for table_name in planned:
        ensure_table_innodb(schema_editor, table_name)


def ensure_warehouse_tables_innodb(apps, schema_editor):
    planned = _prepare_warehouse_engine_conversion(schema_editor.connection)
    _apply_warehouse_engine_conversion(schema_editor, planned)


def repair_mariadb_physical_schema(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "mysql":
        return

    # Complete every read-only preflight before the first non-atomic ALTER.
    uuid_plan = _prepare_uuid_conversion(connection)
    engine_plan = _prepare_warehouse_engine_conversion(connection)
    _apply_warehouse_engine_conversion(schema_editor, engine_plan)
    _apply_uuid_conversion(schema_editor, uuid_plan)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("dtf", "0004_dtfsamplelead_alter_dtforder_length_source_and_more"),
        ("management", "0039_commercialofferemaillog_click_count_and_more"),
        ("storefront", "0045_pushnotificationcampaign_webpushdevicesubscription_and_more"),
        ("warehouse", "0011_alter_stockmovement_reason"),
    ]

    operations = [
        migrations.RunPython(
            repair_mariadb_physical_schema,
            migrations.RunPython.noop,
        ),
    ]
