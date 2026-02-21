from datetime import timedelta
import re
import shlex
from typing import Iterable

from django.db.models import QuerySet
from django.utils import timezone

from .constants import LEAD_ADD_POINTS, POINTS
from .models import Client, ManagementLead


def split_terms(raw_value: str) -> list[str]:
    raw = (raw_value or "").strip()
    if not raw:
        return []

    if any(sep in raw for sep in ["\n", ",", ";"]):
        chunks = re.split(r"[\n,;]+", raw)
        return [chunk.strip() for chunk in chunks if chunk.strip()]

    try:
        tokens = [token.strip() for token in shlex.split(raw) if token.strip()]
    except ValueError:
        tokens = [raw]

    if len(tokens) > 1:
        return tokens
    return [raw]


def client_points_value(client: Client) -> int:
    if client.points_override is not None:
        return int(client.points_override)
    return int(POINTS.get(client.call_result, 0))


def calc_client_points(clients: Iterable[Client]) -> int:
    return sum(client_points_value(client) for client in clients)


def calc_lead_bonus_points(leads_qs: QuerySet[ManagementLead]) -> int:
    return leads_qs.filter(lead_source=ManagementLead.LeadSource.MANUAL).count() * LEAD_ADD_POINTS


def get_user_lead_bonus_points(user, day_start=None, day_end=None) -> tuple[int, int]:
    base = ManagementLead.objects.filter(
        added_by=user,
        lead_source=ManagementLead.LeadSource.MANUAL,
    )
    total = base.count() * LEAD_ADD_POINTS
    if day_start is None or day_end is None:
        now = timezone.localtime(timezone.now())
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
    today = base.filter(created_at__gte=day_start, created_at__lt=day_end).count() * LEAD_ADD_POINTS
    return today, total
