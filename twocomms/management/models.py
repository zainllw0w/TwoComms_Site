from django.db import models
from django.utils.translation import gettext_lazy as _

class Client(models.Model):
    """
    Модель для хранения информации о клиентах/магазинах в CRM системе менеджмента.
    """
    
    class ContactRole(models.TextChoices):
        OWNER = 'owner', _('Управляющий')
        MANAGER = 'manager', _('Менеджер')
        REALIZER = 'realizer', _('Реализатор')
        OTHER = 'other', _('Другое')

    class CallResult(models.TextChoices):
        ORDER_PLACED = 'order_placed', _('Оформил заказ')
        SENT_OFFER_EMAIL = 'sent_offer_email', _('Отправили КП на емейл')
        SENT_OFFER_MESSENGER = 'sent_offer_messenger', _('Отправили КП на мессенджеры')
        WROTE_INSTAGRAM = 'wrote_instagram', _('Написали в инстаграм')
        NO_ANSWER = 'no_answer', _('Не отвечает')
        NOT_INTERESTED = 'not_interested', _('Не интересует')
        NUMBER_UNAVAILABLE = 'number_unavailable', _('Номер недоступен')
        CONNECTED_XML = 'connected_xml', _('Подключил выгрузку XML')
        THINKING = 'thinking', _('Подумает')
        EXPENSIVE = 'expensive', _('Дорого')
        OTHER = 'other', _('Другое')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Дата создания'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Дата обновления'))
    
    # Основная информация
    shop_name = models.CharField(max_length=255, verbose_name=_('Название магазина/Instagram'))
    phone = models.CharField(max_length=50, verbose_name=_('Номер телефона'))
    full_name = models.CharField(max_length=255, verbose_name=_('ФИО (ПІБ)'), blank=True)
    
    # Статус контакта
    contact_role = models.CharField(
        max_length=20, 
        choices=ContactRole.choices, 
        default=ContactRole.MANAGER,
        verbose_name=_('Статус человека')
    )
    
    # Источник
    source = models.CharField(max_length=255, verbose_name=_('Где был взят контакт'), blank=True)
    
    # Результат звонка
    last_call_result = models.CharField(
        max_length=50,
        choices=CallResult.choices,
        default=CallResult.NO_ANSWER,
        verbose_name=_('Итог разговора')
    )
    last_call_result_text = models.TextField(
        blank=True, 
        verbose_name=_('Детали итога (если Другое)')
    )
    
    # Следущий шаг
    next_call_at = models.DateTimeField(
        null=True, 
        blank=True, 
        verbose_name=_('Дата и время следующего звонка')
    )
    is_non_conversion = models.BooleanField(
        default=False, 
        verbose_name=_('Неконверсионный клиент')
    )

    class Meta:
        verbose_name = _('Клиент')
        verbose_name_plural = _('Клиенты')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.shop_name} ({self.full_name})"
