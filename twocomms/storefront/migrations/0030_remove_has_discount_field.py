# Generated manually for optimization
# Removes unused has_discount field (replaced by @property)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('storefront', '0029_product_idx_product_id_desc'),
    ]

    operations = [
        # Note: This field was not actually in the database as it was overridden by @property
        # This migration is a no-op to keep track of the model change
        # migrations.RemoveField(
        #     model_name='product',
        #     name='has_discount',
        # ),
    ]

