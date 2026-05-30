"""Базові довідники фінансового кабінету: компанія, валюти, рахунки,
категорії, контрагенти, проєкти, теги.

Усі сутності прив'язані до Company (на майбутнє — мультикомпанійність),
але UI працює з єдиною компанією TwoComms (див. get_default_company).
"""
from __future__ import annotations

from decimal import Decimal

from django.db import models


class Company(models.Model):
    """Компанія (організація). Наразі використовується єдиний екземпляр."""

    name = models.CharField(max_length=255, default='TwoComms')
    logo = models.ImageField(upload_to='finance/company/', blank=True, null=True)
    base_currency = models.CharField(max_length=3, default='UAH')
    settings = models.JSONField(default=dict, blank=True)
    is_demo = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Компанія'
        verbose_name_plural = 'Компанії'

    def __str__(self):
        return self.name


def get_default_company() -> 'Company':
    """Повертає (створює за потреби) єдину компанію кабінету."""
    company = Company.objects.order_by('id').first()
    if company is None:
        company = Company.objects.create(name='TwoComms', base_currency='UAH')
    return company


class CurrencyRate(models.Model):
    """Курс валют для перерахунку у базову валюту компанії."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='currency_rates')
    currency_from = models.CharField(max_length=3)
    currency_to = models.CharField(max_length=3)
    rate = models.DecimalField(max_digits=18, decimal_places=6)
    date = models.DateField()
    source = models.CharField(max_length=64, blank=True, default='manual')

    class Meta:
        verbose_name = 'Курс валют'
        verbose_name_plural = 'Курси валют'
        ordering = ['-date']
        indexes = [models.Index(fields=['currency_from', 'currency_to', 'date'])]

    def __str__(self):
        return f'{self.currency_from}->{self.currency_to} {self.rate} ({self.date})'


class Account(models.Model):
    """Рахунок: банк, готівка, картка, гаманець, маркетплейс тощо."""

    TYPE_CHOICES = [
        ('bank', 'Банк'),
        ('cash', 'Готівка'),
        ('card', 'Картка'),
        ('wallet', 'Гаманець'),
        ('marketplace', 'Маркетплейс'),
        ('warehouse', 'Склад'),
        ('employee_money', 'Гроші у співробітника'),
        ('other', 'Інше'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='accounts')
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='bank')
    currency = models.CharField(max_length=3, default='UAH')
    initial_balance = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))
    initial_balance_date = models.DateField(blank=True, null=True)
    current_balance = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))
    is_active = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)
    integration = models.ForeignKey(
        'finance.IntegrationConnection', on_delete=models.SET_NULL,
        blank=True, null=True, related_name='accounts',
    )
    # Прив'язка до зовнішнього рахунку провайдера (Monobank account id / jar id).
    external_account_id = models.CharField(max_length=128, blank=True, default='', db_index=True)
    external_kind = models.CharField(max_length=16, blank=True, default='')  # card/fop/jar
    iban = models.CharField(max_length=64, blank=True, default='')
    masked_pan = models.CharField(max_length=32, blank=True, default='')
    # Бізнес vs особистий рахунок. ФОП-рахунки — завжди бізнес; на звичайних
    # картках операції особисті за замовчуванням (можна перемикати поштучно).
    is_business = models.BooleanField(default=False)
    auto_sync = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_demo = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Рахунок'
        verbose_name_plural = 'Рахунки'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f'{self.name} ({self.currency})'

    def recalc_balance(self, save: bool = True) -> Decimal:
        """Перерахунок поточного балансу з фактичних транзакцій.

        current_balance = initial_balance + actual_income - actual_expense
                          + transfers_in - transfers_out
        Планові транзакції не враховуються (див. ТЗ §2.1).
        """
        from .models_txn import Transaction

        agg = {'income': Decimal('0'), 'expense': Decimal('0'),
               'tin': Decimal('0'), 'tout': Decimal('0')}

        actual = Transaction.objects.filter(status=Transaction.STATUS_ACTUAL)
        # Доходи на цей рахунок.
        agg['income'] = actual.filter(
            type=Transaction.TYPE_INCOME, account=self,
        ).aggregate(s=models.Sum('amount'))['s'] or Decimal('0')
        # Витрати з цього рахунку.
        agg['expense'] = actual.filter(
            type=Transaction.TYPE_EXPENSE, account=self,
        ).aggregate(s=models.Sum('amount'))['s'] or Decimal('0')
        # Перекази, що надходять (to_account) — рахуються у валюті отримувача.
        agg['tin'] = actual.filter(
            type=Transaction.TYPE_TRANSFER, to_account=self,
        ).aggregate(s=models.Sum('to_amount'))['s'] or Decimal('0')
        # Перекази, що виходять (account) — у валюті відправника.
        agg['tout'] = actual.filter(
            type=Transaction.TYPE_TRANSFER, account=self,
        ).aggregate(s=models.Sum('amount'))['s'] or Decimal('0')

        balance = (self.initial_balance + agg['income'] - agg['expense']
                   + agg['tin'] - agg['tout'])
        self.current_balance = balance
        if save:
            Account.objects.filter(pk=self.pk).update(current_balance=balance)
        return balance


class Category(models.Model):
    """Категорія доходу/витрати. Може бути вкладеною (parent)."""

    TYPE_INCOME = 'income'
    TYPE_EXPENSE = 'expense'
    TYPE_BOTH = 'both'
    TYPE_CHOICES = [
        (TYPE_INCOME, 'Дохід'),
        (TYPE_EXPENSE, 'Витрата'),
        (TYPE_BOTH, 'Обидва'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TYPE_EXPENSE)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, blank=True, null=True,
                               related_name='children')
    color = models.CharField(max_length=16, blank=True, default='')
    icon = models.CharField(max_length=32, blank=True, default='')
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_demo = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Категорія'
        verbose_name_plural = 'Категорії'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class Counterparty(models.Model):
    """Контрагент (клієнт/постачальник/інше)."""

    TYPE_CHOICES = [
        ('client', 'Клієнт'),
        ('supplier', 'Постачальник'),
        ('employee', 'Співробітник'),
        ('government', 'Держоргани'),
        ('other', 'Інше'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='counterparties')
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='client')
    group = models.CharField(max_length=128, blank=True, default='')
    edrpou = models.CharField(max_length=32, blank=True, default='')
    iban = models.CharField(max_length=64, blank=True, default='')
    country = models.CharField(max_length=64, blank=True, default='')
    address = models.CharField(max_length=512, blank=True, default='')
    contacts = models.JSONField(default=dict, blank=True)
    is_demo = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Контрагент'
        verbose_name_plural = 'Контрагенти'
        ordering = ['name']

    def __str__(self):
        return self.name


class Project(models.Model):
    """Проєкт/напрям (PromUA, Instagram, Rozetka, власний магазин тощо)."""

    STATUS_CHOICES = [
        ('active', 'Активний'),
        ('paused', 'Призупинений'),
        ('archived', 'Архівний'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='projects')
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='active')
    color = models.CharField(max_length=16, blank=True, default='')
    sort_order = models.PositiveIntegerField(default=0)
    is_demo = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Проєкт'
        verbose_name_plural = 'Проєкти'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class Tag(models.Model):
    """Тег операції. Одна операція може мати кілька тегів."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='tags')
    name = models.CharField(max_length=128)
    color = models.CharField(max_length=16, blank=True, default='')
    is_demo = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Тег'
        verbose_name_plural = 'Теги'
        ordering = ['name']

    def __str__(self):
        return self.name
