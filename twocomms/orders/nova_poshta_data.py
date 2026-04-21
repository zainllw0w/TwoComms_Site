from __future__ import annotations

from typing import Mapping


NOVA_POSHTA_REF_FIELDS = (
    "np_settlement_ref",
    "np_city_ref",
    "np_warehouse_ref",
)


def extract_nova_poshta_refs(source: Mapping[str, object] | None) -> dict[str, str]:
    source = source or {}
    return {
        field: str(source.get(field) or "").strip()
        for field in NOVA_POSHTA_REF_FIELDS
    }


def apply_nova_poshta_refs(target: object, ref_values: Mapping[str, object] | None) -> dict[str, str]:
    normalized = extract_nova_poshta_refs(ref_values)
    for field, value in normalized.items():
        setattr(target, field, value)
    return normalized
