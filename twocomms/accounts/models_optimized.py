"""
Оптимизированные модели для accounts приложения
"""

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.cache import cache
from django.db.models import Sum, Count, Q

class UserProfileManager(models.Manager):
    """Оптимизированный менеджер для UserProfile"""
    
    def with_user_data(self):
        """Профили с данными пользователя"""
        return self.select_related('user')
    
    def active_users(self):
        """Активные пользователи"""
        return self.filter(user__is_active=True)
    
    def with_avatar(self):
        """Пользователи с аватарами"""
        return self.exclude(avatar__isnull=True).exclude(avatar='')
    
    def get_cached_profile(self, user):
        """Получить профиль из кэша"""
        cache_key = f'user_profile_{user.id}'
        profile = cache.get(cache_key)
        
        if profile is None:
            try:
                profile = self.get(user=user)
                cache.set(cache_key, profile, 300)  # Кэшируем на 5 минут
            except UserProfile.DoesNotExist:
                profile = None
        
        return profile

class UserPointsManager(models.Manager):
    """Оптимизированный менеджер для UserPoints"""
    
    def with_user_data(self):
        """Баллы с данными пользователя"""
        return self.select_related('user')
    
    def top_earners(self, limit=10):
        """Топ зарабатывающих пользователей"""
        return self.order_by('-total_earned')[:limit]
    
    def top_spenders(self, limit=10):
        """Топ тратящих пользователей"""
        return self.order_by('-total_spent')[:limit]
    
    def get_cached_points(self, user):
        """Получить баллы из кэша"""
        cache_key = f'user_points_{user.id}'
        points = cache.get(cache_key)
        
        if points is None:
            try:
                points = self.get(user=user)
                cache.set(cache_key, points, 300)  # Кэшируем на 5 минут
            except UserPoints.DoesNotExist:
                points = None
        
        return points
    
    def get_total_points_stats(self):
        """Получить общую статистику баллов"""
        cache_key = 'total_points_stats'
        stats = cache.get(cache_key)
        
        if stats is None:
            stats = self.aggregate(
                total_points=Sum('points'),
                total_earned=Sum('total_earned'),
                total_spent=Sum('total_spent'),
                users_count=Count('id')
            )
            cache.set(cache_key, stats, 600)  # Кэшируем на 10 минут
        
        return stats

class PointsHistoryManager(models.Manager):
    """Оптимизированный менеджер для PointsHistory"""
    
    def with_user_data(self):
        """История с данными пользователя"""
        return self.select_related('user')
    
    def recent_activity(self, days=30):
        """Недавняя активность"""
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=cutoff_date)
    
    def get_user_history(self, user, limit=50):
        """История пользователя"""
        cache_key = f'user_points_history_{user.id}_{limit}'
        history = cache.get(cache_key)
        
        if history is None:
            history = list(self.filter(user=user).order_by('-created_at')[:limit])
            cache.set(cache_key, history, 300)  # Кэшируем на 5 минут
        
        return history
    
    def get_activity_stats(self, days=30):
        """Статистика активности"""
        cache_key = f'points_activity_stats_{days}'
        stats = cache.get(cache_key)
        
        if stats is None:
            from django.utils import timezone
            from datetime import timedelta
            
            cutoff_date = timezone.now() - timedelta(days=days)
            stats = self.filter(created_at__gte=cutoff_date).aggregate(
                total_earned=Sum('points_change', filter=Q(change_type='earned')),
                total_spent=Sum('points_change', filter=Q(change_type='spent')),
                transactions_count=Count('id')
            )
            cache.set(cache_key, stats, 600)  # Кэшируем на 10 минут
        
        return stats

class FavoriteProductManager(models.Manager):
    """Оптимизированный менеджер для FavoriteProduct"""
    
    def with_user_and_product(self):
        """Избранное с данными пользователя и товара"""
        return self.select_related('user', 'product', 'product__category')
    
    def get_user_favorites(self, user):
        """Избранные товары пользователя"""
        cache_key = f'user_favorites_{user.id}'
        favorites = cache.get(cache_key)
        
        if favorites is None:
            favorites = list(self.filter(user=user).with_user_and_product().order_by('-created_at'))
            cache.set(cache_key, favorites, 300)  # Кэшируем на 5 минут
        
        return favorites
    
    def get_product_favorites_count(self, product):
        """Количество добавлений товара в избранное"""
        cache_key = f'product_favorites_count_{product.id}'
        count = cache.get(cache_key)
        
        if count is None:
            count = self.filter(product=product).count()
            cache.set(cache_key, count, 600)  # Кэшируем на 10 минут
        
        return count
    
    def get_popular_favorites(self, limit=20):
        """Популярные товары в избранном"""
        cache_key = f'popular_favorites_{limit}'
        popular = cache.get(cache_key)
        
        if popular is None:
            from django.db.models import Count
            popular = list(
                self.values('product')
                .annotate(favorites_count=Count('id'))
                .order_by('-favorites_count')[:limit]
            )
            cache.set(cache_key, popular, 600)  # Кэшируем на 10 минут
        
        return popular

# Оптимизированные модели
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
    instagram = models.CharField(max_length=100, blank=True, verbose_name='Instagram')
    is_ubd = models.BooleanField(default=False, verbose_name='УБД')
    ubd_doc = models.ImageField(upload_to='ubd_docs/', blank=True, null=True, verbose_name='Фото посвідчення УБД')

    objects = UserProfileManager()

    class Meta:
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['is_ubd']),
            models.Index(fields=['pay_type']),
        ]

    def __str__(self):
        return f'Profile for {self.user.username}'

    def invalidate_cache(self):
        """Инвалидация кэша профиля"""
        cache_key = f'user_profile_{self.user.id}'
        cache.delete(cache_key)

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'userprofile'):
        instance.userprofile.save()
        instance.userprofile.invalidate_cache()

class UserPoints(models.Model):
    """Модель для хранения баллов пользователей"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='points')
    points = models.PositiveIntegerField(default=0, verbose_name='Кількість балів')
    total_earned = models.PositiveIntegerField(default=0, verbose_name='Всього зароблено балів')
    total_spent = models.PositiveIntegerField(default=0, verbose_name='Всього витрачено балів')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Створено')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Оновлено')

    objects = UserPointsManager()

    class Meta:
        verbose_name = 'Бали користувача'
        verbose_name_plural = 'Бали користувачів'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['points']),
            models.Index(fields=['total_earned']),
            models.Index(fields=['total_spent']),
        ]

    def __str__(self):
        return f'{self.user.username} - {self.points} балів'

    def add_points(self, amount, reason=''):
        """Добавляет баллы пользователю"""
        self.points += amount
        self.total_earned += amount
        self.save()
        self.invalidate_cache()
        
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
            self.invalidate_cache()
            
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

    def invalidate_cache(self):
        """Инвалидация кэша баллов"""
        cache_key = f'user_points_{self.user.id}'
        cache.delete(cache_key)
        # Также инвалидируем общую статистику
        cache.delete('total_points_stats')

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

    objects = PointsHistoryManager()

    class Meta:
        verbose_name = 'Історія балів'
        verbose_name_plural = 'Історія балів'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['change_type']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f'{self.user.username} - {self.points_change} балів ({self.get_change_type_display()})'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Инвалидируем кэш истории пользователя
        cache_key = f'user_points_history_{self.user.id}_50'
        cache.delete(cache_key)

class FavoriteProduct(models.Model):
    """Модель для избранных товаров пользователя"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites')
    product = models.ForeignKey('storefront.Product', on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Додано до обраного')

    objects = FavoriteProductManager()

    class Meta:
        verbose_name = 'Обраний товар'
        verbose_name_plural = 'Обрані товари'
        unique_together = ['user', 'product']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['product']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f'{self.user.username} - {self.product.title}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Инвалидируем кэш избранного пользователя
        cache_key = f'user_favorites_{self.user.id}'
        cache.delete(cache_key)
        # Инвалидируем кэш популярных товаров
        cache.delete('popular_favorites_20')

    def delete(self, *args, **kwargs):
        user_id = self.user.id
        product_id = self.product.id
        super().delete(*args, **kwargs)
        # Инвалидируем кэш избранного пользователя
        cache_key = f'user_favorites_{user_id}'
        cache.delete(cache_key)
        # Инвалидируем кэш количества избранных для товара
        cache_key = f'product_favorites_count_{product_id}'
        cache.delete(cache_key)
