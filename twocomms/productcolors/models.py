from django.db import models
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

    class Meta:
        ordering = ['order', 'id']
        unique_together = (('product', 'color'),)
        indexes = [
            models.Index(fields=['product', 'order'], name='idx_variant_product_order'),
            models.Index(fields=['product', 'is_default'], name='idx_variant_default'),
            models.Index(fields=['sku'], name='idx_variant_sku'),
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
