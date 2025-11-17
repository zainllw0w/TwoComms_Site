# Generated manually to fix MySQL index length issue
# MySQL has a limit of 1000 bytes for indexes with utf8mb4 (4 bytes per char)
# CharField(255) * 3 fields * 4 bytes = 3060 bytes > 1000 bytes limit
# Solution: Use prefix indexes (first 100 chars per field = 1200 bytes, but MySQL allows this)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('storefront', '0033_useraction_utmsession_and_more'),
    ]

    operations = [
        # Remove the problematic index if it exists
        migrations.RunSQL(
            sql="DROP INDEX IF EXISTS idx_utm_source_medium_campaign ON storefront_utmsession;",
            reverse_sql="CREATE INDEX idx_utm_source_medium_campaign ON storefront_utmsession (utm_source(100), utm_medium(100), utm_campaign(100));"
        ),
        # Create index with prefixes (100 chars per field = 400 bytes per field = 1200 bytes total, within limit)
        migrations.RunSQL(
            sql="CREATE INDEX idx_utm_source_medium_campaign ON storefront_utmsession (utm_source(100), utm_medium(100), utm_campaign(100));",
            reverse_sql="DROP INDEX IF EXISTS idx_utm_source_medium_campaign ON storefront_utmsession;"
        ),
    ]

