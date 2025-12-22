from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('management', '0015_managerpayoutrequest_payoutrejectionreasonrequest_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='managercommissionaccrual',
            name='note',
            field=models.CharField(blank=True, max_length=255, verbose_name='Пояснення'),
        ),
    ]
