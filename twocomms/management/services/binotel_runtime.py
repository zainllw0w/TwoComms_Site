"""Runtime switches for optional Binotel background work."""
from __future__ import annotations

from django.db import DatabaseError, OperationalError, ProgrammingError


def is_binotel_ai_enabled() -> bool:
    """Return the durable Binotel AI switch, failing closed on DB/schema errors."""
    try:
        from management.models import InstagramBotSettings

        value = (
            InstagramBotSettings.objects.filter(pk=1)
            .values_list("binotel_ai_enabled", flat=True)
            .first()
        )
        return bool(value)
    except (DatabaseError, OperationalError, ProgrammingError):
        return False
