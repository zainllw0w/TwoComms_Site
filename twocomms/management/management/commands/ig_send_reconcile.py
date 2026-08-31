"""ЭА.21 — сверка неоднозначних відправок і чисельна перевірка дублікатів.

Обидві операції read-only за замовчуванням і **жодна з них не відправляє
повторно**. Це прямо вимога пункта: якщо Meta прийняла запит, а відповідь до нас
не дійшла, повторна відправка створює друге реальне повідомлення клієнту.
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Сверка UNKNOWN-відправок читанням; --duplicates рахує історичні дублікати"

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Записати результат сверки")
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument(
            "--duplicates",
            action="store_true",
            help="Порахувати історичні дублікати вихідних повідомлень (read-only)",
        )
        parser.add_argument("--window", type=int, default=120)
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **options):
        from management.services import ig_send_intent

        if options["duplicates"]:
            report = ig_send_intent.duplicate_outbound_report(
                window_seconds=int(options["window"]), limit=int(options["limit"])
            )
            if options["json"]:
                self.stdout.write(json.dumps(report, default=str, ensure_ascii=False))
                return
            self.stdout.write(
                f"outbound_scanned={report['outbound_scanned']} "
                f"window={report['window_seconds']}s "
                f"duplicate_pairs={report['duplicate_pairs']}"
            )
            for example in report["examples"]:
                self.stdout.write(
                    f"  client {example['client_id']}: #{example['first_id']} → "
                    f"#{example['second_id']} за {example['gap_seconds']}s"
                )
            return

        outcome = ig_send_intent.reconcile_unknown_sends(
            limit=int(options["limit"]), apply=bool(options["apply"])
        )
        if options["json"]:
            self.stdout.write(json.dumps(outcome, default=str, ensure_ascii=False))
            return
        self.stdout.write(
            f"scanned={outcome['scanned']} applied={outcome['applied']}"
        )
        for name, count in sorted(outcome["counts"].items()):
            self.stdout.write(f"  {name:16s} {count}")
        for entry in outcome["entries"]:
            self.stdout.write(
                f"  row {entry['row_id']} client {entry['client_id']} "
                f"{entry['outcome']} age={entry['age_seconds']}s "
                f"key={entry['key'] or '-'}"
            )
        if not options["apply"] and outcome["scanned"]:
            self.stdout.write(self.style.WARNING("read-only: додайте --apply"))
