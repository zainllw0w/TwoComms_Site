"""
Шифрування PII менеджера (Fernet) + маски для UI.

Ключ — settings.FIELD_ENCRYPTION_KEY (env застосунку, не в репозиторії).
Якщо ключа немає — функції шифрування кидають PIIKeyMissing, а читання
повертає порожнє значення (не падаємо на рендері).

Док: twocomms/Management Implementations/03 (3.6) + 02 (ManagerPersonalData)
"""
from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger("management.pii")


class PIIKeyMissing(Exception):
    pass


def _fernet():
    key = getattr(settings, "FIELD_ENCRYPTION_KEY", "") or ""
    if not key:
        raise PIIKeyMissing("FIELD_ENCRYPTION_KEY не налаштований")
    from cryptography.fernet import Fernet

    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def encrypt(value: str) -> bytes | None:
    """Шифрує рядок у bytes. Порожнє значення → None."""
    if value is None or value == "":
        return None
    return _fernet().encrypt(str(value).encode("utf-8"))


def decrypt(token: bytes | None) -> str:
    """Розшифровує bytes у рядок. None/помилка → ''."""
    if not token:
        return ""
    try:
        if isinstance(token, memoryview):
            token = token.tobytes()
        if isinstance(token, str):
            token = token.encode()
        return _fernet().decrypt(token).decode("utf-8")
    except PIIKeyMissing:
        return ""
    except Exception as exc:
        logger.warning("PII decrypt failed: %s", exc)
        return ""


def mask_tail(value: str, *, visible: int = 4) -> str:
    """Маска ****1234 (показуємо останні visible символів)."""
    value = (value or "").strip()
    if not value:
        return "—"
    if len(value) <= visible:
        return "*" * len(value)
    return "*" * 4 + value[-visible:]


def tail(value: str, *, visible: int = 4) -> str:
    value = (value or "").strip()
    return value[-visible:] if len(value) >= visible else value


def set_personal_data(owner, *, full_name=None, birth_date=None, tax_id=None,
                      passport=None, address=None, phone=None, source="manual",
                      consent_version="", actor=None):
    """Створює/оновлює зашифровані PII і пише AdminAuditLog (без значень)."""
    from django.utils import timezone
    from management.models import ManagerPersonalData, AdminAuditLog

    pii, _ = ManagerPersonalData.objects.get_or_create(owner=owner)
    changed = []
    mapping = {
        "full_name_enc": full_name,
        "birth_date_enc": birth_date,
        "tax_id_enc": tax_id,
        "passport_enc": passport,
        "address_enc": address,
        "phone_enc": phone,
    }
    for field, raw in mapping.items():
        if raw is None:
            continue
        setattr(pii, field, encrypt(raw))
        changed.append(field)
    if tax_id is not None:
        pii.tax_id_tail = tail(tax_id)
    if passport is not None:
        pii.passport_tail = tail(passport)
    if source:
        pii.source = source
    if consent_version:
        pii.consent_version = consent_version
        pii.consent_at = timezone.now()
    pii.save()

    try:
        AdminAuditLog.objects.create(
            actor=actor, actor_role="staff", action="pii_update",
            entity_type="ManagerPersonalData", entity_id=str(owner.id),
            after={"fields": changed, "source": source},  # без значень PII
        )
    except Exception:
        pass
    return pii


def reveal_personal_data(owner, *, actor, reason=""):
    """Повертає розшифровані PII + пише AdminAuditLog про факт перегляду."""
    from management.models import ManagerPersonalData, AdminAuditLog

    pii = ManagerPersonalData.objects.filter(owner=owner).first()
    if not pii:
        return {}
    data = {
        "full_name": decrypt(pii.full_name_enc),
        "birth_date": decrypt(pii.birth_date_enc),
        "tax_id": decrypt(pii.tax_id_enc),
        "passport": decrypt(pii.passport_enc),
        "address": decrypt(pii.address_enc),
        "phone": decrypt(pii.phone_enc),
    }
    try:
        AdminAuditLog.objects.create(
            actor=actor, actor_role="staff", action="pii_reveal",
            entity_type="ManagerPersonalData", entity_id=str(owner.id), reason=reason,
        )
    except Exception:
        pass
    return data
