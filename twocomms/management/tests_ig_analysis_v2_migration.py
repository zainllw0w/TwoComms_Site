from importlib import import_module
import hashlib
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
        self.assertIn("DROP TRIGGER IF EXISTS ig_anprop_identity_update", sql)
        self.assertIn("DROP TRIGGER IF EXISTS ig_anres_insert_guard", sql)
        self.assertIn("DROP TRIGGER IF EXISTS ig_anprop_insert_guard", sql)
        self.assertEqual(sql.count("SIGNAL SQLSTATE '45000'"), 6)

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

    def test_mariadb_tinyint_one_is_the_only_integer_boolean_shape(self):
        from management.migrations._resumable_schema import _validate_field

        editor = Mock()
        editor.connection.vendor = "mysql"
        editor.connection.introspection.get_field_type.return_value = "IntegerField"
        field = models.BooleanField(default=False)
        field.set_attributes_from_name("has_conflicts")
        column = SimpleNamespace(
            type_code=1,
            null_ok=False,
            internal_size=1,
        )

        _validate_field(editor, self.migration.RESULT_TABLE, field, column)
        column.internal_size = 4
        with self.assertRaisesRegex(RuntimeError, "expected BooleanField"):
            _validate_field(editor, self.migration.RESULT_TABLE, field, column)

    def test_partial_one_to_one_validates_its_physical_target_type(self):
        from management.migrations._resumable_schema import _validate_field

        editor = Mock()
        editor.connection.vendor = "mysql"
        editor.connection.introspection.get_field_type.return_value = "BigIntegerField"
        field = SimpleNamespace(
            column="legacy_snapshot_id",
            null=False,
            max_length=None,
            is_relation=True,
            many_to_one=False,
            one_to_one=True,
            target_field=SimpleNamespace(
                get_internal_type=lambda: "BigAutoField"
            ),
        )
        column = SimpleNamespace(
            type_code=8,
            null_ok=False,
            internal_size=None,
        )

        _validate_field(editor, self.migration.RESULT_TABLE, field, column)
        editor.connection.introspection.get_field_type.return_value = "CharField"
        with self.assertRaisesRegex(RuntimeError, "expected BigAutoField"):
            _validate_field(editor, self.migration.RESULT_TABLE, field, column)

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
            result_key="analysis-v2:" + hashlib.sha256(b"trigger-result").hexdigest(),
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
            proposal_key="analysis-proposal:" + hashlib.sha256(b"trigger-proposal").hexdigest(),
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
            valid_payloads = (
                (IgAnalysisProposal.ProposalType.CLOSE_NODE, {}),
                (IgAnalysisProposal.ProposalType.INVALIDATE_NODE, {}),
                (IgAnalysisProposal.ProposalType.OPEN_SUBFUNNEL, {}),
                (IgAnalysisProposal.ProposalType.SWITCH_ACTIVE_LINE, {}),
                (
                    IgAnalysisProposal.ProposalType.START_REPEAT_EPISODE,
                    {"repeat_kind": "reorder"},
                ),
                (
                    IgAnalysisProposal.ProposalType.RECORD_OBJECTION,
                    {"objection_type": "price"},
                ),
                (
                    IgAnalysisProposal.ProposalType.RECORD_DEFERRED_INTENT,
                    {
                        "kind": "payday",
                        "condition_code": "payday",
                        "deferred_until": "",
                    },
                ),
                (
                    IgAnalysisProposal.ProposalType.UPDATE_PROBABILITY,
                    {"probability": "0.5000", "basis": "customer_evidence"},
                ),
            )
            for ordinal, (proposal_type, typed_value) in enumerate(
                valid_payloads,
                start=2,
            ):
                IgAnalysisProposal.objects.create(
                    proposal_key=(
                        "analysis-proposal:"
                        + hashlib.sha256(
                            f"valid-trigger-{proposal_type}".encode()
                        ).hexdigest()
                    ),
                    analysis_result=result,
                    ordinal=ordinal,
                    client=client,
                    proposal_type=proposal_type,
                    target_scope=IgAnalysisProposal.TargetScope.CLIENT,
                    typed_value=typed_value,
                    evidence_message_ids=[1],
                    confidence="1.0000",
                    source_result_digest=result.result_digest,
                    expected_materiality_digest=result.materiality_digest,
                    expected_state_correlation=result.state_correlation,
                )

            def raw_clone_insert(instance, **overrides):
                fields = [
                    field for field in instance._meta.local_fields
                    if not field.primary_key
                ]
                columns = ", ".join(
                    connection.ops.quote_name(field.column) for field in fields
                )
                values = []
                for field in fields:
                    value = overrides.get(
                        field.attname,
                        field.value_from_object(instance),
                    )
                    values.append(field.get_db_prep_save(value, connection))
                placeholders = ", ".join(["%s"] * len(values))
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"INSERT INTO {connection.ops.quote_name(instance._meta.db_table)} "
                        f"({columns}) VALUES ({placeholders})",
                        values,
                    )

            pii_snapshot = IgConversationAnalysisSnapshot.objects.create(
                client=client,
                dedupe_key="analysis-v2-trigger:pii-snapshot",
                score_band=IgConversationAnalysisSnapshot.Band.COLD,
            )
            with self.assertRaisesRegex(DatabaseError, "insert guard"):
                raw_clone_insert(
                    result,
                    result_key=(
                        "analysis-v2:"
                        + hashlib.sha256(b"raw-pii-result").hexdigest()
                    ),
                    legacy_snapshot_id=pii_snapshot.pk,
                    evidence_manifest=[{
                        "message_id": 1,
                        "source_role": "user",
                        "claim_codes": ["interaction"],
                        "quote": "Call +380501234567 or customer@example.com",
                    }],
                    customer_evidence_count=1,
                )
            identity_snapshot = IgConversationAnalysisSnapshot.objects.create(
                client=client,
                dedupe_key="analysis-v2-trigger:identity-snapshot",
                score_band=IgConversationAnalysisSnapshot.Band.COLD,
            )
            with self.assertRaisesRegex(DatabaseError, "insert guard"):
                raw_clone_insert(
                    result,
                    result_key="analysis-v2:not-a-digest",
                    legacy_snapshot_id=identity_snapshot.pk,
                    job_revision=10,
                )
            with self.assertRaisesRegex(DatabaseError, "insert guard"):
                raw_clone_insert(
                    proposal,
                    proposal_key=(
                        "analysis-proposal:"
                        + hashlib.sha256(b"raw-pii-proposal").hexdigest()
                    ),
                    ordinal=12,
                    typed_value={
                        "reason_codes": ["product_conflict"],
                        "phone": "+380501234567",
                    },
                )
            with self.assertRaisesRegex(DatabaseError, "insert guard"):
                raw_clone_insert(
                    proposal,
                    proposal_key="analysis-proposal:not-a-digest",
                    ordinal=11,
                )
            for offset, (basis, interaction, claim) in enumerate((
                ("deterministic_no_buy", "explicit_no_buy", "explicit_no_buy"),
                ("deterministic_opt_out", "opt_out", "opt_out"),
            ), start=3):
                terminal_snapshot = IgConversationAnalysisSnapshot.objects.create(
                    client=client,
                    dedupe_key=f"analysis-v2-trigger:terminal-{offset}",
                    score_band=IgConversationAnalysisSnapshot.Band.COLD,
                )
                with self.assertRaisesRegex(DatabaseError, "insert guard"):
                    raw_clone_insert(
                        result,
                        result_key=(
                            "analysis-v2:"
                            + hashlib.sha256(f"raw-{basis}".encode()).hexdigest()
                        ),
                        legacy_snapshot_id=terminal_snapshot.pk,
                        job_revision=offset,
                        interaction_type=interaction,
                        score_band=(
                            IgConversationAnalysisSnapshot.Band.OPTED_OUT
                            if interaction == "opt_out"
                            else IgConversationAnalysisSnapshot.Band.LOST
                        ),
                        purchase_probability="0.0000",
                        purchase_confidence="1.0000",
                        probability_basis=basis,
                        evidence_manifest=[{
                            "message_id": offset,
                            "source_role": "user",
                            "claim_codes": ["interaction"],
                        }],
                        customer_evidence_count=1,
                    )
            with self.assertRaises(DatabaseError), connection.cursor() as cursor:
                cursor.execute(
                    f"UPDATE {migration.RESULT_TABLE} SET score_band=%s WHERE id=%s",
                    ["qualified", result.pk],
                )
            decided_at = timezone.now()
            with connection.cursor() as cursor:
                cursor.execute(
                    f"UPDATE {migration.PROPOSAL_TABLE} "
                    "SET status=%s, decision_code=%s, projector_version=%s, "
                    "decided_at=%s, updated_at=%s WHERE id=%s",
                    [
                        "shadow_validated", "shadow_valid",
                        "analysis-v2-projector.1", decided_at, decided_at,
                        proposal.pk,
                    ],
                )
            proposal.refresh_from_db()
            self.assertEqual(proposal.status, "shadow_validated")
            self.assertEqual(proposal.decision_code, "shadow_valid")
            self.assertEqual(proposal.projector_version, "analysis-v2-projector.1")
            with self.assertRaises(DatabaseError), connection.cursor() as cursor:
                cursor.execute(
                    f"UPDATE {migration.PROPOSAL_TABLE} SET typed_value=%s WHERE id=%s",
                    ['{"reason_codes":["recipient_conflict"]}', proposal.pk],
                )
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
            # This test explicitly reinstalls the retired 0183 unconditional
            # guards. Remove only those test-owned legacy objects first; the
            # 0185 privacy-fenced production guards remain installed.
            with connection.cursor() as cursor:
                for name in (
                    "ig_anres_no_delete",
                    "ig_anprop_no_delete",
                ):
                    cursor.execute(f"DROP TRIGGER IF EXISTS {name}")
            typed_memory_migration = import_module(
                "management.migrations.0185_typed_memory_v2"
            )
            with connection.schema_editor() as editor:
                typed_memory_migration.reinstall_analysis_v22_insert_guard(
                    None, editor
                )
            # Migration-enabled TransactionTestCase cleanup then uses the same
            # committed fence and shared purge path as runtime erasure before
            # sqlflush runs.
            from management.services.ig_typed_memory import (
                purge_client_analysis_memory,
            )

            IgClient.objects.filter(pk=client.pk).update(
                privacy_erasure_started_at=timezone.now()
            )
            purge_client_analysis_memory([client.pk])
