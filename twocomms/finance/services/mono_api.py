"""Низькорівневий клієнт Monobank Personal API (https://api.monobank.ua).

Покриває персональний API:
- GET  /personal/client-info        — рахунки (картки) + банки (jars) клієнта;
- GET  /personal/statement/{acc}/{from}/{to}  — виписка за період (≤ 31 доба);
- POST /personal/webhook            — встановлення URL вебхука;
- GET  /bank/currency               — публічні курси валют.

Особливості API, які тут враховано:
- авторизація заголовком ``X-Token``;
- ліміт: не частіше ніж 1 запит на 60 секунд до client-info та statement;
- виписка повертає максимум 500 записів за один запит; вікно ≤ 31 доба +1 год;
- суми у мінімальних одиницях (копійки), currencyCode — числовий ISO-4217;
- ``account`` у виписці може бути ``0`` для дефолтного рахунку.

Клієнт навмисно тонкий: лише HTTP + парсинг JSON + типізовані помилки.
Бізнес-логіка (мапінг у наші моделі, дедуплікація) — у ``services.mono``.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import requests

API_BASE = 'https://api.monobank.ua'
DEFAULT_TIMEOUT = 20  # с
# Максимальне вікно виписки за документацією: 31 доба + 1 година.
MAX_STATEMENT_WINDOW = 60 * 60 * 24 * 31 + 60 * 60

# Числовий ISO-4217 → буквений код (підмножина, актуальна для UA-гаманців).
ISO_NUM_TO_ALPHA = {
    980: 'UAH', 840: 'USD', 978: 'EUR', 985: 'PLN', 826: 'GBP',
    643: 'RUB', 985: 'PLN', 756: 'CHF', 124: 'CAD', 203: 'CZK',
}


def iso_alpha(code) -> str:
    """Числовий ISO-код валюти → буквений (фолбек 'UAH')."""
    try:
        return ISO_NUM_TO_ALPHA.get(int(code), 'UAH')
    except (TypeError, ValueError):
        return 'UAH'


class MonoApiError(Exception):
    """Базова помилка Monobank API."""

    def __init__(self, message, *, status=None, payload=None):
        super().__init__(message)
        self.status = status
        self.payload = payload


class MonoAuthError(MonoApiError):
    """Невалідний/відкликаний токен (403)."""


class MonoRateLimitError(MonoApiError):
    """Перевищено ліміт запитів (429) — повторити пізніше."""


@dataclass
class MonoAccount:
    id: str
    send_id: str
    balance: int           # копійки
    credit_limit: int      # копійки
    type: str              # black/white/platinum/iron/fop/yellow/eAid/...
    currency_code: int     # числовий ISO-4217
    masked_pan: list
    iban: str

    @property
    def currency(self) -> str:
        return iso_alpha(self.currency_code)

    @property
    def is_fop(self) -> bool:
        return (self.type or '').lower() == 'fop'

    @property
    def pan(self) -> str:
        return (self.masked_pan or [''])[0] if self.masked_pan else ''


@dataclass
class MonoJar:
    id: str
    send_id: str
    title: str
    description: str
    currency_code: int
    balance: int
    goal: int

    @property
    def currency(self) -> str:
        return iso_alpha(self.currency_code)


class MonoClient:
    """Тонка обгортка над Monobank Personal API під один токен клієнта."""

    def __init__(self, token: str, *, base=API_BASE, timeout=DEFAULT_TIMEOUT, session=None):
        if not token:
            raise MonoAuthError('Порожній токен')
        self._token = token
        self._base = base.rstrip('/')
        self._timeout = timeout
        self._session = session or requests.Session()
        self._client_info_cache = None

    # ----------------------------- HTTP -----------------------------

    def _request(self, method, path, *, params=None, json_body=None):
        url = f'{self._base}{path}'
        headers = {'X-Token': self._token, 'Accept': 'application/json'}
        try:
            resp = self._session.request(
                method, url, headers=headers, params=params, json=json_body,
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise MonoApiError(f'Помилка з’єднання з Monobank: {exc}') from exc

        if resp.status_code == 403:
            raise MonoAuthError('Невалідний або відкликаний токен Monobank', status=403)
        if resp.status_code == 429:
            raise MonoRateLimitError('Перевищено ліміт запитів Monobank (1/60с)', status=429)
        if resp.status_code >= 400:
            payload = _safe_json(resp)
            msg = (payload or {}).get('errorDescription') or f'HTTP {resp.status_code}'
            raise MonoApiError(f'Monobank API: {msg}', status=resp.status_code, payload=payload)
        return _safe_json(resp)

    @staticmethod
    def _safe_json_static(resp):  # backwards alias
        return _safe_json(resp)

    # ----------------------------- Endpoints -----------------------------

    def client_info(self, *, refresh=False) -> dict:
        """Сирі дані /personal/client-info (name, accounts[], jars[]).

        Кешується в межах життя клієнта: Monobank лімітує 1 запит/60с, тож
        у рамках одного флоу (connect→discover→link) робимо лише один виклик.
        """
        if self._client_info_cache is not None and not refresh:
            return self._client_info_cache
        self._client_info_cache = self._request('GET', '/personal/client-info') or {}
        return self._client_info_cache

    def seed_client_info(self, info: dict) -> None:
        """Підставляє вже отриманий client-info (щоб не витрачати ліміт повторно)."""
        if info:
            self._client_info_cache = info

    def accounts(self) -> list:
        """Список рахунків (карток) клієнта як MonoAccount."""
        info = self.client_info()
        out = []
        for a in info.get('accounts', []) or []:
            out.append(MonoAccount(
                id=a.get('id', ''), send_id=a.get('sendId', ''),
                balance=int(a.get('balance', 0) or 0),
                credit_limit=int(a.get('creditLimit', 0) or 0),
                type=a.get('type', ''), currency_code=a.get('currencyCode', 980),
                masked_pan=a.get('maskedPan', []) or [], iban=a.get('iban', '') or '',
            ))
        return out

    def jars(self) -> list:
        info = self.client_info()
        out = []
        for j in info.get('jars', []) or []:
            out.append(MonoJar(
                id=j.get('id', ''), send_id=j.get('sendId', ''),
                title=j.get('title', ''), description=j.get('description', ''),
                currency_code=j.get('currencyCode', 980),
                balance=int(j.get('balance', 0) or 0), goal=int(j.get('goal', 0) or 0),
            ))
        return out

    def statement(self, account_id: str, frm: int, to: int) -> list:
        """Виписка за рахунком за період [frm, to] (UNIX-секунди).

        Повертає список сирих StatementItem (max 500). Вікно має бути ≤ 31 доба.
        ``account_id`` може бути '0' для дефолтного рахунку.
        """
        if to - frm > MAX_STATEMENT_WINDOW:
            raise MonoApiError('Вікно виписки перевищує 31 добу')
        acc = account_id or '0'
        data = self._request('GET', f'/personal/statement/{acc}/{int(frm)}/{int(to)}')
        return data if isinstance(data, list) else []

    def set_webhook(self, webhook_url: str) -> dict:
        """Встановлює URL вебхука для push-нотифікацій про нові транзакції."""
        return self._request('POST', '/personal/webhook',
                             json_body={'webHookUrl': webhook_url}) or {}

    def currency(self) -> list:
        """Публічні курси валют (без токена потрібен, але шлемо для простоти)."""
        data = self._request('GET', '/bank/currency')
        return data if isinstance(data, list) else []


def _safe_json(resp):
    try:
        return resp.json()
    except ValueError:
        return None


def validate_token(token: str) -> dict:
    """Швидка перевірка токена: повертає {ok, name, accounts, jars} або кидає.

    Використовується при підключенні, щоб одразу дати фідбек користувачу.
    """
    client = MonoClient(token)
    info = client.client_info()
    return {
        'ok': True,
        'name': info.get('name', ''),
        'accounts': info.get('accounts', []) or [],
        'jars': info.get('jars', []) or [],
        'client_id': info.get('clientId', ''),
    }
