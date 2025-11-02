from decimal import Decimal

from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    icon = models.ImageField(upload_to='category_icons/', blank=True, null=True)
    cover = models.ImageField(upload_to='category_covers/', blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    # AI-generated content fields
    ai_keywords = models.TextField(blank=True, null=True, verbose_name='AI-ключові слова')
    ai_description = models.TextField(blank=True, null=True, verbose_name='AI-опис')
    ai_content_generated = models.BooleanField(default=False, verbose_name='AI-контент згенеровано')
    
    class Meta:
        ordering = ['order', 'name']
        indexes = [
            models.Index(fields=['is_active'], name='idx_category_active'),
            models.Index(fields=['is_featured'], name='idx_category_featured'),
            models.Index(fields=['order'], name='idx_category_order'),
        ]
    
    def __str__(self):
        return self.name


class Catalog(models.Model):
    name = models.CharField(max_length=200, verbose_name='Назва каталогу')
    slug = models.SlugField(unique=True, verbose_name='URL slug')
    description = models.TextField(blank=True, verbose_name='Опис каталогу')
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок')
    is_active = models.BooleanField(default=True, verbose_name='Активний')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Створено')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Оновлено')

    class Meta:
        verbose_name = 'Каталог'
        verbose_name_plural = 'Каталоги'
        ordering = ['order', 'name']
        indexes = [
            models.Index(fields=['is_active'], name='idx_catalog_active'),
            models.Index(fields=['order', 'name'], name='idx_catalog_order_name'),
        ]

    def __str__(self):
        return self.name


class CatalogOption(models.Model):
    class OptionType(models.TextChoices):
        SIZE = 'size', _('Розмір')
        MATERIAL = 'material', _('Матеріал')
        COLOR = 'color', _('Колір')
        CUSTOM = 'custom', _('Кастомна опція')

    catalog = models.ForeignKey(Catalog, on_delete=models.CASCADE, related_name='options', verbose_name='Каталог')
    name = models.CharField(max_length=200, verbose_name='Назва опції')
    option_type = models.CharField(
        max_length=50,
        choices=OptionType.choices,
        default=OptionType.CUSTOM,
        verbose_name='Тип опції'
    )
    is_required = models.BooleanField(default=True, verbose_name="Обов'язкова")
    is_additional_cost = models.BooleanField(default=False, verbose_name='Додаткова вартість')
    additional_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Додаткова ціна (грн)'
    )
    help_text = models.CharField(max_length=255, blank=True, verbose_name='Підказка')
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок')

    class Meta:
        verbose_name = 'Опція каталогу'
        verbose_name_plural = 'Опції каталогу'
        ordering = ['order', 'id']
        indexes = [
            models.Index(fields=['catalog', 'order'], name='idx_catalog_option_order'),
            models.Index(fields=['catalog', 'option_type'], name='idx_catalog_option_type'),
        ]
        unique_together = ('catalog', 'name')

    def __str__(self):
        return f'{self.catalog.name}: {self.name}'


class CatalogOptionValue(models.Model):
    option = models.ForeignKey(CatalogOption, on_delete=models.CASCADE, related_name='values', verbose_name='Опція')
    value = models.CharField(max_length=200, verbose_name='Значення')
    display_name = models.CharField(max_length=200, verbose_name='Назва для відображення')
    image = models.ImageField(upload_to='catalog_options/', blank=True, null=True, verbose_name='Зображення')
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок')
    is_default = models.BooleanField(default=False, verbose_name='За замовчуванням')
    metadata = models.JSONField(default=dict, blank=True, verbose_name='Додаткові дані')

    class Meta:
        verbose_name = 'Значення опції'
        verbose_name_plural = 'Значення опцій'
        ordering = ['order', 'id']
        indexes = [
            models.Index(fields=['option', 'order'], name='idx_option_value_order'),
        ]
        unique_together = ('option', 'value')

    def __str__(self):
        return f'{self.display_name} ({self.option.name})'


class SizeGrid(models.Model):
    catalog = models.ForeignKey(
        Catalog,
        on_delete=models.CASCADE,
        related_name='size_grids',
        verbose_name='Каталог'
    )
    name = models.CharField(max_length=200, verbose_name='Назва сітки розмірів')
    image = models.ImageField(upload_to='size_grids/', blank=True, null=True, verbose_name='Зображення сітки розмірів')
    description = models.TextField(blank=True, verbose_name='Опис сітки')
    is_active = models.BooleanField(default=True, verbose_name='Активна')
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Створено')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Оновлено')

    class Meta:
        verbose_name = 'Сітка розмірів'
        verbose_name_plural = 'Сітки розмірів'
        ordering = ['order', 'name']
        indexes = [
            models.Index(fields=['catalog', 'order'], name='idx_size_grid_catalog_order'),
            models.Index(fields=['is_active'], name='idx_size_grid_active'),
        ]

    def __str__(self):
        return f'{self.catalog.name}: {self.name}'


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

class ProductStatus(models.TextChoices):
    DRAFT = 'draft', _('Чернетка')
    REVIEW = 'review', _('На модерації')
    SCHEDULED = 'scheduled', _('Заплановано')
    PUBLISHED = 'published', _('Опубліковано')
    ARCHIVED = 'archived', _('Архів')


class Product(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    catalog = models.ForeignKey(
        Catalog,
        on_delete=models.PROTECT,
        related_name='products',
        null=True,
        blank=True,
        verbose_name='Каталог'
    )
    size_grid = models.ForeignKey(
        SizeGrid,
        on_delete=models.SET_NULL,
        related_name='products',
        null=True,
        blank=True,
        verbose_name='Сітка розмірів'
    )
    price = models.PositiveIntegerField(verbose_name='Ціна (грн)')
    # has_discount field removed - see migration 0008_remove_has_discount_field
    # Use @property has_discount below instead (auto-calculated from discount_percent)
    discount_percent = models.PositiveIntegerField(blank=True, null=True)
    featured = models.BooleanField(default=False)
    short_description = models.CharField(max_length=300, blank=True, verbose_name='Короткий опис')
    description = models.TextField(blank=True, verbose_name='Опис (legacy)')
    full_description = models.TextField(blank=True, verbose_name='Повний опис')
    main_image = models.ImageField(upload_to='products/', blank=True, null=True)
    main_image_alt = models.CharField(max_length=200, blank=True, null=True, verbose_name='Alt-текст головного зображення')
    points_reward = models.PositiveIntegerField(default=0, verbose_name='Бали за покупку')
    status = models.CharField(
        max_length=20,
        choices=ProductStatus.choices,
        default=ProductStatus.DRAFT,
        verbose_name='Статус публікації'
    )
    priority = models.PositiveIntegerField(default=0, verbose_name='Пріоритет показу')
    published_at = models.DateTimeField(blank=True, null=True, verbose_name='Опубліковано')
    unpublished_reason = models.CharField(max_length=200, blank=True, verbose_name='Причина відключення')
    last_reviewed_at = models.DateTimeField(blank=True, null=True, verbose_name='Остання модерація')
    seo_title = models.CharField(max_length=160, blank=True, verbose_name='SEO Title')
    seo_description = models.CharField(max_length=320, blank=True, verbose_name='SEO Description')
    seo_keywords = models.CharField(max_length=300, blank=True, verbose_name='SEO ключові слова')
    seo_schema = models.JSONField(blank=True, default=dict, verbose_name='Structured data')
    recommendation_tags = models.JSONField(blank=True, default=list, verbose_name='Теги рекомендацій')
    
    # Дропшип цены
    drop_price = models.PositiveIntegerField(default=0, verbose_name='Ціна дропа (грн)')
    recommended_price = models.PositiveIntegerField(default=0, verbose_name='Рекомендована ціна (грн)')
    
    # Оптовые цены для дропшипа
    wholesale_price = models.PositiveIntegerField(default=0, verbose_name='Оптова ціна (грн)')
    
    # Поля для определения участия в дропшипе
    is_dropship_available = models.BooleanField(default=True, verbose_name='Доступний для дропшипа')
    dropship_note = models.CharField(max_length=200, blank=True, null=True, verbose_name='Примітка для дропшипа')
    
    # AI-generated content fields
    ai_keywords = models.TextField(blank=True, null=True, verbose_name='AI-ключові слова')
    ai_description = models.TextField(blank=True, null=True, verbose_name='AI-опис')
    ai_content_generated = models.BooleanField(default=False, verbose_name='AI-контент згенеровано')

    def save(self, *args, **kwargs):
        # Синхронизуем legacy-описание с новым полем
        if self.full_description and not self.description:
            self.description = self.full_description
        if self.description and not self.full_description:
            self.full_description = self.description
        if self.full_description and not self.short_description:
            plain = self.full_description.strip()
            if len(plain) > 300:
                self.short_description = plain[:297].rstrip() + '...'
            else:
                self.short_description = plain
        super().save(*args, **kwargs)
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
    
    def __str__(self):
        return self.title
    
    def get_drop_price(self, dropshipper=None):
        """Получить цену дропа (оптовая цена) с учетом скидки за успешные дропы"""
        base_price = 0
        
        if self.category and self.category.slug == 'hoodie':
            base_price = 1350
        elif self.category and self.category.slug == 'long-sleeve':
            return 0
        else:
            title_lower = self.title.lower()
            if 'футболка' in title_lower or 't-shirt' in title_lower:
                base_price = 570
            elif 'худи' in title_lower or 'hoodie' in title_lower or 'флис' in title_lower:
                base_price = 1350
            elif self.wholesale_price > 0:
                return self.wholesale_price
            else:
                return self.drop_price
        
        # Если не указан дропшипер, возвращаем базовую цену
        if not dropshipper:
            return base_price
        
        # Рассчитываем скидку за успешные дропы
        from orders.models import DropshipperOrder
        successful_orders = DropshipperOrder.objects.filter(
            dropshipper=dropshipper,
            status='delivered'
        ).count()
        
        # Скидка 10 грн за каждый успешный дроп
        discount = successful_orders * 10
        
        # Минимальные цены
        if base_price == 1350:  # худи
            min_price = 1200
        elif base_price == 570:  # футболки
            min_price = 500
        else:
            min_price = base_price
        
        final_price = max(min_price, base_price - discount)
        return final_price
    
    def get_recommended_price(self):
        """Получить рекомендованную цену (цена со скидкой +-10%)"""
        if self.has_discount and self.discount_percent:
            discounted_price = self.price * (100 - self.discount_percent) / 100
            # Добавляем +-10% к цене со скидкой
            min_price = int(discounted_price * 0.9)
            max_price = int(discounted_price * 1.1)
            return {
                'min': min_price,
                'max': max_price,
                'base': int(discounted_price)
            }
        return {
            'min': int(self.price * 0.9),
            'max': int(self.price * 1.1),
            'base': self.price
        }
    
    def is_available_for_dropship(self):
        """Проверить доступность для дропшипа"""
        if not self.is_dropship_available:
            return False
        if self.category and self.category.slug == 'long-sleeve':
            return False
        return True

    def get_offer_id(self, color_variant_id=None, size='S'):
        """
        Генерирует offer_id для синхронизации с Google Merchant Feed и пикселями.
        
        Args:
            color_variant_id: ID цветового варианта (опционально)
            size: Размер (S, M, L, XL, XXL)
        
        Returns:
            str: offer_id в формате TC-{id}-{variant}-{SIZE}
        
        Examples:
            >>> product.get_offer_id()
            'TC-1-default-S'
            >>> product.get_offer_id(color_variant_id=2, size='M')
            'TC-1-cv2-M'
        """
        from storefront.utils.analytics_helpers import get_offer_id
        return get_offer_id(self.id, color_variant_id, size)
    
    def get_all_offer_ids(self, sizes=None):
        """
        Генерирует все возможные offer_ids для товара (все цвета × все размеры).
        
        Args:
            sizes: Список размеров (по умолчанию ['S', 'M', 'L', 'XL', 'XXL'])
        
        Returns:
            list: Список всех offer_ids
        """
        if sizes is None:
            sizes = ['S', 'M', 'L', 'XL', 'XXL']
        
        offer_ids = []
        
        # Получаем цветовые варианты
        color_variants = self.color_variants.all()
        
        if color_variants.exists():
            # Если есть цветовые варианты - генерируем для каждого
            for variant in color_variants:
                for size in sizes:
                    offer_ids.append(self.get_offer_id(variant.id, size))
        else:
            # Если нет цветовых вариантов - генерируем с default
            for size in sizes:
                offer_ids.append(self.get_offer_id(None, size))
        
        return offer_ids

    class Meta:
        indexes = [
            models.Index(fields=['-id'], name='idx_product_id_desc'),
            models.Index(fields=['featured'], name='idx_product_featured'),
            models.Index(fields=['is_dropship_available'], name='idx_product_dropship'),
            models.Index(fields=['category', '-id'], name='idx_product_category_id'),
            models.Index(fields=['catalog', 'status'], name='idx_product_catalog_status'),
            models.Index(fields=['status', '-id'], name='idx_product_status_id'),
            models.Index(fields=['priority', '-id'], name='idx_product_priority_id'),
            models.Index(fields=['published_at'], name='idx_product_published_at'),
        ]

class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/extra/')
    alt_text = models.CharField(max_length=200, blank=True, null=True, verbose_name='Alt-текст зображення')
    
    def __str__(self):
        return f'Image for {self.product_id}'

class PromoCodeGroup(models.Model):
    """Группа промокодов с ограничением 'один на аккаунт'"""
    name = models.CharField(max_length=100, verbose_name='Назва групи')
    description = models.TextField(blank=True, null=True, verbose_name='Опис групи')
    one_per_account = models.BooleanField(default=True, verbose_name='Один промокод на акаунт з групи')
    is_active = models.BooleanField(default=True, verbose_name='Активна')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Створено')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Оновлено')
    
    class Meta:
        verbose_name = 'Група промокодів'
        verbose_name_plural = 'Групи промокодів'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active', '-created_at'], name='idx_group_active_created'),
        ]
    
    def __str__(self):
        return f'{self.name} {"(один на акаунт)" if self.one_per_account else ""}'


class PromoCode(models.Model):
    DISCOUNT_TYPES = [
        ('percentage', 'Відсоток'),
        ('fixed', 'Фіксована сума'),
    ]
    
    PROMO_TYPES = [
        ('regular', 'Звичайний промокод'),
        ('voucher', 'Ваучер (фіксована сума)'),
        ('grouped', 'Груповий промокод'),
    ]
    
    # Основні поля
    code = models.CharField(max_length=20, unique=True, blank=True, verbose_name='Код промокоду')
    promo_type = models.CharField(max_length=10, choices=PROMO_TYPES, default='regular', verbose_name='Тип промокоду')
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPES, verbose_name='Тип знижки')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Значення знижки')
    description = models.TextField(blank=True, null=True, verbose_name='Опис')
    
    # Группировка
    group = models.ForeignKey(
        PromoCodeGroup, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='promo_codes',
        verbose_name='Група'
    )
    
    # Ограничения использования
    max_uses = models.PositiveIntegerField(default=0, verbose_name='Максимальна кількість використань (0 = безліміт)')
    current_uses = models.PositiveIntegerField(default=0, verbose_name='Поточна кількість використань')
    one_time_per_user = models.BooleanField(default=False, verbose_name='Одноразове використання на користувача')
    min_order_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        verbose_name='Мінімальна сума замовлення'
    )
    
    # Период действия
    valid_from = models.DateTimeField(null=True, blank=True, verbose_name='Дійсний з')
    valid_until = models.DateTimeField(null=True, blank=True, verbose_name='Дійсний до')
    
    # Статус
    is_active = models.BooleanField(default=True, verbose_name='Активний')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Створено')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Оновлено')
    
    class Meta:
        verbose_name = 'Промокод'
        verbose_name_plural = 'Промокоди'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active', '-created_at'], name='idx_promo_active_created'),
            models.Index(fields=['group', 'is_active'], name='idx_promo_group_active'),
            models.Index(fields=['promo_type', 'is_active'], name='idx_promo_type_active'),
            models.Index(fields=['code'], name='idx_promo_code'),
        ]
    
    def __str__(self):
        type_label = dict(self.PROMO_TYPES).get(self.promo_type, 'Промокод')
        return f'{self.code} ({type_label}) - {self.get_discount_display()}'
    
    def get_discount_display(self):
        """Возвращает отображаемое значение скидки"""
        if self.discount_type == 'percentage':
            return f'{self.discount_value}%'
        else:
            return f'{self.discount_value} грн'
    
    def is_valid_now(self):
        """Проверяет, действителен ли промокод по времени"""
        now = timezone.now()
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        return True
    
    def can_be_used(self):
        """Проверяет, можно ли использовать промокод (без проверки пользователя)"""
        if not self.is_active:
            return False
        if not self.is_valid_now():
            return False
        if self.max_uses > 0 and self.current_uses >= self.max_uses:
            return False
        return True
    
    def can_be_used_by_user(self, user):
        """Проверяет, может ли конкретный пользователь использовать промокод"""
        if not user or not user.is_authenticated:
            return False, 'Промокоди доступні тільки для зареєстрованих користувачів'
        
        if not self.can_be_used():
            if not self.is_active:
                return False, 'Промокод неактивний'
            if not self.is_valid_now():
                return False, 'Промокод недійсний за часом'
            if self.max_uses > 0 and self.current_uses >= self.max_uses:
                return False, 'Промокод вичерпано'
            return False, 'Промокод неактивний або вичерпаний'
        
        # Проверка one_time_per_user
        if self.one_time_per_user:
            if PromoCodeUsage.objects.filter(user=user, promo_code=self).exists():
                return False, 'Ви вже використали цей промокод'
        
        # Проверка группы (one_per_account)
        if self.group and self.group.one_per_account:
            # Проверяем, использовал ли пользователь какой-либо промокод из этой группы
            if PromoCodeUsage.objects.filter(user=user, group=self.group).exists():
                return False, f'Ви вже використали промокод з групи "{self.group.name}"'
        
        return True, 'OK'
    
    def use(self):
        """Использует промокод (увеличивает счетчик)"""
        if self.can_be_used():
            self.current_uses += 1
            self.save()
            return True
        return False
    
    def record_usage(self, user, order=None):
        """Записывает использование промокода пользователем"""
        if not user or not user.is_authenticated:
            return None
        
        usage = PromoCodeUsage.objects.create(
            user=user,
            promo_code=self,
            group=self.group,
            order=order
        )
        self.use()
        return usage
    
    def calculate_discount(self, total_amount):
        """Рассчитывает скидку для указанной суммы"""
        if not self.can_be_used():
            return 0
        
        # Проверяем минимальную сумму заказа
        from decimal import Decimal
        total = Decimal(str(total_amount))
        
        if self.min_order_amount and total < self.min_order_amount:
            return 0
        
        discount_value = Decimal(str(self.discount_value))
        
        if self.discount_type == 'percentage':
            return (total * discount_value) / 100
        else:
            # Для ваучеров и фиксированной скидки
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


class PromoCodeUsage(models.Model):
    """История использования промокодов пользователями"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='promo_usages',
        verbose_name='Користувач'
    )
    promo_code = models.ForeignKey(
        PromoCode, 
        on_delete=models.CASCADE, 
        related_name='usages',
        verbose_name='Промокод'
    )
    group = models.ForeignKey(
        PromoCodeGroup, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='usages',
        verbose_name='Група'
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='promo_usages',
        verbose_name='Замовлення'
    )
    used_at = models.DateTimeField(auto_now_add=True, verbose_name='Використано')
    
    class Meta:
        verbose_name = 'Використання промокоду'
        verbose_name_plural = 'Використання промокодів'
        ordering = ['-used_at']
        indexes = [
            models.Index(fields=['user', 'promo_code'], name='idx_usage_user_promo'),
            models.Index(fields=['user', 'group'], name='idx_usage_user_group'),
            models.Index(fields=['-used_at'], name='idx_usage_date'),
        ]
    
    def __str__(self):
        return f'{self.user.username} - {self.promo_code.code} ({self.used_at.strftime("%Y-%m-%d %H:%M")})'


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
        indexes = [
            models.Index(fields=['is_active', 'order'], name='idx_store_active_order'),
        ]
    
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
        indexes = [
            models.Index(fields=['is_bot', '-last_seen'], name='idx_session_bot_seen'),
        ]

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
        indexes = [
            models.Index(fields=['is_bot', '-when'], name='idx_pageview_bot_when'),
        ]

    def __str__(self) -> str:
        return f"{self.path} @ {self.when}"


# ===== Модели для управления оффлайн магазинами =====

class StoreProduct(models.Model):
    """Товар в оффлайн магазине"""
    store = models.ForeignKey(OfflineStore, on_delete=models.CASCADE, related_name='store_products', verbose_name='Магазин')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name='Товар')
    color = models.ForeignKey('productcolors.Color', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Колір')
    size = models.CharField(max_length=10, blank=True, null=True, verbose_name='Розмір')
    quantity = models.PositiveIntegerField(default=1, verbose_name='Кількість')
    cost_price = models.PositiveIntegerField(verbose_name='Собівартість (грн)')
    selling_price = models.PositiveIntegerField(verbose_name='Ціна продажу (грн)')
    is_active = models.BooleanField(default=True, verbose_name='Активний')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Створено')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Оновлено')
    
    class Meta:
        verbose_name = 'Товар в магазині'
        verbose_name_plural = 'Товари в магазинах'
        ordering = ['-created_at']
        unique_together = [['store', 'product', 'size', 'color']]
    
    def __str__(self):
        return f"{self.product.title} - {self.store.name}"
    
    @property
    def margin(self):
        """Маржа товара"""
        return self.selling_price - self.cost_price

    @property
    def total_cost(self):
        return (self.cost_price or 0) * (self.quantity or 0)

    @property
    def total_revenue(self):
        return (self.selling_price or 0) * (self.quantity or 0)

    @property
    def total_margin(self):
        return self.total_revenue - self.total_cost


class StoreOrder(models.Model):
    """Заказ в оффлайн магазине"""
    STATUS_CHOICES = [
        ('draft', 'Чернетка'),
        ('pending', 'В обробці'),
        ('confirmed', 'Підтверджено'),
        ('completed', 'Виконано'),
        ('cancelled', 'Скасовано'),
    ]
    
    store = models.ForeignKey(OfflineStore, on_delete=models.CASCADE, related_name='store_orders', verbose_name='Магазин')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name='Статус')
    notes = models.TextField(blank=True, null=True, verbose_name='Примітки')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Створено')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Оновлено')
    
    class Meta:
        verbose_name = 'Заказ магазина'
        verbose_name_plural = 'Заказы магазинов'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Замовлення #{self.id} - {self.store.name}"


class StoreOrderItem(models.Model):
    """Элемент заказа в оффлайн магазине"""
    order = models.ForeignKey(StoreOrder, on_delete=models.CASCADE, related_name='order_items', verbose_name='Заказ')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name='Товар')
    color = models.ForeignKey('productcolors.Color', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Колір')
    size = models.CharField(max_length=10, blank=True, null=True, verbose_name='Розмір')
    quantity = models.PositiveIntegerField(default=1, verbose_name='Кількість')
    cost_price = models.PositiveIntegerField(verbose_name='Собівартість (грн)')
    selling_price = models.PositiveIntegerField(verbose_name='Ціна продажу (грн)')
    
    class Meta:
        verbose_name = 'Товар в заказі'
        verbose_name_plural = 'Товари в заказах'
        ordering = ['id']
    
    def __str__(self):
        return f"{self.product.title} - {self.order}"
    
    @property
    def total_price(self):
        """Общая цена элемента заказа"""
        return self.selling_price * self.quantity


class StoreSale(models.Model):
    """Факт продажу товару з офлайн-магазину."""

    store = models.ForeignKey(
        OfflineStore,
        on_delete=models.CASCADE,
        related_name='store_sales',
        verbose_name='Магазин'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='store_sales',
        verbose_name='Товар'
    )
    color = models.ForeignKey(
        'productcolors.Color',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Колір'
    )
    size = models.CharField(max_length=10, blank=True, null=True, verbose_name='Розмір')
    quantity = models.PositiveIntegerField(default=1, verbose_name='Кількість')
    cost_price = models.PositiveIntegerField(verbose_name='Собівартість (грн)')
    selling_price = models.PositiveIntegerField(verbose_name='Ціна продажу (грн)')
    sold_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата продажу')
    source_store_product = models.ForeignKey(
        StoreProduct,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales_history',
        verbose_name='Джерело запису'
    )
    notes = models.CharField(max_length=255, blank=True, null=True, verbose_name='Примітки')

    class Meta:
        verbose_name = 'Проданий товар'
        verbose_name_plural = 'Продані товари'
        ordering = ['-sold_at']

    def __str__(self):
        return f"{self.product.title} — {self.store.name} ({self.quantity} шт.)"

    @property
    def margin(self):
        return (self.selling_price - self.cost_price) * self.quantity

    @property
    def total_revenue(self):
        return self.selling_price * self.quantity

    @property
    def total_cost(self):
        return self.cost_price * self.quantity


class StoreInvoice(models.Model):
    """Накладна магазина"""
    store = models.ForeignKey(OfflineStore, on_delete=models.CASCADE, related_name='invoices', verbose_name='Магазин')
    order = models.ForeignKey(StoreOrder, on_delete=models.CASCADE, related_name='invoices', blank=True, null=True, verbose_name='Заказ')
    file_name = models.CharField(max_length=255, default='', verbose_name='Назва файлу')
    file_path = models.CharField(max_length=500, default='', verbose_name='Шлях до файлу')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Створено')
    
    class Meta:
        verbose_name = 'Накладна'
        verbose_name_plural = 'Накладні'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Накладна #{self.id} - {self.store.name}"
