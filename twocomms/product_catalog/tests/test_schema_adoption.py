from pathlib import Path
from tempfile import TemporaryDirectory
from io import StringIO
import json
from unittest.mock import Mock, patch

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError
from django.test import SimpleTestCase, override_settings

from product_catalog.management.commands.adopt_product_catalog_schema import Command
from product_catalog.schema_adoption import (
    ADOPTION_LAST_MIGRATION,
    ADOPTION_MEDIA_FIELDS,
    SchemaAdoptionError,
    build_identifier_rename_plan,
    build_table_manifest,
    classify_metadata_state,
    classify_table_state,
    copy_verified_media,
    database_identifier_rename_sql,
    verify_adoption_invariants,
    replace_identity,
    transition_saved_value,
    validate_unique_replacements,
)


class SchemaAdoptionManifestTests(SimpleTestCase):
    def setUp(self):
        self.legacy_label = "legacy_" + "catalog"
        self.current_label = "product_catalog"

    def test_manifest_covers_every_catalog_model(self):
        manifest = build_table_manifest(
            apps.get_app_config(self.current_label),
            legacy_table_prefix=self.legacy_label,
        )

        model_tables = {
            model._meta.db_table
            for model in apps.get_app_config(self.current_label).get_models()
        }
        self.assertEqual(len(manifest), len(model_tables))
        self.assertEqual({item.current_table for item in manifest}, model_tables)
        self.assertTrue(all(item.legacy_table.startswith(f"{self.legacy_label}_") for item in manifest))

    def test_state_classifier_accepts_only_complete_or_resumable_manifests(self):
        manifest = build_table_manifest(
            apps.get_app_config(self.current_label),
            legacy_table_prefix=self.legacy_label,
        )[:2]
        old = {item.legacy_table for item in manifest}
        new = {item.current_table for item in manifest}

        self.assertEqual(classify_table_state(manifest, set()), "fresh")
        self.assertEqual(classify_table_state(manifest, old), "legacy")
        self.assertEqual(classify_table_state(manifest, new), "adopted")
        self.assertEqual(
            classify_table_state(manifest, {manifest[0].current_table, manifest[1].legacy_table}),
            "resumable",
        )

        with self.assertRaisesMessage(SchemaAdoptionError, "both legacy and current"):
            classify_table_state(manifest, {manifest[0].legacy_table, manifest[0].current_table})
        with self.assertRaisesMessage(SchemaAdoptionError, "partial catalog schema"):
            classify_table_state(manifest, {manifest[0].legacy_table})

    def test_adoption_boundary_is_before_post_adoption_migrations(self):
        self.assertEqual(ADOPTION_LAST_MIGRATION, "0011_refine_brigade_taxonomy")

    @override_settings(MIGRATION_MODULES={})
    def test_historical_adoption_manifest_excludes_post_boundary_models(self):
        from product_catalog.schema_adoption import SchemaAdoption

        adopter = SchemaAdoption(
            legacy_app_label=self.legacy_label,
            legacy_table_prefix=self.legacy_label,
        )
        manifest_labels = {item.model_label for item in adopter.manifest}

        self.assertNotIn("product_catalog.ImageOptimizationJob", manifest_labels)
        collection = next(
            item for item in manifest_labels if item.endswith(".MerchCollection")
        )
        self.assertEqual(collection, "product_catalog.MerchCollection")
        historical_collection = next(
            model
            for model in adopter.app_config.get_models()
            if model.__name__ == "MerchCollection"
        )
        self.assertFalse(any(field.name == "icon" for field in historical_collection._meta.fields))

    def test_renamed_tables_with_legacy_metadata_are_resumable(self):
        self.assertEqual(
            classify_metadata_state(
                table_state="adopted",
                has_legacy_metadata=True,
                has_current_metadata=False,
            ),
            "resumable",
        )

    def test_pre_adoption_media_manifest_excludes_post_adoption_fields(self):
        self.assertIn(("product_catalog", "FeedOnlyImage", "image"), ADOPTION_MEDIA_FIELDS)
        self.assertIn(("product_catalog", "MerchCollection", "cover_image"), ADOPTION_MEDIA_FIELDS)
        self.assertNotIn(("product_catalog", "MerchCollection", "icon"), ADOPTION_MEDIA_FIELDS)

    def test_database_identifier_plan_matches_current_model_state(self):
        app_config = apps.get_app_config(self.current_label)
        manifest = build_table_manifest(
            app_config,
            legacy_table_prefix=self.legacy_label,
        )
        item = next(row for row in manifest if row.model_label.endswith("ProductAudience"))
        audience = next(row for row in manifest if row.model_label.endswith("AudienceTag"))
        old_auto_index = f"{item.legacy_table}_product_id_deadbeef"
        old_foreign_key = f"{item.legacy_table}_tag_id_deadbeef_fk_{audience.legacy_table}_id"
        metadata = {
            item.legacy_table: {
                "constraints": [
                    {
                        "name": "legacy_unique_product_audience",
                        "columns": ["product_id", "tag_id"],
                        "unique": True,
                        "index": True,
                        "primary_key": False,
                        "foreign_key": None,
                    },
                    {
                        "name": old_auto_index,
                        "columns": ["product_id"],
                        "unique": False,
                        "index": True,
                        "primary_key": False,
                        "foreign_key": None,
                    },
                    {
                        "name": old_foreign_key,
                        "columns": ["tag_id"],
                        "unique": False,
                        "index": True,
                        "primary_key": False,
                        "foreign_key": [audience.legacy_table, "id"],
                        "delete_rule": "RESTRICT",
                        "update_rule": "RESTRICT",
                    },
                ]
            }
        }

        editor = __import__("django.db", fromlist=["connection"]).connection.schema_editor()
        plan = build_identifier_rename_plan(
            app_config,
            manifest,
            metadata,
            editor,
        )

        by_old_name = {row.old_name: row for row in plan}
        self.assertEqual(
            by_old_name["legacy_unique_product_audience"].new_name,
            "product_catalog_unique_product_audience",
        )
        self.assertTrue(by_old_name[old_auto_index].new_name.startswith("product_catalog_"))
        self.assertEqual(by_old_name[old_foreign_key].kind, "foreign_key")
        self.assertEqual(
            by_old_name[old_foreign_key].referenced_current_table,
            audience.current_table,
        )
        self.assertNotIn(self.legacy_label, " ".join(row.new_name for row in plan))


class SchemaAdoptionDataTests(SimpleTestCase):
    def test_table_content_and_database_metadata_must_survive_adoption(self):
        before = {
            "legacy_catalog_item": {
                "table": "legacy_catalog_item",
                "count": 7,
                "engine": "InnoDB",
                "collation": "utf8mb4_unicode_ci",
                "auto_increment": 18,
                "constraints": [
                    {
                        "name": "legacy_catalog_item_parent_fk",
                        "columns": ["parent_id"],
                        "unique": False,
                        "index": True,
                        "primary_key": False,
                        "foreign_key": ["legacy_catalog_parent", "id"],
                        "delete_rule": "CASCADE",
                        "update_rule": "RESTRICT",
                    }
                ],
            }
        }
        after = {
            "product_catalog_item": {
                "table": "product_catalog_item",
                "count": 7,
                "engine": "InnoDB",
                "collation": "utf8mb4_unicode_ci",
                "auto_increment": 18,
                "constraints": [
                    {
                        "name": "product_catalog_item_parent_fk",
                        "columns": ["parent_id"],
                        "unique": False,
                        "index": True,
                        "primary_key": False,
                        "foreign_key": ["product_catalog_parent", "id"],
                        "delete_rule": "CASCADE",
                        "update_rule": "RESTRICT",
                    }
                ],
            }
        }
        table_map = {
            "legacy_catalog_item": "product_catalog_item",
            "legacy_catalog_parent": "product_catalog_parent",
        }

        verify_adoption_invariants(before, after, table_map=table_map)

        after["product_catalog_item"]["auto_increment"] = 19
        with self.assertRaisesMessage(SchemaAdoptionError, "auto_increment"):
            verify_adoption_invariants(before, after, table_map=table_map)

    def test_saved_rollback_transition_refuses_drift(self):
        change = {"before": "legacy_catalog:42", "after": "product_catalog:42"}

        self.assertEqual(
            transition_saved_value("product_catalog:42", change, reverse=True),
            "legacy_catalog:42",
        )
        with self.assertRaisesMessage(SchemaAdoptionError, "drift"):
            transition_saved_value("operator-edited:42", change, reverse=True)

    def test_foreign_key_identifier_sql_is_atomic_and_reversible(self):
        from product_catalog.schema_adoption import DatabaseIdentifierRename

        row = DatabaseIdentifierRename(
            model_label="product_catalog.Child",
            legacy_table="legacy_child",
            current_table="product_catalog_child",
            kind="foreign_key",
            old_name="legacy_child_parent_fk",
            new_name="product_catalog_child_parent_fk",
            columns=("parent_id",),
            referenced_legacy_table="legacy_parent",
            referenced_current_table="product_catalog_parent",
            referenced_columns=("id",),
            delete_rule="CASCADE",
            update_rule="RESTRICT",
            rename_supporting_index=True,
        )
        quote = lambda value: f"`{value}`"

        forward = database_identifier_rename_sql(row, quote)
        reverse = database_identifier_rename_sql(row, quote, reverse=True)

        self.assertIn("DROP FOREIGN KEY `legacy_child_parent_fk`", forward)
        self.assertIn(
            "RENAME INDEX `legacy_child_parent_fk` TO `product_catalog_child_parent_fk`",
            forward,
        )
        self.assertIn("REFERENCES `product_catalog_parent` (`id`)", forward)
        self.assertIn("ON DELETE CASCADE ON UPDATE RESTRICT", forward)
        self.assertIn("DROP FOREIGN KEY `product_catalog_child_parent_fk`", reverse)
        self.assertIn(
            "RENAME INDEX `product_catalog_child_parent_fk` TO `legacy_child_parent_fk`",
            reverse,
        )

    def test_nested_json_and_text_values_are_rewritten_without_touching_other_values(self):
        old = "legacy_" + "catalog"
        value = {
            "source_revision": f"{old}:42",
            "assets": [f"{old}/feed/a.png", {"namespace": old}],
            "unchanged": "catalog",
        }

        replaced = replace_identity(value, old, "product_catalog")

        self.assertEqual(replaced["source_revision"], "product_catalog:42")
        self.assertEqual(replaced["assets"][0], "product_catalog/feed/a.png")
        self.assertEqual(replaced["assets"][1]["namespace"], "product_catalog")
        self.assertEqual(replaced["unchanged"], "catalog")

    def test_unique_replacement_validation_rejects_collisions_and_overflow(self):
        with self.assertRaisesMessage(SchemaAdoptionError, "collision"):
            validate_unique_replacements(
                [(1, "legacy:1", "product_catalog:1"), (2, "product_catalog:1", "product_catalog:1")],
                max_length=180,
                field_label="event_key",
            )

        with self.assertRaisesMessage(SchemaAdoptionError, "exceeds max_length"):
            validate_unique_replacements(
                [(1, "legacy", "product_catalog")],
                max_length=5,
                field_label="event_key",
            )

    def test_media_copy_verifies_size_and_hash_and_preserves_source(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "legacy_catalog" / "feed_images" / "print.png"
            target = root / "product_catalog" / "feed_images" / "print.png"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"canonical-print-artwork")

            result = copy_verified_media(root, source.relative_to(root), target.relative_to(root))

            self.assertTrue(source.exists())
            self.assertEqual(target.read_bytes(), source.read_bytes())
            self.assertEqual(result.size, len(b"canonical-print-artwork"))
            self.assertEqual(result.source_sha256, result.target_sha256)


class SchemaAdoptionCommandGuardTests(SimpleTestCase):
    @patch(
        "product_catalog.management.commands.adopt_product_catalog_schema.current_git_sha",
        return_value="b" * 40,
    )
    def test_apply_refuses_a_different_deployed_sha(self, current_sha):
        command = Command()

        with self.assertRaisesMessage(CommandError, "deployed SHA mismatch"):
            command._validate_sha({"apply": True, "expected_sha": "a" * 40})

        current_sha.assert_called_once()

    @patch(
        "product_catalog.management.commands.adopt_product_catalog_schema.current_git_sha",
        return_value="a" * 40,
    )
    def test_apply_accepts_the_exact_deployed_sha(self, current_sha):
        command = Command()

        command._validate_sha({"apply": True, "expected_sha": "a" * 40})

        current_sha.assert_called_once()

    def test_apply_requires_a_full_expected_sha(self):
        command = Command()

        with self.assertRaisesMessage(CommandError, "40-character commit SHA"):
            command._validate_sha({"apply": True, "expected_sha": "abc123"})

    def test_rollback_refuses_post_adoption_migrations(self):
        adopter = object.__new__(__import__(
            "product_catalog.schema_adoption",
            fromlist=["SchemaAdoption"],
        ).SchemaAdoption)
        adopter.current_app_label = "product_catalog"
        adopter._expected_migration_names = Mock(return_value=("0010_example", "0011_boundary"))
        adopter._migration_rows = Mock(
            return_value=[
                {"name": "0010_example", "applied": "2026-08-10T00:00:00"},
                {"name": "0011_boundary", "applied": "2026-08-10T00:00:01"},
                {"name": "0012_post_adoption", "applied": "2026-08-10T00:00:02"},
            ]
        )

        with self.assertRaisesMessage(SchemaAdoptionError, "post-adoption migrations"):
            adopter._assert_rollback_boundary("0011_boundary")

    @patch(
        "product_catalog.management.commands.adopt_product_catalog_schema.current_git_sha",
        return_value="a" * 40,
    )
    @patch(
        "product_catalog.management.commands.adopt_product_catalog_schema.SchemaAdoption"
    )
    def test_management_command_persists_progress_for_database_errors(
        self, adopter_class, current_sha
    ):
        adopter = adopter_class.return_value
        adopter.connection.vendor = "sqlite"
        adopter.media_root = None
        preflight = {
            "state": "legacy",
            "metadata_state": "legacy",
            "identifier_renames": [],
        }
        adopter.preflight.return_value = preflight

        def fail_after_checkpoint(*, last_migration, checkpoint):
            checkpoint({"phase": "tables-renamed", "renamed_tables": [{"from": "a", "to": "b"}]})
            raise DatabaseError("connection dropped")

        adopter.apply.side_effect = fail_after_checkpoint
        database_name = str(settings.DATABASES["default"]["NAME"] or "")
        with TemporaryDirectory() as temp_dir:
            snapshot = Path(temp_dir) / "adoption.json"
            with self.assertRaisesMessage(CommandError, "connection dropped"):
                call_command(
                    "adopt_product_catalog_schema",
                    "--apply",
                    "--legacy-app-label=legacy_catalog",
                    "--legacy-table-prefix=legacy_catalog",
                    f"--expected-database={database_name}",
                    f"--snapshot-path={snapshot}",
                    f"--expected-sha={'a' * 40}",
                    "--confirm-app-label=legacy_catalog",
                    f"--confirm-database={database_name}",
                    "--confirm-write=ADOPT_PRODUCT_CATALOG",
                    "--confirm-maintenance=STOP_TRAFFIC",
                    stdout=StringIO(),
                )

            payload = json.loads(snapshot.read_text(encoding="utf-8"))
            self.assertEqual(payload["phase"], "failed")
            self.assertEqual(payload["progress"]["phase"], "tables-renamed")
            self.assertIn("connection dropped", payload["error"])

        current_sha.assert_called_once()
