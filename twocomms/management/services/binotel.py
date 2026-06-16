"""
Клієнт Binotel REST API 4.0 (порт офіційної бібліотеки BinotelApi.php на Python).

Документація: https://web.archive.org/web/20240227235014/http://developers.binotel.ua/

Особливості API:
- Транспорт: POST на ``{base}{version}/{endpoint}.json`` (наприклад
  ``https://api.binotel.com/api/4.0/calls/internal-number-to-external-number.json``).
- Тіло запиту: raw JSON, до якого додаються поля ``key`` і ``secret``.
- Успіх: ``{"status": "success", ...}``; помилка:
  ``{"status": "error", "code": <int>, "message": "..."}``.

Ключі (``BINOTEL_API_KEY`` / ``BINOTEL_API_SECRET`` / ``BINOTEL_COMPANY_ID``)
зберігаються лише в ENV на сервері, ніколи в репозиторії.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Коди помилок REST API (REST API: List of errors).
BINOTEL_ERROR_MESSAGES = {
    102: "No such method",
    103: "Not enough data",
    104: "Wrong data",
    105: "Something went wrong",
    106: "Requests are too frequent",
    120: "Your company is disabled",
    121: "Your key or secret is wrong",
    150: "Can't call to the ext",
    151: "Can't call to the external number",
}

# Стани дзвінка (disposition), при яких доступний запис розмови.
RECORDING_AVAILABLE_DISPOSITIONS = {"ANSWER", "VM-SUCCESS", "SUCCESS"}


class BinotelError(Exception):
    """Помилка рівня Binotel REST API або транспорту."""

    def __init__(self, message: str, code: int | None = None, *, raw: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.raw = raw

    def __str__(self) -> str:
        if self.code is not None:
            return f"[{self.code}] {self.message}"
        return self.message


class BinotelNotConfigured(BinotelError):
    """Не задані ключі Binotel в ENV."""


class BinotelClient:
    """Тонкий клієнт навколо Binotel REST API 4.0."""

    def __init__(
        self,
        key: str,
        secret: str,
        *,
        api_base: str | None = None,
        api_version: str | None = None,
        timeout: int | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.key = (key or "").strip()
        self.secret = (secret or "").strip()
        self.api_base = (api_base or "https://api.binotel.com/api/").strip()
        if not self.api_base.endswith("/"):
            self.api_base += "/"
        self.api_version = (api_version or "4.0").strip()
        self.timeout = int(timeout or 25)
        self._session = session or requests.Session()

    # --- factory / config helpers -------------------------------------

    @classmethod
    def from_settings(cls) -> "BinotelClient":
        """Створює клієнт з налаштувань Django. Кидає BinotelNotConfigured."""
        key = getattr(settings, "BINOTEL_API_KEY", "") or ""
        secret = getattr(settings, "BINOTEL_API_SECRET", "") or ""
        if not key or not secret:
            raise BinotelNotConfigured(
                "Не задані BINOTEL_API_KEY / BINOTEL_API_SECRET в ENV."
            )
        return cls(
            key,
            secret,
            api_base=getattr(settings, "BINOTEL_API_BASE", None),
            api_version=getattr(settings, "BINOTEL_API_VERSION", None),
            timeout=getattr(settings, "BINOTEL_API_TIMEOUT", 25),
        )

    @staticmethod
    def is_configured() -> bool:
        return bool(
            (getattr(settings, "BINOTEL_API_KEY", "") or "")
            and (getattr(settings, "BINOTEL_API_SECRET", "") or "")
        )

    def _build_url(self, endpoint: str) -> str:
        endpoint = (endpoint or "").strip().strip("/")
        return f"{self.api_base}{self.api_version}/{endpoint}.json"

    # --- core ----------------------------------------------------------

    def send_request(self, endpoint: str, params: dict | None = None) -> dict:
        """
        Виконує POST-запит до Binotel і повертає декодований словник.

        Кидає :class:`BinotelError` при транспортній помилці, не-200 коді,
        невалідному JSON або ``status != success``.
        """
        payload = dict(params or {})
        payload["key"] = self.key
        payload["secret"] = self.secret
        url = self._build_url(endpoint)

        try:
            response = self._session.post(
                url,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            logger.warning("Binotel transport error on %s: %s", endpoint, exc)
            raise BinotelError(f"Помилка з'єднання з Binotel: {exc}") from exc

        if response.status_code != 200:
            raise BinotelError(
                f"Binotel HTTP {response.status_code}",
                raw=response.text[:2000],
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise BinotelError(
                "Binotel повернув невалідний JSON.",
                raw=response.text[:2000],
            ) from exc

        if not isinstance(data, dict):
            raise BinotelError("Binotel повернув неочікувану структуру.", raw=data)

        if data.get("status") != "success":
            code = data.get("code")
            try:
                code = int(code) if code is not None else None
            except (TypeError, ValueError):
                code = None
            message = data.get("message") or BINOTEL_ERROR_MESSAGES.get(
                code, "Невідома помилка Binotel"
            )
            raise BinotelError(message, code=code, raw=data)

        return data

    # --- SETTINGS ------------------------------------------------------

    def list_of_employees(self) -> dict:
        """Усі співробітники (включно з internalNumber та станом ліній)."""
        return self.send_request("settings/list-of-employees")

    def list_of_voice_files(self) -> dict:
        return self.send_request("settings/list-of-voice-files")

    def list_of_routes(self) -> dict:
        return self.send_request("settings/list-of-routes")

    def change_employee_presence_state(self, employee_id: str, presence_state: str) -> dict:
        return self.send_request(
            "settings/change-employee-presence-state",
            {"employeeID": employee_id, "presenceState": presence_state},
        )

    # --- CALLS ---------------------------------------------------------

    def internal_to_external(
        self,
        internal_number: str,
        external_number: str,
        **extra: Any,
    ) -> dict:
        """
        Двосторонній дзвінок: внутрішня лінія співробітника → зовнішній номер.
        Повертає generalCallID. Додаткові параметри: pbxNumber, limitCallTime,
        callTimeToExt, playbackWaiting, callerIdForEmployee, async.
        """
        params = {
            "internalNumber": str(internal_number),
            "externalNumber": str(external_number),
        }
        params.update({k: v for k, v in extra.items() if v not in (None, "")})
        return self.send_request("calls/internal-number-to-external-number", params)

    def external_to_external(
        self,
        external_number1: str,
        external_number2: str,
        pbx_number: str,
        **extra: Any,
    ) -> dict:
        params = {
            "externalNumber1": str(external_number1),
            "externalNumber2": str(external_number2),
            "pbxNumber": str(pbx_number),
        }
        params.update({k: v for k, v in extra.items() if v not in (None, "")})
        return self.send_request("calls/external-number-to-external-number", params)

    def hangup_call(self, general_call_id: str) -> dict:
        return self.send_request("calls/hangup-call", {"generalCallID": str(general_call_id)})

    def attended_call_transfer(self, general_call_id: str, external_number: str) -> dict:
        return self.send_request(
            "calls/attended-call-transfer",
            {"generalCallID": str(general_call_id), "externalNumber": str(external_number)},
        )

    def call_with_announcement(self, external_number: str, voice_file_id: str) -> dict:
        return self.send_request(
            "calls/call-with-announcement",
            {"externalNumber": str(external_number), "voiceFileID": str(voice_file_id)},
        )

    # --- STATS ---------------------------------------------------------

    def online_calls(self) -> dict:
        return self.send_request("stats/online-calls")

    def call_details(self, general_call_ids: list[str] | str) -> dict:
        if not isinstance(general_call_ids, (list, tuple)):
            general_call_ids = [general_call_ids]
        return self.send_request(
            "stats/call-details",
            {"generalCallID": [str(i) for i in general_call_ids]},
        )

    def call_record(self, general_call_id: str) -> dict:
        """
        Посилання на запис розмови. Час життя посилання — 15 хвилин.
        Доступно лише для дзвінків з disposition ANSWER / VM-SUCCESS / SUCCESS.
        """
        return self.send_request(
            "stats/call-record", {"generalCallID": str(general_call_id)}
        )

    def list_of_calls_for_period(self, start_time: int, stop_time: int) -> dict:
        """Вхідні + вихідні за період (не більше 24 годин)."""
        return self.send_request(
            "stats/list-of-calls-for-period",
            {"startTime": int(start_time), "stopTime": int(stop_time)},
        )

    def list_of_calls_per_day(self, day_in_timestamp: int | None = None) -> dict:
        params = {}
        if day_in_timestamp is not None:
            params["dayInTimestamp"] = int(day_in_timestamp)
        return self.send_request("stats/list-of-calls-per-day", params)

    def list_of_calls_by_internal_number_for_period(
        self, internal_number: str, start_time: int, stop_time: int
    ) -> dict:
        """Дзвінки по внутрішньому номеру за період (не більше 7 днів)."""
        return self.send_request(
            "stats/list-of-calls-by-internal-number-for-period",
            {
                "internalNumber": str(internal_number),
                "startTime": int(start_time),
                "stopTime": int(stop_time),
            },
        )

    def recent_calls_by_internal_number(self, internal_number: str) -> dict:
        return self.send_request(
            "stats/recent-calls-by-internal-number",
            {"internalNumber": str(internal_number)},
        )

    def list_of_lost_calls_for_today(self) -> dict:
        return self.send_request("stats/list-of-lost-calls-for-today")

    def history_by_external_number(self, external_numbers: list[str] | str) -> dict:
        if not isinstance(external_numbers, (list, tuple)):
            external_numbers = [external_numbers]
        return self.send_request(
            "stats/history-by-external-number",
            {"externalNumbers": [str(n) for n in external_numbers]},
        )

    # --- CUSTOMERS -----------------------------------------------------

    def customers_search(self, subject: str) -> dict:
        return self.send_request("customers/search", {"subject": subject})

    def customers_list(self) -> dict:
        return self.send_request("customers/list")
