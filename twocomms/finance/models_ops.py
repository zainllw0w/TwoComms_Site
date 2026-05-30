"""Інтеграції, автоправила, бюджети, фінпоказники та аудит-лог."""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models

from .models_core import Category, Company


class IntegrationConnection(models.Model):
    """Підключення банку/сервісу. Реальні API підключаються пізніше;
    на цьому етапі — каркас з QR/статусами та ручним імпортом."""

    PROVIDER_CHOICES = [
        ('privatbank', 'PrivatBank Business'),
        ('monobank', 'monobank'),
        ('mono_business', 'ТОВ monobank'),
        ('novapay', 'NovaPay'),
        ('pumb', 'ПУМБ'),
        ('credit_dnipro', 'Credit Dnipro'),
        ('ukrgasbank', 'Укргазбанк'),
        ('payoneer', 'Payoneer'),
        ('wise', 'Wise'),
        ('crypto', 'Криптогаманець'),
        ('tron', 'TRON'),
        ('fondy', 'Fondy'),
        ('western_bid', 'Western Bid'),
        ('checkbox', 'Checkbox'),
        ('poster', 'Poster'),
        ('vchasno_kasa', 'Вчасно.Каса'),
        ('hutko', 'Hutko'),
        ('manual_import', 'Ручний імпорт'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Очікує підключення'),
        ('waiting_for_scan', 'Очікує сканування'),
        ('connecting', 'Підключення'),
        ('success', 'Підключено'),
        ('error', 'Помилка'),
        ('timeout', 'Час вийшов'),
        ('disconnected', 'Відключено'),
    ]

    METHOD_CHOICES = [
        ('qr', 'QR-код'),
        ('token', 'API-токен'),
        ('manual', 'Ручний імпорт'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='integrations')
    provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    connection_method = models.CharField(max_length=12, choices=METHOD_CHOICES, default='qr')
    provider_account_id = models.CharField(max_length=128, blank=True, default='')
    credentials_ref = models.CharField(max_length=128, blank=True, default='')

    # --- Зашифрований доступ через API-токен (напр. Monobank Personal) ---
    # Сам токен НІКОЛИ не зберігається у відкритому вигляді: лише Fernet-шифротекст.
    encrypted_token = models.TextField(blank=True, default='')
    token_fingerprint = models.CharField(max_length=32, blank=True, default='', db_index=True)
    token_mask = models.CharField(max_length=32, blank=True, default='')
    # Випадковий секрет у шляху URL вебхука — захист від підробних викликів.
    webhook_secret = models.CharField(max_length=64, blank=True, default='')
    webhook_url = models.URLField(blank=True, default='')
    auto_sync = models.BooleanField(default=True)
    # Дані клієнта від провайдера (ім'я, ідентифікатор) — для відображення.
    client_name = models.CharField(max_length=255, blank=True, default='')
    external_client_id = models.CharField(max_length=128, blank=True, default='')
    meta = models.JSONField(default=dict, blank=True)

    sync_from = models.DateField(blank=True, null=True)
    last_sync_at = models.DateTimeField(blank=True, null=True)
    error_message = models.CharField(max_length=512, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Інтеграція'
        verbose_name_plural = 'Інтеграції'

    def __str__(self):
        return f'{self.get_provider_display()} ({self.get_status_display()})'

    # --- Робота з токеном через сервіс шифрування ---
    def set_token(self, raw_token: str) -> None:
        """Шифрує і зберігає токен (+ відбиток і маску). Не save() сам по собі."""
        from .services import crypto
        self.encrypted_token = crypto.encrypt(raw_token)
        self.token_fingerprint = crypto.fingerprint(raw_token)
        self.token_mask = crypto.mask(raw_token)

    def get_token(self) -> str:
        """Розшифровує збережений токен (кидає TokenCryptoError за невдачі)."""
        from .services import crypto
        return crypto.decrypt(self.encrypted_token)

    @property
    def has_token(self) -> bool:
        return bool(self.encrypted_token)


class AutomationRule(models.Model):
    """Автоправило: умови (AND) → дії над операцією."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='automation_rules')
    name = models.CharField(max_length=255)
    transaction_type = models.CharField(max_length=12, blank=True, default='',
                                        help_text='income/expense/transfer або порожнє=будь-який')
    is_enabled = models.BooleanField(default=True)
    priority = models.IntegerField(default=100)
    conditions = models.JSONField(default=list, blank=True)  # [{field, operator, value}]
    actions = models.JSONField(default=list, blank=True)     # [{action, field, value, overwrite}]
    apply_to_existing = models.BooleanField(default=False)
    applied_count = models.PositiveIntegerField(default=0)
    is_demo = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Автоправило'
        verbose_name_plural = 'Автоправила'
        ordering = ['priority', 'id']

    def __str__(self):
        return self.name


class RuleApplication(models.Model):
    """Історія застосування автоправила (для аудиту й відкату)."""

    rule = models.ForeignKey(AutomationRule, on_delete=models.CASCADE, related_name='applications')
    transaction = models.ForeignKey('finance.Transaction', on_delete=models.CASCADE,
                                    related_name='rule_applications')
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    source = models.CharField(max_length=16, default='auto')  # auto/manual/bulk
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   blank=True, null=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    reverted = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Застосування правила'
        verbose_name_plural = 'Застосування правил'
        ordering = ['-created_at']


class BudgetPlan(models.Model):
    """План бюджету за період/категорією/проєктом (для звіту План/Факт)."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='budget_plans')
    period_start = models.DateField()
    period_end = models.DateField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE, blank=True, null=True,
                                 related_name='budget_plans')
    project = models.ForeignKey('finance.Project', on_delete=models.CASCADE, blank=True, null=True,
                                related_name='budget_plans')
    planned_income = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))
    planned_expense = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))
    is_demo = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Бюджетний план'
        verbose_name_plural = 'Бюджетні плани'


class FinancialMetric(models.Model):
    """Налаштовуваний фінансовий показник (KPI)."""

    PERIOD_CHOICES = [
        ('month', 'Місяць'),
        ('quarter', 'Квартал'),
        ('year', 'Рік'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='metrics')
    name = models.CharField(max_length=255)
    formula = models.CharField(max_length=64, default='income_minus_expense')
    income_categories = models.ManyToManyField(Category, blank=True, related_name='metric_income')
    expense_categories = models.ManyToManyField(Category, blank=True, related_name='metric_expense')
    period = models.CharField(max_length=12, choices=PERIOD_CHOICES, default='month')
    display_order = models.PositiveIntegerField(default=0)
    is_demo = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Фінансовий показник'
        verbose_name_plural = 'Фінансові показники'
        ordering = ['display_order', 'id']

    def __str__(self):
        return self.name


class AuditLog(models.Model):
    """Журнал дій (історія дій / audit log)."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='audit_logs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True,
                             null=True, related_name='+')
    action = models.CharField(max_length=32)  # create/update/delete/import/apply_rule/...
    entity_type = models.CharField(max_length=64)
    entity_id = models.CharField(max_length=64, blank=True, default='')
    summary = models.CharField(max_length=512, blank=True, default='')
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    source = models.CharField(max_length=16, default='manual')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Запис аудиту'
        verbose_name_plural = 'Історія дій'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['company', 'entity_type', '-created_at'])]

    def __str__(self):
        return f'{self.action} {self.entity_type}#{self.entity_id}'
