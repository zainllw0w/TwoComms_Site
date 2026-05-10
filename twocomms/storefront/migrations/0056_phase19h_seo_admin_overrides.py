"""Phase 19h (2026-05-10) — admin-editable SEO overrides.

Adds:
* ``Category.showcase_swatch_hexes`` (JSONField, default=list) — manual
  override for the catalog showcase card swatches.
* ``CatalogColorSeoOverride`` — per-(scope, color_slug, category) row
  letting the team edit colour-aware SEO copy without code deploy.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('storefront', '0055_phase15_product_seo_bottom_html'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='showcase_swatch_hexes',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    'Список hex-кольорів для картки в /catalog/ (наприклад '
                    '["#000000","#fafafa"]). Якщо порожньо — обчислюються '
                    'автоматично з товарів категорії (відсіюючи одиничні).'
                ),
                verbose_name='Свотчі на showcase-картці',
            ),
        ),
        migrations.CreateModel(
            name='CatalogColorSeoOverride',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scope', models.CharField(
                    choices=[
                        ('general', 'Загальний каталог /catalog/'),
                        ('brand', 'Каталог /catalog/?color=<колір>'),
                        ('category', 'Категорія /catalog/<cat>/?color=<колір>'),
                    ],
                    max_length=12,
                    verbose_name='Контекст',
                )),
                ('color_slug', models.SlugField(
                    blank=True,
                    default='',
                    help_text=(
                        'Заповніть для контекстів «brand»/«category» (наприклад '
                        '«black», «coyote»). Залиште порожнім для «general».'
                    ),
                    max_length=64,
                    verbose_name='Slug кольору',
                )),
                ('h2', models.CharField(
                    blank=True,
                    help_text='Якщо порожньо — використовується курований заголовок з коду.',
                    max_length=300,
                    verbose_name='Заголовок (H2)',
                )),
                ('body_html', models.TextField(
                    blank=True,
                    help_text=(
                        "Параграфи у форматі HTML (наприклад '<p>Перший абзац…</p>"
                        "<p>Другий…</p>'). Дозволені теги <a>, <strong>, <em>. "
                        'Якщо порожньо — використовуються куровані параграфи з коду.'
                    ),
                    verbose_name='HTML-параграфи',
                )),
                ('queries_json', models.JSONField(
                    blank=True,
                    default=list,
                    help_text=(
                        "JSON-масив об'єктів {label, url, freq}, де freq — 'hf' / "
                        "'mf' / 'lf'. Якщо порожньо — використовуються куровані з коду."
                    ),
                    verbose_name='Чипи-запити',
                )),
                ('is_active', models.BooleanField(default=True, verbose_name='Активний')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Оновлено')),
                ('category', models.ForeignKey(
                    blank=True,
                    help_text='Заповніть для контексту «category»; залиште порожнім для «brand»/«general».',
                    null=True,
                    on_delete=models.deletion.CASCADE,
                    related_name='color_seo_overrides',
                    to='storefront.category',
                    verbose_name='Категорія',
                )),
            ],
            options={
                'verbose_name': 'SEO-копія каталогу за кольором',
                'verbose_name_plural': 'SEO-копії каталогу за кольорами',
            },
        ),
        migrations.AddIndex(
            model_name='catalogcolorseooverride',
            index=models.Index(fields=['scope', 'color_slug'], name='idx_clrseo_scope_slug'),
        ),
        migrations.AddIndex(
            model_name='catalogcolorseooverride',
            index=models.Index(fields=['category'], name='idx_clrseo_category'),
        ),
        migrations.AddIndex(
            model_name='catalogcolorseooverride',
            index=models.Index(fields=['is_active'], name='idx_clrseo_active'),
        ),
        migrations.AddConstraint(
            model_name='catalogcolorseooverride',
            constraint=models.UniqueConstraint(
                fields=('scope', 'color_slug', 'category'),
                name='uq_color_seo_override_scope_slug_cat',
            ),
        ),
    ]
