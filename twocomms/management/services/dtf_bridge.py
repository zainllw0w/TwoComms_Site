from __future__ import annotations

from management.models import DtfBridgeSnapshot


def build_dtf_bridge_payload(*, source_key: str = "default") -> dict:
    snapshot = (
        DtfBridgeSnapshot.objects.filter(source_key=source_key)
        .order_by("-snapshot_date", "-id")
        .first()
    )
    if not snapshot:
        return {
            "source_key": source_key,
            "status": DtfBridgeSnapshot.Status.DEGRADED,
            "freshness_seconds": 0,
            "snapshot_date": "",
            "reason": "dtf_bridge_not_configured",
            "items": [],
            "links": [],
        }

    payload = snapshot.payload or {}
    return {
        "source_key": source_key,
        "status": snapshot.status,
        "freshness_seconds": int(snapshot.freshness_seconds or 0),
        "snapshot_date": snapshot.snapshot_date.isoformat(),
        "reason": payload.get("reason") or "",
        "items": payload.get("items") or [],
        "links": payload.get("links") or [],
    }
