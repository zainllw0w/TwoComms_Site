"""Симетричне шифрування секретів інтеграцій (банківські API-токени).

Токени Monobank (та інших провайдерів) ніколи не зберігаються у відкритому
вигляді. Ми шифруємо їх Fernet (AES-128-CBC + HMAC-SHA256, authenticated),
а ключ шифрування виводимо з ``settings.FINANCE_TOKEN_KEY`` або (фолбек)
з ``settings.SECRET_KEY`` через HKDF-SHA256. У БД лягає лише шифротекст.

Модель безпеки:
- compromise БД без ключа застосунку → токени марні (шифротекст);
- ключ живе в env (``FINANCE_TOKEN_KEY``) або похідний від ``SECRET_KEY``,
  тобто поза дампом таблиць;
- ``fingerprint`` (HMAC-усічений) дозволяє розрізняти/логувати токени, не
  розкриваючи їх; ``mask`` дає безпечний прев'ю-суфікс для UI.

Ротація ключа: задайте ``FINANCE_TOKEN_KEY`` (рекомендовано) та перешифруйте
секрети одноразовою командою. До ротації використовується похідний від
SECRET_KEY ключ — зміна SECRET_KEY зробить наявні токени нечитними (їх
доведеться ввести повторно), тому в проді бажано фіксувати FINANCE_TOKEN_KEY.
"""
from __future__ import annotations

import base64
import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings

# Контекстні мітки HKDF — розділяють призначення похідних ключів.
_ENC_INFO = b'twocomms.finance.integration-token.v1'
_FP_INFO = b'twocomms.finance.integration-fingerprint.v1'


class TokenCryptoError(Exception):
    """Помилка шифрування/розшифрування секрету інтеграції."""


def _root_secret() -> bytes:
    """Кореневий секрет: FINANCE_TOKEN_KEY (пріоритет) або SECRET_KEY."""
    raw = getattr(settings, 'FINANCE_TOKEN_KEY', '') or settings.SECRET_KEY
    if not raw:
        raise TokenCryptoError('Не налаштовано ключ шифрування (SECRET_KEY/FINANCE_TOKEN_KEY)')
    return raw.encode('utf-8') if isinstance(raw, str) else bytes(raw)


def _derive(info: bytes, length: int = 32) -> bytes:
    """HKDF-SHA256 похідний ключ від кореневого секрету під заданий контекст."""
    hkdf = HKDF(algorithm=hashes.SHA256(), length=length,
                salt=b'twocomms.finance.salt.v1', info=info)
    return hkdf.derive(_root_secret())


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(_derive(_ENC_INFO, 32))
    return Fernet(key)


def encrypt(plaintext: str) -> str:
    """Шифрує рядок-секрет → urlsafe-base64 шифротекст (Fernet)."""
    if plaintext is None:
        raise TokenCryptoError('Порожній секрет')
    token = _fernet().encrypt(plaintext.encode('utf-8'))
    return token.decode('ascii')


def decrypt(ciphertext: str) -> str:
    """Розшифровує шифротекст Fernet → вихідний рядок."""
    if not ciphertext:
        raise TokenCryptoError('Порожній шифротекст')
    try:
        raw = _fernet().decrypt(ciphertext.encode('ascii'))
    except (InvalidToken, ValueError, TypeError) as exc:
        raise TokenCryptoError('Не вдалося розшифрувати секрет (можливо, змінився ключ)') from exc
    return raw.decode('utf-8')


def fingerprint(plaintext: str) -> str:
    """Стабільний відбиток секрету (HMAC-SHA256, усічений) для логів/дедуплікації.

    Не дозволяє відновити секрет, але дає змогу впізнати «той самий токен».
    """
    key = _derive(_FP_INFO, 32)
    digest = hmac.new(key, (plaintext or '').encode('utf-8'), hashlib.sha256).hexdigest()
    return digest[:16]


def mask(plaintext: str) -> str:
    """Безпечний прев'ю-суфікс токена для UI (напр. «••••… aB3x»)."""
    s = (plaintext or '').strip()
    if len(s) <= 4:
        return '••••'
    return f'••••… {s[-4:]}'
