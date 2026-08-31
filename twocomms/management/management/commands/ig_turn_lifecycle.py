"""Інвентаризація і реконсиляція lifecycle ходів клієнта (Э2.2B Phase 1).

Чому окрема команда, а не автоматична правка: після міграції `0173` усі
автоматично виконані production-ходи лишились `CLAIMED`, і серед них є як
безпечні (відповідь доставлена, рядок терміналом), так і небезпечні —
`send_state="sending"` без receipt. Масовий слепий `CLAIMED → PROCESSED` зробив
би другу категорію невидимою, а саме вона означає невідому доставку клієнту.

Тому за замовчуванням команда **read-only**: друкує класифікацію. Запис
вимагає явного `--apply`.
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Класифікувати застарілі CLAIMED ходи; --apply терміналізує їх з причиною"

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Записати терміналізацію (за замовчуванням тільки звіт)",
        )
        parser.add_argument("--limit", type=int, default=200)
        parser.add_argument(
            "--json", action="store_true", help="Машинний вивід замість таблиці"
        )

    def handle(self, *args, **options):
        from management.services import ig_customer_turns as turns

        outcome = turns.reconcile_stale_claimed_turns(
            limit=int(options["limit"]), apply=bool(options["apply"])
        )
        if options["json"]:
            self.stdout.write(json.dumps(outcome, default=str, ensure_ascii=False))
            return
        self.stdout.write(
            f"lease={turns.turn_lease_seconds():.0f}s "
            f"scanned={outcome['scanned']} applied={outcome['applied']}"
        )
        for reason, count in sorted(outcome["counts"].items()):
            self.stdout.write(f"  {reason:16s} {count}")
        for entry in outcome["entries"]:
            rows = ", ".join(
                f"#{r['id']}:{r['status']}/{r['send_state'] or '-'}"
                for r in entry.get("rows", [])
            )
            self.stdout.write(
                f"  turn {entry['turn_id']} client {entry.get('client_id')} "
                f"→ {entry['reason']} [{rows}]"
            )
        if not options["apply"] and outcome["scanned"]:
            self.stdout.write(
                self.style.WARNING("read-only: додайте --apply, щоб записати")
            )
