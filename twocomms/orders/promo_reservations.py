"""Cross-channel promo reservation and consumption primitives.

Every account-scoped checkout serializes on the owning promo group (or on the
promo itself for an ungrouped one-time code). Production therefore requires
``storefront_promocodegroup`` to use InnoDB; migration 0087 enforces that.
"""

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.utils import timezone


ACTIVE_RESERVATION_STATES = frozenset({"reserved", "consumed"})


class PromoReservationError(ValueError):
    def __init__(self, reason="invalid"):
        self.reason = str(reason or "invalid")
        super().__init__(self.reason)


@dataclass(frozen=True)
class PromoReservation:
    promo: object
    discount: Decimal
    event_state: dict


def _authenticated_user_id(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    return user.pk


def _has_committed_usage(*, promo, group, user_id):
    from storefront.models import PromoCodeUsage

    usages = PromoCodeUsage.objects.filter(user_id=user_id)
    if group is not None and group.one_per_account:
        return usages.filter(group_id=group.pk).exists()
    if promo.one_time_per_user:
        return usages.filter(promo_code_id=promo.pk).exists()
    return False


def has_active_account_reservation(*, promo, group, user_id):
    """Check durable PaymentAttempt reservations across every checkout surface."""
    from orders.models import PaymentAttempt

    attempts = PaymentAttempt.objects.filter(user_id=user_id)
    if group is not None and group.one_per_account:
        attempts = attempts.filter(promo_code__group_id=group.pk)
    elif promo.one_time_per_user:
        attempts = attempts.filter(promo_code_id=promo.pk)
    else:
        return False
    for event_state in attempts.values_list("event_state", flat=True):
        reservation = dict((event_state or {}).get("promo_reservation") or {})
        if reservation.get("state") in ACTIVE_RESERVATION_STATES:
            return True
    return False


def _lock_promo(*, promo_id=None, code=None):
    from storefront.models import PromoCode, PromoCodeGroup

    locator = PromoCode.objects.all()
    if promo_id is not None:
        locator = locator.filter(pk=promo_id)
    else:
        locator = locator.filter(code__iexact=str(code or "").strip())
    identity = locator.values("pk", "group_id").first()
    if identity is None:
        raise PromoReservationError("invalid")

    group = None
    if identity["group_id"]:
        group = (
            PromoCodeGroup.objects.select_for_update()
            .filter(pk=identity["group_id"])
            .first()
        )
        if group is None or not group.is_active:
            raise PromoReservationError("inactive_group")

    promo = (
        PromoCode.objects.select_for_update()
        .select_related("group")
        .get(pk=identity["pk"])
    )
    if group is not None:
        promo.group = group
    return promo, group


@transaction.atomic
def reserve_promo_for_checkout(*, promo_id=None, code=None, user=None, total_amount):
    """Validate and reserve one promo before creating an external invoice."""
    promo, group = _lock_promo(promo_id=promo_id, code=code)
    if not promo.can_be_used():
        raise PromoReservationError("invalid")

    user_id = _authenticated_user_id(user)
    account_scoped = bool(
        promo.one_time_per_user
        or (group is not None and group.one_per_account)
    )
    if account_scoped and user_id is None:
        raise PromoReservationError("account_required")
    if account_scoped and (
        _has_committed_usage(promo=promo, group=group, user_id=user_id)
        or has_active_account_reservation(
            promo=promo,
            group=group,
            user_id=user_id,
        )
    ):
        raise PromoReservationError("already_reserved_or_used")

    total = Decimal(str(total_amount or 0))
    discount = min(Decimal(str(promo.calculate_discount(total))), total)
    if discount <= 0:
        raise PromoReservationError("not_applicable")

    promo.current_uses += 1
    promo.save(update_fields=["current_uses", "updated_at"])
    return PromoReservation(
        promo=promo,
        discount=discount,
        event_state={
            "promo_reservation": {
                "promo_id": promo.pk,
                "group_id": promo.group_id,
                "state": "reserved",
                "capacity_reserved": True,
                "reserved_at": timezone.now().isoformat(),
            }
        },
    )


@transaction.atomic
def record_immediate_promo_usage(*, promo_id, user, order):
    """Atomically reserve and consume a promo for an immediately placed order."""
    total = getattr(order, "total_sum", None) or getattr(order, "final_total", None) or 0
    reservation = reserve_promo_for_checkout(
        promo_id=promo_id,
        user=user,
        total_amount=total,
    )
    from storefront.models import PromoCodeUsage

    usage = PromoCodeUsage.objects.create(
        user=user,
        promo_code=reservation.promo,
        group=reservation.promo.group,
        order=order,
    )
    return usage


def consume_payment_attempt_promo(attempt, *, order):
    """Consume a reserved slot only after its usage row exists.

    Payment truth must still materialize if usage persistence has an operational
    failure. In that case the reservation deliberately stays ``reserved`` so a
    second code in the same account scope remains blocked until reconciliation.
    """
    promo = attempt.promo_code
    if promo is None:
        return True

    event_state = dict(attempt.event_state or {})
    reservation = dict(event_state.get("promo_reservation") or {})
    was_reserved = (
        reservation.get("state") == "reserved"
        and int(reservation.get("promo_id") or 0) == promo.pk
    )
    try:
        with transaction.atomic():
            if attempt.user_id:
                from storefront.models import PromoCodeUsage

                usage = PromoCodeUsage.objects.filter(order=order).first()
                if usage is None:
                    PromoCodeUsage.objects.create(
                        user=attempt.user,
                        promo_code=promo,
                        group=promo.group,
                        order=order,
                    )
            elif not was_reserved:
                promo.use()
    except Exception as exc:
        reservation.update({
            "promo_id": promo.pk,
            "group_id": promo.group_id,
            "state": "reserved",
            "usage_error_at": timezone.now().isoformat(),
            "usage_error": str(exc)[:200],
        })
        event_state["promo_reservation"] = reservation
        attempt.event_state = event_state
        return False

    if not was_reserved and attempt.user_id:
        # Legacy attempts did not reserve capacity before provider I/O.
        promo.use()
    reservation.update({
        "promo_id": promo.pk,
        "group_id": promo.group_id,
        "state": "consumed",
        "consumed_at": timezone.now().isoformat(),
        "order_id": order.pk,
    })
    event_state["promo_reservation"] = reservation
    attempt.event_state = event_state
    return True


@transaction.atomic
def release_payment_attempt_promo(attempt, *, reason="payment_terminal"):
    """Release one invoice reservation exactly once."""
    from orders.models import PaymentAttempt
    from storefront.models import PromoCode

    locked = PaymentAttempt.objects.select_for_update().get(pk=attempt.pk)
    event_state = dict(locked.event_state or {})
    reservation = dict(event_state.get("promo_reservation") or {})
    if reservation.get("state") != "reserved":
        return False
    promo_id = reservation.get("promo_id") or locked.promo_code_id
    promo = PromoCode.objects.select_for_update().filter(pk=promo_id).first()
    if (
        promo is not None
        and reservation.get("capacity_reserved", True)
        and promo.current_uses > 0
    ):
        promo.current_uses -= 1
        promo.save(update_fields=["current_uses", "updated_at"])
    reservation.update({
        "state": "released",
        "released_at": timezone.now().isoformat(),
        "release_reason": str(reason or "payment_terminal")[:128],
    })
    event_state["promo_reservation"] = reservation
    locked.event_state = event_state
    locked.save(update_fields=["event_state", "updated"])
    return True
