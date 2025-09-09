from django.conf import settings
from django.db import models
from storefront.models import Product, PromoCode
from productcolors.models import ProductColorVariant
from datetime import datetime

class Order(models.Model):
    STATUS_CHOICES = [
        ('new', 'В обробці'),
        ('prep', 'Готується до відправлення'),
        ('ship', 'Відправлено'),
        ('done', 'Отримано'),
        ('cancelled', 'Скасовано'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders', null=True, blank=True)
    order_number = models.CharField(max_length=20, unique=True, blank=True)
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=32)
    city = models.CharField(max_length=100)
    np_office = models.CharField(max_length=200)
    pay_type = models.CharField(max_length=10, default='full')
    payment_status = models.CharField(max_length=20, choices=[
        ('unpaid', 'Не оплачено'),
        ('checking', 'На перевірці'),
        ('partial', 'Внесена передплата'),
        ('paid', 'Оплачено повністю'),
    ], default='unpaid')
    total_sum = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Сума знижки')
    promo_code = models.ForeignKey(PromoCode, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Використаний промокод')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='new')
    tracking_number = models.CharField(max_length=50, blank=True, null=True, verbose_name='Номер ТТН')
    shipment_status = models.CharField(max_length=100, blank=True, null=True, verbose_name='Статус посылки')
    shipment_status_updated = models.DateTimeField(null=True, blank=True, verbose_name='Время обновления статуса')
    payment_screenshot = models.ImageField(upload_to='payment_screenshots/', blank=True, null=True, verbose_name='Скріншот оплати')
    points_awarded = models.BooleanField(default=False, verbose_name='Бали нараховані')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return f'Order {self.order_number} by {self.get_user_display()} — {self.get_status_display()}'
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()
        super().save(*args, **kwargs)
    
    def generate_order_number(self):
        """Генерирует номер заказа в формате TWC+дата+N+номер"""
        today = datetime.now()
        date_str = today.strftime('%d%m%Y')
        
        # Получаем количество заказов за сегодня
        today_orders = Order.objects.filter(
            created__date=today.date()
        ).count()
        
        # Номер по счету (начиная с 01)
        order_count = today_orders + 1
        
        return f"TWC{date_str}N{order_count:02d}"
    
    def get_user_display(self):
        """Возвращает отображаемое имя пользователя"""
        if self.user:
            return f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username
        return "Гість"
    
    def get_payment_status_display(self):
        """Возвращает отображаемое название статуса оплаты"""
        payment_status_choices = dict([
            ('unpaid', 'Не оплачено'),
            ('checking', 'На перевірці'),
            ('partial', 'Внесена передплата'),
            ('paid', 'Оплачено повністю'),
        ])
        return payment_status_choices.get(self.payment_status, self.payment_status)
    
    @classmethod
    def get_processing_count(cls):
        """Возвращает количество заказов в обработке"""
        return cls.objects.filter(status='new').count()
    
    @property
    def subtotal(self):
        """Сумма без скидки"""
        return sum(item.line_total for item in self.items.all())
    
    @property
    def final_total(self):
        """Итоговая сумма с учетом скидки"""
        return self.total_sum
    
    @property
    def total_points(self):
        """Возвращает общее количество балов за заказ"""
        total = 0
        for item in self.items.all():
            if hasattr(item.product, 'points_reward') and item.product.points_reward:
                total += item.product.points_reward * item.qty
        return total
    
    def apply_promo_code(self, promo_code):
        """Применяет промокод к заказу"""
        if not promo_code or not promo_code.can_be_used():
            return False
        
        from decimal import Decimal
        
        subtotal = self.subtotal
        discount = promo_code.calculate_discount(subtotal)
        
        if discount > 0:
            # Преобразуем discount в Decimal для совместимости
            discount_decimal = Decimal(str(discount))
            self.discount_amount = discount_decimal
            self.total_sum = subtotal - discount_decimal
            self.promo_code = promo_code
            return True
        
        return False

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    color_variant = models.ForeignKey(ProductColorVariant, on_delete=models.PROTECT, null=True, blank=True)
    title = models.CharField(max_length=200)
    size = models.CharField(max_length=16, blank=True)
    qty = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f'{self.title} × {self.qty}'
    
    @property
    def color_name(self):
        """Возвращает название цвета или None"""
        if self.color_variant:
            return str(self.color_variant.color)
        return None
    
    @property
    def product_image(self):
        """Возвращает изображение товара с учетом выбранного цвета"""
        if self.color_variant and self.color_variant.images.exists():
            return self.color_variant.images.first().image
        return self.product.main_image
