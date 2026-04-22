from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from django.conf import settings
from django.core import signing


CITY_TOKEN_SALT = "orders.nova_poshta.city_choice"
WAREHOUSE_TOKEN_SALT = "orders.nova_poshta.warehouse_choice"
DEFAULT_TOKEN_MAX_AGE = 7 * 24 * 60 * 60
DELIVERY_SELECTION_FIELDS = (
    "city",
    "np_office",
    "np_settlement_ref",
    "np_city_ref",
    "np_city_token",
    "np_warehouse_ref",
    "np_warehouse_token",
)


class NovaPoshtaSelectionError(Exception):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


@dataclass(frozen=True)
class NovaPoshtaDeliverySelection:
    city: str
    np_office: str
    settlement_ref: str
    city_ref: str
    warehouse_ref: str
    warehouse_kind: str
    city_token: str
    warehouse_token: str


def build_city_choice_token(item: Mapping[str, Any]) -> str:
    payload = {
        "label": _clean_string(item.get("label")),
        "settlement_ref": _clean_string(item.get("settlement_ref") or item.get("legacy_ref")),
        "city_ref": _clean_string(item.get("city_ref") or item.get("legacy_ref")),
    }
    return signing.dumps(payload, salt=CITY_TOKEN_SALT, compress=True)


def build_warehouse_choice_token(
    item: Mapping[str, Any],
    *,
    fallback_city_ref: str = "",
) -> str:
    payload = {
        "label": _clean_string(item.get("label")),
        "ref": _clean_string(item.get("ref")),
        "kind": _clean_kind(item.get("kind")),
        "city_ref": _clean_string(item.get("city_ref") or fallback_city_ref),
    }
    return signing.dumps(payload, salt=WAREHOUSE_TOKEN_SALT, compress=True)


def resolve_delivery_selection(payload: Mapping[str, Any]) -> NovaPoshtaDeliverySelection:
    raw_city_token = _clean_string(payload.get("np_city_token"))
    raw_warehouse_token = _clean_string(payload.get("np_warehouse_token"))

    if not raw_city_token:
        raise NovaPoshtaSelectionError("city", "Оберіть місто зі списку Нової пошти.")
    if not raw_warehouse_token:
        raise NovaPoshtaSelectionError("np_office", "Оберіть відділення або поштомат зі списку Нової пошти.")

    try:
        city_payload = signing.loads(raw_city_token, salt=CITY_TOKEN_SALT, max_age=_token_max_age())
    except signing.BadSignature as exc:
        raise NovaPoshtaSelectionError("city", "Потрібно повторно обрати місто зі списку Нової пошти.") from exc

    try:
        warehouse_payload = signing.loads(
            raw_warehouse_token,
            salt=WAREHOUSE_TOKEN_SALT,
            max_age=_token_max_age(),
        )
    except signing.BadSignature as exc:
        raise NovaPoshtaSelectionError(
            "np_office",
            "Потрібно повторно обрати відділення або поштомат зі списку Нової пошти.",
        ) from exc

    city_label = _clean_string(city_payload.get("label"))
    settlement_ref = _clean_string(city_payload.get("settlement_ref"))
    city_ref = _clean_string(city_payload.get("city_ref"))
    if not city_label or not (settlement_ref or city_ref):
        raise NovaPoshtaSelectionError("city", "Не вдалося підтвердити вибране місто Нової пошти.")

    warehouse_label = _clean_string(warehouse_payload.get("label"))
    warehouse_ref = _clean_string(warehouse_payload.get("ref"))
    warehouse_kind = _clean_kind(warehouse_payload.get("kind"))
    warehouse_city_ref = _clean_string(warehouse_payload.get("city_ref"))
    if not warehouse_label or not warehouse_ref:
        raise NovaPoshtaSelectionError("np_office", "Не вдалося підтвердити вибране відділення Нової пошти.")

    if city_ref and warehouse_city_ref and city_ref != warehouse_city_ref:
        raise NovaPoshtaSelectionError(
            "np_office",
            "Оберіть відділення або поштомат саме для вибраного міста Нової пошти.",
        )

    return NovaPoshtaDeliverySelection(
        city=city_label[:200],
        np_office=warehouse_label[:200],
        settlement_ref=settlement_ref,
        city_ref=city_ref or warehouse_city_ref,
        warehouse_ref=warehouse_ref,
        warehouse_kind=warehouse_kind,
        city_token=raw_city_token,
        warehouse_token=raw_warehouse_token,
    )


def has_delivery_selection_data(payload: Mapping[str, Any] | None) -> bool:
    payload = payload or {}
    return any(_clean_string(payload.get(field)) for field in DELIVERY_SELECTION_FIELDS)


def resolve_optional_delivery_selection(
    payload: Mapping[str, Any] | None,
) -> NovaPoshtaDeliverySelection | None:
    if not has_delivery_selection_data(payload):
        return None
    return resolve_delivery_selection(payload or {})


def format_delivery_selection_address(selection: NovaPoshtaDeliverySelection) -> str:
    return ", ".join(part for part in (selection.city, selection.np_office) if part)


def serialize_city_choice(item: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(item)
    payload["token"] = build_city_choice_token(item)
    return payload


def serialize_warehouse_choice(
    item: Mapping[str, Any],
    *,
    fallback_city_ref: str = "",
) -> dict[str, Any]:
    payload = dict(item)
    payload["token"] = build_warehouse_choice_token(item, fallback_city_ref=fallback_city_ref)
    if not payload.get("city_ref") and fallback_city_ref:
        payload["city_ref"] = fallback_city_ref
    return payload


def _token_max_age() -> int:
    raw_value = getattr(settings, "NOVA_POSHTA_SELECTION_TOKEN_MAX_AGE", DEFAULT_TOKEN_MAX_AGE)
    try:
        return max(int(raw_value), 60)
    except (TypeError, ValueError):
        return DEFAULT_TOKEN_MAX_AGE


def _clean_string(value: Any) -> str:
    return " ".join(str(value or "").split())


def _clean_kind(value: Any) -> str:
    kind = _clean_string(value).lower()
    return kind if kind in {"branch", "postomat"} else "branch"
