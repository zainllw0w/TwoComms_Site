"""Fail-closed Instagram CRM verification against the explicitly named production DB."""

from __future__ import annotations

import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from management.ig_bot_models import IgClient, IgPaymentConfirmationReview
from management.models import IgBotNotification
from management.services import instagram_bot as bot
from management.services.ig_maintenance import maintenance_status


def _normalized_database_name(value) -> str:
    return str(value or "").strip()


def _assert_production_database(expected_database: str) -> dict:
    expected = _normalized_database_name(expected_database)
    actual = _normalized_database_name(connection.settings_dict.get("NAME"))
    vendor = str(connection.vendor or "")
    if not expected:
        raise CommandError("--expected-database is required")
    if expected.lower().startswith("test_") or actual.lower().startswith("test_"):
        raise CommandError("test database is forbidden for production verification")
    if vendor != "mysql":
        raise CommandError(f"production verification requires MySQL/MariaDB, got {vendor!r}")
    if actual != expected:
        raise CommandError(f"database identity mismatch: expected {expected!r}, got {actual!r}")
    with connection.cursor() as cursor:
        cursor.execute("SELECT DATABASE()")
        selected = _normalized_database_name(cursor.fetchone()[0])
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.schemata "
            "WHERE schema_name LIKE 'test\\_%' ESCAPE '\\\\'"
        )
        test_database_count = int(cursor.fetchone()[0])
    if selected != expected:
        raise CommandError(
            f"server-selected database mismatch: expected {expected!r}, got {selected!r}"
        )
    if test_database_count:
        raise CommandError(f"test database schemas detected: {test_database_count}")
    return {
        "vendor": vendor,
        "database": actual,
        "selected_database": selected,
        "test_database_count": test_database_count,
    }


def _run_rollback_fixtures() -> dict:
    maintenance = maintenance_status()
    if not maintenance.get("active"):
        raise CommandError("--rollback-fixtures requires an active maintenance lease")
    prefix = f"prod_contract_{uuid.uuid4().hex}_"
    fixture_ids = [-int(uuid.uuid4().int % 1_000_000_000) - offset for offset in (1, 2, 3)]
    if IgBotNotification.objects.filter(pk__in=fixture_ids).exists():
        raise CommandError("negative fixture ID collision")
    auto_increment_before = _notification_auto_increment()
    failure_rollback = _prove_mid_fixture_failure_rollback(
        prefix=prefix + "failure_",
        fixture_id=-int(uuid.uuid4().int % 1_000_000_000) - 10,
        expected_auto_increment=auto_increment_before,
    )
    outer = transaction.atomic()
    outer.__enter__()
    try:
        payment_review_contract = _run_payment_review_contract(prefix)
        sent = IgBotNotification.objects.create(
            id=fixture_ids[0],
            dedupe_key=prefix + "sent",
            payload={"text": "mocked production contract", "chat_id": "123"},
        )
        unknown = IgBotNotification.objects.create(
            id=fixture_ids[1],
            dedupe_key=prefix + "unknown",
            payload={"text": "mocked production timeout", "chat_id": "123"},
        )
        dead = IgBotNotification.objects.create(
            id=fixture_ids[2],
            dedupe_key=prefix + "dead",
            payload={"text": "mocked production dead letter", "chat_id": "123"},
            status=IgBotNotification.Status.FAILED,
            attempts=4,
            next_attempt_at=timezone.now() - timedelta(seconds=1),
        )
        environment = {
            "MANAGEMENT_TG_BOT_TOKEN": "no-network-contract-token",
            "MANAGEMENT_TG_ADMIN_CHAT_ID": "123",
        }
        with (
            patch.dict("os.environ", environment, clear=False),
            patch(
                "management.services.ig_maintenance.notification_send_boundary",
                _always_allow_mocked_send,
            ),
        ):
            with patch(
                "management.services.instagram_bot._http",
                return_value=(200, json.dumps({"ok": True, "result": {"message_id": 9100}})),
            ) as http:
                if not bot._deliver_manager_notification(sent.dedupe_key):
                    raise CommandError("mocked sent fixture did not reach sent")
                http.assert_called_once()
            with patch(
                "management.services.instagram_bot._http",
                return_value=(-1, "mocked timeout"),
            ) as http:
                if bot._deliver_manager_notification(unknown.dedupe_key):
                    raise CommandError("mocked timeout fixture unexpectedly sent")
                http.assert_called_once()
            with patch(
                "management.services.instagram_bot._http",
                return_value=(503, json.dumps({"ok": False, "description": "mocked"})),
            ) as http:
                bot._deliver_manager_notification(dead.dedupe_key)
                http.assert_called_once()
        sent.refresh_from_db()
        unknown.refresh_from_db()
        dead.refresh_from_db()
        result = {
            "sent": {"status": sent.status, "attempts": sent.attempts},
            "unknown": {"status": unknown.status, "attempts": unknown.attempts},
            "dead": {"status": dead.status, "attempts": dead.attempts},
            "transport": "mocked_no_network",
            "mid_fixture_failure_rollback": failure_rollback,
            "payment_review": payment_review_contract,
        }
        if result != {
            "sent": {"status": IgBotNotification.Status.SENT, "attempts": 1},
            "unknown": {"status": IgBotNotification.Status.UNKNOWN, "attempts": 1},
            "dead": {"status": IgBotNotification.Status.DEAD_LETTER, "attempts": 5},
            "transport": "mocked_no_network",
            "mid_fixture_failure_rollback": "proven",
            "payment_review": {
                "false_media_review": "suppressed",
                "callback_race": "proven",
                "provider_truth": "untouched",
            },
        }:
            raise CommandError(f"rollback fixture contract failed: {result!r}")
        return result
    finally:
        transaction.set_rollback(True)
        outer.__exit__(None, None, None)
        if IgBotNotification.objects.filter(dedupe_key__startswith=prefix).exists():
            raise CommandError("rollback fixture leaked rows")
        auto_increment_after = _notification_auto_increment()
        if auto_increment_after != auto_increment_before:
            raise CommandError(
                "rollback fixture changed AUTO_INCREMENT: "
                f"before={auto_increment_before!r}, after={auto_increment_after!r}"
            )


def _notification_auto_increment():
    table_name = IgBotNotification._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT AUTO_INCREMENT FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = %s",
            [table_name],
        )
        row = cursor.fetchone()
    if not row:
        raise CommandError(f"notification table not found: {table_name}")
    return row[0]


def _run_payment_review_contract(prefix: str) -> dict:
    """Exercise payment-review boundaries inside the surrounding rollback."""
    from django.test import RequestFactory
    from management.services.ig_payment_review import (
        create_payment_review,
        resolve_review_payment_amount,
    )
    from management.views import management_bot_webhook

    client_id = -int(uuid.uuid4().int % 1_000_000_000) - 100
    review_id = -int(uuid.uuid4().int % 1_000_000_000) - 101
    notification_id = -int(uuid.uuid4().int % 1_000_000_000) - 102
    client = IgClient.objects.create(
        id=client_id,
        igsid=prefix + "payment-client",
        username="rollback-contract",
        display_name="Rollback contract",
    )
    messages = [
        {"id": 1, "role": "user", "text": "Беру базову S"},
        {"id": 2, "role": "manager", "text": "Оплата на IBAN, надішліть чек"},
        {
            "id": 3,
            "role": "user",
            "text": "",
            "attachments": '["https://cdn.invalid/product.jpg"]',
        },
    ]
    resolved_media = [{
        "url": "https://cdn.invalid/product.jpg",
        "message_id": 3,
        "role": "product",
        "intent": "interest",
        "payment_evidence": False,
        "catalog_match_allowed": True,
    }]
    with (
        patch("management.services.ig_payment_review._resolve_payment_media_candidates", return_value=resolved_media),
        patch("management.services.ig_payment_review._persist_review_media", return_value=resolved_media),
        patch("management.services.ig_payment_review._catalog_matches_for_media", return_value=[]),
        patch("management.services.instagram_bot.notify_manager") as notify,
    ):
        false_review = create_payment_review(client, messages=messages)
    if false_review is not None or notify.called:
        raise CommandError("vision-reclassified product image created a payment review")

    review = IgPaymentConfirmationReview.objects.create(
        id=review_id,
        client=client,
        dedupe_key=prefix + "callback-review",
        evidence={
            "provider_truth": "unverified",
            "order_draft": {"quoted_total": "2100.00", "currency": "UAH"},
        },
    )
    payment_candidate = resolve_review_payment_amount(review)
    notification = IgBotNotification.objects.create(
        id=notification_id,
        dedupe_key=review.dedupe_key,
        event_type="payment_review",
        status=IgBotNotification.Status.SENT,
        telegram_message_id="88001",
        payload={
            "chat_id": "123",
            "main_delivery_message_id": "88001",
            "media": [{"delivery_status": "sent"}],
            "payment_candidate": {
                "amount": f"{payment_candidate['amount']:.2f}",
                "currency": payment_candidate["currency"],
                "scope": payment_candidate["scope"],
                "source": payment_candidate["source"],
                "evidence_message_ids": payment_candidate["evidence_message_ids"],
                "digest": payment_candidate["digest"],
            },
        },
    )
    request_factory = RequestFactory()

    def callback_request(action: str, callback_id: str):
        return request_factory.post(
            "/management/telegram/webhook/no-network-contract-token",
            data=json.dumps({
                "callback_query": {
                    "id": callback_id,
                    "data": f"igpay:{action}:{review.pk}",
                    "from": {"id": 123, "username": "rollback-contract"},
                    "message": {
                        "chat": {"id": 123, "type": "private"},
                        "message_id": 88001,
                        "text": "Rollback payment review",
                    },
                }
            }),
            content_type="application/json",
        )

    environment = {
        "MANAGEMENT_TG_BOT_TOKEN": "no-network-contract-token",
        "MANAGEMENT_TG_ADMIN_CHAT_ID": "123",
    }
    with (
        patch.dict("os.environ", environment, clear=False),
        patch("management.views._tg_answer_callback") as answer,
        patch("management.views._tg_edit_message") as edit,
    ):
        winner_response = management_bot_webhook(
            callback_request("confirm", "rollback-confirm"),
            "no-network-contract-token",
        )
        loser_response = management_bot_webhook(
            callback_request("cancel", "rollback-cancel"),
            "no-network-contract-token",
        )
    if winner_response.status_code != 200 or loser_response.status_code != 200:
        raise CommandError("payment-review webhook callback failed")
    if edit.call_count != 1 or answer.call_count != 2:
        raise CommandError("payment-review callback did not preserve one winning edit")
    review.refresh_from_db()
    if review.status != IgPaymentConfirmationReview.Status.CONFIRMED:
        raise CommandError("payment-review callback winner was not persisted")
    if review.evidence.get("telegram_decision", {}).get("action") != "confirm":
        raise CommandError("losing payment-review callback overwrote audit")
    notification.refresh_from_db()
    if notification.telegram_message_id != "88001":
        raise CommandError("payment-review notification binding changed")
    if IgPaymentConfirmationReview.objects.filter(pk=review_id).count() != 1:
        raise CommandError("payment-review fixture identity check failed")
    return {
        "false_media_review": "suppressed",
        "callback_race": "proven",
        "provider_truth": "untouched",
    }


def _prove_mid_fixture_failure_rollback(
    *, prefix: str, fixture_id: int, expected_auto_increment
) -> str:
    try:
        with transaction.atomic():
            IgBotNotification.objects.create(
                id=fixture_id,
                dedupe_key=prefix + "row",
                payload={"text": "forced rollback", "chat_id": "123"},
            )
            raise RuntimeError("intentional rollback proof")
    except RuntimeError as exc:
        if str(exc) != "intentional rollback proof":
            raise
    if IgBotNotification.objects.filter(dedupe_key__startswith=prefix).exists():
        raise CommandError("mid-fixture exception leaked rows")
    if _notification_auto_increment() != expected_auto_increment:
        raise CommandError("mid-fixture exception changed AUTO_INCREMENT")
    return "proven"


class _always_allow_mocked_send:
    def __enter__(self):
        return True

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class Command(BaseCommand):
    help = "Перевірити IG CRM тільки проти явно названої production MariaDB."

    def add_arguments(self, parser):
        parser.add_argument("--expected-database", required=True)
        parser.add_argument("--rollback-fixtures", action="store_true")

    def handle(self, *args, **options):
        database = _assert_production_database(options["expected_database"])
        result = {
            "ok": True,
            "read_only": not options["rollback_fixtures"],
            "database_contract": database,
            "rollback_fixtures": None,
        }
        if options["rollback_fixtures"]:
            result["rollback_fixtures"] = _run_rollback_fixtures()
        self.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
