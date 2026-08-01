"""Подтверждённое удаление данных DIRECT_BOT (F-SEC-002).

Разделение ответственности:

* публичная форма `/data-deletion/submit/` только **регистрирует заявку**
  в статусе `PENDING_VERIFICATION` и ничего не удаляет — владение
  Instagram-аккаунтом там не подтверждено, а username публичен;
* signed_request от Meta (`/data-deletion/callback/`) удаляет сразу:
  владение там доказано HMAC-подписью приложения;
* заявку из публичной формы исполняет менеджер после проверки владения,
  через `fulfill_deletion_request` (команда `fulfill_ig_data_deletion`).

Запись `BotDataDeletionRequest` — неудаляемый audit факта удаления:
она не входит ни в один каскад удаления клиентских данных.
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone


class DeletionRequestNotActionable(ValueError):
    """Заявка не в том состоянии, чтобы её можно было исполнить."""


def fulfill_deletion_request(request_row, *, actor_label: str) -> dict:
    """Исполнить заявку после подтверждения владения человеком.

    Идемпотентность: повторный вызов на уже исполненной заявке поднимает
    `DeletionRequestNotActionable` и ничего не меняет. Это осознанно:
    молчаливый no-op скрыл бы двойное нажатие, а данные уже удалены
    и «переудалить» их нельзя.
    """
    from management.bot_views import _delete_direct_bot_records
    from management.models import BotDataDeletionRequest

    actor = (actor_label or "").strip()
    if not actor:
        raise DeletionRequestNotActionable("actor_label is required for the audit trail")

    with transaction.atomic():
        locked = (
            BotDataDeletionRequest.objects.select_for_update()
            .filter(pk=request_row.pk)
            .first()
        )
        if locked is None:
            raise DeletionRequestNotActionable("deletion request no longer exists")
        if locked.status != BotDataDeletionRequest.Status.PENDING_VERIFICATION:
            raise DeletionRequestNotActionable(
                f"request {locked.confirmation_code} is {locked.status}, "
                "only pending_verification can be fulfilled"
            )

        deletion = _delete_direct_bot_records(
            locked.normalized_identifier or locked.identifier
        )
        locked.status = deletion["status"]
        locked.deleted_clients_count = deletion["clients"]
        locked.deleted_messages_count = deletion["messages"]
        locked.deleted_raw_events_count = deletion["raw_events"]
        locked.deleted_logs_count = deletion["logs"]
        locked.detail = f"{deletion['detail']} Verified and fulfilled by {actor}."[:4000]
        locked.completed_at = timezone.now()
        locked.save(
            update_fields=[
                "status",
                "deleted_clients_count",
                "deleted_messages_count",
                "deleted_raw_events_count",
                "deleted_logs_count",
                "detail",
                "completed_at",
            ]
        )

    request_row.refresh_from_db()
    return deletion


def register_public_request(identifier: str, normalized_identifier: str):
    """Зарегистрировать заявку с публичной формы. Ничего не удаляет."""
    import secrets

    from management.models import BotDataDeletionRequest

    return BotDataDeletionRequest.objects.create(
        confirmation_code=secrets.token_hex(8).upper(),
        source=BotDataDeletionRequest.Source.MANUAL_FORM,
        identifier=(identifier or "")[:255],
        normalized_identifier=(normalized_identifier or "")[:255],
        status=BotDataDeletionRequest.Status.PENDING_VERIFICATION,
        detail=(
            "Request received. Ownership verification is required before any "
            "DIRECT_BOT record is deleted."
        ),
    )
