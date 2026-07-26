from importlib import import_module

from django.db import migrations


episode_migration = import_module(
    "management.migrations.0106_ig_commercial_episodes"
)


class Migration(migrations.Migration):
    """Data/trigger rollout is separate from MariaDB auto-committed schema DDL.

    If historical validation fails, rerunning this migration never attempts to
    recreate the already committed columns, tables, indexes, or constraints.
    """

    atomic = False

    dependencies = [
        ("management", "0106_ig_commercial_episodes"),
    ]

    operations = [
        migrations.RunPython(
            episode_migration.backfill_until_quiescent,
            episode_migration.noop_backfill,
        ),
        migrations.RunPython(
            episode_migration.create_append_only_triggers,
            episode_migration.drop_append_only_triggers,
        ),
    ]
