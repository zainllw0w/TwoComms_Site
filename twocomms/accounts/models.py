from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=32, blank=True)
    city = models.CharField(max_length=100, blank=True)
    np_office = models.CharField(max_length=200, blank=True)
    pay_type = models.CharField(max_length=10, choices=[
        ('full', 'Повна оплата'),
        ('partial', 'Часткова оплата')
    ], default='full')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    full_name = models.CharField(max_length=200, blank=True)
    email = models.EmailField(max_length=254, blank=True, verbose_name='Email')
    telegram = models.CharField(max_length=100, blank=True, verbose_name='Telegram')
    telegram_id = models.BigIntegerField(null=True, blank=True, verbose_name='Telegram ID')
    instagram = models.CharField(max_length=100, blank=True, verbose_name='Instagram')
    is_ubd = models.BooleanField(default=False, verbose_name='УБД')
    ubd_doc = models.ImageField(upload_to='ubd_docs/', blank=True, null=True, verbose_name='Фото посвідчення УБД')
    # Менеджмент-бот
    tg_manager_chat_id = models.BigIntegerField(null=True, blank=True, verbose_name='Telegram Management Chat ID')
    tg_manager_username = models.CharField(max_length=255, blank=True, verbose_name='Telegram Management Username')
    tg_manager_bind_code = models.CharField(max_length=64, blank=True, verbose_name='Код привʼязки менеджмент-бота')
    tg_manager_bind_expires_at = models.DateTimeField(null=True, blank=True, verbose_name='Діє до')
    is_manager = models.BooleanField(default=False, verbose_name='Менеджер (доступ до Management)')
    
    # Поля для оптовых заказов
    company_name = models.CharField(max_length=200, blank=True, verbose_name='Назва компанії/ФОП/ПІБ')
    company_number = models.CharField(max_length=50, blank=True, verbose_name='Номер компанії/ЄДРПОУ/ІПН')
    delivery_address = models.TextField(blank=True, verbose_name='Адреса доставки')
    website = models.URLField(blank=True, null=True, verbose_name='Посилання на магазин')
    payment_method = models.CharField(max_length=20, choices=[('card', 'На картку'), ('iban', 'IBAN')], default='card', verbose_name='Спосіб виплати')
    payment_details = models.TextField(blank=True, verbose_name='Реквізити для виплат')

    class Meta:
        indexes = [
            models.Index(fields=['telegram_id'], name='idx_userprofile_telegram'),
            models.Index(fields=['phone'], name='idx_userprofile_phone'),
            models.Index(fields=['user', 'is_ubd'], name='idx_userprofile_user_ubd'),
        ]

    def __str__(self):
        return f'Profile for {self.user.username}'


class UserPoints(models.Model):
    """Модель для хранения баллов пользователей"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='points')
    points = models.PositiveIntegerField(default=0, verbose_name='Кількість балів')
    total_earned = models.PositiveIntegerField(default=0, verbose_name='Всього зароблено балів')
    total_spent = models.PositiveIntegerField(default=0, verbose_name='Всього витрачено балів')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Створено')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Оновлено')

    class Meta:
        verbose_name = 'Бали користувача'
        verbose_name_plural = 'Бали користувачів'

    def __str__(self):
        return f'{self.user.username} - {self.points} балів'

    def add_points(self, amount, reason=''):
        """Добавляет баллы пользователю"""
        self.points += amount
        self.total_earned += amount
        self.save()
        
        # Создаем запись в истории баллов
        PointsHistory.objects.create(
            user=self.user,
            points_change=amount,
            balance_after=self.points,
            reason=reason,
            change_type='earned'
        )

    def spend_points(self, amount, reason=''):
        """Тратит баллы пользователя"""
        if self.points >= amount:
            self.points -= amount
            self.total_spent += amount
            self.save()
            
            # Создаем запись в истории баллов
            PointsHistory.objects.create(
                user=self.user,
                points_change=-amount,
                balance_after=self.points,
                reason=reason,
                change_type='spent'
            )
            return True
        return False

    @classmethod
    def get_or_create_points(cls, user):
        """Получает или создает объект баллов для пользователя"""
        points, created = cls.objects.get_or_create(user=user)
        return points

class PointsHistory(models.Model):
    """История изменений баллов пользователя"""
    CHANGE_TYPES = [
        ('earned', 'Зароблено'),
        ('spent', 'Витрачено'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='points_history')
    points_change = models.IntegerField(verbose_name='Зміна балів')
    balance_after = models.PositiveIntegerField(verbose_name='Баланс після зміни')
    reason = models.CharField(max_length=255, blank=True, verbose_name='Причина')
    change_type = models.CharField(max_length=10, choices=CHANGE_TYPES, verbose_name='Тип зміни')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Створено')

    class Meta:
        verbose_name = 'Історія балів'
        verbose_name_plural = 'Історія балів'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} - {self.points_change} балів ({self.get_change_type_display()})'


class FavoriteProduct(models.Model):
    """Модель для избранных товаров пользователя"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites')
    product = models.ForeignKey('storefront.Product', on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Додано до обраного')

    class Meta:
        verbose_name = 'Обраний товар'
        verbose_name_plural = 'Обрані товари'
        unique_together = ['user', 'product']  # Пользователь может добавить товар в избранное только один раз
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} - {self.product.title}'


# Signal to create UserProfile and UserPoints when a new User is created
@receiver(post_save, sender=User)
def create_user_related_models(sender, instance, created, **kwargs):
    """
    Automatically creates UserProfile and UserPoints for new users.
    
    Note: UserProfile is linked via OneToOneField, so it will be auto-created
    if accessed via instance.userprofile. However, we create it explicitly here
    to ensure it exists immediately after user creation.
    """
    if created:
        UserProfile.objects.get_or_create(user=instance)
        UserPoints.objects.get_or_create(user=instance)
