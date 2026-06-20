"""Блок B: політики мереж у пайплайні чекера (токеносбереження + навчання).

Перед дорогим AI-чеком рушій питає resolve_decision(lead):
- ПІДТВЕРДЖЕНА мережа (confirmed_by != null) з block-політикою → skip без токенів;
- apply_known_verdict → застосувати вердикт мережі без AI;
- recheck_each → повний AI, але з extra_instructions мережі;
- інакше (priority_target/custom_print_only/needs_review/непідтверджена) → повний AI.

Після повного AI-чеку learn_network_from_check() підхоплює сигнал мережі від
моделі (canonical_network_name + suggested_policy) і апсертить LeadNetwork
(suggested_by_ai=True), щоб адмін у UI бачив готові підказки. Авто-навчання
НІКОЛИ не перезаписує підтверджену мережу і не змінює підтверджену політику.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from django.utils import timezone

from management.models import LeadAICheck, LeadNetwork, ManagementLead, NetworkAlias
from management.services import network_resolver

# Оцінка токенів, які економить один пропущений grounded-чек (website + search).
ESTIMATED_TOKENS_PER_FULL_CHECK = 4000

_BLOCK_POLICIES = {LeadNetwork.Policy.BLOCK_NO_COLLAB, LeadNetwork.Policy.BLOCK_IRRELEVANT}
_FULL_AI_POLICIES = {
    LeadNetwork.Policy.PRIORITY_TARGET,
    LeadNetwork.Policy.CUSTOM_PRINT_ONLY,
    LeadNetwork.Policy.NEEDS_REVIEW,
}

# Валідні політики, які модель може запропонувати (suggested_policy).
_AI_SUGGESTABLE_POLICIES = {
    LeadNetwork.Policy.BLOCK_NO_COLLAB,
    LeadNetwork.Policy.BLOCK_IRRELEVANT,
    LeadNetwork.Policy.RECHECK_EACH,
    LeadNetwork.Policy.PRIORITY_TARGET,
}
_AI_KINDS = {c.value for c in LeadNetwork.Kind}


@dataclass
class CheckDecision:
    """Рішення про спосіб перевірки ліда."""
    action: str  # full_ai | skip_block | apply_known | recheck_with_instructions
    verdict_band: str = ""
    extra_instructions: str = ""
    network: LeadNetwork | None = None
    reason: str = ""

    @property
    def is_skip(self) -> bool:
        return self.action in ("skip_block", "apply_known")


def _band_to_score(band: str) -> int:
    return {"fit": 80, "question": 55, "maybe": 50, "unfit": 15}.get(band, 50)


def resolve_decision(lead: ManagementLead) -> CheckDecision:
    """Як перевіряти лід з огляду на ПІДТВЕРДЖЕНУ мережу. Непідтверджені мережі
    (авто/AI-підказки) НЕ впливають — потрібен повний AI."""
    net = getattr(lead, "network", None)
    if net is None or not net.is_confirmed:
        return CheckDecision(action="full_ai", network=net)

    policy = net.policy
    if policy in _BLOCK_POLICIES:
        return CheckDecision(action="skip_block", verdict_band="unfit", network=net, reason=policy)
    if policy == LeadNetwork.Policy.APPLY_KNOWN_VERDICT:
        band = (net.policy_params or {}).get("known_verdict_band") or "maybe"
        return CheckDecision(action="apply_known", verdict_band=band, network=net, reason=policy)
    if policy == LeadNetwork.Policy.RECHECK_EACH:
        return CheckDecision(
            action="recheck_with_instructions",
            extra_instructions=(net.extra_instructions or ""),
            network=net,
        )
    return CheckDecision(action="full_ai", network=net)


def apply_decision(lead: ManagementLead, decision: CheckDecision, *, checked_by=None, job=None) -> LeadAICheck:
    """Застосовує skip/apply-рішення БЕЗ виклику Gemini: створює полегшений
    LeadAICheck(DONE), оновлює кеш-поля ліда, інкрементує лічильники мережі."""
    from management.services import lead_checker

    band = decision.verdict_band or "maybe"
    score = _band_to_score(band)
    policy_label = dict(LeadNetwork.Policy.choices).get(decision.reason, decision.reason)
    net_name = decision.network.canonical_name if decision.network else ""
    comment = (
        f"Пропущено AI-чек за політикою мережі «{net_name}»: {policy_label}. "
        f"Вердикт застосовано без витрати токенів."
    )
    check = LeadAICheck.objects.create(
        lead=lead, job=job, status=LeadAICheck.Status.DONE, checked_by=checked_by,
        overall_score=score, verdict_band=band, verdict_category="retail_chain",
        confidence="high", model_used=f"(policy:{decision.reason})", comment=comment,
        signals={"network_policy": decision.reason, "network": net_name},
        tokens={},
    )
    lead.ai_score = score
    lead.ai_verdict = band
    lead.ai_checked_at = timezone.now()
    lead.niche_status = lead_checker.niche_for_band(band)
    lead.save(update_fields=["ai_score", "ai_verdict", "ai_checked_at", "niche_status", "updated_at"])

    net = decision.network
    if net is not None:
        net.skipped_count = (net.skipped_count or 0) + 1
        net.tokens_saved = (net.tokens_saved or 0) + ESTIMATED_TOKENS_PER_FULL_CHECK
        net.save(update_fields=["skipped_count", "tokens_saved", "updated_at"])
    check._duration_seconds = 0.0
    return check


def learn_network_from_check(lead: ManagementLead, check: LeadAICheck) -> LeadNetwork | None:
    """Post-AI: якщо модель ідентифікувала мережу — апсертить LeadNetwork
    (suggested_by_ai) і привʼязує лід. НЕ чіпає підтверджені мережі/політики."""
    sig = check.signals if isinstance(check.signals, dict) else {}
    name = (sig.get("canonical_network_name") or "").strip()
    if not name:
        return None
    # Не перезаписуємо підтверджену привʼязку ліда.
    current = getattr(lead, "network", None)
    if current is not None and current.is_confirmed:
        return current

    key = network_resolver.network_match_key(name)
    if not key:
        return None

    suggested_policy = (sig.get("suggested_policy") or "").strip()
    kind = (sig.get("network_kind") or "").strip()
    alias = (
        NetworkAlias.objects
        .filter(key_type=NetworkAlias.KeyType.NAME, key_value=key)
        .select_related("network").first()
    )
    if alias:
        net = alias.network
    else:
        net = LeadNetwork.objects.create(
            canonical_name=name,
            slug=network_resolver._unique_slug(name),
            policy=LeadNetwork.Policy.NEEDS_REVIEW,
            suggested_by_ai=True,
        )
        NetworkAlias.objects.create(
            network=net, key_type=NetworkAlias.KeyType.NAME, key_value=key, source="ai",
        )

    update_fields = []
    # AI-підказку політики застосовуємо лише поки мережа НЕ підтверджена і ще
    # на дефолтному needs_review (щоб не перетирати ручні рішення).
    if (
        not net.is_confirmed
        and net.policy == LeadNetwork.Policy.NEEDS_REVIEW
        and suggested_policy in _AI_SUGGESTABLE_POLICIES
    ):
        net.policy = suggested_policy
        update_fields.append("policy")
    if not net.is_confirmed and kind in _AI_KINDS and net.kind == LeadNetwork.Kind.UNKNOWN:
        net.kind = kind
        update_fields.append("kind")
    if not net.suggested_by_ai:
        net.suggested_by_ai = True
        update_fields.append("suggested_by_ai")
    if not net.ai_rationale and (check.brand_summary or check.comment):
        net.ai_rationale = (check.brand_summary or check.comment or "")[:1000]
        update_fields.append("ai_rationale")
    if update_fields:
        update_fields.append("updated_at")
        net.save(update_fields=update_fields)

    # Привʼязуємо лід (лише авто/порожнє джерело — ручне не чіпаємо).
    if lead.network_membership_source in ("", "auto", "ai") and lead.network_id != net.id:
        lead.network = net
        lead.network_membership_source = "ai"
        lead.needs_disambiguation = False
        lead.save(update_fields=["network", "network_membership_source", "needs_disambiguation", "updated_at"])
        net.members_count = net.leads.count()
        net.save(update_fields=["members_count", "updated_at"])
    return net
