from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('storefront', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Color',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, max_length=100)),
                ('primary_hex', models.CharField(help_text='#RRGGBB', max_length=7)),
                ('secondary_hex', models.CharField(blank=True, help_text='#RRGGBB (опционально)', max_length=7, null=True)),
            ],
            options={
                'unique_together': {('primary_hex', 'secondary_hex')},
            },
        ),
        migrations.CreateModel(
            name='ProductColorVariant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_default', models.BooleanField(default=False)),
                ('order', models.PositiveIntegerField(default=0)),
                ('color', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='variants', to='productcolors.color')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='color_variants', to='storefront.product')),
            ],
            options={
                'ordering': ['order', 'id'],
                'unique_together': {('product', 'color')},
            },
        ),
        migrations.CreateModel(
            name='ProductColorImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='product_colors/')),
                ('order', models.PositiveIntegerField(default=0)),
                ('variant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='productcolors.productcolorvariant')),
            ],
            options={
                'ordering': ['order', 'id'],
            },
        ),
    ]
