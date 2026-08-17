"""Runtime switches for optional Binotel background work."""
from __future__ import annotations

from management.services.call_auto_analysis import is_call_auto_analysis_enabled


def is_binotel_ai_enabled() -> bool:
    """Compatibility alias for the canonical fail-closed runtime gate."""
    return is_call_auto_analysis_enabled()
