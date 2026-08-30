from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from django.db import DatabaseError, connection, migrations
from django.test import SimpleTestCase, TransactionTestCase


class CheckoutGenerationMigrationContractTests(SimpleTestCase):
    def setUp(self):
        self.migration = import_module(
            "management.migrations.0184_assisted_checkout_generation_v2"
        )

    def test_migration_is_cross_app_retry_safe_non_atomic_and_irreversible(self):
        migration = self.migration.Migration
        self.assertEqual(
            migration.dependencies,
            [
                ("management", "0183_analysis_v2_result_proposals"),
                ("orders", "0058_paymentattempt_checkout_series"),
            ],
        )
        self.assertFalse(migration.atomic)
        self.assertIsInstance(
            migration.operations[0],
            migrations.SeparateDatabaseAndState,
        )
        self.assertIsNone(migration.operations[1].reverse_code)
        self.assertIsNone(migration.operations[2].reverse_code)

    def test_named_unique_conflict_is_rejected(self):
        migration = self.migration
        model = SimpleNamespace(
            _meta=SimpleNamespace(
                db_table=migration.GENERATION_TABLE,
                get_field=lambda name: SimpleNamespace(column=f"{name}_id"),
            )
        )
        registry = Mock()
        registry.get_model.return_value = model
        editor = Mock()
        cursor = Mock()
        cursor.__enter__ = Mock(return_value=cursor)
        cursor.__exit__ = Mock(return_value=False)
        editor.connection.cursor.return_value = cursor
        editor.connection.introspection.get_constraints.return_value = {
            "ig_invgen_active_slot_uniq": {
                "unique": True,
                "columns": ["wrong"],
            }
        }
        with self.assertRaisesRegex(RuntimeError, "unique shape"):
            migration._ensure_unique_shape(
                registry,
                editor,
                (
                    "management",
                    "IgCheckoutInvoiceGeneration",
                    "ig_invgen_active_slot_uniq",
                    ("proposal", "active_slot"),
                ),
            )

    def test_mariadb_harness_is_guarded_and_covers_kill_races_and_reverse(self):
        source = (
            Path(__file__).resolve().parents[2]
            / "scripts"
            / "run_ig_checkout_generation_s2b_mariadb_retry.py"
        ).read_text(encoding="utf-8")
        for value in (
            "--confirm-disposable is required",
            "test_twocomms_checkout_s2b_",
            "KILL_EXIT_CODE = 97",
            "winner_race_ok",
            "legacy_unchanged",
            "event_update_rejected",
            "event_delete_rejected",
            "reverse_schema_preserved",
        ):
            self.assertIn(value, source)


class CheckoutGenerationTriggerTests(TransactionTestCase):
    reset_sequences = False

    def test_generation_event_update_and_delete_are_blocked(self):
        from datetime import timedelta
        from decimal import Decimal
        import hashlib

        from django.utils import timezone
        from management.models import (
            IgCheckoutInvoiceGeneration,
            IgCheckoutInvoiceGenerationEvent,
            IgCheckoutProposal,
            IgClient,
            IgCommercialEpisode,
            IgDeal,
        )

        migration = import_module(
            "management.migrations.0184_assisted_checkout_generation_v2"
        )
        client = IgClient.objects.create(igsid="checkout-generation-trigger")
        deal = IgDeal.objects.create(
            client=client,
            amount=Decimal("700.00"),
            requested_payment_amount=Decimal("700.00"),
        )
        episode = IgCommercialEpisode.objects.create(
            client=client,
            deal=deal,
            sequence=1,
            open_slot=1,
            materialization_key="checkout-generation-trigger:episode",
        )
        proposal = IgCheckoutProposal.objects.create(
            client=client,
            deal=deal,
            commercial_episode=episode,
            catalog_total=Decimal("700.00"),
            quoted_total=Decimal("700.00"),
            requested_payment_amount=Decimal("700.00"),
            items_digest="a" * 64,
            assisted_checkout_v2=True,
            payment_policy=IgCheckoutProposal.PaymentPolicy.FULL_ONLY,
            expires_at=timezone.now() + timedelta(hours=12),
        )
        generation = IgCheckoutInvoiceGeneration.objects.create(
            proposal=proposal,
            generation=1,
            series_key="b" * 64,
            proposal_revision=1,
            payment_amount=Decimal("700.00"),
            provider_call_token=hashlib.sha256(b"trigger").hexdigest(),
            expires_at=timezone.now() + timedelta(minutes=25),
        )
        event = IgCheckoutInvoiceGenerationEvent.objects.create(
            event_key="checkout-generation-trigger:event",
            generation=generation,
            proposal=proposal,
            kind=IgCheckoutInvoiceGenerationEvent.Kind.CREATED,
        )
        with connection.schema_editor() as editor:
            migration.create_generation_event_triggers(None, editor)
        try:
            with self.assertRaises(DatabaseError), connection.cursor() as cursor:
                cursor.execute(
                    f"UPDATE {migration.EVENT_TABLE} SET payload=%s WHERE id=%s",
                    ["{}", event.pk],
                )
            with self.assertRaises(DatabaseError), connection.cursor() as cursor:
                cursor.execute(
                    f"DELETE FROM {migration.EVENT_TABLE} WHERE id=%s",
                    [event.pk],
                )
        finally:
            with connection.cursor() as cursor:
                cursor.execute("DROP TRIGGER IF EXISTS ig_invgevt_no_update")
                cursor.execute("DROP TRIGGER IF EXISTS ig_invgevt_no_delete")
