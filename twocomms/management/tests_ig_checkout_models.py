import hashlib
from datetime import timedelta
from decimal import Decimal
from threading import Barrier, Lock, Thread
from unittest import skipUnless

from django.core.exceptions import ValidationError
from django.db import (
    DatabaseError,
    IntegrityError,
    close_old_connections,
    connection,
    transaction,
)
from django.db.models.deletion import ProtectedError
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from management.models import IgClient, IgDeal
from management.services.ig_commercial_episodes import ensure_episode_for_deal
from orders.models import Order, PaymentAttempt


class IgCheckoutProposalModelTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # test_settings disables migrations, so install the same SQLite
        # append-only guards used by the checkout migration for raw SQL tests.
        if connection.vendor == "sqlite":
            with connection.cursor() as cursor:
                cursor.execute("DROP TRIGGER IF EXISTS ig_chk_revision_no_update")
                cursor.execute("DROP TRIGGER IF EXISTS ig_chk_revision_no_delete")
                cursor.execute("DROP TRIGGER IF EXISTS ig_chk_lifecycle_no_delete")
                cursor.execute("DROP TRIGGER IF EXISTS ig_chk_lifecycle_identity_no_update")
                cursor.execute(
                    "CREATE TRIGGER ig_chk_revision_no_update BEFORE UPDATE "
                    "ON management_igcheckoutrevision BEGIN SELECT RAISE(ABORT, "
                    "'IgCheckoutRevision is append-only'); END"
                )
                cursor.execute(
                    "CREATE TRIGGER ig_chk_revision_no_delete BEFORE DELETE "
                    "ON management_igcheckoutrevision BEGIN SELECT RAISE(ABORT, "
                    "'IgCheckoutRevision is append-only'); END"
                )
                cursor.execute(
                    "CREATE TRIGGER ig_chk_lifecycle_no_delete BEFORE DELETE "
                    "ON management_iglifecycleevent BEGIN SELECT RAISE(ABORT, "
                    "'IgLifecycleEvent is durable'); END"
                )
                cursor.execute(
                    "CREATE TRIGGER ig_chk_lifecycle_identity_no_update BEFORE UPDATE "
                    "ON management_iglifecycleevent WHEN OLD.event_key IS NOT NEW.event_key "
                    "OR OLD.kind IS NOT NEW.kind OR OLD.client_id IS NOT NEW.client_id "
                    "OR OLD.deal_id IS NOT NEW.deal_id OR OLD.proposal_id IS NOT NEW.proposal_id "
                    "OR OLD.order_id IS NOT NEW.order_id "
                    "OR OLD.commercial_episode_id IS NOT NEW.commercial_episode_id "
                    "OR OLD.attribution_id IS NOT NEW.attribution_id OR OLD.locale IS NOT NEW.locale "
                    "OR OLD.payload IS NOT NEW.payload BEGIN SELECT RAISE(ABORT, "
                    "'IgLifecycleEvent identity is immutable'); END"
                )

    @classmethod
    def tearDownClass(cls):
        if connection.vendor == "sqlite":
            with connection.cursor() as cursor:
                for name in (
                    "ig_chk_revision_no_update",
                    "ig_chk_revision_no_delete",
                    "ig_chk_lifecycle_no_delete",
                    "ig_chk_lifecycle_identity_no_update",
                ):
                    cursor.execute(f"DROP TRIGGER IF EXISTS {name}")
        super().tearDownClass()

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

    def _terminal_attempt(self, suffix="1", *, status=None, order=None):
        invoice_id = f"inv-cancelled-{suffix}"
        return PaymentAttempt.objects.create(
            fingerprint=hashlib.sha256(f"cancelled:{suffix}".encode()).hexdigest(),
            full_name="Instagram Buyer",
            phone="+380501112233",
            email="buyer@example.com",
            city="Kyiv",
            np_office="Branch 1",
            pay_type=PaymentAttempt.PayType.ONLINE_FULL,
            status=status or PaymentAttempt.Status.CANCELLED,
            cart_snapshot={"items": []},
            gross_amount=Decimal("790.00"),
            payable_amount=Decimal("790.00"),
            payment_amount=Decimal("790.00"),
            monobank_invoice_id=invoice_id,
            order=order,
        )

    def _provider_terminal_event(self, attempt, *, provider_status="cancelled", source="provider_pull"):
        from management.models import IgPaymentEvent, IgPaymentProjection

        event = IgPaymentEvent.objects.create(
            event_key=hashlib.sha256(
                f"terminal:{self.deal.pk}:{attempt.pk}:{provider_status}:{source}".encode()
            ).hexdigest(),
            deal=self.deal,
            client=self.client,
            provider="monobank",
            source=source,
            invoice_id=attempt.monobank_invoice_id,
            provider_status=provider_status,
            evidence={"status": provider_status},
            payload_digest=hashlib.sha256(
                f"payload:{attempt.pk}:{provider_status}:{source}".encode()
            ).hexdigest(),
        )
        truth = (
            IgDeal.PaymentTruth.CANCELLED
            if provider_status in {"cancelled", "canceled", "expired"}
            else IgDeal.PaymentTruth.FAILED
        )
        IgPaymentProjection.objects.update_or_create(
            deal=self.deal,
            defaults={
                "client": self.client,
                "truth": truth,
                "last_event": event,
            },
        )
        return event

    def _order_and_attribution(self, *, proposal=None, client=None, deal=None):
        from management.models import IgOrderAttribution

        client = client or self.client
        deal = deal or self.deal

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
            client=client,
            deal=deal,
            creation_mode="provider_auto",
            payment_source="provider_attempt",
        )
        if proposal is not None:
            attempt = self._terminal_attempt(
                f"order-{order.pk}",
                status=PaymentAttempt.Status.CONVERTED,
                order=order,
            )
            proposal.payment_attempt = attempt
            proposal.save(update_fields=["payment_attempt", "updated_at"])
        return order, attribution

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
        order, attribution = self._order_and_attribution(proposal=proposal)
        kwargs = {
            "event_key": "proposal:model-test:payment",
            "kind": IgLifecycleEvent.Kind.PAYMENT_VERIFIED,
            "client": self.client,
            "deal": self.deal,
            "proposal": proposal,
            "order": order,
            "commercial_episode": self.episode,
            "attribution": attribution,
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
        with self.assertRaisesMessage(ValueError, "transition"):
            IgCheckoutProposal.objects.filter(pk=proposal.pk).update(
                status=IgCheckoutProposal.Status.SUPERSEDED,
            )

    def test_paid_proposal_rejects_combined_bulk_state_and_financial_mutation(self):
        from management.models import IgCheckoutProposal

        proposal = self._proposal()
        proposal.status = IgCheckoutProposal.Status.PAID
        proposal.paid_at = timezone.now()
        proposal.save(update_fields=["status", "paid_at", "updated_at"])

        with self.assertRaisesMessage(ValueError, "transition"):
            IgCheckoutProposal.objects.filter(pk=proposal.pk).update(
                status=IgCheckoutProposal.Status.PAID,
                superseded_by_id=proposal.pk,
                quoted_total=Decimal("1.00"),
                items_digest="z" * 64,
            )
        proposal.quoted_total = Decimal("1.00")
        with self.assertRaisesMessage(ValidationError, "paid"):
            proposal.save(update_fields=["quoted_total", "updated_at"])

    def test_paid_proposal_cannot_be_marked_superseded_on_instance_save(self):
        from management.models import IgCheckoutProposal

        proposal = self._proposal()
        replacement = IgCheckoutProposal(
            deal=self.deal,
            client=self.client,
            commercial_episode=self.episode,
            catalog_total=Decimal("890.00"),
            quoted_total=Decimal("890.00"),
            requested_payment_amount=Decimal("890.00"),
            items_digest="r" * 64,
            status=IgCheckoutProposal.Status.READY,
        )
        replacement.save(force_insert=True)
        proposal.status = IgCheckoutProposal.Status.PAID
        proposal.paid_at = timezone.now()
        proposal.save(update_fields=["status", "paid_at", "updated_at"])
        proposal.status = IgCheckoutProposal.Status.SUPERSEDED
        proposal.superseded_by = replacement
        with self.assertRaisesMessage(ValidationError, "paid"):
            proposal.save(update_fields=["status", "superseded_by", "updated_at"])

    def test_deal_retains_historical_proposals_with_one_active_pointer(self):
        from management.models import IgCheckoutProposal

        first = self._proposal()
        attempt = self._terminal_attempt("history")
        event = self._provider_terminal_event(attempt)
        first.status = IgCheckoutProposal.Status.CANCELLED
        first.invoice_cancelled_at = timezone.now()
        first.payment_attempt = attempt
        first.provider_cancellation_event = event
        first.save(update_fields=[
            "status", "invoice_cancelled_at", "payment_attempt",
            "provider_cancellation_event", "updated_at",
        ])

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

    def test_confirmed_cancelled_invoice_can_be_replaced(self):
        from management.models import IgCheckoutProposal

        attempt = self._terminal_attempt("replace")
        event = self._provider_terminal_event(attempt)
        invoice = self._proposal(
            status=IgCheckoutProposal.Status.INVOICE_CREATED,
            payment_attempt=attempt,
        )
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
        with self.assertRaisesMessage(ValidationError, "provider-confirmed"):
            IgCheckoutProposal.objects.replace_current(
                deal=self.deal,
                catalog_total=Decimal("890.00"),
                quoted_total=Decimal("890.00"),
                requested_payment_amount=Decimal("890.00"),
                items_digest="3" * 64,
            )
        invoice.provider_cancellation_event = event
        invoice.save(update_fields=["provider_cancellation_event", "updated_at"])
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

        order, attribution = self._order_and_attribution(proposal=proposal)
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

    def test_provider_cancellation_requires_immutable_event_and_no_order(self):
        from management.models import IgCheckoutProposal

        attempt = self._terminal_attempt("forged")
        proposal = self._proposal(
            status=IgCheckoutProposal.Status.CANCELLED,
            payment_attempt=attempt,
            invoice_cancelled_at=timezone.now(),
        )
        proposal.provider_cancellation_event_id = None
        proposal.save(update_fields=["provider_cancellation_event", "updated_at"])
        self.assertFalse(proposal.has_provider_confirmed_cancellation())

        event = self._provider_terminal_event(attempt, source="manual")
        proposal.provider_cancellation_event = event
        proposal.save(update_fields=["provider_cancellation_event", "updated_at"])
        self.assertFalse(proposal.has_provider_confirmed_cancellation())

        event = self._provider_terminal_event(attempt, source="provider_pull")
        proposal.provider_cancellation_event = event
        proposal.save(update_fields=["provider_cancellation_event", "updated_at"])
        self.assertTrue(proposal.has_provider_confirmed_cancellation())

        order, _ = self._order_and_attribution()
        attempt.order = order
        attempt.save(update_fields=["order", "updated"])
        proposal.refresh_from_db()
        self.assertFalse(proposal.has_provider_confirmed_cancellation())

    def test_lifecycle_orm_writes_validate_exact_attribution_and_are_not_deletable(self):
        from management.models import IgLifecycleEvent

        proposal = self._proposal()
        order, attribution = self._order_and_attribution(proposal=proposal)
        kwargs = {
            "event_key": "proposal:model-test:orm-guard",
            "kind": IgLifecycleEvent.Kind.TTN_CREATED,
            "client": self.client,
            "deal": self.deal,
            "proposal": proposal,
            "order": order,
            "commercial_episode": self.episode,
            "attribution": attribution,
        }
        event = IgLifecycleEvent.objects.create(**kwargs)
        with self.assertRaises(ValueError):
            IgLifecycleEvent.objects.filter(pk=event.pk).update(deal_id=self.deal.pk + 1)
        with self.assertRaises(ValueError):
            IgLifecycleEvent.objects.filter(pk=event.pk).delete()
        with self.assertRaises(ValueError):
            event.delete()

        wrong_client = IgClient.get_or_create_for_sender("ig-checkout-wrong-client")
        wrong_deal = IgDeal.objects.create(
            client=wrong_client,
            status=IgDeal.Status.QUOTED,
            amount=Decimal("790.00"),
            requested_payment_amount=Decimal("790.00"),
        )
        wrong_episode = ensure_episode_for_deal(wrong_deal)
        wrong_order, wrong_attribution = self._order_and_attribution(
            client=wrong_client,
            deal=wrong_deal,
        )
        with self.assertRaises(ValidationError):
            IgLifecycleEvent.objects.create(
                **{
                    **kwargs,
                    "event_key": "proposal:model-test:wrong-attribution",
                    "order": wrong_order,
                    "commercial_episode": wrong_episode,
                    "attribution": wrong_attribution,
                }
            )

    def test_append_only_triggers_protect_revision_and_lifecycle_identity(self):
        from management.models import IgCheckoutRevision, IgLifecycleEvent

        proposal = self._proposal()
        revision = IgCheckoutRevision.objects.create(
            proposal=proposal,
            revision=1,
            digest=proposal.items_digest,
            snapshot={"items": []},
            source=IgCheckoutRevision.Source.BOT_CREATE,
        )
        order, attribution = self._order_and_attribution(proposal=proposal)
        event = IgLifecycleEvent.objects.create(
            event_key="proposal:model-test:trigger-guard",
            kind=IgLifecycleEvent.Kind.TTN_CREATED,
            client=self.client,
            deal=self.deal,
            proposal=proposal,
            order=order,
            commercial_episode=self.episode,
            attribution=attribution,
        )
        with self.assertRaises(DatabaseError):
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE management_igcheckoutrevision SET digest=%s WHERE id=%s",
                    ["x" * 64, revision.pk],
                )
        with self.assertRaises(DatabaseError):
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM management_iglifecycleevent WHERE id=%s",
                    [event.pk],
                )

    def test_catalog_snapshot_relations_do_not_require_cross_engine_foreign_keys(self):
        from management.models import (
            IgCheckoutInventoryReservation,
            IgCheckoutProposalItem,
        )

        for model, field_names in (
            (IgCheckoutProposalItem, ("product", "color_variant")),
            (IgCheckoutInventoryReservation, ("product", "color_variant")),
        ):
            for field_name in field_names:
                with self.subTest(model=model.__name__, field=field_name):
                    self.assertFalse(model._meta.get_field(field_name).db_constraint)


@skipUnless(
    connection.features.has_select_for_update,
    "requires a database with row-level SELECT FOR UPDATE",
)
class IgCheckoutProposalConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        from management.models import IgCheckoutProposal

        self.client = IgClient.get_or_create_for_sender("ig-checkout-concurrency")
        self.deal = IgDeal.objects.create(
            client=self.client,
            status=IgDeal.Status.QUOTED,
            amount=Decimal("790.00"),
            requested_payment_amount=Decimal("790.00"),
        )
        self.episode = ensure_episode_for_deal(self.deal)
        attempt = PaymentAttempt.objects.create(
            fingerprint=hashlib.sha256(b"cancelled:concurrency").hexdigest(),
            full_name="Instagram Buyer",
            phone="+380501112233",
            email="buyer@example.com",
            city="Kyiv",
            np_office="Branch 1",
            pay_type=PaymentAttempt.PayType.ONLINE_FULL,
            status=PaymentAttempt.Status.CANCELLED,
            cart_snapshot={"items": []},
            gross_amount=Decimal("790.00"),
            payable_amount=Decimal("790.00"),
            payment_amount=Decimal("790.00"),
            monobank_invoice_id="inv-cancelled-concurrency",
        )
        proposal = IgCheckoutProposal.objects.create_current(
            deal=self.deal,
            catalog_total=Decimal("790.00"),
            quoted_total=Decimal("790.00"),
            requested_payment_amount=Decimal("790.00"),
            items_digest="a" * 64,
        )
        proposal.status = IgCheckoutProposal.Status.CANCELLED
        proposal.invoice_cancelled_at = timezone.now()
        proposal.payment_attempt = attempt
        from management.models import IgPaymentEvent, IgPaymentProjection

        event = IgPaymentEvent.objects.create(
            event_key=hashlib.sha256(b"terminal:concurrency").hexdigest(),
            deal=self.deal,
            client=self.client,
            provider="monobank",
            source="provider_pull",
            invoice_id=attempt.monobank_invoice_id,
            provider_status="cancelled",
            evidence={"status": "cancelled"},
            payload_digest=hashlib.sha256(b"payload:concurrency").hexdigest(),
        )
        IgPaymentProjection.objects.create(
            deal=self.deal,
            client=self.client,
            truth=IgDeal.PaymentTruth.CANCELLED,
            last_event=event,
        )
        proposal.provider_cancellation_event = event
        proposal.save(update_fields=[
            "status",
            "invoice_cancelled_at",
            "payment_attempt",
            "provider_cancellation_event",
            "updated_at",
        ])

    def test_concurrent_replacement_creation_serializes_on_deal(self):
        from management.models import IgCheckoutProposal

        barrier = Barrier(2)
        result_lock = Lock()
        created_ids = []
        errors = []

        def replace(*, amount, digest):
            close_old_connections()
            try:
                deal = IgDeal.objects.get(pk=self.deal.pk)
                barrier.wait(timeout=10)
                replacement = IgCheckoutProposal.objects.replace_current(
                    deal=deal,
                    catalog_total=amount,
                    quoted_total=amount,
                    requested_payment_amount=amount,
                    items_digest=digest,
                )
                with result_lock:
                    created_ids.append(replacement.pk)
            except BaseException as exc:  # captured for assertion in the test thread
                with result_lock:
                    errors.append(exc)
            finally:
                close_old_connections()

        workers = [
            Thread(target=replace, kwargs={"amount": Decimal("890.00"), "digest": "e" * 64}),
            Thread(target=replace, kwargs={"amount": Decimal("990.00"), "digest": "f" * 64}),
        ]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=15)

        self.assertFalse(any(worker.is_alive() for worker in workers))
        self.assertEqual(len(created_ids), 1)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], ValidationError)
        self.assertIn("provider-confirmed", str(errors[0]))

        self.deal.refresh_from_db()
        self.assertEqual(self.deal.active_checkout_proposal_id, created_ids[0])
        self.assertEqual(self.deal.checkout_proposals.count(), 2)
