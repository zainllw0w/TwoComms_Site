# Generated manually for performance optimization
# Adds database indexes for frequently queried fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('storefront', '0029_product_idx_product_id_desc'),
    ]

    operations = [
        # Category indexes
        migrations.AddIndex(
            model_name='category',
            index=models.Index(fields=['is_active'], name='idx_category_active'),
        ),
        migrations.AddIndex(
            model_name='category',
            index=models.Index(fields=['is_featured'], name='idx_category_featured'),
        ),
        migrations.AddIndex(
            model_name='category',
            index=models.Index(fields=['order'], name='idx_category_order'),
        ),
        
        # Product indexes
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['featured'], name='idx_product_featured'),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['is_dropship_available'], name='idx_product_dropship'),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['category', '-id'], name='idx_product_category_id'),
        ),
        
        # PromoCode indexes
        migrations.AddIndex(
            model_name='promocode',
            index=models.Index(fields=['is_active', '-created_at'], name='idx_promo_active_created'),
        ),
        
        # OfflineStore indexes
        migrations.AddIndex(
            model_name='offlinestore',
            index=models.Index(fields=['is_active', 'order'], name='idx_store_active_order'),
        ),
        
        # SiteSession indexes
        migrations.AddIndex(
            model_name='sitesession',
            index=models.Index(fields=['is_bot', '-last_seen'], name='idx_session_bot_seen'),
        ),
        
        # PageView indexes
        migrations.AddIndex(
            model_name='pageview',
            index=models.Index(fields=['is_bot', '-when'], name='idx_pageview_bot_when'),
        ),
    ]

