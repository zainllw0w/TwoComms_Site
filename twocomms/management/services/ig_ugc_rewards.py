"""Manager-reviewed UGC rewards for assigned Instagram orders."""

from __future__ import annotations

import hashlib
import secrets
import string
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlsplit, urlunsplit

from django.db import transaction
from django.utils import timezone

from orders.fulfillment_truth import nova_poshta_order_fulfillment_confirmed


class UgcRewardConflict(ValueError):
    """The evidence cannot authorize a reward for this order."""


def _normalize_instagram_url(raw_url: str) -> str:
    value = str(raw_url or "").strip()
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme.lower() != "https" or not (
        host == "instagram.com" or host.endswith(".instagram.com")
    ):
        raise UgcRewardConflict("Потрібне HTTPS-посилання на Instagram.")
    if not parsed.path or parsed.path == "/":
        raise UgcRewardConflict("Посилання Instagram не містить публікацію або stories.")
    netloc = host
    if parsed.port:
        netloc = f"{host}:{parsed.port}"
    path = parsed.path.rstrip("/") + "/"
    return urlunsplit(("https", netloc, path, "", ""))


def _fingerprint(kind: str, value: str) -> str:
    return hashlib.sha256(f"{kind}:{value}".encode("utf-8")).hexdigest()


def _new_promo_code() -> str:
    from storefront.models import PromoCode

    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "UGC" + "".join(secrets.choice(alphabet) for _ in range(9))
        if not PromoCode.objects.filter(code=code).exists():
            return code


def reward_payload(reward) -> dict:
    return {
        "id": reward.pk,
        "client_id": reward.client_id,
        "order_id": reward.order_id,
        "order_number": reward.order.order_number or str(reward.order_id),
        "assignment_id": reward.assignment_id,
        "assignment_version": reward.assignment_version,
        "evidence_type": reward.evidence_type,
        "evidence_message_id": reward.evidence_message_id,
        "evidence_url": reward.evidence_url,
        "review_note": reward.review_note,
        "promo_code": reward.promo_code.code,
        "valid_until": (
            reward.promo_code.valid_until.isoformat()
            if reward.promo_code.valid_until
            else ""
        ),
        "reviewed_by": (
            reward.reviewed_by.get_full_name()
            or reward.reviewed_by.get_username()
        ),
        "reviewed_at": reward.reviewed_at.isoformat(),
    }


@transaction.atomic
def award_ugc_reward(
    *,
    client,
    order,
    actor,
    evidence_message_id=None,
    evidence_url="",
    review_note="",
):
    """Issue one 10% promo after a manager verifies one UGC proof."""

    from management.ig_bot_models import IgOrderAssignment, IgUgcReward
    from management.models import InstagramBotMessage
    from orders.models import Order
    from storefront.models import PromoCode

    message_id = str(evidence_message_id or "").strip()
    raw_url = str(evidence_url or "").strip()
    if bool(message_id) == bool(raw_url):
        raise UgcRewardConflict("Вкажіть одне підтвердження: повідомлення Direct або Instagram URL.")
    if actor is None or not getattr(actor, "is_authenticated", False):
        raise UgcRewardConflict("Потрібен авторизований менеджер.")

    locked_order = Order.objects.select_for_update().get(pk=getattr(order, "pk", order))
    assignment = (
        IgOrderAssignment.objects.select_for_update()
        .filter(
            order_id=locked_order.pk,
            client_id=getattr(client, "pk", client),
            unassigned_at__isnull=True,
        )
        .first()
    )
    if assignment is None:
        raise UgcRewardConflict("Замовлення не має поточної прив'язки до цього Instagram-клієнта.")
    if not nova_poshta_order_fulfillment_confirmed(locked_order):
        raise UgcRewardConflict(
            "Нагороду можна видати лише після підтвердженого отримання замовлення."
        )

    evidence_message = None
    normalized_url = ""
    if message_id:
        try:
            evidence_message = (
                InstagramBotMessage.objects.select_for_update()
                .get(pk=int(message_id))
            )
        except (InstagramBotMessage.DoesNotExist, TypeError, ValueError):
            raise UgcRewardConflict("Повідомлення Direct не знайдено.") from None
        if (
            evidence_message.client_id != assignment.client_id
            or evidence_message.role != InstagramBotMessage.Role.USER
        ):
            raise UgcRewardConflict("Доказом може бути лише повідомлення цього клієнта.")
        evidence_type = IgUgcReward.EvidenceType.DIRECT_MESSAGE
        fingerprint = _fingerprint(evidence_type, str(evidence_message.pk))
    else:
        normalized_url = _normalize_instagram_url(raw_url)
        evidence_type = IgUgcReward.EvidenceType.INSTAGRAM_URL
        fingerprint = _fingerprint(evidence_type, normalized_url)

    existing = (
        IgUgcReward.objects.select_for_update()
        .select_related("order", "promo_code", "reviewed_by")
        .filter(order_id=locked_order.pk)
        .first()
    )
    if existing is not None:
        if existing.evidence_fingerprint == fingerprint:
            return existing, False
        raise UgcRewardConflict("Для цього замовлення нагороду вже видано за іншим доказом.")
    if IgUgcReward.objects.filter(evidence_fingerprint=fingerprint).exists():
        raise UgcRewardConflict("Цей доказ уже використано для іншої нагороди.")

    now = timezone.now()
    promo = PromoCode.objects.create(
        code=_new_promo_code(),
        promo_type="regular",
        discount_type="percentage",
        discount_value=Decimal("10.00"),
        description=f"UGC reward for Instagram order {locked_order.order_number or locked_order.pk}",
        max_uses=1,
        one_time_per_user=True,
        valid_from=now,
        valid_until=now + timedelta(days=90),
        is_active=True,
    )
    reward = IgUgcReward.objects.create(
        client_id=assignment.client_id,
        order=locked_order,
        assignment=assignment,
        assignment_version=assignment.version,
        evidence_type=evidence_type,
        evidence_message=evidence_message,
        evidence_url=normalized_url,
        evidence_fingerprint=fingerprint,
        review_note=str(review_note or "").strip()[:1000],
        promo_code=promo,
        reviewed_by=actor,
        reviewed_at=now,
    )
    return reward, True
