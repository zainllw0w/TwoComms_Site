"""Warehouse / Storage models.

Окрема ієрархія складу, не пов'язана з ProductColorVariant.stock на вітрині.
Внутрішня класифікація (крій / тип) ніколи не показується клієнту —
адмін обирає її вручну під час списання за замовленням.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import F, Sum
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify as _django_slugify

try:
    # dtf.utils.build_slug transliterates Cyrillic → Latin and applies slugify.
    from dtf.utils import build_slug as _build_slug
except Exception:  # pragma: no cover - fallback when dtf app unavailable
    _build_slug = None


def _slugify(value: str, fallback: str = "item") -> str:
    """Slugify with Cyrillic transliteration when ``dtf.utils.build_slug`` is available."""
    if _build_slug:
        try:
            result = _build_slug(value, fallback=fallback)
            if result:
                return result
        except Exception:
            pass
    return _django_slugify(value) or fallback


# ---------------------------------------------------------------------------
# Categories / subcategories
# ---------------------------------------------------------------------------


class StorageCategory(models.Model):
    """Тип одягу на складі (Футболки, Худі, Лонгсліви...)."""

    name = models.CharField(max_length=120, verbose_name="Назва")
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    icon = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Назва lucide-іконки або emoji",
    )
    order = models.PositiveIntegerField(default=0)
    linked_storefront_category = models.ForeignKey(
        "storefront.Category",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="storage_categories",
        verbose_name="Пов'язана категорія сайту",
        help_text=(
            "Використовується для співпадіння OrderItem → склад. "
            "Можна залишити порожнім — тоді категорія буде тільки для внутрішнього обліку (warehouse-only)."
        ),
    )
    sizes = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Розміри",
        help_text=(
            "Список розмірів, доступних для цієї категорії (наприклад [\"XS\",\"S\",\"M\",\"L\",\"XL\"]). "
            "Якщо порожній — береться з товарів сайту або стандартний набір."
        ),
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Складська категорія"
        verbose_name_plural = "Складські категорії"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = _slugify(self.name, fallback="category")
            slug = base
            i = 2
            while StorageCategory.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("warehouse:category_detail", kwargs={"slug": self.slug})

    @property
    def total_quantity(self) -> int:
        return (
            StockItem.objects.filter(subcategory__category=self).aggregate(
                total=Sum("quantity")
            )["total"]
            or 0
        )

    @property
    def total_frozen_value(self) -> Decimal:
        agg = StockItem.objects.filter(subcategory__category=self).aggregate(
            v=Sum(F("quantity") * F("cost_price"))
        )
        return Decimal(agg["v"] or 0)

    DEFAULT_SIZES = ("XS", "S", "M", "L", "XL", "XXL")

    def get_sizes(self) -> list[str]:
        """Повертає впорядкований список розмірів цієї категорії.

        1. Якщо ``self.sizes`` непорожній — використовуємо його.
        2. Інакше — стандартний набір ``DEFAULT_SIZES``.

        Розміри можна задати у налаштуваннях категорії — підтримуються довільні
        значення (наприклад ``"42-44"``, ``"One Size"``).
        """
        if isinstance(self.sizes, list) and self.sizes:
            return [str(s).strip() for s in self.sizes if str(s).strip()]
        return list(self.DEFAULT_SIZES)


class StorageSubcategory(models.Model):
    """Крій / тип всередині категорії: оверсайз ERC, базова без резинки, жіноча, бамбукова..."""

    category = models.ForeignKey(
        StorageCategory,
        on_delete=models.CASCADE,
        related_name="subcategories",
        verbose_name="Категорія",
    )
    name = models.CharField(max_length=120, verbose_name="Назва (крій / тип)")
    slug = models.SlugField(max_length=140, blank=True)
    description = models.CharField(max_length=255, blank=True, default="")
    is_default = models.BooleanField(default=False, help_text="Підкатегорія за замовчуванням під час списання")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    colors = models.ManyToManyField(
        "productcolors.Color",
        blank=True,
        related_name="storage_subcategories",
        verbose_name="Доступні кольори",
        help_text=(
            "Список кольорів, у яких випускається цей крій. "
            "Якщо порожній — у партії можна обрати будь-який колір."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category__order", "order", "name"]
        unique_together = (("category", "slug"),)
        verbose_name = "Підкатегорія (крій)"
        verbose_name_plural = "Підкатегорії (крої)"

    def __str__(self) -> str:
        return f"{self.category.name} / {self.name}"

    def get_allowed_colors(self):
        """Повертає QuerySet кольорів, з якими можна додавати в цей крій.

        Якщо у підкатегорії явно задані кольори — повертає їх.
        Якщо порожньо — повертає всі кольори (free choice).
        """
        from productcolors.models import Color
        m2m = self.colors.all()
        if m2m.exists():
            return m2m.order_by("name", "primary_hex")
        return Color.objects.all().order_by("name", "primary_hex")

    def save(self, *args, **kwargs):
        if not self.slug:
            base = _slugify(self.name, fallback="sub")
            slug = base
            i = 2
            while (
                StorageSubcategory.objects.filter(category=self.category, slug=slug)
                .exclude(pk=self.pk)
                .exists()
            ):
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        if self.is_default and self.category_id:
            StorageSubcategory.objects.filter(
                category_id=self.category_id, is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Stock items (clothing)
# ---------------------------------------------------------------------------


class StockItem(models.Model):
    """Конкретна складська позиція: (підкатегорія + колір + розмір) → кількість."""

    subcategory = models.ForeignKey(
        StorageSubcategory,
        on_delete=models.PROTECT,
        related_name="stock_items",
        verbose_name="Підкатегорія",
    )
    color = models.ForeignKey(
        "productcolors.Color",
        on_delete=models.PROTECT,
        related_name="warehouse_stock_items",
        null=True,
        blank=True,
        verbose_name="Колір",
    )
    size = models.CharField(max_length=16, verbose_name="Розмір")
    quantity = models.PositiveIntegerField(default=0, verbose_name="Залишок")
    cost_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00"), verbose_name="Собівартість (грн)"
    )
    notes = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["subcategory__category__order", "subcategory__order", "size"]
        unique_together = (("subcategory", "color", "size"),)
        indexes = [
            models.Index(fields=["subcategory", "size"], name="idx_stock_subcat_size"),
            models.Index(fields=["color", "size"], name="idx_stock_color_size"),
        ]
        verbose_name = "Складська позиція (одяг)"
        verbose_name_plural = "Складські позиції (одяг)"

    def __str__(self) -> str:
        color_name = self.color.name if self.color and self.color.name else "—"
        return f"{self.subcategory} · {color_name} · {self.size} ({self.quantity} шт)"

    @property
    def category(self) -> StorageCategory:
        return self.subcategory.category

    @property
    def frozen_value(self) -> Decimal:
        return Decimal(self.quantity) * Decimal(self.cost_price)

    @property
    def color_display(self) -> str:
        if not self.color:
            return "—"
        name = (self.color.name or "").strip()
        if name:
            return name
        return self.color.primary_hex


# ---------------------------------------------------------------------------
# Prints
# ---------------------------------------------------------------------------


class PrintCategory(models.Model):
    """Категорія для групування принтів (Військові, Гумор, Природа, Україна тощо).

    Чисто внутрішня класифікація для зручного сортування і пошуку в списку принтів.
    """

    name = models.CharField(max_length=120, verbose_name="Назва")
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.CharField(max_length=255, blank=True, default="")
    icon = models.CharField(
        max_length=8,
        blank=True,
        default="",
        verbose_name="Іконка (emoji)",
        help_text="Опціонально: одна emoji для індикатора (🎯 ⚔️ 🌿)",
    )
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Категорія принтів"
        verbose_name_plural = "Категорії принтів"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = _slugify(self.name, fallback="print-cat")
            slug = base
            i = 2
            while PrintCategory.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def prints_count(self) -> int:
        return self.prints.filter(is_active=True).count()


class Print(models.Model):
    """Принт як окрема сутність (фото + назва, можливо різні кольори друку)."""

    name = models.CharField(max_length=160, verbose_name="Назва")
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    category = models.ForeignKey(
        PrintCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prints",
        verbose_name="Категорія",
    )
    main_image = models.ImageField(
        upload_to="warehouse/prints/", blank=True, null=True, verbose_name="Основне фото"
    )
    description = models.TextField(blank=True, default="")
    default_products = models.ManyToManyField(
        "storefront.Product",
        related_name="warehouse_default_prints",
        blank=True,
        verbose_name="Зв'язані товари сайту",
        help_text="Якщо у замовленні присутній один із цих товарів, цей принт пропонується за замовчуванням під час списання.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category__order", "category__name", "name"]
        verbose_name = "Принт"
        verbose_name_plural = "Принти"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = _slugify(self.name, fallback="print")
            slug = base
            i = 2
            while Print.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("warehouse:print_detail", kwargs={"slug": self.slug})

    @property
    def total_quantity(self) -> int:
        return self.color_variants.aggregate(total=Sum("quantity"))["total"] or 0

    @property
    def total_frozen_value(self) -> Decimal:
        agg = self.color_variants.aggregate(v=Sum(F("quantity") * F("cost_price")))
        return Decimal(agg["v"] or 0)


class PrintColorVariant(models.Model):
    """Кольоровий варіант принта (Зелений, Білий, Золотий тощо)."""

    print = models.ForeignKey(
        Print, on_delete=models.CASCADE, related_name="color_variants", verbose_name="Принт"
    )
    color_name = models.CharField(max_length=80, verbose_name="Назва кольору")
    color_hex = models.CharField(
        max_length=7,
        blank=True,
        default="",
        help_text="#RRGGBB (для індикатора)",
    )
    quantity = models.PositiveIntegerField(default=0, verbose_name="Кількість")
    cost_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00"), verbose_name="Собівартість (грн)"
    )
    image = models.ImageField(
        upload_to="warehouse/prints/variants/", blank=True, null=True
    )
    order = models.PositiveIntegerField(default=0)
    is_default = models.BooleanField(default=False, help_text="Варіант, що пропонується за замовчуванням")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "id"]
        unique_together = (("print", "color_name"),)
        verbose_name = "Варіант кольору принта"
        verbose_name_plural = "Варіанти кольорів принтів"

    def __str__(self) -> str:
        return f"{self.print.name} · {self.color_name} ({self.quantity} шт)"

    def save(self, *args, **kwargs):
        if self.is_default and self.print_id:
            PrintColorVariant.objects.filter(
                print_id=self.print_id, is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    @property
    def frozen_value(self) -> Decimal:
        return Decimal(self.quantity) * Decimal(self.cost_price)


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


class MovementReason(models.TextChoices):
    MANUAL_ADD = "manual_add", "Ручне додавання"
    MANUAL_REMOVE = "manual_remove", "Ручне списання"
    BULK_ADD = "bulk_add", "Партія (масове додавання)"
    ORDER_WRITE_OFF = "order_write_off", "Списання за замовленням"
    RECOUNT = "recount", "Інвентаризація"
    PRINT_ADD = "print_add", "Додавання принта"
    PRINT_REMOVE = "print_remove", "Списання принта"
    ADJUSTMENT = "adjustment", "Коригування"


class StockMovement(models.Model):
    """Аудит-лог усіх змін кількостей на складі.

    Поліморфний — може посилатись на StockItem або PrintColorVariant
    через ContentType framework.
    """

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name="warehouse_movements",
    )
    object_id = models.PositiveIntegerField()
    target = GenericForeignKey("content_type", "object_id")

    delta = models.IntegerField(verbose_name="Зміна кількості (+/-)")
    quantity_after = models.IntegerField(default=0, verbose_name="Залишок після операції")
    reason = models.CharField(
        max_length=32, choices=MovementReason.choices, default=MovementReason.MANUAL_ADD
    )
    comment = models.CharField(max_length=255, blank=True, default="")

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="warehouse_movements",
    )
    write_off_request = models.ForeignKey(
        "warehouse.WriteOffRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movements",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="warehouse_movements_created",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    verified = models.BooleanField(default=False, db_index=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="warehouse_movements_verified",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["content_type", "object_id"], name="idx_mov_target"),
            models.Index(fields=["created_at"], name="idx_mov_created"),
            models.Index(fields=["reason"], name="idx_mov_reason"),
            models.Index(fields=["verified"], name="idx_mov_verified"),
        ]
        verbose_name = "Рух складу"
        verbose_name_plural = "Рухи складу"

    def __str__(self) -> str:
        sign = "+" if self.delta > 0 else ""
        return f"{sign}{self.delta} · {self.get_reason_display()} · {self.created_at:%Y-%m-%d %H:%M}"

    @classmethod
    def for_target(cls, target):
        ct = ContentType.objects.get_for_model(type(target))
        return cls.objects.filter(content_type=ct, object_id=target.pk)

    def mark_verified(self, user):
        if self.verified:
            return
        self.verified = True
        self.verified_at = timezone.now()
        self.verified_by = user
        self.save(update_fields=["verified", "verified_at", "verified_by"])


# ---------------------------------------------------------------------------
# Write-off request (token from Telegram bot)
# ---------------------------------------------------------------------------


class WriteOffRequest(models.Model):
    """Сесія списання за замовленням.

    Створюється при першому переході з кнопки «Списати зі складу» в Telegram.
    Зберігається до завершення (або скасування).
    """

    STATUS_PENDING = "pending"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = (
        (STATUS_PENDING, "В очікуванні"),
        (STATUS_COMPLETED, "Виконано"),
        (STATUS_CANCELLED, "Скасовано"),
    )

    token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="warehouse_write_off_requests",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)

    opened_at = models.DateTimeField(null=True, blank=True)
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="warehouse_writeoffs_opened",
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="warehouse_writeoffs_completed",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Запит на списання"
        verbose_name_plural = "Запити на списання"

    def __str__(self) -> str:
        return f"WriteOff #{self.order.order_number} ({self.get_status_display()})"

    def get_absolute_url(self) -> str:
        return reverse("warehouse:write_off", kwargs={"token": self.token})


# ---------------------------------------------------------------------------
# Settings (singleton)
# ---------------------------------------------------------------------------


class WarehouseSettings(models.Model):
    """Налаштування модуля (singleton)."""

    evening_reminder_enabled = models.BooleanField(default=True)
    evening_reminder_hour = models.PositiveSmallIntegerField(default=22)
    evening_reminder_minute = models.PositiveSmallIntegerField(default=0)
    evening_reminder_chat_ids = models.CharField(
        max_length=512,
        blank=True,
        default="",
        help_text="Список chat_id Telegram, розділених комами",
    )

    last_reminder_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Налаштування складу"
        verbose_name_plural = "Налаштування складу"

    def __str__(self) -> str:
        return "Налаштування складу"

    @classmethod
    def load(cls) -> "WarehouseSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @property
    def reminder_chat_ids_list(self) -> list[str]:
        if not self.evening_reminder_chat_ids:
            return []
        return [c.strip() for c in self.evening_reminder_chat_ids.split(",") if c.strip()]
