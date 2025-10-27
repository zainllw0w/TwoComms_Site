# Generated manually for promo codes system redesign
# Adds PromoCodeGroup, PromoCodeUsage models and extends PromoCode

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('orders', '0035_dropshipperorder_monobank_invoice_id'),
        ('storefront', '0030_add_performance_indexes'),
    ]

    operations = [
        # 1. Создаем модель PromoCodeGroup
        migrations.CreateModel(
            name='PromoCodeGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Назва групи')),
                ('description', models.TextField(blank=True, null=True, verbose_name='Опис групи')),
                ('one_per_account', models.BooleanField(default=True, verbose_name='Один промокод на акаунт з групи')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активна')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Створено')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Оновлено')),
            ],
            options={
                'verbose_name': 'Група промокодів',
                'verbose_name_plural': 'Групи промокодів',
                'ordering': ['-created_at'],
            },
        ),
        
        # 2. Добавляем новые поля в PromoCode
        migrations.AddField(
            model_name='promocode',
            name='promo_type',
            field=models.CharField(
                choices=[
                    ('regular', 'Звичайний промокод'),
                    ('voucher', 'Ваучер (фіксована сума)'),
                    ('grouped', 'Груповий промокод')
                ],
                default='regular',
                max_length=10,
                verbose_name='Тип промокоду'
            ),
        ),
        migrations.AddField(
            model_name='promocode',
            name='description',
            field=models.TextField(blank=True, null=True, verbose_name='Опис'),
        ),
        migrations.AddField(
            model_name='promocode',
            name='one_time_per_user',
            field=models.BooleanField(default=False, verbose_name='Одноразове використання на користувача'),
        ),
        migrations.AddField(
            model_name='promocode',
            name='min_order_amount',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=10,
                null=True,
                verbose_name='Мінімальна сума замовлення'
            ),
        ),
        migrations.AddField(
            model_name='promocode',
            name='valid_from',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Дійсний з'),
        ),
        migrations.AddField(
            model_name='promocode',
            name='valid_until',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Дійсний до'),
        ),
        
        # 3. Добавляем FK на группу в PromoCode
        migrations.AddField(
            model_name='promocode',
            name='group',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='promo_codes',
                to='storefront.promocodegroup',
                verbose_name='Група'
            ),
        ),
        
        # 4. Создаем модель PromoCodeUsage
        migrations.CreateModel(
            name='PromoCodeUsage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('used_at', models.DateTimeField(auto_now_add=True, verbose_name='Використано')),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='promo_usages',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Користувач'
                )),
                ('promo_code', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='usages',
                    to='storefront.promocode',
                    verbose_name='Промокод'
                )),
                ('group', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='usages',
                    to='storefront.promocodegroup',
                    verbose_name='Група'
                )),
                ('order', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='promo_usages',
                    to='orders.order',
                    verbose_name='Замовлення'
                )),
            ],
            options={
                'verbose_name': 'Використання промокоду',
                'verbose_name_plural': 'Використання промокодів',
                'ordering': ['-used_at'],
            },
        ),
        
        # 5. Добавляем индексы
        migrations.AddIndex(
            model_name='promocodegroup',
            index=models.Index(fields=['is_active', '-created_at'], name='idx_group_active_created'),
        ),
        migrations.AddIndex(
            model_name='promocode',
            index=models.Index(fields=['group', 'is_active'], name='idx_promo_group_active'),
        ),
        migrations.AddIndex(
            model_name='promocode',
            index=models.Index(fields=['promo_type', 'is_active'], name='idx_promo_type_active'),
        ),
        migrations.AddIndex(
            model_name='promocode',
            index=models.Index(fields=['code'], name='idx_promo_code'),
        ),
        migrations.AddIndex(
            model_name='promocodeusage',
            index=models.Index(fields=['user', 'promo_code'], name='idx_usage_user_promo'),
        ),
        migrations.AddIndex(
            model_name='promocodeusage',
            index=models.Index(fields=['user', 'group'], name='idx_usage_user_group'),
        ),
        migrations.AddIndex(
            model_name='promocodeusage',
            index=models.Index(fields=['-used_at'], name='idx_usage_date'),
        ),
    ]

