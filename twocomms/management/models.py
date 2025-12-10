from django.db import models
from django.utils.translation import gettext_lazy as _

class Client(models.Model):
    class Role(models.TextChoices):
        MANAGER = 'manager', _('Управляющий')
        REALIZER = 'realizer', _('Реализатор')
        OTHER = 'other', _('Другое')

    class CallResult(models.TextChoices):
        ORDER = 'order', _('Оформил заказ')
        SENT_EMAIL = 'sent_email', _('Отправили КП на емейл')
        SENT_MESSENGER = 'sent_messenger', _('Отправили КП на мессенджеры')
        WROTE_IG = 'wrote_ig', _('Написали в инстаграм')
        NO_ANSWER = 'no_answer', _('Не отвечает')
        NOT_INTERESTED = 'not_interested', _('Не интересует')
        INVALID_NUMBER = 'invalid_number', _('Номер недоступен')
        XML_CONNECTED = 'xml_connected', _('Подключил выгрузку XML')
        THINKING = 'thinking', _('Подумает')
        EXPENSIVE = 'expensive', _('Дорого')
        OTHER = 'other', _('Другое')

    shop_name = models.CharField(_("Название магазина/Instagram"), max_length=255)
    phone = models.CharField(_("Номер телефона"), max_length=50)
    full_name = models.CharField(_("ПІБ"), max_length=255)
    role = models.CharField(_("Статус"), max_length=50, choices=Role.choices, default=Role.MANAGER)
    source = models.CharField(_("Источник контакта"), max_length=255, blank=True)
    call_result = models.CharField(_("Итог разговора"), max_length=50, choices=CallResult.choices, default=CallResult.NO_ANSWER)
    call_result_details = models.TextField(_("Детали итога"), blank=True, help_text="Если выбрано 'Другое'")
    next_call_at = models.DateTimeField(_("Следующий звонок"), null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Клиент")
        verbose_name_plural = _("Клиенты")
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.shop_name} ({self.full_name})"
