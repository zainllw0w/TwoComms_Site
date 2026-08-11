from types import SimpleNamespace

from django.test import SimpleTestCase
from django.core.management.base import CommandError

import product_catalog.schema_merge as schema_merge

from product_catalog.management.commands.merge_product_catalog_schema import (
    _has_pre_drop_verification,
    _validate_snapshot_identity,
)
from product_catalog.schema_merge import compare_rows, dependency_order
from product_catalog.models import ProductAudience, ProductOptionProfileI18n


class SchemaMergePlanTests(SimpleTestCase):
    def _snapshot(self):
        return {
            "phase": "preflight",
            "expected_database": "catalog_db",
            "expected_sha": "a" * 40,
            "legacy_table_prefix": "retired_catalog",
            "legacy_app_label": "retired_catalog",
            "preflight": {
                "current_app_label": "product_catalog",
                "legacy_table_prefix": "retired_catalog",
                "order": ["product_catalog_audiencetag"],
                "pairs": [
                    {
                        "model_label": "product_catalog.AudienceTag",
                        "current_table": "product_catalog_audiencetag",
                        "legacy_table": "retired_catalog_audiencetag",
                    }
                ],
            },
        }

    def _options(self):
        return {
            "expected_database": "catalog_db",
            "expected_sha": "a" * 40,
            "legacy_table_prefix": "retired_catalog",
            "legacy_app_label": "retired_catalog",
        }

    def test_compare_rows_marks_legacy_rows_for_insert_and_authoritative_updates(self):
        old = [
            {"id": 1, "product_id": 1, "source": "warehouse", "updated_at": 1},
            {"id": 3, "product_id": 3, "source": "untracked", "updated_at": 3},
        ]
        current = [
            {"id": 1, "product_id": 1, "source": "untracked", "updated_at": 2},
            {"id": 2, "product_id": 2, "source": "untracked", "updated_at": 2},
        ]

        result = compare_rows(
            old,
            current,
            ("id", "product_id", "source", "updated_at"),
            unique_keys=(("product_id",),),
        )

        self.assertEqual(result["missing_ids"], [3])
        self.assertEqual(result["current_only_ids"], [2])
        self.assertEqual(result["update_ids"], [1])
        self.assertEqual(result["update_columns"], {"1": ["source", "updated_at"]})

    def test_compare_rows_rekeys_a_colliding_surrogate_id_for_a_distinct_unique_row(self):
        legacy = [
            {"id": 1, "product_id": 1, "tag_id": 1, "note": ""},
            {"id": 2, "product_id": 2, "tag_id": 1, "note": ""},
        ]
        current = [
            {"id": 1, "product_id": 98, "tag_id": 1, "note": ""},
        ]

        result = compare_rows(
            legacy,
            current,
            ("id", "product_id", "tag_id", "note"),
            unique_keys=(("product_id", "tag_id"),),
            strict_conflicts=True,
        )

        self.assertEqual(result["missing_ids"], [1, 2])
        self.assertEqual(result["pk_map"], {"1": 3, "2": 2})
        self.assertEqual(result["current_only_ids"], [1])
        self.assertEqual(result["conflicts"], [])

    def test_compare_rows_maps_a_natural_match_and_targets_authoritative_update(self):
        legacy = [{"id": 1, "product_id": 7, "source": "warehouse"}]
        current = [{"id": 9, "product_id": 7, "source": "untracked"}]

        result = compare_rows(
            legacy,
            current,
            ("id", "product_id", "source"),
            unique_keys=(("product_id",),),
            authoritative_columns=("source",),
            strict_conflicts=True,
        )

        self.assertEqual(result["missing_ids"], [])
        self.assertEqual(result["pk_map"], {"1": 9})
        self.assertEqual(result["update_ids"], [1])
        self.assertEqual(result["update_target_ids"], {"1": 9})
        self.assertEqual(result["update_columns"], {"1": ["source"]})
        self.assertEqual(result["conflicts"], [])

    def test_compare_rows_preserves_both_rows_when_no_natural_key_exists(self):
        legacy = [{"id": 1, "payload": "legacy"}]
        current = [{"id": 1, "payload": "current"}]

        result = compare_rows(
            legacy,
            current,
            ("id", "payload"),
            strict_conflicts=True,
        )

        self.assertEqual(result["missing_ids"], [1])
        self.assertEqual(result["pk_map"], {"1": 2})
        self.assertEqual(result["current_only_ids"], [1])
        self.assertEqual(result["conflicts"], [])

    def test_compare_rows_rejects_natural_keys_pointing_to_different_rows(self):
        legacy = [{"id": 1, "left": "a", "right": "b"}]
        current = [
            {"id": 7, "left": "a", "right": "x"},
            {"id": 8, "left": "y", "right": "b"},
        ]

        with self.assertRaisesMessage(
            schema_merge.SchemaMergeError,
            "matches multiple current natural keys",
        ):
            compare_rows(
                legacy,
                current,
                ("id", "left", "right"),
                unique_keys=(("left",), ("right",)),
                strict_conflicts=True,
            )

    def test_remap_rows_applies_own_and_parent_primary_key_maps(self):
        rows = [{"id": 1, "profile_id": 2, "lang": "uk"}]

        remapped = schema_merge.remap_rows(
            rows,
            primary_key="id",
            primary_key_map={"1": 10},
            foreign_key_maps={"profile_id": {"2": 20}},
        )

        self.assertEqual(
            remapped,
            [{"id": 10, "profile_id": 20, "lang": "uk"}],
        )

    def test_model_metadata_exposes_unique_and_internal_relation_keys(self):
        self.assertIn(
            ("product_id", "tag_id"),
            schema_merge.model_unique_keys(ProductAudience),
        )
        maps = schema_merge.model_foreign_key_maps(
            ProductOptionProfileI18n,
            legacy_table_prefix="retired_catalog",
            primary_key_maps={
                "retired_catalog_productoptionprofile": {"2": 20},
            },
        )

        self.assertEqual(maps, {"profile_id": {"2": 20}})

    def test_rows_digest_is_order_independent_and_detects_protected_changes(self):
        rows = [
            {"id": 2, "value": "b", "updated_at": "later"},
            {"id": 1, "value": "a", "updated_at": "earlier"},
        ]

        digest = schema_merge.rows_digest(
            rows,
            columns=("id", "value"),
            primary_key="id",
        )

        self.assertEqual(
            digest,
            schema_merge.rows_digest(
                list(reversed(rows)),
                columns=("id", "value"),
                primary_key="id",
            ),
        )
        self.assertNotEqual(
            digest,
            schema_merge.rows_digest(
                [{"id": 1, "value": "changed"}, {"id": 2, "value": "b"}],
                columns=("id", "value"),
                primary_key="id",
            ),
        )

    def test_self_referencing_rows_are_ordered_parent_before_child(self):
        rows = [
            {"id": 1, "parent_id": 2},
            {"id": 2, "parent_id": None},
        ]

        ordered = schema_merge.order_self_referencing_rows(
            rows,
            primary_key="id",
            parent_columns=("parent_id",),
            existing_ids=(),
        )

        self.assertEqual([row["id"] for row in ordered], [2, 1])

    def test_self_referencing_rows_reject_a_cycle(self):
        rows = [
            {"id": 1, "parent_id": 2},
            {"id": 2, "parent_id": 1},
        ]

        with self.assertRaisesMessage(
            schema_merge.SchemaMergeError,
            "self-reference cycle",
        ):
            schema_merge.order_self_referencing_rows(
                rows,
                primary_key="id",
                parent_columns=("parent_id",),
                existing_ids=(),
            )

    def test_dependency_order_places_parents_before_children(self):
        class Introspection:
            def get_constraints(self, _cursor, table):
                if table == "product_catalog_child":
                    return {"fk_parent": {"foreign_key": ("product_catalog_parent", "id")}}
                return {}

        connection = SimpleNamespace(
            introspection=Introspection(),
            cursor=lambda: SimpleNamespace(__enter__=lambda self: self, __exit__=lambda *args: False),
        )
        pairs = [
            {"current_table": "product_catalog_child"},
            {"current_table": "product_catalog_parent"},
        ]

        self.assertEqual(
            dependency_order(connection, pairs),
            ["product_catalog_parent", "product_catalog_child"],
        )

    def test_snapshot_identity_rejects_another_database(self):
        options = self._options()
        options["expected_database"] = "other_db"

        with self.assertRaisesMessage(CommandError, "expected_database"):
            _validate_snapshot_identity(self._snapshot(), options)

    def test_snapshot_identity_rejects_unknown_phase(self):
        snapshot = self._snapshot()
        snapshot["phase"] = "drop-everything"

        with self.assertRaisesMessage(CommandError, "unsupported merge snapshot phase"):
            _validate_snapshot_identity(snapshot, self._options())

    def test_snapshot_identity_rejects_unsafe_table_pair(self):
        snapshot = self._snapshot()
        snapshot["preflight"]["pairs"][0]["legacy_table"] = "unrelated_table"

        with self.assertRaisesMessage(CommandError, "unsafe legacy table"):
            _validate_snapshot_identity(snapshot, self._options())

    def test_snapshot_identity_rejects_duplicate_table_pairs(self):
        snapshot = self._snapshot()
        snapshot["preflight"]["pairs"].append(
            dict(snapshot["preflight"]["pairs"][0])
        )
        snapshot["preflight"]["order"].append("product_catalog_audiencetag")

        with self.assertRaisesMessage(CommandError, "duplicate table pairs"):
            _validate_snapshot_identity(snapshot, self._options())

    def test_snapshot_identity_rejects_late_phase_without_post_merge_evidence(self):
        snapshot = self._snapshot()
        snapshot["phase"] = "metadata-remapped"

        with self.assertRaisesMessage(CommandError, "missing post_merge evidence"):
            _validate_snapshot_identity(snapshot, self._options())

    def test_snapshot_identity_rejects_drop_resume_without_pre_drop_verification(self):
        snapshot = self._snapshot()
        snapshot["phase"] = "legacy-tables-dropped"
        snapshot["post_merge"] = {
            "order": ["product_catalog_audiencetag"],
            "pairs": [
                {
                    "current_table": "product_catalog_audiencetag",
                    "comparison": {
                        "missing_ids": [],
                        "update_ids": [],
                        "conflicts": [],
                    },
                }
            ],
        }
        snapshot["metadata"] = {}
        snapshot["migration_rows_deleted"] = 1

        with self.assertRaisesMessage(CommandError, "pre-drop verification"):
            _validate_snapshot_identity(snapshot, self._options())

    def test_metadata_resume_requires_pre_drop_evidence_before_cleanup(self):
        snapshot = self._snapshot()
        snapshot["phase"] = "migration-metadata-removed"
        snapshot["post_merge"] = {
            "order": ["product_catalog_audiencetag"],
            "pairs": [{"current_table": "product_catalog_audiencetag"}],
        }
        snapshot["metadata"] = {}
        snapshot["migration_rows_deleted"] = 1

        self.assertFalse(_has_pre_drop_verification(snapshot))
        snapshot["pre_drop_verification"] = {
            "pairs": [{"current_table": "product_catalog_audiencetag"}],
        }
        self.assertTrue(_has_pre_drop_verification(snapshot))
