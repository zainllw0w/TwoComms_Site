from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from django.db import DatabaseError, connection, migrations, models
from django.test import SimpleTestCase, TransactionTestCase
from django.utils import timezone


class AnalysisV2MigrationTests(SimpleTestCase):
    def setUp(self):
        self.migration = import_module(
            "management.migrations.0183_analysis_v2_result_proposals"
        )

    def test_migration_is_non_atomic_retry_safe_and_irreversible(self):
        migration = self.migration
        self.assertEqual(
            migration.Migration.dependencies,
            [("management", "0182_analysis_materiality_ledger")],
        )
        self.assertFalse(migration.Migration.atomic)
        self.assertIsInstance(
            migration.Migration.operations[0],
            migrations.SeparateDatabaseAndState,
        )
        self.assertIsInstance(migration.Migration.operations[1], migrations.RunPython)
        self.assertIsNone(migration.Migration.operations[1].reverse_code)
        self.assertIsNone(migration.Migration.operations[2].reverse_code)

    def test_result_mysql_triggers_are_idempotent_and_append_only(self):
        editor = Mock()
        editor.connection.vendor = "mysql"

        self.migration.create_result_append_only_triggers(Mock(), editor)

        sql = "\n".join(item.args[0] for item in editor.execute.call_args_list)
        self.assertIn("DROP TRIGGER IF EXISTS ig_anres_no_update", sql)
        self.assertIn("DROP TRIGGER IF EXISTS ig_anres_no_delete", sql)
        self.assertIn("DROP TRIGGER IF EXISTS ig_anprop_no_delete", sql)
        self.assertEqual(sql.count("SIGNAL SQLSTATE '45000'"), 3)

    def test_fresh_schema_creates_result_then_proposal_and_verifies_engines(self):
        result_model = SimpleNamespace(_meta=SimpleNamespace(db_table=self.migration.RESULT_TABLE))
        proposal_model = SimpleNamespace(_meta=SimpleNamespace(db_table=self.migration.PROPOSAL_TABLE))
        registry = Mock()
        registry.get_model.side_effect = lambda _app, name: {
            "IgConversationAnalysisResult": result_model,
            "IgAnalysisProposal": proposal_model,
        }[name]
        editor = Mock()
        editor.connection.vendor = "sqlite"
        editor.connection.introspection.table_names.return_value = []

        with patch.object(self.migration, "ensure_additive_schema") as ensure:
            self.migration.ensure_analysis_v2_schema(registry, editor)

        self.assertEqual(
            editor.create_model.call_args_list,
            [call(result_model), call(proposal_model)],
        )
        ensure.assert_called_once_with(
            registry,
            editor,
            field_specs=(),
            index_specs=(),
            constraint_specs=(),
        )

    def test_existing_partial_tables_delegate_to_structural_reconciler(self):
        result_model = SimpleNamespace(_meta=SimpleNamespace(db_table=self.migration.RESULT_TABLE))
        proposal_model = SimpleNamespace(_meta=SimpleNamespace(db_table=self.migration.PROPOSAL_TABLE))
        registry = Mock()
        registry.get_model.side_effect = lambda _app, name: {
            "IgConversationAnalysisResult": result_model,
            "IgAnalysisProposal": proposal_model,
        }[name]
        editor = Mock()
        editor.connection.vendor = "sqlite"
        editor.connection.introspection.table_names.return_value = [
            self.migration.RESULT_TABLE,
            self.migration.PROPOSAL_TABLE,
        ]

        with patch.object(self.migration, "ensure_additive_schema") as ensure, patch.object(
            self.migration, "_ensure_unique_shape"
        ) as ensure_unique:
            self.migration.ensure_analysis_v2_schema(registry, editor)

        editor.create_model.assert_not_called()
        self.assertEqual(ensure.call_args.kwargs["field_specs"], self.migration.FIELD_SPECS)
        self.assertEqual(ensure.call_args.kwargs["index_specs"], self.migration.INDEX_SPECS)
        self.assertEqual(ensure.call_args.kwargs["constraint_specs"], self.migration.CHECK_SPECS)
        self.assertEqual(ensure_unique.call_count, len(self.migration.UNIQUE_SPECS))

    def test_existing_mysql_tables_are_converted_to_innodb(self):
        result_model = SimpleNamespace(_meta=SimpleNamespace(db_table=self.migration.RESULT_TABLE))
        proposal_model = SimpleNamespace(_meta=SimpleNamespace(db_table=self.migration.PROPOSAL_TABLE))
        registry = Mock()
        registry.get_model.side_effect = lambda _app, name: {
            "IgConversationAnalysisResult": result_model,
            "IgAnalysisProposal": proposal_model,
        }[name]
        editor = Mock()
        editor.quote_name.side_effect = lambda value: f"`{value}`"
        editor.connection.vendor = "mysql"
        editor.connection.introspection.table_names.return_value = [
            self.migration.RESULT_TABLE,
            self.migration.PROPOSAL_TABLE,
        ]
        cursor = Mock()
        cursor.fetchone.side_effect = [("MyISAM",), ("MyISAM",)]
        cursor.__enter__ = Mock(return_value=cursor)
        cursor.__exit__ = Mock(return_value=False)
        editor.connection.cursor.return_value = cursor

        with patch.object(self.migration, "ensure_additive_schema"), patch.object(
            self.migration, "_ensure_unique_shape"
        ):
            self.migration.ensure_analysis_v2_schema(registry, editor)

        self.assertIn(
            call(f"ALTER TABLE `{self.migration.RESULT_TABLE}` ENGINE=InnoDB"),
            editor.execute.call_args_list,
        )
        self.assertIn(
            call(f"ALTER TABLE `{self.migration.PROPOSAL_TABLE}` ENGINE=InnoDB"),
            editor.execute.call_args_list,
        )

    def test_unique_shape_rejects_named_incompatible_constraint(self):
        constraint = models.UniqueConstraint(
            fields=["result_key"],
            name="ig_anres_result_key_uniq",
        )
        field = SimpleNamespace(column="result_key")
        model = SimpleNamespace(
            _meta=SimpleNamespace(
                db_table=self.migration.RESULT_TABLE,
                get_field=lambda _name: field,
                constraints=[constraint],
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
            "ig_anres_result_key_uniq": {
                "unique": False,
                "columns": ["wrong"],
            }
        }

        with self.assertRaisesRegex(RuntimeError, "incompatible shape"):
            self.migration._ensure_unique_shape(
                registry,
                editor,
                (
                    "management", "IgConversationAnalysisResult",
                    "ig_anres_result_key_uniq", ("result_key",),
                ),
            )

    def test_mariadb_retry_harness_is_disposable_guarded_and_targets_0183(self):
        source = (
            Path(__file__).resolve().parents[2]
            / "scripts"
            / "run_ig_analysis_v2_0183_mariadb_retry.py"
        ).read_text(encoding="utf-8")
        self.assertIn("--confirm-disposable is required", source)
        self.assertIn("test_settings_mariadb", source)
        self.assertIn("^test_twocomms_", source)
        self.assertIn("0183_analysis_v2_result_proposals", source)
        self.assertIn("KILL_EXIT_CODE = 97", source)


class AnalysisV2TriggerDatabaseTests(TransactionTestCase):
    reset_sequences = False

    def test_result_update_and_both_deletes_are_blocked_but_status_update_works(self):
        migration = import_module(
            "management.migrations.0183_analysis_v2_result_proposals"
        )
        from management.models import (
            IgAnalysisProposal,
            IgClient,
            IgConversationAnalysisResult,
            IgConversationAnalysisSnapshot,
        )

        client = IgClient.objects.create(igsid="analysis-v2-trigger")
        snapshot = IgConversationAnalysisSnapshot.objects.create(
            client=client,
            dedupe_key="analysis-v2-trigger:snapshot",
            score_band=IgConversationAnalysisSnapshot.Band.COLD,
        )
        result = IgConversationAnalysisResult.objects.create(
            result_key="analysis-v2-trigger:result",
            legacy_snapshot=snapshot,
            client=client,
            watermark_message_id=1,
            job_revision=1,
            materiality_event_highwater=1,
            materiality_digest="a" * 64,
            state_correlation="b" * 64,
            result_schema_version="analysis-v2.1",
            normalizer_version="analysis-v2-normalizer.1",
            score_band=IgConversationAnalysisSnapshot.Band.COLD,
            result_digest="c" * 64,
            analyzed_at=timezone.now(),
        )
        proposal = IgAnalysisProposal.objects.create(
            proposal_key="analysis-v2-trigger:proposal",
            analysis_result=result,
            ordinal=1,
            client=client,
            proposal_type=IgAnalysisProposal.ProposalType.REQUEST_CLARIFICATION,
            target_scope=IgAnalysisProposal.TargetScope.CLIENT,
            typed_value={"reason_codes": ["product_conflict"]},
            evidence_message_ids=[1],
            confidence="1.0000",
            source_result_digest=result.result_digest,
            expected_materiality_digest=result.materiality_digest,
            expected_state_correlation=result.state_correlation,
        )
        with connection.schema_editor() as editor:
            migration.create_result_append_only_triggers(None, editor)
        try:
            with self.assertRaises(DatabaseError), connection.cursor() as cursor:
                cursor.execute(
                    f"UPDATE {migration.RESULT_TABLE} SET score_band=%s WHERE id=%s",
                    ["qualified", result.pk],
                )
            with connection.cursor() as cursor:
                cursor.execute(
                    f"UPDATE {migration.PROPOSAL_TABLE} SET status=%s WHERE id=%s",
                    ["shadow_validated", proposal.pk],
                )
            proposal.refresh_from_db()
            self.assertEqual(proposal.status, "shadow_validated")
            with self.assertRaises(DatabaseError), connection.cursor() as cursor:
                cursor.execute(
                    f"DELETE FROM {migration.PROPOSAL_TABLE} WHERE id=%s",
                    [proposal.pk],
                )
            with self.assertRaises(DatabaseError), connection.cursor() as cursor:
                cursor.execute(
                    f"DELETE FROM {migration.RESULT_TABLE} WHERE id=%s",
                    [result.pk],
                )
        finally:
            with connection.cursor() as cursor:
                for name in (
                    "ig_anres_no_update",
                    "ig_anres_no_delete",
                    "ig_anprop_no_delete",
                ):
                    cursor.execute(f"DROP TRIGGER IF EXISTS {name}")
