import hashlib
import json

from django.db import connection
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from management.models import (
    BotPolicyPublication,
    IgClient,
    IgCustomerTurn,
    IgRevisionDeliveryEffect,
    IgTurnMessage,
    InstagramBotMessage,
    InstagramBotSettings,
)
from management.services.ig_catalog_media import (
    CatalogMediaItem,
    CatalogMediaSelection,
    CatalogMediaState,
    prepare_catalog_media,
)
from management.services.ig_message_templates import (
    GenericTemplate,
    TemplateCard,
    prepare_template_effects,
)
from management.services.ig_revision_delivery import (
    ProviderPartResult,
    drain_group,
)
from management.services.ig_revision_outbox import (
    PublicationBinding,
    plan_revision_effects,
)
from management.services.ig_turn_revisions import (
    claim_revision_preparation,
    claim_sealed_revision,
    create_collecting_revision,
    seal_revision,
)


@override_settings(SITE_BASE_URL="https://twocomms.test")
class RevisionDeliveryTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        snapshot = {"schema_version": 1, "instructions": []}
        snapshot_hash = hashlib.sha256(json.dumps(
            snapshot,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()).hexdigest()
        self.publication = BotPolicyPublication.objects.create(
            version=1,
            kind=BotPolicyPublication.Kind.PUBLISH,
            schema_version=1,
            snapshot=snapshot,
            snapshot_hash=snapshot_hash,
            compiler_version="instruction-set-v1",
            instruction_count=0,
        )
        self.settings = InstagramBotSettings.objects.create(
            pk=1,
            is_enabled=True,
            reply_permission_epoch=4,
            active_instruction_publication=self.publication,
        )
        self.client_row = IgClient.objects.create(
            igsid="revision-delivery-client",
            reply_permission_epoch=3,
        )
        self.source = InstagramBotMessage.objects.create(
            client=self.client_row,
            sender_id=self.client_row.igsid,
            provider_namespace="instagram_login:owner-1",
            role=InstagramBotMessage.Role.USER,
            source="webhook",
            text="question",
            mid="revision-delivery-source",
            status=InstagramBotMessage.Status.PENDING,
        )
        now = timezone.now()
        turn = IgCustomerTurn.objects.create(
            client=self.client_row,
            primary_source_message=self.source,
            window_started_at=now,
            window_deadline=now,
        )
        IgTurnMessage.objects.create(
            turn=turn, message=self.source, ordinal=1, role=self.source.role
        )
        revision = create_collecting_revision(
            turn, [self.source], now=now, bypass_quiet=True
        ).revision
        preparation = claim_revision_preparation(revision.pk, now=now)
        revision = seal_revision(revision.pk, preparation.token, now=now).revision
        claim = claim_sealed_revision(revision.pk, now=now)
        self.revision = claim.revision
        self.revision_token = claim.token
        self.binding = PublicationBinding(
            self.publication.pk,
            self.publication.version,
            self.publication.snapshot_hash,
        )

    def _payload(self, text):
        return {
            "recipient": {"id": self.client_row.igsid},
            "message": {"text": text},
        }

    def _plan(self, specs):
        result = plan_revision_effects(
            self.revision.pk,
            self.revision_token,
            source_message_id=self.source.pk,
            settings_id=self.settings.pk,
            settings_permission_epoch=self.settings.reply_permission_epoch,
            publication=self.binding,
            authority_context_digest="e" * 64,
            effects=specs,
        )
        self.assertTrue(result.created, result.reasons)
        return result

    def test_three_chunks_stop_at_second_unknown_and_resume_never_repeats_first(self):
        self._plan([
            {"group": "substantive_text", "kind": "text", "payload": self._payload("one")},
            {"group": "substantive_text", "kind": "text", "payload": self._payload("two")},
            {"group": "substantive_text", "kind": "text", "payload": self._payload("three")},
        ])
        calls = []

        def transport(payload):
            calls.append(payload["message"]["text"])
            if len(calls) == 1:
                return ProviderPartResult(
                    "instagram_login:owner-1", 200, "receipt-one"
                )
            return ProviderPartResult(
                "instagram_login:owner-1", 503, outcome="response"
            )

        first = drain_group(
            self.revision.pk,
            self.revision_token,
            "substantive_text",
            transport,
        )
        resumed_calls = []
        resumed = drain_group(
            self.revision.pk,
            self.revision_token,
            "substantive_text",
            lambda payload: resumed_calls.append(payload),
        )

        self.assertEqual(first.state, "unknown")
        self.assertEqual(calls, ["one", "two"])
        self.assertEqual(
            [(part.part_index, part.provider_message_id) for part in first.sent_parts],
            [(0, "receipt-one")],
        )
        self.assertEqual(resumed.state, "unknown")
        self.assertEqual(resumed_calls, [])

    def test_transport_receives_fresh_db_payload_copy_outside_atomic(self):
        caller_payload = self._payload("canonical")
        plan = self._plan([
            {"group": "substantive_text", "kind": "text", "payload": caller_payload},
        ])
        caller_payload["message"]["text"] = "caller-mutated"
        observed = {}

        def transport(payload):
            observed["atomic"] = connection.in_atomic_block
            observed["text"] = payload["message"]["text"]
            payload["message"]["text"] = "callback-mutated"
            return ProviderPartResult(
                "instagram_login:owner-1", 200, "canonical-receipt"
            )

        result = drain_group(
            self.revision.pk,
            self.revision_token,
            "substantive_text",
            transport,
        )

        self.assertEqual(result.state, "sent")
        self.assertFalse(observed["atomic"])
        self.assertEqual(observed["text"], "canonical")
        plan.effects[0].refresh_from_db()
        self.assertEqual(plan.effects[0].payload["message"]["text"], "canonical")

    def test_media_unknown_does_not_block_independent_text(self):
        self._plan([
            {
                "group": "catalog_media",
                "kind": "image",
                "payload": {
                    "recipient": {"id": self.client_row.igsid},
                    "message": {"attachment": {"type": "image", "payload": {"url": "https://twocomms.test/a.jpg"}}},
                },
            },
            {"group": "substantive_text", "kind": "text", "payload": self._payload("caption")},
        ])
        media = drain_group(
            self.revision.pk,
            self.revision_token,
            "catalog_media",
            lambda _payload: ProviderPartResult(
                "instagram_login:owner-1", outcome="timeout"
            ),
        )
        text = drain_group(
            self.revision.pk,
            self.revision_token,
            "substantive_text",
            lambda _payload: ProviderPartResult(
                "instagram_login:owner-1", 200, "text-receipt"
            ),
        )

        self.assertEqual(media.state, "unknown")
        self.assertEqual(text.state, "sent")
        self.assertEqual(text.sent_parts[0].provider_message_id, "text-receipt")

    def test_template_unknown_terminalizes_fallback_without_calling_it(self):
        prepared = prepare_template_effects(
            self.client_row.igsid,
            GenericTemplate(
                cards=(TemplateCard(title="Card", subtitle="Subtitle"),),
                fallback_text="Fallback text",
                projection_text="Card projection",
            ),
        )
        self._plan(prepared.effects)
        primary = drain_group(
            self.revision.pk,
            self.revision_token,
            "template",
            lambda _payload: ProviderPartResult(
                "instagram_login:owner-1", outcome="timeout"
            ),
        )
        fallback_calls = []
        fallback = drain_group(
            self.revision.pk,
            self.revision_token,
            "template_fallback",
            lambda payload: fallback_calls.append(payload),
        )

        self.assertEqual(primary.state, "unknown")
        self.assertEqual(fallback.state, "cancelled")
        self.assertEqual(fallback_calls, [])

    def test_catalog_preparation_returns_exact_payloads_and_safe_projection(self):
        selection = CatalogMediaSelection(
            state=CatalogMediaState.READY,
            items=(
                CatalogMediaItem(
                    "https://twocomms.test/a.jpg",
                    "First",
                    "First alt",
                    10,
                    "image/jpeg",
                    100,
                ),
                CatalogMediaItem(
                    "https://twocomms.test/b.png",
                    "Second",
                    "Second alt",
                    20,
                    "image/png",
                    200,
                ),
            ),
        )

        prepared = prepare_catalog_media(
            self.settings, self.client_row.igsid, selection
        )

        self.assertEqual(len(prepared.payloads), 2)
        self.assertEqual(
            [payload["message"]["attachment"]["payload"]["url"] for payload in prepared.payloads],
            ["https://twocomms.test/a.jpg", "https://twocomms.test/b.png"],
        )
        self.assertEqual(
            prepared.product_refs,
            (
                {"part_index": 0, "product_id": 10, "title": "First"},
                {"part_index": 1, "product_id": 20, "title": "Second"},
            ),
        )
