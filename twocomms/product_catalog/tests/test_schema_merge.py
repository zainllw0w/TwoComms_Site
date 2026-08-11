from types import SimpleNamespace

from django.test import SimpleTestCase
from django.core.management.base import CommandError

from product_catalog.management.commands.merge_product_catalog_schema import (
    _validate_snapshot_identity,
)
from product_catalog.schema_merge import compare_rows, dependency_order


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
            {"id": 1, "source": "warehouse", "updated_at": 1},
            {"id": 3, "source": "untracked", "updated_at": 3},
        ]
        current = [
            {"id": 1, "source": "untracked", "updated_at": 2},
            {"id": 2, "source": "untracked", "updated_at": 2},
        ]

        result = compare_rows(old, current, ("id", "source", "updated_at"))

        self.assertEqual(result["missing_ids"], [3])
        self.assertEqual(result["current_only_ids"], [2])
        self.assertEqual(result["update_ids"], [1])
        self.assertEqual(result["update_columns"], {"1": ["source", "updated_at"]})

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
