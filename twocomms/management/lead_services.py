import re
import shlex
from typing import Iterable

from django.db.models import QuerySet

from .models import Client, ManagementLead
from .services.visible_points import client_visible_points_value


def split_terms(raw_value: str) -> list[str]:
    raw = (raw_value or "").strip()
    if not raw:
        return []

    if any(sep in raw for sep in ["\n", ",", ";"]):
        chunks: list[str] = []
        current: list[str] = []
        quote_char = ""

        for char in raw:
            if char in {'"', "'"}:
                if quote_char == char:
                    quote_char = ""
                    continue
                if not quote_char:
                    quote_char = char
                    continue
            if char in {"\n", ",", ";"} and not quote_char:
                chunk = "".join(current).strip()
                if chunk:
                    chunks.append(chunk)
                current = []
                continue
            current.append(char)

        tail = "".join(current).strip()
        if tail:
            chunks.append(tail)

        return [chunk.strip().strip('"').strip("'").strip() for chunk in chunks if chunk.strip()]

    try:
        tokens = [token.strip() for token in shlex.split(raw) if token.strip()]
    except ValueError:
        tokens = [raw]

    if len(tokens) > 1:
        return tokens
    return [raw]


def client_points_value(client: Client) -> int:
    return client_visible_points_value(client)


def calc_client_points(clients: Iterable[Client]) -> int:
    return sum(client_points_value(client) for client in clients)


def calc_lead_bonus_points(leads_qs: QuerySet[ManagementLead]) -> int:
    return 0


def get_user_lead_bonus_points(user, day_start=None, day_end=None) -> tuple[int, int]:
    return 0, 0
