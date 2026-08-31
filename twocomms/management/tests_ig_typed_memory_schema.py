from importlib import import_module

from django.core.exceptions import ValidationError
from django.db import migrations
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from management.models import IgMemoryFact, IgMemoryFactEvidence, IgMemoryHead


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
            integrity_key_id="test-v1",
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
        }.issubset({item.name for item in IgMemoryFact._meta.constraints}))

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
