"""Deterministic Assisted Checkout V2 payment-policy evidence."""
from __future__ import annotations

import re
from dataclasses import dataclass

from django.core.signing import salted_hmac


PROPOSAL_TTL_SECONDS = 12 * 60 * 60
GENERATION_TTL_SECONDS = 25 * 60
PROVIDER_VALIDITY_SECONDS = 1500
PREPAY_200_AMOUNT = "200.00"

PREPAY_200_QUICK_REPLY = "twc:v1:checkout_payment:prepay_200_cod"
_DIRECT_PREPAY_QUESTION_RE = re.compile(
    r"(?:\b(?:200|двісті|двести)\s*(?:грн|uah|₴)?\b.{0,80}"
    r"(?:передоплат|предоплат|післяплат|налож|cod|cash\s+on\s+delivery)"
    r"|(?:передоплат|предоплат|післяплат|налож|cod|cash\s+on\s+delivery)"
    r".{0,80}\b(?:200|двісті|двести)\s*(?:грн|uah|₴)?\b)",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True, slots=True)
class PaymentPolicyDecision:
    policy: str
    evidence_message_id: int | None = None
    evidence_kind: str = ""
    evidence_revision: int = 0
    evidence_digest: str = ""
    custom_print_full_only: bool = False


def _evidence_digest(*, client_id: int, message_id: int, kind: str) -> str:
    return salted_hmac(
        "management.assisted-checkout-v2.payment-policy",
        f"{int(client_id)}:{int(message_id)}:{kind}",
        algorithm="sha256",
    ).hexdigest()[:64]


def resolve_payment_policy(
    *,
    client,
    evidence_message_ids=(),
    custom_print_full_only=False,
) -> PaymentPolicyDecision:
    """Only the current customer's latest direct turn may unlock 200+COD."""
    from management.models import IgCheckoutProposal, InstagramBotMessage
    from management.services.ig_funnel_reset import current_message_floor

    if custom_print_full_only:
        return PaymentPolicyDecision(
            policy=IgCheckoutProposal.PaymentPolicy.FULL_ONLY,
            custom_print_full_only=True,
        )
    evidence_ids = {
        int(value)
        for value in evidence_message_ids or ()
        if str(value).isdigit() and int(value) > 0
    }
    if not evidence_ids:
        return PaymentPolicyDecision(
            policy=IgCheckoutProposal.PaymentPolicy.FULL_ONLY
        )
    floor = current_message_floor(client)
    latest = (
        InstagramBotMessage.objects.filter(
            client_id=client.pk,
            role=InstagramBotMessage.Role.USER,
            pk__gte=floor,
        )
        .order_by("-pk")
        .only("pk", "text", "quick_reply_payload")
        .first()
    )
    if latest is None or latest.pk not in evidence_ids:
        return PaymentPolicyDecision(
            policy=IgCheckoutProposal.PaymentPolicy.FULL_ONLY
        )
    if latest.quick_reply_payload == PREPAY_200_QUICK_REPLY:
        kind = "quick_reply"
    elif _DIRECT_PREPAY_QUESTION_RE.search(str(latest.text or "")):
        kind = "direct_question"
    else:
        return PaymentPolicyDecision(
            policy=IgCheckoutProposal.PaymentPolicy.FULL_ONLY
        )
    return PaymentPolicyDecision(
        policy=IgCheckoutProposal.PaymentPolicy.FULL_OR_200_COD,
        evidence_message_id=latest.pk,
        evidence_kind=kind,
        evidence_revision=latest.pk,
        evidence_digest=_evidence_digest(
            client_id=client.pk,
            message_id=latest.pk,
            kind=kind,
        ),
    )


def payment_choice_for_post(proposal, raw_choice: object):
    """Validate browser choice against immutable server-side policy."""
    from management.models import IgCheckoutInvoiceGeneration, IgCheckoutProposal

    choice = str(raw_choice or "online_full").strip().casefold()
    if choice in {"", "full", "online_full"}:
        return IgCheckoutInvoiceGeneration.PaymentChoice.FULL
    if choice != IgCheckoutInvoiceGeneration.PaymentChoice.PREPAY_200_COD:
        raise ValueError("forged_payment_choice")
    if (
        not proposal.assisted_checkout_v2
        or proposal.custom_print_full_only
        or proposal.payment_policy
        != IgCheckoutProposal.PaymentPolicy.FULL_OR_200_COD
        or not proposal.payment_policy_evidence_message_id
        or proposal.payment_policy_evidence_kind
        not in {"direct_question", "quick_reply"}
        or not re.fullmatch(
            r"[0-9a-f]{64}",
            str(proposal.payment_policy_evidence_digest or ""),
        )
    ):
        raise ValueError("forged_payment_choice")
    return IgCheckoutInvoiceGeneration.PaymentChoice.PREPAY_200_COD
