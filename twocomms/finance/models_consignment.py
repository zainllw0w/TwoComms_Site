"""Модуль «Магазини під реалізацію» (consignment).

Магазини-реалізатори — це контрагенти, яким ми віддаємо товар:
- під реалізацію (заморожені гроші, залежать від продажу);
- у борг з виплатами;
- як тестову партію.

Ключова ідея обліку: **борг магазину = планові income-транзакції**
(``Transaction`` type=income, status=planned, source='consignment',
reseller=...). Це автоматично потрапляє в дебіторку (``reports_debt``),
прогноз балансу (``balances.planned_totals``) та календар — без дублювання
логіки. Усі грошові рухи проходять через ``services/transactions.py``.

Заморожені під реалізацію товари — окрема сутність (``ConsignmentItem``),
рахується агрегатом ``(qty - sold_qty) * unit_cost`` за патерном
``warehouse_link.frozen_in_warehouse`` і показується окремим рядком
поряд зі «складом» (не змішується з ним).
"""
from __future__ import annotations

from decimal import Decimal

from django.db import models

from .models_core import Company, Counterparty


class Reseller(models.Model):
    """Магазин-реалізатор: кому віддаємо товар під реалізацію/у борг."""

    STATUS_ACTIVE = 'active'
    STATUS_PAUSED = 'paused'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Активний'),
        (STATUS_PAUSED, 'Призупинено'),
        (STATUS_CLOSED, 'Закрито'),
    ]

    # Тип умов оплати (опис графіку зберігається у JSON ``terms``).
    TERMS_ONETIME = 'onetime'        # віддати протягом N днів
    TERMS_INSTALLMENT = 'installment'  # розстрочка раз на місяць/тиждень
    TERMS_PERIODIC = 'periodic'      # безстроково періодично (сума необов'язкова)
    TERMS_CHOICES = [
        (TERMS_ONETIME, 'Одноразово (через N днів)'),
        (TERMS_INSTALLMENT, 'Розстрочка (період × сума)'),
        (TERMS_PERIODIC, 'Безстроково періодично'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='resellers')
    name = models.CharField(max_length=255, verbose_name='Назва магазину')
    counterparty = models.ForeignKey(
        Counterparty, on_delete=models.SET_NULL, blank=True, null=True,
        related_name='resellers', verbose_name='Контрагент',
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    terms_kind = models.CharField(max_length=16, choices=TERMS_CHOICES, default=TERMS_INSTALLMENT)
    # Параметри графіку оплати. Формати:
    #   onetime:     {'due_days': 14}
    #   installment: {'period': 'month'|'week', 'every': 1, 'amount': '12000.00',
    #                 'periods': 6|None, 'anchor_day': 5}
    #   periodic:    {'period': 'month'|'week', 'every': 1, 'anchor_day': 5}
    terms = models.JSONField(default=dict, blank=True)
    # Контакти: {'phone': ..., 'telegram': ..., 'responsible': ...}
    contacts = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True, default='')
    is_demo = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Магазин (реалізація)'
        verbose_name_plural = 'Магазини (реалізація)'
        ordering = ['name']
        indexes = [
            models.Index(fields=['company', 'status'], name='idx_reseller_comp_status'),
        ]

    def __str__(self):
        return self.name

    # Property делегують у сервіс, щоб уникнути важких запитів у моделі
    # та не дублювати логіку. Імпорт усередині — щоб не було циклічного.
    @property
    def current_debt(self) -> Decimal:
        from .services import consignment as svc
        return svc.reseller_debt(self)

    @property
    def frozen_value(self) -> Decimal:
        from .services import consignment as svc
        return svc.reseller_frozen(self)

    @property
    def overdue_days(self) -> int:
        from .services import consignment as svc
        return svc.reseller_overdue_days(self)


class ConsignmentShipment(models.Model):
    """Поставка (накладна-відправка) магазину.

    Формує борг магазину (планова income-транзакція ``debt_txn``) та/або
    містить заморожені під реалізацію позиції (``items``).
    """

    company = models.ForeignKey(Company, on_delete=models.CASCADE,
                                related_name='consignment_shipments')
    reseller = models.ForeignKey(Reseller, on_delete=models.CASCADE, related_name='shipments')
    number = models.CharField(max_length=64, blank=True, default='', verbose_name='Номер накладної')
    ttn = models.CharField(max_length=64, blank=True, default='', verbose_name='ТТН Нової Пошти')
    date = models.DateField(verbose_name='Дата відправки')
    # Ручна сума боргу (коли товарів немає в БД — заповнюємо вручну).
    debt_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))
    currency = models.CharField(max_length=3, default='UAH')
    comment = models.TextField(blank=True, default='')
    attachments = models.ManyToManyField(
        'finance.Attachment', blank=True, related_name='consignment_shipments',
    )
    # Планова income-транзакція, що відображає борг цієї поставки.
    debt_txn = models.ForeignKey(
        'finance.Transaction', on_delete=models.SET_NULL, blank=True, null=True,
        related_name='+',
    )
    # Заглушка для майбутньої інтеграції з менеджментом (тестові партії).
    external_source = models.CharField(max_length=16, blank=True, default='')
    external_ref = models.CharField(max_length=64, blank=True, default='')
    is_demo = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Поставка магазину'
        verbose_name_plural = 'Поставки магазинів'
        ordering = ['-date', '-id']
        indexes = [
            models.Index(fields=['company', 'reseller'], name='idx_cons_ship_comp_res'),
        ]

    def __str__(self):
        return f'Поставка №{self.number or self.id} → {self.reseller.name}'

    @property
    def items_debt(self) -> Decimal:
        """Сума боргових (не консигнаційних) позицій."""
        total = Decimal('0')
        for item in self.items.all():
            if not item.is_consignment:
                total += item.line_total
        return total

    @property
    def total_debt(self) -> Decimal:
        return self.debt_amount + self.items_debt


class ConsignmentItem(models.Model):
    """Позиція поставки: товар під реалізацію або в борг.

    ``is_consignment=True``  → заморожує гроші (не борг), борг виникає лише
                               при фіксації продажу (опційно).
    ``is_consignment=False`` → формує борг магазину (line_total).
    """

    SOURCE_MANUAL = 'manual'
    SOURCE_STOCK = 'stock'
    SOURCE_EXTERNAL = 'external'
    SOURCE_CHOICES = [
        (SOURCE_MANUAL, 'Вручну'),
        (SOURCE_STOCK, 'Склад'),
        (SOURCE_EXTERNAL, 'Менеджмент'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE,
                                related_name='consignment_items')
    shipment = models.ForeignKey(ConsignmentShipment, on_delete=models.CASCADE,
                                 related_name='items')
    # Денормалізація для швидких агрегатів по магазину.
    reseller = models.ForeignKey(Reseller, on_delete=models.CASCADE,
                                 related_name='consignment_items')
    source_kind = models.CharField(max_length=12, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    stock_item = models.ForeignKey(
        'warehouse.StockItem', on_delete=models.SET_NULL, blank=True, null=True,
        related_name='+',
    )
    external_ref = models.CharField(max_length=64, blank=True, default='')
    title = models.CharField(max_length=255, verbose_name='Назва')
    print_name = models.CharField(max_length=128, blank=True, default='', verbose_name='Принт')
    color = models.CharField(max_length=64, blank=True, default='', verbose_name='Колір')
    size = models.CharField(max_length=16, blank=True, default='', verbose_name='Розмір')
    qty = models.PositiveIntegerField(default=0, verbose_name='Кількість')
    sold_qty = models.PositiveIntegerField(default=0, verbose_name='Продано')
    unit_cost = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'),
                                    verbose_name='Собівартість за од.')
    unit_price = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'),
                                     verbose_name='Ціна продажу за од.')
    is_consignment = models.BooleanField(default=True, verbose_name='Під реалізацію')
    comment = models.TextField(blank=True, default='')
    is_demo = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Позиція поставки'
        verbose_name_plural = 'Позиції поставок'
        ordering = ['id']
        indexes = [
            models.Index(fields=['reseller', 'is_consignment'], name='idx_cons_item_res_cons'),
            models.Index(fields=['shipment'], name='idx_cons_item_ship'),
        ]

    def __str__(self):
        return f'{self.title} {self.size} × {self.qty}'

    @property
    def remaining_qty(self) -> int:
        return max(0, self.qty - self.sold_qty)

    @property
    def frozen_value(self) -> Decimal:
        """Заморожена сума: лише консигнаційні, лише непродані одиниці."""
        if not self.is_consignment:
            return Decimal('0')
        return Decimal(self.remaining_qty) * self.unit_cost

    @property
    def line_total(self) -> Decimal:
        """Повна вартість позиції (для боргових позицій формує борг)."""
        return Decimal(self.qty) * self.unit_cost

    @property
    def revenue(self) -> Decimal:
        return Decimal(self.sold_qty) * self.unit_price


class ResellerPayment(models.Model):
    """Виплата магазину (журнал погашень боргу).

    Окремо від ``Transaction``, бо одна виплата може гасити кілька планових
    боргів і нам треба зберегти зв'язок «виплата → фактична income-транзакція».
    """

    company = models.ForeignKey(Company, on_delete=models.CASCADE,
                                related_name='reseller_payments')
    reseller = models.ForeignKey(Reseller, on_delete=models.CASCADE, related_name='payments')
    date = models.DateField()
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.CharField(max_length=3, default='UAH')
    txn = models.ForeignKey(
        'finance.Transaction', on_delete=models.SET_NULL, blank=True, null=True,
        related_name='+',
    )
    comment = models.TextField(blank=True, default='')
    is_demo = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Виплата магазину'
        verbose_name_plural = 'Виплати магазинів'
        ordering = ['-date', '-id']

    def __str__(self):
        return f'Виплата {self.amount} {self.currency} ← {self.reseller.name}'


class ConsignmentSale(models.Model):
    """Фіксація продажу позиції товару, що лежала під реалізацію."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE,
                                related_name='consignment_sales')
    reseller = models.ForeignKey(Reseller, on_delete=models.CASCADE, related_name='sales')
    item = models.ForeignKey(ConsignmentItem, on_delete=models.CASCADE, related_name='sales')
    qty = models.PositiveIntegerField()
    date = models.DateField()
    unit_price = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))
    # Чи продаж сформував борг магазину (планова income-транзакція).
    creates_debt = models.BooleanField(default=False)
    debt_txn = models.ForeignKey(
        'finance.Transaction', on_delete=models.SET_NULL, blank=True, null=True,
        related_name='+',
    )
    comment = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Продаж під реалізацію'
        verbose_name_plural = 'Продажі під реалізацію'
        ordering = ['-date', '-id']

    def __str__(self):
        return f'Продаж {self.qty} × {self.item.title} ({self.reseller.name})'
