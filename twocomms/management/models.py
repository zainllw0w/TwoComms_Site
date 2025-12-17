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
    id = models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")
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
    id = models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")
    key = models.CharField(max_length=255, db_index=True)
    chat_id = models.BigIntegerField()
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('key', 'chat_id')


class ReminderRead(models.Model):
    id = models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")
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

    class CpCtaType(models.TextChoices):
        TELEGRAM_MANAGER = "TELEGRAM_MANAGER", _("Telegram менеджера")
        WHATSAPP_MANAGER = "WHATSAPP_MANAGER", _("WhatsApp менеджера")
        TELEGRAM_GENERAL = "TELEGRAM_GENERAL", _("Telegram загальний")
        MAILTO_COOPERATION = "MAILTO_COOPERATION", _("Email cooperation@")
        REPLY_HINT_ONLY = "REPLY_HINT_ONLY", _("Відповідь на лист (без лінка)")
        CUSTOM_URL = "CUSTOM_URL", _("Custom URL")

    class PricingMode(models.TextChoices):
        OPT = "OPT", _("Опт")
        DROP = "DROP", _("Дроп")

    class OptTier(models.TextChoices):
        TIER_8_15 = "8_15", _("8–15")
        TIER_16_31 = "16_31", _("16–31")
        TIER_32_63 = "32_63", _("32–63")
        TIER_64_99 = "64_99", _("64–99")
        TIER_100_PLUS = "100_PLUS", _("100+")

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Менеджер"),
        on_delete=models.CASCADE,
        related_name="commercial_offer_email_settings",
    )
    show_manager = models.BooleanField(default=True, verbose_name=_("Показувати менеджера"))
    manager_name = models.CharField(max_length=255, blank=True, verbose_name=_("Імʼя менеджера"))
    phone_enabled = models.BooleanField(default=False, verbose_name=_("Телефон увімкнено"))
    phone = models.CharField(max_length=50, blank=True, verbose_name=_("Телефон"))

    viber_enabled = models.BooleanField(default=False, verbose_name=_("Viber увімкнено"))
    viber = models.CharField(max_length=100, blank=True, verbose_name=_("Viber (номер)"))

    whatsapp_enabled = models.BooleanField(default=False, verbose_name=_("WhatsApp увімкнено"))
    whatsapp = models.CharField(max_length=100, blank=True, verbose_name=_("WhatsApp (номер)"))

    telegram_enabled = models.BooleanField(default=False, verbose_name=_("Telegram увімкнено"))
    telegram = models.CharField(max_length=100, blank=True, verbose_name=_("Telegram (@username або номер)"))

    general_tg = models.CharField(max_length=255, blank=True, verbose_name=_("Резервний Telegram (канал/чат)"))

    pricing_mode = models.CharField(
        max_length=10,
        choices=PricingMode.choices,
        default=PricingMode.OPT,
        verbose_name=_("База входу (опт/дроп)"),
    )
    opt_tier = models.CharField(
        max_length=10,
        choices=OptTier.choices,
        default=OptTier.TIER_8_15,
        verbose_name=_("Опт: обсяг (tier)"),
    )
    drop_tee_price = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Дроп ціна футболка (грн)"))
    drop_hoodie_price = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Дроп ціна худі (грн)"))
    dropship_loyalty_bonus = models.BooleanField(default=False, verbose_name=_("Дроп бонус (-10 грн)"))

    include_catalog_link = models.BooleanField(default=True, verbose_name=_("Додавати лінк на каталог"))
    include_wholesale_link = models.BooleanField(default=True, verbose_name=_("Додавати лінк на опт"))
    include_dropship_link = models.BooleanField(default=True, verbose_name=_("Додавати лінк на дроп"))
    include_instagram_link = models.BooleanField(default=True, verbose_name=_("Додавати Instagram"))
    include_site_link = models.BooleanField(default=True, verbose_name=_("Додавати сайт"))

    cta_type = models.CharField(
        max_length=32,
        blank=True,
        choices=CpCtaType.choices,
        verbose_name=_("CTA тип"),
    )
    cta_custom_url = models.CharField(max_length=500, blank=True, verbose_name=_("CTA custom URL"))
    cta_button_text = models.CharField(max_length=120, blank=True, verbose_name=_("Текст CTA кнопки"))
    cta_microtext = models.CharField(max_length=255, blank=True, verbose_name=_("Мікротекст під CTA"))

    gallery_initialized = models.BooleanField(default=False, verbose_name=_("Галерея налаштована"))
    gallery_neutral = models.JSONField(default=list, blank=True, verbose_name=_("Галерея (Neutral)"))
    gallery_edgy = models.JSONField(default=list, blank=True, verbose_name=_("Галерея (Edgy)"))

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

    class CpCtaType(models.TextChoices):
        TELEGRAM_MANAGER = "TELEGRAM_MANAGER", _("Telegram менеджера")
        WHATSAPP_MANAGER = "WHATSAPP_MANAGER", _("WhatsApp менеджера")
        TELEGRAM_GENERAL = "TELEGRAM_GENERAL", _("Telegram загальний")
        MAILTO_COOPERATION = "MAILTO_COOPERATION", _("Email cooperation@")
        REPLY_HINT_ONLY = "REPLY_HINT_ONLY", _("Відповідь на лист (без лінка)")
        CUSTOM_URL = "CUSTOM_URL", _("Custom URL")

    class PricingMode(models.TextChoices):
        OPT = "OPT", _("Опт")
        DROP = "DROP", _("Дроп")

    class OptTier(models.TextChoices):
        TIER_8_15 = "8_15", _("8–15")
        TIER_16_31 = "16_31", _("16–31")
        TIER_32_63 = "32_63", _("32–63")
        TIER_64_99 = "64_99", _("64–99")
        TIER_100_PLUS = "100_PLUS", _("100+")

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

    cta_type = models.CharField(
        max_length=32,
        blank=True,
        choices=CpCtaType.choices,
        verbose_name=_("CTA тип"),
    )
    cta_url = models.CharField(max_length=500, blank=True, verbose_name=_("CTA URL"))
    cta_custom_url = models.CharField(max_length=500, blank=True, verbose_name=_("CTA custom URL"))
    cta_button_text = models.CharField(max_length=120, blank=True, verbose_name=_("Текст CTA кнопки"))
    cta_microtext = models.CharField(max_length=255, blank=True, verbose_name=_("Мікротекст під CTA"))

    general_tg = models.CharField(max_length=255, blank=True, verbose_name=_("Резервний Telegram"))
    pricing_mode = models.CharField(
        max_length=10,
        choices=PricingMode.choices,
        default=PricingMode.OPT,
        verbose_name=_("База входу (опт/дроп)"),
    )
    opt_tier = models.CharField(
        max_length=10,
        choices=OptTier.choices,
        default=OptTier.TIER_8_15,
        verbose_name=_("Опт: обсяг (tier)"),
    )
    drop_tee_price = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Дроп ціна футболка (грн)"))
    drop_hoodie_price = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Дроп ціна худі (грн)"))
    dropship_loyalty_bonus = models.BooleanField(default=False, verbose_name=_("Дроп бонус (-10 грн)"))
    include_catalog_link = models.BooleanField(default=True, verbose_name=_("Каталог (лінк)"))
    include_wholesale_link = models.BooleanField(default=True, verbose_name=_("Опт (лінк)"))
    include_dropship_link = models.BooleanField(default=True, verbose_name=_("Дроп (лінк)"))
    include_instagram_link = models.BooleanField(default=True, verbose_name=_("Instagram (лінк)"))
    include_site_link = models.BooleanField(default=True, verbose_name=_("Сайт (лінк)"))

    gallery_urls = models.JSONField(default=list, blank=True, verbose_name=_("Галерея URL (ввід)"))
    gallery_items = models.JSONField(default=list, blank=True, verbose_name=_("Галерея (використано)"))

    tee_entry = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Вхід футболка (грн)"))
    tee_retail_example = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Роздріб футболка (приклад, грн)"))
    tee_profit = models.IntegerField(null=True, blank=True, verbose_name=_("Прибуток футболка (приклад, грн)"))
    hoodie_entry = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Вхід худі (грн)"))
    hoodie_retail_example = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Роздріб худі (приклад, грн)"))
    hoodie_profit = models.IntegerField(null=True, blank=True, verbose_name=_("Прибуток худі (приклад, грн)"))

    show_manager = models.BooleanField(default=True, verbose_name=_("Показувати менеджера"))
    manager_name = models.CharField(max_length=255, blank=True, verbose_name=_("Імʼя менеджера"))
    phone_enabled = models.BooleanField(default=False, verbose_name=_("Телефон увімкнено"))
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


class Shop(models.Model):
    class ShopType(models.TextChoices):
        FULL = "full", _("Опт / повний магазин")
        TEST = "test", _("Тестова партія")

    name = models.CharField(_("Назва магазину"), max_length=255)
    photo = models.ImageField(_("Фото магазину"), upload_to="shops/photos/", blank=True, null=True)

    owner_full_name = models.CharField(_("ПІБ власника"), max_length=255, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Додав (менеджер)"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="management_shops_created",
    )
    managed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Веде (менеджер)"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="management_shops_managed",
    )

    shop_type = models.CharField(_("Тип магазину"), max_length=10, choices=ShopType.choices, default=ShopType.FULL)

    registration_place = models.CharField(_("Місце реєстрації"), max_length=255, blank=True)
    is_physical = models.BooleanField(_("Фізичний магазин"), default=False)
    city = models.CharField(_("Місто"), max_length=120, blank=True)
    address = models.TextField(_("Адреса"), blank=True)

    website_url = models.URLField(_("Сайт"), blank=True)
    instagram_url = models.URLField(_("Instagram / Instashop"), blank=True)
    prom_url = models.URLField(_("Prom.ua"), blank=True)
    other_sales_channel = models.CharField(_("Інше (де ще продають)"), max_length=500, blank=True)

    # Test shop fields
    test_product = models.ForeignKey(
        "storefront.Product",
        verbose_name=_("Тестова партія: товар"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="management_test_shops",
    )
    test_package = models.JSONField(_("Тестова партія: комплектація"), default=dict, blank=True)
    test_connected_at = models.DateField(_("Дата підключення (старт 14 днів)"), null=True, blank=True)
    test_period_days = models.PositiveIntegerField(_("Тривалість тесту (днів)"), default=14)

    next_contact_at = models.DateTimeField(_("Наступний контакт"), null=True, blank=True)
    notes = models.TextField(_("Нотатки"), blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Магазин")
        verbose_name_plural = _("Магазини")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["shop_type", "-created_at"], name="mgmt_shop_type_dt"),
            models.Index(fields=["managed_by", "-created_at"], name="mgmt_shop_mgr_dt"),
        ]

    def __str__(self):
        return self.name


class ShopPhone(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", _("Власник")
        MANAGER = "manager", _("Менеджер")
        ADMIN = "admin", _("Адміністратор")
        OTHER = "other", _("Інший")

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="phones", verbose_name=_("Магазин"))
    role = models.CharField(_("Роль"), max_length=20, choices=Role.choices, default=Role.OWNER)
    role_other = models.CharField(_("Хто це (якщо інший)"), max_length=120, blank=True)
    phone = models.CharField(_("Телефон"), max_length=50)
    is_primary = models.BooleanField(_("Основний"), default=False)
    sort_order = models.PositiveIntegerField(_("Порядок"), default=0)

    class Meta:
        verbose_name = _("Контакт магазину")
        verbose_name_plural = _("Контакти магазину")
        ordering = ["sort_order", "id"]
        indexes = [
            models.Index(fields=["shop", "is_primary"], name="mgmt_shop_phone_primary"),
        ]

    def __str__(self):
        return f"{self.shop_id}: {self.phone}"


class ShopShipment(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="shipments", verbose_name=_("Магазин"))
    ttn_number = models.CharField(_("ТТН"), max_length=64, db_index=True)
    shipped_at = models.DateField(_("Дата відправки"), db_index=True)
    is_test_batch = models.BooleanField(_("Тестова партія"), default=False, db_index=True)

    wholesale_invoice = models.ForeignKey(
        "orders.WholesaleInvoice",
        verbose_name=_("Накладна (система)"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="management_shop_shipments",
    )
    uploaded_invoice_file = models.FileField(
        _("Накладна (Excel файл)"),
        upload_to="shops/invoices/",
        blank=True,
        null=True,
    )
    invoice_summary = models.JSONField(_("Сводка накладной"), default=dict, blank=True)
    invoice_total_amount = models.DecimalField(_("Сума накладної"), max_digits=12, decimal_places=2, null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Створив"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="management_shop_shipments_created",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Відправка (ТТН)")
        verbose_name_plural = _("Відправки (ТТН)")
        ordering = ["-shipped_at", "-created_at"]
        indexes = [
            models.Index(fields=["shop", "-shipped_at"], name="mgmt_ship_shop_dt"),
        ]

    def __str__(self):
        return f"{self.shop_id}: {self.ttn_number}"


class ShopCommunication(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="communications", verbose_name=_("Магазин"))
    contacted_at = models.DateTimeField(_("Коли звʼязувались"), auto_now_add=False)
    contact_person = models.CharField(_("З ким"), max_length=255, blank=True)
    phone = models.CharField(_("Номер"), max_length=50, blank=True)
    note = models.TextField(_("Нотатка"), blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Створив"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="management_shop_comms_created",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("Комунікація (магазин)")
        verbose_name_plural = _("Комунікації (магазин)")
        ordering = ["-contacted_at", "-created_at"]
        indexes = [
            models.Index(fields=["shop", "-contacted_at"], name="mgmt_shop_comm_dt"),
        ]

    def __str__(self):
        return f"{self.shop_id}: {self.contacted_at:%Y-%m-%d %H:%M}"


class ShopInventoryMovement(models.Model):
    class Kind(models.TextChoices):
        RECEIPT = "receipt", _("Надходження")
        SALE = "sale", _("Продаж")
        ADJUST = "adjust", _("Коригування")

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="inventory_moves", verbose_name=_("Магазин"))
    shipment = models.ForeignKey(
        ShopShipment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_moves",
        verbose_name=_("ТТН"),
    )
    kind = models.CharField(_("Тип"), max_length=20, choices=Kind.choices, db_index=True)

    product_name = models.CharField(_("Товар"), max_length=255)
    category = models.CharField(_("Категорія"), max_length=120, blank=True)
    size = models.CharField(_("Розмір"), max_length=40, blank=True)
    color = models.CharField(_("Колір"), max_length=80, blank=True)

    delta_qty = models.IntegerField(_("Зміна кількості (±)"))
    note = models.CharField(_("Коментар"), max_length=255, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Створив"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="management_shop_inventory_moves_created",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("Рух товару (магазин)")
        verbose_name_plural = _("Рух товару (магазин)")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["shop", "kind", "-created_at"], name="mgmt_inv_shop_kind"),
        ]

    def __str__(self):
        return f"{self.shop_id}: {self.kind} {self.delta_qty}"
