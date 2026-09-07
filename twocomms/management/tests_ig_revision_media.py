import hashlib
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from management.models import (
    IgClient,
    IgCustomerTurn,
    IgTurnMessage,
    InstagramBotMessage,
)
from management.services.ig_revision_media import collect_revision_media
from management.services.ig_turn_revisions import (
    claim_revision_preparation,
    claim_sealed_revision,
    create_collecting_revision,
    seal_revision,
)


class RevisionMediaCollectorTests(TestCase):
    def setUp(self):
        self.client_row = IgClient.objects.create(igsid="revision-media-client")

    def _part(self, suffix, body, mime, *, index=0, url="https://signed.invalid/a"):
        return {
            "source_part_id": "mp1_" + suffix * 32,
            "original_index": index,
            "identity_origin": "ingress",
            "type": "audio" if mime.startswith("audio/") else "image",
            "status": "owned",
            "mime": mime,
            "bytes": len(body),
            "content_hash": hashlib.sha256(body).hexdigest(),
            "private_storage": True,
            "storage_name": f"ig-private/{suffix}",
            "url": url,
        }

    def _message(self, mid, text, parts):
        return InstagramBotMessage.objects.create(
            client=self.client_row,
            sender_id=self.client_row.igsid,
            provider_namespace="instagram_login:owner-1",
            role=InstagramBotMessage.Role.USER,
            source="webhook",
            text=text,
            mid=mid,
            status=InstagramBotMessage.Status.PENDING,
            private_media_state=InstagramBotMessage.PrivateMediaState.ACTIVE,
            attachment_media=parts,
        )

    def _revision(self, messages, *, claim=True):
        now = timezone.now()
        turn = IgCustomerTurn.objects.create(
            client=self.client_row,
            primary_source_message=messages[0],
            window_started_at=now,
            window_deadline=now,
        )
        for ordinal, message in enumerate(messages, start=1):
            IgTurnMessage.objects.create(
                turn=turn, message=message, ordinal=ordinal, role=message.role
            )
        revision = create_collecting_revision(
            turn, messages, now=now, bypass_quiet=True
        ).revision
        preparation = claim_revision_preparation(revision.pk, now=now)
        revision = seal_revision(revision.pk, preparation.token, now=now).revision
        if not claim:
            return revision, ""
        claimed = claim_sealed_revision(revision.pk, now=now)
        return claimed.revision, claimed.token

    def test_two_sources_preserve_image_caption_audio_and_owner_headers(self):
        image = b"image-body"
        audio = b"audio-body"
        first = self._message(
            "revision-media-image",
            "Ось фото і підпис",
            [self._part("a", image, "image/jpeg")],
        )
        second = self._message(
            "revision-media-audio",
            "",
            [self._part("b", audio, "audio/mpeg")],
        )
        revision, token = self._revision([first, second])
        bodies = {
            "mp1_" + "a" * 32: ("image/jpeg", image),
            "mp1_" + "b" * 32: ("audio/mpeg", audio),
        }

        with patch(
            "management.services.instagram_bot._owned_media_bytes",
            side_effect=lambda item, **_kwargs: bodies[item["source_part_id"]],
        ):
            result = collect_revision_media(revision.pk, token)

        self.assertEqual(result.readiness, "ready")
        self.assertEqual(result.inline_media, [
            ("image/jpeg", image), ("audio/mpeg", audio),
        ])
        self.assertEqual(result.coverage["image_admitted"], 1)
        self.assertEqual(result.coverage["audio_admitted"], 1)
        self.assertEqual(
            [item["source_message_id"] for item in result.binding["items"]],
            [first.pk, second.pk],
        )
        self.assertEqual(
            [item["source_part_id"] for item in result.binding["items"]],
            ["mp1_" + "a" * 32, "mp1_" + "b" * 32],
        )
        rendered = str(result.binding)
        self.assertNotIn("signed.invalid", rendered)
        self.assertNotIn("storage_name", rendered)
        self.assertNotIn("Ось фото", rendered)
        self.assertNotIn("image-body", repr(result))

    def test_changed_hash_is_partial_but_erasure_invalidates_whole_collection(self):
        first_body = b"first-image"
        second_body = b"second-image"
        first = self._message(
            "revision-media-first",
            "first",
            [self._part("c", first_body, "image/jpeg")],
        )
        second = self._message(
            "revision-media-second",
            "second",
            [self._part("d", second_body, "image/png")],
        )
        revision, token = self._revision([first, second])
        first.attachment_media[0]["content_hash"] = "f" * 64
        first.save(update_fields=["attachment_media"])

        with patch(
            "management.services.instagram_bot._owned_media_bytes",
            return_value=("image/png", second_body),
        ) as reader:
            partial = collect_revision_media(revision.pk, token)

        self.assertEqual(partial.readiness, "partial")
        self.assertEqual(partial.coverage["admitted"], 1)
        self.assertEqual(partial.coverage["unavailable"], 1)
        self.assertEqual(reader.call_count, 1)
        self.assertEqual(
            partial.binding["outcomes"][0]["reason"], "sealed_part_changed"
        )

        self.client_row.privacy_erasure_started_at = timezone.now()
        self.client_row.save(update_fields=["privacy_erasure_started_at", "updated_at"])
        with patch(
            "management.services.instagram_bot._owned_media_bytes"
        ) as erased_reader:
            erased = collect_revision_media(revision.pk, token)
        self.assertEqual(erased.readiness, "invalidated")
        self.assertEqual(erased.reasons, ("client_erasure_active",))
        self.assertFalse(erased.parts)
        erased_reader.assert_not_called()

    def test_raw_budget_omits_each_excess_duplicate_url_part_by_identity(self):
        body = b"x" * (2 * 1024 * 1024)
        shared_url = "https://signed.invalid/equal-url"
        first_parts = [
            self._part(chr(ord("a") + index), body, "image/jpeg", index=index, url=shared_url)
            for index in range(8)
        ]
        second_parts = [
            self._part("i", body, "image/jpeg", index=0, url=shared_url)
        ]
        first = self._message("revision-media-budget-1", "caption", first_parts)
        second = self._message("revision-media-budget-2", "", second_parts)
        revision, token = self._revision([first, second])

        with patch(
            "management.services.instagram_bot._owned_media_bytes",
            return_value=("image/jpeg", body),
        ):
            result = collect_revision_media(revision.pk, token)

        self.assertEqual(result.readiness, "partial")
        self.assertEqual(result.coverage["total_parts"], 9)
        self.assertEqual(result.coverage["admitted"], 6)
        self.assertEqual(result.coverage["omitted"], 3)
        self.assertEqual(len(result.binding["outcomes"]), 9)
        self.assertEqual(
            len({item["source_part_id"] for item in result.binding["outcomes"]}),
            9,
        )
        self.assertTrue(all(
            item["reason"] == "inline_raw_budget"
            for item in result.binding["outcomes"][-3:]
        ))

    def test_not_sealed_not_claimed_and_stale_token_are_typed(self):
        message = self._message("revision-media-state", "caption", [])
        now = timezone.now()
        turn = IgCustomerTurn.objects.create(
            client=self.client_row,
            primary_source_message=message,
            window_started_at=now,
            window_deadline=now,
        )
        IgTurnMessage.objects.create(
            turn=turn, message=message, ordinal=1, role=message.role
        )
        collecting = create_collecting_revision(
            turn, [message], now=now, bypass_quiet=True
        ).revision
        self.assertEqual(
            collect_revision_media(collecting.pk, "wrong").readiness,
            "not_sealed",
        )
        preparation = claim_revision_preparation(collecting.pk, now=now)
        sealed = seal_revision(collecting.pk, preparation.token, now=now).revision
        self.assertEqual(
            collect_revision_media(sealed.pk, "wrong").readiness,
            "not_claimed",
        )
        claimed = claim_sealed_revision(sealed.pk, now=now)
        self.assertEqual(
            collect_revision_media(claimed.revision.pk, "wrong").readiness,
            "stale_revision",
        )
