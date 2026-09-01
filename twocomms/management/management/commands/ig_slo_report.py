"""Э0.7 — отчёт SLO пути клиента (read-only).

Печатает по каждому из трёх путей распределение исходов, `terminal_disposition`
и `correct_final_outcome` РАЗДЕЛЬНО, p50 отдельно от p95/p99, когорты и решение
бюджета ошибок о выкате новой автоматической политики.

Все числа берутся из `services/ig_slo.slo_report()` и не пересчитываются здесь.
Это не удобство, а требование пункта: панель в админке, этот отчёт и решение о
выкате обязаны показывать один и тот же числитель и один и тот же знаменатель.
Как только команда начнёт считать что-то своё, появится третий источник числа.

Использование::

    manage.py ig_slo_report [--days 7] [--json] [--baseline path/to/report.json]
"""
import json

from django.core.management.base import BaseCommand

from management.services import ig_slo


def _pct(value) -> str:
    """Доля в проценты. `None` печатается как `n/a`, а НЕ как `0.0%`.

    Ноль в пустом знаменателе читается как измеренная катастрофа там, где
    измерения вообще не было, — и оператор принимает решение по выдумке.
    """
    if value is None:
        return "n/a"
    return f"{value * 100:.2f}%"


def _sec(value) -> str:
    return "n/a" if value is None else f"{value:.1f}s"


class Command(BaseCommand):
    help = "Э0.7: SLO пути клиента по трём путям (read-only)"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=ig_slo.DEFAULT_WINDOW_DAYS)
        parser.add_argument("--json", action="store_true")
        parser.add_argument(
            "--baseline",
            default="",
            help="JSON прошлого запуска: включает проверку регрессии по когортам",
        )

    def handle(self, *args, **options):
        report = ig_slo.slo_report(days=options["days"])
        baseline = None
        baseline_path = (options.get("baseline") or "").strip()
        if baseline_path:
            with open(baseline_path, "r", encoding="utf-8") as handle:
                baseline = json.load(handle)
        gate = ig_slo.policy_rollout_gate(report, baseline=baseline)
        report["policy_rollout_gate"] = gate

        if options["json"]:
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, default=str))
            return

        window = report["window"]
        line = "=" * 78
        self.stdout.write(line)
        self.stdout.write("Э0.7 — SLO пути клиента")
        self.stdout.write(
            f"Окно: {window['days']} сут, {window['since_local']} .. "
            f"{window['until_local']} ({window['timezone']})"
        )
        self.stdout.write(
            "correct_final_outcome НЕ включает unknown-доставку и НЕ включает "
            "ответ, за которым сразу открылся человеческий кейс."
        )
        self.stdout.write(line)

        for path in ig_slo.PATHS:
            self._write_path(report["paths"][path])

        self.stdout.write("")
        self.stdout.write("Guardrail-метрики вреда (показатель не должен расти за счёт клиента):")
        harm = report["guardrails"]
        self.stdout.write(f"  opt-out за окно: {harm['opt_outs_in_window']}")
        blocks = harm["clients_with_confirmed_delivery_block"]
        if not blocks:
            self.stdout.write("  подтверждённых запретов доставки нет")
        for reason, count in blocks.items():
            self.stdout.write(f"  подтверждённый запрет доставки [{reason}]: {count}")

        self.stdout.write("")
        self.stdout.write(f"Бюджет ошибок: {gate['decision'].upper()}")
        self.stdout.write(
            f"  выкат новой автоматической политики: "
            f"{'разрешён' if gate['allow_new_automatic_policy'] else 'приостановлен'}"
        )
        self.stdout.write(
            "  поддержка клиентов: НЕ останавливается (инвариант пункта)"
        )
        for reason in gate["reasons"]:
            self.stdout.write(f"  ! {reason}")
        for path in gate["insufficient_sample_paths"]:
            self.stdout.write(
                f"  ~ {path}: выборка меньше {ig_slo.MIN_SAMPLE_PER_PATH} — вывод не делается"
            )
        self.stdout.write(line)

    def _write_path(self, path_report: dict) -> None:
        self.stdout.write("")
        self.stdout.write(
            f"[{path_report['path']}]  единица знаменателя: {path_report['unit']}"
            f"  SLA: {path_report['sla_seconds']:.0f}s"
        )
        disposition = path_report["terminal_disposition"]
        correct = path_report["correct_final_outcome"]
        owed = path_report["answer_rate_when_owed"]
        self.stdout.write(
            f"  terminal_disposition : {disposition['numerator']}/"
            f"{disposition['denominator']} = {_pct(disposition['rate'])}"
            "   (наблюдение о системе; unknown входит)"
        )
        self.stdout.write(
            f"  correct_final_outcome: {correct['numerator']}/"
            f"{correct['denominator']} = {_pct(correct['rate'])}"
            "   (наблюдение о клиенте; unknown НЕ входит)"
        )
        self.stdout.write(
            f"  answer_rate_when_owed: {owed['numerator']}/{owed['denominator']}"
            f" = {_pct(owed['rate'])}"
        )
        latency = path_report["latency_to_terminal_seconds"]
        self.stdout.write(
            f"  время до терминального исхода: p50={_sec(latency['p50'])} "
            f"| p95={_sec(latency['p95'])} p99={_sec(latency['p99'])} "
            f"max={_sec(latency['max'])} (n={latency['count']})"
        )
        self.stdout.write("  p50 не является SLO: вся боль клиента живёт в хвосте.")

        self.stdout.write("  распределение исходов (сумма = знаменателю):")
        for bucket in ig_slo.ALL_OUTCOMES:
            count = path_report["buckets"][bucket]
            if not count:
                continue
            mark = "OK " if bucket in ig_slo.CORRECT_OUTCOMES else "   "
            self.stdout.write(f"    {mark}{bucket:<26} {count}")
        self.stdout.write(
            f"    -- всего: {path_report['denominator_total']}"
            f" (терминальных: {path_report['denominator_terminal']})"
        )

        blocks = path_report["policy_blocks_by_reason"]
        if blocks:
            self.stdout.write(
                "  блокировки политикой по причине (сумма = корзине policy_blocked):"
            )
            for reason, count in blocks.items():
                self.stdout.write(f"    {reason:<26} {count}")
        not_recorded = path_report["guardrails"].get("policy_reason_not_recorded")
        if not_recorded:
            self.stdout.write(
                f"  молчание без записанной причины: {not_recorded}"
                " (рантайм пишет её только в текст лога, без ссылки на ход)"
            )

        self.stdout.write("  когорты (стадия клиента на момент отчёта, не на момент хода):")
        for cohort in ig_slo.COHORTS:
            data = path_report["cohorts"][cohort]
            critical = "*" if cohort in ig_slo.CRITICAL_COHORTS else " "
            self.stdout.write(
                f"   {critical}{cohort:<16} correct "
                f"{data['correct_numerator']}/{data['denominator_terminal']}"
                f" = {_pct(data['correct_final_outcome_rate'])}"
                f"  unknown={data['unknown']} overdue={data['overdue']}"
            )
        self.stdout.write("   * регрессия в этой когорте приостанавливает выкат политики")

        guardrails = path_report["guardrails"]
        self.stdout.write("  guardrails:")
        for key in sorted(guardrails):
            value = guardrails[key]
            printed = _pct(value) if key.endswith("_share") else value
            self.stdout.write(f"    {key:<34} {printed}")

        broken = [name for name, ok in path_report["invariants"].items() if not ok]
        if broken:
            self.stdout.write(
                self.style.ERROR(f"  НАРУШЕНЫ ИНВАРИАНТЫ КОРЗИН: {', '.join(broken)}")
            )
        if not path_report["sample_sufficient"]:
            self.stdout.write(
                f"  выборка меньше {ig_slo.MIN_SAMPLE_PER_PATH} терминальных строк:"
                " вывод по этому пути не делается"
            )
