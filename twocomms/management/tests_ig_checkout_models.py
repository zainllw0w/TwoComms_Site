import hashlib
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone

from management.models import IgClient, IgDeal
from management.services.ig_commercial_episodes import ensure_episode_for_deal
from orders.models import Order


class IgCheckoutProposalModelTests(TestCase):
    def setUp(self):
        self.client = IgClient.get_or_create_for_sender("ig-checkout-models")
        self.deal = IgDeal.objects.create(
            client=self.client,
            status=IgDeal.Status.QUOTED,
            amount=Decimal("790.00"),
            requested_payment_amount=Decimal("790.00"),
        )
        self.episode = ensure_episode_for_deal(self.deal)

    def _proposal(self, **overrides):
        from management.models import IgCheckoutProposal

        defaults = {
            "deal": self.deal,
            "catalog_total": Decimal("790.00"),
            "quoted_total": Decimal("790.00"),
            "requested_payment_amount": Decimal("790.00"),
            "items_digest": "a" * 64,
        }
        defaults.update(overrides)
        return IgCheckoutProposal.objects.create_current(**defaults)

    def test_active_proposal_has_positive_total_and_future_expiry(self):
        from management.models import IgCheckoutProposal

        for quoted_total, expires_at in (
            (Decimal("0.00"), timezone.now() + timedelta(hours=12)),
            (Decimal("-1.00"), timezone.now() + timedelta(hours=12)),
            (Decimal("790.00"), timezone.now() - timedelta(seconds=1)),
        ):
            proposal = IgCheckoutProposal(
                client=self.client,
                deal=self.deal,
                commercial_episode=self.episode,
                status=IgCheckoutProposal.Status.READY,
                catalog_total=Decimal("790.00"),
                quoted_total=quoted_total,
                requested_payment_amount=Decimal("790.00"),
                items_digest="b" * 64,
                expires_at=expires_at,
            )
            with self.assertRaises(ValidationError):
                proposal.full_clean()

    def test_revision_is_append_only(self):
        from management.models import IgCheckoutRevision

        proposal = self._proposal()
        revision = IgCheckoutRevision.objects.create(
            proposal=proposal,
            revision=1,
            digest=proposal.items_digest,
            snapshot={"items": [], "quoted_total": "790.00"},
            source=IgCheckoutRevision.Source.BOT_CREATE,
        )

        revision.snapshot = {"items": [{"changed": True}]}
        with self.assertRaisesMessage(ValueError, "append-only"):
            revision.save()
        with self.assertRaisesMessage(ValueError, "append-only"):
            IgCheckoutRevision.objects.filter(pk=revision.pk).update(source="changed")
        with self.assertRaisesMessage(ValueError, "append-only"):
            IgCheckoutRevision.objects.filter(pk=revision.pk).delete()

    def test_access_token_stores_digest_not_raw_token(self):
        from management.models import IgCheckoutAccessToken

        proposal = self._proposal()
        raw_token, token = IgCheckoutAccessToken.issue(
            proposal=proposal,
            kind=IgCheckoutAccessToken.Kind.BOT,
        )

        token.refresh_from_db()
        self.assertNotEqual(raw_token, token.token_digest)
        self.assertEqual(
            token.token_digest,
            hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
        )
        persisted_fields = {
            field.name: getattr(token, field.name)
            for field in token._meta.concrete_fields
        }
        self.assertNotIn(raw_token, map(str, persisted_fields.values()))

    def test_lifecycle_event_key_is_unique(self):
        from management.models import IgLifecycleEvent

        proposal = self._proposal()
        kwargs = {
            "event_key": "proposal:model-test:payment",
            "kind": IgLifecycleEvent.Kind.PAYMENT_VERIFIED,
            "client": self.client,
            "deal": self.deal,
            "proposal": proposal,
            "commercial_episode": self.episode,
        }
        IgLifecycleEvent.objects.create(**kwargs)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                IgLifecycleEvent.objects.create(**kwargs)

    def test_paid_proposal_cannot_be_superseded(self):
        from management.models import IgCheckoutProposal

        proposal = self._proposal()
        proposal.status = IgCheckoutProposal.Status.PAID
        proposal.paid_at = timezone.now()
        proposal.save(update_fields=["status", "paid_at", "updated_at"])

        with self.assertRaisesMessage(ValidationError, "paid"):
            IgCheckoutProposal.objects.replace_current(
                deal=self.deal,
                catalog_total=Decimal("890.00"),
                quoted_total=Decimal("890.00"),
                requested_payment_amount=Decimal("890.00"),
                items_digest="c" * 64,
            )

    def test_deal_retains_historical_proposals_with_one_active_pointer(self):
        from management.models import IgCheckoutProposal

        first = self._proposal()
        first.status = IgCheckoutProposal.Status.CANCELLED
        first.invoice_cancelled_at = timezone.now()
        first.save(update_fields=["status", "invoice_cancelled_at", "updated_at"])

        second = IgCheckoutProposal.objects.replace_current(
            deal=self.deal,
            catalog_total=Decimal("890.00"),
            quoted_total=Decimal("890.00"),
            requested_payment_amount=Decimal("890.00"),
            items_digest="d" * 64,
        )

        self.deal.refresh_from_db()
        first.refresh_from_db()
        self.assertEqual(self.deal.checkout_proposals.count(), 2)
        self.assertEqual(self.deal.active_checkout_proposal_id, second.pk)
        self.assertEqual(first.superseded_by_id, second.pk)
        self.assertEqual(first.status, IgCheckoutProposal.Status.SUPERSEDED)

    def test_concurrent_replacement_creation_serializes_on_deal(self):
        from management.models import IgCheckoutProposal

        first = self._proposal()
        first.status = IgCheckoutProposal.Status.CANCELLED
        first.invoice_cancelled_at = timezone.now()
        first.save(update_fields=["status", "invoice_cancelled_at", "updated_at"])
        second = IgCheckoutProposal.objects.replace_current(
            deal=self.deal,
            catalog_total=Decimal("890.00"),
            quoted_total=Decimal("890.00"),
            requested_payment_amount=Decimal("890.00"),
            items_digest="e" * 64,
        )

        with self.assertRaisesMessage(ValidationError, "current proposal"):
            IgCheckoutProposal.objects.replace_current(
                deal=self.deal,
                catalog_total=Decimal("990.00"),
                quoted_total=Decimal("990.00"),
                requested_payment_amount=Decimal("990.00"),
                items_digest="f" * 64,
            )
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.active_checkout_proposal_id, second.pk)

    def test_confirmed_cancelled_invoice_can_be_replaced(self):
        from management.models import IgCheckoutProposal

        invoice = self._proposal(status=IgCheckoutProposal.Status.INVOICE_CREATED)
        with self.assertRaisesMessage(ValidationError, "payable or ambiguous"):
            IgCheckoutProposal.objects.replace_current(
                deal=self.deal,
                catalog_total=Decimal("890.00"),
                quoted_total=Decimal("890.00"),
                requested_payment_amount=Decimal("890.00"),
                items_digest="1" * 64,
            )

        invoice.status = IgCheckoutProposal.Status.CANCELLED
        invoice.invoice_cancelled_at = timezone.now()
        invoice.save(update_fields=["status", "invoice_cancelled_at", "updated_at"])
        replacement = IgCheckoutProposal.objects.replace_current(
            deal=self.deal,
            catalog_total=Decimal("890.00"),
            quoted_total=Decimal("890.00"),
            requested_payment_amount=Decimal("890.00"),
            items_digest="2" * 64,
        )
        self.assertNotEqual(replacement.pk, invoice.pk)

    def test_archiving_client_or_deal_cannot_cascade_financial_evidence(self):
        proposal = self._proposal()

        with self.assertRaises(ProtectedError):
            self.client.delete()
        with self.assertRaises(ProtectedError):
            self.deal.delete()
        self.assertTrue(type(proposal).objects.filter(pk=proposal.pk).exists())

    def test_invoice_proposal_requires_episode_and_lifecycle_attribution(self):
        from management.models import (
            IgCheckoutProposal,
            IgLifecycleEvent,
            IgOrderAttribution,
        )

        proposal = self._proposal(status=IgCheckoutProposal.Status.INVOICE_CREATED)
        self.assertEqual(proposal.commercial_episode_id, self.episode.pk)

        order = Order.objects.create(
            full_name="Instagram Buyer",
            phone="+380501112233",
            city="Kyiv",
            np_office="Branch 1",
            pay_type="online_full",
            status="new",
            payment_status="paid",
            total_sum=Decimal("790.00"),
        )
        attribution = IgOrderAttribution.objects.create(
            order=order,
            client=self.client,
            deal=self.deal,
            creation_mode="provider_auto",
            payment_source="provider_attempt",
        )
        event = IgLifecycleEvent(
            event_key="proposal:model-test:ttn",
            kind=IgLifecycleEvent.Kind.TTN_CREATED,
            client=self.client,
            deal=self.deal,
            proposal=proposal,
            order=order,
            commercial_episode=self.episode,
        )
        with self.assertRaises(ValidationError):
            event.full_clean()

        event.attribution = attribution
        event.full_clean()
        event.save()
        self.assertEqual(event.attribution_id, attribution.pk)
