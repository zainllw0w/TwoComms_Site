"""Блок D: API керування мережами лідів (перегляд / підтвердження / політика).

Підтвердження мережі (confirmed_by) активує токеносбереження Блоку B:
рушій чекера починає застосовувати політику (skip/apply/recheck) для її лідів.
"""
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import LeadNetwork, ManagementLead
from .parsing_views import _require_admin_json

NETWORKS_PAGE_SIZE = 24
_POLICY_LABELS = dict(LeadNetwork.Policy.choices)
_KIND_LABELS = dict(LeadNetwork.Kind.choices)
_VALID_POLICIES = {c.value for c in LeadNetwork.Policy}
_VALID_BANDS = {"fit", "question", "maybe", "unfit"}


def serialize_network(net: LeadNetwork, *, with_members: bool = True, members_limit: int = 12) -> dict:
    members = []
    if with_members:
        for lead in net.leads.all().order_by("-id")[:members_limit]:
            members.append({
                "lead_id": lead.id,
                "shop_name": lead.shop_name,
                "city": lead.city,
                "phone": lead.phone,
                "website_url": lead.website_url,
                "ai_verdict": lead.ai_verdict or "",
                "ai_score": lead.ai_score,
            })
    return {
        "id": net.id,
        "canonical_name": net.canonical_name,
        "slug": net.slug,
        "kind": net.kind,
        "kind_label": _KIND_LABELS.get(net.kind, net.kind),
        "policy": net.policy,
        "policy_label": _POLICY_LABELS.get(net.policy, net.policy),
        "policy_params": net.policy_params or {},
        "extra_instructions": net.extra_instructions or "",
        "members_count": net.members_count,
        "skipped_count": net.skipped_count,
        "tokens_saved": int(net.tokens_saved or 0),
        "is_confirmed": net.is_confirmed,
        "suggested_by_ai": net.suggested_by_ai,
        "ai_rationale": net.ai_rationale or "",
        "updated_at": net.updated_at.isoformat() if net.updated_at else None,
        "members": members,
    }


def _networks_queryset(*, q: str, policy: str, state: str):
    qs = LeadNetwork.objects.all()
    if q:
        qs = qs.filter(canonical_name__icontains=q.strip())
    if policy and policy in _VALID_POLICIES:
        qs = qs.filter(policy=policy)
    if state == "confirmed":
        qs = qs.filter(confirmed_by__isnull=False)
    elif state == "suggested":
        qs = qs.filter(suggested_by_ai=True, confirmed_by__isnull=True)
    elif state == "needs_review":
        qs = qs.filter(policy=LeadNetwork.Policy.NEEDS_REVIEW, confirmed_by__isnull=True)
    # «найвпливовіші» спершу: більше точок → більший сенс політики.
    return qs.order_by("-members_count", "-updated_at")


@login_required(login_url="management_login")
@require_GET
def networks_list_api(request):
    denied = _require_admin_json(request)
    if denied:
        return denied
    q = request.GET.get("q", "")
    policy = request.GET.get("policy", "")
    state = request.GET.get("state", "all")
    try:
        page = max(1, int(request.GET.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    qs = _networks_queryset(q=q, policy=policy, state=state).prefetch_related("leads")
    paginator = Paginator(qs, NETWORKS_PAGE_SIZE)
    page_obj = paginator.get_page(page)
    rows = [serialize_network(n) for n in page_obj.object_list]
    base = LeadNetwork.objects.all()
    stats = {
        "total": base.count(),
        "confirmed": base.filter(confirmed_by__isnull=False).count(),
        "suggested": base.filter(suggested_by_ai=True, confirmed_by__isnull=True).count(),
        "tokens_saved": int(sum(base.values_list("tokens_saved", flat=True)) or 0),
    }
    return JsonResponse({"success": True, "networks": {
        "rows": rows,
        "page": page_obj.number,
        "num_pages": paginator.num_pages,
        "total": paginator.count,
        "stats": stats,
        "policy_choices": [{"value": v, "label": l} for v, l in LeadNetwork.Policy.choices],
    }})


@login_required(login_url="management_login")
@require_POST
def network_update_api(request, network_id):
    denied = _require_admin_json(request)
    if denied:
        return denied
    net = LeadNetwork.objects.filter(id=network_id).first()
    if net is None:
        return JsonResponse({"success": False, "error": "Мережу не знайдено."}, status=404)

    action = request.POST.get("action", "")

    if action == "reject_leads":
        # «Відхилити всю мережу» (кейс «Мілітарист»): блок-політика + масовий REJECTED усіх точок.
        net.policy = LeadNetwork.Policy.BLOCK_NO_COLLAB
        net.confirmed_by = request.user
        net.confirmed_at = timezone.now()
        net.save(update_fields=["policy", "confirmed_by", "confirmed_at", "updated_at"])
        reason = (request.POST.get("rejection_reason") or "").strip() or "Мережа не співпрацює (масове відхилення)"
        rejected_count = (
            ManagementLead.objects.filter(network=net)
            .exclude(status=ManagementLead.Status.REJECTED)
            .update(
                status=ManagementLead.Status.REJECTED,
                moderated_by=request.user,
                rejection_reason=reason,
                updated_at=timezone.now(),
            )
        )
        net.refresh_from_db()
        return JsonResponse({"success": True, "network": serialize_network(net), "rejected_count": rejected_count})

    fields = []

    policy = request.POST.get("policy", "")
    if policy:
        if policy not in _VALID_POLICIES:
            return JsonResponse({"success": False, "error": "Невідома політика."}, status=400)
        net.policy = policy
        fields.append("policy")

    if request.POST.get("extra_instructions") is not None:
        net.extra_instructions = request.POST.get("extra_instructions", "").strip()
        fields.append("extra_instructions")

    band = request.POST.get("known_verdict_band", "")
    if band:
        if band not in _VALID_BANDS:
            return JsonResponse({"success": False, "error": "Невідомий вердикт."}, status=400)
        params = dict(net.policy_params or {})
        params["known_verdict_band"] = band
        net.policy_params = params
        fields.append("policy_params")

    if action == "confirm":
        net.confirmed_by = request.user
        net.confirmed_at = timezone.now()
        fields += ["confirmed_by", "confirmed_at"]
    elif action == "unconfirm":
        net.confirmed_by = None
        net.confirmed_at = None
        fields += ["confirmed_by", "confirmed_at"]

    if fields:
        fields.append("updated_at")
        net.save(update_fields=list(dict.fromkeys(fields)))
    net.refresh_from_db()
    return JsonResponse({"success": True, "network": serialize_network(net)})
