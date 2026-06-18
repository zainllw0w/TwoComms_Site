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
import re
import time
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

# Людські пояснення кодів помилок (для UI).
BINOTEL_ERROR_HINTS_UK = {
    102: "Такого методу не існує (перевірте назву endpoint).",
    103: "Недостатньо даних у запиті (відсутній обов'язковий параметр).",
    104: "Невірні дані у запиті.",
    105: "Щось пішло не так на боці Binotel.",
    106: "Забагато запитів поспіль — спрацював rate limit (5 запитів/хв).",
    120: "Вашу компанію вимкнено в Binotel.",
    121: "Невірні key або secret (перевірте ключі в ENV).",
    150: "Неможливо подзвонити на внутрішню лінію (перевірте internalNumber / стан лінії).",
    151: "Неможливо подзвонити на зовнішній номер (перевірте формат номера).",
}

# Стани дзвінка (disposition), при яких доступний запис розмови.
RECORDING_AVAILABLE_DISPOSITIONS = {"ANSWER", "VM-SUCCESS", "SUCCESS"}

# Класифікація disposition для UI/логіки.
DISPOSITION_META = {
    "ANSWER": {"group": "success", "label_uk": "Успішний дзвінок", "final": True},
    "TRANSFER": {"group": "success", "label_uk": "Успішний (переведений)", "final": True},
    "ONLINE": {"group": "online", "label_uk": "У розмові", "final": False},
    "BUSY": {"group": "failed", "label_uk": "Зайнято", "final": True},
    "NOANSWER": {"group": "failed", "label_uk": "Немає відповіді", "final": True},
    "CANCEL": {"group": "failed", "label_uk": "Скасовано", "final": True},
    "CONGESTION": {"group": "failed", "label_uk": "Перевантаження мережі", "final": True},
    "CHANUNAVAIL": {"group": "failed", "label_uk": "Лінія недоступна", "final": True},
    "VM": {"group": "voicemail", "label_uk": "Голосова пошта (без повідомлення)", "final": True},
    "VM-SUCCESS": {"group": "voicemail", "label_uk": "Голосова пошта (з повідомленням)", "final": True},
    "SMS-SENDING": {"group": "sms", "label_uk": "SMS відправляється", "final": False},
    "SMS-SUCCESS": {"group": "sms", "label_uk": "SMS відправлено", "final": True},
    "SMS-FAILED": {"group": "sms", "label_uk": "SMS не відправлено", "final": True},
    "SUCCESS": {"group": "success", "label_uk": "Факс прийнято", "final": True},
    "FAILED": {"group": "failed", "label_uk": "Факс не прийнято", "final": True},
}

# Ендпоінти, безпечні для повторної відправки (читання/ідемпотентні).
# ВАЖЛИВО: calls/* НІКОЛИ не ретраяться — повторний POST може ініціювати
# дубль реального дзвінка клієнту навіть якщо перший запит "завис" по timeout.
_IDEMPOTENT_PREFIXES = ("stats/", "settings/list", "customers/list", "customers/search",
                        "customers/take", "customers/listOfLabels")

# Офіційний список IP-адрес серверів Binotel, з яких приходять вебхуки
# (apiCallSettings / apiCallCompleted). Приймати запити лише з цих адрес.
BINOTEL_SERVER_IPS = frozenset({
    "194.88.218.116",  # my.binotel.ua
    "194.88.218.114", "194.88.218.117", "194.88.218.118",
    "194.88.219.67", "194.88.219.78", "194.88.219.70", "194.88.219.71",
    "194.88.219.72", "194.88.219.79", "194.88.219.80", "194.88.219.81",
    "194.88.219.82", "194.88.219.83", "194.88.219.84", "194.88.219.85",
    "194.88.219.86", "194.88.219.87", "194.88.219.88", "194.88.219.89",
    "194.88.219.92", "194.88.218.119", "194.88.218.120",
    "185.100.66.145", "185.100.66.146", "185.100.66.147",
})


def normalize_phone(value: str) -> str:
    """Прибирає форматування з номера, лишаючи цифри та провідний +."""
    if value is None:
        return ""
    value = str(value).strip()
    plus = value.startswith("+")
    digits = re.sub(r"\D", "", value)
    return ("+" + digits) if plus else digits


def client_ip_from_request(request) -> str:
    """Визначає IP джерела запиту з урахуванням проксі/Passenger.

    Бере крайній лівий IP з X-Forwarded-For (це початковий клієнт), інакше
    REMOTE_ADDR. Для звірки з whitelist Binotel цього достатньо; підмінити
    XFF може лише той, хто вже за нашим проксі."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first
    return (request.META.get("REMOTE_ADDR") or "").strip()


def is_binotel_ip(ip: str) -> bool:
    return bool(ip) and ip in BINOTEL_SERVER_IPS


def parse_webhook_call_details(call_details: dict) -> dict:
    """Витягує ключові поля з callDetails вебхука apiCallCompleted у плаский dict.

    Структура callDetails задокументована в розділі STATS (єдина для всього API).
    Повертає поля, зручні для збереження у CallRecord.
    """
    if not isinstance(call_details, dict):
        return {}
    call_type = str(call_details.get("callType", ""))
    direction = "inbound" if call_type == "0" else ("outbound" if call_type == "1" else "unknown")
    employee = call_details.get("employeeData") or {}
    customer = call_details.get("customerData") or {}
    return {
        "general_call_id": str(call_details.get("generalCallID") or ""),
        "company_id": str(call_details.get("companyID") or ""),
        "call_type": call_type,
        "direction": direction,
        "external_number": normalize_phone(call_details.get("externalNumber") or ""),
        "internal_number": str(call_details.get("internalNumber") or ""),
        "start_time": call_details.get("startTime"),
        "wait_seconds": call_details.get("waitsec") or 0,
        "bill_seconds": call_details.get("billsec") or 0,
        "disposition": call_details.get("disposition") or "",
        "employee_name": employee.get("name") or "",
        "employee_email": employee.get("email") or "",
        "customer_id": (customer.get("id") if isinstance(customer, dict) else None),
        "customer_name": (customer.get("name") if isinstance(customer, dict) else "") or "",
    }


def mask_secret(value: str) -> str:
    """Маскує секрет для логів: лишає перші 3 символи."""
    if not value:
        return ""
    value = str(value)
    if len(value) <= 4:
        return "***"
    return value[:3] + "***"


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

    @property
    def hint(self) -> str:
        return BINOTEL_ERROR_HINTS_UK.get(self.code, "") if self.code else ""


class BinotelNotConfigured(BinotelError):
    """Не задані ключі Binotel в ENV."""


_SESSION = None


def _shared_session() -> requests.Session:
    """Єдина requests.Session з пулом keep-alive з'єднань на процес.

    Ретраї тут НЕ налаштовуємо на рівні адаптера: політику повторів
    застосовуємо вручну в send_request, бо вона залежить від ідемпотентності
    конкретного методу (calls/* ретраїти не можна)."""
    global _SESSION
    if _SESSION is None:
        s = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=4, pool_maxsize=8, max_retries=0
        )
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        _SESSION = s
    return _SESSION





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
        max_retries: int = 2,
    ) -> None:
        self.key = (key or "").strip()
        self.secret = (secret or "").strip()
        self.api_base = (api_base or "https://api.binotel.com/api/").strip()
        if not self.api_base.endswith("/"):
            self.api_base += "/"
        self.api_version = (api_version or "4.0").strip()
        # Роздільні таймаути (connect, read): з'єднання має встановлюватися
        # швидко, а read може бути довшим (ініціювання дзвінка чекає лінію).
        total = int(timeout or 25)
        self.timeout = (min(10, total), total)
        self.max_retries = max(0, int(max_retries))
        self._session = session or _shared_session()

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

    @staticmethod
    def _is_idempotent(endpoint: str) -> bool:
        ep = (endpoint or "").strip().strip("/")
        return ep.startswith(_IDEMPOTENT_PREFIXES)

    # --- core ----------------------------------------------------------

    def send_request(self, endpoint: str, params: dict | None = None) -> dict:
        """
        Виконує POST-запит до Binotel і повертає декодований словник.

        Повтори застосовуються ЛИШЕ для ідемпотентних методів (stats/settings/
        читання customers) при транспортних помилках, HTTP 5xx та коді 106
        (rate limit). calls/* ніколи не повторюються, щоб не створити дубль
        реального дзвінка.

        Кидає :class:`BinotelError` при транспортній помилці, не-200 коді,
        невалідному JSON або ``status != success``.
        """
        endpoint_clean = (endpoint or "").strip().strip("/")
        idempotent = self._is_idempotent(endpoint_clean)
        attempts = (self.max_retries + 1) if idempotent else 1
        last_exc: BinotelError | None = None

        for attempt in range(attempts):
            try:
                return self._send_once(endpoint_clean, params)
            except BinotelError as exc:
                last_exc = exc
                retriable = idempotent and self._is_retriable(exc)
                if not retriable or attempt == attempts - 1:
                    raise
                # Експоненційний backoff; для 106 (rate limit) — довша пауза.
                base = 10.0 if exc.code == 106 else 0.6
                time.sleep(base * (2 ** attempt))
        # Недосяжно, але про всяк випадок:
        raise last_exc or BinotelError("Невідома помилка Binotel")

    @staticmethod
    def _is_retriable(exc: BinotelError) -> bool:
        # Rate limit — ретраїмо.
        if exc.code == 106:
            return True
        # Помилки рівня API (auth/wrong data/...) не ретраяться.
        if exc.code is not None:
            return False
        # Транспорт/HTTP-5xx/невалідний JSON (code is None) — ретраїмо.
        return True

    def _send_once(self, endpoint: str, params: dict | None = None) -> dict:
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
            logger.warning(
                "Binotel transport error on %s (key=%s): %s",
                endpoint, mask_secret(self.key), exc,
            )
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
            "internalNumber": str(internal_number).strip(),
            "externalNumber": normalize_phone(external_number),
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

    @staticmethod
    def extract_record_url(data: dict) -> str:
        """Дістає URL запису з відповіді call-record (буває в url або callDetails)."""
        if not isinstance(data, dict):
            return ""
        url = data.get("url")
        if not url:
            details = data.get("callDetails")
            if isinstance(details, dict):
                url = details.get("url")
            elif isinstance(details, str):
                url = details
        return url or ""

    def fetch_record_stream(self, general_call_id: str):
        """Повертає (requests.Response stream, url) для запису розмови.

        Тягне mp3 з сервера Binotel server-side — так браузер отримує файл з
        нашого https-домену (без mixed-content і без короткоживучого посилання).
        Викликач зобовʼязаний закрити response.
        """
        data = self.call_record(general_call_id)
        url = self.extract_record_url(data)
        if not url:
            raise BinotelError("Для цього дзвінка немає запису розмови.", raw=data)
        # Якщо Binotel віддав http — все одно тягнемо server-side, клієнту піде https.
        resp = self._session.get(url, stream=True, timeout=(min(10, self.timeout[1]), 60))
        if resp.status_code != 200:
            resp.close()
            raise BinotelError(f"Не вдалося завантажити запис (HTTP {resp.status_code}).")
        return resp, url

    def fetch_record_bytes(self, general_call_id: str) -> tuple[bytes, str]:
        """Повертає (повні байти mp3, content_type) запису розмови.

        Тягне файл цілком server-side. Потрібно для коректної перемотки в
        браузері: HTML5-плеєр уміє seek лише коли наш бекенд підтримує HTTP
        Range, а для цього зручно мати повний буфер (дзвінки короткі, кілька МБ).
        """
        upstream, _url = self.fetch_record_stream(general_call_id)
        try:
            content_type = upstream.headers.get("Content-Type") or "audio/mpeg"
            if "audio" not in content_type and "mpeg" not in content_type:
                content_type = "audio/mpeg"
            chunks = []
            for chunk in upstream.iter_content(chunk_size=64 * 1024):
                if chunk:
                    chunks.append(chunk)
            return b"".join(chunks), content_type
        finally:
            upstream.close()

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
