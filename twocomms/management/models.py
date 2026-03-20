import re
from decimal import Decimal
from unicodedata import normalize as unicode_normalize

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings

try:
    import phonenumbers
    from phonenumbers import PhoneNumberFormat
except Exception:  # pragma: no cover - optional runtime dependency until installed everywhere
    phonenumbers = None
    PhoneNumberFormat = None


def _ua_phone_candidates(raw_phone: str) -> list[str]:
    raw = str(raw_phone or "").strip()
    digits = re.sub(r"\D+", "", raw)
    if not digits:
        return []

    candidates: list[str] = []
    for value in (
        raw,
        f"+{digits}" if raw.startswith("+") else "",
        f"+{digits}" if digits.startswith("380") and len(digits) == 12 else "",
        digits if digits.startswith("0") and len(digits) == 10 else "",
        f"0{digits}" if len(digits) == 9 else "",
        f"0{digits[1:]}" if digits.startswith("80") and len(digits) == 11 else "",
    ):
        value = (value or "").strip()
        if value and value not in candidates:
            candidates.append(value)
    return candidates


def normalize_phone(raw_phone: str) -> str:
    digits = re.sub(r"\D+", "", raw_phone or "")
    if not digits:
        return ""

    if phonenumbers is not None:
        for candidate in _ua_phone_candidates(raw_phone):
            try:
                parsed = phonenumbers.parse(candidate, "UA")
            except Exception:
                continue
            if not phonenumbers.is_possible_number(parsed):
                continue
            if not phonenumbers.is_valid_number(parsed):
                continue
            try:
                return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
            except Exception:
                continue

    if digits.startswith("380") and len(digits) == 12:
        return f"+{digits}"
    if digits.startswith("80") and len(digits) == 11:
        return f"+38{digits[1:]}"
    if digits.startswith("0") and len(digits) == 10:
        return f"+38{digits}"
    if len(digits) == 9:
        return f"+380{digits}"
    if raw_phone and str(raw_phone).strip().startswith("+"):
        return f"+{digits}"
    return digits


LEGAL_ENTITY_TOKENS = {
    "тов",
    "тзов",
    "фоп",
    "llc",
    "ltd",
    "inc",
    "corp",
    "company",
}


def build_phone_last7(raw_phone: str) -> str:
    normalized = normalize_phone(raw_phone)
    digits = re.sub(r"\D+", "", normalized or raw_phone or "")
    return digits[-7:] if len(digits) >= 7 else digits


def normalize_name_for_match(raw_value: str) -> str:
    value = unicode_normalize("NFKC", str(raw_value or "")).lower().strip()
    value = re.sub(r"[^\w\s]", " ", value)
    tokens = [token for token in value.split() if token and token not in LEGAL_ENTITY_TOKENS]
    return " ".join(tokens)


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
    phone_normalized = models.CharField(_("Нормалізований номер"), max_length=50, blank=True, db_index=True)
    phone_last7 = models.CharField(_("Останні 7 цифр"), max_length=7, blank=True, db_index=True)
    normalized_name_display = models.CharField(_("Нормалізоване ім'я"), max_length=255, blank=True)
    normalized_name_match_key = models.CharField(_("Ключ збігу імені"), max_length=255, blank=True, db_index=True)
    is_shared_phone = models.BooleanField(_("Спільний номер"), default=False)
    phone_group_id = models.CharField(_("ID групи номера"), max_length=64, blank=True)
    shared_phone_reason = models.CharField(_("Причина спільного номера"), max_length=255, blank=True)
    website_url = models.CharField(_("Сайт"), max_length=500, blank=True)
    full_name = models.CharField(_("ПІБ"), max_length=255)
    role = models.CharField(_("Статус"), max_length=50, choices=Role.choices, default=Role.MANAGER)
    source = models.CharField(_("Джерело контакту"), max_length=255, blank=True)
    call_result = models.CharField(_("Підсумок розмови"), max_length=50, choices=CallResult.choices, default=CallResult.NO_ANSWER)
    points_override = models.PositiveIntegerField(_("Кастомні бали"), null=True, blank=True)
    call_result_reason_code = models.CharField(_("Код причини підсумку"), max_length=64, blank=True, db_index=True)
    call_result_reason_note = models.TextField(_("Уточнення причини"), blank=True)
    call_result_context = models.JSONField(_("Контекст підсумку"), default=dict, blank=True)
    call_result_details = models.TextField(_("Деталі підсумку"), blank=True, help_text="Якщо вибрано 'Інше'")
    manager_note = models.TextField(_("Нотатка менеджера"), blank=True)
    phase_root = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="phase_family_members",
        verbose_name=_("Коренева фаза"),
    )
    previous_phase = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="next_phase_members",
        verbose_name=_("Попередня фаза"),
    )
    phase_number = models.PositiveIntegerField(_("Номер фази"), default=1, db_index=True)
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

    def save(self, *args, **kwargs):
        self.phone_normalized = normalize_phone(self.phone)
        self.phone_last7 = build_phone_last7(self.phone_normalized or self.phone)
        self.normalized_name_display = normalize_name_for_match(self.shop_name)
        self.normalized_name_match_key = self.normalized_name_display
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.shop_name} ({self.full_name})"


class ManagementLead(models.Model):
    class Status(models.TextChoices):
        MODERATION = "moderation", _("На модерації")
        BASE = "base", _("У базі")
        CONVERTED = "converted", _("Оброблено")
        REJECTED = "rejected", _("Не підходить")

    class LeadSource(models.TextChoices):
        MANUAL = "manual", _("Ручне додавання")
        PARSER = "parser", _("Парсинг")

    class NicheStatus(models.TextChoices):
        NICHE = "niche", _("Нішевий")
        MAYBE = "maybe", _("Під питанням")
        NON_NICHE = "non_niche", _("Не нішевий")

    shop_name = models.CharField(_("Назва магазину"), max_length=255)
    phone = models.CharField(_("Номер телефону"), max_length=50)
    phone_normalized = models.CharField(_("Нормалізований номер"), max_length=50, blank=True, db_index=True)
    phone_last7 = models.CharField(_("Останні 7 цифр"), max_length=7, blank=True, db_index=True)
    normalized_name_display = models.CharField(_("Нормалізоване ім'я"), max_length=255, blank=True)
    normalized_name_match_key = models.CharField(_("Ключ збігу імені"), max_length=255, blank=True, db_index=True)
    is_shared_phone = models.BooleanField(_("Спільний номер"), default=False)
    phone_group_id = models.CharField(_("ID групи номера"), max_length=64, blank=True)
    shared_phone_reason = models.CharField(_("Причина спільного номера"), max_length=255, blank=True)
    full_name = models.CharField(_("ПІБ"), max_length=255, blank=True)
    role = models.CharField(_("Статус людини"), max_length=50, choices=Client.Role.choices, default=Client.Role.OTHER)
    source = models.CharField(_("Де взяли контакт"), max_length=255, blank=True)
    website_url = models.CharField(_("Сайт"), max_length=500, blank=True)
    city = models.CharField(_("Місто"), max_length=120, blank=True)
    parser_keyword = models.CharField(_("Ключове слово парсера"), max_length=255, blank=True)
    parser_query = models.CharField(_("Пошуковий запит"), max_length=500, blank=True)
    google_place_id = models.CharField(_("Google Place ID"), max_length=255, blank=True, db_index=True)
    google_maps_url = models.CharField(_("Google Maps URL"), max_length=500, blank=True)
    details = models.TextField(_("Деталі"), blank=True)
    comments = models.TextField(_("Коментарі"), blank=True)
    extra_data = models.JSONField(_("Сирі дані"), default=dict, blank=True)
    status = models.CharField(_("Статус"), max_length=20, choices=Status.choices, default=Status.BASE, db_index=True)
    lead_source = models.CharField(_("Джерело ліда"), max_length=20, choices=LeadSource.choices, default=LeadSource.MANUAL, db_index=True)
    niche_status = models.CharField(_("Нішевість"), max_length=20, choices=NicheStatus.choices, default=NicheStatus.MAYBE, db_index=True)
    rejection_reason = models.TextField(_("Причина відхилення"), blank=True)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Додав"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="management_leads_added",
    )
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Модератор"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="management_leads_moderated",
    )
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Обробив"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="management_leads_processed",
    )
    converted_client = models.OneToOneField(
        Client,
        verbose_name=_("Створений клієнт"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_lead",
    )
    parser_job = models.ForeignKey(
        "LeadParsingJob",
        verbose_name=_("Сесія парсингу"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_leads",
    )
    approved_to_base_at = models.DateTimeField(_("Додано у базу"), null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Лід")
        verbose_name_plural = _("Ліди")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="mgmt_lead_status_dt"),
            models.Index(fields=["lead_source", "-created_at"], name="mgmt_lead_src_dt"),
            models.Index(fields=["city", "status"], name="mgmt_lead_city_st"),
        ]

    def save(self, *args, **kwargs):
        self.phone_normalized = normalize_phone(self.phone)
        self.phone_last7 = build_phone_last7(self.phone_normalized or self.phone)
        self.normalized_name_display = normalize_name_for_match(self.shop_name)
        self.normalized_name_match_key = self.normalized_name_display
        super().save(*args, **kwargs)

    @property
    def added_by_display(self) -> str:
        if self.lead_source == self.LeadSource.PARSER:
            return "парсинг"
        if self.added_by:
            return self.added_by.get_full_name() or self.added_by.username
        return "невідомо"

    def __str__(self):
        return f"{self.shop_name} ({self.get_status_display()})"


class LeadParsingJob(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", _("Працює")
        PAUSED = "paused", _("Пауза")
        STOPPED = "stopped", _("Зупинено")
        COMPLETED = "completed", _("Завершено")
        FAILED = "failed", _("Помилка")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="management_lead_parsing_jobs",
        verbose_name=_("Створив"),
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RUNNING, db_index=True)
    keywords_raw = models.TextField(_("Ключові слова (raw)"), blank=True)
    cities_raw = models.TextField(_("Міста (raw)"), blank=True)
    keywords = models.JSONField(_("Ключові слова"), default=list, blank=True)
    cities = models.JSONField(_("Міста"), default=list, blank=True)
    request_limit = models.PositiveIntegerField(_("Ліміт запитів"), default=100)
    request_count = models.PositiveIntegerField(_("Виконано запитів"), default=0)
    current_keyword_index = models.PositiveIntegerField(default=0)
    current_city_index = models.PositiveIntegerField(default=0)
    total_found = models.PositiveIntegerField(default=0)
    no_phone_skipped = models.PositiveIntegerField(default=0)
    duplicate_skipped = models.PositiveIntegerField(default=0)
    added_to_moderation = models.PositiveIntegerField(default=0)
    moved_to_bad = models.PositiveIntegerField(default=0)
    already_rejected_skipped = models.PositiveIntegerField(default=0)
    current_query = models.CharField(max_length=500, blank=True)
    next_page_token = models.CharField(max_length=255, blank=True)
    last_error = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True, db_index=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Сесія парсингу лідів")
        verbose_name_plural = _("Сесії парсингу лідів")
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["status", "-started_at"], name="mgmt_parse_status_dt"),
        ]

    def __str__(self):
        return f"ParseJob#{self.id} ({self.status})"


class LeadParsingResult(models.Model):
    class ResultStatus(models.TextChoices):
        ADDED = "added", _("Додано до модерації")
        DUPLICATE = "duplicate", _("Дубль")
        NO_PHONE = "no_phone", _("Без телефону")
        REJECTED = "rejected", _("Раніше відхилено")
        ERROR = "error", _("Помилка")

    job = models.ForeignKey(
        LeadParsingJob,
        on_delete=models.CASCADE,
        related_name="results",
        verbose_name=_("Сесія парсингу"),
    )
    lead = models.ForeignKey(
        ManagementLead,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="parser_results",
        verbose_name=_("Лід"),
    )
    keyword = models.CharField(max_length=255, blank=True, verbose_name=_("Ключове слово"))
    city = models.CharField(max_length=120, blank=True, verbose_name=_("Місто"))
    query = models.CharField(max_length=500, blank=True, verbose_name=_("Запит"))
    place_id = models.CharField(max_length=255, blank=True, db_index=True, verbose_name=_("Place ID"))
    place_name = models.CharField(max_length=255, blank=True, verbose_name=_("Назва"))
    phone = models.CharField(max_length=50, blank=True, verbose_name=_("Телефон"))
    website_url = models.CharField(max_length=500, blank=True, verbose_name=_("Сайт"))
    maps_url = models.CharField(max_length=500, blank=True, verbose_name=_("Google Maps URL"))
    status = models.CharField(max_length=20, choices=ResultStatus.choices, default=ResultStatus.ADDED, db_index=True)
    reason = models.CharField(max_length=255, blank=True, verbose_name=_("Причина"))
    payload = models.JSONField(default=dict, blank=True, verbose_name=_("Payload"))
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("Результат парсингу")
        verbose_name_plural = _("Результати парсингу")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["job", "-created_at"], name="mgmt_parse_res_job_dt"),
            models.Index(fields=["status", "-created_at"], name="mgmt_parse_res_st_dt"),
        ]

    def __str__(self):
        return f"{self.job_id}:{self.status}:{self.place_name}"


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

    # URLs can be stored without scheme (http/https); we'll normalize for clickable links in UI.
    website_url = models.CharField(_("Сайт"), max_length=500, blank=True)
    instagram_url = models.CharField(_("Instagram / Instashop"), max_length=500, blank=True)
    prom_url = models.CharField(_("Prom.ua"), max_length=500, blank=True)
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
    test_contract_file = models.FileField(_("Договір (тест)"), upload_to="shops/contracts/", blank=True, null=True)
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


class ManagementDailyActivity(models.Model):
    """
    Aggregated manager activity per local day (Europe/Kiev).
    Active time counts only when the Management tab is visible + focused and user is not idle.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="management_daily_activity",
        verbose_name=_("Користувач"),
    )
    date = models.DateField(db_index=True, verbose_name=_("Дата (локальна)"))
    active_seconds = models.PositiveIntegerField(default=0, verbose_name=_("Активний час (сек)"))
    last_seen_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Остання активність"))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Активність менеджера (доба)")
        verbose_name_plural = _("Активність менеджера (доба)")
        unique_together = ("user", "date")
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["user", "-date"], name="mgmt_act_user_dt"),
        ]

    def __str__(self):
        return f"{self.user_id} {self.date} ({self.active_seconds}s)"


class ClientFollowUp(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", _("Відкрито")
        DONE = "done", _("Виконано")
        RESCHEDULED = "rescheduled", _("Перенесено")
        CANCELLED = "cancelled", _("Скасовано")
        MISSED = "missed", _("Пропущено")

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="followups",
        verbose_name=_("Клієнт"),
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="management_client_followups",
        verbose_name=_("Менеджер"),
    )

    scheduled_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name=_("Створено"))
    due_at = models.DateTimeField(db_index=True, verbose_name=_("Коли передзвонити"))
    due_date = models.DateField(db_index=True, verbose_name=_("Дата (локальна)"))

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True)
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Закрито"))
    grace_until = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name=_("Пільгове вікно до"))
    last_notified_at = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name=_("Останнє нагадування"))
    escalation_level = models.PositiveSmallIntegerField(default=0, db_index=True, verbose_name=_("Рівень ескалації"))
    closed_by_report = models.ForeignKey(
        Report,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_followups",
        verbose_name=_("Закрито звітом"),
    )
    meta = models.JSONField(default=dict, blank=True, verbose_name=_("Мета"))

    class Meta:
        verbose_name = _("Передзвон (клієнт)")
        verbose_name_plural = _("Передзвони (клієнти)")
        ordering = ["-due_at", "-id"]
        indexes = [
            models.Index(fields=["owner", "due_date", "status"], name="mgmt_fu_owner_dt_st"),
            models.Index(fields=["client", "status"], name="mgmt_fu_client_st"),
        ]

    def __str__(self):
        return f"FollowUp({self.owner_id} → {self.client_id}) {self.due_at} {self.status}"


class ManagementStatsAdviceDismissal(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="management_stats_advice_dismissals",
        verbose_name=_("Користувач"),
    )
    key = models.CharField(max_length=255, db_index=True, verbose_name=_("Ключ"))
    dismissed_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Коли приховано"))
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name=_("Діє до"))
    meta = models.JSONField(default=dict, blank=True, verbose_name=_("Мета"))

    class Meta:
        verbose_name = _("Прихована порада (статистика)")
        verbose_name_plural = _("Приховані поради (статистика)")
        unique_together = ("user", "key")
        indexes = [
            models.Index(fields=["user", "expires_at"], name="mgmt_adv_user_exp"),
        ]

    def __str__(self):
        return f"{self.user_id}:{self.key}"


class ManagementStatsConfig(models.Model):
    """
    Singleton-like config holder for KPI/Advice tuning (admin-editable via Django admin).
    """

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    kpd_weights = models.JSONField(default=dict, blank=True, verbose_name=_("Ваги КПД"))
    advice_thresholds = models.JSONField(default=dict, blank=True, verbose_name=_("Пороги порад"))
    formula_version = models.CharField(max_length=64, default="mosaic-v1", verbose_name=_("Версія формули"))
    legacy_kpd_formula_version = models.CharField(max_length=64, default="kpd-v1", verbose_name=_("Версія legacy КПД"))
    shadow_mosaic_formula_version = models.CharField(max_length=64, default="mosaic-v1", verbose_name=_("Версія shadow MOSAIC"))
    defaults_version = models.CharField(max_length=64, default="2026-03-13", verbose_name=_("Версія дефолтів"))
    snapshot_schema_version = models.CharField(max_length=32, default="v1", verbose_name=_("Версія snapshot-схеми"))
    payload_version = models.CharField(max_length=32, default="v1", verbose_name=_("Версія payload"))
    rollout_state = models.CharField(max_length=32, default="shadow", verbose_name=_("Стан rollout"))
    feature_flags = models.JSONField(default=dict, blank=True, verbose_name=_("Feature flags"))
    formula_defaults = models.JSONField(default=dict, blank=True, verbose_name=_("Дефолти формул"))
    mosaic_config = models.JSONField(default=dict, blank=True, verbose_name=_("Конфіг MOSAIC"))
    payroll_config = models.JSONField(default=dict, blank=True, verbose_name=_("Конфіг payroll"))
    forecast_config = models.JSONField(default=dict, blank=True, verbose_name=_("Конфіг forecast"))
    telephony_config = models.JSONField(default=dict, blank=True, verbose_name=_("Конфіг телфонії"))
    ui_config = models.JSONField(default=dict, blank=True, verbose_name=_("UI конфіг"))
    validation_state = models.JSONField(default=dict, blank=True, verbose_name=_("Стан валідації"))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Налаштування статистики")
        verbose_name_plural = _("Налаштування статистики")

    def __str__(self):
        return "ManagementStatsConfig"


class ComponentReadiness(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", _("Активно")
        SHADOW = "shadow", _("Тіньовий режим")
        DORMANT = "dormant", _("Неактивно")

    component = models.CharField(max_length=64, unique=True, verbose_name=_("Компонент"))
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SHADOW, db_index=True)
    notes = models.TextField(blank=True, verbose_name=_("Нотатки"))
    meta = models.JSONField(default=dict, blank=True, verbose_name=_("Мета"))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Готовність компонента")
        verbose_name_plural = _("Готовність компонентів")
        ordering = ["component"]

    def __str__(self):
        return f"{self.component}: {self.status}"


class DuplicateReview(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", _("Відкрито")
        RESOLVED = "resolved", _("Закрито")

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="management_duplicate_reviews",
        verbose_name=_("Ініціатор"),
    )
    zone = models.CharField(max_length=20, db_index=True, verbose_name=_("Зона"))
    incoming_shop_name = models.CharField(max_length=255, verbose_name=_("Вхідна назва"))
    incoming_phone = models.CharField(max_length=50, verbose_name=_("Вхідний номер"))
    incoming_payload = models.JSONField(default=dict, blank=True, verbose_name=_("Вхідні дані"))
    candidate_summary = models.JSONField(default=list, blank=True, verbose_name=_("Кандидати"))
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True, db_index=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="management_duplicate_reviews_resolved",
        verbose_name=_("Закрив"),
    )
    resolution_note = models.TextField(blank=True, verbose_name=_("Нотатка по рішенню"))

    class Meta:
        verbose_name = _("Перевірка дубля")
        verbose_name_plural = _("Перевірки дублів")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.incoming_shop_name} [{self.zone}]"


class ClientInteractionAttempt(models.Model):
    class VerificationLevel(models.TextChoices):
        SELF_REPORTED = "self_reported", _("Самозвіт")
        LINKED_EVIDENCE = "linked_evidence", _("Підтверджено доказом")
        OVERRIDE = "override", _("З override перевіркою")

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="interaction_attempts",
        verbose_name=_("Клієнт"),
    )
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="management_client_interactions",
        verbose_name=_("Менеджер"),
    )
    result = models.CharField(_("Підсумок"), max_length=50, choices=Client.CallResult.choices, db_index=True)
    reason_code = models.CharField(_("Код причини"), max_length=64, blank=True, db_index=True)
    reason_note = models.TextField(_("Коментар причини"), blank=True)
    context = models.JSONField(_("Контекст"), default=dict, blank=True)
    details = models.TextField(_("Деталі"), blank=True)
    next_call_at = models.DateTimeField(_("Наступний дзвінок"), null=True, blank=True)
    verification_level = models.CharField(
        _("Рівень верифікації"),
        max_length=32,
        choices=VerificationLevel.choices,
        default=VerificationLevel.SELF_REPORTED,
        db_index=True,
    )
    linked_shop = models.ForeignKey(
        "management.Shop",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="client_interaction_attempts",
        verbose_name=_("Пов'язаний магазин"),
    )
    cp_log = models.ForeignKey(
        "management.CommercialOfferEmailLog",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="client_interaction_attempts",
        verbose_name=_("Лог КП"),
    )
    duplicate_review = models.ForeignKey(
        "management.DuplicateReview",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="interaction_attempts",
        verbose_name=_("Перевірка дубля"),
    )
    duplicate_override_reason = models.TextField(_("Причина override"), blank=True)
    messenger_type = models.CharField(_("Месенджер"), max_length=32, blank=True)
    messenger_target_mode = models.CharField(_("Режим цілі месенджера"), max_length=32, blank=True)
    messenger_target_value = models.CharField(_("Ціль месенджера"), max_length=255, blank=True)
    xml_platform = models.CharField(_("XML платформа"), max_length=32, blank=True)
    xml_resource_url = models.CharField(_("XML ресурс"), max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("Спроба взаємодії з клієнтом")
        verbose_name_plural = _("Спроби взаємодії з клієнтами")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["manager", "-created_at"], name="mgmt_client_attempt_mgr_dt"),
            models.Index(fields=["client", "-created_at"], name="mgmt_client_attempt_cli_dt"),
        ]

    def __str__(self):
        return f"{self.client_id}: {self.result}"


class ClientCPLink(models.Model):
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="cp_links",
        verbose_name=_("Клієнт"),
    )
    cp_log = models.ForeignKey(
        "management.CommercialOfferEmailLog",
        on_delete=models.CASCADE,
        related_name="client_links",
        verbose_name=_("Лог КП"),
    )
    linked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="management_client_cp_links",
        verbose_name=_("Прив'язав"),
    )
    interaction = models.ForeignKey(
        "management.ClientInteractionAttempt",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cp_links",
        verbose_name=_("Спроба взаємодії"),
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("Зв'язок клієнта з КП")
        verbose_name_plural = _("Зв'язки клієнтів з КП")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["client", "cp_log"], name="mgmt_client_cp_unique"),
        ]

    def __str__(self):
        return f"{self.client_id} -> {self.cp_log_id}"


class CommandRunLog(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", _("Виконується")
        SUCCESS = "success", _("Успішно")
        FAILED = "failed", _("Помилка")
        PARTIAL = "partial", _("Частково")

    command_name = models.CharField(max_length=128, db_index=True, verbose_name=_("Команда"))
    run_key = models.CharField(max_length=128, unique=True, verbose_name=_("Ключ запуску"))
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RUNNING, db_index=True)
    rows_processed = models.PositiveIntegerField(default=0, verbose_name=_("Оброблено рядків"))
    warnings_count = models.PositiveIntegerField(default=0, verbose_name=_("Попереджень"))
    error_excerpt = models.TextField(blank=True, verbose_name=_("Короткий текст помилки"))
    meta = models.JSONField(default=dict, blank=True, verbose_name=_("Мета"))
    started_at = models.DateTimeField(auto_now_add=True, db_index=True)
    finished_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = _("Лог запуску команди")
        verbose_name_plural = _("Логи запуску команд")
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["command_name", "-started_at"], name="mgmt_cmd_name_dt"),
            models.Index(fields=["status", "-started_at"], name="mgmt_cmd_status_dt"),
        ]

    def mark_finished(self, *, status: str, rows_processed: int = 0, warnings_count: int = 0, error_excerpt: str = ""):
        self.status = status
        self.rows_processed = max(0, int(rows_processed or 0))
        self.warnings_count = max(0, int(warnings_count or 0))
        self.error_excerpt = (error_excerpt or "").strip()
        self.finished_at = timezone.now()
        self.save(update_fields=["status", "rows_processed", "warnings_count", "error_excerpt", "finished_at"])

    def __str__(self):
        return f"{self.command_name} [{self.status}]"


class ManagerDayStatus(models.Model):
    class Status(models.TextChoices):
        WORKING = "working", _("Робочий день")
        WEEKEND = "weekend", _("Вихідний")
        HOLIDAY = "holiday", _("Свято")
        VACATION = "vacation", _("Відпустка")
        SICK = "sick", _("Лікарняний")
        EXCUSED = "excused", _("Погоджена відсутність")
        TECH_FAILURE = "tech_failure", _("Технічний збій")
        FORCE_MAJEURE = "force_majeure", _("Форс-мажор")

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="management_day_statuses",
        verbose_name=_("Менеджер"),
    )
    day = models.DateField(db_index=True, verbose_name=_("День"))
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.WORKING, db_index=True)
    capacity_factor = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("1.00"), verbose_name=_("Фактор доступності"))
    source_reason = models.CharField(max_length=255, blank=True, verbose_name=_("Причина / джерело"))
    reintegration_flag = models.BooleanField(default=False, verbose_name=_("Період повернення"))
    meta = models.JSONField(default=dict, blank=True, verbose_name=_("Мета"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Статус дня менеджера")
        verbose_name_plural = _("Статуси днів менеджера")
        ordering = ["-day"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "day"], name="mgmt_day_owner_unique"),
        ]
        indexes = [
            models.Index(fields=["owner", "-day"], name="mgmt_day_owner_dt"),
            models.Index(fields=["status", "-day"], name="mgmt_day_status_dt"),
        ]

    def save(self, *args, **kwargs):
        value = Decimal(self.capacity_factor or 0)
        value = max(Decimal("0.00"), min(Decimal("1.00"), value))
        self.capacity_factor = value
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.owner_id}:{self.day} {self.status}"


class NightlyScoreSnapshot(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="management_score_snapshots",
        verbose_name=_("Менеджер"),
    )
    snapshot_date = models.DateField(db_index=True, verbose_name=_("Локальна дата"))
    formula_version = models.CharField(max_length=64, verbose_name=_("Версія формули"))
    defaults_version = models.CharField(max_length=64, verbose_name=_("Версія дефолтів"))
    snapshot_schema_version = models.CharField(max_length=32, verbose_name=_("Версія snapshot-схеми"))
    payload_version = models.CharField(max_length=32, verbose_name=_("Версія payload"))
    kpd_value = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"), verbose_name=_("KPD"))
    mosaic_score = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"), verbose_name=_("MOSAIC"))
    score_confidence = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name=_("Рівень довіри"))
    working_day_factor = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("1.00"), verbose_name=_("Фактор робочого дня"))
    freshness_seconds = models.PositiveIntegerField(default=0, verbose_name=_("Freshness, сек"))
    payload = models.JSONField(default=dict, blank=True, verbose_name=_("Payload"))
    job_run = models.ForeignKey(
        CommandRunLog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="snapshots",
        verbose_name=_("Лог запуску"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Нічний snapshot score")
        verbose_name_plural = _("Нічні snapshot-и score")
        ordering = ["-snapshot_date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "snapshot_date"], name="mgmt_snapshot_owner_day_unique"),
        ]
        indexes = [
            models.Index(fields=["owner", "-snapshot_date"], name="mgmt_snapshot_owner_dt"),
        ]

    def __str__(self):
        return f"{self.owner_id}:{self.snapshot_date} {self.mosaic_score}"


class ScoreAppeal(models.Model):
    class AppealType(models.TextChoices):
        SCORE = "score", _("Score")
        FREEZE = "freeze", _("Freeze")
        OWNERSHIP = "ownership", _("Ownership")

    class Status(models.TextChoices):
        OPEN = "open", _("Відкрито")
        APPROVED = "approved", _("Підтверджено")
        REJECTED = "rejected", _("Відхилено")

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="management_score_appeals",
        verbose_name=_("Менеджер"),
    )
    snapshot = models.ForeignKey(
        NightlyScoreSnapshot,
        on_delete=models.CASCADE,
        related_name="appeals",
        verbose_name=_("Snapshot"),
    )
    appeal_type = models.CharField(max_length=20, choices=AppealType.choices, default=AppealType.SCORE, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True)
    reason_code = models.CharField(max_length=64, blank=True, verbose_name=_("Код причини"))
    reason = models.TextField(verbose_name=_("Причина"))
    manager_note = models.TextField(blank=True, verbose_name=_("Нотатка менеджера"))
    evidence = models.JSONField(default=dict, blank=True, verbose_name=_("Докази"))
    evidence_payload = models.JSONField(default=dict, blank=True, verbose_name=_("Payload доказів"))
    resolution_note = models.TextField(blank=True, verbose_name=_("Рішення"))
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_management_score_appeals",
        verbose_name=_("Розглянув"),
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    opened_at = models.DateTimeField(default=timezone.now, db_index=True)
    due_at = models.DateTimeField(null=True, blank=True, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = _("Оскарження score")
        verbose_name_plural = _("Оскарження score")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "status", "-created_at"], name="mgmt_appeal_owner_st"),
        ]

    def mark_resolved(self, status: str, resolution_note: str):
        self.status = status
        self.resolution_note = (resolution_note or "").strip()
        self.resolved_at = timezone.now()
        self.save(update_fields=["status", "resolution_note", "resolved_at"])

    def __str__(self):
        return f"{self.owner_id}:{self.status}"


class ManagerCommissionAccrual(models.Model):
    class AccrualType(models.TextChoices):
        NEW = "new", _("Новий")
        REPEAT = "repeat", _("Повторний")
        REACTIVATION = "reactivation", _("Реактивація")
        RESCUE_SPIFF = "rescue_spiff", _("Rescue SPIFF")
        MANUAL = "manual", _("Ручне")

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='management_commission_accruals',
        verbose_name=_('Менеджер'),
    )
    invoice = models.OneToOneField(
        'orders.WholesaleInvoice',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='management_commission_accrual',
        verbose_name=_('Накладна'),
    )
    source_snapshot = models.ForeignKey(
        NightlyScoreSnapshot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="commission_accruals",
        verbose_name=_("Source snapshot"),
    )

    accrual_type = models.CharField(max_length=20, choices=AccrualType.choices, default=AccrualType.MANUAL, db_index=True)
    base_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name=_('База (грн)'))
    percent = models.DecimalField(max_digits=6, decimal_places=2, default=0, verbose_name=_('Відсоток'))
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name=_('Нараховано (грн)'))
    note = models.CharField(max_length=255, blank=True, verbose_name=_('Пояснення'))
    freeze_reason_code = models.CharField(max_length=64, blank=True, verbose_name=_("Код причини заморозки"))
    freeze_reason_text = models.TextField(blank=True, verbose_name=_("Причина заморозки"))
    working_factor_applied = models.DecimalField(max_digits=5, decimal_places=4, default=1, verbose_name=_("Working factor"))
    evidence_payload = models.JSONField(default=dict, blank=True, verbose_name=_("Payload доказів"))

    frozen_until = models.DateTimeField(db_index=True, verbose_name=_('Заморожено до'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Нарахування менеджера')
        verbose_name_plural = _('Нарахування менеджера')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner', '-created_at'], name='mgmt_comm_owner_dt'),
            models.Index(fields=['owner', 'frozen_until'], name='mgmt_comm_owner_frz'),
        ]

    def __str__(self):
        return f"{self.owner_id}: +{self.amount}"


class ManagerPayoutRequest(models.Model):
    class Status(models.TextChoices):
        PROCESSING = 'processing', _('В обробці')
        APPROVED = 'approved', _('Схвалено')
        REJECTED = 'rejected', _('Відхилено')
        PAID = 'paid', _('Виплачено')

    class Kind(models.TextChoices):
        REQUEST = 'request', _('Запит менеджера')
        MANUAL = 'manual', _('Ручний запис')

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='management_payout_requests',
        verbose_name=_('Менеджер'),
    )

    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.REQUEST, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_('Сума (грн)'))

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROCESSING, db_index=True)
    rejection_reason = models.TextField(blank=True, verbose_name=_('Причина (якщо відхилено)'))

    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_management_payout_requests',
        verbose_name=_('Обробив (адмін)'),
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True, db_index=True)
    rejected_at = models.DateTimeField(null=True, blank=True, db_index=True)
    paid_at = models.DateTimeField(null=True, blank=True, db_index=True)

    admin_tg_chat_id = models.BigIntegerField(null=True, blank=True)
    admin_tg_message_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = _('Запит на виплату')
        verbose_name_plural = _('Запити на виплату')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner', 'status', '-created_at'], name='mgmt_pay_owner_st'),
            models.Index(fields=['status', '-created_at'], name='mgmt_pay_st_dt'),
        ]

    def __str__(self):
        return f"{self.owner_id}: {self.status} {self.amount}"


class PayoutRejectionReasonRequest(models.Model):
    payout_request = models.ForeignKey(
        ManagerPayoutRequest,
        on_delete=models.CASCADE,
        related_name='rejection_reason_requests',
    )
    admin_chat_id = models.BigIntegerField(db_index=True)
    prompt_message_id = models.BigIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Причина відхилення виплати (запит)')
        verbose_name_plural = _('Причини відхилення виплати (запити)')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['admin_chat_id', 'is_active'], name='mgmt_payrej_chat_act'),
        ]

    def __str__(self):
        return f"{self.payout_request_id} ({'active' if self.is_active else 'closed'})"


class ContractSequence(models.Model):
    year = models.PositiveIntegerField(unique=True)
    last_number = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Нумерація договорів (рік)")
        verbose_name_plural = _("Нумерація договорів (рік)")

    def __str__(self):
        return f"{self.year}: {self.last_number}"


class ManagementContract(models.Model):
    REVIEW_STATUS_CHOICES = [
        ('draft', 'Чернетка'),
        ('pending', 'На перевірці'),
        ('approved', 'Підтверджено'),
        ('rejected', 'Відхилено'),
    ]

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="management_contracts",
        verbose_name=_("Менеджер"),
    )
    contract_number = models.CharField(max_length=50, unique=True, verbose_name=_("Номер договору"))
    contract_date = models.DateField(verbose_name=_("Дата договору"))
    realizer_name = models.CharField(max_length=255, verbose_name=_("Реалізатор"))
    file_path = models.CharField(max_length=500, verbose_name=_("Шлях до файлу"))
    review_status = models.CharField(
        max_length=20,
        choices=REVIEW_STATUS_CHOICES,
        default='draft',
        verbose_name=_("Статус перевірки"),
    )
    review_reject_reason = models.TextField(blank=True, verbose_name=_("Причина відхилення"))
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Дата перевірки"))
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_management_contracts',
        verbose_name=_("Перевірив (адмін)"),
    )
    admin_tg_chat_id = models.BigIntegerField(null=True, blank=True, verbose_name=_("Telegram admin chat id"))
    admin_tg_message_id = models.BigIntegerField(null=True, blank=True, verbose_name=_("Telegram admin message id"))
    is_approved = models.BooleanField(default=False, verbose_name=_("Підтверджено"))
    payload = models.JSONField(default=dict, blank=True, verbose_name=_("Дані договору"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Договір (менеджмент)")
        verbose_name_plural = _("Договори (менеджмент)")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.contract_number} ({self.realizer_name})"


class ContractRejectionReasonRequest(models.Model):
    contract = models.ForeignKey(
        ManagementContract,
        on_delete=models.CASCADE,
        related_name='rejection_reason_requests',
        verbose_name=_("Договір"),
    )
    admin_chat_id = models.BigIntegerField(db_index=True, verbose_name=_("Telegram chat id (адмін)"))
    prompt_message_id = models.BigIntegerField(null=True, blank=True, verbose_name=_("Message id запиту"))
    is_active = models.BooleanField(default=True, db_index=True, verbose_name=_("Активний запит"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Запит причини відхилення договору")
        verbose_name_plural = _("Запити причин відхилення договорів")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['admin_chat_id', 'is_active'], name='mgmt_contractrej_chat_act'),
        ]

    def __str__(self):
        return f"{self.contract_id} ({'active' if self.is_active else 'closed'})"


class OwnershipChangeLog(models.Model):
    class EntityType(models.TextChoices):
        CLIENT = "client", _("Клієнт")
        LEAD = "lead", _("Лід")
        SHOP = "shop", _("Магазин")

    entity_type = models.CharField(max_length=20, choices=EntityType.choices, db_index=True, verbose_name=_("Тип сутності"))
    entity_id = models.PositiveIntegerField(db_index=True, verbose_name=_("ID сутності"))
    previous_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="management_previous_ownership_changes",
        verbose_name=_("Попередній owner"),
    )
    new_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="management_new_ownership_changes",
        verbose_name=_("Новий owner"),
    )
    reason = models.CharField(max_length=255, blank=True, verbose_name=_("Причина"))
    payload = models.JSONField(default=dict, blank=True, verbose_name=_("Payload"))
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("Лог зміни ownership")
        verbose_name_plural = _("Логи зміни ownership")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id", "-created_at"], name="mgmt_ownerchange_ent"),
        ]

    def __str__(self):
        return f"{self.entity_type}:{self.entity_id}"


class TelephonyWebhookLog(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", _("Очікує")
        PROCESSED = "processed", _("Оброблено")
        FAILED = "failed", _("Помилка")
        IGNORED = "ignored", _("Пропущено")

    provider = models.CharField(max_length=64, db_index=True, verbose_name=_("Провайдер"))
    external_event_id = models.CharField(max_length=255, verbose_name=_("Зовнішній event ID"))
    event_type = models.CharField(max_length=128, blank=True, verbose_name=_("Тип події"))
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    payload = models.JSONField(default=dict, blank=True, verbose_name=_("Payload"))
    error_excerpt = models.TextField(blank=True, verbose_name=_("Помилка"))
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = _("Webhook IP-телефонії")
        verbose_name_plural = _("Webhook-и IP-телефонії")
        ordering = ["-received_at"]
        constraints = [
            models.UniqueConstraint(fields=["provider", "external_event_id"], name="mgmt_tel_event_unique"),
        ]
        indexes = [
            models.Index(fields=["provider", "status", "-received_at"], name="mgmt_tel_provider_st"),
        ]

    def __str__(self):
        return f"{self.provider}:{self.external_event_id}"


class CallRecord(models.Model):
    class Direction(models.TextChoices):
        INBOUND = "inbound", _("Вхідний")
        OUTBOUND = "outbound", _("Вихідний")
        UNKNOWN = "unknown", _("Невідомо")

    class QaStatus(models.TextChoices):
        PENDING = "pending", _("Очікує QA")
        REVIEWED = "reviewed", _("Перевірено")
        EXEMPT = "exempt", _("Без QA")

    provider = models.CharField(max_length=64, db_index=True, verbose_name=_("Провайдер"))
    external_call_id = models.CharField(max_length=255, verbose_name=_("Зовнішній call ID"))
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="management_call_records",
        verbose_name=_("Менеджер"),
    )
    matched_client = models.ForeignKey(
        Client,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="call_records",
        verbose_name=_("Матчений клієнт"),
    )
    phone = models.CharField(max_length=64, blank=True, verbose_name=_("Телефон"))
    direction = models.CharField(max_length=20, choices=Direction.choices, default=Direction.UNKNOWN, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True, db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0, verbose_name=_("Тривалість, сек"))
    recording_url = models.URLField(blank=True, verbose_name=_("Recording URL"))
    transcript_excerpt = models.TextField(blank=True, verbose_name=_("Уривок транскрипту"))
    qa_status = models.CharField(max_length=20, choices=QaStatus.choices, default=QaStatus.PENDING, db_index=True)
    payload = models.JSONField(default=dict, blank=True, verbose_name=_("Payload"))
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Запис дзвінка")
        verbose_name_plural = _("Записи дзвінків")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["provider", "external_call_id"], name="mgmt_call_provider_ext_unique"),
        ]
        indexes = [
            models.Index(fields=["manager", "-created_at"], name="mgmt_call_mgr_dt"),
            models.Index(fields=["qa_status", "-created_at"], name="mgmt_call_qa_dt"),
        ]

    def __str__(self):
        return f"{self.provider}:{self.external_call_id}"


class TelephonyHealthSnapshot(models.Model):
    class Status(models.TextChoices):
        HEALTHY = "healthy", _("Здорово")
        DEGRADED = "degraded", _("Деградація")
        OUTAGE = "outage", _("Недоступно")

    provider = models.CharField(max_length=64, db_index=True, verbose_name=_("Провайдер"))
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DEGRADED, db_index=True)
    total_events = models.PositiveIntegerField(default=0, verbose_name=_("Усього подій"))
    unmatched_calls = models.PositiveIntegerField(default=0, verbose_name=_("Не змечені дзвінки"))
    backlog_count = models.PositiveIntegerField(default=0, verbose_name=_("Backlog"))
    meta = models.JSONField(default=dict, blank=True, verbose_name=_("Meta"))
    snapshot_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("Health snapshot IP-телефонії")
        verbose_name_plural = _("Health snapshot-и IP-телефонії")
        ordering = ["-snapshot_at"]
        indexes = [
            models.Index(fields=["provider", "-snapshot_at"], name="mgmt_tel_health_dt"),
        ]

    def __str__(self):
        return f"{self.provider}:{self.status}"


class CallQAReview(models.Model):
    class Verdict(models.TextChoices):
        PASS = "pass", _("ОК")
        COACHING = "coaching", _("Потрібен коучинг")
        FAIL = "fail", _("Провал")

    call_record = models.ForeignKey(CallRecord, on_delete=models.CASCADE, related_name="qa_reviews", verbose_name=_("Дзвінок"))
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="call_qa_reviews",
        verbose_name=_("Перевірив"),
    )
    score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name=_("QA score"))
    verdict = models.CharField(max_length=20, choices=Verdict.choices, default=Verdict.PASS, db_index=True)
    notes = models.TextField(blank=True, verbose_name=_("Нотатки"))
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("QA review дзвінка")
        verbose_name_plural = _("QA reviews дзвінків")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.call_record_id}:{self.verdict}"


class SupervisorActionLog(models.Model):
    class ActionType(models.TextChoices):
        COACHING = "coaching", _("Коучинг")
        ESCALATION = "escalation", _("Ескалація")
        FREEZE_OVERRIDE = "freeze_override", _("Override freeze")
        APPEAL_RESOLUTION = "appeal_resolution", _("Рішення по апеляції")

    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="supervisor_actions",
        verbose_name=_("Менеджер"),
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="performed_supervisor_actions",
        verbose_name=_("Хто виконав"),
    )
    action_type = models.CharField(max_length=32, choices=ActionType.choices, db_index=True)
    payload = models.JSONField(default=dict, blank=True, verbose_name=_("Payload"))
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("Лог дії супервайзера")
        verbose_name_plural = _("Логи дій супервайзера")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action_type", "-created_at"], name="mgmt_supervisor_act"),
        ]

    def __str__(self):
        return f"{self.action_type}:{self.manager_id}"


class DtfBridgeSnapshot(models.Model):
    class Status(models.TextChoices):
        FRESH = "fresh", _("Актуально")
        DEGRADED = "degraded", _("Деградація")
        STALE = "stale", _("Застаріло")

    source_key = models.CharField(max_length=64, db_index=True, verbose_name=_("Ключ джерела"))
    snapshot_date = models.DateField(db_index=True, verbose_name=_("Дата snapshot"))
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DEGRADED, db_index=True)
    freshness_seconds = models.PositiveIntegerField(default=0, verbose_name=_("Freshness, сек"))
    payload = models.JSONField(default=dict, blank=True, verbose_name=_("Payload"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("DTF bridge snapshot")
        verbose_name_plural = _("DTF bridge snapshots")
        ordering = ["-snapshot_date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["source_key", "snapshot_date"], name="mgmt_dtf_source_day_unique"),
        ]
        indexes = [
            models.Index(fields=["source_key", "-snapshot_date"], name="mgmt_dtf_source_dt"),
        ]

    def __str__(self):
        return f"{self.source_key}:{self.snapshot_date}"
