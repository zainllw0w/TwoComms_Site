import hashlib
from datetime import timedelta
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image

from management.models import IgClient, InstagramBotMessage


class UGCSettingsContractTests(TestCase):
    def test_auto_award_mode_is_explicit_and_bounded(self):
        """Production can opt in only through the documented setting values."""
        self.assertIn(
            settings.IG_UGC_AUTO_AWARD_MODE,
            {"auto", "shadow", "disabled"},
        )


@override_settings(
    IG_UGC_AUTO_AWARD_MODE="auto",
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)
class UGCIngressAssessmentTests(TestCase):
    def _owned_image(self, storage_name, *, color=(25, 70, 120)):
        buffer = BytesIO()
        Image.new("RGB", (16, 16), color).save(buffer, format="JPEG")
        raw = buffer.getvalue()
        if default_storage.exists(storage_name):
            default_storage.delete(storage_name)
        saved_name = default_storage.save(storage_name, ContentFile(raw))
        self.addCleanup(default_storage.delete, saved_name)
        return {
            "storage_name": saved_name,
            "mime": "image/jpeg",
            "bytes": len(raw),
            "content_hash": hashlib.sha256(raw).hexdigest(),
        }

    def setUp(self):
        self.client = IgClient.get_or_create_for_sender("ugc-poster-1")
        owned = self._owned_image("ig/owned/story-1.jpg")
        self.message = InstagramBotMessage.objects.create(
            client=self.client,
            sender_id=self.client.igsid,
            role=InstagramBotMessage.Role.USER,
            text="Ми вийшли у ваших футболках @twocomms",
            source="webhook",
            mid="story-mid-1",
            media_capture_eligible=True,
            attachment_media=[
                {
                    "url": "https://lookaside.fbsbx.com/media/story.jpg",
                    "provider_object_key": "story:object-1",
                    "provider_media_id": "media-1",
                    "provider_event_id": "story-mid-1",
                    "media_type": "story_mention",
                    "target_username": "twocomms",
                    "provider_native_mention": True,
                    "provenance": "live_webhook",
                    "status": "owned",
                    **owned,
                }
            ],
        )

    def _assessment(self, **overrides):
        from management.services.ig_ugc_assessment import assess_ugc_evidence

        facts = {
            "provider_native_mention": True,
            "target_username": "twocomms",
            "owned_media": True,
            "personal_worn_apparel": True,
            "customer_created_content": True,
            "customer_content_confidence": 0.99,
            "brand_match_confidence": 0.99,
            "catalog_matches": [
                {"garment_index": 0, "product_id": 11, "confidence": 0.98},
                {"garment_index": 1, "product_id": 12, "confidence": 0.97},
            ],
            "risk_flags": [],
            "people_count": 2,
            "garment_count": 2,
            "perceptual_fingerprint": "same-fingerprint",
        }
        facts.update(overrides)
        return assess_ugc_evidence(
            message=self.message,
            facts=facts,
            now=timezone.now().replace(microsecond=0),
        )

    def test_two_people_two_shirts_auto_qualifies_but_one_owner(self):
        assessment = self._assessment()

        self.assertEqual(assessment.decision, "qualified_auto")
        self.assertEqual(assessment.reward_owner_client_id, self.client.pk)
        self.assertEqual(len(assessment.catalog_candidates), 2)
        self.assertEqual(assessment.people_count, 2)
        self.assertEqual(assessment.garment_count, 2)

    @patch("management.services.bot_vision.build_match_candidates", return_value=[])
    @patch("management.services.bot_vision.assess_ugc")
    @patch("management.services.instagram_bot.download_image")
    def test_transient_cdn_failure_is_retried_and_reassessed_without_new_message(
        self,
        download,
        assess_ugc,
        _candidates,
    ):
        from management.services.instagram_bot import _capture_message_media
        from management.services.ig_ugc_assessment import (
            ensure_pending_ugc_assessment,
            reconcile_pending_ugc_media,
        )

        url = "https://lookaside.fbsbx.com/media/transient-story.jpg"
        message = InstagramBotMessage.objects.create(
            client=self.client,
            sender_id=self.client.igsid,
            role=InstagramBotMessage.Role.USER,
            text="Ми у ваших футболках @twocomms",
            source="webhook",
            mid="transient-story-mid",
            media_capture_eligible=True,
            attachment_media=[{
                "url": url,
                "provider_object_key": "story:transient-object",
                "provider_media_id": "transient-media",
                "provider_event_id": "transient-story-mid",
                "media_type": "story_mention",
                "target_username": "twocomms",
                "provider_native_mention": True,
                "provenance": "live_webhook",
                "status": "pending",
            }],
        )
        assessment = ensure_pending_ugc_assessment(message)
        self.assertEqual(assessment.decision, "pending")
        initial_message_ids = set(
            InstagramBotMessage.objects.values_list("pk", flat=True)
        )

        download.side_effect = [
            None,
            ("image/jpeg", b"recovered-story-bytes"),
        ]
        assess_ugc.return_value = {
            "personal_worn_apparel": True,
            "customer_created_content": True,
            "customer_content_confidence": 0.99,
            "brand_match_confidence": 0.99,
            "people_count": 1,
            "garment_count": 1,
            "catalog_matches": [{
                "garment_index": 0,
                "product_id": 11,
                "confidence": 0.99,
            }],
            "risk_flags": [],
        }
        _capture_message_media(message)
        message.refresh_from_db()
        self.assertEqual(message.attachment_media[0]["status"], "unavailable")
        # The worker runs after the durable backoff window, not in a hot loop.
        message.attachment_media[0]["capture_next_attempt_at"] = (
            timezone.now() - timedelta(seconds=1)
        ).isoformat()
        message.save(update_fields=["attachment_media"])

        result = reconcile_pending_ugc_media(
            limit=1,
            now=timezone.now() + timedelta(minutes=2),
        )

        message.refresh_from_db()
        assessment.refresh_from_db()
        self.assertEqual(result["selected"], 1)
        self.assertEqual(result["owned"], 1)
        self.assertEqual(message.attachment_media[0]["status"], "owned")
        self.assertEqual(assessment.decision, "needs_manager_review")
        assess_ugc.assert_called_once()
        from management.models import IgBotNotification
        from management.ig_bot_models import IgUgcReward

        self.assertFalse(IgUgcReward.objects.filter(client=self.client).exists())
        notification = IgBotNotification.objects.get(
            event_type="ugc_reward_review"
        )
        buttons = notification.payload["reply_markup"]["inline_keyboard"][0]
        self.assertEqual(
            [button["text"] for button in buttons],
            ["5%", "10%", "Відхилити"],
        )
        self.assertEqual(result["review_queued"], 1)
        self.assertEqual(
            initial_message_ids,
            set(InstagramBotMessage.objects.values_list("pk", flat=True)),
        )

    @patch("management.services.instagram_bot.download_image")
    def test_exhausted_capture_becomes_manager_review_without_network_retry(self, download):
        from management.services.ig_ugc_assessment import (
            ensure_pending_ugc_assessment,
            reconcile_pending_ugc_media,
        )

        message = InstagramBotMessage.objects.create(
            client=self.client,
            sender_id=self.client.igsid,
            role=InstagramBotMessage.Role.USER,
            text="Відмітка @twocomms",
            source="webhook",
            mid="exhausted-story-mid",
            media_capture_eligible=True,
            attachment_media=[{
                "url": "https://lookaside.fbsbx.com/media/exhausted-story.jpg",
                "provider_object_key": "story:exhausted-object",
                "provider_media_id": "exhausted-media",
                "provider_event_id": "exhausted-story-mid",
                "media_type": "story_mention",
                "target_username": "twocomms",
                "provider_native_mention": True,
                "provenance": "live_webhook",
                "status": "unavailable",
                "capture_attempts": 2,
                "error_kind": "download_failed",
            }],
        )
        assessment = ensure_pending_ugc_assessment(message)

        result = reconcile_pending_ugc_media(limit=1, now=timezone.now())

        assessment.refresh_from_db()
        self.assertEqual(result["terminalized"], 1)
        self.assertEqual(
            assessment.decision,
            "needs_manager_review",
        )
        self.assertEqual(assessment.reason_codes, ["media_capture_exhausted"])
        download.assert_not_called()

    def test_duplicate_product_cannot_cover_two_distinct_garments(self):
        assessment = self._assessment(
            catalog_matches=[
                {"garment_index": 0, "product_id": 11, "confidence": 0.99},
                {"garment_index": 1, "product_id": 11, "confidence": 0.99},
            ],
        )

        self.assertEqual(assessment.decision, "needs_manager_review")
        self.assertIn("catalog_coverage_insufficient", assessment.reason_codes)

    def test_each_claimed_garment_requires_an_independent_mapping(self):
        assessment = self._assessment(
            catalog_matches=[
                {"garment_index": 0, "product_id": 11, "confidence": 0.99},
                {"garment_index": 0, "product_id": 12, "confidence": 0.99},
            ],
        )

        self.assertEqual(assessment.decision, "needs_manager_review")
        self.assertIn("catalog_coverage_insufficient", assessment.reason_codes)

    def test_missing_provider_provenance_never_auto_qualifies(self):
        media = dict(self.message.attachment_media[0])
        media["provider_native_mention"] = False
        self.message.attachment_media = [media]
        self.message.save(update_fields=["attachment_media"])

        assessment = self._assessment(provider_native_mention=True)

        self.assertIn(assessment.decision, {"needs_manager_review", "rejected"})
        self.assertNotEqual(assessment.decision, "qualified_auto")

    def test_model_facts_cannot_forge_provider_target_or_native_mention(self):
        media = dict(self.message.attachment_media[0])
        media["target_username"] = "another_brand"
        media["provider_native_mention"] = False
        self.message.attachment_media = [media]
        self.message.save(update_fields=["attachment_media"])

        assessment = self._assessment(
            provider_native_mention=True,
            target_username="twocomms",
        )

        self.assertNotEqual(assessment.decision, "qualified_auto")
        self.assertEqual(assessment.target_username, "another_brand")

    def test_model_facts_cannot_replace_provider_object_identity(self):
        assessment = self._assessment(provider_object_key="story:forged-object")

        self.assertEqual(assessment.provider_object_key, "story:object-1")

    def test_malformed_native_metadata_cannot_auto_qualify_or_issue_reward(self):
        from management.services.ig_ugc_rewards import (
            UgcRewardConflict,
            award_external_ugc_reward,
        )

        media = dict(self.message.attachment_media[0])
        media.update({
            "provider_event_id": "",
            "provider_media_id": "",
            "provider_object_key": "story:arbitrary-object-id",
            "provider_native_mention": True,
            "target_username": "twocomms",
        })
        self.message.attachment_media = [media]
        self.message.save(update_fields=["attachment_media"])

        assessment = self._assessment()

        self.assertNotEqual(assessment.decision, "qualified_auto")
        with self.assertRaises(UgcRewardConflict):
            award_external_ugc_reward(
                client=self.client,
                assessment=assessment,
                actor=SimpleNamespace(is_authenticated=True),
            )

    def test_non_user_message_never_auto_qualifies(self):
        self.message.role = InstagramBotMessage.Role.MANAGER
        self.message.save(update_fields=["role"])

        assessment = self._assessment()

        self.assertNotEqual(assessment.decision, "qualified_auto")

    def test_non_webhook_message_never_auto_qualifies(self):
        self.message.source = "poll"
        self.message.save(update_fields=["source"])

        assessment = self._assessment()

        self.assertNotEqual(assessment.decision, "qualified_auto")

    def test_missing_owned_bytes_never_auto_qualifies(self):
        default_storage.delete(self.message.attachment_media[0]["storage_name"])

        assessment = self._assessment()

        self.assertNotEqual(assessment.decision, "qualified_auto")

    def test_ad_or_ocr_only_content_is_rejected(self):
        assessment = self._assessment(
            personal_worn_apparel=False,
            owned_media=False,
            ocr_text="@twocomms знижка 10% купуйте зараз",
        )

        self.assertEqual(assessment.decision, "rejected")

    def test_customer_created_lifestyle_evidence_is_required_for_auto_award(self):
        unknown_origin = self._assessment(
            customer_created_content=False,
            customer_content_confidence=0.99,
        )

        self.assertEqual(unknown_origin.decision, "needs_manager_review")
        self.assertIn("customer_origin_unproven", unknown_origin.reason_codes)

    def test_generic_share_without_native_brand_target_is_not_a_ugc_turn(self):
        from management.services.ig_ugc_assessment import potential_ugc_message

        self.message.attachment_media = [{
            **self.message.attachment_media[0],
            "media_type": "share",
            "provider_native_mention": False,
            "target_username": "",
        }]
        self.message.save(update_fields=["attachment_media"])

        self.assertFalse(potential_ugc_message(self.message))

    def test_provider_native_share_repost_can_qualify_like_story_mention(self):
        """A typed provider post ID is sufficient provenance for a repost."""
        media = dict(self.message.attachment_media[0])
        media.update({
            "media_type": "ig_post",
            "provider_media_id": "post-media-share",
            "provider_object_key": "ig_post:post-media-share",
        })
        self.message.attachment_media = [media]
        self.message.save(update_fields=["attachment_media"])

        assessment = self._assessment()

        self.assertEqual(assessment.decision, "qualified_auto")

    def test_potential_ugc_requires_media_capture_eligibility(self):
        from management.services.ig_ugc_assessment import potential_ugc_message

        self.message.media_capture_eligible = False
        self.message.save(update_fields=["media_capture_eligible"])

        self.assertFalse(potential_ugc_message(self.message))

    def test_verified_native_mention_suppresses_commerce_before_media_capture_succeeds(self):
        """A failed download must not turn a real tag back into a sales turn."""
        from management.services.ig_ugc_assessment import (
            ensure_pending_ugc_assessment,
            potential_ugc_message,
        )

        for status in ("pending", "unavailable"):
            with self.subTest(status=status):
                media = dict(self.message.attachment_media[0])
                media.update({"status": status})
                for field in ("storage_name", "mime", "bytes", "content_hash"):
                    media.pop(field, None)
                self.message.attachment_media = [media]
                self.message.save(update_fields=["attachment_media"])

                self.assertTrue(potential_ugc_message(self.message))
                assessment = ensure_pending_ugc_assessment(self.message)
                self.assertEqual(assessment.decision, "pending")
                self.assertNotEqual(assessment.decision, "qualified_auto")

    def test_contradictory_zero_count_worn_facts_never_auto_qualify(self):
        assessment = self._assessment(
            personal_worn_apparel=True,
            people_count=0,
            garment_count=0,
        )

        self.assertNotEqual(assessment.decision, "qualified_auto")
        self.assertIn("model_fact_inconsistent", assessment.reason_codes)

    @override_settings(IG_UGC_AUTO_AWARD_MODE="shadow")
    def test_shadow_rollout_never_auto_qualifies(self):
        assessment = self._assessment()

        self.assertEqual(assessment.decision, "needs_manager_review")
        self.assertIn("auto_award_shadow", assessment.reason_codes)

    def test_consumed_lifetime_slot_rejects_repeat_poster_before_promise(self):
        from management.ig_bot_models import IgUgcRewardLifetime
        from management.services.ig_ugc_rewards import _identity_digest

        IgUgcRewardLifetime.objects.create(
            client=self.client,
            identity_digest=_identity_digest(self.client),
            consumed_at=timezone.now(),
        )

        assessment = self._assessment()

        self.assertEqual(assessment.decision, "rejected")
        self.assertIn("already_rewarded", assessment.reason_codes)

    def test_duplicate_provider_object_is_hard_reject(self):
        first = self._assessment()
        self.assertEqual(first.decision, "qualified_auto")
        self.assertTrue(getattr(first, "provider_object_digest", None))

        from management.services.ig_ugc_assessment import assess_ugc_evidence

        duplicate_message = InstagramBotMessage.objects.create(
            client=self.client,
            sender_id=self.client.igsid,
            role=InstagramBotMessage.Role.USER,
            text="Повторна подія",
            source="webhook",
            mid="story-mid-duplicate-object",
            media_capture_eligible=True,
            attachment_media=self.message.attachment_media,
        )

        duplicate = assess_ugc_evidence(
            message=duplicate_message,
            facts={
                "provider_native_mention": True,
                "target_username": "twocomms",
                "owned_media": True,
                "personal_worn_apparel": True,
                "brand_match_confidence": 0.99,
                "catalog_matches": [{"product_id": 11, "confidence": 0.98}],
                "provider_object_key": "story:object-1",
            },
        )
        self.assertEqual(duplicate.decision, "rejected")
        self.assertIn("duplicate_provider_object", duplicate.reason_codes)
        self.assertIsNone(getattr(duplicate, "provider_object_digest", None))

    def test_pending_assessment_recovers_from_concurrent_provider_digest_collision(self):
        from django.db.models.query import QuerySet

        from management.services.ig_ugc_assessment import (
            ensure_pending_ugc_assessment,
        )

        first = self._assessment()
        duplicate_message = InstagramBotMessage.objects.create(
            client=self.client,
            sender_id=self.client.igsid,
            role=InstagramBotMessage.Role.USER,
            text="Конкурентна повторна подія",
            source="webhook",
            mid="story-mid-concurrent-object",
            media_capture_eligible=True,
            attachment_media=self.message.attachment_media,
        )

        original_exists = QuerySet.exists

        def miss_provider_preflight(queryset):
            if "provider_object_digest" in queryset.query.where.children[0].lhs.target.name:
                return False
            return original_exists(queryset)

        with patch.object(QuerySet, "exists", autospec=True, side_effect=miss_provider_preflight):
            duplicate = ensure_pending_ugc_assessment(duplicate_message)

        self.assertNotEqual(duplicate.pk, first.pk)
        self.assertEqual(duplicate.decision, "rejected")
        self.assertIn("duplicate_provider_object", duplicate.reason_codes)
        self.assertIsNone(duplicate.provider_object_digest)

    def test_duplicate_webhook_message_coalesces_to_same_assessment(self):
        from management.ig_bot_models import IgUgcEvidenceAssessment

        first = self._assessment()
        replay = self._assessment()

        self.assertEqual(replay.pk, first.pk)
        self.assertEqual(
            IgUgcEvidenceAssessment.objects.filter(
                client=self.client,
                source_message_id=self.message.mid,
            ).count(),
            1,
        )

    def test_near_duplicate_from_different_provider_object_requires_review(self):
        self._assessment()
        self.message.mid = "story-mid-2"
        self.message.pk = None
        second_owned = self._owned_image("ig/owned/story-2.jpg")
        self.message.attachment_media = [
            {
                "url": "https://lookaside.fbsbx.com/media/story-2.jpg",
                "provider_object_key": "story:object-2",
                "provider_media_id": "media-2",
                "provider_event_id": "story-mid-2",
                "media_type": "story_mention",
                "target_username": "twocomms",
                "provider_native_mention": True,
                "provenance": "live_webhook",
                "status": "owned",
                **second_owned,
            }
        ]
        self.message.save(force_insert=True)
        assessment = self._assessment()
        self.assertEqual(assessment.decision, "needs_manager_review")

    def test_expired_owned_media_can_be_assessed_but_url_only_cannot(self):
        from management.services.ig_ugc_assessment import assess_ugc_evidence

        old = timezone.now() - timedelta(days=2)
        self.message.provider_created_at = old
        self.message.save(update_fields=["provider_created_at"])
        owned = self._assessment()
        self.assertEqual(owned.decision, "qualified_auto")

        url_only_message = InstagramBotMessage.objects.create(
            client=self.client,
            sender_id=self.client.igsid,
            role=InstagramBotMessage.Role.USER,
            text="URL-only згадка",
            source="webhook",
            mid="story-mid-url-only",
            media_capture_eligible=False,
            attachment_media=[
                {
                    "url": "https://lookaside.fbsbx.com/media/expired.jpg",
                    "provenance": "live_webhook",
                    "status": "unavailable",
                    "provider_object_key": "story:expired",
                }
            ],
        )
        from management.services.ig_ugc_assessment import assess_ugc_evidence

        url_only = assess_ugc_evidence(
            message=url_only_message,
            facts={
                "provider_native_mention": True,
                "target_username": "twocomms",
                "owned_media": False,
                "personal_worn_apparel": True,
                "brand_match_confidence": 0.99,
                "catalog_matches": [{"product_id": 11, "confidence": 0.98}],
            },
        )
        self.assertNotEqual(url_only.decision, "qualified_auto")

    def test_assessment_suppresses_commerce_discovery_for_turn(self):
        assessment = self._assessment()

        from management.services.ig_ugc_assessment import commerce_suppressed_for_ugc

        self.assertTrue(commerce_suppressed_for_ugc(assessment))

    def test_same_turn_acknowledgement_strips_product_price_follow_and_discount_pitch(self):
        from management.services.ig_ugc_assessment import safe_ugc_acknowledgement

        unsafe_variants = (
            "Давайте я розповім про цей продукт і підберу розмір.",
            "Це модель Бойова квіточка за 1090 грн.",
            "Будемо раді бачити вас серед підписників.",
            "Підпишіться на сторінку, а після перевірки дамо знижку.",
        )
        for generated in unsafe_variants:
            with self.subTest(generated=generated):
                reply = safe_ugc_acknowledgement(self.client, generated)
                lowered = reply.casefold()
                self.assertIn("дяку", lowered)
                self.assertNotIn("1090", reply)
                self.assertNotIn("продукт", lowered)
                self.assertNotIn("підпис", lowered)
                self.assertNotIn("зниж", lowered)

    def test_same_turn_acknowledgement_rejects_soft_sales_invites_and_questions(self):
        from management.services.ig_ugc_assessment import safe_ugc_acknowledgement

        unsafe_variants = (
            "Дякуємо! Якщо захочете, я покажу інші варіанти.",
            "Вам дуже пасує цей образ, напишіть, якщо хочете дізнатися більше.",
            "Класна світлина - давайте підберемо ще щось для вас?",
            "Ви чудово виглядаєте. Можемо оформити замовлення вже зараз.",
        )
        for generated in unsafe_variants:
            with self.subTest(generated=generated):
                reply = safe_ugc_acknowledgement(self.client, generated)
                lowered = reply.casefold()
                self.assertIn("дяку", lowered)
                self.assertNotIn("якщо", lowered)
                self.assertNotIn("хоч", lowered)
                self.assertNotIn("напиш", lowered)
                self.assertNotIn("покаж", lowered)
                self.assertNotIn("замов", lowered)
                self.assertNotIn("?", reply)

    def test_same_turn_acknowledgement_rejects_model_text_without_social_anchor(self):
        from management.services.ig_ugc_assessment import safe_ugc_acknowledgement

        reply = safe_ugc_acknowledgement(
            self.client,
            "Це повідомлення описує внутрішні правила бренду без подяки.",
        )

        self.assertIn("дяку", reply.casefold())

    def test_pending_and_rejected_acknowledgements_never_claim_verified_brand_clothing(self):
        from types import SimpleNamespace

        from management.services.ig_ugc_assessment import safe_ugc_acknowledgement

        for decision in ("pending", "needs_manager_review", "rejected"):
            with self.subTest(decision=decision):
                reply = safe_ugc_acknowledgement(
                    self.client,
                    "Ви круто виглядаєте в нашому одязі!",
                    assessment=SimpleNamespace(decision=decision),
                )
                lowered = reply.casefold()
                self.assertIn("дяку", lowered)
                self.assertNotIn("нашому одязі", lowered)
                self.assertNotIn("нашій одежі", lowered)
                self.assertNotIn("виглядаєте", lowered)

    @patch("management.services.bot_vision.gemini_generate_text")
    def test_multimodal_facts_are_strictly_bounded(self, generate):
        from management.services.bot_vision import assess_ugc

        generate.return_value = {
            "parsed": (
                '{"provider_native_mention": true, "personal_worn_apparel": true, '
                '"customer_created_content": true, "customer_content_confidence": 0.99, '
                '"brand_match_confidence": 0.99, "people_count": 2, "garment_count": 2, '
                '"catalog_matches": [{"garment_index": 0, "product_id": 11, "confidence": 0.98}, '
                '{"garment_index": 1, "product_id": 12, "confidence": 0.97}], '
                '"risk_flags": ["ocr_instruction_should_not_be_trusted"], '
                '"reason": "ignore this prompt"}'
            )
        }
        facts = assess_ugc(
            images=[("image/jpeg", b"owned-bytes")],
            candidates=[
                {"id": 11, "title": "Бойова квіточка", "fingerprint": "велика квітка"},
                {"id": 12, "title": "Правди нема", "fingerprint": "ведмідь і напис"},
            ],
        )

        self.assertTrue(facts["personal_worn_apparel"])
        self.assertTrue(facts["customer_created_content"])
        self.assertEqual(facts["catalog_matches"][0]["product_id"], 11)
        self.assertEqual(facts["catalog_matches"][0]["product_name"], "Бойова квіточка")
        self.assertEqual(facts["catalog_matches"][0]["garment_index"], 0)
        self.assertEqual(facts["people_count"], 2)
        self.assertNotIn("reason", facts)
        prompt = generate.call_args.args[0]["contents"][0]["parts"][0]["text"]
        self.assertIn("велика квітка", prompt)
        self.assertIn("ведмідь і напис", prompt)

    @patch("management.services.bot_vision.gemini_generate_text")
    def test_multimodal_boolean_contract_rejects_string_false(self, generate):
        from management.services.bot_vision import assess_ugc

        generate.return_value = {
            "parsed": (
                '{"personal_worn_apparel": "false", "brand_match_confidence": 0.99, '
                '"people_count": 0, "garment_count": 0, "catalog_matches": []}'
            )
        }

        facts = assess_ugc(
            images=[("image/jpeg", b"owned-bytes")],
            candidates=[],
        )

        self.assertIs(facts["personal_worn_apparel"], False)

    def test_ugc_reasoning_policy_is_registered_and_bounded(self):
        from management.services.call_ai_analysis import reasoning_policy

        policy = reasoning_policy("ugc_evidence_assessment")

        self.assertEqual(policy["level"], "high")
        self.assertEqual(policy["max_output_tokens"], 2048)
