import hashlib
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from management.models import (
    IgCheckoutInvoiceGeneration,
    IgCheckoutInvoiceGenerationEvent,
    IgCheckoutProposal,
    IgClient,
    IgCommercialEpisode,
    IgDeal,
    InstagramBotMessage,
)


class CheckoutGenerationSchemaTests(TestCase):
    def setUp(self):
        self.client_row = IgClient.objects.create(igsid="checkout-generation-schema")
        self.deal = IgDeal.objects.create(
            client=self.client_row,
            amount=Decimal("800.00"),
            requested_payment_amount=Decimal("800.00"),
        )
        self.episode = IgCommercialEpisode.objects.create(
            client=self.client_row,
            deal=self.deal,
            sequence=1,
            open_slot=1,
            materialization_key="checkout-generation-schema:episode",
        )

    def _proposal(self, **overrides):
        values = {
            "client": self.client_row,
            "deal": self.deal,
            "commercial_episode": self.episode,
            "catalog_total": Decimal("800.00"),
            "quoted_total": Decimal("800.00"),
            "requested_payment_amount": Decimal("800.00"),
            "items_digest": "a" * 64,
            "expires_at": timezone.now() + timedelta(minutes=25),
        }
        values.update(overrides)
        return IgCheckoutProposal.objects.create(**values)

    def _generation(self, proposal, number, **overrides):
        values = {
            "proposal": proposal,
            "generation": number,
            "series_key": "b" * 64,
            "proposal_revision": proposal.revision,
            "state": IgCheckoutInvoiceGeneration.State.PLANNED,
            "payment_choice": IgCheckoutInvoiceGeneration.PaymentChoice.FULL,
            "payment_amount": proposal.quoted_total,
            "provider_call_token": hashlib.sha256(
                f"generation:{proposal.pk}:{number}".encode()
            ).hexdigest(),
            "expires_at": timezone.now() + timedelta(minutes=25),
        }
        values.update(overrides)
        return IgCheckoutInvoiceGeneration.objects.create(**values)

    def test_legacy_defaults_do_not_rewrite_ttl_or_activate_v2(self):
        before = timezone.now()
        proposal = self._proposal()

        self.assertFalse(proposal.assisted_checkout_v2)
        self.assertEqual(proposal.payment_policy, proposal.PaymentPolicy.LEGACY)
        self.assertIsNone(proposal.current_invoice_generation_id)
        self.assertIsNone(proposal.winner_invoice_generation_id)
        self.assertLess(proposal.expires_at, before + timedelta(minutes=26))

    def test_v2_policy_requires_owned_user_evidence_and_custom_is_full_only(self):
        manager = InstagramBotMessage.objects.create(
            client=self.client_row,
            sender_id=self.client_row.igsid,
            role=InstagramBotMessage.Role.MANAGER,
            text="наложка",
        )
        with self.assertRaises(ValidationError):
            self._proposal(
                assisted_checkout_v2=True,
                payment_policy=IgCheckoutProposal.PaymentPolicy.FULL_OR_200_COD,
                payment_policy_evidence_message=manager,
                payment_policy_evidence_kind="direct_question",
                payment_policy_evidence_revision=1,
                payment_policy_evidence_digest="c" * 64,
                expires_at=timezone.now() + timedelta(hours=12),
            )

        user_message = InstagramBotMessage.objects.create(
            client=self.client_row,
            sender_id=self.client_row.igsid,
            role=InstagramBotMessage.Role.USER,
            text="Чи можна 200 грн передоплати, а решту післяплатою?",
        )
        proposal = self._proposal(
            assisted_checkout_v2=True,
            payment_policy=IgCheckoutProposal.PaymentPolicy.FULL_OR_200_COD,
            payment_policy_evidence_message=user_message,
            payment_policy_evidence_kind="direct_question",
            payment_policy_evidence_revision=1,
            payment_policy_evidence_digest="d" * 64,
            expires_at=timezone.now() + timedelta(hours=12),
        )
        self.assertTrue(proposal.assisted_checkout_v2)

        proposal.custom_print_full_only = True
        with self.assertRaises(ValidationError):
            proposal.full_clean()

    def test_generation_active_winner_and_provider_id_barriers(self):
        proposal = self._proposal(
            assisted_checkout_v2=True,
            payment_policy=IgCheckoutProposal.PaymentPolicy.FULL_ONLY,
            expires_at=timezone.now() + timedelta(hours=12),
        )
        self._generation(
            proposal,
            1,
            active_slot=1,
            provider_invoice_id="invoice-one",
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._generation(proposal, 2, active_slot=1)
        second = self._generation(proposal, 2, winner_slot=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._generation(proposal, 3, winner_slot=1)
        other_client = IgClient.objects.create(
            igsid="checkout-generation-schema-other"
        )
        other_deal = IgDeal.objects.create(
            client=other_client,
            amount=Decimal("900.00"),
            requested_payment_amount=Decimal("900.00"),
        )
        other_proposal = IgCheckoutProposal.objects.create(
            client=other_client,
            deal=other_deal,
            commercial_episode=IgCommercialEpisode.objects.create(
                client=other_client,
                deal=other_deal,
                sequence=1,
                open_slot=1,
                materialization_key="checkout-generation-schema:episode:other",
            ),
            catalog_total=Decimal("900.00"),
            quoted_total=Decimal("900.00"),
            requested_payment_amount=Decimal("900.00"),
            items_digest="e" * 64,
            assisted_checkout_v2=True,
            payment_policy=IgCheckoutProposal.PaymentPolicy.FULL_ONLY,
            expires_at=timezone.now() + timedelta(hours=12),
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._generation(
                other_proposal,
                1,
                provider_invoice_id="invoice-one",
            )
        self.assertEqual(second.winner_slot, 1)

    def test_generation_events_are_append_only_at_orm_boundary(self):
        proposal = self._proposal(
            assisted_checkout_v2=True,
            payment_policy=IgCheckoutProposal.PaymentPolicy.FULL_ONLY,
            expires_at=timezone.now() + timedelta(hours=12),
        )
        generation = self._generation(proposal, 1)
        event = IgCheckoutInvoiceGenerationEvent.objects.create(
            event_key="checkout-generation-schema:event:1",
            generation=generation,
            proposal=proposal,
            kind=IgCheckoutInvoiceGenerationEvent.Kind.CREATED,
            payload={"generation": 1},
        )
        with self.assertRaisesRegex(ValueError, "append-only"):
            IgCheckoutInvoiceGenerationEvent._base_manager.filter(
                pk=event.pk
            ).update(payload={})
        with self.assertRaisesRegex(ValueError, "append-only"):
            event.delete()

    def test_engine_inventory_registers_generation_tables(self):
        from management.services.ig_engine_health import IG_RUNTIME_TABLES

        self.assertIn("management_igcheckoutinvoicegeneration", IG_RUNTIME_TABLES)
        self.assertIn("management_igcheckoutinvoicegenerationevent", IG_RUNTIME_TABLES)
