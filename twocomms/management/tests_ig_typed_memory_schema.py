from importlib import import_module
from unittest.mock import patch

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import connection, migrations
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from management.models import IgMemoryFact, IgMemoryFactEvidence, IgMemoryHead
from management.tests_support import AnalysisPrivacyCleanupMixin


class TypedMemorySchemaTests(TestCase):
    def test_schema_has_no_free_text_or_forbidden_business_truth(self):
        fact_fields = {field.name for field in IgMemoryFact._meta.get_fields()}
        self.assertFalse(fact_fields & {
            "text", "quote", "summary", "phone", "email", "address",
            "payment", "order_status", "price", "stock", "discount", "reminder",
            "provider_body", "key_alias",
        })
        self.assertTrue({
            "record_key", "slot_key", "fact_key", "typed_value", "supersedes",
            "producer_policy_version", "closure_method", "integrity_hmac",
        }.issubset(fact_fields))

    def test_append_only_managers_reject_bulk_and_head_shortcuts(self):
        bad = IgMemoryFact(
            record_key="memory-fact:" + "a" * 64,
            slot_key="memory-slot:" + "b" * 64,
            client_id=1,
            scope="client",
            fact_key="observed_language",
            operation="assert",
            typed_value={"phone": "+380501234567"},
            source_role="user",
            producer="analysis_v2",
            closure_method="analysis_assertion",
            source_result_id=1,
            source_result_digest="c" * 64,
            source_materiality_digest="d" * 64,
            source_state_correlation="e" * 64,
            source_watermark_message_id=1,
            expected_evidence_count=1,
            integrity_hmac="f" * 64,
            integrity_key_id="tmk_test_v1",
            observed_at=timezone.now(),
            sensitivity="low",
            retention_class="client",
        )
        with self.assertRaises(ValidationError):
            IgMemoryFact._base_manager.bulk_create([bad])
        with self.assertRaisesRegex(ValueError, "locked projector"):
            IgMemoryHead.objects.update(state="active")
        with self.assertRaisesRegex(ValueError, "append-only"):
            IgMemoryFactEvidence.objects.update(source_role="manager")

    def test_declared_constraints_and_indexes_are_complete(self):
        self.assertEqual(
            {item.name for item in IgMemoryFact._meta.indexes},
            {
                "ig_memfact_client_obs", "ig_memfact_slot_id",
                "ig_memfact_result_key", "ig_memfact_valid_until",
            },
        )
        self.assertTrue({
            "ig_memfact_record_uniq", "ig_memfact_supersedes_uniq",
            "ig_memfact_scope_shape", "ig_memfact_source_shape",
            "ig_memfact_policy_shape",
        }.issubset({item.name for item in IgMemoryFact._meta.constraints}))
        self.assertIn(
            "ig_memhead_revision_bounds",
            {item.name for item in IgMemoryHead._meta.constraints},
        )

    def test_analysis_digest_is_version_aware_for_historical_v21_rows(self):
        from management.services import ig_analysis_v2

        base = {
            "result_schema_version": "analysis-v2.1",
            "detected_language": "uk",
            "language_evidence_message_ids": [],
        }
        old_digest = ig_analysis_v2.result_digest_for_values(base)
        changed_language_ids = ig_analysis_v2.result_digest_for_values({
            **base,
            "language_evidence_message_ids": [123],
        })
        self.assertEqual(old_digest, changed_language_ids)
        self.assertNotEqual(
            ig_analysis_v2.result_digest_for_values({
                **base,
                "result_schema_version": "analysis-v2.2",
            }),
            ig_analysis_v2.result_digest_for_values({
                **base,
                "result_schema_version": "analysis-v2.2",
                "language_evidence_message_ids": [123],
            }),
        )


class TypedMemoryMigrationContractTests(SimpleTestCase):
    def test_0185_is_non_atomic_resumable_irreversible_and_after_0184(self):
        migration = import_module("management.migrations.0185_typed_memory_v2")
        self.assertFalse(migration.Migration.atomic)
        self.assertEqual(
            migration.Migration.dependencies,
            [("management", "0184_assisted_checkout_generation_v2")],
        )
        self.assertIsInstance(
            migration.Migration.operations[0],
            migrations.SeparateDatabaseAndState,
        )
        self.assertTrue(all(
            operation.reverse_code is None
            for operation in migration.Migration.operations[1:]
        ))
        self.assertEqual(
            {migration.FACT_TABLE, migration.EVIDENCE_TABLE, migration.HEAD_TABLE},
            {
                "management_igmemoryfact",
                "management_igmemoryfactevidence",
                "management_igmemoryhead",
            },
        )

    def test_engine_registry_and_arbitrary_kill_harness_are_declared(self):
        from pathlib import Path
        from management.services.ig_engine_health import IG_RUNTIME_TABLES

        self.assertTrue({
            "management_igmemoryfact",
            "management_igmemoryfactevidence",
            "management_igmemoryhead",
        }.issubset(IG_RUNTIME_TABLES))
        source = (
            Path(__file__).resolve().parents[2]
            / "scripts" / "run_ig_typed_memory_0185_mariadb_retry.py"
        ).read_text(encoding="utf-8")
        self.assertIn("--kill-after", source)
        self.assertIn("--confirm-disposable is required", source)
        self.assertIn("KILL_EXIT_CODE = 97", source)
        self.assertIn("0185_typed_memory_v2", source)

    def test_every_guarded_transaction_owner_uses_shared_privacy_cleanup(self):
        from management.tests_ig_analysis_materiality import (
            MaterialityConcurrencyTests,
        )
        from management.tests_ig_analysis_v2_migration import (
            AnalysisV2TriggerDatabaseTests,
        )
        from management.tests_ig_typed_memory_mariadb import (
            TypedMemoryMariaConcurrencyTests,
        )

        for test_case in (
            MaterialityConcurrencyTests,
            AnalysisV2TriggerDatabaseTests,
            TypedMemoryMariaConcurrencyTests,
            TypedMemoryPhysicalContractTests,
        ):
            self.assertTrue(issubclass(test_case, AnalysisPrivacyCleanupMixin))

    @override_settings(
        IG_TYPED_MEMORY_MODE="shadow_compare",
        IG_ANALYSIS_V2_MODE="off",
        IG_ANALYSIS_MATERIALITY_MODE="off",
        IG_ANALYSIS_V2_EXTENDED_PROMPT=False,
        IG_TYPED_MEMORY_HMAC_KEYRING={},
        IG_TYPED_MEMORY_HMAC_ACTIVE_KEY_ID="",
    )
    def test_shadow_system_check_fails_closed_without_dependencies(self):
        from management.checks import typed_memory_shadow_check

        self.assertEqual(
            {item.id for item in typed_memory_shadow_check()},
            {"management.E920", "management.E921"},
        )

    @override_settings(
        IG_TYPED_MEMORY_MODE="shadow_compare",
        IG_ANALYSIS_V2_MODE="shadow",
        IG_ANALYSIS_MATERIALITY_MODE="shadow",
        IG_ANALYSIS_V2_EXTENDED_PROMPT=True,
        IG_TYPED_MEMORY_HMAC_ACTIVE_KEY_ID="tmk_good_v1",
        IG_TYPED_MEMORY_HMAC_KEYRING={
            "tmk_good_v1": "a" * 32,
            "bad retained id": "b" * 32,
        },
    )
    def test_invalid_retained_key_id_disables_shadow_and_fails_system_check(self):
        from management.checks import typed_memory_shadow_check
        from management.services import ig_typed_memory

        self.assertFalse(ig_typed_memory.shadow_enabled())
        self.assertIn("retained_key_id_invalid", ig_typed_memory._keyring_configuration()[2])
        self.assertEqual(
            {item.id for item in typed_memory_shadow_check()},
            {"management.E921"},
        )

    @override_settings(
        IG_TYPED_MEMORY_MODE="shadow_compare",
        IG_ANALYSIS_V2_MODE="shadow",
        IG_ANALYSIS_MATERIALITY_MODE="shadow",
        IG_ANALYSIS_V2_EXTENDED_PROMPT=True,
        IG_TYPED_MEMORY_HMAC_ACTIVE_KEY_ID="invalid active",
        IG_TYPED_MEMORY_HMAC_KEYRING={"tmk_good_v1": "a" * 32},
    )
    def test_invalid_active_key_id_disables_shadow(self):
        from management.checks import typed_memory_shadow_check
        from management.services import ig_typed_memory

        self.assertFalse(ig_typed_memory.shadow_enabled())
        self.assertIn("active_key_id_invalid", ig_typed_memory._keyring_configuration()[2])
        self.assertEqual(
            {item.id for item in typed_memory_shadow_check()},
            {"management.E921"},
        )


class TypedMemoryPhysicalContractTests(AnalysisPrivacyCleanupMixin, TransactionTestCase):
    reset_sequences = False

    def _require_migration_profile(self):
        if connection.vendor != "sqlite":
            self.skipTest("SQLite adversarial schema proof")
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM sqlite_master "
                "WHERE type='trigger' AND name='ig_memfact_insert_guard'"
            )
            if not cursor.fetchone()[0]:
                self.skipTest("requires migration-enabled SQLite profile")

    def test_same_name_noop_trigger_fails_closed_and_exact_trigger_restores(self):
        self._require_migration_profile()
        migration = import_module("management.migrations.0185_typed_memory_v2")
        with connection.cursor() as cursor:
            cursor.execute("DROP TRIGGER ig_memfact_no_update")
            cursor.execute(
                "CREATE TRIGGER ig_memfact_no_update BEFORE UPDATE ON "
                "management_igmemoryfact BEGIN SELECT 1; END"
            )
        try:
            with connection.schema_editor() as editor:
                with self.assertRaisesRegex(RuntimeError, "body mismatch"):
                    migration.install_typed_memory_and_privacy_triggers(apps, editor)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("DROP TRIGGER IF EXISTS ig_memfact_no_update")
            with connection.schema_editor() as editor:
                migration.install_typed_memory_and_privacy_triggers(apps, editor)

    def test_weakened_same_name_check_predicate_fails_exact_comparison(self):
        self._require_migration_profile()
        migration = import_module("management.migrations.0185_typed_memory_v2")
        with connection.schema_editor() as editor, patch.object(
            migration,
            "_physical_check_clause",
            return_value="confidence IS NULL OR confidence >= 0",
        ):
            with self.assertRaisesRegex(RuntimeError, "physical predicate"):
                migration._validate_check(
                    apps,
                    editor,
                    ("management", "IgMemoryFact", "ig_memfact_conf_range"),
                )

    def test_partial_or_expression_unique_cannot_impersonate_named_constraint(self):
        self._require_migration_profile()
        migration = import_module("management.migrations.0185_typed_memory_v2")
        quote = connection.ops.quote_name
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE tm_mem_unique_good (a INTEGER, b INTEGER, "
                "CONSTRAINT tm_mem_exact UNIQUE (a, b))"
            )
            cursor.execute("CREATE TABLE tm_mem_unique_bad (a INTEGER, b INTEGER)")
            cursor.execute(
                "CREATE UNIQUE INDEX tm_mem_exact_bad ON tm_mem_unique_bad(a, b) "
                "WHERE a > 0"
            )
        try:
            with connection.schema_editor() as editor:
                migration._validate_physical_unique(
                    editor, "tm_mem_unique_good", "tm_mem_exact", ("a", "b")
                )
                with self.assertRaisesRegex(RuntimeError, "named table UNIQUE"):
                    migration._validate_physical_unique(
                        editor,
                        "tm_mem_unique_bad",
                        "tm_mem_exact_bad",
                        ("a", "b"),
                    )
        finally:
            with connection.cursor() as cursor:
                cursor.execute(f"DROP TABLE IF EXISTS {quote('tm_mem_unique_bad')}")
                cursor.execute(f"DROP TABLE IF EXISTS {quote('tm_mem_unique_good')}")
