from django.db import models
from django.contrib.auth.models import User

class Category(models.Model):
    name=models.CharField(max_length=100, unique=True)
    slug=models.SlugField(unique=True)
    icon=models.ImageField(upload_to='category_icons/', blank=True, null=True)
    cover=models.ImageField(upload_to='category_covers/', blank=True, null=True)
    order=models.PositiveIntegerField(default=0)
    description=models.TextField(blank=True, null=True)
    is_active=models.BooleanField(default=True)
    is_featured=models.BooleanField(default=False)
    class Meta: ordering=['order','name']
    def __str__(self): return self.name


class PrintProposal(models.Model):
    """Заявка пользователя на предложенный принт"""
    STATUS_CHOICES = [
        ("pending", "На розгляді"),
        ("approved", "Схвалено"),
        ("rejected", "Відхилено"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="print_proposals", verbose_name="Користувач")
    image = models.ImageField(upload_to="print_proposals/", blank=True, null=True, verbose_name="Зображення")
    link_url = models.URLField(blank=True, verbose_name="Посилання на зображення")
    description = models.TextField(blank=True, verbose_name="Опис / примітки")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending", verbose_name="Статус")
    awarded_points = models.PositiveIntegerField(default=0, verbose_name="Нараховані бали")
    awarded_promocode = models.ForeignKey(
        "storefront.PromoCode", on_delete=models.SET_NULL, blank=True, null=True, verbose_name="Промокод"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Створено")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Оновлено")

    class Meta:
        verbose_name = "Пропозиція принта"
        verbose_name_plural = "Пропозиції принтів"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        base = f"{self.user.username} — {self.get_status_display()}"
        if self.awarded_points:
            base += f" (+{self.awarded_points} б.)"
        return base

class Product(models.Model):
    title=models.CharField(max_length=200)
    slug=models.SlugField(unique=True)
    category=models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    price=models.PositiveIntegerField()
    has_discount=models.BooleanField(default=False)
    discount_percent=models.PositiveIntegerField(blank=True, null=True)
    featured=models.BooleanField(default=False)
    description=models.TextField(blank=True)
    main_image=models.ImageField(upload_to='products/', blank=True, null=True)
    points_reward=models.PositiveIntegerField(default=0, verbose_name='Бали за покупку')
    @property
    def has_discount(self):
        """Автоматически определяет, есть ли скидка"""
        return bool(self.discount_percent and self.discount_percent > 0)
    
    @property
    def final_price(self):
        if self.has_discount:
            return int(self.price*(100-self.discount_percent)/100)
        return self.price
    
    @property
    def display_image(self):
        """Возвращает главное изображение или первую фотографию первого цвета"""
        if self.main_image:
            return self.main_image
        
        # Если нет главного изображения, ищем в цветах
        first_color_variant = self.color_variants.first()
        if first_color_variant:
            first_image = first_color_variant.images.first()
            if first_image:
                return first_image.image
        
        return None
    
    def __str__(self): return self.title

class ProductImage(models.Model):
    product=models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image=models.ImageField(upload_to='products/extra/')
    def __str__(self): return f'Image for {self.product_id}'

class PromoCode(models.Model):
    DISCOUNT_TYPES = [
        ('percentage', 'Відсоток'),
        ('fixed', 'Фіксована сума'),
    ]
    
    code = models.CharField(max_length=20, unique=True, blank=True, verbose_name='Код промокоду')
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPES, verbose_name='Тип знижки')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Значення знижки')
    max_uses = models.PositiveIntegerField(default=0, verbose_name='Максимальна кількість використань (0 = безліміт)')
    current_uses = models.PositiveIntegerField(default=0, verbose_name='Поточна кількість використань')
    is_active = models.BooleanField(default=True, verbose_name='Активний')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Створено')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Оновлено')
    
    class Meta:
        verbose_name = 'Промокод'
        verbose_name_plural = 'Промокоди'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.code} - {self.get_discount_display()}'
    
    def get_discount_display(self):
        """Возвращает отображаемое значение скидки"""
        if self.discount_type == 'percentage':
            return f'{self.discount_value}%'
        else:
            return f'{self.discount_value} грн'
    
    def can_be_used(self):
        """Проверяет, можно ли использовать промокод"""
        if not self.is_active:
            return False
        if self.max_uses > 0 and self.current_uses >= self.max_uses:
            return False
        return True
    
    def use(self):
        """Использует промокод"""
        if self.can_be_used():
            self.current_uses += 1
            self.save()
            return True
        return False
    
    def calculate_discount(self, total_amount):
        """Рассчитывает скидку для указанной суммы"""
        if not self.can_be_used():
            return 0
        
        # Преобразуем в Decimal для точных вычислений
        from decimal import Decimal
        total = Decimal(str(total_amount))
        discount_value = Decimal(str(self.discount_value))
        
        if self.discount_type == 'percentage':
            return (total * discount_value) / 100
        else:
            return min(discount_value, total)
    
    def get_purchases_count(self):
        """Возвращает количество покупок с этим промокодом (исключая отмененные и в обработке)"""
        from orders.models import Order
        return Order.objects.filter(
            promo_code=self,
            status__in=['prep', 'ship', 'done']
        ).count()
    
    @classmethod
    def generate_code(cls, length=8):
        """Генерирует уникальный код промокода"""
        import random
        import string
        
        while True:
            # Генерируем код из букв и цифр
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
            # Проверяем, что код уникален
            if not cls.objects.filter(code=code).exists():
                return code


class OfflineStore(models.Model):
    """Модель для оффлайн магазинов"""
    name = models.CharField(max_length=200, verbose_name='Назва магазину')
    address = models.TextField(verbose_name='Адреса')
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name='Телефон')
    email = models.EmailField(blank=True, null=True, verbose_name='Email')
    working_hours = models.CharField(max_length=100, blank=True, null=True, verbose_name='Робочі години')
    description = models.TextField(blank=True, null=True, verbose_name='Опис')
    is_active = models.BooleanField(default=True, verbose_name='Активний')
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок відображення')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Створено')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Оновлено')
    
    class Meta:
        verbose_name = 'Оффлайн магазин'
        verbose_name_plural = 'Оффлайн магазини'
        ordering = ['order', 'name']
    
    def __str__(self):
        return self.name


# ===== Лёгкая аналитика посещений =====
class SiteSession(models.Model):
    """
    Агрегированная сессионная метрика по посетителю.
    Используем session_key как идентификатор уникального визита (для анонимов),
    а для авторизованных — связываем с пользователем.
    """
    session_key = models.CharField(max_length=40, unique=True, db_index=True)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    is_bot = models.BooleanField(default=False, db_index=True)
    first_seen = models.DateTimeField(auto_now_add=True, db_index=True)
    last_seen = models.DateTimeField(auto_now=True, db_index=True)
    last_path = models.CharField(max_length=512, blank=True)
    pageviews = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-last_seen']

    def __str__(self) -> str:
        return f"{self.session_key} ({'bot' if self.is_bot else 'user'})"


class PageView(models.Model):
    """Запись отдельного просмотра страницы"""
    session = models.ForeignKey(SiteSession, on_delete=models.CASCADE, related_name='views')
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    path = models.CharField(max_length=512)
    referrer = models.CharField(max_length=512, blank=True)
    when = models.DateTimeField(auto_now_add=True, db_index=True)
    is_bot = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ['-when']

    def __str__(self) -> str:
        return f"{self.path} @ {self.when}"


class SiteSession(models.Model):
    """Модель для отслеживания сессий пользователей"""
    session_key = models.CharField(max_length=40, unique=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    is_bot = models.BooleanField(default=False)
    last_path = models.CharField(max_length=512, blank=True)
    pageviews = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_seen']
        verbose_name = 'Сессия сайта'
        verbose_name_plural = 'Сессии сайта'

    def __str__(self):
        return f"Session {self.session_key[:8]}... ({self.pageviews} views)"


class PageView(models.Model):
    """Модель для отслеживания просмотров страниц"""
    session = models.ForeignKey(SiteSession, on_delete=models.CASCADE, related_name='page_views')
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    path = models.CharField(max_length=512, db_index=True)
    referrer = models.CharField(max_length=512, blank=True)
    is_bot = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Просмотр страницы'
        verbose_name_plural = 'Просмотры страниц'

    def __str__(self):
        return f"{self.path} @ {self.created_at}"
