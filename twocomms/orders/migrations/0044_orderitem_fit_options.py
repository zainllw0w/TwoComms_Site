from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0043_dropshipperorder_client_np_city_ref_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderitem',
            name='fit_option_code',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
        migrations.AddField(
            model_name='orderitem',
            name='fit_option_label',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='dropshipperorderitem',
            name='fit_option_code',
            field=models.CharField(blank=True, default='', max_length=50, verbose_name='Код посадки'),
        ),
        migrations.AddField(
            model_name='dropshipperorderitem',
            name='fit_option_label',
            field=models.CharField(blank=True, default='', max_length=100, verbose_name='Посадка'),
        ),
    ]
