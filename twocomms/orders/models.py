from django.conf import settings
from django.db import models, IntegrityError, transaction
from storefront.models import Product, PromoCode
from productcolors.models import ProductColorVariant
from django.utils import timezone

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
    session_key = models.CharField(max_length=40, blank=True, null=True)
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
    payment_provider = models.CharField(max_length=50, blank=True, default='')
    payment_invoice_id = models.CharField(max_length=128, blank=True, default='')
    payment_payload = models.JSONField(blank=True, null=True)
    points_awarded = models.BooleanField(default=False, verbose_name='Бали нараховані')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']
        indexes = [
            models.Index(fields=['-created'], name='idx_order_created_desc'),
            models.Index(fields=['status', '-created'], name='idx_order_status_created'),
            models.Index(fields=['payment_status', '-created'], name='idx_order_payment_created'),
        ]

    def __str__(self):
        return f'Order {self.order_number} by {self.get_user_display()} — {self.get_status_display()}'
    
    def save(self, *args, **kwargs):
        attempts = 0
        while True:
            if not self.order_number:
                self.order_number = self.generate_order_number()
            try:
                with transaction.atomic():
                    super().save(*args, **kwargs)
                break
            except IntegrityError:
                attempts += 1
                if attempts >= 5:
                    raise
                # сбросим номер и попробуем ещё раз
                self.order_number = None
    
    def generate_order_number(self):
        """Генерирует уникальный номер заказа в формате TWC+дата+N+номер."""
        today = timezone.localdate()
        date_str = today.strftime('%d%m%Y')
        counter = 1

        while True:
            number = f"TWC{date_str}N{counter:02d}"
            if not Order.objects.filter(order_number=number).exists():
                return number
            counter += 1
    
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
            color = getattr(self.color_variant, 'color', None)
            if color:
                name = (getattr(color, 'name', '') or '').strip()
                if name:
                    return name
                primary = (getattr(color, 'primary_hex', '') or '').strip().lstrip('#').upper()
                secondary = (getattr(color, 'secondary_hex', '') or '').strip().lstrip('#').upper()

                hex_map = {
                    '000000': 'чорний',
                    'FFFFFF': 'білий',
                    'FAFAFA': 'білий',
                    'F5F5F5': 'білий',
                    'FF0000': 'червоний',
                    'C1382F': 'бордовий',
                    'FFA500': 'помаранчевий',
                    'FFFF00': 'жовтий',
                    '00FF00': 'зелений',
                    '0000FF': 'синій',
                    '808080': 'сірий',
                    'A52A2A': 'коричневий',
                    '800080': 'фіолетовий',
                }

                if secondary:
                    a = hex_map.get(primary)
                    b = hex_map.get(secondary)
                    if a and b:
                        return f"{a}/{b}"
                if primary in hex_map:
                    return hex_map[primary]
                if secondary and secondary in hex_map:
                    return hex_map[secondary]
        return None
    
    @property
    def product_image(self):
        """Возвращает изображение товара с учетом выбранного цвета"""
        if self.color_variant and self.color_variant.images.exists():
            return self.color_variant.images.first().image
        return self.product.main_image


class WholesaleInvoice(models.Model):
    """Модель для оптовых накладных"""
    STATUS_CHOICES = [
        ('draft', 'Чернетка'),
        ('pending', 'Очікує перевірки'),
        ('processing', 'Прийнято в обробку'),
        ('shipped', 'Готується до відправки'),
        ('delivered', 'Товари відправлені'),
        ('cancelled', 'Скасовано'),
    ]
    
    invoice_number = models.CharField(max_length=100, unique=True, verbose_name="Номер накладної")
    company_name = models.CharField(max_length=200, verbose_name="Назва компанії/ФОП/ПІБ")
    company_number = models.CharField(max_length=50, blank=True, verbose_name="Номер компанії/ЄДРПОУ/ІПН")
    contact_phone = models.CharField(max_length=32, verbose_name="Номер телефону")
    delivery_address = models.TextField(verbose_name="Адреса доставки")
    store_link = models.URLField(blank=True, null=True, verbose_name="Посилання на магазин")
    
    total_tshirts = models.IntegerField(default=0, verbose_name="Кількість футболок")
    total_hoodies = models.IntegerField(default=0, verbose_name="Кількість худі")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Загальна сума")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name="Статус")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата створення")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата оновлення")
    
    # JSON поле для хранения деталей заказа
    order_details = models.JSONField(verbose_name="Деталі замовлення")
    
    # Путь к файлу накладной
    file_path = models.CharField(max_length=500, blank=True, null=True, verbose_name="Шлях до файлу")
    
    # Поле для одобрения накладной (доступна для оплаты)
    is_approved = models.BooleanField(default=False, verbose_name="Одобрена для оплаты")
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('not_paid', 'Не оплачена'),
            ('paid', 'Оплачена'),
            ('pending', 'Ожидает оплаты'),
            ('failed', 'Ошибка оплаты'),
        ],
        default='not_paid',
        verbose_name="Статус оплаты"
    )
    
    class Meta:
        verbose_name = "Оптова накладна"
        verbose_name_plural = "Оптові накладні"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.invoice_number} - {self.company_name}"
    
    @property
    def file_name(self):
        """Генерирует имя файла для Excel"""
        date_str = self.created_at.strftime('%Y%m%d_%H%M%S')
        return f"{self.company_name}_накладнаОПТ_{date_str}.xlsx"


class DropshipperOrder(models.Model):
    """Модель для заказов дропшиперов"""
    STATUS_CHOICES = [
        ('draft', 'Чернетка'),
        ('pending', 'Очікує підтвердження'),
        ('awaiting_payment', 'Очікує оплати'),
        ('confirmed', 'Підтверджено'),
        ('processing', 'В обробці'),
        ('awaiting_shipment', 'Очікує відправки'),
        ('shipped', 'Відправлено'),
        ('delivered_awaiting_pickup', 'Доставлено, очікує отримувача'),
        ('received', 'Товар отримано'),
        ('refused', 'Від товару відмовились'),
        ('delivered', 'Доставлено'),  # Оставляем для совместимости
        ('cancelled', 'Скасовано'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('unpaid', 'Не оплачено'),
        ('paid', 'Оплачено'),
        ('refunded', 'Повернено'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('prepaid', 'Товар оплачено'),
        ('cod', 'Накладний платіж'),
        ('delegation', 'Повне делегування'),
    ]
    
    # Информация о дропшипере
    dropshipper = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='dropshipper_orders', verbose_name="Дропшипер")
    
    # Информация о клиенте
    client_name = models.CharField(max_length=200, verbose_name="ПІБ клієнта")
    client_phone = models.CharField(max_length=32, verbose_name="Телефон клієнта")
    client_np_address = models.CharField(max_length=500, verbose_name="Адреса НП клієнта")
    
    # Информация о заказе
    order_number = models.CharField(max_length=20, unique=True, blank=True, verbose_name="Номер замовлення")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name="Статус")
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='unpaid', verbose_name="Статус оплати")
    
    # Финансовая информация
    total_drop_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Загальна ціна дропа")
    total_selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Загальна ціна продажу")
    profit = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Прибуток")
    
    # Информация об оплате
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cod', verbose_name="Спосіб оплати")
    prepayment_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Сума передоплати")
    dropshipper_payment_required = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Дропшипер має сплатити")
    monobank_invoice_id = models.CharField(max_length=100, blank=True, null=True, verbose_name="ID інвойсу Monobank")
    
    # Дополнительная информация
    notes = models.TextField(blank=True, null=True, verbose_name="Примітки")
    order_source = models.CharField(max_length=500, blank=True, null=True, verbose_name="Джерело замовлення")
    tracking_number = models.CharField(max_length=50, blank=True, null=True, verbose_name="Номер ТТН")
    shipment_status = models.CharField(max_length=100, blank=True, null=True, verbose_name='Статус НП')
    shipment_status_updated = models.DateTimeField(null=True, blank=True, verbose_name='Оновлення статусу НП')
    payout_processed = models.BooleanField(default=False, verbose_name="Виплату оброблено")
    
    # Временные метки
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата створення")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата оновлення")
    
    class Meta:
        verbose_name = "Замовлення дропшипера"
        verbose_name_plural = "Замовлення дропшиперів"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at'], name='dropship_ord_created'),
            models.Index(fields=['status', '-created_at'], name='dropship_ord_status'),
            models.Index(fields=['payment_status', '-created_at'], name='dropship_ord_payment'),
        ]
    
    def __str__(self):
        return f"Дропшип замовлення #{self.order_number} - {self.client_name}"
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()
        super().save(*args, **kwargs)
    
    def generate_order_number(self):
        """Генерирует уникальный номер заказа дропшипера"""
        from django.utils import timezone
        today = timezone.localdate()
        date_str = today.strftime('%d%m%Y')
        counter = 1
        
        while True:
            number = f"DS{date_str}{counter:03d}"
            if not DropshipperOrder.objects.filter(order_number=number).exists():
                return number
            counter += 1
    
    def calculate_profit(self):
        """Рассчитывает прибыль от заказа"""
        self.profit = self.total_selling_price - self.total_drop_price
        return self.profit
    
    def calculate_dropshipper_payment(self):
        """Рассчитывает сумму которую должен оплатить дропшипер"""
        if self.payment_method == 'prepaid':
            # Товар оплачено - дропшипер платит полную стоимость дропа
            self.dropshipper_payment_required = self.total_drop_price
            self.prepayment_amount = 0
        elif self.payment_method == 'cod':
            # Накладний платіж - дропшипер платит предоплату 200 грн
            self.prepayment_amount = 200
            self.dropshipper_payment_required = 200
        else:  # delegation - повне делегування
            # Ми все беремо на себе - дропшипер нічого не платить
            self.prepayment_amount = 0
            self.dropshipper_payment_required = 0
        
        return self.dropshipper_payment_required
    
    def get_payment_method_display_detailed(self):
        """Возвращает детальное описание способа оплаты"""
        if self.payment_method == 'prepaid':
            return f"Товар оплачено (дропшипер сплачує {self.total_drop_price} грн)"
        elif self.payment_method == 'cod':
            return f"Накладний платіж (200 грн вираховується з суми при отриманні)"
        else:  # delegation
            return "Повне делегування (0 грн - всі ризики на нас)"
    
    def process_payout(self):
        """Обрабатывает выплату дропшиперу при получении товара"""
        if self.payout_processed:
            return False, "Виплату вже оброблено"
        
        # Рассчитываем сумму выплаты
        payout_amount = self.profit
        
        # Для COD вычитаем 200 грн (предоплату)
        if self.payment_method == 'cod':
            payout_amount = self.profit - 200
        
        # Создаем выплату
        from decimal import Decimal
        if payout_amount > 0:
            payout = DropshipperPayout.objects.create(
                dropshipper=self.dropshipper,
                amount=Decimal(str(payout_amount)),
                status='pending',
                description=f"Виплата за замовлення #{self.order_number}",
                order=self
            )
            
            self.payout_processed = True
            self.save(update_fields=['payout_processed'])
            
            return True, f"Створено виплату на суму {payout_amount} грн"
        
        return False, "Сума виплати <= 0"
    
    def update_status_on_payment(self):
        """Обновляет статус заказа после оплаты"""
        if self.payment_status == 'paid':
            if self.payment_method in ['prepaid', 'cod']:
                # Для предоплаты и COD переводим в "Ожидает отправки"
                self.status = 'awaiting_shipment'
            else:  # delegation
                # Для делегирования сразу в "Подтверждено"
                self.status = 'confirmed'
            self.save(update_fields=['status'])
            return True
        return False
    
    def check_np_status_and_update(self):
        """Проверяет статус НП и обновляет статус заказа"""
        if not self.tracking_number:
            return False, "ТТН не вказано"
        
        try:
            from .nova_poshta_service import NovaPoshtaService
            np_service = NovaPoshtaService()
            status_info = np_service.track_parcel(self.tracking_number)
            
            if not status_info:
                return False, "Не вдалося отримати статус"
            
            old_status = self.shipment_status
            self.shipment_status = status_info.get('Status', '')
            self.shipment_status_updated = timezone.now()
            
            # Обновляем статус заказа на основе статуса НП
            np_status_code = status_info.get('StatusCode', 0)
            
            # 3 - Прибыло в отделение
            # 9 - Получено
            # 10 - Возвращено отправителю
            # 11 - Отказ от получения
            
            if np_status_code == 3:
                self.status = 'delivered_awaiting_pickup'
            elif np_status_code == 9:
                self.status = 'received'
                # Обрабатываем выплату только если еще не обработана
                if not self.payout_processed:
                    self.process_payout()
            elif np_status_code in [10, 11]:
                self.status = 'refused'
            
            self.save()
            
            return True, f"Статус оновлено: {old_status} -> {self.shipment_status}"
        
        except Exception as e:
            return False, f"Помилка: {str(e)}"


class DropshipperOrderItem(models.Model):
    """Элемент заказа дропшипера"""
    order = models.ForeignKey(DropshipperOrder, on_delete=models.CASCADE, related_name='items', verbose_name="Замовлення")
    product = models.ForeignKey('storefront.Product', on_delete=models.PROTECT, verbose_name="Товар")
    color_variant = models.ForeignKey('productcolors.ProductColorVariant', on_delete=models.PROTECT, null=True, blank=True, verbose_name="Колір")
    size = models.CharField(max_length=16, verbose_name="Розмір")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Кількість")
    
    # Цены
    drop_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Ціна дропа")
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Ціна продажу")
    recommended_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Рекомендована ціна")
    
    # Итоговые суммы
    total_drop_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Загальна ціна дропа")
    total_selling_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Загальна ціна продажу")
    item_profit = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Прибуток з товару")
    
    class Meta:
        verbose_name = "Товар в замовленні дропшипера"
        verbose_name_plural = "Товари в замовленнях дропшиперів"
        ordering = ['id']
    
    def __str__(self):
        return f"{self.product.title} - {self.size} x{self.quantity}"
    
    def save(self, *args, **kwargs):
        # Рассчитываем итоговые суммы
        self.total_drop_price = self.drop_price * self.quantity
        self.total_selling_price = self.selling_price * self.quantity
        self.item_profit = self.total_selling_price - self.total_drop_price
        super().save(*args, **kwargs)


class DropshipperStats(models.Model):
    """Статистика дропшипера"""
    dropshipper = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='dropshipper_stats', verbose_name="Дропшипер")
    
    # Общая статистика
    total_orders = models.PositiveIntegerField(default=0, verbose_name="Всього замовлень")
    completed_orders = models.PositiveIntegerField(default=0, verbose_name="Виконаних замовлень")
    cancelled_orders = models.PositiveIntegerField(default=0, verbose_name="Скасованих замовлень")
    
    # Финансовая статистика
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Загальний дохід")
    total_profit = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Загальний прибуток")
    total_drop_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Загальна собівартість")
    
    # Статистика по товарам
    total_items_sold = models.PositiveIntegerField(default=0, verbose_name="Всього товарів продано")
    
    # Временные метки
    last_order_date = models.DateTimeField(null=True, blank=True, verbose_name="Дата останнього замовлення")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата створення")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата оновлення")
    
    class Meta:
        verbose_name = "Статистика дропшипера"
        verbose_name_plural = "Статистика дропшиперів"
    
    def __str__(self):
        return f"Статистика {self.dropshipper.username}"
    
    def update_stats(self):
        """Обновляет статистику на основе заказов"""
        orders = DropshipperOrder.objects.filter(dropshipper=self.dropshipper)
        
        self.total_orders = orders.count()
        self.completed_orders = orders.filter(status='delivered').count()
        self.cancelled_orders = orders.filter(status='cancelled').count()
        
        # Финансовая статистика
        self.total_revenue = sum(order.total_selling_price for order in orders.filter(status='delivered'))
        self.total_drop_cost = sum(order.total_drop_price for order in orders.filter(status='delivered'))
        self.total_profit = self.total_revenue - self.total_drop_cost
        
        # Статистика по товарам
        self.total_items_sold = sum(
            sum(item.quantity for item in order.items.all()) 
            for order in orders.filter(status='delivered')
        )
        
        # Дата последнего заказа
        last_order = orders.order_by('-created_at').first()
        if last_order:
            self.last_order_date = last_order.created_at
        
        self.save()


class DropshipperPayout(models.Model):
    """Выплаты дропшиперам"""
    STATUS_CHOICES = [
        ('pending', 'Очікує виплати'),
        ('processing', 'В обробці'),
        ('completed', 'Виплачено'),
        ('cancelled', 'Скасовано'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('card', 'На картку'),
        ('bank', 'Банківський переказ'),
        ('cash', 'Готівка'),
        ('crypto', 'Криптовалюта'),
    ]
    
    dropshipper = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='dropshipper_payouts', verbose_name="Дропшипер")
    order = models.ForeignKey(DropshipperOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name='single_payout', verbose_name="Замовлення")
    
    # Информация о выплате
    payout_number = models.CharField(max_length=20, unique=True, blank=True, verbose_name="Номер виплати")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Сума виплати")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Статус")
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True, null=True, verbose_name="Спосіб виплати")
    description = models.CharField(max_length=500, blank=True, verbose_name="Опис")
    
    # Детали выплаты
    payment_details = models.CharField(max_length=500, blank=True, null=True, verbose_name="Деталі виплати (номер картки/рахунку)")
    notes = models.TextField(blank=True, null=True, verbose_name="Примітки")
    
    # Заказы, включенные в выплату
    included_orders = models.ManyToManyField(DropshipperOrder, related_name='payouts', blank=True, verbose_name="Включені замовлення")
    
    # Временные метки
    requested_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата запиту")
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата обробки")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата виплати")
    
    class Meta:
        verbose_name = "Виплата дропшипера"
        verbose_name_plural = "Виплати дропшиперів"
        ordering = ['-requested_at']
    
    def __str__(self):
        return f"Виплата #{self.payout_number} - {self.dropshipper.username} ({self.amount} грн)"
    
    def save(self, *args, **kwargs):
        if not self.payout_number:
            self.payout_number = self.generate_payout_number()
        super().save(*args, **kwargs)
    
    def generate_payout_number(self):
        """Генерирует уникальный номер выплаты"""
        from django.utils import timezone
        today = timezone.localdate()
        date_str = today.strftime('%d%m%Y')
        counter = 1
        
        while True:
            number = f"PY{date_str}{counter:03d}"
            if not DropshipperPayout.objects.filter(payout_number=number).exists():
                return number
            counter += 1
