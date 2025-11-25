from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('storefront', '0035_alter_product_price'),
    ]

    operations = [
        migrations.AddField(
            model_name='productimage',
            name='order',
            field=models.IntegerField(db_index=True, default=0),
        ),
        migrations.AlterModelOptions(
            name='productimage',
            options={'ordering': ['order', 'id']},
        ),
    ]
