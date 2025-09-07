"""
Базовая миграция для добавления индексов производительности
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('storefront', '0018_add_database_indexes'),
    ]

    operations = [
        # Базовые индексы для товаров
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_product_featured ON storefront_product (featured);",
            reverse_sql="DROP INDEX IF EXISTS idx_product_featured;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_product_category ON storefront_product (category_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_product_category;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_product_price ON storefront_product (price);",
            reverse_sql="DROP INDEX IF EXISTS idx_product_price;"
        ),
        
        # Базовые индексы для категорий
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_category_featured ON storefront_category (is_featured);",
            reverse_sql="DROP INDEX IF EXISTS idx_category_featured;"
        ),
        
        # Базовые индексы для промокодов
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_promocode_code ON storefront_promocode (code);",
            reverse_sql="DROP INDEX IF EXISTS idx_promocode_code;"
        ),
        
        # Базовые индексы для заказов
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_order_user ON orders_order (user_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_order_user;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_order_status ON orders_order (status);",
            reverse_sql="DROP INDEX IF EXISTS idx_order_status;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_order_payment_status ON orders_order (payment_status);",
            reverse_sql="DROP INDEX IF EXISTS idx_order_payment_status;"
        ),
        
        # Базовые индексы для пользователей
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_user_staff ON auth_user (is_staff);",
            reverse_sql="DROP INDEX IF EXISTS idx_user_staff;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_user_active ON auth_user (is_active);",
            reverse_sql="DROP INDEX IF EXISTS idx_user_active;"
        ),
    ]
