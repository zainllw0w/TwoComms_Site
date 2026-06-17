"""
Коучинг-поради менеджеру за останніми дзвінками (Фаза 4).

Бере останні N завершених ШІ-аналізів дзвінків менеджера й детерміновано
(без звернення до LLM — швидко й безкоштовно) синтезує:
  - focus[]: що менеджер найчастіше НЕ обговорює (повторювані missed_topics);
  - tips[]: повторювані рекомендації ШІ;
  - trend: словесний тренд якості (БЕЗ цифр — бали менеджеру не показуємо).

Приватність: менеджер бачить лише поради/фокус/тренд словами. Конкретні бали
дзвінків лишаються для адміна (тут не повертаються).
"""
from __future__ import annotations

import re
from collections import Counter

from management.models import CallAIAnalysis

MIN_FOR_COACHING = 2
DEFAULT_LIMIT = 10


def _norm(text: str) -> str:
    t = (text or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def _dedupe_rank(items: list[str], top: int = 5) -> list[dict]:
    """Рахує повторюваність нормалізованих формулювань, повертає топ із
    оригінальним (першим побаченим) текстом і лічильником."""
    counter: Counter = Counter()
    original: dict[str, str] = {}
    for raw in items:
        key = _norm(raw)
        if len(key) < 4:
            continue
        counter[key] += 1
        if key not in original:
            original[key] = raw.strip()
    ranked = []
    for key, count in counter.most_common(top):
        text = original[key]
        if len(text) > 140:
            text = text[:139].rstrip() + "…"
        ranked.append({"text": text, "count": count})
    return ranked


def build_call_coaching(user, limit: int = DEFAULT_LIMIT) -> dict:
    analyses = list(
        CallAIAnalysis.objects.filter(
            call_record__manager=user, status=CallAIAnalysis.Status.DONE
        )
        .order_by("-created_at")[:limit]
    )
    analyzed = len(analyses)
    if analyzed < MIN_FOR_COACHING:
        return {
            "ready": False,
            "analyzed_count": analyzed,
            "message": "Зробіть кілька дзвінків — і тут зʼявляться персональні поради на основі ваших розмов.",
        }

    missed: list[str] = []
    recs: list[str] = []
    scores: list[float] = []
    verdicts = Counter()
    for a in analyses:
        missed.extend([str(x) for x in (a.missed_topics or []) if x])
        recs.extend([str(x) for x in (a.recommendations or []) if x])
        try:
            scores.append(float(a.overall_score))
        except (TypeError, ValueError):
            pass
        verdicts[a.verdict] += 1

    focus = _dedupe_rank(missed, top=5)
    tips = _dedupe_rank(recs, top=5)

    # Тренд за балами (словами, без цифр для менеджера).
    trend = {"tone": "neutral", "label": "Тримайте темп"}
    if len(scores) >= 4:
        half = len(scores) // 2
        recent = scores[:half]          # свіжіші (через order -created_at)
        older = scores[half:]
        avg_recent = sum(recent) / len(recent) if recent else 0
        avg_older = sum(older) / len(older) if older else 0
        diff = avg_recent - avg_older
        if diff >= 5:
            trend = {"tone": "good", "label": "Ви прогресуєте — дзвінки стали якіснішими 👏"}
        elif diff <= -5:
            trend = {"tone": "warn", "label": "Останні дзвінки слабші за попередні — зосередьтеся на фокус-зонах нижче"}
        else:
            trend = {"tone": "neutral", "label": "Стабільний рівень — спробуйте додати один сильний крок із порад"}

    strong = verdicts.get(CallAIAnalysis.Verdict.PASS, 0)

    return {
        "ready": True,
        "analyzed_count": analyzed,
        "focus": focus,
        "tips": tips,
        "trend": trend,
        "strong_calls": strong,
    }
