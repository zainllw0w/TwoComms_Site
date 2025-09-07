# Generated manually for performance optimization

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('storefront', '0011_category_description_category_is_active_and_more'),
    ]

    operations = [
        # Индексы для Product
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_product_featured ON storefront_product (featured);",
            reverse_sql="DROP INDEX IF EXISTS idx_product_featured;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_product_category ON storefront_product (category_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_product_category;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_product_created ON storefront_product (id DESC);",
            reverse_sql="DROP INDEX IF EXISTS idx_product_created;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_product_price ON storefront_product (price);",
            reverse_sql="DROP INDEX IF EXISTS idx_product_price;"
        ),
        
        # Индексы для Category
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_category_order ON storefront_category (`order`, name);",
            reverse_sql="DROP INDEX IF EXISTS idx_category_order;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_category_active ON storefront_category (is_active);",
            reverse_sql="DROP INDEX IF EXISTS idx_category_active;"
        ),
        
        # Индексы для PromoCode
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_promocode_code ON storefront_promocode (code);",
            reverse_sql="DROP INDEX IF EXISTS idx_promocode_code;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_promocode_active ON storefront_promocode (is_active);",
            reverse_sql="DROP INDEX IF EXISTS idx_promocode_active;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_promocode_created ON storefront_promocode (created_at DESC);",
            reverse_sql="DROP INDEX IF EXISTS idx_promocode_created;"
        ),
    ]
