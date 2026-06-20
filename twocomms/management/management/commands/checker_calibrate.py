"""READ-ONLY: переоцінка вердиктів чекера за scoring v2 (розподіл до/після).

Нічого не записує. Допомагає підібрати пороги COLLAB_GATE_* перед деплоєм,
щоб 'question' не поглинув усе і 'fit' не зник. Запуск на проді:
    python manage.py checker_calibrate
"""
from collections import Counter

from django.core.management.base import BaseCommand

from management.models import LeadAICheck
from management.services import lead_checker as lc


class Command(BaseCommand):
    help = "Read-only: розподіл вердиктів чекера до/після scoring v2"

    def handle(self, *args, **options):
        before, after = Counter(), Counter()
        evidence = Counter()
        total = 0
        for c in LeadAICheck.objects.filter(status=LeadAICheck.Status.DONE).select_related("lead").iterator():
            total += 1
            before[c.lead.ai_verdict or "—"] += 1
            crit = c.criteria if isinstance(c.criteria, list) else []
            by = {x.get("key"): x.get("score", 0) for x in crit if isinstance(x, dict)}
            score = lc.compute_overall_from_criteria(by)
            sig = c.signals if isinstance(c.signals, dict) else {}
            cap, ev = lc.compute_collaboration_gate(
                sells_third_party=sig.get("sells_third_party_brands", "unknown"),
                own_production=sig.get("own_production", "unknown"),
            )
            band = lc.compute_verdict_band(
                score=min(score, cap),
                apparel=int(by.get("apparel_focus", 0) or 0),
                collab_evidence=ev,
                confidence=c.confidence,
            )
            after[band] += 1
            evidence[ev] += 1
        self.stdout.write(f"TOTAL done checks: {total}")
        self.stdout.write(f"BEFORE (lead.ai_verdict): {dict(before)}")
        self.stdout.write(f"AFTER  (scoring v2 band): {dict(after)}")
        self.stdout.write(f"collaboration_evidence  : {dict(evidence)}")
