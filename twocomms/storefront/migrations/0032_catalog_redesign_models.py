from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('storefront', '0031_promo_codes_redesign'),
    ]

    operations = [
        migrations.CreateModel(
            name='Catalog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Назва каталогу')),
                ('slug', models.SlugField(unique=True, verbose_name='URL slug')),
                ('description', models.TextField(blank=True, verbose_name='Опис каталогу')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='Порядок')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активний')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Створено')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Оновлено')),
            ],
            options={
                'verbose_name': 'Каталог',
                'verbose_name_plural': 'Каталоги',
                'ordering': ['order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='CatalogOption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Назва опції')),
                ('option_type', models.CharField(choices=[('size', 'Розмір'), ('material', 'Матеріал'), ('color', 'Колір'), ('custom', 'Кастомна опція')], default='custom', max_length=50, verbose_name='Тип опції')),
                ('is_required', models.BooleanField(default=True, verbose_name="Обов'язкова")),
                ('is_additional_cost', models.BooleanField(default=False, verbose_name='Додаткова вартість')),
                ('additional_cost', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name='Додаткова ціна (грн)')),
                ('help_text', models.CharField(blank=True, max_length=255, verbose_name='Підказка')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='Порядок')),
                ('catalog', models.ForeignKey(on_delete=models.CASCADE, related_name='options', to='storefront.catalog', verbose_name='Каталог')),
            ],
            options={
                'verbose_name': 'Опція каталогу',
                'verbose_name_plural': 'Опції каталогу',
                'ordering': ['order', 'id'],
            },
        ),
        migrations.CreateModel(
            name='SizeGrid',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Назва сітки розмірів')),
                ('image', models.ImageField(blank=True, null=True, upload_to='size_grids/', verbose_name='Зображення сітки розмірів')),
                ('description', models.TextField(blank=True, verbose_name='Опис сітки')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активна')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='Порядок')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Створено')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Оновлено')),
                ('catalog', models.ForeignKey(on_delete=models.CASCADE, related_name='size_grids', to='storefront.catalog', verbose_name='Каталог')),
            ],
            options={
                'verbose_name': 'Сітка розмірів',
                'verbose_name_plural': 'Сітки розмірів',
                'ordering': ['order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='CatalogOptionValue',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.CharField(max_length=200, verbose_name='Значення')),
                ('display_name', models.CharField(max_length=200, verbose_name='Назва для відображення')),
                ('image', models.ImageField(blank=True, null=True, upload_to='catalog_options/', verbose_name='Зображення')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='Порядок')),
                ('is_default', models.BooleanField(default=False, verbose_name='За замовчуванням')),
                ('metadata', models.JSONField(blank=True, default=dict, verbose_name='Додаткові дані')),
                ('option', models.ForeignKey(on_delete=models.CASCADE, related_name='values', to='storefront.catalogoption', verbose_name='Опція')),
            ],
            options={
                'verbose_name': 'Значення опції',
                'verbose_name_plural': 'Значення опцій',
                'ordering': ['order', 'id'],
            },
        ),
        migrations.AddField(
            model_name='product',
            name='catalog',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.PROTECT, related_name='products', to='storefront.catalog', verbose_name='Каталог'),
        ),
        migrations.AddField(
            model_name='product',
            name='full_description',
            field=models.TextField(blank=True, verbose_name='Повний опис'),
        ),
        migrations.AddField(
            model_name='product',
            name='last_reviewed_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Остання модерація'),
        ),
        migrations.AddField(
            model_name='product',
            name='priority',
            field=models.PositiveIntegerField(default=0, verbose_name='Пріоритет показу'),
        ),
        migrations.AddField(
            model_name='product',
            name='published_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Опубліковано'),
        ),
        migrations.AddField(
            model_name='product',
            name='recommendation_tags',
            field=models.JSONField(blank=True, default=list, verbose_name='Теги рекомендацій'),
        ),
        migrations.AddField(
            model_name='product',
            name='seo_description',
            field=models.CharField(blank=True, max_length=320, verbose_name='SEO Description'),
        ),
        migrations.AddField(
            model_name='product',
            name='seo_keywords',
            field=models.CharField(blank=True, max_length=300, verbose_name='SEO ключові слова'),
        ),
        migrations.AddField(
            model_name='product',
            name='seo_schema',
            field=models.JSONField(blank=True, default=dict, verbose_name='Structured data'),
        ),
        migrations.AddField(
            model_name='product',
            name='seo_title',
            field=models.CharField(blank=True, max_length=160, verbose_name='SEO Title'),
        ),
        migrations.AddField(
            model_name='product',
            name='short_description',
            field=models.CharField(blank=True, max_length=300, verbose_name='Короткий опис'),
        ),
        migrations.AddField(
            model_name='product',
            name='size_grid',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='products', to='storefront.sizegrid', verbose_name='Сітка розмірів'),
        ),
        migrations.AddField(
            model_name='product',
            name='status',
            field=models.CharField(choices=[('draft', 'Чернетка'), ('review', 'На модерації'), ('scheduled', 'Заплановано'), ('published', 'Опубліковано'), ('archived', 'Архів')], default='draft', max_length=20, verbose_name='Статус публікації'),
        ),
        migrations.AddField(
            model_name='product',
            name='unpublished_reason',
            field=models.CharField(blank=True, max_length=200, verbose_name='Причина відключення'),
        ),
        migrations.AlterField(
            model_name='product',
            name='price',
            field=models.PositiveIntegerField(verbose_name='Ціна (грн)'),
        ),
        migrations.AlterField(
            model_name='product',
            name='description',
            field=models.TextField(blank=True, verbose_name='Опис (legacy)'),
        ),
        migrations.AddConstraint(
            model_name='catalogoption',
            constraint=models.UniqueConstraint(fields=('catalog', 'name'), name='unique_catalog_option_name'),
        ),
        migrations.AddConstraint(
            model_name='catalogoptionvalue',
            constraint=models.UniqueConstraint(fields=('option', 'value'), name='unique_catalog_option_value'),
        ),
        migrations.AddIndex(
            model_name='catalog',
            index=models.Index(fields=['is_active'], name='idx_catalog_active'),
        ),
        migrations.AddIndex(
            model_name='catalog',
            index=models.Index(fields=['order', 'name'], name='idx_catalog_order_name'),
        ),
        migrations.AddIndex(
            model_name='catalogoption',
            index=models.Index(fields=['catalog', 'order'], name='idx_catalog_option_order'),
        ),
        migrations.AddIndex(
            model_name='catalogoption',
            index=models.Index(fields=['catalog', 'option_type'], name='idx_catalog_option_type'),
        ),
        migrations.AddIndex(
            model_name='catalogoptionvalue',
            index=models.Index(fields=['option', 'order'], name='idx_option_value_order'),
        ),
        migrations.AddIndex(
            model_name='sizegrid',
            index=models.Index(fields=['catalog', 'order'], name='idx_size_grid_catalog_order'),
        ),
        migrations.AddIndex(
            model_name='sizegrid',
            index=models.Index(fields=['is_active'], name='idx_size_grid_active'),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['catalog', 'status'], name='idx_product_catalog_status'),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['status', '-id'], name='idx_product_status_id'),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['priority', '-id'], name='idx_product_priority_id'),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['published_at'], name='idx_product_published_at'),
        ),
    ]
