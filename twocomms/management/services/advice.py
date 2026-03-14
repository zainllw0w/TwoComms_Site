from __future__ import annotations


def build_why_changed_today(*, summary: dict, shadow_score: dict) -> list[dict]:
    items = []
    kpd_delta = float(summary.get("kpd_delta") or 0)
    if kpd_delta:
        items.append(
            {
                "tone": "positive" if kpd_delta > 0 else "negative",
                "label": "Legacy КПД",
                "value": f"{kpd_delta:+.2f}",
                "detail": summary.get("kpd_insight") or "Порівняно з попереднім періодом.",
            }
        )
    if shadow_score.get("incident_keys"):
        items.append(
            {
                "tone": "negative",
                "label": "Інциденти",
                "value": ", ".join(shadow_score.get("incident_keys")[:3]),
                "detail": "Операційні інциденти знижують довіру та визначеність пріоритетів.",
            }
        )
    if shadow_score.get("confidence_band"):
        items.append(
            {
                "tone": "neutral",
                "label": "Довіра",
                "value": shadow_score["confidence_band"],
                "detail": "Тіньова інтерпретація обмежується свіжістю знімка та підтвердженим покриттям.",
            }
        )
    return items[:3]


def build_action_stack(*, summary: dict, shops: dict, pipeline: dict, shadow_score: dict) -> dict:
    must_do_today = []
    best_opportunities = []

    for row in (summary.get("followups") or {}).get("problem_list", [])[:5]:
        must_do_today.append(
            {
                "title": row.get("shop") or "Передзвон",
                "detail": row.get("due_label") or "Прострочений передзвон",
                "badge": "Передзвон",
            }
        )
    for row in (pipeline.get("followup_plan_missing_examples") or [])[:3]:
        must_do_today.append(
            {
                "title": row.get("shop") or "Заплануйте наступний крок",
                "detail": f"Етап: {row.get('stage') or 'потрібен план'}",
                "badge": "Воронка",
            }
        )
    for row in (shops.get("next_contact_due_list") or [])[:3]:
        must_do_today.append(
            {
                "title": row.get("name") or "Контакт магазину",
                "detail": row.get("next_contact_label") or "Контакт прострочено",
                "badge": "Магазин",
            }
        )

    for row in shadow_score.get("rescue_top5") or []:
        best_opportunities.append(
            {
                "title": row.get("name") or "Кейс порятунку",
                "detail": f"Ризик: {row.get('value_at_risk')} грн • {row.get('urgency')}",
                "badge": row.get("confidence_badge_label") or row.get("confidence_badge") or "Можливість",
            }
        )
    return {
        "must_do_today": must_do_today[:6],
        "best_opportunities": best_opportunities[:5],
    }
