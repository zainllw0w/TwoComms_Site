"""B01.7 editable programme seeding and durable prize-review cases."""
import json
import inspect
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from management.models import (
    BotInstruction,
    IgBotNotification,
    IgClient,
    IgDeal,
    IgFollowUpTask,
    IgPaymentProjection,
    InstagramBotMessage,
)
from management.ig_bot_models import IgUgcReward
from management.services.ig_prize_cases import upsert_prize_review_case
from management.services.ig_prize_programme import (
    PROGRAMME_ID,
    RESERVED_INTENT_TAG,
    PrizeProgramme,
    active_shooting_prize_programme,
)


class PrizeCaseTests(TestCase):
    def setUp(self):
        self.client = IgClient.objects.create(igsid="prize-case-client")
        self.programme = PrizeProgramme(
            programme_id=PROGRAMME_ID,
            version="programme-version-1",
            instruction="Visible shooting target and programme mark only.",
            cue_codes=("programme_mark", "shooting_target"),
            confirmed_visual_sample=False,
        )

    def source(self, suffix: str, *, digest_char: str = "a", valid=True):
        source = InstagramBotMessage.objects.create(
            client=self.client,
            sender_id=self.client.igsid,
            role=InstagramBotMessage.Role.USER,
            text="",
            mid=f"prize-{suffix}",
            source="webhook",
            media_capture_eligible=True,
            private_media_state=InstagramBotMessage.PrivateMediaState.ACTIVE,
        )
        source_part_id = "mp1_" + digest_char * 32
        content_hash = digest_char * 64
        request_id = f"request-{suffix}"
        provider_model = "gemini-actual"
        source.attachment_media = [{
            "url": f"https://lookaside.example/{suffix}.jpg",
            "source_part_id": source_part_id,
            "original_index": 0,
            "content_hash": content_hash,
            "status": "owned",
            "provenance": "live_webhook",
            "private_storage": True,
            "storage_name": f"private/{suffix}.jpg",
            "mime": "image/jpeg",
            "inspection": {
                "state": "inspected",
                "source_part_id": source_part_id,
                "content_hash": content_hash,
                "request_id": request_id,
                "provider_model": provider_model,
            },
        }]
        source.turn_intelligence_artifact = {
            "schema_version": 1,
            "source_message_id": source.pk,
            "image_observations": [{
                "source_part_id": source_part_id,
                "original_index": 0,
                "content_hash": content_hash if valid else "f" * 64,
                "outcome": "uncertain",
                "evidence_code": "visual_content",
                "type_code": "certificate",
                "prize_certificate": {
                    "programme_id": PROGRAMME_ID,
                    "programme_version": self.programme.version,
                    "status": "recognized",
                    "cue_codes": ["shooting_target"],
                    "reason_code": "visible_programme_cues",
                    "manager_required": True,
                },
            }],
            "media_request": {
                "request_id": request_id,
                "provider_model": provider_model,
                "inline_count_known": True,
                "actual_inline_count": 1,
            },
        }
        source.save(update_fields=["attachment_media", "turn_intelligence_artifact"])
        return source

    def test_repeated_parts_group_into_one_open_business_case_and_notification(self):
        first = self.source("first", digest_char="a")
        second = self.source("second", digest_char="b")

        first_result = upsert_prize_review_case(
            first,
            programme=self.programme,
            now=timezone.now(),
        )
        notification = IgBotNotification.objects.get(pk=first_result.notification_id)
        first_preview_url = notification.payload["media"][0]["preview_url"]
        notification.payload["main_delivery_message_id"] = "telegram-main-41"
        notification.payload["media"][0]["delivery_status"] = (
            "not_forwarded_private"
        )
        notification.payload["media"][0]["delivery_message_id"] = (
            "telegram-media-42"
        )
        notification.status = IgBotNotification.Status.SENT
        notification.telegram_message_id = "telegram-main-41"
        notification.attempts = 1
        notification.failure_kind = ""
        notification.last_error = ""
        notification.last_attempt_at = timezone.now()
        notification.sent_at = timezone.now()
        notification.save(update_fields=[
            "payload", "status", "telegram_message_id", "attempts",
            "failure_kind", "last_error", "last_attempt_at", "sent_at",
            "updated_at",
        ])
        second_result = upsert_prize_review_case(
            second,
            programme=self.programme,
            now=timezone.now(),
        )

        self.assertEqual(first_result.task_id, second_result.task_id)
        self.assertTrue(first_result.created)
        self.assertFalse(second_result.created)
        self.assertEqual(IgFollowUpTask.objects.count(), 1)
        self.assertEqual(IgBotNotification.objects.count(), 1)
        task = IgFollowUpTask.objects.get(pk=first_result.task_id)
        document = task.manager_context
        self.assertEqual(len(document["evidence"]), 2)
        self.assertEqual(document["candidate_status"], "uncertain")
        self.assertEqual(document["authority"]["entitlement"], "unconfirmed")
        self.assertEqual(task.kind, IgFollowUpTask.Kind.MANAGER_TASK)
        self.assertEqual(
            task.manager_approval_status,
            IgFollowUpTask.ManagerApprovalStatus.PENDING,
        )
        self.assertEqual(task.status, IgFollowUpTask.Status.SKIPPED)
        self.assertTrue(task.message_text.startswith("Потребує перевірки:"))
        self.assertNotIn("{", task.message_text)
        self.assertNotIn("content_hash", task.message_text)
        self.assertNotIn("request-", task.message_text)
        notification.refresh_from_db()
        self.assertEqual(notification.status, IgBotNotification.Status.SENT)
        self.assertEqual(notification.telegram_message_id, "telegram-main-41")
        self.assertEqual(notification.attempts, 1)
        self.assertEqual(
            notification.payload["main_delivery_message_id"],
            "telegram-main-41",
        )
        first_media = next(
            item
            for item in notification.payload["media"]
            if item.get("preview_url") == first_preview_url
        )
        self.assertEqual(first_media["delivery_status"], "not_forwarded_private")
        self.assertEqual(first_media["delivery_message_id"], "telegram-media-42")
        self.assertEqual(notification.payload["evidence_count"], 2)
        self.assertIn("потрібна перевірка", notification.payload["text"])
        self.assertIn(
            f"/bot/?client={self.client.pk}",
            notification.payload["client_url"],
        )
        self.assertNotIn(self.client.igsid, notification.payload["text"])
        self.assertNotIn("lookaside.example", json.dumps(notification.payload))
        self.assertNotIn("storage_name", json.dumps(notification.payload))
        self.assertFalse(self.client.bot_paused)
        self.assertFalse(self.client.manager_takeover)
        self.assertEqual(IgDeal.objects.count(), 0)
        self.assertEqual(IgPaymentProjection.objects.count(), 0)
        self.assertEqual(IgUgcReward.objects.count(), 0)
        from management.services.bot_followups import process_due_followups

        with patch("management.services.instagram_bot.send_text") as send_text:
            self.assertEqual(
                process_due_followups(now=timezone.now(), limit=10),
                0,
            )
        send_text.assert_not_called()
        from management import bot_views

        projection_source = inspect.getsource(bot_views.bot_client_detail_api)
        self.assertIn('"status_label"', projection_source)
        self.assertIn("Потребує перевірки", projection_source)
        template = (
            Path(__file__).parent / "templates" / "management" / "bot.html"
        ).read_text(encoding="utf-8")
        self.assertIn("item.status_label||", template)

    def test_later_catalog_and_custom_preferences_stay_on_same_case(self):
        candidate = self.source("preference-candidate", digest_char="c")
        created = upsert_prize_review_case(candidate, programme=self.programme)
        catalog = InstagramBotMessage.objects.create(
            client=self.client,
            sender_id=self.client.igsid,
            role=InstagramBotMessage.Role.USER,
            text="Хочу річ з каталогу",
            mid="prize-preference-catalog",
        )
        custom = InstagramBotMessage.objects.create(
            client=self.client,
            sender_id=self.client.igsid,
            role=InstagramBotMessage.Role.USER,
            text="Краще свій принт",
            mid="prize-preference-custom",
        )

        catalog_result = upsert_prize_review_case(
            catalog,
            programme=self.programme,
            preference={"kind": "catalog", "product_id": 77},
        )
        custom_result = upsert_prize_review_case(
            custom,
            programme=self.programme,
            preference={"kind": "custom"},
        )

        self.assertEqual(
            {created.task_id, catalog_result.task_id, custom_result.task_id},
            {created.task_id},
        )
        task = IgFollowUpTask.objects.get(pk=created.task_id)
        document = task.manager_context
        self.assertEqual(
            document["preferences"],
            [
                {
                    "kind": "catalog",
                    "product_id": 77,
                    "source_message_id": catalog.pk,
                },
                {
                    "kind": "custom",
                    "source_message_id": custom.pk,
                },
            ],
        )
        self.assertIn("вибір: каталог, власний принт", task.message_text)
        self.assertFalse(self.client.bot_paused)

    def test_unknown_notification_stays_unknown_when_case_evidence_grows(self):
        first = self.source("unknown-first", digest_char="8")
        result = upsert_prize_review_case(first, programme=self.programme)
        notification = IgBotNotification.objects.get(pk=result.notification_id)
        notification.payload["main_delivery_message_id"] = "possible-main-51"
        notification.status = IgBotNotification.Status.UNKNOWN
        notification.attempts = 1
        notification.telegram_message_id = "possible-main-51"
        notification.failure_kind = "ambiguous_provider_response"
        notification.last_error = "success response missing receipt"
        notification.save(update_fields=[
            "payload", "status", "attempts", "telegram_message_id",
            "failure_kind", "last_error", "updated_at",
        ])

        second = self.source("unknown-second", digest_char="9")
        upsert_prize_review_case(second, programme=self.programme)

        notification.refresh_from_db()
        self.assertEqual(notification.status, IgBotNotification.Status.UNKNOWN)
        self.assertEqual(notification.attempts, 1)
        self.assertEqual(notification.telegram_message_id, "possible-main-51")
        self.assertEqual(
            notification.failure_kind,
            "ambiguous_provider_response",
        )
        self.assertEqual(
            notification.payload["main_delivery_message_id"],
            "possible-main-51",
        )
        self.assertEqual(notification.payload["evidence_count"], 2)

    def test_caption_keyword_wrong_hash_version_or_missing_cues_creates_no_case(self):
        caption_only = InstagramBotMessage.objects.create(
            client=self.client,
            sender_id=self.client.igsid,
            role=InstagramBotMessage.Role.USER,
            text="У мене призовий сертифікат",
            mid="prize-caption-only",
        )
        wrong_hash = self.source("wrong-hash", digest_char="d", valid=False)
        wrong_version = self.source("wrong-version", digest_char="e")
        wrong_version.turn_intelligence_artifact["image_observations"][0][
            "prize_certificate"
        ]["programme_version"] = "old-version"
        wrong_version.save(update_fields=["turn_intelligence_artifact"])
        missing_cues = self.source("missing-cues", digest_char="f")
        missing_cues.turn_intelligence_artifact["image_observations"][0][
            "prize_certificate"
        ]["cue_codes"] = []
        missing_cues.save(update_fields=["turn_intelligence_artifact"])
        missing_programme = self.source("missing-programme", digest_char="1")

        self.assertEqual(
            upsert_prize_review_case(
                missing_programme,
                programme=None,
            ).reason,
            "programme_missing",
        )

        for source in (caption_only, wrong_hash, wrong_version, missing_cues):
            with self.subTest(source=source.mid):
                result = upsert_prize_review_case(
                    source,
                    programme=self.programme,
                )
                self.assertEqual(result.reason, "candidate_not_validated")

        self.assertEqual(IgFollowUpTask.objects.count(), 0)
        self.assertEqual(IgBotNotification.objects.count(), 0)

    def test_unsafe_client_deleted_media_and_owner_mismatch_are_rejected(self):
        client_cases = (
            ("hidden_at", timezone.now(), "client_hidden"),
            ("is_blocked", True, "client_blocked"),
            (
                "privacy_erasure_started_at",
                timezone.now(),
                "client_erasure_active",
            ),
        )
        for index, (field, value, expected) in enumerate(client_cases):
            with self.subTest(field=field):
                source = self.source(f"unsafe-client-{index}", digest_char=str(index + 2))
                setattr(self.client, field, value)
                self.client.save(update_fields=[field, "updated_at"])
                result = upsert_prize_review_case(
                    source,
                    programme=self.programme,
                )
                self.assertEqual(result.reason, expected)
                setattr(self.client, field, None if field != "is_blocked" else False)
                self.client.save(update_fields=[field, "updated_at"])

        deleted = self.source("deleted-private", digest_char="5")
        deleted.private_media_state = InstagramBotMessage.PrivateMediaState.DELETE_PENDING
        deleted.save(update_fields=["private_media_state"])
        self.assertEqual(
            upsert_prize_review_case(
                deleted,
                programme=self.programme,
            ).reason,
            "source_not_reviewable",
        )
        excluded = self.source("excluded-source", digest_char="7")
        excluded.media_capture_eligible = False
        excluded.save(update_fields=["media_capture_eligible"])
        self.assertEqual(
            upsert_prize_review_case(
                excluded,
                programme=self.programme,
            ).reason,
            "source_not_reviewable",
        )
        mismatched = self.source("owner-mismatch", digest_char="6")
        mismatched.sender_id = "different-owner"
        mismatched.save(update_fields=["sender_id"])
        self.assertEqual(
            upsert_prize_review_case(
                mismatched,
                programme=self.programme,
            ).reason,
            "source_owner_mismatch",
        )
        self.assertEqual(IgFollowUpTask.objects.count(), 0)
        self.assertEqual(IgBotNotification.objects.count(), 0)

    def test_permission_epoch_pause_takeover_and_optout_block_stale_case(self):
        source = self.source("permission-race", digest_char="0")
        expected_epoch = int(self.client.reply_permission_epoch or 0)
        self.client.reply_permission_epoch = expected_epoch + 1
        self.client.save(update_fields=["reply_permission_epoch", "updated_at"])
        self.assertEqual(
            upsert_prize_review_case(
                source,
                programme=self.programme,
                expected_permission_epoch=expected_epoch,
            ).reason,
            "permission_epoch_changed",
        )

        self.client.bot_paused = True
        self.client.save(update_fields=["bot_paused", "updated_at"])
        self.assertEqual(
            upsert_prize_review_case(source, programme=self.programme).reason,
            "client_paused",
        )
        self.client.bot_paused = False
        self.client.manager_takeover = True
        self.client.save(update_fields=[
            "bot_paused", "manager_takeover", "updated_at",
        ])
        self.assertEqual(
            upsert_prize_review_case(source, programme=self.programme).reason,
            "manager_takeover",
        )
        self.client.manager_takeover = False
        self.client.opted_out_at = timezone.now()
        self.client.opted_in_at = None
        self.client.save(update_fields=[
            "manager_takeover", "opted_out_at", "opted_in_at", "updated_at",
        ])
        self.assertEqual(
            upsert_prize_review_case(source, programme=self.programme).reason,
            "client_opted_out",
        )
        self.assertEqual(IgFollowUpTask.objects.count(), 0)
        self.assertEqual(IgBotNotification.objects.count(), 0)


class PrizeProgrammeSeedCommandTests(TestCase):
    def test_dry_run_apply_and_reapply_preserve_edit_and_disabled_state(self):
        output = StringIO()
        call_command("seed_ig_prize_programme", stdout=output)
        self.assertIn("dry-run", output.getvalue())
        self.assertEqual(BotInstruction.objects.count(), 0)

        call_command("seed_ig_prize_programme", apply=True, stdout=StringIO())
        instruction = BotInstruction.objects.get()
        self.assertEqual(instruction.intent_tags, RESERVED_INTENT_TAG)
        seeded_version = active_shooting_prize_programme().version
        instruction.body = "Власна відредагована інструкція"
        instruction.save(update_fields=["body", "updated_at"])
        self.assertNotEqual(
            active_shooting_prize_programme().version,
            seeded_version,
        )
        instruction.is_active = False
        instruction.save(update_fields=["is_active", "updated_at"])

        call_command("seed_ig_prize_programme", apply=True, stdout=StringIO())
        instruction.refresh_from_db()
        self.assertEqual(instruction.body, "Власна відредагована інструкція")
        self.assertFalse(instruction.is_active)
        self.assertIsNone(active_shooting_prize_programme())
        self.assertEqual(BotInstruction.objects.count(), 1)

    def test_ambiguous_duplicate_tags_are_reported_and_never_autopicked(self):
        for index in range(2):
            BotInstruction.objects.create(
                title=f"Programme {index}",
                body=f"Body {index}",
                intent_tags=RESERVED_INTENT_TAG,
                is_active=bool(index),
            )
        output = StringIO()

        call_command("seed_ig_prize_programme", stdout=output)
        self.assertIn("ambiguous", output.getvalue())
        with self.assertRaises(CommandError):
            call_command("seed_ig_prize_programme", apply=True, stdout=StringIO())
        self.assertEqual(BotInstruction.objects.count(), 2)
