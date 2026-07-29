"""Моделі апгрейду Instagram-бота TwoComms (Phase 0+).

Винесені в окремий модуль, щоб не роздувати і без того велику models.py.
Імпортуються в кінці management/models.py (`from .ig_bot_models import *`),
тож app_label='management' визначається автоматично, а міграції лягають у
management/migrations. Перехресні FK задаються рядком ('management.IgClient',
'orders.Order') — без жорстких import, щоб уникнути циклічних залежностей.
"""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

__all__ = [
    "InstagramBotRawEvent",
    "IgClient",
    "IgDeal",
    "IgPaymentEvent",
    "IgPaymentProjection",
    "IgDealItem",
    "BotInstruction",
    "BotQuickLink",
    "BotAdCampaign",
    "IgClientStageEvent",
    "IgFollowUpTask",
    "IgPollCursor",
    "IgConversationSignal",
    "IgConversationAnalysisSnapshot",
    "IgConversationAnalysisJob",
    "IgMetaEventLog",
    "BotDataDeletionRequest",
    "IgBotNotification",
    "IgBotNotificationAudit",
    "IgPaymentConfirmationReview",
    "IgPaymentReviewDecision",
    "IgOrderAttribution",
    "IgOrderLinkEvent",
    "IgCommercialEpisode",
    "IgCommercialEpisodeEvent",
    "IgPostSaleCase",
]


class InstagramBotRawEvent(models.Model):
    """Сире збереження вхідних вебхук-подій IG для діагностики форматів.

    Дозволяє побачити реальний payload пересланого поста / story_mention /
    відповіді на сторис / рекламного referral / echo менеджера на цьому
    акаунті, а не покладатись на здогадки про формат Meta.
    """

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    sender_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    attachment_types = models.CharField(max_length=255, blank=True, default="")
    has_referral = models.BooleanField(default=False)
    has_echo = models.BooleanField(default=False)
    note = models.CharField(max_length=255, blank=True, default="")
    payload = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "IG raw webhook event"
        verbose_name_plural = "IG raw webhook events"
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["-created_at"], name="ig_rawevent_created"),
        ]

    def __str__(self) -> str:  # pragma: no cover - тривіально
        return f"RawEvent#{self.pk} {self.sender_id} [{self.attachment_types}]"


class BotDataDeletionRequest(models.Model):
    """Public/Meta deletion request receipt for DIRECT_BOT data."""

    class Source(models.TextChoices):
        MANUAL_FORM = "manual_form", "Manual form"
        META_CALLBACK = "meta_callback", "Meta callback"

    class Status(models.TextChoices):
        COMPLETED = "completed", "Completed"
        NO_MATCH = "no_match", "No matching records"
        RECEIVED = "received", "Received"

    confirmation_code = models.CharField(max_length=32, unique=True, db_index=True)
    source = models.CharField(max_length=24, choices=Source.choices)
    identifier = models.CharField(max_length=255, blank=True, default="")
    normalized_identifier = models.CharField(max_length=255, blank=True, default="", db_index=True)
    meta_user_id = models.CharField(max_length=128, blank=True, default="", db_index=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.RECEIVED)
    deleted_clients_count = models.PositiveIntegerField(default=0)
    deleted_messages_count = models.PositiveIntegerField(default=0)
    deleted_raw_events_count = models.PositiveIntegerField(default=0)
    deleted_logs_count = models.PositiveIntegerField(default=0)
    detail = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "DIRECT_BOT data deletion request"
        verbose_name_plural = "DIRECT_BOT data deletion requests"
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="bot_del_status_dt"),
            models.Index(fields=["source", "-created_at"], name="bot_del_source_dt"),
        ]

    def mark_completed(self, *, status: str | None = None) -> None:
        if status:
            self.status = status
        self.completed_at = timezone.now()
        self.save(update_fields=[
            "status",
            "deleted_clients_count",
            "deleted_messages_count",
            "deleted_raw_events_count",
            "deleted_logs_count",
            "detail",
            "completed_at",
        ])


class IgBotNotification(models.Model):
    """Durable, idempotent Telegram notification attempt for the IG bot."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENDING = "sending", "Sending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        UNKNOWN = "unknown", "Delivery unknown"
        DEAD_LETTER = "dead_letter", "Manual review required"
        RESOLVED = "resolved", "Resolved by operator"

    client = models.ForeignKey(
        "management.IgClient",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bot_notifications",
        # Kept constraint-free for compatibility with installations that have
        # not yet completed the runtime-table InnoDB migration.
        db_constraint=False,
    )
    event_type = models.CharField(max_length=64, default="generic", db_index=True)
    dedupe_key = models.CharField(max_length=255, unique=True)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    telegram_message_id = models.CharField(max_length=64, blank=True, default="")
    last_error = models.CharField(max_length=500, blank=True, default="")
    failure_kind = models.CharField(max_length=32, blank=True, default="")
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="ig_notif_status_dt"),
            models.Index(fields=["client", "event_type", "-created_at"], name="ig_notif_client_event"),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial representation
        return f"IgBotNotification#{self.pk} {self.event_type}/{self.status}"


class IgBotNotificationAudit(models.Model):
    """Immutable operator action history for notification recovery."""

    notification = models.ForeignKey(
        "management.IgBotNotification",
        on_delete=models.CASCADE,
        related_name="audit_events",
        db_constraint=False,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ig_notification_audits",
        db_constraint=False,
    )
    action = models.CharField(max_length=32)
    from_status = models.CharField(max_length=16)
    to_status = models.CharField(max_length=16)
    note = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["notification", "-created_at"], name="ig_notif_audit_dt"),
        ]


class IgClient(models.Model):
    """Картка співрозмовника в Instagram Direct (B2C).

    Окрема сутність від B2B `Client` (холодний обзвон магазинів). Тут — кінцевий
    покупець, що пише в Direct: профіль, стадія воронки, атрибуція реклами,
    стисла пам'ять діалогу, лічильники, антиспам, стоп/перехоплення менеджером.
    """

    class Stage(models.TextChoices):
        NEW = "new", _("Написав")
        QUALIFYING = "qualifying", _("З'ясовуємо потребу")
        PRODUCT_MATCHED = "product_matched", _("Товар і ціна визначені")
        CHECKOUT = "checkout", _("Обирає оплату")
        PAYMENT_PENDING = "payment_pending", _("Очікуємо оплату")
        PAID = "paid", _("Оплачено")
        ORDER_CREATED = "order_created", _("Замовлення створено")
        DONE = "done", _("Завершено")
        LEAD_TO_MANAGER = "lead_manager", _("Передано менеджеру")
        SPAM = "spam", _("Спам / заблоковано")
        COLD = "cold", _("Не відповідає / охолов")

    class Intent(models.TextChoices):
        UNKNOWN = "unknown", _("Невідомо")
        PRODUCT = "product", _("Готовий товар")
        CUSTOM_PRINT = "custom_print", _("Кастомний принт")
        PRICE = "price", _("Ціна")
        SIZE = "size", _("Розмір")
        PAYMENT = "payment", _("Оплата")
        DELIVERY = "delivery", _("Доставка")
        ORDER_STATUS = "order_status", _("Статус замовлення")
        SUPPORT = "support", _("Підтримка")
        SPAM = "spam", _("Спам")

    class Objection(models.TextChoices):
        NONE = "none", _("Немає")
        PRICE = "price", _("Дорого")
        PREPAYMENT = "prepayment", _("Передоплата")
        SIZE = "size", _("Розмір")
        THINKING = "thinking", _("Подумаю")
        NO_REPLY = "no_reply", _("Не відповідає")
        NO_BUY = "no_buy", _("Не купує")
        TRUST = "trust", _("Довіра")
        DELIVERY = "delivery", _("Доставка")
        OTHER = "other", _("Інше")

    class DeliveryStatus(models.TextChoices):
        ADVANCED_ACCESS = "advanced_access", _("Meta не дозволяє відповідь: потрібен Advanced Access")
        WINDOW_CLOSED = "window_closed", _("24-годинне вікно Meta закрито")
        MESSAGE_REQUEST_CHECK = "message_request_check", _("Перевірте «Запити» в Instagram")
        SEND_BLOCKED = "send_blocked", _("Meta тимчасово або постійно блокує відповідь")

    # Головна воронка (для прогрес-бару/кружечків у картці).
    FUNNEL_ORDER = [
        Stage.NEW,
        Stage.QUALIFYING,
        Stage.PRODUCT_MATCHED,
        Stage.CHECKOUT,
        Stage.PAYMENT_PENDING,
        Stage.PAID,
        Stage.ORDER_CREATED,
        Stage.DONE,
    ]

    # Identity
    igsid = models.CharField(_("IG sender id"), max_length=64, unique=True, db_index=True)
    username = models.CharField(_("Username"), max_length=120, blank=True, default="")
    display_name = models.CharField(_("Ім'я"), max_length=255, blank=True, default="")
    profile_pic_url = models.CharField(_("Аватар URL"), max_length=600, blank=True, default="")
    # Локальна копія аватарки (media). IG CDN-URL протухають і мають hotlink-захист,
    # тож для CRM зберігаємо власну копію й віддаємо локальний URL.
    avatar_local = models.CharField(_("Аватар (локально)"), max_length=300, blank=True, default="")
    profile_fetched_at = models.DateTimeField(null=True, blank=True)
    profile_sync_attempted_at = models.DateTimeField(null=True, blank=True)
    profile_sync_failures = models.PositiveSmallIntegerField(default=0)
    profile_sync_next_at = models.DateTimeField(null=True, blank=True, db_index=True)
    profile_sync_error_kind = models.CharField(max_length=32, blank=True, default="")

    # Контакти (для ліда / замовлення)
    phone = models.CharField(_("Телефон"), max_length=50, blank=True, default="")
    phone_normalized = models.CharField(max_length=50, blank=True, default="", db_index=True)

    # Воронка
    stage = models.CharField(
        _("Стадія"), max_length=24, choices=Stage.choices, default=Stage.NEW, db_index=True
    )
    stage_updated_at = models.DateTimeField(null=True, blank=True)

    # Керування ботом / перехоплення менеджером
    bot_paused = models.BooleanField(_("Бот на паузі"), default=False, db_index=True)
    paused_reason = models.CharField(max_length=255, blank=True, default="")
    paused_at = models.DateTimeField(null=True, blank=True)
    manager_takeover = models.BooleanField(_("Веде менеджер"), default=False)
    # Monotonic permission epoch. Pause/takeover increments it so a worker
    # that generated before the transition cannot send afterwards.
    reply_permission_epoch = models.PositiveBigIntegerField(default=0)
    opted_out_at = models.DateTimeField(null=True, blank=True, db_index=True)
    opt_out_message_id = models.PositiveBigIntegerField(null=True, blank=True)
    opted_in_at = models.DateTimeField(null=True, blank=True)
    opted_in_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ig_manual_opt_ins",
        db_constraint=False,
    )

    # Закріплений товар діалогу (визначений за [PRODUCT:id] від моделі або
    # впевненим матчингом фото). Посилання на оплату формується саме на нього,
    # без повторного вгадування. Скидається після створення замовлення.
    current_product = models.ForeignKey(
        "storefront.Product",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("Закріплений товар"),
    )
    current_size = models.CharField(_("Поточний розмір"), max_length=16, blank=True, default="")
    current_color = models.CharField(_("Поточний колір"), max_length=64, blank=True, default="")
    current_qty = models.PositiveIntegerField(_("Поточна кількість"), default=1)
    current_product_confidence = models.DecimalField(
        _("Впевненість у товарі"), max_digits=4, decimal_places=2, default=0
    )
    current_commercial_episode = models.ForeignKey(
        "management.IgCommercialEpisode",
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="current_for_clients",
        db_constraint=False,
    )

    # Sales brain / CRM state
    language = models.CharField(max_length=8, blank=True, default="", db_index=True)
    intent = models.CharField(
        max_length=32, choices=Intent.choices, default=Intent.UNKNOWN, db_index=True
    )
    buying_readiness = models.PositiveSmallIntegerField(default=0, db_index=True)
    primary_objection = models.CharField(
        max_length=32, choices=Objection.choices, default=Objection.NONE, db_index=True
    )
    lost_reason = models.CharField(max_length=64, blank=True, default="", db_index=True)
    hidden_at = models.DateTimeField(null=True, blank=True, db_index=True)
    hidden_reason = models.CharField(max_length=255, blank=True, default="")
    # Короткоживуча lease одного worker-а. Вона не є станом воронки: потрібна
    # лише щоб hide не підтверджувався, поки триває відповідь цьому клієнту.
    automation_lease_token = models.CharField(max_length=40, blank=True, default="")
    automation_lease_until = models.DateTimeField(null=True, blank=True)
    discount_offered_percent = models.PositiveSmallIntegerField(default=0)
    next_followup_at = models.DateTimeField(null=True, blank=True, db_index=True)
    followup_level = models.PositiveSmallIntegerField(default=0)
    last_manager_message_at = models.DateTimeField(null=True, blank=True)
    sales_context = models.JSONField(default=dict, blank=True)

    # Остання підтверджена технічна перешкода доставки. Це не замінює стадію
    # воронки та не означає автоматичну передачу ліда менеджеру.
    delivery_status = models.CharField(
        max_length=32, choices=DeliveryStatus.choices, blank=True, default="", db_index=True
    )
    delivery_error = models.CharField(max_length=500, blank=True, default="")
    delivery_http_code = models.PositiveSmallIntegerField(null=True, blank=True)
    delivery_graph_code = models.PositiveIntegerField(null=True, blank=True)
    delivery_graph_subcode = models.PositiveIntegerField(null=True, blank=True)
    delivery_failed_at = models.DateTimeField(null=True, blank=True)

    # Атрибуція реклами (Click-to-IG-Direct)
    ad_ref = models.CharField(max_length=255, blank=True, default="")
    ad_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    ad_source = models.CharField(max_length=64, blank=True, default="")
    ad_title = models.CharField(max_length=255, blank=True, default="")
    ad_creative_url = models.CharField(max_length=600, blank=True, default="")
    referral_payload = models.JSONField(default=dict, blank=True)

    # Пам'ять діалогу (rolling summary — Task 10)
    memory_summary = models.TextField(blank=True, default="")
    memory_updated_at = models.DateTimeField(null=True, blank=True)

    # Лічильники / конверсія
    purchases_count = models.PositiveIntegerField(default=0)
    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    conversion_flags = models.JSONField(default=dict, blank=True)

    # Антиспам
    spam_strikes = models.PositiveSmallIntegerField(default=0)
    is_blocked = models.BooleanField(default=False)

    # Тайминги
    first_contact_at = models.DateTimeField(null=True, blank=True)
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_bot_reply_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("IG клієнт")
        verbose_name_plural = _("IG клієнти")
        ordering = ["-last_message_at", "-id"]
        indexes = [
            models.Index(fields=["stage", "-last_message_at"], name="ig_client_stage_dt"),
            models.Index(fields=["-last_message_at"], name="ig_client_lastmsg"),
            models.Index(fields=["intent", "stage"], name="ig_client_intent_stage"),
            models.Index(fields=["hidden_at", "-last_message_at"], name="ig_client_hidden_dt"),
            models.Index(fields=["next_followup_at"], name="ig_client_next_fu"),
        ]

    def save(self, *args, **kwargs):
        # Нормалізація телефону (lazy import, щоб уникнути циклічного імпорту).
        if self.phone:
            try:
                from management.models import normalize_phone

                self.phone_normalized = normalize_phone(self.phone)
            except Exception:
                pass
        super().save(*args, **kwargs)

    def __str__(self) -> str:  # pragma: no cover - тривіально
        label = self.username or self.display_name or self.igsid
        return f"IgClient({label}, {self.stage})"

    @classmethod
    def get_or_create_for_sender(cls, igsid: str, defaults: dict | None = None) -> "IgClient":
        obj, _created = cls.objects.get_or_create(igsid=igsid, defaults=defaults or {})
        return obj

    def set_stage(self, new_stage: str, reason: str = "") -> None:
        """Оновлює стадію + час і фіксує перехід у таймлайні (IgClientStageEvent)."""
        from django.utils import timezone

        old = self.stage
        self.stage = new_stage
        self.stage_updated_at = timezone.now()
        self.save(update_fields=["stage", "stage_updated_at", "updated_at"])
        try:
            from management.models import IgClientStageEvent

            IgClientStageEvent.objects.create(
                client=self, from_stage=old or "", to_stage=new_stage, reason=(reason or "")[:255]
            )
        except Exception:
            pass

    def touch_inbound(self) -> None:
        """Фіксує вхідне повідомлення: first_contact_at (раз) і last_message_at."""
        from django.utils import timezone

        now = timezone.now()
        fields = ["last_message_at", "updated_at"]
        if not self.first_contact_at:
            self.first_contact_at = now
            fields.append("first_contact_at")
        self.last_message_at = now
        self.save(update_fields=fields)

    def funnel_progress(self) -> list[dict]:
        """Прогрес по основних стадіях воронки (для кружечків у картці)."""
        order = list(self.FUNNEL_ORDER)
        try:
            cur = order.index(self.stage)
        except ValueError:
            cur = -1
        result = []
        for i, st in enumerate(order):
            result.append({
                "stage": st.value,
                "label": str(st.label),
                "done": cur >= 0 and i <= cur,
                "current": st.value == self.stage,
            })
        return result


class IgDeal(models.Model):
    """«Кошик» діалогу: вибрані позиції, сума, оплата, invoice, дані НП.

    Замовлення (orders.Order) створюється ТІЛЬКИ після підтвердженої оплати
    (рішення Q2), тож тут зберігаємо invoice_id/url і чекаємо вебхук/поллінг.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", _("Чернетка")
        QUOTED = "quoted", _("Названо ціну")
        AWAITING_PAYMENT = "awaiting_payment", _("Очікує оплату")
        PAID = "paid", _("Оплачено")
        ORDER_CREATED = "order_created", _("Замовлення створено")
        CANCELLED = "cancelled", _("Скасовано")

    class PayType(models.TextChoices):
        ONLINE_FULL = "online_full", _("Повна онлайн-оплата")
        PREPAYMENT = "prepayment", _("Передоплата за погодженою сумою")
        PREPAY_200 = "prepay_200", _("Передоплата 200 грн (legacy)")

    class PaymentTruth(models.TextChoices):
        UNVERIFIED = "unverified", _("Не підтверджено")
        PENDING = "pending", _("Перевіряється")
        CONFIRMED = "confirmed", _("Оплату підтверджено")
        PARTIALLY_REFUNDED = "partially_refunded", _("Частково повернено")
        REFUNDED = "refunded", _("Повністю повернено")
        REVERSED = "reversed", _("Платіж скасовано банком")
        FAILED = "failed", _("Оплата не пройшла")
        CANCELLED = "cancelled", _("Оплату скасовано")

    class DeliveryStatus(models.TextChoices):
        UNVERIFIED = "unverified", _("Доставку не підтверджено")
        VALIDATED = "validated", _("Доставку підтверджено довідником НП")
        NEEDS_REVIEW = "needs_review", _("Потрібна перевірка доставки")
        INVALID = "invalid", _("Дані доставки невалідні")

    client = models.ForeignKey(
        "management.IgClient", on_delete=models.CASCADE, related_name="deals"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    pay_type = models.CharField(
        max_length=20, choices=PayType.choices, default=PayType.ONLINE_FULL
    )
    requested_payment_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Сума конкретного платіжного запиту; не замінює повну вартість замовлення.",
    )
    requested_payment_evidence_ids = models.JSONField(default=list, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=8, default="UAH")

    # Monobank acquiring
    invoice_id = models.CharField(max_length=128, blank=True, default="", db_index=True)
    invoice_url = models.CharField(max_length=600, blank=True, default="")
    payment_status = models.CharField(max_length=20, default="unpaid")
    payment_payload = models.JSONField(default=dict, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    payment_truth = models.CharField(
        max_length=24,
        choices=PaymentTruth.choices,
        default=PaymentTruth.UNVERIFIED,
        db_index=True,
    )
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    refunded_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_truth_updated_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # Створене замовлення (після оплати)
    order = models.ForeignKey(
        "orders.Order",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ig_deals",
    )

    # Коли клієнта вже сповістили в Direct про відправку (ТТН) — щоб не дублювати.
    shipped_notified_at = models.DateTimeField(null=True, blank=True)
    order_truth_updated_at = models.DateTimeField(null=True, blank=True)

    # Display values are kept for conversation/context.  Fulfillment may only
    # use a validated signed-directory selection stored in the Ref fields.
    np_full_name = models.CharField(max_length=255, blank=True, default="")
    np_phone = models.CharField(max_length=50, blank=True, default="")
    np_city = models.CharField(max_length=160, blank=True, default="")
    np_office = models.CharField(max_length=255, blank=True, default="")
    np_settlement_ref = models.CharField(max_length=36, blank=True, default="")
    np_city_ref = models.CharField(max_length=36, blank=True, default="")
    np_warehouse_ref = models.CharField(max_length=36, blank=True, default="")
    np_warehouse_kind = models.CharField(max_length=16, blank=True, default="branch")
    delivery_status = models.CharField(
        max_length=16,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.UNVERIFIED,
        db_index=True,
    )
    delivery_source = models.CharField(max_length=32, blank=True, default="")
    delivery_error = models.CharField(max_length=500, blank=True, default="")
    delivery_verified_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("IG угода")
        verbose_name_plural = _("IG угоди")
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["client", "-id"], name="ig_deal_client_dt"),
            models.Index(fields=["status", "-id"], name="ig_deal_status_dt"),
        ]

    def __str__(self) -> str:  # pragma: no cover - тривіально
        return f"IgDeal#{self.pk} {self.client_id} {self.status} {self.amount}{self.currency}"

    def recalc_total(self) -> Decimal:
        """Перераховує суму як суму позицій і зберігає."""
        from django.db.models import Sum

        total = self.items.aggregate(s=Sum("line_total"))["s"] or Decimal("0")
        self.amount = total
        self.save(update_fields=["amount", "updated_at"])
        return total

    def payable_amount(self) -> Decimal:
        """Exact amount requested by this invoice, separate from order total."""
        requested = Decimal(self.requested_payment_amount or 0)
        if self.pay_type == self.PayType.PREPAYMENT:
            return requested
        if self.pay_type == self.PayType.PREPAY_200:
            # Preserve already-created legacy deals without using 200 for new flows.
            return requested or Decimal("200.00")
        return requested or self.amount


class AppendOnlyPaymentEventQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValueError("IgPaymentEvent is append-only")

    def delete(self):
        raise ValueError("IgPaymentEvent is append-only")


class IgPaymentEvent(models.Model):
    """Append-only, idempotent provider evidence for payment truth changes."""

    event_key = models.CharField(max_length=64, unique=True)
    deal = models.ForeignKey(
        "management.IgDeal",
        on_delete=models.DO_NOTHING,
        related_name="payment_events",
        db_constraint=False,
    )
    client = models.ForeignKey(
        "management.IgClient",
        on_delete=models.DO_NOTHING,
        related_name="payment_events",
        db_constraint=False,
    )
    provider = models.CharField(max_length=32, default="monobank")
    source = models.CharField(max_length=32, default="provider")
    invoice_id = models.CharField(max_length=128, blank=True, default="", db_index=True)
    provider_status = models.CharField(max_length=32, db_index=True)
    provider_modified_at = models.DateTimeField(null=True, blank=True, db_index=True)
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    final_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    refunded_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    amount_valid = models.BooleanField(null=True, blank=True)
    currency = models.CharField(max_length=8, default="UAH")
    evidence = models.JSONField(default=dict, blank=True)
    payload_digest = models.CharField(max_length=64)
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = models.Manager.from_queryset(AppendOnlyPaymentEventQuerySet)()

    class Meta:
        ordering = ["-provider_modified_at", "-id"]
        indexes = [
            models.Index(fields=["deal", "-received_at"], name="ig_payevt_deal_dt"),
            models.Index(fields=["provider_status", "-received_at"], name="ig_payevt_status_dt"),
        ]

    def __str__(self):
        return f"IgPaymentEvent#{self.pk} deal={self.deal_id} {self.provider_status}"

    def save(self, *args, **kwargs):
        if self.pk and not kwargs.get("force_insert"):
            raise ValueError("IgPaymentEvent is append-only")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("IgPaymentEvent is append-only")


class IgPaymentProjection(models.Model):
    """Transactional current truth derived from append-only payment events."""

    deal = models.OneToOneField(
        "management.IgDeal",
        on_delete=models.DO_NOTHING,
        related_name="payment_projection",
        db_constraint=False,
    )
    client = models.ForeignKey(
        "management.IgClient",
        on_delete=models.DO_NOTHING,
        related_name="payment_projections",
        db_constraint=False,
    )
    truth = models.CharField(
        max_length=24,
        choices=IgDeal.PaymentTruth.choices,
        default=IgDeal.PaymentTruth.UNVERIFIED,
        db_index=True,
    )
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    refunded_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_at = models.DateTimeField(null=True, blank=True, db_index=True)
    provider_modified_at = models.DateTimeField(null=True, blank=True, db_index=True)
    needs_reconciliation = models.BooleanField(default=False, db_index=True)
    reconciled_at = models.DateTimeField(null=True, blank=True)
    last_event = models.ForeignKey(
        "management.IgPaymentEvent",
        on_delete=models.PROTECT,
        related_name="projected_by",
        null=True,
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["client", "-updated_at"], name="ig_payproj_client_dt"),
            models.Index(fields=["truth", "-updated_at"], name="ig_payproj_truth_dt"),
        ]

    @property
    def net_paid_amount(self):
        return max(Decimal("0"), self.gross_amount - self.refunded_amount)


class IgPaymentConfirmationReview(models.Model):
    """Audited manager decision on customer-provided payment evidence.

    This is deliberately separate from :class:`IgPaymentProjection`: a chat
    statement or receipt is not provider truth.  A confirmed review authorizes
    the manager to prepare an order, while the provider projection remains
    unchanged and visible as unverified until a real provider event arrives.
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("Очікує підтвердження")
        CONFIRMED = "confirmed", _("Підтверджено менеджером")
        CANCELLED = "cancelled", _("Скасовано менеджером")
        SUPERSEDED = "superseded", _("Замінено канонічною перевіркою")

    client = models.ForeignKey(
        "management.IgClient",
        on_delete=models.CASCADE,
        related_name="payment_confirmation_reviews",
        db_constraint=False,
    )
    deal = models.ForeignKey(
        "management.IgDeal",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payment_confirmation_reviews",
        db_constraint=False,
    )
    order = models.ForeignKey(
        "orders.Order",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="instagram_payment_reviews",
        db_constraint=False,
    )
    dedupe_key = models.CharField(max_length=160, unique=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    evidence = models.JSONField(default=dict, blank=True)
    watermark_message_id = models.PositiveBigIntegerField(default=0)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="confirmed_ig_payment_reviews",
        db_constraint=False,
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cancelled_ig_payment_reviews",
        db_constraint=False,
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(max_length=500, blank=True, default="")
    superseded_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="superseded_reviews",
        db_constraint=False,
    )
    superseded_at = models.DateTimeField(null=True, blank=True)
    supersede_reason = models.CharField(max_length=120, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Перевірка оплати Instagram")
        verbose_name_plural = _("Перевірки оплати Instagram")
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="ig_payreview_status_dt"),
            models.Index(fields=["client", "-id"], name="ig_payreview_client_id"),
            models.Index(fields=["superseded_by", "-id"], name="ig_payreview_superseded"),
        ]

    @property
    def manual_payment_truth(self) -> str:
        decision = self.decisions.order_by("-id").first()
        return decision.decision if decision else ""


class _AppendOnlyDecisionQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValueError("IgPaymentReviewDecision is append-only")

    def delete(self):
        raise ValueError("IgPaymentReviewDecision is append-only")


class _AppendOnlyDecisionManager(models.Manager.from_queryset(_AppendOnlyDecisionQuerySet)):
    pass


class IgPaymentReviewDecision(models.Model):
    """Append-only, source-qualified operator decision for payment evidence.

    This record is intentionally separate from ``IgPaymentProjection``. A
    manager can verify an IBAN receipt without pretending that a provider ledger
    webhook was received, and a later provider event can still disagree.
    """

    class Decision(models.TextChoices):
        MANAGER_VERIFIED = "manager_verified", _("Підтверджено менеджером")
        MANAGER_REJECTED = "manager_rejected", _("Відхилено менеджером")
        EVIDENCE_ACCEPTED_PROVIDER_UNVERIFIED = (
            "evidence_accepted_provider_unverified",
            _("Доказ прийнято, provider не підтверджено"),
        )

    class ActorSource(models.TextChoices):
        MANAGEMENT_USER = "management_user", _("Користувач management")
        TELEGRAM_USER = "telegram_user", _("Користувач Telegram")
        LEGACY_IMPORT = "legacy_import", _("Імпортовано з legacy review")

    class VerificationScope(models.TextChoices):
        FULL_PAYMENT = "full_payment", _("Повна оплата")
        PREPAYMENT = "prepayment", _("Передоплата")
        PAYMENT_CLAIM = "payment_claim", _("Заявлений платіж")

    review = models.ForeignKey(
        "management.IgPaymentConfirmationReview",
        # The customer row may be erased for GDPR. The append-only decision
        # remains as an anonymized audit tombstone with orphan-safe IDs.
        on_delete=models.DO_NOTHING,
        related_name="decisions",
        db_constraint=False,
    )
    client = models.ForeignKey(
        "management.IgClient",
        on_delete=models.DO_NOTHING,
        related_name="payment_review_decisions",
        db_constraint=False,
    )
    decision = models.CharField(max_length=48, choices=Decision.choices, db_index=True)
    verification_source = models.CharField(max_length=32, default="manager", db_index=True)
    verification_scope = models.CharField(max_length=32, choices=VerificationScope.choices)
    confirmed_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Точна сума, фактично перевірена менеджером; не повна вартість замовлення за замовчуванням.",
    )
    currency = models.CharField(max_length=8, default="UAH")
    amount_source = models.CharField(max_length=48, blank=True, default="")
    amount_evidence_message_ids = models.JSONField(default=list, blank=True)
    reason_code = models.CharField(max_length=64, blank=True, default="")
    reason_text = models.CharField(max_length=500, blank=True, default="")
    evidence_watermark_message_id = models.PositiveBigIntegerField(default=0)
    review_status_before = models.CharField(max_length=16, blank=True, default="")
    review_status_after = models.CharField(max_length=16, blank=True, default="")
    stage_before = models.CharField(max_length=32, blank=True, default="")
    stage_after = models.CharField(max_length=32, blank=True, default="")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ig_payment_review_decisions",
        db_constraint=False,
    )
    actor_source = models.CharField(max_length=32, choices=ActorSource.choices)
    actor_external_id = models.CharField(max_length=128)
    actor_label = models.CharField(max_length=150, blank=True, default="")
    telegram_decision = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    objects = _AppendOnlyDecisionManager()

    class Meta:
        verbose_name = _("Рішення щодо перевірки оплати Instagram")
        verbose_name_plural = _("Рішення щодо перевірок оплати Instagram")
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["review", "-id"], name="ig_paydec_review_id"),
            models.Index(fields=["client", "-created_at"], name="ig_paydec_client_dt"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(actor_external_id=""),
                name="ig_paydec_actor_required",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(decision="manager_rejected")
                    | ~models.Q(reason_code="")
                ),
                name="ig_paydec_reject_reason",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk and not kwargs.get("force_insert"):
            raise ValueError("IgPaymentReviewDecision is append-only")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("IgPaymentReviewDecision is append-only")


class IgDealItem(models.Model):
    """Позиція угоди. product/color_variant необов'язкові (позиція може бути
    поза каталогом, як кастом). line_total рахується автоматично."""

    deal = models.ForeignKey(IgDeal, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "storefront.Product", null=True, blank=True, on_delete=models.SET_NULL
    )
    color_variant = models.ForeignKey(
        "productcolors.ProductColorVariant", null=True, blank=True, on_delete=models.SET_NULL
    )
    title = models.CharField(max_length=255)
    size = models.CharField(max_length=16, blank=True, default="")
    fit_option_code = models.CharField(max_length=50, blank=True, default="")
    fit_option_label = models.CharField(max_length=100, blank=True, default="")
    option_values = models.JSONField(default=dict, blank=True)
    option_labels = models.JSONField(default=dict, blank=True)
    qty = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    price_source = models.CharField(max_length=64, blank=True, default="")
    price_evidence_message_ids = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = _("Позиція IG угоди")
        verbose_name_plural = _("Позиції IG угод")
        ordering = ["id"]

    def save(self, *args, **kwargs):
        try:
            self.line_total = (self.unit_price or Decimal("0")) * int(self.qty or 0)
        except Exception:
            self.line_total = Decimal("0")
        super().save(*args, **kwargs)

    def __str__(self) -> str:  # pragma: no cover - тривіально
        return f"{self.title} ×{self.qty}"


class _AppendOnlyOrderAttributionQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValueError("IgOrderAttribution is append-only")

    def delete(self):
        raise ValueError("IgOrderAttribution is append-only")


class IgOrderAttribution(models.Model):
    """Immutable commercial attribution snapshot for one real order.

    Direct Instagram profile values are intentionally excluded.  The digest is
    only for deterministic audit correlation and cannot be used to recover the
    profile without the application secret.
    """

    CREATION_MODES = (
        ("provider_auto", _("Автоматично за provider payment")),
        ("manager_review", _("Створено після перевірки менеджером")),
        ("linked_existing", _("Прив'язано до існуючого замовлення")),
    )
    PAYMENT_SOURCES = (
        ("provider_projection", _("Provider projection")),
        ("provider_attempt", _("Provider payment attempt")),
        ("manager_verified", _("Перевірено менеджером")),
        ("unknown", _("Невідоме джерело")),
    )

    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name="instagram_attribution",
    )
    client = models.ForeignKey(
        "management.IgClient",
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name="order_attributions",
    )
    deal = models.ForeignKey(
        "management.IgDeal",
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="order_attributions",
        db_constraint=False,
    )
    payment_review = models.ForeignKey(
        "management.IgPaymentConfirmationReview",
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="order_attributions",
        db_constraint=False,
    )
    manager_decision = models.ForeignKey(
        "management.IgPaymentReviewDecision",
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="order_attributions",
        db_constraint=False,
    )
    creation_mode = models.CharField(max_length=32, choices=CREATION_MODES)
    payment_source = models.CharField(max_length=32, choices=PAYMENT_SOURCES, default="unknown")
    identity_digest = models.CharField(max_length=64, blank=True, default="", db_index=True)
    evidence_watermark_message_id = models.PositiveBigIntegerField(default=0)
    item_provenance = models.JSONField(default=list, blank=True)
    negotiated_total = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    price_source = models.CharField(max_length=64, blank=True, default="")
    price_evidence_message_ids = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="ig_order_attributions_created",
        db_constraint=False,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("Атрибуція Instagram-замовлення")
        verbose_name_plural = _("Атрибуції Instagram-замовлень")
        indexes = [
            models.Index(fields=["client", "-created_at"], name="ig_order_attr_client_dt"),
            models.Index(fields=["creation_mode", "-created_at"], name="ig_order_attr_mode_dt"),
        ]

    objects = models.Manager.from_queryset(_AppendOnlyOrderAttributionQuerySet)()

    def save(self, *args, **kwargs):
        if self.pk and not kwargs.get("force_insert"):
            raise ValueError("IgOrderAttribution is append-only")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("IgOrderAttribution is append-only")


class _AppendOnlyOrderLinkEventQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValueError("IgOrderLinkEvent is append-only")

    def delete(self):
        raise ValueError("IgOrderLinkEvent is append-only")


class IgOrderLinkEvent(models.Model):
    """Auditable edge between a payment review episode and an order."""

    order = models.ForeignKey(
        "orders.Order", on_delete=models.DO_NOTHING, db_constraint=False,
        related_name="instagram_link_events"
    )
    client = models.ForeignKey(
        "management.IgClient", on_delete=models.DO_NOTHING, db_constraint=False,
        related_name="order_link_events",
    )
    review = models.ForeignKey(
        "management.IgPaymentConfirmationReview", null=True, blank=True,
        on_delete=models.DO_NOTHING, related_name="order_link_events", db_constraint=False,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.DO_NOTHING,
        related_name="ig_order_link_events", db_constraint=False,
    )
    event_kind = models.CharField(max_length=32, default="linked")
    reason_code = models.CharField(max_length=64, blank=True, default="")
    mismatch_snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["order", "review", "event_kind"],
                name="ig_order_link_event_once",
            )
        ]
        indexes = [models.Index(fields=["client", "-created_at"], name="ig_order_link_client_dt")]

    objects = models.Manager.from_queryset(_AppendOnlyOrderLinkEventQuerySet)()

    def save(self, *args, **kwargs):
        if self.pk and not kwargs.get("force_insert"):
            raise ValueError("IgOrderLinkEvent is append-only")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("IgOrderLinkEvent is append-only")


class IgCommercialEpisode(models.Model):
    """Durable Instagram purchase journey with one intended physical order."""

    class State(models.TextChoices):
        ACTIVE = "active", _("Активний цикл")
        ORDER_CREATED = "order_created", _("Замовлення створено")
        FULFILLED = "fulfilled", _("Замовлення виконано")
        CANCELLED = "cancelled", _("Скасовано")
        LOST = "lost", _("Втрачено")

    class RepeatKind(models.TextChoices):
        FIRST_PURCHASE = "first_purchase", _("Перша покупка")
        EXPLICIT_MORE = "explicit_more", _("Хоче ще")
        REORDER = "reorder", _("Повторне замовлення")
        GIFT = "gift", _("Подарунок")
        ANOTHER_RECIPIENT = "another_recipient", _("Для іншого отримувача")

    client = models.ForeignKey(
        "management.IgClient",
        on_delete=models.DO_NOTHING,
        related_name="commercial_episodes",
        db_constraint=False,
    )
    sequence = models.PositiveIntegerField()
    # MariaDB permits multiple NULL values but only one value=1 per client.
    # This gives a database-backed single-current-episode guard.
    open_slot = models.PositiveSmallIntegerField(null=True, blank=True, default=1)
    materialization_key = models.CharField(max_length=96, unique=True)
    state = models.CharField(
        max_length=24,
        choices=State.choices,
        default=State.ACTIVE,
        db_index=True,
    )
    repeat_kind = models.CharField(
        max_length=32,
        choices=RepeatKind.choices,
        default=RepeatKind.FIRST_PURCHASE,
        db_index=True,
    )
    deal = models.OneToOneField(
        "management.IgDeal",
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="commercial_episode",
        db_constraint=False,
    )
    primary_payment_review = models.OneToOneField(
        "management.IgPaymentConfirmationReview",
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="commercial_episode",
        db_constraint=False,
    )
    order_attribution = models.OneToOneField(
        "management.IgOrderAttribution",
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="commercial_episode",
        db_constraint=False,
    )
    intended_order = models.OneToOneField(
        "orders.Order",
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="instagram_commercial_episode",
        db_constraint=False,
    )
    stage_snapshot = models.JSONField(default=dict, blank=True)
    product_snapshot = models.JSONField(default=list, blank=True)
    price_snapshot = models.JSONField(default=dict, blank=True)
    payment_snapshot = models.JSONField(default=dict, blank=True)
    fulfillment_snapshot = models.JSONField(default=dict, blank=True)
    outcome = models.CharField(max_length=64, blank=True, default="")
    repeat_evidence_message_ids = models.JSONField(default=list, blank=True)
    repeat_confidence = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    analysis_model = models.CharField(max_length=80, blank=True, default="")
    analysis_prompt_version = models.CharField(max_length=80, blank=True, default="")
    opened_watermark_message_id = models.BigIntegerField(default=0, db_index=True)
    shipment_notified_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(auto_now_add=True, db_index=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Комерційний епізод Instagram")
        verbose_name_plural = _("Комерційні епізоди Instagram")
        ordering = ["-sequence", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["client", "sequence"],
                name="ig_episode_client_sequence_once",
            ),
            models.UniqueConstraint(
                fields=["client", "open_slot"],
                name="ig_episode_one_open_slot",
            ),
            models.CheckConstraint(
                condition=models.Q(open_slot__isnull=True) | models.Q(open_slot=1),
                name="ig_episode_open_slot_null_or_one",
            ),
        ]
        indexes = [
            models.Index(fields=["client", "-opened_at"], name="ig_episode_client_opened"),
            models.Index(fields=["state", "-updated_at"], name="ig_episode_state_updated"),
        ]

    def __str__(self):  # pragma: no cover - trivial representation
        return f"IgCommercialEpisode#{self.pk} client={self.client_id} seq={self.sequence}"

    @property
    def evidence_message_ids(self):
        """Stable public alias for the bounded episode API/test contract."""
        return list(self.repeat_evidence_message_ids or [])


class IgPostSaleCase(models.Model):
    """Exchange or return request tied to an existing purchase journey."""

    class CaseType(models.TextChoices):
        EXCHANGE = "exchange", _("Обмін")
        RETURN = "return", _("Повернення")

    class Status(models.TextChoices):
        NEEDS_DETAILS = "needs_details", _("Потрібні уточнення")
        OPEN = "open", _("Відкрито")
        APPROVED = "approved", _("Погоджено")
        IN_TRANSIT = "in_transit", _("У дорозі")
        RECEIVED = "received", _("Отримано")
        COMPLETED = "completed", _("Завершено")
        REJECTED = "rejected", _("Відхилено")
        CANCELLED = "cancelled", _("Скасовано")

    client = models.ForeignKey(
        "management.IgClient",
        on_delete=models.DO_NOTHING,
        related_name="post_sale_cases",
        db_constraint=False,
    )
    order = models.ForeignKey(
        "orders.Order",
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="instagram_post_sale_cases",
        db_constraint=False,
    )
    commercial_episode = models.ForeignKey(
        "management.IgCommercialEpisode",
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="post_sale_cases",
        db_constraint=False,
    )
    source_message = models.OneToOneField(
        "management.InstagramBotMessage",
        on_delete=models.DO_NOTHING,
        related_name="post_sale_case",
        db_constraint=False,
    )
    case_type = models.CharField(max_length=16, choices=CaseType.choices, db_index=True)
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.NEEDS_DETAILS,
        db_index=True,
    )
    source_item_title = models.CharField(max_length=255, blank=True, default="")
    source_fit = models.CharField(max_length=64, blank=True, default="")
    source_size = models.CharField(max_length=32, blank=True, default="")
    requested_fit = models.CharField(max_length=64, blank=True, default="")
    requested_size = models.CharField(max_length=32, blank=True, default="")
    reason = models.CharField(max_length=500, blank=True, default="")
    manager_note = models.TextField(blank=True, default="")
    evidence_message_ids = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="ig_post_sale_cases_created",
        db_constraint=False,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Післяпродажне звернення Instagram")
        verbose_name_plural = _("Післяпродажні звернення Instagram")
        ordering = ["-updated_at", "-id"]
        indexes = [
            models.Index(fields=["client", "status", "-updated_at"], name="ig_postsale_client_state"),
            models.Index(fields=["order", "-updated_at"], name="ig_postsale_order_dt"),
        ]


class _AppendOnlyCommercialEpisodeEventQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValueError("IgCommercialEpisodeEvent is append-only")

    def delete(self):
        raise ValueError("IgCommercialEpisodeEvent is append-only")


class IgCommercialEpisodeEvent(models.Model):
    """Append-only episode timeline for funnel, payment, order and shipment."""

    episode = models.ForeignKey(
        "management.IgCommercialEpisode",
        on_delete=models.DO_NOTHING,
        related_name="events",
        db_constraint=False,
    )
    dedupe_key = models.CharField(max_length=160, unique=True)
    event_type = models.CharField(max_length=40)
    from_state = models.CharField(max_length=32, blank=True, default="")
    to_state = models.CharField(max_length=32, blank=True, default="")
    stage = models.CharField(max_length=32, blank=True, default="")
    source = models.CharField(max_length=40, blank=True, default="")
    evidence = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    objects = models.Manager.from_queryset(_AppendOnlyCommercialEpisodeEventQuerySet)()

    class Meta:
        verbose_name = _("Подія комерційного епізоду Instagram")
        verbose_name_plural = _("Події комерційних епізодів Instagram")
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["episode", "-created_at"], name="ig_episode_event_dt"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and not kwargs.get("force_insert"):
            raise ValueError("IgCommercialEpisodeEvent is append-only")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("IgCommercialEpisodeEvent is append-only")


class BotInstruction(models.Model):
    """Окрема інструкція для бота (нескінченна кількість, редагується в UI).

    Усі активні інструкції збираються в один блок і інжектяться в контекст
    Gemini поряд з базою знань. intent_tags — необов'язкові ключові слова, за
    якими в майбутньому можна підбирати релевантні інструкції під запит.
    """

    title = models.CharField(_("Заголовок"), max_length=200, blank=True, default="")
    body = models.TextField(_("Текст інструкції"))
    intent_tags = models.CharField(
        _("Ключові слова (через кому)"), max_length=400, blank=True, default=""
    )
    is_active = models.BooleanField(_("Активна"), default=True, db_index=True)
    priority = models.IntegerField(_("Пріоритет"), default=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Інструкція бота")
        verbose_name_plural = _("Інструкції бота")
        ordering = ["priority", "id"]

    def __str__(self) -> str:  # pragma: no cover - тривіально
        return self.title or (self.body[:50] if self.body else f"Instruction#{self.pk}")

    @classmethod
    def active_block(cls) -> str:
        """Текст усіх активних інструкцій (для інжекту в system_instruction)."""
        parts = []
        for inst in cls.objects.filter(is_active=True).order_by("priority", "id"):
            body = (inst.body or "").strip()
            if not body:
                continue
            title = (inst.title or "").strip()
            parts.append(f"• {title}: {body}" if title else f"• {body}")
        return "\n".join(parts)


class BotQuickLink(models.Model):
    """Швидке посилання, яке бот може надіслати (розмірна сітка-хайлайт,
    каталог, тощо). garment_type дозволяє підібрати правильну розмірну сітку."""

    class Kind(models.TextChoices):
        SIZE_CHART = "size_chart", _("Розмірна сітка")
        CATALOG = "catalog", _("Каталог")
        HIGHLIGHT = "highlight", _("Хайлайт")
        OTHER = "other", _("Інше")

    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.OTHER, db_index=True)
    label = models.CharField(_("Підпис"), max_length=200)
    url = models.CharField(_("Посилання"), max_length=600)
    garment_type = models.CharField(
        _("Тип одягу (tshirt/hoodie/longsleeve…)"), max_length=40, blank=True, default="", db_index=True
    )
    trigger_keywords = models.CharField(
        _("Тригер-слова (через кому)"), max_length=400, blank=True, default=""
    )
    is_active = models.BooleanField(default=True, db_index=True)
    order = models.IntegerField(default=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Швидке посилання бота")
        verbose_name_plural = _("Швидкі посилання бота")
        ordering = ["order", "id"]

    def __str__(self) -> str:  # pragma: no cover - тривіально
        return f"{self.label} ({self.kind})"

    @classmethod
    def for_garment(cls, garment_type: str, kind: str | None = None):
        qs = cls.objects.filter(is_active=True)
        if kind:
            qs = qs.filter(kind=kind)
        if garment_type:
            qs = qs.filter(garment_type=garment_type)
        return qs.order_by("order", "id").first()

    @classmethod
    def active_block(cls) -> str:
        """Текст активних швидких посилань (інжектиться в контекст бота)."""
        lines = []
        for ln in cls.objects.filter(is_active=True).order_by("order", "id"):
            gt = f" [{ln.garment_type}]" if ln.garment_type else ""
            lines.append(f"• {ln.get_kind_display()}{gt}: {ln.label} — {ln.url}")
        return "\n".join(lines)


class BotAdCampaign(models.Model):
    """Мапінг рекламної кампанії (Click-to-IG-Direct) на товар/тему.

    Коли клієнт пише з реклами, referral дає ad_id/ref. Якщо ad_title загальний,
    цей мапінг каже боту, ЩО саме продавала реклама (товар або тема), щоб одразу
    вести по суті, а не питати «дайте фото».
    """

    ad_id = models.CharField(_("Ad ID"), max_length=64, blank=True, default="", db_index=True)
    ref = models.CharField(_("Ref"), max_length=255, blank=True, default="", db_index=True)
    title = models.CharField(_("Назва кампанії"), max_length=255, blank=True, default="")
    product = models.ForeignKey(
        "storefront.Product", null=True, blank=True, on_delete=models.SET_NULL
    )
    theme = models.CharField(_("Тема"), max_length=120, blank=True, default="")
    landing_note = models.TextField(_("Що в рекламі / CTA"), blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Рекламна кампанія бота")
        verbose_name_plural = _("Рекламні кампанії бота")
        ordering = ["-id"]

    def __str__(self) -> str:  # pragma: no cover - тривіально
        return self.title or self.ad_id or self.ref or f"AdCampaign#{self.pk}"

    @classmethod
    def match(cls, ad_id: str | None = None, ref: str | None = None):
        qs = cls.objects.filter(is_active=True)
        if ad_id:
            obj = qs.filter(ad_id=ad_id).first()
            if obj:
                return obj
        if ref:
            obj = qs.filter(ref=ref).first()
            if obj:
                return obj
        return None


class IgClientStageEvent(models.Model):
    """Подія зміни стадії воронки клієнта (для таймлайну/кружечків у картці)."""

    client = models.ForeignKey(
        "management.IgClient", on_delete=models.CASCADE, related_name="stage_events"
    )
    from_stage = models.CharField(max_length=24, blank=True, default="")
    to_stage = models.CharField(max_length=24)
    reason = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("Подія стадії IG-клієнта")
        verbose_name_plural = _("Події стадій IG-клієнтів")
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["client", "-id"], name="ig_stageevent_client"),
        ]

    def __str__(self) -> str:  # pragma: no cover - тривіально
        return f"{self.client_id}: {self.from_stage}→{self.to_stage}"


class IgFollowUpTask(models.Model):
    """Scheduled Instagram follow-up with Meta-window and quiet-hours guardrails."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Очікує")
        SENT = "sent", _("Надіслано")
        CANCELLED = "cancelled", _("Скасовано")
        SKIPPED = "skipped", _("Пропущено")

    class Kind(models.TextChoices):
        QUALIFICATION = "qualification", _("Уточнення")
        PAYMENT = "payment", _("Нагадування про оплату")
        THINKING = "thinking", _("Клієнт думає")
        RESCUE = "rescue", _("Rescue offer")
        FINAL = "final", _("Фінальний офер")
        MANAGER_TASK = "manager_task", _("Завдання менеджеру")

    client = models.ForeignKey(
        "management.IgClient", on_delete=models.CASCADE, related_name="followup_tasks"
    )
    deal = models.ForeignKey(
        "management.IgDeal", null=True, blank=True, on_delete=models.SET_NULL, related_name="followup_tasks"
    )
    due_at = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    kind = models.CharField(max_length=24, choices=Kind.choices, default=Kind.QUALIFICATION, db_index=True)
    level = models.PositiveSmallIntegerField(default=0)
    reason = models.CharField(max_length=120, blank=True, default="", db_index=True)
    discount_percent = models.PositiveSmallIntegerField(default=0)
    meta_window_deadline = models.DateTimeField(null=True, blank=True, db_index=True)
    message_text = models.TextField(blank=True, default="")
    sent_message = models.ForeignKey(
        "management.InstagramBotMessage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    skip_reason = models.CharField(max_length=255, blank=True, default="")
    attempt_count = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_error = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("IG follow-up")
        verbose_name_plural = _("IG follow-ups")
        ordering = ["due_at", "id"]
        indexes = [
            models.Index(fields=["status", "due_at"], name="ig_fu_status_due"),
            models.Index(fields=["client", "status"], name="ig_fu_client_status"),
            models.Index(fields=["kind", "status"], name="ig_fu_kind_status"),
        ]

    def __str__(self) -> str:  # pragma: no cover - тривіально
        return f"FollowUp#{self.pk} {self.client_id} {self.kind}/{self.status}"


class IgPollCursor(models.Model):
    """Durable per-conversation cursor for the optional polling backstop."""

    conversation_id = models.CharField(max_length=255, unique=True)
    last_message_id = models.CharField(max_length=255, blank=True, default="")
    last_message_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "IG polling cursor"
        verbose_name_plural = "IG polling cursors"

    def __str__(self) -> str:  # pragma: no cover - trivial representation
        return f"IgPollCursor({self.conversation_id})"


class IgConversationSignal(models.Model):
    """Classified sales signal extracted from client/bot/manager conversation."""

    class Type(models.TextChoices):
        PRICE_OBJECTION = "price_objection", _("Дорого")
        PREPAYMENT_OBJECTION = "prepayment_objection", _("Передоплата")
        SIZE_CONCERN = "size_concern", _("Розмір")
        GIFT = "gift", _("На подарунок")
        SELF_PURCHASE = "self_purchase", _("Для себе")
        CUSTOM_PRINT = "custom_print", _("Кастомний принт")
        AD_REPLY = "ad_reply", _("Відповідь з реклами")
        NO_REPLY = "no_reply", _("Не відповідає")
        CHECKOUT_STARTED = "checkout_started", _("Checkout started")
        PAYMENT_PENDING = "payment_pending", _("Очікує оплату")
        PAID = "paid", _("Оплачено")
        LOST = "lost", _("Втрачено")
        SPAM = "spam", _("Спам")
        MANAGER_TAKEOVER = "manager_takeover", _("Взяв менеджер")
        DISCOUNT_OFFER = "discount_offer", _("Знижка")
        PRODUCT_INTEREST = "product_interest", _("Інтерес до товару")

    client = models.ForeignKey(
        "management.IgClient", on_delete=models.CASCADE, related_name="conversation_signals"
    )
    message = models.ForeignKey(
        "management.InstagramBotMessage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="conversation_signals",
    )
    signal_type = models.CharField(max_length=40, choices=Type.choices, db_index=True)
    confidence = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("1.00"))
    value = models.CharField(max_length=255, blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("IG conversation signal")
        verbose_name_plural = _("IG conversation signals")
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["client", "-id"], name="ig_sig_client_id"),
            models.Index(fields=["signal_type", "-id"], name="ig_sig_type_id"),
        ]

    def __str__(self) -> str:  # pragma: no cover - тривіально
        return f"{self.client_id}: {self.signal_type}"


class IgConversationAnalysisSnapshot(models.Model):
    """Versioned, evidence-bound interpretation of one conversation watermark."""

    class Band(models.TextChoices):
        COLD = "cold", _("Холодний")
        EXPLORING = "exploring", _("Вивчає")
        QUALIFIED = "qualified", _("Кваліфікований")
        HIGH_INTENT = "high_intent", _("Високий намір")
        CHECKOUT = "checkout", _("Оформлення")
        PAID = "paid", _("Оплачено")
        LOST = "lost", _("Втрачено")
        OPTED_OUT = "opted_out", _("Відмовився від повідомлень")

    class InteractionType(models.TextChoices):
        UNKNOWN = "unknown", _("Невідомо")
        REACTION_ONLY = "reaction_only", _("Лише реакція")
        INFORMATION_ONLY = "information_only", _("Лише інформація")
        PRODUCT_INTEREST = "product_interest", _("Інтерес до товару")
        SIZE_FIT_QUESTION = "size_fit_question", _("Питання про розмір")
        CUSTOM_PRINT = "custom_print", _("Кастомний принт")
        PRICE_OBJECTION = "price_objection", _("Заперечення щодо ціни")
        HIGH_INTENT = "high_intent", _("Високий намір")
        PAYMENT_PENDING = "payment_pending", _("Очікує оплату")
        PAID_ORDER_WAITING = "paid_order_waiting", _("Оплачено / очікує товар")
        NO_REPLY = "no_reply", _("Не відповідає")
        EXPLICIT_NO_BUY = "explicit_no_buy", _("Явно не купує")
        OPT_OUT = "opt_out", _("Відмовився від повідомлень")
        SPAM_ABUSE = "spam_abuse", _("Спам / образи")
        MANAGER_OBSERVATION = "manager_observation", _("Спостереження менеджера")
        COLLABORATION = "collaboration", _("Співпраця / creator")
        WHOLESALE_B2B = "wholesale_b2b", _("Опт / B2B")
        SUPPORT_COMPLAINT = "support_complaint", _("Підтримка / скарга")
        COMMUNITY_CASUAL = "community_casual", _("Спільнота / casual")

    client = models.ForeignKey(
        "management.IgClient",
        on_delete=models.CASCADE,
        related_name="analysis_snapshots",
        # IgClient is a legacy MyISAM table in production; keep this new
        # InnoDB snapshot table valid without a cross-engine FK constraint.
        db_constraint=False,
    )
    last_analyzed_message = models.ForeignKey(
        "management.InstagramBotMessage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="analysis_snapshots",
        db_constraint=False,
    )
    dedupe_key = models.CharField(max_length=160, unique=True)
    score_band = models.CharField(max_length=24, choices=Band.choices, db_index=True)
    interaction_type = models.CharField(
        max_length=32,
        choices=InteractionType.choices,
        default=InteractionType.UNKNOWN,
        db_index=True,
    )
    purchase_probability = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal("0.0000")
    )
    confidence = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal("0.0000")
    )
    evidence = models.JSONField(default=list, blank=True)
    uncertainties = models.JSONField(default=list, blank=True)
    repeat_intent = models.JSONField(default=dict, blank=True)
    commercial_episode = models.ForeignKey(
        "management.IgCommercialEpisode",
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="analysis_snapshots",
        db_constraint=False,
    )
    analysis_model = models.CharField(max_length=80, blank=True, default="rules")
    analysis_prompt_version = models.CharField(max_length=40, blank=True, default="")
    required_state_fingerprint = models.CharField(max_length=64, blank=True, default="")
    rules_version = models.CharField(max_length=40, blank=True, default="")
    key_alias = models.CharField(max_length=32, blank=True, default="")
    reasoning_task = models.CharField(max_length=64, blank=True, default="")
    reasoning_level = models.CharField(max_length=16, blank=True, default="")
    reasoning_policy_version = models.CharField(max_length=32, blank=True, default="")
    thoughts_tokens = models.PositiveIntegerField(default=0)
    candidates_tokens = models.PositiveIntegerField(default=0)
    trigger = models.CharField(max_length=32, blank=True, default="message", db_index=True)
    analysis_latency_ms = models.PositiveIntegerField(default=0)
    analyzed_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("Знімок аналізу IG-діалогу")
        verbose_name_plural = _("Знімки аналізу IG-діалогів")
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["client", "-id"], name="ig_analysis_client_id"),
            models.Index(fields=["score_band", "-id"], name="ig_analysis_band_id"),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial representation
        return f"{self.client_id}: {self.score_band} ({self.purchase_probability})"


class IgConversationAnalysisJob(models.Model):
    """One durable, coalescing high-reasoning analysis cursor per IG client."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Очікує аналізу")
        PROCESSING = "processing", _("Аналізується")
        DONE = "done", _("Проаналізовано")
        FAILED = "failed", _("Помилка аналізу")
        SKIPPED = "skipped", _("Аналіз пропущено")

    client = models.OneToOneField(
        "management.IgClient",
        on_delete=models.CASCADE,
        related_name="analysis_job",
        db_constraint=False,
    )
    watermark_message_id = models.PositiveBigIntegerField(default=0)
    analyzed_watermark_message_id = models.PositiveBigIntegerField(default=0)
    revision = models.PositiveBigIntegerField(default=0)
    analyzed_revision = models.PositiveBigIntegerField(default=0)
    claimed_watermark_message_id = models.PositiveBigIntegerField(default=0)
    claimed_revision = models.PositiveBigIntegerField(default=0)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    due_at = models.DateTimeField(default=timezone.now, db_index=True)
    next_attempt_at = models.DateTimeField(default=timezone.now, db_index=True)
    lease_token = models.CharField(max_length=40, blank=True, default="")
    lease_until = models.DateTimeField(null=True, blank=True, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.CharField(max_length=1000, blank=True, default="")
    skip_reason = models.CharField(max_length=64, blank=True, default="")
    trigger = models.CharField(max_length=32, blank=True, default="message")
    analysis_model = models.CharField(max_length=80, blank=True, default="")
    analysis_prompt_version = models.CharField(max_length=40, blank=True, default="")
    required_state_fingerprint = models.CharField(max_length=64, blank=True, default="")
    key_alias = models.CharField(max_length=32, blank=True, default="")
    reasoning_task = models.CharField(max_length=64, blank=True, default="")
    reasoning_level = models.CharField(max_length=16, blank=True, default="")
    reasoning_policy_version = models.CharField(max_length=32, blank=True, default="")
    thoughts_tokens = models.PositiveIntegerField(default=0)
    candidates_tokens = models.PositiveIntegerField(default=0)
    analysis_latency_ms = models.PositiveIntegerField(default=0)
    analyzed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Завдання аналізу IG-діалогу")
        verbose_name_plural = _("Завдання аналізу IG-діалогів")
        ordering = ["due_at", "id"]
        indexes = [
            models.Index(fields=["status", "next_attempt_at", "due_at"], name="ig_analysis_job_due"),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial representation
        return f"{self.client_id}: {self.status}@{self.watermark_message_id}"


class IgMetaEventLog(models.Model):
    """Audit log for safe Meta CAPI feedback attempts from IG Direct funnel."""

    class Status(models.TextChoices):
        DISABLED = "disabled", _("Вимкнено")
        SKIPPED = "skipped", _("Пропущено")
        SENT = "sent", _("Надіслано")
        FAILED = "failed", _("Помилка")

    event_name = models.CharField(max_length=80, db_index=True)
    event_id = models.CharField(max_length=120, blank=True, default="", db_index=True)
    client = models.ForeignKey(
        "management.IgClient", null=True, blank=True, on_delete=models.SET_NULL, related_name="meta_events"
    )
    deal = models.ForeignKey(
        "management.IgDeal", null=True, blank=True, on_delete=models.SET_NULL, related_name="meta_events"
    )
    order = models.ForeignKey(
        "orders.Order", null=True, blank=True, on_delete=models.SET_NULL, related_name="ig_meta_events"
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SKIPPED, db_index=True)
    reason = models.CharField(max_length=255, blank=True, default="")
    response_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("IG Meta event log")
        verbose_name_plural = _("IG Meta event logs")
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["event_name", "-id"], name="ig_meta_event_id"),
            models.Index(fields=["status", "-id"], name="ig_meta_status_id"),
        ]

    def __str__(self) -> str:  # pragma: no cover - тривіально
        return f"{self.event_name}:{self.status}"
