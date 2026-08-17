from __future__ import annotations

ANALYSIS_DELAY_SECONDS = 90
MIN_ANALYSIS_DURATION_SECONDS = 30
MAX_ANALYSIS_ATTEMPTS = 3
STALE_ANALYSIS_LOCK_MINUTES = 15
RECORDABLE_DISPOSITIONS = frozenset({"ANSWER", "VM-SUCCESS", "SUCCESS", "TRANSFER"})

ELIGIBLE = "eligible"
METADATA_PENDING = "metadata_pending"
INELIGIBLE = "ineligible"


def analysis_queue_category(payload, duration_seconds) -> str:
    payload = payload if isinstance(payload, dict) else {}
    disposition = str(payload.get("disposition") or "").strip().upper()
    if not disposition:
        return METADATA_PENDING
    try:
        duration = int(duration_seconds or 0)
    except (TypeError, ValueError):
        duration = 0
    if disposition in RECORDABLE_DISPOSITIONS and duration >= MIN_ANALYSIS_DURATION_SECONDS:
        return ELIGIBLE
    return INELIGIBLE
