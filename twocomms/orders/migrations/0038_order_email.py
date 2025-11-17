from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0037_order_utm_campaign_order_utm_content_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='email',
            field=models.EmailField(blank=True, max_length=254, null=True, verbose_name='Email'),
        ),
    ]
