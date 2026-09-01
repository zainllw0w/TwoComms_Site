"""Э0.3 — операторский срез терминальных причин lifecycle-событий.

Только чтение: команда не отправляет клиентам ничего, не пишет в БД и не
обращается к провайдеру, поэтому её безопасно запускать на production.

    manage.py ig_lifecycle_reason_funnel [--days 30] [--json]

Что показывает отчёт (и чего он НЕ показывает — см. `ig_lifecycle_reasons`):
измерено ТЕКУЩЕЕ состояние строки (вариант A), а не история переходов.
"""
import json
import subprocess

from django.core.management.base import BaseCommand

from management.services.ig_lifecycle_reasons import (
    DEFAULT_WINDOW_DAYS,
    MAX_WINDOW_DAYS,
    lifecycle_reason_funnel,
)


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        ).strip()[:12]
    except Exception:
        return "unknown"


class Command(BaseCommand):
    help = "Terminal reason funnel for Instagram lifecycle events (read-only)"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=DEFAULT_WINDOW_DAYS)
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **options):
        days = max(1, min(int(options["days"]), MAX_WINDOW_DAYS))
        report = lifecycle_reason_funnel(days=days)
        report["git_sha"] = _git_sha()
        if options["json"]:
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, default=str))
            return
        if not report.get("enabled"):
            self.stdout.write(
                f"Funnel disabled by flag {report.get('flag')}: {report.get('reason')}"
            )
            return
        write = self.stdout.write
        write("=" * 80)
        write("IG lifecycle terminal reason funnel (variant A: current disposition)")
        write(f"Git SHA: {report['git_sha']}")
        write(f"Window: {report['window_days']} days from {report['window_start']}")
        write(f"Measured: {report['measured']}; transition history available: "
              f"{report['history_available']}")
        write(f"Caveat: {report['caveat']}")
        write("=" * 80)
        events = report["events"]
        write(f"Lifecycle events in window (denominator): {events['denominator']}")
        write(f"  Per kind: {events['by_kind']}")
        write(f"  Sum of reason buckets matches denominator: "
              f"{events['buckets_sum_matches_denominator']}")
        write(f"  Explicit unknown bucket: {events['unknown']}")
        write("")
        write("Terminal reason distribution (reason / stage / evidence):")
        for bucket in events["buckets"]:
            age = bucket["seconds_since_last_transition"]
            write(
                f"  {bucket['reason']:<30} {bucket['stage']:<22} "
                f"{bucket['evidence']:<26} {bucket['count']:>6} "
                f"({bucket['share'] * 100:.1f}%) terminal={bucket['terminal']} "
                f"age_s p50={age['p50']} p95={age['p95']} max={age['max']}"
            )
            write(f"      per kind: {bucket['by_kind']}")
            if bucket["details"]:
                write(f"      details: {bucket['details']}")
        write("")
        write(f"Stage distribution: {events['by_stage']}")
        write(f"Evidence distribution: {events['by_evidence']}")
        write("")
        hypothesis = report["window_closed_hypothesis"]
        write("NEW-CRIT-001 direct check (delivered_review_requested):")
        write(f"  Numerator (typed window_closed): {hypothesis['numerator']}")
        write(f"  Numerator (raw state+last_error): "
              f"{hypothesis['raw_state_last_error_match']}")
        write(f"  Denominator (events of this kind): {hypothesis['denominator']}")
        write(f"  Share: {hypothesis['share'] * 100:.1f}%")
        write(f"  Full reason distribution for this kind: "
              f"{hypothesis['reason_distribution']}")
        write("")
        delivered = report["delivered_orders"]
        write("Delivered IG orders without a lifecycle event:")
        write(f"  Unit of count: {delivered['unit_of_count']}")
        write(f"  Denominator (delivered IG orders): {delivered['denominator']}")
        write(f"  With delivered-kind event: {delivered['with_delivered_event']}")
        write(f"  Without delivered-kind event: {delivered['without_event']} "
              f"({delivered['share_without_event'] * 100:.1f}%)")
        write(f"  Without any lifecycle event: {delivered['without_any_event']}")
        write(f"  Absence reasons ({delivered['absence_evidence']}): "
              f"{delivered['absence_reasons']}")
        write(f"  Absence buckets match the numerator: "
              f"{delivered['absence_sum_matches_without_event']}")
        write("")
        cod = report["cod"]
        write("COD share among delivered IG orders:")
        write(f"  Denominator: {cod['denominator']}")
        write(f"  COD orders: {cod['cod_orders']} ({cod['share'] * 100:.1f}%)")
        write(f"  Pay type distribution: {cod['by_pay_type']}")
        write("=" * 80)
