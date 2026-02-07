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
