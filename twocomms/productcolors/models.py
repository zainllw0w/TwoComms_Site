from django.db import models
from django.utils.text import slugify
from storefront.models import Product


class Color(models.Model):
    """
    Универсальная сущность цвета: один или составной (два цвета).
    """
    name = models.CharField(max_length=100, blank=True)
    primary_hex = models.CharField(max_length=7, help_text='#RRGGBB')
    secondary_hex = models.CharField(max_length=7, blank=True, null=True, help_text='#RRGGBB (опционально)')

    class Meta:
        unique_together = (('primary_hex', 'secondary_hex'),)

    def __str__(self):
        if self.secondary_hex:
            return f'{self.primary_hex}+{self.secondary_hex}'
        return self.primary_hex


class ProductColorVariant(models.Model):
    """
    Вариант цвета для конкретного товара.
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='color_variants')
    color = models.ForeignKey(Color, on_delete=models.PROTECT, related_name='variants')
    is_default = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    sku = models.CharField(max_length=64, blank=True, verbose_name='SKU')
    barcode = models.CharField(max_length=64, blank=True, verbose_name='Штрих-код')
    stock = models.PositiveIntegerField(default=0, verbose_name='Залишок')
    price_override = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name='Ціна для варіанту (грн)'
    )
    metadata = models.JSONField(blank=True, default=dict, verbose_name='Додаткові дані')
    # Phase 7.1 — URL slug used by path-style variant URLs
    # ``/product/<product>/<color-slug>/``. Auto-filled from
    # ``color.name`` on save; unique within a product so the slug can
    # safely sit in the URL.
    slug = models.SlugField(
        max_length=80,
        blank=True,
        verbose_name='URL slug',
        help_text='Унікальний у межах товару фрагмент URL для path-варіантів.',
    )

    class Meta:
        ordering = ['order', 'id']
        unique_together = (('product', 'color'), ('product', 'slug'))
        indexes = [
            models.Index(fields=['product', 'order'], name='idx_variant_product_order'),
            models.Index(fields=['product', 'is_default'], name='idx_variant_default'),
            models.Index(fields=['sku'], name='idx_variant_sku'),
            models.Index(fields=['product', 'slug'], name='idx_variant_product_slug'),
        ]

    def __str__(self):
        return f'{self.product.title} [{self.color}]'

    def get_variant_key(self):
        """
        Возвращает ключ варианта для offer_id.

        Returns:
            str: 'cv{id}' (например 'cv2')
        """
        return f'cv{self.id}'

    def _generate_url_slug(self) -> str:
        """Build a stable, URL-safe slug for this color variant.

        Falls back gracefully when ``color.name`` is empty, ensures
        uniqueness within the parent product, and avoids collisions
        with ``Product.size`` codes (one-letter slugs like ``m`` would
        be ambiguous in path-style URLs from Phase 7.2).
        """
        base = ""
        color = getattr(self, "color", None)
        if color is not None:
            base = slugify(color.name or "") or ""
            if not base and getattr(color, "primary_hex", ""):
                base = slugify(color.primary_hex.lstrip("#")) or ""
        if not base:
            base = "color"

        # Disambiguate one/two-letter slugs that would collide with
        # size codes (S, M, L, XL, XXL, XXXL). Always append "-c".
        if len(base) <= 4:
            base = f"{base}-c"

        candidate = base
        index = 2
        while (
            ProductColorVariant.objects
            .filter(product_id=self.product_id, slug=candidate)
            .exclude(pk=self.pk)
            .exists()
        ):
            candidate = f"{base}-{index}"
            index += 1
        return candidate

    def save(self, *args, **kwargs):
        if self.product_id and not self.slug:
            self.slug = self._generate_url_slug()
        super().save(*args, **kwargs)

    def get_offer_id(self, size='S'):
        """
        Генерирует offer_id для этого цветового варианта.

        Args:
            size: Размер (S, M, L, XL, XXL)

        Returns:
            str: offer_id в формате TC-{product_id}-cv{variant_id}-{SIZE}
        """
        return self.product.get_offer_id(self.id, size)


class ProductColorImage(models.Model):
    """
    Изображения, привязанные к цветовому варианту товара.
    """
    variant = models.ForeignKey(ProductColorVariant, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='product_colors/')
    alt_text = models.CharField(max_length=200, blank=True, null=True, verbose_name='Alt-текст зображення')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f'Image for {self.variant}'
