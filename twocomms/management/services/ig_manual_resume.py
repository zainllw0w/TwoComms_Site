"""Explicit, client-scoped return from manager ownership to automation."""
from __future__ import annotations

from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from management.models import (
    IgAiReplyRecoveryJob,
    IgClient,
    IgCommerceTurnDecision,
    IgCustomerTurn,
    IgPermissionTransitionJob,
    IgTurnMessage,
    InstagramBotMessage,
    InstagramBotSettings,
)
from management.services.ig_permission_transitions import (
    ACTIVE_STATUSES,
    cancel_client_unstarted_automation,
    supersede_permission_transitions,
)
from management.services.ig_reply_boundary import pause_reply_boundary


@dataclass(frozen=True)
class ManualResumeResult:
    client_id: int
    changed: bool
    permission_epoch: int
    successor_turn_id: int | None = None
    successor_source_message_id: int | None = None
    successor_created: bool = False
    unresolved_turn_id: int | None = None
    unresolved_source_message_id: int | None = None
    successor_reason: str = ""
    cancelled: dict[str, int] = field(default_factory=dict)


class ManualResumeRejected(ValueError):
    def __init__(self, code: str, message: str, *, status: int = 409):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _active_opt_out(client: IgClient) -> bool:
    recorded = bool(
        client.opted_out_at
        and (not client.opted_in_at or client.opted_in_at < client.opted_out_at)
    )
    pending = IgPermissionTransitionJob.objects.filter(
        client_id=client.pk,
        kind=IgPermissionTransitionJob.Kind.OPT_OUT,
        status__in=ACTIVE_STATUSES,
    ).exists()
    return recorded or pending


def _reject_ineligible_client(client: IgClient) -> None:
    if client.hidden_at:
        raise ManualResumeRejected(
            "client_hidden",
            "Прихованого клієнта спочатку потрібно окремо повернути до активних.",
        )
    if client.privacy_erasure_started_at:
        raise ManualResumeRejected(
            "privacy_erasure_active",
            "Відновлення недоступне під час видалення даних клієнта.",
        )
    if client.is_blocked:
        raise ManualResumeRejected(
            "client_blocked",
            "Заблокованого клієнта не можна передати автоматизації.",
        )
    if _active_opt_out(client):
        raise ManualResumeRejected(
            "active_opt_out",
            (
                "Клієнт відмовився від автоматичних повідомлень. "
                "Щоб повернути бота, спочатку потрібно окремо "
                "підтвердити нову згоду клієнта."
            ),
        )


def _dangerous_delivery_exists(client_id: int, source_ids: list[int]) -> bool:
    dangerous_send_states = ("sending", "unknown", "ambiguous")
    if InstagramBotMessage.objects.filter(
        client_id=client_id,
        send_state__in=dangerous_send_states,
    ).filter(Q(pk__in=source_ids) | Q(role__in=(
        InstagramBotMessage.Role.MODEL,
        InstagramBotMessage.Role.MANAGER,
    ), id__gt=max(source_ids))).exists():
        return True
    if IgAiReplyRecoveryJob.objects.filter(
        client_id=client_id,
        source_message_id__in=source_ids,
    ).filter(
        Q(status__in=(
            IgAiReplyRecoveryJob.Status.PROCESSING,
            IgAiReplyRecoveryJob.Status.SENDING,
            IgAiReplyRecoveryJob.Status.AMBIGUOUS,
        ))
        | Q(reply_message__send_state__in=dangerous_send_states)
    ).exists():
        return True
    return IgCommerceTurnDecision.objects.filter(
        source_message_id__in=source_ids,
        delivery_state__in=(
            IgCommerceTurnDecision.DeliveryState.SENDING,
            IgCommerceTurnDecision.DeliveryState.UNKNOWN,
            IgCommerceTurnDecision.DeliveryState.PARTIAL,
        ),
    ).exists()


def _latest_unanswered_reference(client: IgClient):
    source = (
        InstagramBotMessage.objects.filter(
            client_id=client.pk,
            role=InstagramBotMessage.Role.USER,
        )
        .order_by("-id")
        .first()
    )
    if source is None:
        return None, None, "no_customer_request"

    from management.services.ig_reply_expectation import classify

    if not classify(source).substantive_reply_owed:
        return None, None, "latest_turn_needs_no_reply"

    manager_answered = InstagramBotMessage.objects.filter(
        client_id=client.pk,
        role=InstagramBotMessage.Role.MANAGER,
        id__gt=source.pk,
    ).exclude(status=InstagramBotMessage.Status.FAILED).exists()
    if manager_answered:
        return None, None, "manager_answered"

    model_answered = InstagramBotMessage.objects.filter(
        client_id=client.pk,
        role=InstagramBotMessage.Role.MODEL,
        id__gt=source.pk,
    ).exclude(status=InstagramBotMessage.Status.FAILED).filter(
        Q(provider_message_id__gt="") | Q(send_state="sent")
    ).exists()
    if model_answered:
        return None, None, "model_answered"

    membership = (
        IgTurnMessage.objects.select_related("turn")
        .filter(message_id=source.pk)
        .first()
    )
    if membership is None:
        turn = None
    else:
        turn = membership.turn
    if turn is None:
        return None, source, "customer_turn_unavailable"
    if turn.claim_state == IgCustomerTurn.ClaimState.CLAIMED:
        return None, None, "turn_execution_in_progress"
    if turn.claim_state == IgCustomerTurn.ClaimState.SUPERSEDED:
        return None, None, "turn_superseded"
    if turn.terminal_reason in {
        IgCustomerTurn.TerminalReason.REPLIED,
        IgCustomerTurn.TerminalReason.SEND_UNKNOWN,
    }:
        return None, None, "turn_delivery_already_crossed"

    from management.services.ig_customer_turns import (
        claimable_row_id,
        turn_message_ids,
    )

    source_ids = turn_message_ids(turn) or [source.pk]
    claimable_id = claimable_row_id(turn)
    claimable = InstagramBotMessage.objects.filter(
        pk=claimable_id,
        client_id=client.pk,
        role=InstagramBotMessage.Role.USER,
        status=InstagramBotMessage.Status.DONE,
        send_state="",
    ).first()
    if claimable is None:
        return None, None, "turn_not_safely_replayable"
    if _dangerous_delivery_exists(client.pk, source_ids):
        return None, None, "delivery_reconciliation_required"
    # IgCustomerTurn.primary_source_message and IgTurnMessage are one-to-one
    # historical evidence.  The current schema has no immutable successor
    # revision, so B02.2 must leave the turn untouched rather than re-open it.
    return turn, claimable, "successor_revision_unavailable"


def resume_client_automation(client_id: int, *, actor=None) -> ManualResumeResult:
    """Resume one client only after an explicit authorized operator command.

    Consent is deliberately outside this transition.  Existing valid consent is
    preserved, while an active opt-out always rejects the command.
    """
    with pause_reply_boundary():
        with transaction.atomic():
            client = (
                IgClient.objects.select_for_update()
                .filter(pk=client_id)
                .first()
            )
            if client is None:
                raise ManualResumeRejected(
                    "client_not_found", "Клієнта не знайдено.", status=404
                )
            _reject_ineligible_client(client)
            if not client.bot_paused and not client.manager_takeover:
                return ManualResumeResult(
                    client_id=client.pk,
                    changed=False,
                    permission_epoch=int(client.reply_permission_epoch or 0),
                    successor_reason="already_resumed",
                )

            now = timezone.now()
            supersede_permission_transitions(
                client_id=client.pk,
                kinds=(
                    IgPermissionTransitionJob.Kind.MANAGER_TAKEOVER,
                    IgPermissionTransitionJob.Kind.CLIENT_PAUSE,
                ),
            )
            cancelled = cancel_client_unstarted_automation(
                client,
                reason="manual_resume_reconcile",
                now=now,
                nowait=False,
            )

            client.bot_paused = False
            client.manager_takeover = False
            client.paused_reason = ""
            client.paused_at = None
            client.reply_permission_epoch = int(client.reply_permission_epoch or 0) + 1
            client.save(update_fields=[
                "bot_paused",
                "manager_takeover",
                "paused_reason",
                "paused_at",
                "reply_permission_epoch",
                "updated_at",
            ])

            turn = source = None
            successor_reason = "global_reply_paused"
            if InstagramBotSettings.load().is_enabled:
                turn, source, successor_reason = _latest_unanswered_reference(client)

            from management.services.instagram_bot import log

            actor_id = int(getattr(actor, "pk", 0) or 0)
            previous_epoch = int(client.reply_permission_epoch or 0) - 1
            log(
                "info",
                "manual_resume",
                (
                    f"client={client.pk}; user={actor_id}; "
                    f"epoch={previous_epoch}->{client.reply_permission_epoch}; "
                    f"successor={successor_reason}"
                ),
            )

            return ManualResumeResult(
                client_id=client.pk,
                changed=True,
                permission_epoch=int(client.reply_permission_epoch or 0),
                successor_created=False,
                unresolved_turn_id=turn.pk if turn is not None else None,
                unresolved_source_message_id=source.pk if source is not None else None,
                successor_reason=successor_reason,
                cancelled=cancelled,
            )
