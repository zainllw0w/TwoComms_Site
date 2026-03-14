from __future__ import annotations


def build_why_changed_today(*, summary: dict, shadow_score: dict) -> list[dict]:
    items = []
    kpd_delta = float(summary.get("kpd_delta") or 0)
    if kpd_delta:
        items.append(
            {
                "tone": "positive" if kpd_delta > 0 else "negative",
                "label": "Legacy KPD",
                "value": f"{kpd_delta:+.2f}",
                "detail": summary.get("kpd_insight") or "Compared with previous period.",
            }
        )
    if shadow_score.get("incident_keys"):
        items.append(
            {
                "tone": "negative",
                "label": "Incidents",
                "value": ", ".join(shadow_score.get("incident_keys")[:3]),
                "detail": "Operational incidents reduce confidence and routing certainty.",
            }
        )
    if shadow_score.get("confidence_band"):
        items.append(
            {
                "tone": "neutral",
                "label": "Confidence",
                "value": shadow_score["confidence_band"],
                "detail": "Shadow interpretation stays bounded by freshness and verified coverage.",
            }
        )
    return items[:3]


def build_action_stack(*, summary: dict, shops: dict, pipeline: dict, shadow_score: dict) -> dict:
    must_do_today = []
    best_opportunities = []

    for row in (summary.get("followups") or {}).get("problem_list", [])[:5]:
        must_do_today.append(
            {
                "title": row.get("shop") or "Follow-up",
                "detail": row.get("due_label") or "Overdue follow-up",
                "badge": "Follow-up",
            }
        )
    for row in (pipeline.get("followup_plan_missing_examples") or [])[:3]:
        must_do_today.append(
            {
                "title": row.get("shop") or "Plan next step",
                "detail": f"Stage: {row.get('stage') or 'needs plan'}",
                "badge": "Pipeline",
            }
        )
    for row in (shops.get("next_contact_due_list") or [])[:3]:
        must_do_today.append(
            {
                "title": row.get("name") or "Shop contact",
                "detail": row.get("next_contact_label") or "Contact overdue",
                "badge": "Shop",
            }
        )

    for row in shadow_score.get("rescue_top5") or []:
        best_opportunities.append(
            {
                "title": row.get("name") or "Rescue case",
                "detail": f"Risk: {row.get('value_at_risk')} UAH • {row.get('urgency')}",
                "badge": row.get("confidence_badge") or "Opportunity",
            }
        )
    return {
        "must_do_today": must_do_today[:6],
        "best_opportunities": best_opportunities[:5],
    }
