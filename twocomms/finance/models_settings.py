"""Моделі для налаштувань користувача та push-повідомлень."""
from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class UserSettings(models.Model):
    """Налаштування користувача фінансового кабінету."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='finance_settings',
        verbose_name='Користувач'
    )

    # Push-повідомлення
    push_enabled = models.BooleanField(default=False, verbose_name='Push увімкнено')
    push_daily_enabled = models.BooleanField(default=False, verbose_name='Щоденний звіт')
    push_daily_time = models.TimeField(default='20:00', verbose_name='Час щоденного звіту')
    push_weekly_enabled = models.BooleanField(default=False, verbose_name='Тижневий звіт')
    push_weekly_day = models.IntegerField(
        default=1,
        choices=[
            (0, 'Неділя'),
            (1, 'Понеділок'),
            (2, 'Вівторок'),
            (3, 'Середа'),
            (4, 'Четвер'),
            (5, 'П\'ятниця'),
            (6, 'Субота'),
        ],
        verbose_name='День тижневого звіту'
    )
    # Час тижневого звіту (раніше прив'язувався до часу щоденного).
    push_weekly_time = models.TimeField(default='10:00', verbose_name='Час тижневого звіту')
    # Сповіщення про критичні ризики здоров'я (касовий розрив, прострочка, збиток).
    push_health_alerts = models.BooleanField(
        default=True, verbose_name='Сповіщення про фінансові ризики')
    # Нагадування про планові платежі (за день до дати).
    push_planned_reminders = models.BooleanField(
        default=False, verbose_name='Нагадування про планові платежі')
    # Сповіщення про великі операції (понад поріг) під час синку банку.
    push_large_txn = models.BooleanField(
        default=False, verbose_name='Сповіщення про великі операції')
    push_large_txn_threshold = models.DecimalField(
        max_digits=18, decimal_places=2, default=10000,
        verbose_name='Поріг великої операції')
    telegram_notifications = models.BooleanField(
        default=False,
        verbose_name='Дублювати в Telegram'
    )

    # Метадані
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Створено')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Оновлено')

    class Meta:
        db_table = 'finance_user_settings'
        verbose_name = 'Налаштування користувача'
        verbose_name_plural = 'Налаштування користувачів'

    def __str__(self):
        return f'Налаштування {self.user.username}'


class PushSubscription(models.Model):
    """Push-підписка користувача (Web Push API)."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='push_subscriptions',
        verbose_name='Користувач'
    )

    endpoint = models.URLField(max_length=500, verbose_name='Endpoint')
    p256dh = models.CharField(max_length=255, verbose_name='P256DH ключ')
    auth = models.CharField(max_length=255, verbose_name='Auth ключ')

    # Метадані
    user_agent = models.CharField(max_length=500, blank=True, verbose_name='User Agent')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Створено')
    last_used = models.DateTimeField(auto_now=True, verbose_name='Останнє використання')
    is_active = models.BooleanField(default=True, verbose_name='Активна')

    class Meta:
        db_table = 'finance_push_subscriptions'
        verbose_name = 'Push-підписка'
        verbose_name_plural = 'Push-підписки'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'endpoint'],
                name='unique_user_endpoint',
            ),
        ]

    def __str__(self):
        return f'Push-підписка {self.user.username}'


class NotificationLog(models.Model):
    """Лог відправлених повідомлень."""

    NOTIFICATION_TYPES = [
        ('daily', 'Щоденний звіт'),
        ('weekly', 'Тижневий звіт'),
        ('planned', 'Нагадування про платежі'),
        ('large_txn', 'Велика операція'),
        ('custom', 'Кастомне повідомлення'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notification_logs',
        verbose_name='Користувач'
    )

    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPES,
        verbose_name='Тип повідомлення'
    )
    title = models.CharField(max_length=255, verbose_name='Заголовок')
    body = models.TextField(verbose_name='Текст')

    # Статус відправки
    sent_at = models.DateTimeField(auto_now_add=True, verbose_name='Відправлено')
    success = models.BooleanField(default=True, verbose_name='Успішно')
    error_message = models.TextField(blank=True, verbose_name='Помилка')

    # Дані звіту (JSON)
    report_data = models.JSONField(null=True, blank=True, verbose_name='Дані звіту')

    class Meta:
        db_table = 'finance_notification_logs'
        verbose_name = 'Лог повідомлень'
        verbose_name_plural = 'Логи повідомлень'
        ordering = ['-sent_at']

    def __str__(self):
        return f'{self.get_notification_type_display()} для {self.user.username}'
