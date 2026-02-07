from decimal import Decimal
import uuid

from django.conf import settings
from django.db import models, IntegrityError, transaction
from django.db.models import Max
from django.utils.html import escape
from django.utils.text import slugify
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

try:
    import markdown as markdown_lib
except Exception:  # pragma: no cover - fallback when optional dependency is missing
    markdown_lib = None


def render_markdown_to_html(source: str) -> str:
    source = (source or "").strip()
    if not source:
        return ""
    if markdown_lib:
        return markdown_lib.markdown(
            source,
            extensions=["extra", "sane_lists"],
        )
    # Fallback keeps output safe and readable if Markdown package is unavailable.
    return "<p>{}</p>".format("<br>".join(escape(source).splitlines()))


class ContactChannel(models.TextChoices):
    TELEGRAM = "telegram", _("Telegram")
    WHATSAPP = "whatsapp", _("WhatsApp")
    INSTAGRAM = "instagram", _("Instagram")
    CALL = "call", _("Телефонний дзвінок")


class LeadType(models.TextChoices):
    HELP = "help", _("Потрібна допомога")
    CONSULTATION = "consultation", _("Консультація")
    FAB = "fab", _("Заявка з кнопки")


class LeadStatus(models.TextChoices):
    NEW = "new", _("Нова")
    IN_PROGRESS = "in_progress", _("В роботі")
    CLOSED = "closed", _("Закрита")


class DtfLead(models.Model):
    lead_number = models.CharField(max_length=24, unique=True, blank=True)
    lead_type = models.CharField(max_length=20, choices=LeadType.choices, default=LeadType.HELP)
    status = models.CharField(max_length=20, choices=LeadStatus.choices, default=LeadStatus.NEW)

    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=32, db_index=True)
    contact_channel = models.CharField(max_length=20, choices=ContactChannel.choices, default=ContactChannel.TELEGRAM)
    contact_handle = models.CharField(max_length=200, blank=True)

    city = models.CharField(max_length=100, blank=True)
    np_branch = models.CharField(max_length=200, blank=True)

    task_description = models.TextField(blank=True)
    deadline_note = models.CharField(max_length=200, blank=True)
    folder_link = models.URLField(blank=True)
    source = models.CharField(max_length=50, blank=True, default="")

    manager_note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "DTF Lead"
        verbose_name_plural = "DTF Leads"

    def __str__(self):
        return f"{self.lead_number or 'DTF Lead'} — {self.name}"

    def save(self, *args, **kwargs):
        attempts = 0
        while True:
            if not self.lead_number:
                self.lead_number = self.generate_lead_number()
            try:
                with transaction.atomic():
                    super().save(*args, **kwargs)
                break
            except IntegrityError:
                attempts += 1
                if attempts >= 5:
                    raise
                self.lead_number = None

    @staticmethod
    def generate_lead_number():
        today = timezone.localdate()
        date_str = today.strftime('%d%m%Y')
        prefix = f"DTF{date_str}L"
        last = DtfLead.objects.filter(lead_number__startswith=prefix).aggregate(Max('lead_number'))
        max_number = last.get('lead_number__max')
        if max_number:
            try:
                suffix = max_number.replace(prefix, '')
                counter = int(suffix) + 1
            except ValueError:
                counter = 1
        else:
            counter = 1
        return f"{prefix}{counter:02d}"


class DtfLeadAttachment(models.Model):
    lead = models.ForeignKey(DtfLead, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="dtf/leads/")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "DTF Lead Attachment"
        verbose_name_plural = "DTF Lead Attachments"

    def __str__(self):
        return f"Attachment for {self.lead_id}"


class OrderStatus(models.TextChoices):
    NEW_LEAD = "new_lead", _("Прийнято (заявка)")
    NEW_ORDER = "new_order", _("Прийнято")
    CHECK_MOCKUP = "check_mockup", _("Перевірка макета")
    NEED_FIX = "need_fix", _("Потрібні правки")
    AWAITING_PAYMENT = "awaiting_payment", _("Очікує оплати")
    PRINTING = "printing", _("У друці")
    READY = "ready", _("Готово")
    SHIPPED = "shipped", _("Відправлено")
    CLOSED = "closed", _("Закрито")


class DtfLifecycleStatus(models.TextChoices):
    NEW = "new", _("Нове")
    NEEDS_REVIEW = "needs_review", _("Потребує перевірки")
    CONFIRMED = "confirmed", _("Підтверджено")
    IN_PRODUCTION = "in_production", _("У виробництві")
    QA_CHECK = "qa_check", _("Контроль якості")
    PACKED = "packed", _("Упаковано")
    SHIPPED = "shipped", _("Відправлено")
    DELIVERED = "delivered", _("Доставлено")
    CANCELLED = "cancelled", _("Скасовано")


class OrderType(models.TextChoices):
    READY = "ready", _("Готовий ганг-лист")
    HELP = "help", _("Потрібна допомога")


class LengthSource(models.TextChoices):
    MANUAL = "manual", _("Ручний ввід")
    AUTO = "auto", _("Автовизначення")


class DtfOrder(models.Model):
    order_number = models.CharField(max_length=24, unique=True, blank=True)
    order_type = models.CharField(max_length=20, choices=OrderType.choices, default=OrderType.READY)
    status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.CHECK_MOCKUP)
    lifecycle_status = models.CharField(
        max_length=24,
        choices=DtfLifecycleStatus.choices,
        default=DtfLifecycleStatus.NEW,
        db_index=True,
    )

    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=32, db_index=True)
    contact_channel = models.CharField(max_length=20, choices=ContactChannel.choices, default=ContactChannel.TELEGRAM)
    contact_handle = models.CharField(max_length=200, blank=True)

    city = models.CharField(max_length=100)
    np_branch = models.CharField(max_length=200)

    gang_file = models.FileField(upload_to="dtf/orders/", blank=True)
    length_m = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    length_source = models.CharField(max_length=10, choices=LengthSource.choices, default=LengthSource.MANUAL)
    copies = models.PositiveIntegerField(default=1)

    meters_total = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_per_meter = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    price_total = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    pricing_tier = models.CharField(max_length=50, blank=True)
    requires_review = models.BooleanField(default=False)

    comment = models.TextField(blank=True)
    need_fix_reason = models.CharField(max_length=255, blank=True)
    tracking_number = models.CharField(max_length=64, blank=True)
    manager_note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "DTF Order"
        verbose_name_plural = "DTF Orders"

    def __str__(self):
        return f"{self.order_number or 'DTF Order'} — {self.name}"

    def save(self, *args, **kwargs):
        attempts = 0
        while True:
            if not self.order_number:
                self.order_number = self.generate_order_number()
            try:
                with transaction.atomic():
                    super().save(*args, **kwargs)
                break
            except IntegrityError:
                attempts += 1
                if attempts >= 5:
                    raise
                self.order_number = None

    @staticmethod
    def generate_order_number():
        today = timezone.localdate()
        date_str = today.strftime('%d%m%Y')
        prefix = f"DTF{date_str}N"
        last = DtfOrder.objects.filter(order_number__startswith=prefix).aggregate(Max('order_number'))
        max_number = last.get('order_number__max')
        if max_number:
            try:
                suffix = max_number.replace(prefix, '')
                counter = int(suffix) + 1
            except ValueError:
                counter = 1
        else:
            counter = 1
        return f"{prefix}{counter:02d}"

    def transition_lifecycle(self, to_status: str, *, actor: str = "system", public_message: str = "", internal_message: str = ""):
        transitions = {
            DtfLifecycleStatus.NEW: {DtfLifecycleStatus.NEEDS_REVIEW, DtfLifecycleStatus.CONFIRMED, DtfLifecycleStatus.CANCELLED},
            DtfLifecycleStatus.NEEDS_REVIEW: {DtfLifecycleStatus.CONFIRMED, DtfLifecycleStatus.CANCELLED},
            DtfLifecycleStatus.CONFIRMED: {DtfLifecycleStatus.IN_PRODUCTION, DtfLifecycleStatus.CANCELLED},
            DtfLifecycleStatus.IN_PRODUCTION: {DtfLifecycleStatus.QA_CHECK, DtfLifecycleStatus.CANCELLED},
            DtfLifecycleStatus.QA_CHECK: {DtfLifecycleStatus.PACKED, DtfLifecycleStatus.CANCELLED},
            DtfLifecycleStatus.PACKED: {DtfLifecycleStatus.SHIPPED, DtfLifecycleStatus.CANCELLED},
            DtfLifecycleStatus.SHIPPED: {DtfLifecycleStatus.DELIVERED},
            DtfLifecycleStatus.DELIVERED: set(),
            DtfLifecycleStatus.CANCELLED: set(),
        }
        current = self.lifecycle_status or DtfLifecycleStatus.NEW
        if to_status == current:
            return None
        if to_status not in transitions.get(current, set()):
            raise ValueError(f"Invalid transition from {current} to {to_status}")

        self.lifecycle_status = to_status
        self.save(update_fields=["lifecycle_status", "updated_at"])
        return DtfStatusEvent.objects.create(
            order=self,
            status_from=current,
            status_to=to_status,
            actor=actor,
            public_message=public_message or "",
            internal_message=internal_message or "",
        )


class DtfPricingConfig(models.Model):
    name = models.CharField(max_length=120, default="Default DTF pricing")
    is_active = models.BooleanField(default=True, db_index=True)
    effective_from = models.DateField(default=timezone.localdate, db_index=True)
    version = models.PositiveIntegerField(default=1)

    width_cm = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("60.00"))
    min_order_m = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("1.00"))
    base_price_per_meter = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("350.00"))
    tiers_json = models.JSONField(
        default=list,
        blank=True,
        help_text="List of objects: [{\"min_m\": 10, \"rate\": 330}, ...]",
    )
    urgency_multipliers_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Dict of urgency multipliers, e.g. {'standard': 1.0, 'rush': 1.2}",
    )
    layout_help_fee = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    shipping_estimate_fee = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    validity_days = models.PositiveIntegerField(default=7)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-effective_from", "-id"]
        verbose_name = "DTF Pricing Config"
        verbose_name_plural = "DTF Pricing Configs"

    def __str__(self):
        return f"{self.name} v{self.version} ({self.effective_from})"


class DtfUpload(models.Model):
    file = models.FileField(upload_to="dtf/uploads/")
    size_bytes = models.PositiveBigIntegerField(default=0)
    mime_type = models.CharField(max_length=120, blank=True)
    sha256 = models.CharField(max_length=64, db_index=True)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="dtf_uploads",
    )
    lead = models.ForeignKey("DtfLead", null=True, blank=True, on_delete=models.SET_NULL, related_name="uploads")
    order = models.ForeignKey("DtfOrder", null=True, blank=True, on_delete=models.SET_NULL, related_name="uploads")
    source = models.CharField(max_length=40, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "DTF Upload"
        verbose_name_plural = "DTF Uploads"

    def __str__(self):
        return f"{self.sha256[:12]}… ({self.mime_type or 'unknown'})"


class DtfPreflightResult(models.TextChoices):
    PASS = "pass", _("PASS")
    WARN = "warn", _("WARN")
    FAIL = "fail", _("FAIL")


class DtfPreflightReport(models.Model):
    upload = models.ForeignKey(DtfUpload, on_delete=models.CASCADE, related_name="preflight_reports")
    result = models.CharField(max_length=10, choices=DtfPreflightResult.choices, default=DtfPreflightResult.PASS)
    checks_json = models.JSONField(default=list, blank=True)
    metrics_json = models.JSONField(default=dict, blank=True)
    warnings_json = models.JSONField(default=list, blank=True)
    errors_json = models.JSONField(default=list, blank=True)

    thumbnail = models.ImageField(upload_to="dtf/preflight/thumbs/", blank=True)
    overlay_image = models.ImageField(upload_to="dtf/preflight/overlays/", blank=True)
    preflight_version = models.CharField(max_length=24, default="2.0")
    engine_version = models.CharField(max_length=24, default="1.0.0")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "DTF Preflight Report"
        verbose_name_plural = "DTF Preflight Reports"

    def __str__(self):
        return f"{self.get_result_display()} ({self.upload_id})"


class DtfQuote(models.Model):
    source = models.CharField(max_length=40, blank=True, default="")
    width_cm = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("60.00"))
    length_m = models.DecimalField(max_digits=8, decimal_places=2)
    urgency = models.CharField(max_length=20, default="standard")
    services_json = models.JSONField(default=dict, blank=True)
    shipping_method = models.CharField(max_length=40, blank=True, default="")

    unit_price = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    base_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    services_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    shipping_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=10, default="UAH")
    pricing_version = models.CharField(max_length=32, default="default")
    valid_until = models.DateField(null=True, blank=True)
    disclaimer = models.CharField(max_length=255, blank=True)

    order = models.ForeignKey("DtfOrder", null=True, blank=True, on_delete=models.SET_NULL, related_name="quotes")
    upload = models.ForeignKey("DtfUpload", null=True, blank=True, on_delete=models.SET_NULL, related_name="quotes")
    raw_inputs = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "DTF Quote"
        verbose_name_plural = "DTF Quotes"

    def __str__(self):
        return f"{self.total} {self.currency} ({self.length_m}m)"


class DtfStatusActor(models.TextChoices):
    SYSTEM = "system", _("System")
    MANAGER = "manager", _("Manager")
    CUSTOMER = "customer", _("Customer")


class DtfStatusEvent(models.Model):
    order = models.ForeignKey(DtfOrder, on_delete=models.CASCADE, related_name="status_events")
    status_from = models.CharField(max_length=24, choices=DtfLifecycleStatus.choices)
    status_to = models.CharField(max_length=24, choices=DtfLifecycleStatus.choices)
    actor = models.CharField(max_length=20, choices=DtfStatusActor.choices, default=DtfStatusActor.SYSTEM)
    public_message = models.CharField(max_length=255, blank=True)
    internal_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name = "DTF Status Event"
        verbose_name_plural = "DTF Status Events"

    def __str__(self):
        return f"{self.order_id}: {self.status_from} -> {self.status_to}"


class DtfEventLog(models.Model):
    event_name = models.CharField(max_length=80, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    order = models.ForeignKey("DtfOrder", null=True, blank=True, on_delete=models.SET_NULL, related_name="event_logs")
    quote = models.ForeignKey("DtfQuote", null=True, blank=True, on_delete=models.SET_NULL, related_name="event_logs")
    preflight_report = models.ForeignKey("DtfPreflightReport", null=True, blank=True, on_delete=models.SET_NULL, related_name="event_logs")
    ip_hash = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "DTF Event Log"
        verbose_name_plural = "DTF Event Logs"

    def __str__(self):
        return f"{self.event_name} ({self.created_at:%Y-%m-%d %H:%M})"


class KnowledgePostQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True, pub_date__lte=timezone.localdate())


class KnowledgePost(models.Model):
    title = models.CharField(max_length=220)
    slug = models.SlugField(max_length=240, unique=True)
    excerpt = models.CharField(max_length=320)
    content_md = models.TextField()
    content_html = models.TextField(blank=True, editable=False)
    pub_date = models.DateField(default=timezone.localdate, db_index=True)
    is_published = models.BooleanField(default=True)
    seo_title = models.CharField(max_length=160, blank=True)
    seo_description = models.CharField(max_length=220, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = KnowledgePostQuerySet.as_manager()

    class Meta:
        ordering = ["-pub_date", "-id"]
        verbose_name = "Knowledge Base Post"
        verbose_name_plural = "Knowledge Base Posts"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:240]
        self.content_html = render_markdown_to_html(self.content_md)
        if not self.seo_title:
            self.seo_title = self.title
        if not self.seo_description:
            source = (self.excerpt or self.content_md or "").strip()
            self.seo_description = source[:220]
        super().save(*args, **kwargs)


class WorkCategory(models.TextChoices):
    MACRO = "macro", _("Макро")
    PROCESS = "process", _("Процес")
    FINAL = "final", _("Готовий виріб")


class DtfWork(models.Model):
    title = models.CharField(max_length=200, blank=True)
    category = models.CharField(max_length=20, choices=WorkCategory.choices, default=WorkCategory.FINAL)
    image = models.ImageField(upload_to="dtf/works/")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "-created_at"]
        verbose_name = "DTF Work"
        verbose_name_plural = "DTF Works"

    def __str__(self):
        return self.title or f"DTF Work #{self.pk}"


class SampleSize(models.TextChoices):
    A4 = "a4", _("A4 sample")
    A3 = "a3", _("A3 sample")
    STRIP_60x10 = "strip_60x10", _("Calibration strip 60x10 cm")


class SampleStatus(models.TextChoices):
    NEW = "new", _("Нова")
    CONTACTED = "contacted", _("В роботі")
    SHIPPED = "shipped", _("Відправлено")
    CLOSED = "closed", _("Закрито")


class DtfSampleLead(models.Model):
    sample_number = models.CharField(max_length=24, unique=True, blank=True)
    status = models.CharField(max_length=20, choices=SampleStatus.choices, default=SampleStatus.NEW)
    sample_size = models.CharField(max_length=20, choices=SampleSize.choices, default=SampleSize.A4)
    is_brand_volume = models.BooleanField(default=False)

    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=32, db_index=True)
    contact_channel = models.CharField(max_length=20, choices=ContactChannel.choices, default=ContactChannel.TELEGRAM)
    contact_handle = models.CharField(max_length=200, blank=True)

    city = models.CharField(max_length=120)
    np_branch = models.CharField(max_length=240)
    niche = models.CharField(max_length=200, blank=True)
    monthly_volume = models.CharField(max_length=120, blank=True)
    comment = models.TextField(blank=True)

    consent = models.BooleanField(default=False)
    source = models.CharField(max_length=50, blank=True, default="sample_page")
    manager_note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "DTF Sample Lead"
        verbose_name_plural = "DTF Sample Leads"

    def __str__(self):
        return f"{self.sample_number or 'DTF Sample'} — {self.name}"

    def save(self, *args, **kwargs):
        attempts = 0
        while True:
            if not self.sample_number:
                self.sample_number = self.generate_sample_number()
            try:
                with transaction.atomic():
                    super().save(*args, **kwargs)
                break
            except IntegrityError:
                attempts += 1
                if attempts >= 5:
                    raise
                self.sample_number = None

    @staticmethod
    def generate_sample_number():
        today = timezone.localdate()
        date_str = today.strftime("%d%m%Y")
        prefix = f"DTF{date_str}S"
        last = DtfSampleLead.objects.filter(sample_number__startswith=prefix).aggregate(Max("sample_number"))
        max_number = last.get("sample_number__max")
        if max_number:
            try:
                suffix = max_number.replace(prefix, "")
                counter = int(suffix) + 1
            except ValueError:
                counter = 1
        else:
            counter = 1
        return f"{prefix}{counter:02d}"


class BuilderStatus(models.TextChoices):
    DRAFT = "draft", _("Чернетка")
    SUBMITTED = "submitted", _("Надіслано")


class BuilderProductType(models.TextChoices):
    TSHIRT = "tshirt", _("T-shirt")
    HOODIE = "hoodie", _("Hoodie")
    TOTE = "tote", _("Tote")
    MY_ITEM = "my_item", _("My item")


class BuilderPlacement(models.TextChoices):
    FRONT = "front", _("Front")
    BACK = "back", _("Back")
    LEFT_CHEST = "left_chest", _("Left chest")
    SLEEVE = "sleeve", _("Sleeve")


class DtfBuilderSession(models.Model):
    session_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="dtf_builder_sessions")
    status = models.CharField(max_length=20, choices=BuilderStatus.choices, default=BuilderStatus.DRAFT)

    product_type = models.CharField(max_length=20, choices=BuilderProductType.choices, default=BuilderProductType.TSHIRT)
    product_color = models.CharField(max_length=40, default="#151515")
    quantity = models.PositiveIntegerField(default=1)
    size_breakdown_json = models.JSONField(default=dict, blank=True)
    placement = models.CharField(max_length=20, choices=BuilderPlacement.choices, default=BuilderPlacement.FRONT)
    placements_json = models.JSONField(default=list, blank=True)

    design_file = models.FileField(upload_to="dtf/builder/uploads/", blank=True)
    preflight_json = models.JSONField(default=dict, blank=True)
    preview_image = models.ImageField(upload_to="dtf/builder/previews/", blank=True)
    risk_ack = models.BooleanField(default=False)

    delivery_city = models.CharField(max_length=120, blank=True)
    delivery_np_branch = models.CharField(max_length=240, blank=True)
    comment = models.TextField(blank=True)

    submitted_lead = models.ForeignKey(DtfLead, null=True, blank=True, on_delete=models.SET_NULL, related_name="builder_sessions")
    source = models.CharField(max_length=50, blank=True, default="constructor")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "DTF Builder Session"
        verbose_name_plural = "DTF Builder Sessions"

    def __str__(self):
        return f"{self.session_id} ({self.get_product_type_display()})"
