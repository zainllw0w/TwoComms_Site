from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings


class Client(models.Model):
    class Role(models.TextChoices):
        SUPERVISOR = 'supervisor', _('Управляючий')
        MANAGER = 'manager', _('Менеджер')
        REALIZER = 'realizer', _('Реалізатор')
        OWNER = 'owner', _('Власник')
        OTHER = 'other', _('Інше')

    class CallResult(models.TextChoices):
        ORDER = 'order', _('Оформив замовлення')
        SENT_EMAIL = 'sent_email', _('Відправили КП на e-mail')
        SENT_MESSENGER = 'sent_messenger', _('Відправили КП у месенджери')
        WROTE_IG = 'wrote_ig', _('Написали в Instagram')
        NO_ANSWER = 'no_answer', _('Не відповідає')
        NOT_INTERESTED = 'not_interested', _('Не цікавить')
        INVALID_NUMBER = 'invalid_number', _('Номер недоступний')
        XML_CONNECTED = 'xml_connected', _('Підключив XML')
        THINKING = 'thinking', _('Подумає')
        EXPENSIVE = 'expensive', _('Дорого')
        WAITING_PAYMENT = 'waiting_payment', _('Очікується оплата')
        WAITING_PREPAYMENT = 'waiting_prepayment', _('Очікується передоплата')
        TEST_BATCH = 'test_batch', _('Замовив тестову партію')
        OTHER = 'other', _('Інше')

    shop_name = models.CharField(_("Назва магазину / Instagram"), max_length=255)
    phone = models.CharField(_("Номер телефону"), max_length=50)
    full_name = models.CharField(_("ПІБ"), max_length=255)
    role = models.CharField(_("Статус"), max_length=50, choices=Role.choices, default=Role.MANAGER)
    source = models.CharField(_("Джерело контакту"), max_length=255, blank=True)
    call_result = models.CharField(_("Підсумок розмови"), max_length=50, choices=CallResult.choices, default=CallResult.NO_ANSWER)
    call_result_details = models.TextField(_("Деталі підсумку"), blank=True, help_text="Якщо вибрано 'Інше'")
    next_call_at = models.DateTimeField(_("Наступний дзвінок"), null=True, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Менеджер"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="management_clients"
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        verbose_name = _("Клієнт")
        verbose_name_plural = _("Клієнти")
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.shop_name} ({self.full_name})"


class Report(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Менеджер"),
        on_delete=models.CASCADE,
        related_name="management_reports"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    points = models.PositiveIntegerField(default=0)
    processed = models.PositiveIntegerField(default=0)
    file = models.FileField(upload_to='reports/', blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _("Звіт")
        verbose_name_plural = _("Звіти")

    def __str__(self):
        return f"Звіт {self.owner} {self.created_at:%Y-%m-%d}"


class ReminderSent(models.Model):
    key = models.CharField(max_length=255, db_index=True)
    chat_id = models.BigIntegerField()
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('key', 'chat_id')


class ReminderRead(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="management_read_reminders",
        verbose_name=_("Користувач"),
    )
    key = models.CharField(max_length=255, db_index=True)
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'key')
        verbose_name = _("Прочитане нагадування")
        verbose_name_plural = _("Прочитані нагадування")


class InvoiceRejectionReasonRequest(models.Model):
    invoice = models.ForeignKey(
        'orders.WholesaleInvoice',
        on_delete=models.CASCADE,
        related_name='management_rejection_reason_requests',
        verbose_name=_("Накладна"),
    )
    admin_chat_id = models.BigIntegerField(db_index=True, verbose_name=_("Telegram chat id (адмін)"))
    prompt_message_id = models.BigIntegerField(null=True, blank=True, verbose_name=_("Message id запиту"))
    is_active = models.BooleanField(default=True, db_index=True, verbose_name=_("Активний запит"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Запит причини відхилення накладної")
        verbose_name_plural = _("Запити причин відхилення накладних")
        ordering = ['-created_at']


class CommercialOfferEmailSettings(models.Model):
    class CpMode(models.TextChoices):
        LIGHT = "LIGHT", _("Light")
        VISUAL = "VISUAL", _("Visual")

    class CpSegmentMode(models.TextChoices):
        NEUTRAL = "NEUTRAL", _("Neutral")
        EDGY = "EDGY", _("Edgy")

    class CpSubjectPreset(models.TextChoices):
        PRESET_1 = "PRESET_1", _("Preset 1")
        PRESET_2 = "PRESET_2", _("Preset 2")
        PRESET_3 = "PRESET_3", _("Preset 3")
        CUSTOM = "CUSTOM", _("Custom")

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Менеджер"),
        on_delete=models.CASCADE,
        related_name="commercial_offer_email_settings",
    )
    show_manager = models.BooleanField(default=True, verbose_name=_("Показувати менеджера"))
    manager_name = models.CharField(max_length=255, blank=True, verbose_name=_("Імʼя менеджера"))
    phone = models.CharField(max_length=50, blank=True, verbose_name=_("Телефон"))

    viber_enabled = models.BooleanField(default=False, verbose_name=_("Viber увімкнено"))
    viber = models.CharField(max_length=100, blank=True, verbose_name=_("Viber (номер)"))

    whatsapp_enabled = models.BooleanField(default=False, verbose_name=_("WhatsApp увімкнено"))
    whatsapp = models.CharField(max_length=100, blank=True, verbose_name=_("WhatsApp (номер)"))

    telegram_enabled = models.BooleanField(default=False, verbose_name=_("Telegram увімкнено"))
    telegram = models.CharField(max_length=100, blank=True, verbose_name=_("Telegram (@username або номер)"))

    mode = models.CharField(
        max_length=10,
        choices=CpMode.choices,
        default=CpMode.VISUAL,
        verbose_name=_("Режим шаблону"),
    )
    segment_mode = models.CharField(
        max_length=10,
        choices=CpSegmentMode.choices,
        default=CpSegmentMode.NEUTRAL,
        verbose_name=_("Сегмент контенту"),
    )
    subject_preset = models.CharField(
        max_length=20,
        choices=CpSubjectPreset.choices,
        default=CpSubjectPreset.PRESET_1,
        verbose_name=_("Пресет теми"),
    )
    subject_custom = models.CharField(max_length=255, blank=True, verbose_name=_("Кастомна тема"))

    tee_entry = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Вхід футболка (грн)"))
    tee_retail_example = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Роздріб футболка (приклад, грн)"))
    hoodie_entry = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Вхід худі (грн)"))
    hoodie_retail_example = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Роздріб худі (приклад, грн)"))

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Налаштування КП на e-mail")
        verbose_name_plural = _("Налаштування КП на e-mail")

    def __str__(self):
        return f"КП на e-mail: {self.owner}"


class CommercialOfferEmailLog(models.Model):
    class Status(models.TextChoices):
        SENT = "sent", _("Надіслано")
        FAILED = "failed", _("Помилка")

    class CpMode(models.TextChoices):
        LIGHT = "LIGHT", _("Light")
        VISUAL = "VISUAL", _("Visual")

    class CpSegmentMode(models.TextChoices):
        NEUTRAL = "NEUTRAL", _("Neutral")
        EDGY = "EDGY", _("Edgy")

    class CpSubjectPreset(models.TextChoices):
        PRESET_1 = "PRESET_1", _("Preset 1")
        PRESET_2 = "PRESET_2", _("Preset 2")
        PRESET_3 = "PRESET_3", _("Preset 3")
        CUSTOM = "CUSTOM", _("Custom")

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Менеджер"),
        on_delete=models.CASCADE,
        related_name="commercial_offer_email_logs",
    )
    recipient_email = models.EmailField(verbose_name=_("Email отримувача"), db_index=True)
    recipient_name = models.CharField(max_length=255, blank=True, verbose_name=_("Імʼя/компанія отримувача"))
    subject = models.CharField(max_length=255, verbose_name=_("Тема листа"))
    preheader = models.CharField(max_length=255, blank=True, verbose_name=_("Preheader"))
    body_html = models.TextField(blank=True, verbose_name=_("HTML листа"))
    body_text = models.TextField(blank=True, verbose_name=_("Текст листа"))

    mode = models.CharField(
        max_length=10,
        choices=CpMode.choices,
        default=CpMode.VISUAL,
        verbose_name=_("Режим шаблону"),
        db_index=True,
    )
    segment_mode = models.CharField(
        max_length=10,
        choices=CpSegmentMode.choices,
        default=CpSegmentMode.NEUTRAL,
        verbose_name=_("Сегмент контенту"),
        db_index=True,
    )
    subject_preset = models.CharField(
        max_length=20,
        choices=CpSubjectPreset.choices,
        default=CpSubjectPreset.PRESET_1,
        verbose_name=_("Пресет теми"),
    )
    subject_custom = models.CharField(max_length=255, blank=True, verbose_name=_("Кастомна тема"))

    tee_entry = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Вхід футболка (грн)"))
    tee_retail_example = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Роздріб футболка (приклад, грн)"))
    tee_profit = models.IntegerField(null=True, blank=True, verbose_name=_("Прибуток футболка (приклад, грн)"))
    hoodie_entry = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Вхід худі (грн)"))
    hoodie_retail_example = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Роздріб худі (приклад, грн)"))
    hoodie_profit = models.IntegerField(null=True, blank=True, verbose_name=_("Прибуток худі (приклад, грн)"))

    show_manager = models.BooleanField(default=True, verbose_name=_("Показувати менеджера"))
    manager_name = models.CharField(max_length=255, blank=True, verbose_name=_("Імʼя менеджера"))
    phone = models.CharField(max_length=50, blank=True, verbose_name=_("Телефон"))
    viber = models.CharField(max_length=100, blank=True, verbose_name=_("Viber"))
    whatsapp = models.CharField(max_length=100, blank=True, verbose_name=_("WhatsApp"))
    telegram = models.CharField(max_length=100, blank=True, verbose_name=_("Telegram"))

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SENT, db_index=True)
    error = models.TextField(blank=True, verbose_name=_("Помилка"))
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("Відправлена КП (лог)")
        verbose_name_plural = _("Відправлені КП (лог)")
        ordering = ['-created_at']

    def __str__(self):
        return f"КП → {self.recipient_email} ({self.created_at:%Y-%m-%d %H:%M})"
