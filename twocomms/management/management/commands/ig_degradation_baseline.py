"""Read-only Instagram bot degradation baseline measurement.

Measures technical-delay spam across the window, with proxy-incident grouping.
Run before and after a fix to quantify the improvement.

Usage:
    manage.py ig_degradation_baseline [--days 14] [--incident-window-minutes 5] [--json]
"""
import json
import subprocess
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from management.models import (
    GeminiRequestAttempt,
    IgClientDegradationEpisode,
    IgProviderIncident,
    InstagramBotLog,
    InstagramBotMessage,
)
from management.services.ig_provider_incidents import HOLDING_MESSAGE_SOURCE


HOLDING_SUBSTRINGS = {
    "uk": "технічну затримку",
    "ru": "техническую задержку",
    "en": "technical delay",
}

APOLOGY_STEMS = (
    "вибач", "перепрош", "извин", "прощен", "sorry", "apolog"
)


def _git_sha():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        ).strip()[:12]
    except Exception:
        return "unknown"


def _is_holding_text(text: str) -> bool:
    text_lower = (text or "").lower()
    return any(phrase in text_lower for phrase in HOLDING_SUBSTRINGS.values())


def _contains_apology(text: str) -> bool:
    text_lower = (text or "").lower()
    return any(stem in text_lower for stem in APOLOGY_STEMS)


def _group_failures_into_incidents(attempts, window_minutes: int):
    """Group failed attempts by role into proxy incidents.

    Returns list of incidents: [{role, start_dt, end_dt, attempt_ids}]
    """
    by_role = defaultdict(list)
    for att in attempts:
        by_role[att.role].append(att)

    incidents = []
    for role, role_attempts in by_role.items():
        role_attempts.sort(key=lambda x: x.created_at)
        current_incident = None
        window_delta = timedelta(minutes=window_minutes)

        for att in role_attempts:
            if current_incident is None:
                current_incident = {
                    "role": role,
                    "start_dt": att.created_at,
                    "end_dt": att.created_at,
                    "attempt_ids": [att.id],
                }
            else:
                gap = att.created_at - current_incident["end_dt"]
                if gap <= window_delta:
                    current_incident["end_dt"] = att.created_at
                    current_incident["attempt_ids"].append(att.id)
                else:
                    incidents.append(current_incident)
                    current_incident = {
                        "role": role,
                        "start_dt": att.created_at,
                        "end_dt": att.created_at,
                        "attempt_ids": [att.id],
                    }

        if current_incident:
            incidents.append(current_incident)

    return incidents


def _compute_metrics(days: int, incident_window_minutes: int):
    now = timezone.now()
    start_dt = now - timedelta(days=days)

    # Holding rows
    holding_qs = InstagramBotMessage.objects.filter(
        role=InstagramBotMessage.Role.MODEL,
        created_at__gte=start_dt,
    ).values_list("id", "text", "client_id", "created_at", "source")

    holding_rows = []
    for msg_id, text, client_id, created_at, source in holding_qs.iterator(chunk_size=500):
        # После ЭА.3 holding имеет durable-признак `source`. До него его можно
        # опознать только по стабильной подстроке текста. Считаем оба, чтобы
        # замер до и после правки выполнялся ОДНИМ кодом.
        if source == HOLDING_MESSAGE_SOURCE or _is_holding_text(text):
            holding_rows.append({
                "id": msg_id,
                "client_id": client_id,
                "created_at": created_at,
                "durable_marker": source == HOLDING_MESSAGE_SOURCE,
            })

    # Ключи по суткам — строки: JSON не сериализует `datetime.date` как ключ.
    holding_per_day = defaultdict(int)
    holding_per_client = defaultdict(int)
    for row in holding_rows:
        day = row["created_at"].astimezone(ZoneInfo("Europe/Kyiv")).date().isoformat()
        holding_per_day[day] += 1
        holding_per_client[row["client_id"]] += 1

    # Failed attempts
    failed_attempts = list(
        GeminiRequestAttempt.objects.filter(
            created_at__gte=start_dt,
        ).exclude(outcome="succeeded").order_by("created_at").iterator(chunk_size=500)
    )

    incidents = _group_failures_into_incidents(failed_attempts, incident_window_minutes)

    incidents_per_role = defaultdict(int)
    incidents_per_day = defaultdict(int)
    for inc in incidents:
        incidents_per_role[inc["role"]] += 1
        day = inc["start_dt"].astimezone(ZoneInfo("Europe/Kyiv")).date().isoformat()
        incidents_per_day[day] += 1

    # Holding per incident-client
    inbound_qs = InstagramBotMessage.objects.filter(
        role=InstagramBotMessage.Role.USER,
        created_at__gte=start_dt,
    ).values_list("client_id", "created_at")

    inbound_by_client = defaultdict(list)
    for client_id, created_at in inbound_qs.iterator(chunk_size=500):
        inbound_by_client[client_id].append(created_at)

    incident_client_pairs = set()
    for inc in incidents:
        for client_id, timestamps in inbound_by_client.items():
            for ts in timestamps:
                if inc["start_dt"] <= ts <= inc["end_dt"]:
                    incident_client_pairs.add((tuple(inc["attempt_ids"]), client_id))
                    break

    holding_per_incident_client = (
        Decimal(len(holding_rows)) / Decimal(max(1, len(incident_client_pairs)))
    )

    # Double apology turns
    model_qs = InstagramBotMessage.objects.filter(
        role=InstagramBotMessage.Role.MODEL,
        created_at__gte=start_dt,
    ).select_related("client").order_by("client_id", "created_at").values_list(
        "id", "client_id", "text", "created_at"
    )

    model_messages = list(model_qs.iterator(chunk_size=500))

    holding_msg_ids = {row["id"] for row in holding_rows}

    recovery_qs = InstagramBotMessage.objects.filter(
        created_at__gte=start_dt,
        role=InstagramBotMessage.Role.MODEL,
    ).exclude(
        Q(ai_recovery_reply_for__isnull=True)
    ).values_list("id", flat=True)

    recovery_msg_ids = set(recovery_qs.iterator(chunk_size=500))

    double_apology = 0
    prev_client = None
    prev_was_holding = False
    prev_id = None

    for msg_id, client_id, text, created_at in model_messages:
        if client_id != prev_client:
            prev_client = client_id
            prev_was_holding = False
            prev_id = None

        if prev_was_holding and msg_id in recovery_msg_ids and _contains_apology(text):
            double_apology += 1

        prev_was_holding = msg_id in holding_msg_ids
        prev_id = msg_id

    # Daemon restarts
    daemon_logs = InstagramBotLog.objects.filter(
        created_at__gte=start_dt,
        event__in=["daemon_start", "daemon_spawn"],
    ).values_list("event", "created_at")

    daemon_restarts_per_day = defaultdict(lambda: {"daemon_start": 0, "daemon_spawn": 0})
    for event, created_at in daemon_logs.iterator(chunk_size=500):
        day = created_at.astimezone(ZoneInfo("Europe/Kyiv")).date().isoformat()
        daemon_restarts_per_day[day][event] += 1

    # Failure class distribution
    failure_counts = defaultdict(int)
    for att in failed_attempts:
        kind = att.failure_kind or "other"
        if att.http_code == 429:
            kind = "429"
        elif att.http_code == 503:
            kind = "503"
        failure_counts[kind] += 1

    # Alerts per incident
    try:
        from management.ig_bot_models import IgBotNotification

        alerts = IgBotNotification.objects.filter(
            created_at__gte=start_dt,
            status=IgBotNotification.Status.SENT,
        ).count()
    except Exception:
        alerts = 0

    alerts_per_incident = (
        Decimal(alerts) / Decimal(max(1, len(incidents)))
    )

    # Silent inbound (p95 reply latency guardrail).
    #
    # Наивная реализация «для каждого inbound пройти по всем исходящим» даёт
    # O(n²) на 14 сутках production-данных и превращает read-only замер в
    # многоминутную нагрузку на боевую MariaDB. Здесь вместо этого: один проход
    # по каждой роли, группировка по клиенту, бинарный поиск ближайшего
    # следующего исходящего.
    from bisect import bisect_right

    def _timestamps_by_client(role):
        grouped = defaultdict(list)
        rows = InstagramBotMessage.objects.filter(
            role=role,
            created_at__gte=start_dt,
        ).values_list("client_id", "created_at").iterator(chunk_size=2000)
        for client_id, created_at in rows:
            grouped[client_id].append(created_at)
        for values in grouped.values():
            values.sort()
        return grouped

    inbound_times = _timestamps_by_client(InstagramBotMessage.Role.USER)
    model_times = _timestamps_by_client(InstagramBotMessage.Role.MODEL)
    manager_times = _timestamps_by_client(InstagramBotMessage.Role.MANAGER)

    total_inbound = sum(len(values) for values in inbound_times.values())

    def _next_after(sorted_values, moment):
        index = bisect_right(sorted_values, moment)
        return sorted_values[index] if index < len(sorted_values) else None

    reply_latencies = []
    for client_id, moments in inbound_times.items():
        outgoing = model_times.get(client_id) or []
        if not outgoing:
            continue
        for moment in moments:
            reply_at = _next_after(outgoing, moment)
            if reply_at is not None:
                reply_latencies.append((reply_at - moment).total_seconds())

    reply_latencies.sort()
    p95_latency = (
        reply_latencies[min(len(reply_latencies) - 1, int(len(reply_latencies) * 0.95))]
        if reply_latencies else 300.0
    )

    silent_inbound = 0
    for client_id, moments in inbound_times.items():
        outgoing = model_times.get(client_id) or []
        manager = manager_times.get(client_id) or []
        for moment in moments:
            reply_at = _next_after(outgoing, moment)
            if reply_at is not None and (reply_at - moment).total_seconds() <= p95_latency:
                continue
            if _next_after(manager, moment) is not None:
                continue
            silent_inbound += 1

    # Durable-метрика (доступна только после ЭА.2/ЭА.3): те же числитель и
    # знаменатель, но по реальному incident_id вместо прокси-инцидента. Именно
    # её проверяет приёмка ЭА.24.
    durable_incidents = IgProviderIncident.objects.filter(opened_at__gte=start_dt).count()
    durable_episodes = IgClientDegradationEpisode.objects.filter(
        created_at__gte=start_dt
    )
    durable_pairs = durable_episodes.count()
    durable_holdings = durable_episodes.filter(
        holding_message__isnull=False
    ).count()
    durable_double_apology = durable_episodes.filter(apology_count__gt=1).count()
    durable_holding_per_incident_client = (
        Decimal(durable_holdings) / Decimal(max(1, durable_pairs))
    )

    return {
        "holding_rows": {
            "total": len(holding_rows),
            "per_day": dict(holding_per_day),
            "top_clients": sorted(
                holding_per_client.items(), key=lambda x: x[1], reverse=True
            )[:20],
        },
        "proxy_incidents": {
            "total": len(incidents),
            "per_role": dict(incidents_per_role),
            "per_day": dict(incidents_per_day),
        },
        "holding_per_incident_client": float(holding_per_incident_client),
        "incident_client_pairs": len(incident_client_pairs),
        "double_apology_turns": double_apology,
        "daemon_restarts": dict(daemon_restarts_per_day),
        "failure_class_distribution": dict(failure_counts),
        "alerts_per_incident": float(alerts_per_incident),
        "alerts_total": alerts,
        "silent_inbound": {
            "count": silent_inbound,
            "p95_reply_latency_seconds": p95_latency,
            "total_inbound": total_inbound,
        },
        "durable": {
            "incidents": durable_incidents,
            "incident_client_pairs": durable_pairs,
            "holding_rows": durable_holdings,
            "holding_per_incident_client": float(durable_holding_per_incident_client),
            "episodes_with_more_than_one_apology": durable_double_apology,
        },
    }


class Command(BaseCommand):
    help = "Measure Instagram bot degradation baseline (read-only)"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=14)
        parser.add_argument("--incident-window-minutes", type=int, default=5)
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **options):
        days = max(1, min(options["days"], 90))
        incident_window = max(1, min(options["incident_window_minutes"], 60))
        as_json = options["json"]

        git_sha = _git_sha()
        now = timezone.now()
        kyiv_tz = ZoneInfo("Europe/Kyiv")
        now_kyiv = now.astimezone(kyiv_tz)

        metrics = _compute_metrics(days, incident_window)

        if as_json:
            output = {
                "git_sha": git_sha,
                "timestamp_utc": now.isoformat(),
                "timestamp_kyiv": now_kyiv.isoformat(),
                "window_days": days,
                "incident_window_minutes": incident_window,
                "assumption": f"proxy-incident window = {incident_window} minutes (assumption: no durable incident_id exists before EA.2)",
                "metrics": metrics,
            }
            self.stdout.write(json.dumps(output, ensure_ascii=False, indent=2, default=str))
        else:
            self.stdout.write("=" * 80)
            self.stdout.write(f"Instagram Bot Degradation Baseline")
            self.stdout.write(f"Git SHA: {git_sha}")
            self.stdout.write(f"Measured at: {now_kyiv.strftime('%Y-%m-%d %H:%M:%S')} Kyiv / {now.strftime('%Y-%m-%d %H:%M:%S')} UTC")
            self.stdout.write(f"Window: {days} days")
            self.stdout.write(f"Assumption: proxy-incident window = {incident_window} minutes (no durable incident_id before EA.2)")
            self.stdout.write("=" * 80)
            self.stdout.write("")

            self.stdout.write(f"Holding rows (total): {metrics['holding_rows']['total']}")
            self.stdout.write(f"  Per day: {metrics['holding_rows']['per_day']}")
            if metrics['holding_rows']['top_clients']:
                self.stdout.write(f"  Top clients (client_id: count):")
                for client_id, count in metrics['holding_rows']['top_clients'][:10]:
                    self.stdout.write(f"    {client_id}: {count}")
            self.stdout.write("")

            self.stdout.write(f"Proxy incidents (total): {metrics['proxy_incidents']['total']}")
            self.stdout.write(f"  Per role: {metrics['proxy_incidents']['per_role']}")
            self.stdout.write(f"  Per day: {metrics['proxy_incidents']['per_day']}")
            self.stdout.write("")

            self.stdout.write(f"Holding per incident-client: {metrics['holding_per_incident_client']:.4f}")
            self.stdout.write(f"  Numerator (holding rows): {metrics['holding_rows']['total']}")
            self.stdout.write(f"  Denominator (incident-client pairs): {metrics['incident_client_pairs']}")
            self.stdout.write("")

            self.stdout.write(f"Double apology turns: {metrics['double_apology_turns']}")
            self.stdout.write("")

            self.stdout.write(f"Daemon restarts per day:")
            for day, counts in sorted(metrics['daemon_restarts'].items()):
                self.stdout.write(f"  {day}: start={counts['daemon_start']}, spawn={counts['daemon_spawn']}")
            self.stdout.write("")

            self.stdout.write(f"Failure class distribution:")
            for kind, count in sorted(metrics['failure_class_distribution'].items(), key=lambda x: x[1], reverse=True):
                self.stdout.write(f"  {kind}: {count}")
            self.stdout.write("")

            self.stdout.write(f"Alerts per incident: {metrics['alerts_per_incident']:.4f}")
            self.stdout.write(f"  Numerator (alerts): {metrics['alerts_total']}")
            self.stdout.write(f"  Denominator (incidents): {metrics['proxy_incidents']['total']}")
            self.stdout.write("")

            self.stdout.write(f"Silent inbound (GUARDRAIL):")
            self.stdout.write(f"  Count: {metrics['silent_inbound']['count']}")
            self.stdout.write(f"  p95 reply latency used: {metrics['silent_inbound']['p95_reply_latency_seconds']:.1f}s")
            self.stdout.write(f"  Total inbound: {metrics['silent_inbound']['total_inbound']}")
            self.stdout.write("")

            durable = metrics["durable"]
            self.stdout.write("Durable incident metrics (empty before EA.2/EA.3 deploy):")
            self.stdout.write(f"  Incidents: {durable['incidents']}")
            self.stdout.write(f"  Incident-client pairs: {durable['incident_client_pairs']}")
            self.stdout.write(f"  Holding rows: {durable['holding_rows']}")
            self.stdout.write(
                "  Holding per incident-client (TARGET <= 1.0): "
                f"{durable['holding_per_incident_client']:.4f}"
            )
            self.stdout.write(
                "  Episodes with more than one apology (TARGET 0): "
                f"{durable['episodes_with_more_than_one_apology']}"
            )
            self.stdout.write("")
            self.stdout.write("=" * 80)
