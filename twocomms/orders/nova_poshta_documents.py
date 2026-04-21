from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

import requests
from django.conf import settings

from orders.nova_poshta_lookup import NovaPoshtaDirectoryService

logger = logging.getLogger(__name__)

TELEGRAM_CREATE_NP_WAYBILL_ACTION = "create-np-waybill"


class NovaPoshtaDocumentError(Exception):
    """Raised when a Nova Poshta waybill cannot be prepared or created."""


@dataclass(frozen=True)
class NovaPoshtaResolvedPoint:
    city_label: str
    warehouse_label: str
    settlement_ref: str
    city_ref: str
    warehouse_ref: str
    warehouse_kind: str


def normalize_phone_for_np(phone: str) -> str:
    digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
    if digits.startswith("380") and len(digits) >= 12:
        return digits[:12]
    if digits.startswith("80") and len(digits) >= 11:
        return f"3{digits[:11]}"
    if digits.startswith("0") and len(digits) >= 10:
        return f"38{digits[:10]}"
    return digits


def split_person_name(full_name: str) -> dict[str, str]:
    parts = [part for part in str(full_name or "").strip().split() if part]
    if not parts:
        return {"first_name": "", "middle_name": "", "last_name": ""}
    if len(parts) == 1:
        return {"first_name": parts[0], "middle_name": "", "last_name": ""}
    if len(parts) == 2:
        return {"first_name": parts[1], "middle_name": "", "last_name": parts[0]}
    return {
        "first_name": parts[1],
        "middle_name": " ".join(parts[2:]),
        "last_name": parts[0],
    }


def build_waybill_description(order) -> str:
    items = list(getattr(order, "items", []).all() if hasattr(getattr(order, "items", None), "all") else getattr(order, "items", []) or [])
    total_qty = sum(int(getattr(item, "qty", 0) or 0) for item in items)
    if total_qty == 1 and len(items) == 1:
        title = str(getattr(items[0], "title", "") or "товар").strip()
        return f"Одяг бренду TwoComms, {title}"[:120]
    if total_qty > 1:
        return f"Одяг бренду TwoComms, у кількості {total_qty} шт."
    return "Одяг бренду TwoComms"


class NovaPoshtaDocumentService:
    API_URL = "https://api.novaposhta.ua/v2.0/json/"
    REQUEST_TIMEOUT = 20
    SENDER_CITY_QUERY = "Харків"
    SENDER_WAREHOUSE_QUERY = "138"
    DEFAULT_WEIGHT = Decimal("1")
    DEFAULT_LENGTH_CM = Decimal("30")
    DEFAULT_WIDTH_CM = Decimal("20")
    DEFAULT_HEIGHT_CM = Decimal("8")

    def __init__(self) -> None:
        self.api_key = getattr(settings, "NOVA_POSHTA_API_KEY", "") or ""
        self.api_url = getattr(settings, "NOVA_POSHTA_API_URL", self.API_URL) or self.API_URL
        self.api_url = self.api_url.rstrip("/") + "/"
        self.directory = NovaPoshtaDirectoryService()

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def build_initial_payload(self, order) -> dict[str, Any]:
        sender_point = self._resolve_default_sender_point()
        declared_cost = self._as_money(getattr(order, "total_sum", 0))
        remaining_cod = self._get_cod_amount(order)

        return {
            "recipient_full_name": getattr(order, "full_name", "") or "",
            "recipient_phone": getattr(order, "phone", "") or "",
            "recipient_city": getattr(order, "city", "") or "",
            "recipient_settlement_ref": getattr(order, "np_settlement_ref", "") or "",
            "recipient_city_ref": getattr(order, "np_city_ref", "") or "",
            "recipient_warehouse": getattr(order, "np_office", "") or "",
            "recipient_warehouse_ref": getattr(order, "np_warehouse_ref", "") or "",
            "sender_city": sender_point.city_label,
            "sender_settlement_ref": sender_point.settlement_ref,
            "sender_city_ref": sender_point.city_ref,
            "sender_warehouse": sender_point.warehouse_label,
            "sender_warehouse_ref": sender_point.warehouse_ref,
            "description": build_waybill_description(order),
            "declared_cost": f"{declared_cost:.2f}",
            "weight": "1.0",
            "seats_amount": "1",
            "length_cm": f"{self.DEFAULT_LENGTH_CM}",
            "width_cm": f"{self.DEFAULT_WIDTH_CM}",
            "height_cm": f"{self.DEFAULT_HEIGHT_CM}",
            "cod_amount": f"{remaining_cod:.2f}" if remaining_cod > 0 else "",
            "payer_type": "Recipient",
            "payment_method": "Cash",
        }

    def create_waybill(self, order, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.is_configured():
            raise NovaPoshtaDocumentError("NOVA_POSHTA_API_KEY не налаштований.")

        sender_profile = self._resolve_sender_profile()
        sender_point = self._resolve_point(
            city_label=payload.get("sender_city", ""),
            settlement_ref=payload.get("sender_settlement_ref", ""),
            city_ref=payload.get("sender_city_ref", ""),
            warehouse_label=payload.get("sender_warehouse", ""),
            warehouse_ref=payload.get("sender_warehouse_ref", ""),
            preferred_kind="branch",
            point_role="відправника",
        )
        recipient_point = self._resolve_point(
            city_label=payload.get("recipient_city", ""),
            settlement_ref=payload.get("recipient_settlement_ref", ""),
            city_ref=payload.get("recipient_city_ref", ""),
            warehouse_label=payload.get("recipient_warehouse", ""),
            warehouse_ref=payload.get("recipient_warehouse_ref", ""),
            preferred_kind="all",
            point_role="одержувача",
        )

        recipient_phone = normalize_phone_for_np(payload.get("recipient_phone", ""))
        if len(recipient_phone) < 12:
            raise NovaPoshtaDocumentError("Вкажіть коректний телефон одержувача у форматі +380XXXXXXXXX.")

        recipient_name = split_person_name(payload.get("recipient_full_name", ""))
        if not recipient_name["first_name"]:
            raise NovaPoshtaDocumentError("Вкажіть ПІБ одержувача.")

        recipient_ref = self._create_recipient_counterparty(recipient_point.city_ref, recipient_name, recipient_phone)
        recipient_contact_ref = self._create_recipient_contact(
            recipient_ref,
            recipient_name,
            recipient_phone,
        )

        dimensions = self._normalize_dimensions(
            payload.get("length_cm"),
            payload.get("width_cm"),
            payload.get("height_cm"),
        )
        weight = self._normalize_decimal(payload.get("weight"), fallback=self.DEFAULT_WEIGHT, minimum=Decimal("0.1"))
        declared_cost = self._as_money(payload.get("declared_cost"))
        seats_amount = int(str(payload.get("seats_amount") or "1").strip() or "1")
        description = str(payload.get("description") or "").strip() or build_waybill_description(order)
        cod_amount = self._as_money(payload.get("cod_amount") or "0")

        method_properties = {
            "PayerType": str(payload.get("payer_type") or "Recipient").strip() or "Recipient",
            "PaymentMethod": str(payload.get("payment_method") or "Cash").strip() or "Cash",
            "DateTime": date.today().strftime("%d.%m.%Y"),
            "CargoType": "Parcel",
            "Weight": self._format_decimal(weight),
            "ServiceType": "WarehouseWarehouse",
            "SeatsAmount": str(max(seats_amount, 1)),
            "Description": description[:120],
            "Cost": self._format_money(declared_cost),
            "CitySender": sender_point.city_ref,
            "Sender": sender_profile["sender_ref"],
            "SenderAddress": sender_point.warehouse_ref,
            "ContactSender": sender_profile["contact_ref"],
            "SendersPhone": sender_profile["phone"],
            "CityRecipient": recipient_point.city_ref,
            "Recipient": recipient_ref,
            "RecipientAddress": recipient_point.warehouse_ref,
            "ContactRecipient": recipient_contact_ref,
            "RecipientsPhone": recipient_phone,
            "RecipientType": "PrivatePerson",
            "RecipientName": str(payload.get("recipient_full_name") or "").strip(),
            "VolumeGeneral": self._format_volume(*dimensions),
            "OptionsSeat": [
                {
                    "weight": self._format_decimal(weight),
                    "volumetricLength": self._format_decimal(dimensions[0], trim_zeroes=True),
                    "volumetricWidth": self._format_decimal(dimensions[1], trim_zeroes=True),
                    "volumetricHeight": self._format_decimal(dimensions[2], trim_zeroes=True),
                    "volumetricVolume": self._format_volume(*dimensions),
                }
            ],
        }

        if cod_amount > 0:
            method_properties["AfterpaymentOnGoodsCost"] = self._format_money(cod_amount)
            method_properties["BackwardDeliveryData"] = [
                {
                    "PayerType": "Recipient",
                    "CargoType": "Money",
                    "RedeliveryString": self._format_money(cod_amount),
                }
            ]

        response = self._request("InternetDocument", "save", method_properties)
        result = next(iter(response.get("data") or []), None) or {}
        tracking_number = str(result.get("IntDocNumber") or "").strip()
        document_ref = str(result.get("Ref") or "").strip()
        if not tracking_number:
            raise NovaPoshtaDocumentError("Nova Poshta API не повернув номер ТТН.")

        return {
            "tracking_number": tracking_number,
            "document_ref": document_ref,
            "recipient_ref": recipient_ref,
            "recipient_contact_ref": recipient_contact_ref,
            "recipient_point": recipient_point,
            "sender_point": sender_point,
            "warnings": [str(item).strip() for item in response.get("warnings") or [] if str(item).strip()],
        }

    def _resolve_sender_profile(self) -> dict[str, str]:
        configured_ref = (getattr(settings, "NOVA_POSHTA_SENDER_COUNTERPARTY_REF", "") or "").strip()
        configured_contact_ref = (getattr(settings, "NOVA_POSHTA_SENDER_CONTACT_REF", "") or "").strip()
        configured_phone = normalize_phone_for_np(getattr(settings, "NOVA_POSHTA_SENDER_PHONE", "") or "")
        if configured_ref and configured_contact_ref and configured_phone:
            return {
                "sender_ref": configured_ref,
                "contact_ref": configured_contact_ref,
                "phone": configured_phone,
            }

        senders = self._request(
            "Counterparty",
            "getCounterparties",
            {
                "CounterpartyProperty": "Sender",
                "Page": "1",
            },
        )
        sender = next(iter(senders.get("data") or []), None) or {}
        sender_ref = str(sender.get("Ref") or "").strip()
        if not sender_ref:
            raise NovaPoshtaDocumentError("У Nova Poshta API не знайдено відправника FOP/компанії.")

        contacts = self._request(
            "Counterparty",
            "getCounterpartyContactPersons",
            {"Ref": sender_ref},
        )
        contact = next(iter(contacts.get("data") or []), None) or {}
        contact_ref = str(contact.get("Ref") or "").strip()
        phone = normalize_phone_for_np(contact.get("Phones") or sender.get("Phone") or "")
        if not contact_ref or not phone:
            raise NovaPoshtaDocumentError(
                "Не вдалося отримати контактні дані відправника з Nova Poshta API."
            )

        return {
            "sender_ref": sender_ref,
            "contact_ref": contact_ref,
            "phone": phone,
        }

    def _resolve_default_sender_point(self) -> NovaPoshtaResolvedPoint:
        sender_city = (getattr(settings, "NOVA_POSHTA_SENDER_CITY", "") or self.SENDER_CITY_QUERY).strip()
        sender_warehouse = (getattr(settings, "NOVA_POSHTA_SENDER_WAREHOUSE", "") or self.SENDER_WAREHOUSE_QUERY).strip()
        return self._resolve_point(
            city_label=sender_city,
            settlement_ref=(getattr(settings, "NOVA_POSHTA_SENDER_SETTLEMENT_REF", "") or "").strip(),
            city_ref=(getattr(settings, "NOVA_POSHTA_SENDER_CITY_REF", "") or "").strip(),
            warehouse_label=sender_warehouse,
            warehouse_ref=(getattr(settings, "NOVA_POSHTA_SENDER_WAREHOUSE_REF", "") or "").strip(),
            preferred_kind="branch",
            point_role="відправника",
        )

    def _resolve_point(
        self,
        *,
        city_label: str,
        settlement_ref: str,
        city_ref: str,
        warehouse_label: str,
        warehouse_ref: str,
        preferred_kind: str,
        point_role: str,
    ) -> NovaPoshtaResolvedPoint:
        normalized_city = str(city_label or "").strip()
        normalized_warehouse = str(warehouse_label or "").strip()
        normalized_settlement_ref = str(settlement_ref or "").strip()
        normalized_city_ref = str(city_ref or "").strip()
        normalized_warehouse_ref = str(warehouse_ref or "").strip()

        if not normalized_city_ref and not normalized_settlement_ref:
            city = self._pick_city_candidate(normalized_city, point_role=point_role)
            normalized_settlement_ref = city.get("settlement_ref", "")
            normalized_city_ref = city.get("city_ref", "")
            normalized_city = city.get("label", normalized_city)

        warehouse = self._pick_warehouse_candidate(
            normalized_warehouse,
            settlement_ref=normalized_settlement_ref,
            city_ref=normalized_city_ref,
            warehouse_ref=normalized_warehouse_ref,
            preferred_kind=preferred_kind,
            point_role=point_role,
        )
        return NovaPoshtaResolvedPoint(
            city_label=normalized_city,
            warehouse_label=warehouse.get("label", normalized_warehouse or normalized_city),
            settlement_ref=normalized_settlement_ref,
            city_ref=normalized_city_ref,
            warehouse_ref=warehouse.get("ref", ""),
            warehouse_kind=warehouse.get("kind", "branch"),
        )

    def _pick_city_candidate(self, query: str, *, point_role: str) -> dict[str, str]:
        normalized_query = str(query or "").strip()
        if not normalized_query:
            raise NovaPoshtaDocumentError(f"Не вказано місто {point_role}.")

        items = self.directory.search_settlements(normalized_query, limit=10)
        if not items:
            raise NovaPoshtaDocumentError(f"Не вдалося знайти місто {point_role} в довіднику Нової пошти.")

        normalized_target = self._normalize_name(normalized_query)
        exact = [
            item for item in items
            if self._normalize_name(item.get("label")) == normalized_target
            or self._normalize_name(item.get("main_description")) == normalized_target
        ]
        if exact:
            return exact[0]

        for item in items:
            label = self._normalize_name(item.get("label"))
            if normalized_target and normalized_target in label:
                return item
        return items[0]

    def _pick_warehouse_candidate(
        self,
        query: str,
        *,
        settlement_ref: str,
        city_ref: str,
        warehouse_ref: str,
        preferred_kind: str,
        point_role: str,
    ) -> dict[str, str]:
        if warehouse_ref:
            items = self.directory.search_warehouses(
                settlement_ref=settlement_ref,
                city_ref=city_ref,
                kind="all",
                limit=50,
            )
            for item in items:
                if str(item.get("ref") or "").strip() == warehouse_ref:
                    return item

        normalized_query = str(query or "").strip()
        if not normalized_query:
            raise NovaPoshtaDocumentError(f"Не вказано відділення/поштомат {point_role}.")

        items = self.directory.search_warehouses(
            settlement_ref=settlement_ref,
            city_ref=city_ref,
            query=normalized_query,
            kind=preferred_kind if preferred_kind in {"branch", "postomat"} else "all",
            limit=25,
        )
        if not items and preferred_kind != "all":
            items = self.directory.search_warehouses(
                settlement_ref=settlement_ref,
                city_ref=city_ref,
                query=normalized_query,
                kind="all",
                limit=25,
            )
        if not items:
            raise NovaPoshtaDocumentError(
                f"Не вдалося знайти відділення/поштомат {point_role} в довіднику Нової пошти."
            )

        number = "".join(ch for ch in normalized_query if ch.isdigit())
        if number:
            for item in items:
                if str(item.get("number") or "").strip() == number:
                    return item

        normalized_target = self._normalize_name(normalized_query)
        exact = [
            item for item in items
            if normalized_target in {
                self._normalize_name(item.get("label")),
                self._normalize_name(item.get("description")),
                self._normalize_name(item.get("short_address")),
            }
        ]
        if exact:
            return exact[0]

        for item in items:
            haystack = " ".join(
                self._normalize_name(item.get(key))
                for key in ("label", "description", "short_address")
            )
            if normalized_target and normalized_target in haystack:
                return item
        return items[0]

    def _create_recipient_counterparty(
        self,
        city_ref: str,
        person_name: dict[str, str],
        phone: str,
    ) -> str:
        response = self._request(
            "Counterparty",
            "save",
            {
                "CounterpartyProperty": "Recipient",
                "CityRef": city_ref,
                "CounterpartyType": "PrivatePerson",
                "FirstName": person_name["first_name"],
                "MiddleName": person_name["middle_name"],
                "LastName": person_name["last_name"],
                "Phone": phone,
            },
        )
        recipient = next(iter(response.get("data") or []), None) or {}
        recipient_ref = str(recipient.get("Ref") or "").strip()
        if not recipient_ref:
            raise NovaPoshtaDocumentError("Nova Poshta API не повернув Ref одержувача.")
        return recipient_ref

    def _create_recipient_contact(
        self,
        counterparty_ref: str,
        person_name: dict[str, str],
        phone: str,
    ) -> str:
        response = self._request(
            "ContactPerson",
            "save",
            {
                "CounterpartyRef": counterparty_ref,
                "FirstName": person_name["first_name"],
                "MiddleName": person_name["middle_name"],
                "LastName": person_name["last_name"],
                "Phone": phone,
            },
        )
        contact = next(iter(response.get("data") or []), None) or {}
        contact_ref = str(contact.get("Ref") or "").strip()
        if not contact_ref:
            contacts = self._request(
                "Counterparty",
                "getCounterpartyContactPersons",
                {"Ref": counterparty_ref},
            )
            contact = next(iter(contacts.get("data") or []), None) or {}
            contact_ref = str(contact.get("Ref") or "").strip()
        if not contact_ref:
            raise NovaPoshtaDocumentError("Nova Poshta API не повернув контактну особу одержувача.")
        return contact_ref

    def _request(self, model_name: str, called_method: str, method_properties: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "apiKey": self.api_key,
            "modelName": model_name,
            "calledMethod": called_method,
            "methodProperties": method_properties or {},
        }
        try:
            response = requests.post(self.api_url, json=payload, timeout=self.REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as exc:
            logger.warning("Nova Poshta document request failed for %s.%s: %s", model_name, called_method, exc)
            raise NovaPoshtaDocumentError("Не вдалося зв’язатися з Nova Poshta API.") from exc
        except ValueError as exc:
            logger.warning("Nova Poshta document request returned invalid JSON for %s.%s", model_name, called_method)
            raise NovaPoshtaDocumentError("Nova Poshta API повернув некоректну відповідь.") from exc

        errors = [str(item).strip() for item in data.get("errors") or [] if str(item).strip()]
        if errors:
            raise NovaPoshtaDocumentError("; ".join(errors))
        if not data.get("success"):
            raise NovaPoshtaDocumentError("Nova Poshta API не підтвердив створення накладної.")
        return data

    def _get_cod_amount(self, order) -> Decimal:
        pay_type = str(getattr(order, "pay_type", "") or "").strip()
        if pay_type == "prepay_200":
            remaining = getattr(order, "get_remaining_amount", None)
            if callable(remaining):
                return max(self._as_money(remaining()), Decimal("0.00"))
        if pay_type == "cod":
            return max(self._as_money(getattr(order, "total_sum", 0)), Decimal("0.00"))
        return Decimal("0.00")

    @staticmethod
    def _normalize_name(value: Any) -> str:
        return " ".join(str(value or "").strip().lower().split())

    @staticmethod
    def _normalize_decimal(
        value: Any,
        *,
        fallback: Decimal,
        minimum: Decimal = Decimal("0"),
    ) -> Decimal:
        try:
            normalized = Decimal(str(value if value not in (None, "") else fallback))
        except (InvalidOperation, ValueError, TypeError):
            normalized = fallback
        if normalized < minimum:
            return fallback
        return normalized

    @staticmethod
    def _as_money(value: Any) -> Decimal:
        try:
            normalized = Decimal(str(value if value not in (None, "") else "0"))
        except (InvalidOperation, ValueError, TypeError):
            normalized = Decimal("0")
        return normalized.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _normalize_dimensions(self, length: Any, width: Any, height: Any) -> tuple[Decimal, Decimal, Decimal]:
        return (
            self._normalize_decimal(length, fallback=self.DEFAULT_LENGTH_CM, minimum=Decimal("1")),
            self._normalize_decimal(width, fallback=self.DEFAULT_WIDTH_CM, minimum=Decimal("1")),
            self._normalize_decimal(height, fallback=self.DEFAULT_HEIGHT_CM, minimum=Decimal("1")),
        )

    @staticmethod
    def _format_decimal(value: Decimal, *, trim_zeroes: bool = False) -> str:
        text = format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")
        if trim_zeroes:
            return text.rstrip("0").rstrip(".") or "0"
        return text.rstrip("0").rstrip(".") if "." in text else text

    @classmethod
    def _format_money(cls, value: Decimal) -> str:
        return cls._format_decimal(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    @classmethod
    def _format_volume(cls, length_cm: Decimal, width_cm: Decimal, height_cm: Decimal) -> str:
        volume = (length_cm * width_cm * height_cm) / Decimal("1000000")
        return cls._format_decimal(volume.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))
