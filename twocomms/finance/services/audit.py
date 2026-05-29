"""Запис у журнал аудиту (історія дій)."""
from __future__ import annotations

from ..models import AuditLog, get_default_company


def log_action(user, action: str, entity_type: str, entity_id='', summary='',
               before=None, after=None, source='manual', company=None):
    """Створює запис AuditLog. Безпечно ковтає помилки (лог не має ламати дію)."""
    try:
        AuditLog.objects.create(
            company=company or get_default_company(),
            user=user if getattr(user, 'is_authenticated', False) else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id or ''),
            summary=summary or '',
            before=before or {},
            after=after or {},
            source=source,
        )
    except Exception:  # noqa: BLE001 — аудит не повинен переривати основну операцію
        pass
