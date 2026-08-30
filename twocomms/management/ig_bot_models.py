"""Моделі апгрейду Instagram-бота TwoComms (Phase 0+).

Винесені в окремий модуль, щоб не роздувати і без того велику models.py.
Імпортуються в кінці management/models.py (`from .ig_bot_models import *`),
тож app_label='management' визначається автоматично, а міграції лягають у
management/migrations. Перехресні FK задаються рядком ('management.IgClient',
'orders.Order') — без жорстких import, щоб уникнути циклічних залежностей.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.signing import salted_hmac
from django.db import transaction
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

__all__ = [
    "InstagramBotRawEvent",
    "IgClient",
    "IgDeal",
    "IgDealInvoiceLifecycle",
    "IgPaymentEvent",
    "IgPaymentProjection",
    "IgDealItem",
    "BotInstruction",
    "BotQuickLink",
    "BotAdCampaign",
    "IgClientStageEvent",
    "IgFollowUpTask",
    "IgPollCursor",
    "IgInboxRefreshRun",
    "IgInboxRefreshItem",
    "IgConversationSignal",
    "IgObjection",
    "IgObjectionAttempt",
    "IgConversationAnalysisSnapshot",
    "IgConversationAnalysisEvent",
    "IgConversationAnalysisJob",
    "IgAiReplyRecoveryJob",
    "IgProviderIncident",
    "IgClientDegradationEpisode",
    "IgCustomerTurn",
    "IgTurnMessage",
    "IgPermissionTransitionJob",
    "IgMetaEventLog",
    "BotDataDeletionRequest",
    "IgBotNotification",
    "IgBotNotificationAudit",
    "IgPaymentConfirmationReview",
    "IgPaymentReviewDecision",
    "IgOrderAttribution",
    "IgOrderLinkEvent",
    "IgOrderAssignment",
    "IgOrderAssignmentEvent",
    "IgUgcReward",
    "IgUgcEvidenceAssessment",
    "IgUgcRewardLifetime",
    "IgUgcRewardDelivery",
    "IgUgcRewardLifecycleJob",
    "IgOrderCustomerEvent",
    "IgCommercialEpisode",
    "IgCommercialEpisodeEvent",
    "IgFunnelStepEvent",
    "IgFunnelDropOff",
    "IgPostSaleCase",
    "IgOrderShipment",
    "BotPromptRevision",
    "IgFunnelResetAudit",
    "IgCheckoutProposal",
    "IgCheckoutProposalItem",
    "IgCheckoutRevision",
    "IgCheckoutAccessToken",
    "IgCheckoutInventoryReservation",
    "IgLifecycleEvent",
    "IgFollowCapabilityState",
    "IgFollowState",
    "IgFollowObservation",
    "IgFollowRefreshJob",
    "IgFollowCtaDecision",
    "IgPaymentFollowPreparation",
    "IgCommerceSelectionSession",
    "IgCommerceSelectionTransition",
    "IgCommerceTurnDecision",
    "IgCommerceManagerReview",
    "provider_evidence_signature",
]


def provider_evidence_signature(
    *,
    deal_id,
    client_id,
    provider,
    source,
    invoice_id,
    provider_status,
    payload_digest,
):
    """Authenticate provider observations before they can authorize money state."""
    canonical = json.dumps(
        {
            "client_id": int(client_id),
            "deal_id": int(deal_id),
            "invoice_id": str(invoice_id or ""),
            "payload_digest": str(payload_digest or ""),
            "provider": str(provider or ""),
            "provider_status": str(provider_status or ""),
            "source": str(source or ""),
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return salted_hmac(
        "twocomms.ig_payment_event.v1",
        canonical,
        algorithm="sha1",
    ).hexdigest()


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
        # Заявка принята, но владение идентификатором ещё не подтверждено.
        # Публичная форма создаёт ТОЛЬКО этот статус: удалять данные по
        # анонимному POST нельзя (F-SEC-002). Переход в COMPLETED/NO_MATCH
        # делает менеджер через `services.ig_data_deletion`.
        PENDING_VERIFICATION = "pending_verification", "Pending ownership verification"

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
    # Окно Meta считается ТОЛЬКО от этого поля. `last_message_at` смешивает
    # входящие и исходящие (у него четыре писателя, включая backfill без фильтра
    # по роли) и остаётся для сортировки списка и отображения — там смешивание
    # удобно. Разделение полей дешевле, чем дисциплинировать четырёх писателей.
    last_user_message_at = models.DateTimeField(null=True, blank=True, db_index=True)
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
        """Оновлює стадію + час і фіксує перехід у таймлайні (IgClientStageEvent).

        Э3.2: стадія і подія пишуться в ОДНІЙ транзакції. Раніше стадія
        зберігалась, а створення `IgClientStageEvent` стояло в окремому
        `try/except`, який **проглатував** виключення. `ig_funnel_fsm` трактував
        відсутність виключення як успішний перехід, тому в CRM з'являлась стадія
        без жодного evidence у таймлайні — і на питання «як клієнт тут опинився»
        відповіді не було. Без атомарності не можна довіряти ні воронці, ні
        аналітиці, а на них опирається майже все інше.

        Виключення тепер НЕ проглатується: транзакція відкочує і стадію, і
        подію, а `apply_stage` повертає `write_failed`. Тихого успіху більше
        немає.

        Атомарність тут реально виконувана: зріз Э0.2 на production підтвердив
        InnoDB для `management_igclient` і `management_igclientstageevent`.
        """
        from django.db import transaction
        from django.utils import timezone

        old = self.stage
        stage_at = timezone.now()
        with transaction.atomic():
            from management.models import IgClientStageEvent

            self.stage = new_stage
            self.stage_updated_at = stage_at
            self.save(update_fields=["stage", "stage_updated_at", "updated_at"])
            IgClientStageEvent.objects.create(
                client=self,
                from_stage=old or "",
                to_stage=new_stage,
                reason=(reason or "")[:255],
            )

    def touch_inbound(self) -> None:
        """Фіксує вхідне повідомлення: first_contact_at (раз) і last_message_at."""
        from django.utils import timezone

        now = timezone.now()
        fields = ["last_message_at", "last_user_message_at", "updated_at"]
        if not self.first_contact_at:
            self.first_contact_at = now
            fields.append("first_contact_at")
        self.last_message_at = now
        # Вікно Meta відкриває ТІЛЬКИ повідомлення клієнта. `last_message_at`
        # має чотирьох писателів, один з них — backfill з `Max("created_at")`
        # без фільтра по ролі, тому вихідне повідомлення бота потрапляло в поле
        # і «відкривало» вікно, якого не було (Э2.6).
        self.last_user_message_at = now
        self.save(update_fields=fields)

    @property
    def meta_window_anchor(self):
        """Єдина точка істини для початку відліку 24-годинного вікна Meta.

        Читати вікно напряму з `last_message_at` не можна: у нього пишуть і
        вихідні повідомлення, тому власне повідомлення бота «відкривало» вікно,
        якого не було.

        Перехідний dual-read: якщо нове поле ще NULL (клієнт створений до
        міграції `0172` і не потрапив у backfill), падаємо назад на
        `last_message_at`. Це expand-фаза: для таких рядків ми просто не маємо
        інформації, а вважати вікно закритим для всієї історії означало б
        замовкнути для реальних клієнтів. Для всіх рядків з заповненим полем
        (увесь новий трафік і backfill) діє строгий контракт. Прибрати fallback
        можна тільки після перевірки backfill на production — це contract-фаза.
        """
        return self.last_user_message_at or self.last_message_at or self.first_contact_at

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
    # Инвойсы, которые мы перестали считать актуальными (смена товара или
    # типа оплаты). Ссылка при этом остаётся оплачиваемой на стороне
    # Monobank, поэтому платёж по ней обязан находить сделку (F-PAY-001).
    superseded_invoice_ids = models.JSONField(default=list, blank=True)
    # IMP-050: без срока жизни ссылки истечение ненаблюдаемо, и бот отвечал
    # «посилання ще активне», не проверив ничего. NULL означает «не знаем»
    # (ссылка выдана до появления поля), а не «истекла».
    invoice_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
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
    active_checkout_proposal = models.OneToOneField(
        "management.IgCheckoutProposal",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="active_for_deal",
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


class IgDealInvoiceLifecycle(models.Model):
    """Bounded provider lifecycle for each current or superseded invoice."""

    class Status(models.TextChoices):
        OPEN = "open", _("Активний моніторинг")
        PAID = "paid", _("Оплачено")
        FAILED = "failed", _("Помилка оплати")
        CANCELLED = "cancelled", _("Скасовано")
        EXPIRED = "expired", _("Протерміновано")
        UNKNOWN = "unknown", _("Термін моніторингу вичерпано")

    deal = models.ForeignKey(
        "management.IgDeal",
        on_delete=models.CASCADE,
        related_name="invoice_lifecycles",
        db_constraint=False,
    )
    invoice_id = models.CharField(max_length=128, unique=True, db_index=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    provider_status = models.CharField(max_length=32, blank=True, default="")
    superseded_at = models.DateTimeField(null=True, blank=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_polled_at = models.DateTimeField(null=True, blank=True)
    next_poll_at = models.DateTimeField(null=True, blank=True, db_index=True)
    terminal_at = models.DateTimeField(null=True, blank=True, db_index=True)
    poll_attempts = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [
            models.Index(fields=["deal", "status"], name="ig_inv_life_deal_status"),
            models.Index(fields=["status", "next_poll_at"], name="ig_inv_life_poll_due"),
        ]

    @property
    def is_terminal(self):
        return self.status != self.Status.OPEN


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

    class ResolutionKind(models.TextChoices):
        NONE = "", _("Не завершено окремим рішенням")
        HISTORICAL_PAID_ARCHIVED = (
            "historical_paid_archived",
            _("Старий оплачений продаж архівовано"),
        )

    class ResolutionOutcome(models.TextChoices):
        ALREADY_RECEIVED = "already_received", _("Старе замовлення отримано")
        ALREADY_DELIVERED = "already_delivered", _("Старе замовлення доставлено")
        COMPLETED_UNKNOWN = (
            "completed_unknown",
            _("Старе замовлення завершено; спосіб невідомий"),
        )

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
    resolution_kind = models.CharField(
        max_length=40,
        choices=ResolutionKind.choices,
        blank=True,
        default=ResolutionKind.NONE,
        db_index=True,
    )
    resolution_outcome = models.CharField(
        max_length=32,
        choices=ResolutionOutcome.choices,
        null=True,
        blank=True,
    )
    resolution_note = models.TextField(blank=True, default="")
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resolved_ig_payment_reviews",
        db_constraint=False,
    )
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
        HISTORICAL_FULFILLED = "historical_fulfilled", _("Історично виконане замовлення")

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
    order_total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Повна вартість замовлення, відновлена для історичного завершення.",
    )
    order_total_source = models.CharField(max_length=48, blank=True, default="")
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


_ig_order_assignment_mutation_allowed = ContextVar(
    "ig_order_assignment_mutation_allowed",
    default=False,
)


@contextmanager
def _ig_order_assignment_mutation_scope():
    token = _ig_order_assignment_mutation_allowed.set(True)
    try:
        yield
    finally:
        _ig_order_assignment_mutation_allowed.reset(token)


def _require_ig_order_assignment_mutation_scope():
    if not _ig_order_assignment_mutation_allowed.get():
        raise ValueError(
            "IgOrderAssignment is managed by the assignment service"
        )


class _IgOrderAssignmentQuerySet(models.QuerySet):
    def update(self, **kwargs):
        _require_ig_order_assignment_mutation_scope()
        return super().update(**kwargs)

    def bulk_create(self, objs, batch_size=None, ignore_conflicts=False, update_conflicts=False, update_fields=None, unique_fields=None):
        _require_ig_order_assignment_mutation_scope()
        return super().bulk_create(
            objs,
            batch_size=batch_size,
            ignore_conflicts=ignore_conflicts,
            update_conflicts=update_conflicts,
            update_fields=update_fields,
            unique_fields=unique_fields,
        )

    def bulk_update(self, objs, fields, batch_size=None):
        _require_ig_order_assignment_mutation_scope()
        return super().bulk_update(objs, fields, batch_size=batch_size)

    def delete(self):
        raise ValueError("IgOrderAssignment is managed by the assignment service")

    def _raw_delete(self, using):
        raise ValueError("IgOrderAssignment is managed by the assignment service")


class IgOrderAssignment(models.Model):
    """Current operational owner of an order in the Instagram workspace."""

    class Source(models.TextChoices):
        PROVIDER_AUTO = "provider_auto", _("Автоматично за оплатою")
        CHECKOUT_AUTO = "checkout_auto", _("Автоматично через Direct checkout")
        MANAGER_PAYMENT_REVIEW = "manager_payment_review", _("Менеджер після перевірки оплати")
        MANAGER_MANUAL = "manager_manual", _("Менеджер вручну")
        MANAGER_CREATED = "manager_created", _("Створено менеджером")
        LEGACY_ATTRIBUTION = "legacy_attribution", _("Імпортовано з атрибуції")

    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name="instagram_assignment",
    )
    client = models.ForeignKey(
        "management.IgClient",
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name="order_assignments",
    )
    source = models.CharField(max_length=32, choices=Source.choices, db_index=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name="ig_order_assignments",
    )
    assigned_at = models.DateTimeField(default=timezone.now, db_index=True)
    unassigned_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    last_reason_code = models.CharField(max_length=64, blank=True, default="")
    last_reason = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-assigned_at", "-id"]
        indexes = [
            models.Index(fields=["client", "-assigned_at"], name="ig_assign_client_dt"),
            models.Index(fields=["source", "-assigned_at"], name="ig_assign_source_dt"),
        ]

    objects = models.Manager.from_queryset(_IgOrderAssignmentQuerySet)()

    def save(self, *args, **kwargs):
        _require_ig_order_assignment_mutation_scope()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("IgOrderAssignment is managed by the assignment service")


class _AppendOnlyOrderAssignmentEventQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValueError("IgOrderAssignmentEvent is append-only")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValueError("IgOrderAssignmentEvent is append-only")

    def delete(self):
        raise ValueError("IgOrderAssignmentEvent is append-only")

    def _raw_delete(self, using):
        raise ValueError("IgOrderAssignmentEvent is append-only")


class IgOrderAssignmentEvent(models.Model):
    """Immutable audit trail for manager and automatic assignment changes."""

    class Kind(models.TextChoices):
        LINKED = "linked", _("Прив'язано")
        UNLINKED = "unlinked", _("Відв'язано")
        AUTO_CONFIRMED = "auto_confirmed", _("Автоматичну прив'язку підтверджено")

    class ActorSource(models.TextChoices):
        MANAGEMENT_USER = "management_user", _("Користувач management")
        AUTOMATION = "automation", _("Автоматизація")
        MIGRATION = "migration", _("Міграція")

    operation_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    assignment = models.ForeignKey(
        "management.IgOrderAssignment",
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name="events",
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name="instagram_assignment_events",
    )
    kind = models.CharField(max_length=24, choices=Kind.choices, db_index=True)
    from_client = models.ForeignKey(
        "management.IgClient",
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name="order_assignment_events_from",
    )
    to_client = models.ForeignKey(
        "management.IgClient",
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name="order_assignment_events_to",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name="ig_order_assignment_events",
    )
    actor_source = models.CharField(max_length=24, choices=ActorSource.choices)
    assignment_source = models.CharField(max_length=32, choices=IgOrderAssignment.Source.choices)
    reason_code = models.CharField(max_length=64, blank=True, default="")
    reason = models.CharField(max_length=500, blank=True, default="")
    assignment_version = models.PositiveIntegerField()
    snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = models.Manager.from_queryset(_AppendOnlyOrderAssignmentEventQuerySet)()

    class Meta:
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["assignment", "-created_at"], name="ig_assign_evt_dt"),
            models.Index(fields=["order", "-created_at"], name="ig_assign_order_evt"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and not kwargs.get("force_insert"):
            raise ValueError("IgOrderAssignmentEvent is append-only")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("IgOrderAssignmentEvent is append-only")


class IgUgcReward(models.Model):
    """One lifetime UGC grant for an Instagram identity.

    ``delivered_order`` keeps the historical order/assignment requirements;
    ``external_ugc`` deliberately leaves them empty because a qualifying
    provider-native mention may come from the public site, a store, a friend,
    or another sales channel.
    """

    class EvidenceType(models.TextChoices):
        DIRECT_MESSAGE = "direct_message", _("Повідомлення Direct")
        INSTAGRAM_URL = "instagram_url", _("Посилання Instagram")
        STORY_MENTION = "story_mention", _("Відмітка в story")

    class LifecycleState(models.TextChoices):
        ACTIVE = "active", _("Активна")
        HELD = "held", _("Тимчасово призупинена")
        REVOKED = "revoked", _("Відкликана")

    client = models.ForeignKey(
        "management.IgClient",
        on_delete=models.SET_NULL,
        related_name="ugc_rewards",
        null=True,
        blank=True,
        db_constraint=False,
    )
    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="instagram_ugc_reward",
        null=True,
        blank=True,
        # Production still contains legacy tables with mixed storage engines;
        # retain this relationship at the ORM/service boundary only.
        db_constraint=False,
    )
    assignment = models.ForeignKey(
        "management.IgOrderAssignment",
        on_delete=models.PROTECT,
        related_name="ugc_rewards",
        null=True,
        blank=True,
        db_constraint=False,
    )
    assignment_version = models.PositiveIntegerField(default=0)
    evidence_type = models.CharField(max_length=24, choices=EvidenceType.choices)
    evidence_message = models.ForeignKey(
        "management.InstagramBotMessage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ugc_rewards",
        db_constraint=False,
    )
    evidence_url = models.URLField(max_length=500, blank=True, default="")
    evidence_fingerprint = models.CharField(max_length=64, unique=True)
    review_note = models.CharField(max_length=1000, blank=True, default="")
    promo_code = models.OneToOneField(
        "storefront.PromoCode",
        on_delete=models.PROTECT,
        related_name="instagram_ugc_reward",
        db_constraint=False,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="reviewed_ig_ugc_rewards",
        null=True,
        blank=True,
        # `auth_user` на проді — MyISAM, як і ще 204 таблиці цієї бази: рушій
        # InnoDB отримують лише нові таблиці. FK на MyISAM неможливий, і
        # міграція падала з errno 150 «Foreign key constraint is incorrectly
        # formed». Обмеження лишається на рівні ORM, як це вже зроблено для
        # `RestockSubscription.user` — тобто це прийнятий у проєкті спосіб, а не
        # виняток заради деплою.
        db_constraint=False,
    )
    reward_path = models.CharField(max_length=24, default="delivered_order", db_index=True)
    decision_source = models.CharField(max_length=16, default="manager")
    assessment = models.ForeignKey(
        "management.IgUgcEvidenceAssessment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rewards",
        db_constraint=False,
    )
    assessment_generation_snapshot = models.PositiveBigIntegerField(default=0)
    discount_percent = models.PositiveSmallIntegerField(default=10)
    policy_version_snapshot = models.CharField(max_length=32, blank=True, default="")
    provider_object_digest_snapshot = models.CharField(max_length=64, blank=True, default="")
    catalog_candidates_snapshot = models.JSONField(default=list, blank=True)
    lifecycle_state = models.CharField(
        max_length=16,
        choices=LifecycleState.choices,
        default=LifecycleState.ACTIVE,
        db_index=True,
    )
    lifecycle_reason = models.CharField(max_length=64, blank=True, default="")
    lifecycle_updated_at = models.DateTimeField(default=timezone.now, db_index=True)
    issued_at = models.DateTimeField(default=timezone.now, db_index=True)
    lifetime_slot_key = models.CharField(max_length=128, unique=True, null=True, blank=True)
    reviewed_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-reviewed_at", "-id"]
        indexes = [
            models.Index(fields=["client", "-reviewed_at"], name="ig_ugc_client_dt"),
            models.Index(fields=["assignment", "assignment_version"], name="ig_ugc_assign_ver"),
            models.Index(fields=["reward_path", "-issued_at"], name="ig_ugc_path_issued"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        reward_path="external_ugc",
                        order__isnull=True,
                        assignment__isnull=True,
                    )
                    | models.Q(
                        reward_path="delivered_order",
                        order__isnull=False,
                        assignment__isnull=False,
                    )
                ),
                name="ig_ugc_reward_path_refs",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(decision_source="auto", reviewed_by__isnull=True)
                    | models.Q(decision_source="manager", reviewed_by__isnull=False)
                ),
                name="ig_ugc_reward_source_reviewer",
            ),
        ]


class IgUgcEvidenceAssessment(models.Model):
    """Durable, provenance-bound UGC assessment with deterministic policy gates."""

    class Decision(models.TextChoices):
        PENDING = "pending", _("Очікує оцінки")
        QUALIFIED_AUTO = "qualified_auto", _("Автоматично підтверджено")
        NEEDS_MANAGER_REVIEW = "needs_manager_review", _("Потрібен менеджер")
        MANAGER_APPROVED = "manager_approved", _("Підтверджено менеджером")
        REJECTED = "rejected", _("Відхилено")

    client = models.ForeignKey(
        "management.IgClient",
        on_delete=models.SET_NULL,
        related_name="ugc_assessments",
        db_constraint=False,
        null=True,
        blank=True,
    )
    source_message_id = models.CharField(max_length=255, db_index=True)
    provider_object_key = models.CharField(max_length=255, blank=True, default="", db_index=True)
    provider_object_digest = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        unique=True,
    )
    provider_media_id = models.CharField(max_length=255, blank=True, default="")
    provider_event_id = models.CharField(max_length=255, blank=True, default="")
    target_username = models.CharField(max_length=80, blank=True, default="")
    evidence_fingerprint = models.CharField(max_length=128, db_index=True)
    perceptual_fingerprint = models.CharField(max_length=128, blank=True, default="", db_index=True)
    decision = models.CharField(max_length=24, choices=Decision.choices, default=Decision.PENDING, db_index=True)
    decision_source = models.CharField(max_length=16, default="policy")
    policy_version = models.CharField(max_length=32, default="ugc-v1")
    reason_codes = models.JSONField(default=list, blank=True)
    catalog_candidates = models.JSONField(default=list, blank=True)
    confidence = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    people_count = models.PositiveSmallIntegerField(default=0)
    garment_count = models.PositiveSmallIntegerField(default=0)
    reward_owner_client_id = models.PositiveBigIntegerField(null=True, blank=True)
    generation = models.PositiveBigIntegerField(default=1)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_ig_ugc_assessments",
        db_constraint=False,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    lease_token = models.CharField(max_length=64, blank=True, default="")
    lease_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["client", "source_message_id"],
                name="ig_ugc_assess_source_once",
            ),
        ]
        indexes = [
            models.Index(fields=["client", "-created_at"], name="ig_ugc_assess_client_dt"),
            models.Index(fields=["decision", "-created_at"], name="ig_ugc_assess_decision_dt"),
            models.Index(fields=["provider_object_key", "source_message_id"], name="ig_ugc_assess_provider"),
        ]


class IgUgcRewardLifetime(models.Model):
    """InnoDB identity slot that serializes all UGC reward paths per client."""

    client = models.OneToOneField(
        "management.IgClient",
        on_delete=models.SET_NULL,
        related_name="ugc_reward_lifetime",
        db_constraint=False,
        null=True,
        blank=True,
    )
    identity_digest = models.CharField(max_length=128, unique=True)
    reward = models.OneToOneField(
        "management.IgUgcReward",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="lifetime_slot",
        db_constraint=False,
    )
    # Privacy deletion may remove the reward/promo payload while the
    # irreversible lifetime grant remains represented by this digest.
    consumed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["client", "reward"], name="ig_ugc_life_client_reward")]


class IgUgcRewardDelivery(models.Model):
    """Receipt-backed outbox for the private UGC code message."""

    class State(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SENT = "sent", "Sent"
        WAITING_WINDOW = "waiting_window", "Waiting window"
        AMBIGUOUS = "ambiguous", "Ambiguous"
        FAILED = "failed", "Failed"

    reward = models.OneToOneField(
        "management.IgUgcReward",
        on_delete=models.PROTECT,
        related_name="delivery",
        db_constraint=False,
    )
    client = models.ForeignKey(
        "management.IgClient",
        on_delete=models.SET_NULL,
        related_name="ugc_reward_deliveries",
        db_constraint=False,
        null=True,
        blank=True,
    )
    message_snapshot = models.TextField()
    state = models.CharField(max_length=20, choices=State.choices, default=State.PENDING, db_index=True)
    due_at = models.DateTimeField(default=timezone.now, db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    lease_token = models.CharField(max_length=64, blank=True, default="")
    lease_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    provider_message_ids = models.JSONField(default=list, blank=True)
    last_error = models.CharField(max_length=500, blank=True, default="")
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_at", "id"]
        indexes = [
            models.Index(fields=["state", "due_at", "id"], name="ig_ugc_delivery_due"),
            models.Index(fields=["client", "-created_at"], name="ig_ugc_delivery_client"),
        ]


class IgUgcRewardLifecycleJob(models.Model):
    """Event-scoped retry queue for linked-order reward truth changes."""

    order_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)
    client_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)
    source = models.CharField(max_length=32, blank=True, default="")
    due_at = models.DateTimeField(default=timezone.now, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error_kind = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(order_id__isnull=False)
                    | models.Q(client_id__isnull=False)
                ),
                name="ig_ugc_life_job_target",
            ),
        ]
        indexes = [
            models.Index(
                fields=["due_at", "id"],
                name="ig_ugc_life_job_due",
            ),
        ]


class _IgOrderCustomerEventQuerySet(models.QuerySet):
    _IDENTITY_FIELDS = {
        "event_key",
        "assignment",
        "assignment_id",
        "assignment_version",
        "order",
        "order_id",
        "client",
        "client_id",
        "kind",
        "locale",
        "message_snapshot",
        "payload",
    }

    def update(self, **kwargs):
        if self._IDENTITY_FIELDS.intersection(kwargs):
            raise ValueError("IgOrderCustomerEvent identity is immutable")
        return super().update(**kwargs)

    def bulk_update(self, objs, fields, batch_size=None):
        if self._IDENTITY_FIELDS.intersection(fields):
            raise ValueError("IgOrderCustomerEvent identity is immutable")
        return super().bulk_update(objs, fields, batch_size=batch_size)

    def delete(self):
        raise ValueError("IgOrderCustomerEvent is durable")

    def _raw_delete(self, using):
        raise ValueError("IgOrderCustomerEvent is durable")


class IgOrderCustomerEvent(models.Model):
    """Durable localized customer message derived from current order ownership."""

    class Kind(models.TextChoices):
        TTN_ASSIGNED = "ttn_assigned", _("ТТН прив'язано")
        # An exchange replacement is not a second shipment of the order. The
        # generic text «Ваше замовлення відправлено» reads as a repeat and hides
        # the fact that this is the size the customer asked for.
        EXCHANGE_SHIPPED = "exchange_shipped", _("Заміну відправлено")
        # F-PAY-007: подтверждение оплаты клиенту не было детерминированным —
        # оно зависело от того, сгенерирует ли модель нужную фразу.
        PAYMENT_CONFIRMED = "payment_confirmed", _("Оплату підтверджено")
        DELIVERED_REVIEW = "delivered_review", _("Запит відгуку після отримання")

    class State(models.TextChoices):
        PENDING = "pending", _("Очікує")
        PROCESSING = "processing", _("Обробляється")
        SENT = "sent", _("Надіслано")
        WAITING_WINDOW = "waiting_window", _("Очікує вікна відповіді")
        MANAGER_REVIEW = "manager_review", _("Потрібен менеджер")
        AMBIGUOUS = "ambiguous", _("Невідомий результат")
        FAILED = "failed", _("Помилка")
        CANCELLED = "cancelled", _("Скасовано")

    event_key = models.CharField(max_length=180, unique=True)
    assignment = models.ForeignKey(
        "management.IgOrderAssignment",
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name="customer_events",
    )
    assignment_version = models.PositiveIntegerField()
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name="instagram_customer_events",
    )
    client = models.ForeignKey(
        "management.IgClient",
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name="order_customer_events",
    )
    kind = models.CharField(max_length=32, choices=Kind.choices, db_index=True)
    locale = models.CharField(max_length=12, default="uk")
    message_snapshot = models.TextField()
    payload = models.JSONField(default=dict, blank=True)
    state = models.CharField(max_length=24, choices=State.choices, default=State.PENDING, db_index=True)
    due_at = models.DateTimeField(default=timezone.now, db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    lease_token = models.CharField(max_length=64, blank=True, default="")
    lease_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    provider_message_id = models.CharField(max_length=255, blank=True, default="")
    delivery_provider_message_ids = models.JSONField(default=list, blank=True)
    last_error = models.CharField(max_length=1000, blank=True, default="")
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_at", "id"]
        indexes = [
            models.Index(fields=["state", "due_at", "id"], name="ig_order_evt_state_due"),
            models.Index(fields=["client", "-created_at"], name="ig_order_evt_client_dt"),
            models.Index(fields=["order", "kind"], name="ig_order_evt_kind"),
        ]

    objects = models.Manager.from_queryset(_IgOrderCustomerEventQuerySet)()

    _IDENTITY_FIELDS = (
        "event_key",
        "kind",
        "assignment_id",
        "assignment_version",
        "order_id",
        "client_id",
        "locale",
        "message_snapshot",
        "payload",
    )

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values(*self._IDENTITY_FIELDS).first()
            if previous:
                for field_name in self._IDENTITY_FIELDS:
                    if getattr(self, field_name) != previous[field_name]:
                        raise ValueError("IgOrderCustomerEvent identity is immutable")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("IgOrderCustomerEvent is durable")


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


def default_checkout_proposal_expiry():
    return timezone.now() + timedelta(minutes=25)


class IgCheckoutProposalQuerySet(models.QuerySet):
    _PROTECTED_UPDATE_FIELDS = {
        "client",
        "client_id",
        "deal",
        "deal_id",
        "commercial_episode",
        "commercial_episode_id",
        "status",
        "revision",
        "catalog_total",
        "negotiated_discount",
        "quoted_total",
        "requested_payment_amount",
        "currency",
        "pay_type",
        "allow_promo",
        "items_digest",
        "expires_at",
        "details_locked_at",
        "invoice_cancelled_at",
        "provider_cancellation_event",
        "provider_cancellation_event_id",
        "paid_at",
        "payment_attempt",
        "payment_attempt_id",
        "superseded_by",
        "superseded_by_id",
    }

    def update(self, **kwargs):
        if self._PROTECTED_UPDATE_FIELDS.intersection(kwargs):
            raise ValueError(
                "Instagram checkout proposal state requires a locked transition service"
            )
        return super().update(**kwargs)

    def delete(self):
        raise ValueError("IgCheckoutProposal financial evidence cannot be deleted")


class IgCheckoutProposalManager(models.Manager.from_queryset(IgCheckoutProposalQuerySet)):
    def _proposal_values(self, *, deal, **values):
        from management.services.ig_commercial_episodes import ensure_episode_for_deal

        episode = ensure_episode_for_deal(deal)
        values.setdefault("client", deal.client)
        values.setdefault("commercial_episode", episode)
        values.setdefault("expires_at", default_checkout_proposal_expiry())
        values.setdefault("catalog_total", values.get("quoted_total"))
        values.setdefault(
            "requested_payment_amount",
            values.get("quoted_total"),
        )
        values.setdefault("negotiated_discount", Decimal("0.00"))
        values.setdefault("revision", 1)
        return values

    @transaction.atomic
    def create_current(self, *, deal, **values):
        deal = (
            IgDeal.objects.select_for_update()
            .select_related("client", "active_checkout_proposal")
            .get(pk=deal.pk)
        )
        if deal.active_checkout_proposal_id:
            raise ValidationError("Deal already has a current proposal")
        values = self._proposal_values(deal=deal, **values)
        proposal = self.model(deal=deal, **values)
        proposal.full_clean()
        proposal.save(force_insert=True)
        deal.active_checkout_proposal = proposal
        deal.save(update_fields=["active_checkout_proposal", "updated_at"])
        return proposal

    @transaction.atomic
    def replace_current(self, *, deal, **values):
        deal = (
            IgDeal.objects.select_for_update()
            .select_related("client", "active_checkout_proposal")
            .get(pk=deal.pk)
        )
        current = deal.active_checkout_proposal
        if current is None:
            raise ValidationError("Deal has no current proposal to replace")
        current = self.select_for_update().get(pk=current.pk)
        if current.status == current.Status.PAID:
            raise ValidationError("A paid proposal cannot be superseded")
        if current.status == current.Status.INVOICE_CREATED:
            raise ValidationError("A payable or ambiguous invoice cannot be replaced")
        attempt = None
        event = None
        projection = None
        if current.payment_attempt_id:
            from orders.models import PaymentAttempt

            attempt = PaymentAttempt.objects.select_for_update().get(
                pk=current.payment_attempt_id
            )
        if current.provider_cancellation_event_id:
            event = IgPaymentEvent.objects.select_for_update().get(
                pk=current.provider_cancellation_event_id
            )
            projection = (
                IgPaymentProjection.objects.select_for_update()
                .filter(deal_id=deal.pk)
                .first()
            )
        if not current.has_provider_confirmed_cancellation(
            attempt=attempt,
            event=event,
            projection=projection,
        ):
            raise ValidationError("The current proposal is not provider-confirmed cancelled")

        values = self._proposal_values(deal=deal, **values)
        replacement = self.model(deal=deal, **values)
        replacement.full_clean()
        replacement.save(force_insert=True)

        current.status = current.Status.SUPERSEDED
        current.superseded_by = replacement
        current.save(update_fields=["status", "superseded_by", "updated_at"])
        deal.active_checkout_proposal = replacement
        deal.save(update_fields=["active_checkout_proposal", "updated_at"])
        return replacement


class IgCheckoutProposal(models.Model):
    """Frozen first-party checkout offer created from an Instagram deal."""

    class Status(models.TextChoices):
        READY = "ready", _("Готова")
        VIEWED = "viewed", _("Переглянута")
        DETAILS_LOCKED = "details_locked", _("Дані зафіксовані")
        INVOICE_CREATED = "invoice_created", _("Рахунок створено")
        MANAGER_REVIEW = "manager_review", _("Потрібна перевірка менеджера")
        PAID = "paid", _("Оплачено")
        CANCELLED = "cancelled", _("Рахунок скасовано")
        EXPIRED = "expired", _("Протерміновано")
        REVOKED = "revoked", _("Відкликано")
        SUPERSEDED = "superseded", _("Замінено")

    class PayType(models.TextChoices):
        ONLINE_FULL = "online_full", _("Повна онлайн-оплата")
        PREPAYMENT = "prepayment", _("Передоплата")

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    client = models.ForeignKey(
        "management.IgClient",
        on_delete=models.PROTECT,
        related_name="checkout_proposals",
    )
    deal = models.ForeignKey(
        "management.IgDeal",
        on_delete=models.PROTECT,
        related_name="checkout_proposals",
    )
    commercial_episode = models.ForeignKey(
        "management.IgCommercialEpisode",
        on_delete=models.PROTECT,
        related_name="checkout_proposals",
    )
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.READY,
        db_index=True,
    )
    revision = models.PositiveIntegerField(default=1)
    locale = models.CharField(max_length=12, default="uk")
    currency = models.CharField(max_length=8, default="UAH")
    catalog_total = models.DecimalField(max_digits=12, decimal_places=2)
    negotiated_discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    quoted_total = models.DecimalField(max_digits=12, decimal_places=2)
    requested_payment_amount = models.DecimalField(max_digits=12, decimal_places=2)
    pay_type = models.CharField(
        max_length=20,
        choices=PayType.choices,
        default=PayType.ONLINE_FULL,
    )
    allow_promo = models.BooleanField(default=False)
    items_digest = models.CharField(max_length=64)
    expires_at = models.DateTimeField(default=default_checkout_proposal_expiry, db_index=True)
    viewed_at = models.DateTimeField(null=True, blank=True)
    details_locked_at = models.DateTimeField(null=True, blank=True)
    invoice_cancelled_at = models.DateTimeField(null=True, blank=True)
    provider_cancellation_event = models.ForeignKey(
        "management.IgPaymentEvent",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="cancelled_checkout_proposals",
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    payment_attempt = models.OneToOneField(
        "orders.PaymentAttempt",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="instagram_checkout_proposal",
    )
    superseded_by = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="supersedes",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = IgCheckoutProposalManager()

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["status", "expires_at"], name="ig_prop_status_exp"),
            models.Index(fields=["client", "-created_at"], name="ig_prop_client_dt"),
            models.Index(fields=["deal", "-created_at"], name="ig_prop_deal_dt"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(catalog_total__gt=0),
                name="ig_prop_catalog_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(quoted_total__gt=0),
                name="ig_prop_quoted_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(requested_payment_amount__gt=0),
                name="ig_prop_payment_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(negotiated_discount__gte=0),
                name="ig_prop_discount_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(revision__gte=1),
                name="ig_prop_revision_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status="superseded", superseded_by__isnull=False)
                    | ~models.Q(status="superseded")
                ),
                name="ig_prop_superseded_link",
            ),
            models.CheckConstraint(
                condition=~models.Q(status="paid", superseded_by__isnull=False),
                name="ig_prop_paid_not_superseded",
            ),
        ]

    def __str__(self):  # pragma: no cover - trivial representation
        return f"IgCheckoutProposal#{self.pk} deal={self.deal_id} {self.status}"

    @property
    def is_expired(self):
        return self.expires_at <= timezone.now()

    def has_provider_confirmed_cancellation(
        self,
        *,
        attempt=None,
        event=None,
        projection=None,
    ):
        if self.status != self.Status.CANCELLED or not self.invoice_cancelled_at:
            return False
        attempt = attempt or self.payment_attempt
        event = event or self.provider_cancellation_event
        if attempt is None or attempt.order_id or self.deal.order_id:
            return False
        if event is None:
            return False
        if event.deal_id != self.deal_id or event.client_id != self.client_id:
            return False
        invoice_id = str(attempt.monobank_invoice_id or "").strip()
        status = str(event.provider_status or "").strip().lower()
        if not invoice_id or event.provider != "monobank":
            return False
        if str(event.invoice_id or "").strip() != invoice_id:
            return False
        if str(event.source or "").strip().lower() not in {
            "provider",
            "provider_pull",
            "provider_webhook",
            "signed_webhook",
            "webhook",
            "poll",
        }:
            return False
        from secrets import compare_digest

        expected_signature = provider_evidence_signature(
            deal_id=self.deal_id,
            client_id=self.client_id,
            provider=event.provider,
            source=event.source,
            invoice_id=event.invoice_id,
            provider_status=event.provider_status,
            payload_digest=event.payload_digest,
        )
        if not compare_digest(
            str((event.evidence or {}).get("signature") or ""),
            expected_signature,
        ):
            return False
        expected_attempt_status = {
            "cancelled": attempt.Status.CANCELLED,
            "canceled": attempt.Status.CANCELLED,
            "expired": attempt.Status.EXPIRED,
            "failure": attempt.Status.FAILED,
            "rejected": attempt.Status.FAILED,
        }.get(status)
        if expected_attempt_status is None or attempt.status != expected_attempt_status:
            return False
        projection = projection
        if projection is None:
            try:
                projection = self.deal.payment_projection
            except IgPaymentProjection.DoesNotExist:
                return False
        expected_truth = (
            self.deal.PaymentTruth.CANCELLED
            if expected_attempt_status in {attempt.Status.CANCELLED, attempt.Status.EXPIRED}
            else self.deal.PaymentTruth.FAILED
        )
        return (
            projection.last_event_id == event.pk
            and projection.truth == expected_truth
        )

    def clean(self):
        errors = {}
        if self.deal_id and self.client_id and self.deal.client_id != self.client_id:
            errors["client"] = "Proposal client must own the deal"
        if self.commercial_episode_id:
            episode = self.commercial_episode
            if self.client_id and episode.client_id != self.client_id:
                errors["commercial_episode"] = "Episode must belong to the proposal client"
            if episode.deal_id and self.deal_id and episode.deal_id != self.deal_id:
                errors["commercial_episode"] = "Episode must be bound to the proposal deal"
        if self.quoted_total is not None and self.quoted_total <= 0:
            errors["quoted_total"] = "Active proposal total must be positive"
        if self.catalog_total is not None and self.catalog_total <= 0:
            errors["catalog_total"] = "Catalog total must be positive"
        if (
            self.requested_payment_amount is not None
            and self.quoted_total is not None
            and (
                self.requested_payment_amount <= 0
                or self.requested_payment_amount > self.quoted_total
            )
        ):
            errors["requested_payment_amount"] = "Requested payment must fit the quote"
        if self._state.adding and self.status in {
            self.Status.READY,
            self.Status.VIEWED,
        } and self.expires_at <= timezone.now():
            errors["expires_at"] = "Active proposal expiry must be in the future"
        if self.status == self.Status.PAID and self.superseded_by_id:
            errors["superseded_by"] = "A paid proposal cannot be superseded"
        if self.status == self.Status.SUPERSEDED and not self.superseded_by_id:
            errors["superseded_by"] = "Superseded proposal must point to its replacement"
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values(
                "client_id",
                "deal_id",
                "commercial_episode_id",
                "status",
                "revision",
                "catalog_total",
                "negotiated_discount",
                "quoted_total",
                "requested_payment_amount",
                "currency",
                "pay_type",
                "allow_promo",
                "items_digest",
                "expires_at",
                "details_locked_at",
                "invoice_cancelled_at",
                "provider_cancellation_event_id",
                "paid_at",
                "payment_attempt_id",
                "superseded_by_id",
            ).first()
            if previous:
                if previous["status"] == self.Status.PAID:
                    protected = {
                        field: getattr(self, field)
                        for field in (
                            "client_id", "deal_id", "commercial_episode_id", "revision",
                            "catalog_total", "negotiated_discount", "quoted_total",
                            "requested_payment_amount", "currency", "pay_type", "allow_promo",
                            "items_digest", "expires_at", "details_locked_at",
                            "invoice_cancelled_at", "provider_cancellation_event_id",
                            "paid_at", "payment_attempt_id", "superseded_by_id",
                        )
                    }
                    if any(protected[field] != previous[field] for field in protected):
                        raise ValidationError("A paid proposal financial/state record is immutable")
                if previous["status"] == self.Status.PAID and self.status != self.Status.PAID:
                    raise ValidationError("A paid proposal cannot be superseded")
                if previous["status"] != self.Status.PAID and self.status == self.Status.PAID:
                    if not self.paid_at or not self.payment_attempt_id:
                        raise ValidationError("A proposal can be paid only after verified payment")
                    from orders.models import PaymentAttempt

                    attempt = PaymentAttempt.objects.filter(pk=self.payment_attempt_id).first()
                    if not attempt or attempt.status != PaymentAttempt.Status.CONVERTED or not attempt.order_id:
                        raise ValidationError("A proposal can be paid only after verified payment")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("IgCheckoutProposal financial evidence cannot be deleted")


class IgCheckoutProposalItem(models.Model):
    proposal = models.ForeignKey(
        "management.IgCheckoutProposal",
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        "storefront.Product",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="instagram_checkout_items",
        db_constraint=False,
    )
    color_variant = models.ForeignKey(
        "productcolors.ProductColorVariant",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="instagram_checkout_items",
        db_constraint=False,
    )
    product_title = models.CharField(max_length=255)
    sku = models.CharField(max_length=128, blank=True, default="")
    image_url = models.CharField(max_length=600, blank=True, default="")
    color_code = models.CharField(max_length=64, blank=True, default="")
    color_label = models.CharField(max_length=100, blank=True, default="")
    size = models.CharField(max_length=32, blank=True, default="")
    fit_code = models.CharField(max_length=64, blank=True, default="")
    fit_label = models.CharField(max_length=100, blank=True, default="")
    option_values = models.JSONField(default=dict, blank=True)
    option_labels = models.JSONField(default=dict, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    catalog_unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    catalog_line_total = models.DecimalField(max_digits=12, decimal_places=2)
    quoted_unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quoted_line_total = models.DecimalField(max_digits=12, decimal_places=2)
    price_source = models.CharField(max_length=64, blank=True, default="catalog")
    evidence_message_ids = models.JSONField(default=list, blank=True)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["proposal", "position"],
                name="ig_prop_item_position_once",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="ig_prop_item_qty_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(catalog_unit_price__gte=0)
                & models.Q(quoted_unit_price__gte=0),
                name="ig_prop_item_prices_nonneg",
            ),
        ]


class _AppendOnlyCheckoutRevisionQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValueError("IgCheckoutRevision is append-only")

    def delete(self):
        raise ValueError("IgCheckoutRevision is append-only")


class IgCheckoutRevision(models.Model):
    class Source(models.TextChoices):
        BOT_CREATE = "bot_create", _("Створено ботом")
        BOT_UPDATE = "bot_update", _("Оновлено ботом")
        SYSTEM_SUPERSEDE = "system_supersede", _("Системна заміна")

    proposal = models.ForeignKey(
        "management.IgCheckoutProposal",
        on_delete=models.CASCADE,
        related_name="revisions",
    )
    revision = models.PositiveIntegerField()
    digest = models.CharField(max_length=64)
    snapshot = models.JSONField(default=dict)
    source = models.CharField(max_length=24, choices=Source.choices)
    evidence_message_ids = models.JSONField(default=list, blank=True)
    source_watermark_message_id = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = models.Manager.from_queryset(_AppendOnlyCheckoutRevisionQuerySet)()

    class Meta:
        ordering = ["proposal", "revision"]
        constraints = [
            models.UniqueConstraint(
                fields=["proposal", "revision"],
                name="ig_prop_revision_once",
            ),
            models.CheckConstraint(
                condition=models.Q(revision__gte=1),
                name="ig_prop_revision_num_pos",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk and not kwargs.get("force_insert"):
            raise ValueError("IgCheckoutRevision is append-only")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("IgCheckoutRevision is append-only")


class IgCheckoutAccessToken(models.Model):
    class Kind(models.TextChoices):
        BOT = "bot", _("Посилання бота")
        SHARE = "share", _("Посилання для оплати іншою людиною")
        REPLACEMENT = "replacement", _("Посилання заміни")

    proposal = models.ForeignKey(
        "management.IgCheckoutProposal",
        on_delete=models.CASCADE,
        related_name="access_tokens",
    )
    token_digest = models.CharField(max_length=64, unique=True)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.BOT)
    expires_at = models.DateTimeField(db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    use_count = models.PositiveIntegerField(default=0)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["proposal", "kind", "expires_at"], name="ig_token_prop_exp"),
        ]

    @classmethod
    def issue(cls, *, proposal, kind=Kind.BOT, expires_at=None):
        raw_token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        token = cls.objects.create(
            proposal=proposal,
            token_digest=digest,
            kind=kind,
            expires_at=min(expires_at or proposal.expires_at, proposal.expires_at),
        )
        return raw_token, token

    @classmethod
    def digest(cls, raw_token):
        return hashlib.sha256(str(raw_token or "").encode("utf-8")).hexdigest()


class IgCheckoutInventoryReservation(models.Model):
    class State(models.TextChoices):
        ACTIVE = "active", _("Зарезервовано")
        PAID_COMMITTED = "paid_committed", _("Оплата підтверджена")
        FULFILLED = "fulfilled", _("Виконано")
        RELEASED = "released", _("Звільнено")
        OVERBOOKED_REVIEW = "overbooked_review", _("Потрібна перевірка дефіциту")
        # Kept for rows written by the pre-allocation implementation. New
        # payment paths use FULFILLED; the lifecycle migration normalizes old
        # consumed rows where it can prove a catalog allocation.
        CONSUMED = "consumed", _("Використано")

    proposal = models.ForeignKey(
        "management.IgCheckoutProposal",
        on_delete=models.PROTECT,
        related_name="inventory_reservations",
    )
    item = models.ForeignKey(
        "management.IgCheckoutProposalItem",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="inventory_reservations",
    )
    product = models.ForeignKey(
        "storefront.Product",
        on_delete=models.PROTECT,
        related_name="instagram_checkout_reservations",
        db_constraint=False,
    )
    color_variant = models.ForeignKey(
        "productcolors.ProductColorVariant",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="instagram_checkout_reservations",
        db_constraint=False,
    )
    allocation_source = models.CharField(max_length=24, default="catalog_variant")
    stock_item = models.ForeignKey(
        "warehouse.StockItem",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="instagram_checkout_reservations",
        db_constraint=False,
    )
    allocation_key = models.CharField(max_length=128, blank=True, default="")
    line_ids = models.JSONField(default=list, blank=True)
    order = models.ForeignKey(
        "orders.Order",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="instagram_inventory_reservations",
        db_constraint=False,
    )
    order_item = models.ForeignKey(
        "orders.OrderItem",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="instagram_inventory_reservations",
        db_constraint=False,
    )
    write_off_request = models.ForeignKey(
        "warehouse.WriteOffRequest",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="instagram_inventory_reservations",
        db_constraint=False,
    )
    stock_movement = models.OneToOneField(
        "warehouse.StockMovement",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="instagram_inventory_reservation",
        db_constraint=False,
    )
    quantity = models.PositiveIntegerField()
    reservation_fingerprint = models.CharField(max_length=64, unique=True)
    state = models.CharField(
        max_length=24,
        choices=State.choices,
        default=State.ACTIVE,
        db_index=True,
    )
    expires_at = models.DateTimeField(db_index=True)
    released_at = models.DateTimeField(null=True, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    paid_committed_at = models.DateTimeField(null=True, blank=True)
    fulfilled_at = models.DateTimeField(null=True, blank=True)
    release_reason = models.CharField(max_length=128, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["state", "expires_at"], name="ig_res_state_exp"),
            models.Index(fields=["proposal", "state"], name="ig_res_prop_state"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="ig_res_qty_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(allocation_source="warehouse", stock_item__isnull=False)
                    | models.Q(allocation_source="catalog_variant")
                    | models.Q(allocation_source="untracked")
                ),
                name="ig_res_allocation_source_valid",
            ),
        ]


class _IgLifecycleEventQuerySet(models.QuerySet):
    _IDENTITY_FIELDS = {
        "event_key",
        "kind",
        "client",
        "client_id",
        "deal",
        "deal_id",
        "proposal",
        "proposal_id",
        "order",
        "order_id",
        "commercial_episode",
        "commercial_episode_id",
        "attribution",
        "attribution_id",
        "locale",
        "payload",
        "final_text",
    }

    def update(self, **kwargs):
        if self._IDENTITY_FIELDS.intersection(kwargs):
            raise ValueError("IgLifecycleEvent identity is immutable")
        return super().update(**kwargs)

    def delete(self):
        raise ValueError("IgLifecycleEvent is durable")


class IgLifecycleEvent(models.Model):
    class Kind(models.TextChoices):
        PAYMENT_VERIFIED = "payment_verified", _("Оплату підтверджено")
        TTN_CREATED = "ttn_created", _("ТТН створено")
        # Код 7 Нової Пошти — «прибуло у відділення». До цього між «ТТН створено»
        # і «отримано» у бота не було жодної події, хоча незабрана посилка — це
        # прямий збиток: зворотна доставка плюс замерзлий товар плюс майже
        # гарантована втрата повторної продажі, а для наложки ще й втрата виручки.
        PARCEL_ARRIVED = "parcel_arrived", _("Посилка у відділенні")
        DELIVERED_REVIEW_REQUESTED = (
            "delivered_review_requested",
            _("Замовлення отримано, запит відгуку"),
        )

    class State(models.TextChoices):
        PENDING = "pending", _("Очікує")
        PROCESSING = "processing", _("Обробляється")
        SENT = "sent", _("Надіслано")
        WAITING_WINDOW = "waiting_window", _("Поза вікном відповіді")
        MANAGER_REVIEW = "manager_review", _("Потрібен менеджер")
        AMBIGUOUS = "ambiguous", _("Невідомий результат")
        FAILED = "failed", _("Помилка")
        CANCELLED = "cancelled", _("Скасовано")

    event_key = models.CharField(max_length=180, unique=True)
    kind = models.CharField(max_length=40, choices=Kind.choices, db_index=True)
    client = models.ForeignKey(
        "management.IgClient",
        on_delete=models.PROTECT,
        related_name="lifecycle_events",
    )
    deal = models.ForeignKey(
        "management.IgDeal",
        on_delete=models.PROTECT,
        related_name="lifecycle_events",
    )
    proposal = models.ForeignKey(
        "management.IgCheckoutProposal",
        on_delete=models.PROTECT,
        related_name="lifecycle_events",
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="instagram_lifecycle_events",
    )
    commercial_episode = models.ForeignKey(
        "management.IgCommercialEpisode",
        on_delete=models.PROTECT,
        related_name="lifecycle_events",
    )
    attribution = models.ForeignKey(
        "management.IgOrderAttribution",
        on_delete=models.PROTECT,
        related_name="lifecycle_events",
    )
    locale = models.CharField(max_length=12, default="uk")
    payload = models.JSONField(default=dict, blank=True)
    # Optional follow copy is materialized exactly once immediately before
    # provider I/O. It is deliberately separate from the immutable business
    # payload so retries cannot rewrite payment evidence or message identity.
    final_text = models.TextField(blank=True, default="")
    state = models.CharField(
        max_length=24,
        choices=State.choices,
        default=State.PENDING,
        db_index=True,
    )
    due_at = models.DateTimeField(default=timezone.now, db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    lease_token = models.CharField(max_length=64, blank=True, default="")
    lease_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    provider_message_id = models.CharField(max_length=128, blank=True, default="")
    last_error = models.CharField(max_length=1000, blank=True, default="")
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager.from_queryset(_IgLifecycleEventQuerySet)()

    class Meta:
        ordering = ["due_at", "id"]
        indexes = [
            models.Index(fields=["state", "due_at", "id"], name="ig_life_state_due"),
            models.Index(fields=["client", "-created_at"], name="ig_life_client_dt"),
            models.Index(fields=["order", "kind"], name="ig_life_order_kind"),
        ]

    def clean(self):
        errors = {}
        if self.deal_id and self.client_id and self.deal.client_id != self.client_id:
            errors["deal"] = "Lifecycle deal must belong to the client"
        if self.proposal_id:
            if self.proposal.client_id != self.client_id:
                errors["proposal"] = "Lifecycle proposal must belong to the client"
            if self.proposal.deal_id != self.deal_id:
                errors["proposal"] = "Lifecycle proposal must belong to the deal"
            if self.proposal.commercial_episode_id != self.commercial_episode_id:
                errors["commercial_episode"] = "Lifecycle episode must match proposal"
            if not self.proposal.payment_attempt_id:
                errors["proposal"] = "Lifecycle proposal requires a payment attempt"
            elif self.proposal.payment_attempt.order_id != self.order_id:
                errors["order"] = "Lifecycle order must match proposal payment attempt"
        if not self.order_id:
            errors["order"] = "Lifecycle event requires an order"
        if not self.attribution_id:
            errors["attribution"] = "Lifecycle event requires exact attribution"
        if self.attribution_id and self.order_id:
            if self.attribution.order_id != self.order_id:
                errors["attribution"] = "Attribution must belong to the lifecycle order"
            if self.attribution.client_id != self.client_id:
                errors["attribution"] = "Attribution must belong to the lifecycle client"
            if self.attribution.deal_id != self.deal_id:
                errors["attribution"] = "Attribution must belong to the lifecycle deal"
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values(
                "event_key",
                "kind",
                "client_id",
                "deal_id",
                "proposal_id",
                "order_id",
                "commercial_episode_id",
                "attribution_id",
                "locale",
                "payload",
                "final_text",
            ).first()
            if previous:
                for field_name in (
                    "event_key",
                    "kind",
                    "client_id",
                    "deal_id",
                    "proposal_id",
                    "order_id",
                    "commercial_episode_id",
                    "attribution_id",
                    "locale",
                    "payload",
                ):
                    if getattr(self, field_name) != previous[field_name]:
                        raise ValidationError("IgLifecycleEvent identity is immutable")
                previous_final_text = previous.get("final_text", "")
                if previous_final_text and self.final_text != previous_final_text:
                    raise ValidationError("IgLifecycleEvent final_text is immutable")
        # Leave uniqueness enforcement to the database so duplicate event
        # delivery raises IntegrityError and remains transaction-safe.
        self.full_clean(validate_unique=False)
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("IgLifecycleEvent is durable")


class IgFollowCapabilityState(models.Model):
    """Provider-wide capability and circuit state for follow lookups."""

    class Status(models.TextChoices):
        UNKNOWN = "unknown", _("Невідомо")
        AVAILABLE = "available", _("Доступно")
        DEGRADED = "degraded", _("Тимчасово недоступно")
        BLOCKED = "blocked", _("Заблоковано політикою Meta")

    singleton_key = models.PositiveSmallIntegerField(default=1, unique=True)
    transport = models.CharField(max_length=32, blank=True, default="")
    graph_version = models.CharField(max_length=16, blank=True, default="")
    ig_user_id = models.CharField(max_length=64, blank=True, default="")
    config_fingerprint = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.UNKNOWN,
        db_index=True,
    )
    checked_at = models.DateTimeField(null=True, blank=True)
    next_probe_at = models.DateTimeField(null=True, blank=True, db_index=True)
    blocked_until = models.DateTimeField(null=True, blank=True, db_index=True)
    consecutive_failures = models.PositiveIntegerField(default=0)
    last_error_kind = models.CharField(max_length=32, blank=True, default="")
    last_error_code = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(singleton_key=1),
                name="ig_follow_cap_singleton_one",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "next_probe_at"],
                name="ig_follow_cap_status",
            ),
        ]

    def is_probe_blocked(self, *, now=None) -> bool:
        now = now or timezone.now()
        return bool(
            (self.blocked_until and self.blocked_until > now)
            or (self.next_probe_at and self.next_probe_at > now)
        )


class IgFollowState(models.Model):
    """Latest authoritative follow observation for one Instagram client."""

    class State(models.TextChoices):
        UNKNOWN = "unknown", _("Невідомо")
        FOLLOWING = "following", _("Підписаний")
        NOT_FOLLOWING = "not_following", _("Не підписаний")

    class CheckResult(models.TextChoices):
        NEVER = "never", _("Не перевірялось")
        KNOWN = "known", _("Отримано")
        ERROR = "error", _("Помилка")
        SKIPPED = "skipped", _("Пропущено політикою")

    client = models.OneToOneField(
        "management.IgClient",
        on_delete=models.DO_NOTHING,
        related_name="follow_state_projection",
        db_constraint=False,
    )
    state = models.CharField(
        max_length=16,
        choices=State.choices,
        default=State.UNKNOWN,
        db_index=True,
    )
    revision = models.PositiveBigIntegerField(default=0)
    source = models.CharField(max_length=32, blank=True, default="")
    graph_version = models.CharField(max_length=16, blank=True, default="")
    config_fingerprint = models.CharField(max_length=64, blank=True, default="")
    observed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    first_observed_following_at = models.DateTimeField(null=True, blank=True)
    last_check_at = models.DateTimeField(null=True, blank=True)
    last_result = models.CharField(
        max_length=16,
        choices=CheckResult.choices,
        default=CheckResult.NEVER,
    )
    consecutive_failures = models.PositiveIntegerField(default=0)
    last_error_kind = models.CharField(max_length=32, blank=True, default="")
    last_error_code = models.CharField(max_length=64, blank=True, default="")
    next_retry_at = models.DateTimeField(null=True, blank=True, db_index=True)
    refresh_generation = models.PositiveBigIntegerField(default=0)
    refresh_lease_token = models.CharField(max_length=64, blank=True, default="")
    refresh_lease_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_cta_touch_at = models.DateTimeField(null=True, blank=True, db_index=True)
    cta_refused_at = models.DateTimeField(null=True, blank=True)
    cta_refusal_message_id = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["state", "expires_at"],
                name="ig_follow_state_fresh",
            ),
            models.Index(
                fields=["next_retry_at", "client"],
                name="ig_follow_state_retry",
            ),
        ]


class _AppendOnlyFollowObservationQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValueError("IgFollowObservation is append-only")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValueError("IgFollowObservation is append-only")

    def delete(self):
        raise ValueError("IgFollowObservation is append-only")

    def _raw_delete(self, using):
        raise ValueError("IgFollowObservation is append-only")


class IgFollowObservation(models.Model):
    """Append-only, token-free evidence returned by the Meta follow endpoint."""

    class Result(models.TextChoices):
        KNOWN = "known", _("Отримано")
        ERROR = "error", _("Помилка")
        SKIPPED = "skipped", _("Пропущено")

    client = models.ForeignKey(
        "management.IgClient",
        on_delete=models.DO_NOTHING,
        related_name="follow_observations",
        db_constraint=False,
    )
    revision = models.PositiveBigIntegerField(default=0)
    trigger = models.CharField(max_length=32)
    result = models.CharField(max_length=16, choices=Result.choices, db_index=True)
    observed_value = models.BooleanField(null=True, blank=True)
    field_present = models.BooleanField(default=False)
    field_type = models.CharField(max_length=24, blank=True, default="")
    transport = models.CharField(max_length=32, blank=True, default="")
    graph_version = models.CharField(max_length=16, blank=True, default="")
    config_fingerprint = models.CharField(max_length=64)
    http_code = models.PositiveSmallIntegerField(null=True, blank=True)
    graph_code = models.PositiveIntegerField(null=True, blank=True)
    graph_subcode = models.PositiveIntegerField(null=True, blank=True)
    error_kind = models.CharField(max_length=32, blank=True, default="")
    error_code = models.CharField(max_length=64, blank=True, default="")
    duration_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = models.Manager.from_queryset(_AppendOnlyFollowObservationQuerySet)()

    class Meta:
        ordering = ["-id"]
        indexes = [
            models.Index(
                fields=["client", "-created_at"],
                name="ig_follow_obs_client_dt",
            ),
            models.Index(
                fields=["result", "-created_at"],
                name="ig_follow_obs_result_dt",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk and not kwargs.get("force_insert"):
            raise ValueError("IgFollowObservation is append-only")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("IgFollowObservation is append-only")


class IgFollowRefreshJob(models.Model):
    """One coalescing, lease-backed follow lookup request per client."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Очікує")
        PROCESSING = "processing", _("Обробляється")
        DONE = "done", _("Завершено")
        FAILED = "failed", _("Помилка")

    client = models.OneToOneField(
        "management.IgClient",
        on_delete=models.DO_NOTHING,
        related_name="follow_refresh_job",
        db_constraint=False,
    )
    requested_generation = models.PositiveBigIntegerField(default=0)
    claimed_generation = models.PositiveBigIntegerField(default=0)
    triggers = models.JSONField(default=list, blank=True)
    expected_config_fingerprint = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    due_at = models.DateTimeField(default=timezone.now, db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    lease_token = models.CharField(max_length=64, blank=True, default="")
    lease_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_error_kind = models.CharField(max_length=32, blank=True, default="")
    last_error_code = models.CharField(max_length=64, blank=True, default="")
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["status", "due_at", "id"],
                name="ig_follow_job_due",
            ),
        ]


class _IgFollowCtaDecisionQuerySet(models.QuerySet):
    _IDENTITY_FIELDS = {
        "trigger_key",
        "client",
        "client_id",
        "opportunity",
        "commercial_episode",
        "commercial_episode_id",
        "order",
        "order_id",
        "lifecycle_event",
        "lifecycle_event_id",
        "source_message",
        "source_message_id",
        "follow_state_revision",
        "conversation_watermark",
        "context_fingerprint",
        "base_text",
    }

    def update(self, **kwargs):
        if self._IDENTITY_FIELDS.intersection(kwargs):
            raise ValueError("IgFollowCtaDecision identity is immutable")
        return super().update(**kwargs)

    def bulk_update(self, objs, fields, batch_size=None):
        if self._IDENTITY_FIELDS.intersection(fields):
            raise ValueError("IgFollowCtaDecision identity is immutable")
        return super().bulk_update(objs, fields, batch_size=batch_size)

    def delete(self):
        raise ValueError("IgFollowCtaDecision is durable")

    def _raw_delete(self, using):
        raise ValueError("IgFollowCtaDecision is durable")


class IgFollowCtaDecision(models.Model):
    """Durable optional follow CTA decision and provider delivery outcome."""

    class Opportunity(models.TextChoices):
        PAYMENT = "payment", _("Підтвердження оплати")
        HESITATION = "hesitation", _("М'яке вагання")
        POST_DELIVERY = "post_delivery", _("Після позитивної відповіді")

    class State(models.TextChoices):
        SUPPRESSED = "suppressed", _("Заборонено політикою")
        WAITING_FOLLOW = "waiting_follow", _("Очікує перевірки підписки")
        PREPARING = "preparing", _("Готується")
        PREPARED = "prepared", _("Підготовлено")
        RESERVED = "reserved", _("Зарезервовано до відправлення")
        SENT = "sent", _("Надіслано")
        AMBIGUOUS = "ambiguous", _("Результат невідомий")
        CANCELLED = "cancelled", _("Скасовано")
        FAILED = "failed", _("Помилка")

    trigger_key = models.CharField(max_length=180, unique=True)
    client = models.ForeignKey(
        "management.IgClient",
        on_delete=models.DO_NOTHING,
        related_name="follow_cta_decisions",
        db_constraint=False,
    )
    commercial_episode = models.ForeignKey(
        "management.IgCommercialEpisode",
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="follow_cta_decisions",
        db_constraint=False,
    )
    order = models.ForeignKey(
        "orders.Order",
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="instagram_follow_cta_decisions",
        db_constraint=False,
    )
    lifecycle_event = models.ForeignKey(
        "management.IgLifecycleEvent",
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="follow_cta_decisions",
        db_constraint=False,
    )
    source_message = models.ForeignKey(
        "management.InstagramBotMessage",
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="follow_cta_decisions",
        db_constraint=False,
    )
    opportunity = models.CharField(max_length=24, choices=Opportunity.choices, db_index=True)
    policy_version = models.CharField(max_length=32, default="follow-v1")
    state = models.CharField(
        max_length=24,
        choices=State.choices,
        default=State.PREPARING,
        db_index=True,
    )
    episode_slot_key = models.CharField(
        max_length=160,
        null=True,
        blank=True,
        unique=True,
    )
    sent_scope_key = models.CharField(
        max_length=180,
        null=True,
        blank=True,
        unique=True,
    )
    follow_state_revision = models.PositiveBigIntegerField(default=0)
    conversation_watermark = models.PositiveBigIntegerField(default=0)
    context_fingerprint = models.CharField(max_length=64, blank=True, default="")
    base_text = models.TextField(blank=True, default="")
    candidate_text = models.CharField(max_length=300, blank=True, default="")
    candidate_hash = models.CharField(max_length=64, blank=True, default="")
    final_text = models.TextField(blank=True, default="")
    suppression_reason = models.CharField(max_length=64, blank=True, default="")
    reason_codes = models.JSONField(default=list, blank=True)
    model = models.CharField(max_length=80, blank=True, default="")
    model_key_alias = models.CharField(max_length=80, blank=True, default="")
    prompt_version = models.CharField(max_length=40, blank=True, default="")
    lease_token = models.CharField(max_length=64, blank=True, default="")
    lease_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    provider_message_ids = models.JSONField(default=list, blank=True)
    provider_io_started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    follow_observed_after_cta_at = models.DateTimeField(null=True, blank=True)
    last_error_kind = models.CharField(max_length=32, blank=True, default="")
    last_error_code = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager.from_queryset(_IgFollowCtaDecisionQuerySet)()

    _IDENTITY_FIELDS = (
        "trigger_key",
        "client_id",
        "commercial_episode_id",
        "order_id",
        "lifecycle_event_id",
        "source_message_id",
        "opportunity",
        "follow_state_revision",
        "conversation_watermark",
        "context_fingerprint",
        "base_text",
    )

    class Meta:
        ordering = ["-id"]
        indexes = [
            models.Index(
                fields=["client", "-created_at"],
                name="ig_follow_dec_client_dt",
            ),
            models.Index(
                fields=["state", "-created_at"],
                name="ig_follow_dec_state_dt",
            ),
            models.Index(
                fields=["commercial_episode", "state"],
                name="ig_follow_dec_episode",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values(
                *self._IDENTITY_FIELDS
            ).first()
            if previous:
                for field_name in self._IDENTITY_FIELDS:
                    if getattr(self, field_name) != previous[field_name]:
                        raise ValueError("IgFollowCtaDecision identity is immutable")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("IgFollowCtaDecision is durable")


class IgPaymentFollowPreparation(models.Model):
    """Lease-backed optional-copy preparation for one payment lifecycle event."""

    class State(models.TextChoices):
        PENDING = "pending", _("Очікує підготовки")
        WAITING_FOLLOW = "waiting_follow", _("Очікує перевірки підписки")
        PROCESSING = "processing", _("Готується")
        PREPARED = "prepared", _("Підготовлено")
        SUPPRESSED = "suppressed", _("Не додавати CTA")
        EXPIRED = "expired", _("Час підготовки минув")
        FAILED = "failed", _("Помилка підготовки")

    lifecycle_event = models.OneToOneField(
        "management.IgLifecycleEvent",
        on_delete=models.DO_NOTHING,
        related_name="follow_preparation",
        db_constraint=False,
    )
    client = models.ForeignKey(
        "management.IgClient",
        on_delete=models.DO_NOTHING,
        related_name="payment_follow_preparations",
        db_constraint=False,
    )
    deadline_at = models.DateTimeField(db_index=True)
    state = models.CharField(
        max_length=24,
        choices=State.choices,
        default=State.PENDING,
        db_index=True,
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    lease_token = models.CharField(max_length=64, blank=True, default="")
    lease_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_error_kind = models.CharField(max_length=32, blank=True, default="")
    last_error_code = models.CharField(max_length=64, blank=True, default="")
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["state", "deadline_at", "id"],
                name="ig_pay_follow_prep_due",
            ),
            models.Index(
                fields=["client", "state"],
                name="ig_pay_follow_prep_client",
            ),
        ]


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


class _AppendOnlyOrderShipmentQuerySet(models.QuerySet):
    def update(self, **kwargs):
        forbidden = {
            "order",
            "order_id",
            "tracking_number",
            "direction",
            "purpose",
            "supersedes",
            "supersedes_id",
        }
        if forbidden.intersection(kwargs):
            raise ValueError("IgOrderShipment identity is immutable")
        return super().update(**kwargs)

    def delete(self):
        raise ValueError("IgOrderShipment is append-only")

    def _raw_delete(self, using):
        raise ValueError("IgOrderShipment is append-only")


class IgOrderShipment(models.Model):
    """Every parcel that ever moved for one order, in both directions.

    ``Order.tracking_number`` is a single scalar with no history anywhere in the
    project, so writing an exchange replacement into it used to erase the
    original number and with it the fact that there were two shipments.

    An exchange is one purchase and several parcels, which is why this is a
    journal on the order rather than a second order: a second order would double
    the revenue and ``purchases_count``.
    """

    class Direction(models.TextChoices):
        OUTBOUND = "outbound", _("Ми відправили")
        INBOUND = "inbound", _("Клієнт відправив нам")

    class Purpose(models.TextChoices):
        INITIAL = "initial", _("Перша відправка")
        EXCHANGE_REPLACEMENT = "exchange_replacement", _("Заміна відправлена")
        RETURN_INBOUND = "return_inbound", _("Повернення від клієнта")
        CORRECTION = "correction", _("Переоформлена ТТН")

    class Source(models.TextChoices):
        ORDER_FIELD = "order_field", _("Поле замовлення")
        MANAGER_MANUAL = "manager_manual", _("Введено менеджером")
        CUSTOMER_MESSAGE = "customer_message", _("З повідомлення клієнта")

    class Payer(models.TextChoices):
        SHOP = "shop", _("За наш рахунок")
        CUSTOMER = "customer", _("За рахунок клієнта")
        UNKNOWN = "unknown", _("Не визначено")

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name="instagram_shipments",
    )
    post_sale_case = models.ForeignKey(
        "management.IgPostSaleCase",
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name="shipments",
    )
    tracking_number = models.CharField(max_length=64)
    direction = models.CharField(max_length=16, choices=Direction.choices, db_index=True)
    purpose = models.CharField(max_length=32, choices=Purpose.choices, db_index=True)
    supersedes = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name="superseded_by_shipments",
    )
    source = models.CharField(
        max_length=32, choices=Source.choices, default=Source.ORDER_FIELD
    )
    payer = models.CharField(
        max_length=16, choices=Payer.choices, default=Payer.SHOP
    )
    # A Nova Poshta "fast return" travels back on the SAME waybill as the
    # outbound parcel, and the customer pays nothing for it. One number in two
    # directions is therefore normal, not a data-entry mistake, and the flag
    # keeps the timeline from reading like a duplicate.
    reuses_outbound_tracking = models.BooleanField(default=False)
    evidence_message_id = models.PositiveBigIntegerField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_constraint=False,
        related_name="ig_order_shipments",
    )
    note = models.CharField(max_length=500, blank=True, default="")
    notified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = models.Manager.from_queryset(_AppendOnlyOrderShipmentQuerySet)()

    class Meta:
        verbose_name = _("Відправка замовлення Instagram")
        verbose_name_plural = _("Відправки замовлень Instagram")
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "tracking_number", "direction"],
                name="ig_shipment_once_per_direction",
            ),
        ]
        indexes = [
            models.Index(fields=["order", "created_at"], name="ig_shipment_order_dt"),
            models.Index(
                fields=["post_sale_case", "created_at"], name="ig_shipment_case_dt"
            ),
        ]

    def delete(self, *args, **kwargs):
        raise ValueError("IgOrderShipment is append-only")

    def __str__(self) -> str:  # pragma: no cover - тривіально
        return f"{self.tracking_number} ({self.purpose})"


class _AppendOnlyPromptRevisionQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValueError("BotPromptRevision is append-only")

    def delete(self):
        raise ValueError("BotPromptRevision is append-only")


class BotPromptRevision(models.Model):
    """Change history for the parts of the prompt that are edited by hand.

    IMP-025 asked to version ``InstagramBotSettings.system_prompt``. Measured on
    production that field is 3136 of ~26 900 assembled characters (11.7%), is
    byte-identical to the constant in code, and has never been saved through the
    form — ``settings_saved`` has zero log entries. The other 88% comes from code
    and from ``bot_knowledge/brand.md``, both already versioned by git.

    So the audited layer is the one that is genuinely editable and absent from
    git: ``BotInstruction`` bodies and the live ``knowledge_base``.
    """

    class Target(models.TextChoices):
        INSTRUCTION = "instruction", _("Інструкція бота")
        KNOWLEDGE_BASE = "knowledge_base", _("Оперативні директиви")

    class Kind(models.TextChoices):
        EDIT = "edit", _("Зміна")
        ROLLBACK = "rollback", _("Відкат")

    target = models.CharField(max_length=32, choices=Target.choices, db_index=True)
    target_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.EDIT)
    title = models.CharField(max_length=200, blank=True, default="")
    body = models.TextField(blank=True, default="")
    previous_body = models.TextField(blank=True, default="")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_constraint=False,
        related_name="bot_prompt_revisions",
    )
    actor_label = models.CharField(max_length=150, blank=True, default="")
    note = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = models.Manager.from_queryset(_AppendOnlyPromptRevisionQuerySet)()

    class Meta:
        verbose_name = _("Ревізія промпту бота")
        verbose_name_plural = _("Ревізії промпту бота")
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["target", "target_id", "-id"], name="bot_prompt_rev_target"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and not kwargs.get("force_insert"):
            raise ValueError("BotPromptRevision is append-only")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("BotPromptRevision is append-only")

    def diff_lines(self) -> list[str]:
        """Unified diff between the previous and the new body."""
        import difflib

        return list(
            difflib.unified_diff(
                (self.previous_body or "").splitlines(),
                (self.body or "").splitlines(),
                lineterm="",
                n=2,
            )
        )


class IgFunnelResetAudit(models.Model):
    """Immutable operator boundary between old CRM inference and a new test run."""

    client = models.ForeignKey(
        "management.IgClient",
        on_delete=models.DO_NOTHING,
        related_name="funnel_reset_audits",
        db_constraint=False,
    )
    reset_after_message_id = models.PositiveBigIntegerField(default=0, db_index=True)
    previous_state = models.JSONField(default=dict, blank=True)
    resulting_stage = models.CharField(max_length=24, blank=True, default="")
    reason = models.CharField(max_length=255)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="ig_funnel_reset_audits",
        db_constraint=False,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("Скидання воронки Instagram")
        verbose_name_plural = _("Скидання воронок Instagram")
        ordering = ["-id"]
        indexes = [
            models.Index(
                fields=["client", "-created_at"],
                name="ig_funnel_reset_client_dt",
            ),
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


class _AppendOnlyFunnelStepEventQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValueError("IgFunnelStepEvent is append-only")

    def delete(self):
        raise ValueError("IgFunnelStepEvent is append-only")


class IgFunnelStepEvent(models.Model):
    """Immutable event-time fact for one commercial funnel episode."""

    class Type(models.TextChoices):
        CONVERSATION_STARTED = "conversation_started", _("Діалог розпочато")
        BOT_REPLIED_FIRST = "bot_replied_first", _("Перша відповідь бота")
        PRODUCT_PINNED = "product_pinned", _("Товар визначено")
        VARIANT_SELECTED = "variant_selected", _("Варіант визначено")
        PRICE_QUOTED = "price_quoted", _("Ціну названо")
        PAYLINK_ISSUED = "paylink_issued", _("Посилання на оплату видано")
        PAYLINK_VIEWED = "paylink_viewed", _("Посилання на оплату відкрито")
        PAYMENT_CONFIRMED = "payment_confirmed", _("Оплату підтверджено")
        OBJECTION_RAISED = "objection_raised", _("Заперечення зафіксовано")
        OBJECTION_HANDLED = "objection_handled", _("Заперечення опрацьовано")
        DISCOUNT_OFFERED = "discount_offered", _("Знижку запропоновано")
        MANAGER_ENGAGED = "manager_engaged", _("Менеджер долучився")
        ORDER_CREATED = "order_created", _("Замовлення створено")
        TTN_CREATED = "ttn_created", _("ТТН створено")
        DELIVERED = "delivered", _("Замовлення отримано")
        DROP_OFF = "drop_off", _("Відвал зафіксовано")
        RECOVERED = "recovered", _("Клієнт повернувся")

    episode = models.ForeignKey(
        "management.IgCommercialEpisode",
        on_delete=models.DO_NOTHING,
        related_name="funnel_step_events",
        db_constraint=False,
    )
    event_key = models.CharField(max_length=160, unique=True)
    event_type = models.CharField(max_length=32, choices=Type.choices, db_index=True)
    stage = models.CharField(max_length=32, blank=True, default="", db_index=True)
    actor = models.CharField(max_length=40, blank=True, default="")
    occurred_at = models.DateTimeField(db_index=True)
    evidence = models.JSONField(default=dict, blank=True)
    is_backfilled = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager.from_queryset(_AppendOnlyFunnelStepEventQuerySet)()

    class Meta:
        ordering = ["occurred_at", "id"]
        indexes = [
            models.Index(fields=["episode", "occurred_at"], name="ig_fstep_episode_dt"),
            models.Index(fields=["event_type", "occurred_at"], name="ig_fstep_type_dt"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and not kwargs.get("force_insert"):
            raise ValueError("IgFunnelStepEvent is append-only")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("IgFunnelStepEvent is append-only")


class IgFunnelDropOffQuerySet(models.QuerySet):
    _RECOVERY_FIELDS = {"recovered_at", "recovered_by_followup", "recovery_event"}

    def update(self, **kwargs):
        if not set(kwargs).issubset(self._RECOVERY_FIELDS):
            raise ValueError("IgFunnelDropOff identity is immutable")
        return super().update(**kwargs)

    def delete(self):
        raise ValueError("IgFunnelDropOff cannot be deleted")


class IgFunnelDropOff(models.Model):
    """Durable classified loss fact; recovery may close it exactly once."""

    class Kind(models.TextChoices):
        SILENCE = "silence", _("Мовчання")
        EXPLICIT_REFUSAL = "explicit_refusal", _("Явна відмова")
        OPT_OUT = "opt_out", _("Відмова від повідомлень")
        UNREACHABLE = "unreachable", _("Недоступний через доставку")
        SPAM = "spam", _("Спам")
        SUPERSEDED = "superseded", _("Цикл заміщено")

    episode = models.ForeignKey(
        "management.IgCommercialEpisode",
        on_delete=models.DO_NOTHING,
        related_name="drop_offs",
        db_constraint=False,
    )
    step_event = models.OneToOneField(
        "management.IgFunnelStepEvent",
        on_delete=models.DO_NOTHING,
        related_name="drop_off",
        db_constraint=False,
    )
    kind = models.CharField(max_length=24, choices=Kind.choices, db_index=True)
    reason_code = models.CharField(max_length=80, blank=True, default="", db_index=True)
    stage_at_drop = models.CharField(max_length=32, blank=True, default="", db_index=True)
    objection_at_drop = models.CharField(max_length=32, blank=True, default="")
    silence_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    followups_sent_before = models.PositiveSmallIntegerField(default=0)
    detected_by = models.CharField(max_length=40, blank=True, default="")
    is_recoverable = models.BooleanField(default=False, db_index=True)
    occurred_at = models.DateTimeField(db_index=True)
    recovered_at = models.DateTimeField(null=True, blank=True, db_index=True)
    recovered_by_followup = models.BooleanField(default=False)
    recovery_event = models.ForeignKey(
        "management.IgFunnelStepEvent",
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="recovered_drop_offs",
        db_constraint=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = IgFunnelDropOffQuerySet.as_manager()
    _IDENTITY_FIELDS = (
        "episode_id", "step_event_id", "kind", "reason_code", "stage_at_drop",
        "objection_at_drop", "silence_hours", "followups_sent_before",
        "detected_by", "is_recoverable", "occurred_at",
    )

    class Meta:
        ordering = ["-occurred_at", "-id"]
        indexes = [
            models.Index(fields=["episode", "-occurred_at"], name="ig_drop_episode_dt"),
            models.Index(fields=["kind", "recovered_at"], name="ig_drop_kind_recovery"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values(
                *self._IDENTITY_FIELDS
            ).first()
            if previous:
                for field_name in self._IDENTITY_FIELDS:
                    if getattr(self, field_name) != previous[field_name]:
                        raise ValueError("IgFunnelDropOff identity is immutable")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("IgFunnelDropOff cannot be deleted")


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


class _IgFollowUpTaskQuerySet(models.QuerySet):
    _EVENT_BOUNDARY_FIELDS = {
        "event_key",
        "trigger",
        "event_occurred_at",
        "event_payload",
        "policy_started_at",
        "policy_version",
    }

    def update(self, **kwargs):
        if self._EVENT_BOUNDARY_FIELDS.intersection(kwargs):
            raise ValueError("IgFollowUpTask event boundary is immutable")
        return super().update(**kwargs)

    def bulk_update(self, objs, fields, batch_size=None):
        if self._EVENT_BOUNDARY_FIELDS.intersection(fields):
            raise ValueError("IgFollowUpTask event boundary is immutable")
        return super().bulk_update(objs, fields, batch_size=batch_size)


class IgFollowUpTask(models.Model):
    """Scheduled Instagram follow-up with Meta-window and quiet-hours guardrails."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Очікує")
        PROCESSING = "processing", _("Надсилається")
        SENT = "sent", _("Надіслано")
        AMBIGUOUS = "ambiguous", _("Потрібна перевірка доставки")
        COMPLETED = "completed", _("Завершено")
        CANCELLED = "cancelled", _("Скасовано")
        SKIPPED = "skipped", _("Пропущено")

    class Kind(models.TextChoices):
        QUALIFICATION = "qualification", _("Уточнення")
        PAYMENT = "payment", _("Нагадування про оплату")
        THINKING = "thinking", _("Клієнт думає")
        RESCUE = "rescue", _("Rescue offer")
        FINAL = "final", _("Фінальний офер")
        FULFILLMENT = "fulfillment", _("Дані для виконання замовлення")
        MANAGER_TASK = "manager_task", _("Завдання менеджеру")

    class Trigger(models.TextChoices):
        TIME = "time", _("За часом")
        EVENT = "event", _("Подія")
        REACTIVE = "reactive", _("Реактивно")

    class ManagerApprovalStatus(models.TextChoices):
        NOT_REQUIRED = "not_required", _("Не потрібне")
        PENDING = "pending", _("Очікує рішення")
        APPROVED = "approved", _("Підтверджено")
        REJECTED = "rejected", _("Відхилено")

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
    manager_approval_status = models.CharField(
        max_length=16,
        choices=ManagerApprovalStatus.choices,
        default=ManagerApprovalStatus.NOT_REQUIRED,
        db_index=True,
    )
    manager_approval_requested_at = models.DateTimeField(null=True, blank=True)
    manager_approval_decided_at = models.DateTimeField(null=True, blank=True)
    manager_approval_actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ig_followup_approvals",
        db_constraint=False,
    )
    meta_window_deadline = models.DateTimeField(null=True, blank=True, db_index=True)
    message_text = models.TextField(blank=True, default="")
    # Durable event identity and two-phase worker claim.  A nullable unique
    # key lets ordinary time-based tasks coexist while event-triggered tasks
    # remain idempotent across daemon/cron/retry workers.
    event_key = models.CharField(max_length=180, null=True, blank=True, unique=True)
    trigger = models.CharField(
        max_length=16,
        choices=Trigger.choices,
        default=Trigger.TIME,
        db_index=True,
    )
    event_occurred_at = models.DateTimeField(null=True, blank=True, db_index=True)
    event_payload = models.JSONField(default=dict, blank=True)
    policy_started_at = models.DateTimeField(null=True, blank=True, db_index=True)
    policy_version = models.CharField(max_length=32, default="followup-v1")
    claim_token = models.CharField(max_length=64, blank=True, default="")
    claim_until = models.DateTimeField(null=True, blank=True, db_index=True)
    provider_message_id = models.CharField(max_length=255, blank=True, default="")
    sent_message = models.ForeignKey(
        "management.InstagramBotMessage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    delivery_review_for = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="delivery_review",
    )
    skip_reason = models.CharField(max_length=255, blank=True, default="")
    attempt_count = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_error = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    objects = models.Manager.from_queryset(_IgFollowUpTaskQuerySet)()

    class Meta:
        verbose_name = _("IG follow-up")
        verbose_name_plural = _("IG follow-ups")
        ordering = ["due_at", "id"]
        indexes = [
            models.Index(fields=["status", "due_at"], name="ig_fu_status_due"),
            models.Index(fields=["client", "status"], name="ig_fu_client_status"),
            models.Index(fields=["kind", "status"], name="ig_fu_kind_status"),
            models.Index(fields=["trigger", "event_occurred_at"], name="ig_fu_trigger_event"),
        ]

    _EVENT_BOUNDARY_FIELDS = (
        "event_key",
        "trigger",
        "event_occurred_at",
        "event_payload",
        "policy_started_at",
        "policy_version",
    )

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values(
                *self._EVENT_BOUNDARY_FIELDS
            ).first()
            if previous:
                for field_name in self._EVENT_BOUNDARY_FIELDS:
                    if getattr(self, field_name) != previous[field_name]:
                        raise ValidationError("IgFollowUpTask event boundary is immutable")
        return super().save(*args, **kwargs)

    def __str__(self) -> str:  # pragma: no cover - тривіально
        return f"FollowUp#{self.pk} {self.client_id} {self.kind}/{self.status}"


class IgPollCursor(models.Model):
    """Durable per-conversation cursor for the optional polling backstop."""

    conversation_id = models.CharField(max_length=255, unique=True)
    participant_igsid = models.CharField(max_length=64, blank=True, default="", db_index=True)
    provider_updated_at = models.DateTimeField(null=True, blank=True, db_index=True)
    synced_provider_updated_at = models.DateTimeField(null=True, blank=True)
    excluded_at = models.DateTimeField(null=True, blank=True, db_index=True)
    excluded_reason = models.CharField(max_length=32, blank=True, default="")
    failure_count = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_error = models.CharField(max_length=80, blank=True, default="")
    last_message_id = models.CharField(max_length=255, blank=True, default="")
    last_message_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "IG polling cursor"
        verbose_name_plural = "IG polling cursors"

    def __str__(self) -> str:  # pragma: no cover - trivial representation
        return f"IgPollCursor({self.conversation_id})"


class IgInboxRefreshRun(models.Model):
    """Durable administrator-requested recovery of Meta-readable messages."""

    class Status(models.TextChoices):
        QUEUED = "queued", _("У черзі")
        DISCOVERING = "discovering", _("Пошук переписок")
        RUNNING = "running", _("Оновлення повідомлень")
        CANCELLING = "cancelling", _("Скасування")
        COMPLETED = "completed", _("Завершено")
        COMPLETED_ERRORS = "completed_errors", _("Завершено з помилками")
        CANCELLED = "cancelled", _("Скасовано")
        FAILED = "failed", _("Помилка")

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ig_inbox_refresh_runs",
        db_constraint=False,
    )
    provider_owner_id = models.CharField(max_length=128, db_index=True)
    transport = models.CharField(max_length=32, default="instagram_login")
    # MariaDB permits multiple NULLs but only one value=1 per provider owner.
    open_slot = models.PositiveSmallIntegerField(null=True, blank=True, default=1)
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.QUEUED,
        db_index=True,
    )
    recovery_cutoff = models.DateTimeField(db_index=True)
    discovery_cursor = models.TextField(blank=True, default="")
    discovery_pages_seen = models.PositiveSmallIntegerField(default=0)
    discovery_complete = models.BooleanField(default=False)
    lease_token = models.CharField(max_length=64, blank=True, default="")
    lease_until = models.DateTimeField(null=True, blank=True, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_error = models.CharField(max_length=1000, blank=True, default="")
    cancel_requested_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Оновлення Instagram inbox")
        verbose_name_plural = _("Оновлення Instagram inbox")
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider_owner_id", "open_slot"],
                name="ig_refresh_one_open_owner",
            ),
            models.CheckConstraint(
                condition=models.Q(open_slot__isnull=True) | models.Q(open_slot=1),
                name="ig_refresh_open_null_one",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "next_attempt_at", "id"],
                name="ig_refresh_run_due",
            ),
            models.Index(
                fields=["provider_owner_id", "-created_at"],
                name="ig_refresh_owner_dt",
            ),
        ]


class IgInboxRefreshItem(models.Model):
    """One conversation in a durable inbox recovery run."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Очікує")
        PROCESSING = "processing", _("Обробка")
        DONE = "done", _("Готово")
        SKIPPED = "skipped", _("Пропущено")
        FAILED = "failed", _("Помилка")
        CANCELLED = "cancelled", _("Скасовано")

    run = models.ForeignKey(
        "management.IgInboxRefreshRun",
        on_delete=models.CASCADE,
        related_name="items",
        db_constraint=False,
    )
    conversation_id = models.CharField(max_length=255)
    participant_igsid = models.CharField(max_length=64, blank=True, default="", db_index=True)
    client = models.ForeignKey(
        "management.IgClient",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="inbox_refresh_items",
        db_constraint=False,
    )
    provider_updated_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    skip_reason = models.CharField(max_length=64, blank=True, default="")
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True, db_index=True)
    lease_token = models.CharField(max_length=64, blank=True, default="")
    lease_until = models.DateTimeField(null=True, blank=True, db_index=True)
    messages_seen = models.PositiveSmallIntegerField(default=0)
    messages_created = models.PositiveSmallIntegerField(default=0)
    messages_existing = models.PositiveSmallIntegerField(default=0)
    messages_after_cutoff = models.PositiveSmallIntegerField(default=0)
    analysis_watermark_message_id = models.PositiveBigIntegerField(default=0)
    history_cursor = models.TextField(blank=True, default="")
    history_complete = models.BooleanField(default=False)
    truncated_reason = models.CharField(max_length=64, blank=True, default="")
    provider_http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    last_error = models.CharField(max_length=1000, blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Переписка оновлення Instagram inbox")
        verbose_name_plural = _("Переписки оновлення Instagram inbox")
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "conversation_id"],
                name="ig_refresh_item_run_conv",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "next_attempt_at", "id"],
                name="ig_refresh_item_due",
            ),
            models.Index(
                fields=["run", "status", "id"],
                name="ig_refresh_item_run",
            ),
            models.Index(
                fields=["participant_igsid", "status"],
                name="ig_refresh_item_user",
            ),
        ]


class IgConversationSignal(models.Model):
    """Classified sales signal extracted from client/bot/manager conversation."""

    class Type(models.TextChoices):
        PRICE_OBJECTION = "price_objection", _("Дорого")
        PREPAYMENT_OBJECTION = "prepayment_objection", _("Передоплата")
        SIZE_CONCERN = "size_concern", _("Розмір")
        THINKING_OBJECTION = "thinking_objection", _("Подумаю")
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


class IgObjection(models.Model):
    """One durable objection lifecycle inside a commercial episode."""

    class Type(models.TextChoices):
        PRICE = "price", _("Дорого")
        THINKING = "thinking", _("Подумаю")
        SIZE_RISK = "size_risk", _("Не підійде розмір")
        PREPAYMENT_TRUST = "prepayment_trust", _("Не довіряє передоплаті")
        DEFECT_RISK = "defect_risk", _("Боїться браку")
        DELIVERY_TIME = "delivery_time", _("Довго чекати")
        CHEAPER_ELSEWHERE = "cheaper_elsewhere", _("Є дешевше")
        PRINT_QUALITY = "print_quality", _("Якість принта")
        OUT_OF_STOCK = "out_of_stock", _("Немає розміру/варіанта")
        PAYDAY = "payday", _("Після зарплати")
        COMPARE_BRAND = "compare_brand", _("Порівнює з брендом")
        ASK_PARTNER = "ask_partner", _("Порадиться з близькою людиною")

    class State(models.TextChoices):
        OPEN = "open", _("Відкрите")
        HANDLED = "handled", _("Метод застосовано")
        RESOLVED = "resolved", _("Закрито фактом")
        ABANDONED = "abandoned", _("Втрачено")

    class Outcome(models.TextChoices):
        UNRESOLVED = "unresolved", _("Не вирішено")
        PURCHASED = "purchased", _("Купив")
        LOST = "lost", _("Втрачено")
        SILENT = "silent", _("Замовк")
        MANAGER_TAKEN = "manager_taken", _("Передано менеджеру")

    client = models.ForeignKey(
        "management.IgClient", on_delete=models.DO_NOTHING,
        related_name="objection_lifecycles", db_constraint=False,
    )
    episode = models.ForeignKey(
        "management.IgCommercialEpisode", null=True, blank=True,
        on_delete=models.DO_NOTHING, related_name="objections", db_constraint=False,
    )
    objection_type = models.CharField(max_length=32, choices=Type.choices, db_index=True)
    state = models.CharField(max_length=16, choices=State.choices, default=State.OPEN, db_index=True)
    is_true_objection = models.BooleanField(default=True)
    first_message = models.ForeignKey(
        "management.InstagramBotMessage", null=True, blank=True,
        on_delete=models.DO_NOTHING, related_name="opened_objections", db_constraint=False,
    )
    last_message = models.ForeignKey(
        "management.InstagramBotMessage", null=True, blank=True,
        on_delete=models.DO_NOTHING, related_name="latest_objections", db_constraint=False,
    )
    repeat_count = models.PositiveIntegerField(default=1)
    attempts_count = models.PositiveIntegerField(default=0)
    resolution_method = models.CharField(max_length=48, blank=True, default="")
    outcome = models.CharField(max_length=24, choices=Outcome.choices, default=Outcome.UNRESOLVED)
    readiness_before = models.PositiveSmallIntegerField(default=0)
    readiness_after = models.PositiveSmallIntegerField(default=0)
    opened_watermark_message_id = models.PositiveBigIntegerField(default=0, db_index=True)
    dedupe_key = models.CharField(max_length=160, unique=True)
    opened_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [
            models.Index(fields=["client", "state", "-id"], name="ig_obj_client_state"),
            models.Index(fields=["objection_type", "state"], name="ig_obj_type_state"),
        ]


class IgObjectionAttempt(models.Model):
    """Append-only claimed objection-handling method and observed result."""

    class Result(models.TextChoices):
        PENDING = "pending", _("Очікує реакції")
        ACCEPTED = "accepted", _("Прийнято")
        RE_OBJECTED = "re_objected", _("Повторив заперечення")
        SILENT = "silent", _("Без відповіді")
        ESCALATED = "escalated", _("Передано менеджеру")
        PURCHASED = "purchased", _("Купив")
        IGNORED = "ignored", _("Метод не застосовано")

    objection = models.ForeignKey(
        "management.IgObjection", on_delete=models.DO_NOTHING,
        related_name="attempts", db_constraint=False,
    )
    method = models.CharField(max_length=48, default="none", db_index=True)
    claimed_by = models.CharField(max_length=24, default="model")
    verified = models.BooleanField(default=False, db_index=True)
    verification_reason = models.CharField(max_length=255, blank=True, default="")
    reply_message = models.OneToOneField(
        "management.InstagramBotMessage", null=True, blank=True,
        on_delete=models.DO_NOTHING, related_name="objection_attempts", db_constraint=False,
    )
    client_response_message = models.ForeignKey(
        "management.InstagramBotMessage", null=True, blank=True,
        on_delete=models.DO_NOTHING, related_name="objection_responses", db_constraint=False,
    )
    result = models.CharField(max_length=24, choices=Result.choices, default=Result.PENDING)
    readiness_before = models.PositiveSmallIntegerField(default=0)
    readiness_after = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-id"]
        indexes = [models.Index(fields=["objection", "-id"], name="ig_obj_attempt_dt")]


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
        # A size exchange is neither a complaint nor an objection to buying: it
        # is a service case on top of a purchase that already happened. Keeping
        # it inside SUPPORT_COMPLAINT made a satisfied customer read as an
        # unhappy one (F-SCORE-002).
        EXCHANGE_REQUEST = "exchange_request", _("Обмін товару")
        RETURN_REQUEST = "return_request", _("Повернення товару")
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


class _IgConversationAnalysisEventQuerySet(models.QuerySet):
    _IMMUTABLE_FIELDS = {
        "event_key",
        "client",
        "client_id",
        "snapshot",
        "snapshot_id",
        "event_type",
        "payload",
        "required_state_fingerprint",
        "source_digest",
    }

    def update(self, **kwargs):
        if self._IMMUTABLE_FIELDS.intersection(kwargs):
            raise ValueError("IgConversationAnalysisEvent identity is immutable")
        return super().update(**kwargs)

    def delete(self):
        raise ValueError("IgConversationAnalysisEvent identity is immutable")


class IgConversationAnalysisEvent(models.Model):
    """Typed operational proposal emitted by a completed analysis snapshot.

    The identity and payload are immutable after publication.  Only the
    deterministic consumer may advance the outcome fields, which keeps a
    provider result from mutating episodes, sessions or funnel state directly.
    """

    class EventType(models.TextChoices):
        REPEAT_EPISODE = "repeat_episode", _("Новий епізод повторного замовлення")

    class Status(models.TextChoices):
        PENDING = "pending", _("Очікує матеріалізації")
        APPLIED = "applied", _("Матеріалізовано")
        REJECTED = "rejected", _("Відхилено перевіркою")
        FAILED = "failed", _("Вичерпано повторні спроби")

    _IDENTITY_FIELDS = {
        "event_key",
        "client_id",
        "snapshot_id",
        "event_type",
        "payload",
        "required_state_fingerprint",
        "source_digest",
    }

    event_key = models.CharField(max_length=160, unique=True)
    client = models.ForeignKey(
        "management.IgClient",
        on_delete=models.DO_NOTHING,
        related_name="analysis_events",
        db_constraint=False,
    )
    snapshot = models.OneToOneField(
        "management.IgConversationAnalysisSnapshot",
        on_delete=models.DO_NOTHING,
        related_name="operational_event",
        db_constraint=False,
    )
    event_type = models.CharField(max_length=32, choices=EventType.choices)
    payload = models.JSONField(default=dict, blank=True)
    required_state_fingerprint = models.CharField(max_length=64, blank=True, default="")
    source_digest = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    applied_episode = models.ForeignKey(
        "management.IgCommercialEpisode",
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="analysis_events",
        db_constraint=False,
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(
        null=True,
        blank=True,
        default=timezone.now,
        db_index=True,
    )
    last_error = models.CharField(max_length=1000, blank=True, default="")
    rejected_reason = models.CharField(max_length=120, blank=True, default="")
    applied_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Операційна подія аналізу IG")
        verbose_name_plural = _("Операційні події аналізу IG")
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(
                fields=["status", "next_attempt_at", "id"],
                name="ig_analysis_event_due",
            ),
            models.Index(fields=["client", "status"], name="ig_analysis_event_client"),
        ]

    objects = models.Manager.from_queryset(_IgConversationAnalysisEventQuerySet)()

    def save(self, *args, **kwargs):
        if self.pk:
            previous = (
                type(self)
                .objects.filter(pk=self.pk)
                .values(*self._IDENTITY_FIELDS)
                .first()
            )
            if previous:
                for field_name in self._IDENTITY_FIELDS:
                    value = getattr(self, field_name)
                    if field_name.endswith("_id"):
                        value = getattr(self, field_name)
                    if value != previous[field_name]:
                        raise ValueError("IgConversationAnalysisEvent identity is immutable")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("IgConversationAnalysisEvent identity is immutable")

    def __str__(self) -> str:  # pragma: no cover - trivial representation
        return f"{self.event_type}:{self.event_key} ({self.status})"


class IgConversationAnalysisJob(models.Model):
    """One durable, coalescing high-reasoning analysis cursor per IG client."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Очікує аналізу")
        PROCESSING = "processing", _("Аналізується")
        DONE = "done", _("Проаналізовано")
        FAILED = "failed", _("Помилка аналізу")
        SKIPPED = "skipped", _("Аналіз пропущено")

    class MediaPhase(models.TextChoices):
        NOT_STARTED = "not_started", _("Медіа не розпочато")
        ACQUIRING = "acquiring", _("Медіа обробляється")
        READY = "ready", _("Медіа готове")
        METADATA_ONLY = "metadata_only", _("Лише метадані")
        FAILED = "failed", _("Помилка медіа")

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
    media_phase = models.CharField(
        max_length=24,
        choices=MediaPhase.choices,
        default=MediaPhase.NOT_STARTED,
        db_index=True,
    )
    media_error_kind = models.CharField(max_length=64, blank=True, default="")
    media_started_at = models.DateTimeField(null=True, blank=True)
    media_completed_at = models.DateTimeField(null=True, blank=True)
    media_item_count = models.PositiveSmallIntegerField(default=0)
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


class IgAiReplyRecoveryJob(models.Model):
    """One non-replayable recovery intent for a failed customer AI turn.

    A recovery is deliberately separate from sales follow-ups and conversation
    analysis: it exists only to complete one specific inbound turn after a
    transient provider failure.  ``SENDING`` means the Meta request boundary
    was crossed.  It is never retried automatically without a provider receipt.
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("Очікує відновлення")
        PROCESSING = "processing", _("Готується відповідь")
        SENDING = "sending", _("Надсилається")
        SENT = "sent", _("Надіслано")
        CANCELLED = "cancelled", _("Скасовано")
        AMBIGUOUS = "ambiguous", _("Невідомий результат")
        FAILED = "failed", _("Помилка відновлення")

    source_message = models.OneToOneField(
        "management.InstagramBotMessage",
        on_delete=models.CASCADE,
        related_name="ai_reply_recovery_job",
        db_constraint=False,
    )
    client = models.ForeignKey(
        "management.IgClient",
        on_delete=models.CASCADE,
        related_name="ai_reply_recovery_jobs",
        db_constraint=False,
    )
    # The generic outage holding reply is allowed to precede the recovery.  A
    # later substantive model reply still cancels this stale intent.
    holding_message = models.OneToOneField(
        "management.InstagramBotMessage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ai_recovery_holding_for",
        db_constraint=False,
    )
    # The row is created before the Meta request.  It makes the exact draft
    # visible for manual reconciliation even if the process dies during I/O.
    reply_message = models.OneToOneField(
        "management.InstagramBotMessage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ai_recovery_reply_for",
        db_constraint=False,
    )
    dedupe_key = models.CharField(max_length=160, unique=True)
    # Епізод деградації (ЭА.7): курсор відновлення живе на парі
    # (клієнт, інцидент), а не на кожному source-повідомленні. Три вхідні під
    # час одного інциденту раніше давали три job'и й кілька відповідей клієнту.
    degradation_episode = models.ForeignKey(
        "management.IgClientDegradationEpisode",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recovery_jobs",
        db_constraint=False,
    )
    superseded_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="superseded_jobs",
        db_constraint=False,
    )
    # «Один активний курсор на (клієнт, інцидент)» тримається в БД через
    # nullable unique-колонку: активний job має ключ, терминальний — NULL.
    # Часткові unique-індекси MariaDB не підтримує, тому це єдиний портативний
    # спосіб отримати справжню гарантію, а не перевірку в коді.
    active_cursor_key = models.CharField(
        max_length=80, null=True, blank=True, unique=True
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    draft_text = models.TextField(blank=True, default="")
    routing_decision = models.JSONField(default=dict, blank=True)
    provider_message_id = models.CharField(max_length=255, blank=True, default="", db_index=True)
    settings_permission_epoch = models.PositiveBigIntegerField(default=0)
    client_permission_epoch = models.PositiveBigIntegerField(default=0)
    message_floor = models.PositiveBigIntegerField(default=0)
    response_window_deadline = models.DateTimeField(null=True, blank=True, db_index=True)
    # Created before the holding Meta send, then explicitly armed only after
    # its provider receipt is persisted. A prepared job is never worker-due.
    activated_at = models.DateTimeField(null=True, blank=True, db_index=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True, db_index=True)
    lease_token = models.CharField(max_length=40, blank=True, default="")
    lease_until = models.DateTimeField(null=True, blank=True, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.CharField(max_length=1000, blank=True, default="")
    sending_started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Відновлення AI-відповіді IG")
        verbose_name_plural = _("Відновлення AI-відповідей IG")
        ordering = ["id"]
        indexes = [
            models.Index(fields=["status", "response_window_deadline"], name="ig_ai_recovery_due"),
            models.Index(
                fields=["status", "activated_at", "next_attempt_at"],
                name="ig_ai_recovery_ready",
            ),
            models.Index(fields=["client", "status"], name="ig_ai_recovery_client"),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial representation
        return f"recovery:{self.source_message_id}:{self.status}"


class IgPermissionTransitionJob(models.Model):
    """Durable fail-closed pause/takeover/opt-out transition."""

    class Kind(models.TextChoices):
        OPT_OUT = "opt_out", _("Відмова від повідомлень")
        MANAGER_TAKEOVER = "manager_takeover", _("Діалог веде менеджер")
        CLIENT_PAUSE = "client_pause", _("Ручна пауза для клієнта")
        GLOBAL_PAUSE = "global_pause", _("Глобальна пауза бота")

    class Status(models.TextChoices):
        PENDING = "pending", _("Очікує застосування")
        PROCESSING = "processing", _("Застосовується")
        APPLIED = "applied", _("Застосовано")
        SUPERSEDED = "superseded", _("Вже не актуально")
        FAILED = "failed", _("Потрібне відновлення")

    kind = models.CharField(max_length=32, choices=Kind.choices, db_index=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    client = models.ForeignKey(
        "management.IgClient",
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="permission_transition_jobs",
        db_constraint=False,
    )
    settings = models.ForeignKey(
        "management.InstagramBotSettings",
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="permission_transition_jobs",
        db_constraint=False,
    )
    source_message = models.ForeignKey(
        "management.InstagramBotMessage",
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="permission_transition_jobs",
        db_constraint=False,
    )
    dedupe_key = models.CharField(max_length=255, unique=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True, default=timezone.now)
    lease_token = models.CharField(max_length=40, blank=True, default="")
    lease_until = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error_kind = models.CharField(max_length=64, blank=True, default="")
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(
                fields=["status", "next_attempt_at", "id"],
                name="ig_perm_transition_due",
            ),
            models.Index(
                fields=["client", "status"],
                name="ig_perm_transition_client",
            ),
            models.Index(fields=["lease_until"], name="ig_perm_transition_lease"),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial representation
        return f"permission:{self.kind}:{self.status}:{self.pk}"


class IgCommerceSelectionSession(models.Model):
    """Authoritative, reversible product-selection state for one sales episode."""

    class State(models.TextChoices):
        OPEN = "open", _("Відкрита")
        CLOSED = "closed", _("Закрита")

    client = models.ForeignKey(
        "management.IgClient",
        on_delete=models.DO_NOTHING,
        related_name="commerce_selection_sessions",
        db_constraint=False,
    )
    commercial_episode = models.ForeignKey(
        "management.IgCommercialEpisode",
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="commerce_selection_sessions",
        db_constraint=False,
    )
    generation = models.PositiveIntegerField()
    # MariaDB permits multiple NULL values in a unique key, so only the open
    # row occupies slot 1 while historical generations use NULL.
    open_slot = models.PositiveSmallIntegerField(null=True, blank=True, default=1)
    state = models.CharField(
        max_length=16,
        choices=State.choices,
        default=State.OPEN,
        db_index=True,
    )
    lines = models.JSONField(default=list, blank=True)
    active_index = models.PositiveIntegerField(default=0)
    selection_constraints = models.JSONField(default=dict, blank=True)
    query_constraints = models.JSONField(default=dict, blank=True)
    candidate_product_ids = models.JSONField(default=list, blank=True)
    candidate_digest = models.CharField(max_length=64, blank=True, default="")
    candidate_generation = models.PositiveIntegerField(default=0)
    candidate_prompt_provider_ids = models.JSONField(default=list, blank=True)
    rejected_selection = models.JSONField(default=dict, blank=True)
    rejected_reason = models.CharField(max_length=120, blank=True, default="")
    pending_field = models.CharField(max_length=80, blank=True, default="")
    pending_clarification = models.CharField(max_length=120, blank=True, default="")
    semantic_block_key = models.CharField(max_length=160, blank=True, default="", db_index=True)
    graph_digest = models.CharField(max_length=64, blank=True, default="")
    last_provider_event_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_provider_message_id = models.CharField(max_length=255, blank=True, default="")
    revision = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["client_id", "-generation"]
        constraints = [
            models.UniqueConstraint(
                fields=["client", "generation"],
                name="ig_commerce_client_generation",
            ),
            models.UniqueConstraint(
                fields=["client", "open_slot"],
                name="ig_commerce_one_open_slot",
            ),
            models.CheckConstraint(
                condition=models.Q(open_slot__isnull=True) | models.Q(open_slot=1),
                name="ig_commerce_open_slot_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["client", "state", "-generation"],
                name="ig_com_sess_client_state",
            ),
            models.Index(fields=["state", "-updated_at"], name="ig_com_sess_state_dt"),
        ]

    def snapshot(self) -> dict:
        return {
            "generation": self.generation,
            "state": self.state,
            "lines": list(self.lines or []),
            "active_index": int(self.active_index or 0),
            "selection_constraints": dict(self.selection_constraints or {}),
            "query_constraints": dict(self.query_constraints or {}),
            "candidate_product_ids": list(self.candidate_product_ids or []),
            "candidate_digest": self.candidate_digest or "",
            "candidate_generation": int(self.candidate_generation or 0),
            "candidate_prompt_provider_ids": list(self.candidate_prompt_provider_ids or []),
            "rejected_selection": dict(self.rejected_selection or {}),
            "rejected_reason": self.rejected_reason or "",
            "pending_field": self.pending_field or "",
            "pending_clarification": self.pending_clarification or "",
            "semantic_block_key": self.semantic_block_key or "",
            "graph_digest": self.graph_digest or "",
            "last_provider_event_at": (
                self.last_provider_event_at.isoformat() if self.last_provider_event_at else None
            ),
            "last_provider_message_id": self.last_provider_message_id or "",
            "revision": int(self.revision or 0),
        }


class _AppendOnlyCommerceTransitionQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValueError("IgCommerceSelectionTransition is append-only")

    def delete(self):
        raise ValueError("IgCommerceSelectionTransition is append-only")


class IgCommerceSelectionTransition(models.Model):
    """Append-only state change with complete before/after evidence."""

    session = models.ForeignKey(
        "management.IgCommerceSelectionSession",
        on_delete=models.CASCADE,
        related_name="transitions",
    )
    source_message = models.OneToOneField(
        "management.InstagramBotMessage",
        on_delete=models.DO_NOTHING,
        related_name="commerce_selection_transition",
        db_constraint=False,
    )
    action = models.CharField(max_length=80, db_index=True)
    from_revision = models.PositiveIntegerField()
    to_revision = models.PositiveIntegerField()
    previous_snapshot = models.JSONField(default=dict)
    next_snapshot = models.JSONField(default=dict)
    effects = models.JSONField(default=dict, blank=True)
    reasons = models.JSONField(default=list, blank=True)
    graph_digest = models.CharField(max_length=64, blank=True, default="")
    source_order_key = models.CharField(max_length=360, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = _AppendOnlyCommerceTransitionQuerySet.as_manager()

    class Meta:
        ordering = ["session_id", "to_revision", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "to_revision"],
                name="ig_commerce_session_revision",
            )
        ]
        indexes = [
            models.Index(fields=["session", "-created_at"], name="ig_com_trans_session_dt"),
            models.Index(fields=["action", "-created_at"], name="ig_com_trans_action_dt"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValueError("IgCommerceSelectionTransition is append-only")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("IgCommerceSelectionTransition is append-only")


class _CommerceDecisionQuerySet(models.QuerySet):
    mutable_fields = frozenset({
        "delivery_state",
        "attempts",
        "delivery_started_at",
        "last_attempt_at",
        "delivered_at",
        "delivery_error",
        "text_receipts",
        "media_receipts",
        "provider_message_ids",
        "reconciliation_status",
        "reconciliation_result",
        "reconciliation_evidence",
        "updated_at",
    })

    def update(self, **kwargs):
        immutable = set(kwargs) - self.mutable_fields
        if immutable:
            raise ValueError("IgCommerceTurnDecision identity is immutable")
        return super().update(**kwargs)

    def delete(self):
        raise ValueError("IgCommerceTurnDecision is durable")


class IgCommerceTurnDecision(models.Model):
    """One immutable reduction result plus a separately mutable delivery outbox."""

    class DeliveryState(models.TextChoices):
        PENDING = "pending", _("Очікує")
        SENDING = "sending", _("Надсилається")
        UNKNOWN = "unknown", _("Результат невідомий")
        PARTIAL = "partial", _("Частково надіслано")
        SENT = "sent", _("Надіслано")
        NOT_REQUIRED = "not_required", _("Доставка не потрібна")

    class ReconciliationStatus(models.TextChoices):
        NOT_REQUIRED = "not_required", _("Не потрібне")
        REQUIRED = "required", _("Потрібне")
        PENDING = "pending", _("Очікує")
        RECONCILED = "reconciled", _("Звірено")
        MANAGER_REVIEW = "manager_review", _("Перевірка менеджера")

    source_message = models.OneToOneField(
        "management.InstagramBotMessage",
        on_delete=models.DO_NOTHING,
        related_name="commerce_turn_decision",
        db_constraint=False,
    )
    session = models.ForeignKey(
        "management.IgCommerceSelectionSession",
        on_delete=models.CASCADE,
        related_name="decisions",
    )
    transition = models.ForeignKey(
        "management.IgCommerceSelectionTransition",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="decisions",
    )
    request_payload = models.JSONField(default=dict)
    result_payload = models.JSONField(default=dict)
    reply_payload = models.JSONField(default=dict)
    effects_payload = models.JSONField(default=dict)
    accepted = models.BooleanField(default=True)
    is_stale = models.BooleanField(default=False, db_index=True)
    delivery_required = models.BooleanField(default=True)
    delivery_state = models.CharField(
        max_length=16,
        choices=DeliveryState.choices,
        default=DeliveryState.PENDING,
        db_index=True,
    )
    attempts = models.PositiveIntegerField(default=0)
    delivery_started_at = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    delivery_error = models.CharField(max_length=1000, blank=True, default="")
    text_receipts = models.JSONField(default=list, blank=True)
    media_receipts = models.JSONField(default=list, blank=True)
    provider_message_ids = models.JSONField(default=list, blank=True)
    reconciliation_status = models.CharField(
        max_length=24,
        choices=ReconciliationStatus.choices,
        default=ReconciliationStatus.NOT_REQUIRED,
        db_index=True,
    )
    reconciliation_result = models.JSONField(default=dict, blank=True)
    reconciliation_evidence = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = _CommerceDecisionQuerySet.as_manager()

    _immutable_fields = (
        "source_message_id",
        "session_id",
        "transition_id",
        "request_payload",
        "result_payload",
        "reply_payload",
        "effects_payload",
        "accepted",
        "is_stale",
        "delivery_required",
    )

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(
                fields=["delivery_state", "created_at"],
                name="ig_com_decision_delivery",
            ),
            models.Index(fields=["session", "-created_at"], name="ig_com_decision_session"),
            models.Index(
                fields=["reconciliation_status", "-updated_at"],
                name="ig_com_decision_recon",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            stored = type(self).objects.filter(pk=self.pk).values(*self._immutable_fields).first()
            if stored and any(stored[name] != getattr(self, name) for name in self._immutable_fields):
                raise ValueError("IgCommerceTurnDecision identity is immutable")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("IgCommerceTurnDecision is durable")


class IgCommerceManagerReview(models.Model):
    """SLA-backed manager recovery for ambiguous or unreconciled decisions."""

    class Status(models.TextChoices):
        OPEN = "open", _("Відкрита")
        CLAIMED = "claimed", _("В роботі")
        RESOLVED = "resolved", _("Вирішена")
        CANCELLED = "cancelled", _("Скасована")

    idempotency_key = models.CharField(max_length=180, unique=True)
    client = models.ForeignKey(
        "management.IgClient",
        on_delete=models.DO_NOTHING,
        related_name="commerce_manager_reviews",
        db_constraint=False,
    )
    session = models.ForeignKey(
        "management.IgCommerceSelectionSession",
        on_delete=models.CASCADE,
        related_name="manager_reviews",
    )
    decision = models.ForeignKey(
        "management.IgCommerceTurnDecision",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="manager_reviews",
    )
    reason = models.CharField(max_length=120, db_index=True)
    selection_snapshot = models.JSONField(default=dict, blank=True)
    selection_digest = models.CharField(max_length=64, blank=True, default="")
    selection_generation = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    due_at = models.DateTimeField(db_index=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="ig_commerce_reviews_owned",
        db_constraint=False,
    )
    claimed_at = models.DateTimeField(null=True, blank=True)
    claim_lease_token = models.CharField(max_length=64, blank=True, default="")
    claim_lease_until = models.DateTimeField(null=True, blank=True, db_index=True)
    resolution_payload = models.JSONField(default=dict, blank=True)
    resolution_note = models.CharField(max_length=1000, blank=True, default="")
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        related_name="ig_commerce_reviews_resolved",
        db_constraint=False,
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_at", "id"]
        indexes = [
            models.Index(
                fields=["status", "due_at", "id"],
                name="ig_com_review_status_due",
            ),
            models.Index(
                fields=["owner", "status", "due_at"],
                name="ig_com_review_owner_due",
            ),
            models.Index(fields=["client", "-created_at"], name="ig_com_review_client_dt"),
        ]


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


class IgProviderIncident(models.Model):
    """Одна durable деградація провайдера, а не окремий збій запиту.

    Система вміла бачити окремі збої (`GeminiRequestAttempt`, `GeminiKeyState`),
    але не вміла відповісти на питання «чи вже триває інцидент?». Через це кожен
    новий вхідний починав міркування з нуля й отримував власне технічне
    вибачення. Інцидент — це стан ПРОВАЙДЕРА; стан конкретного клієнта в межах
    інциденту описує `IgClientDegradationEpisode`.

    Fingerprint — це `role + failure_class`. Область (`scope`: модель, ключ,
    project-group) свідомо НЕ входить у ключ: клієнту байдуже, який саме ключ
    впав, йому важливо, що бот молчить. Області накопичуються в
    `observed_scopes`, щоб інцидент по шести алиасах залишався одним інцидентом.
    """

    class State(models.TextChoices):
        OPEN = "open", _("Відкритий")
        RECOVERING = "recovering", _("Відновлюється")
        CLOSED = "closed", _("Закритий")

    class FailureClass(models.TextChoices):
        QUOTA = "quota", _("Квота (429)")
        UNAVAILABLE = "unavailable", _("Недоступність (5xx)")
        TIMEOUT = "timeout", _("Таймаут читання")
        CONNECT = "connect", _("Транспорт/з'єднання")
        INVALID_PAYLOAD = "invalid_payload", _("Некоректний запит (400)")
        AUTH = "auth", _("Ключ/доступ (401/403)")
        EMPTY = "empty", _("Порожня відповідь")
        UNKNOWN = "unknown", _("Інше")

    role = models.CharField(max_length=20, db_index=True)
    failure_class = models.CharField(
        max_length=20, choices=FailureClass.choices, default=FailureClass.UNKNOWN
    )
    fingerprint = models.CharField(max_length=120, db_index=True)
    # MariaDB не підтримує частковий unique-індекс, тому «один відкритий
    # інцидент на fingerprint» тримається на nullable unique-колонці: активний
    # інцидент має значення, закритий — NULL (MySQL/MariaDB і SQLite дозволяють
    # багато NULL у unique-індексі). Це справжня гарантія в БД, а не в коді.
    active_fingerprint = models.CharField(
        max_length=120, null=True, blank=True, unique=True
    )
    state = models.CharField(
        max_length=12, choices=State.choices, default=State.OPEN, db_index=True
    )
    opened_at = models.DateTimeField(default=timezone.now, db_index=True)
    last_failure_at = models.DateTimeField(null=True, blank=True, db_index=True)
    first_success_after_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    close_reason = models.CharField(max_length=32, blank=True, default="")
    observed_scopes = models.JSONField(default=list, blank=True)
    failure_count = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    consecutive_success_count = models.PositiveSmallIntegerField(default=0)
    affected_clients_count = models.PositiveIntegerField(default=0)
    holding_sent_count = models.PositiveIntegerField(default=0)
    # Обчислюється для агрегації алертів менеджеру; НЕ використовується для
    # рішень, видимих клієнту.
    severity = models.PositiveSmallIntegerField(default=1)
    manager_alert_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Інцидент провайдера IG")
        verbose_name_plural = _("Інциденти провайдера IG")
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["state", "-last_failure_at"], name="ig_incident_state_recent"),
            models.Index(fields=["role", "state", "-id"], name="ig_incident_role_state"),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial representation
        return f"incident:{self.role}:{self.failure_class}:{self.state}"

    @property
    def is_active(self) -> bool:
        return self.state in {self.State.OPEN, self.State.RECOVERING}


class IgClientDegradationEpisode(models.Model):
    """Стан одного клієнта в межах одного інциденту провайдера.

    Одиниця «не більше одного технічного повідомлення» — це пара
    (інцидент, клієнт), а НЕ `source_message_id`. Старий dedupe по source
    формально проходив власний тест і при цьому давав клієнту три однакові
    вибачення за 6 хвилин: три різні вхідні — це три різні source_id.

    Діаграма станів:
        OPEN → HOLDING_SENT → RECOVERY_PENDING → RECOVERED
    гілки: → MANUAL (takeover/виснаження), → SUPERSEDED (новий інцидент),
            → CANCELLED (opt-out, hidden, зміна epoch).
    """

    class State(models.TextChoices):
        OPEN = "open", _("Відкритий")
        HOLDING_SENT = "holding_sent", _("Холдинг надіслано")
        RECOVERY_PENDING = "recovery_pending", _("Готується відновлення")
        RECOVERED = "recovered", _("Відновлено")
        MANUAL = "manual", _("Передано менеджеру")
        SUPERSEDED = "superseded", _("Витіснено")
        CANCELLED = "cancelled", _("Скасовано")

    _TERMINAL_STATES = frozenset({
        State.RECOVERED, State.MANUAL, State.SUPERSEDED, State.CANCELLED,
    })

    client = models.ForeignKey(
        "management.IgClient",
        on_delete=models.CASCADE,
        related_name="degradation_episodes",
        db_constraint=False,
    )
    incident = models.ForeignKey(
        "management.IgProviderIncident",
        on_delete=models.CASCADE,
        related_name="client_episodes",
        db_constraint=False,
    )
    state = models.CharField(
        max_length=20, choices=State.choices, default=State.OPEN, db_index=True
    )
    # Рівно один holding на епізод; O2O тримає цю інваріанту в БД.
    holding_message = models.OneToOneField(
        "management.InstagramBotMessage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="degradation_episode_holding",
        db_constraint=False,
    )
    first_source_message_id = models.PositiveBigIntegerField(default=0)
    latest_source_message_id = models.PositiveBigIntegerField(default=0, db_index=True)
    logical_turn_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    holding_sent_at = models.DateTimeField(null=True, blank=True)
    holding_reserved_at = models.DateTimeField(null=True, blank=True)
    inbound_count = models.PositiveIntegerField(default=0)
    suppressed_count = models.PositiveIntegerField(default=0)
    # Фактично надіслані клієнту вибачення в межах цього епізоду. Рахуємо по
    # факту тексту, а не по флагах: holding і recovery складаються разом.
    apology_count = models.PositiveSmallIntegerField(default=0)
    last_decision = models.CharField(max_length=24, blank=True, default="")
    last_decision_reason = models.CharField(max_length=48, blank=True, default="")
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Епізод деградації клієнта IG")
        verbose_name_plural = _("Епізоди деградації клієнтів IG")
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["client", "incident"], name="ig_degradation_episode_unique"
            ),
        ]
        indexes = [
            models.Index(fields=["client", "state", "-id"], name="ig_degradation_client"),
            models.Index(fields=["incident", "state"], name="ig_degradation_incident"),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial representation
        return f"degradation:{self.client_id}:{self.incident_id}:{self.state}"

    @property
    def is_terminal(self) -> bool:
        return self.state in self._TERMINAL_STATES

    @property
    def holding_delivered(self) -> bool:
        return bool(self.holding_sent_at and self.holding_message_id)


class IgCustomerTurn(models.Model):
    """Один логічний хід клієнта — спільне поняття для трьох механізмів (Э0.6).

    Три різні механізми потребують поняття «один логічний хід»: склейка burst-у
    (Э2.2), дедуплікація webhook без `mid` (Э2.11) і provenance відповіді (Э3.6).
    Роздільні реалізації дали б три неузгоджені механізми дедуплікації, а
    найгірший випадок — burst із двох повідомлень, де одне задубльоване
    провайдером, — не обробив би жоден з них правильно.

    **Обмеження схеми, яке не можна обійти.** `IgCommerceSelectionTransition` і
    `IgCommerceTurnDecision` тримають `OneToOneField(source_message)`. Якщо хід
    об'єднує кілька повідомлень, а decision вимагає ОДНУ строку, схема стала б
    суперечливою. Тому `primary_source_message` обов'язковий: він зберігає
    сумісність з наявними OneToOne, поки вони не переведені на хід.
    """

    class ClaimState(models.TextChoices):
        OPEN = "open", _("Відкритий")
        CLAIMED = "claimed", _("Захоплений")
        PROCESSED = "processed", _("Опрацьований")
        SUPERSEDED = "superseded", _("Витіснений")

    client = models.ForeignKey(
        "management.IgClient",
        on_delete=models.CASCADE,
        related_name="customer_turns",
        db_constraint=False,
    )
    episode = models.ForeignKey(
        "management.IgCommercialEpisode",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="customer_turns",
        db_constraint=False,
    )
    # Перше повідомлення ходу. Саме воно підставляється в наявні OneToOne-контракти.
    primary_source_message = models.OneToOneField(
        "management.InstagramBotMessage",
        on_delete=models.CASCADE,
        related_name="primary_customer_turn",
        db_constraint=False,
    )
    window_started_at = models.DateTimeField(default=timezone.now, db_index=True)
    # Дедлайн фіксується від ПЕРШОГО повідомлення і не продовжується наступними:
    # інакше клієнт, який продовжує писати, ніколи не отримав би відповіді.
    window_deadline = models.DateTimeField(db_index=True)
    claim_state = models.CharField(
        max_length=12, choices=ClaimState.choices, default=ClaimState.OPEN, db_index=True
    )
    claimed_at = models.DateTimeField(null=True, blank=True)
    claim_token = models.CharField(max_length=40, blank=True, default="")
    message_count = models.PositiveIntegerField(default=1)
    # Ключі ідентичності повідомлень ходу: native `mid`, provider object id
    # вкладення, або синтетичний ключ. Кілька типів свідомо в одному списку —
    # дедуплікація мусить працювати по будь-якому доступному.
    dedupe_keys = models.JSONField(default=list, blank=True)
    # Postback і quick reply обходять debounce: кнопка — завершена дія, а не
    # частина набору тексту. Це поле, а не комментар у коді.
    bypass_debounce = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Хід клієнта IG")
        verbose_name_plural = _("Ходи клієнтів IG")
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["client", "claim_state", "-id"], name="ig_turn_client_state"),
            models.Index(fields=["claim_state", "window_deadline"], name="ig_turn_due"),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial representation
        return f"turn:{self.client_id}:{self.pk}:{self.claim_state}"

    @property
    def is_open(self) -> bool:
        return self.claim_state == self.ClaimState.OPEN


class IgTurnMessage(models.Model):
    """Append-only зв'язок «хід → повідомлення».

    Сирі повідомлення НЕ видаляються і не зливаються: кожна строка лишається як
    evidence у CRM. Хід лише групує їх.
    """

    turn = models.ForeignKey(
        "management.IgCustomerTurn",
        on_delete=models.CASCADE,
        related_name="turn_messages",
        db_constraint=False,
    )
    # Одне повідомлення належить рівно одному ходу. Унікальність у БД — це і є
    # захист від того, що дублюючий webhook додасть другу строку.
    message = models.OneToOneField(
        "management.InstagramBotMessage",
        on_delete=models.CASCADE,
        related_name="turn_membership",
        db_constraint=False,
    )
    ordinal = models.PositiveSmallIntegerField(default=1)
    role = models.CharField(max_length=8, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("Повідомлення ходу IG")
        verbose_name_plural = _("Повідомлення ходів IG")
        ordering = ["turn_id", "ordinal", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["turn", "ordinal"], name="ig_turn_message_ordinal_unique"
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial representation
        return f"turn_message:{self.turn_id}:{self.ordinal}"
