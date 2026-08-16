import importlib

from django.db import migrations


_REAL_MIGRATION = importlib.import_module(
    "warehouse.migrations.0012_mariadb_native_uuid_compatibility"
)
NON_DTF_UUID_COLUMNS = tuple(
    item
    for item in _REAL_MIGRATION.LEGACY_UUID_COLUMNS
    if not item[0].casefold().startswith("dtf_")
)
WAREHOUSE_TABLES = _REAL_MIGRATION.WAREHOUSE_TABLES


def repair_non_dtf_mariadb_physical_schema(apps, schema_editor):
    original_uuid_columns = _REAL_MIGRATION.LEGACY_UUID_COLUMNS
    _REAL_MIGRATION.LEGACY_UUID_COLUMNS = NON_DTF_UUID_COLUMNS
    try:
        _REAL_MIGRATION.repair_mariadb_physical_schema(apps, schema_editor)
    finally:
        _REAL_MIGRATION.LEGACY_UUID_COLUMNS = original_uuid_columns


class Migration(migrations.Migration):
    atomic = False
    dependencies = [
        ("management", "0039_commercialofferemaillog_click_count_and_more"),
        ("storefront", "0045_pushnotificationcampaign_webpushdevicesubscription_and_more"),
        ("warehouse", "0011_alter_stockmovement_reason"),
    ]
    operations = [
        migrations.RunPython(
            repair_non_dtf_mariadb_physical_schema,
            migrations.RunPython.noop,
        )
    ]
