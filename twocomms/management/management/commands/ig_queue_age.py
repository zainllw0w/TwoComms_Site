"""Э2.8 — базова метрика віку черги вхідних (read-only).

Без цього числа твердження «свіжі більше не морять старих голодом» недоказуемо:
потрібен знімок до правки і після. Команда нічого не пише.
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Вік черги вхідних: p50/p95/p99, максимум і число випадків голодування"

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **options):
        from management.services import ig_queue_priority

        report = ig_queue_priority.queue_age_report()
        if options["json"]:
            self.stdout.write(json.dumps(report, ensure_ascii=False))
            return
        self.stdout.write(
            f"pending={report['pending']} ceiling={report['age_ceiling_seconds']}s"
        )
        self.stdout.write(
            f"  p50={report['p50_seconds']}s p95={report['p95_seconds']}s "
            f"p99={report['p99_seconds']}s max={report['max_seconds']}s"
        )
        self.stdout.write(
            f"  голодують={report['starving']} "
            f"найстаріший={report['starving_max_seconds']}s"
        )
        if report["starving"]:
            self.stdout.write(
                self.style.WARNING("є рядки старші за потолок віку")
            )
