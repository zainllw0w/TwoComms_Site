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
from django.test import SimpleTestCase, TestCase, override_settings

from product_catalog.management.commands.adopt_product_catalog_schema import Command
from product_catalog.schema_adoption import (
    ADOPTION_LAST_MIGRATION,
    ADOPTION_MEDIA_FIELDS,
    DatabaseIdentifierRename,
    SchemaAdoption,
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
    unexpected_prefixed_tables,
    validate_unique_replacements,
    write_snapshot,
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

    def test_mixed_metadata_is_resumable_after_table_rename(self):
        self.assertEqual(
            classify_metadata_state(
                table_state="adopted",
                has_legacy_metadata=True,
                has_current_metadata=True,
            ),
            "resumable",
        )

    def test_fresh_tables_with_stale_metadata_are_rejected(self):
        for legacy, current in ((True, False), (False, True), (True, True)):
            with self.subTest(legacy=legacy, current=current):
                with self.assertRaisesMessage(SchemaAdoptionError, "metadata exists without catalog tables"):
                    classify_metadata_state(
                        table_state="fresh",
                        has_legacy_metadata=legacy,
                        has_current_metadata=current,
                    )

    def test_unknown_prefixed_tables_are_rejected_but_known_post_boundary_table_is_reported(self):
        manifest = build_table_manifest(
            apps.get_app_config(self.current_label),
            legacy_table_prefix=self.legacy_label,
        )[:2]
        actual = {
            *(item.legacy_table for item in manifest),
            f"{self.legacy_label}_orphan",
            "product_catalog_imageoptimizationjob",
        }

        extra = unexpected_prefixed_tables(
            manifest,
            actual,
            legacy_prefix=self.legacy_label,
            current_prefix=self.current_label,
            known_current_tables={"product_catalog_imageoptimizationjob"},
        )

        self.assertEqual(extra["legacy"], {f"{self.legacy_label}_orphan"})
        self.assertEqual(extra["unknown_current"], set())
        self.assertEqual(extra["known_post_boundary"], {"product_catalog_imageoptimizationjob"})

    def test_pre_adoption_media_manifest_excludes_post_adoption_fields(self):
        self.assertIn(("product_catalog", "FeedOnlyImage", "image"), ADOPTION_MEDIA_FIELDS)
        self.assertIn(("product_catalog", "MerchCollection", "cover_image"), ADOPTION_MEDIA_FIELDS)
        self.assertNotIn(("product_catalog", "MerchCollection", "icon"), ADOPTION_MEDIA_FIELDS)

    @override_settings(MIGRATION_MODULES={})
    def test_supported_media_fields_follow_the_selected_historical_boundary(self):
        from product_catalog.schema_adoption import SchemaAdoption

        before_collections = SchemaAdoption(
            legacy_app_label=self.legacy_label,
            legacy_table_prefix=self.legacy_label,
            adoption_last_migration="0009_audience_taxonomy",
        )
        at_boundary = SchemaAdoption(
            legacy_app_label=self.legacy_label,
            legacy_table_prefix=self.legacy_label,
        )

        self.assertEqual(
            {(model._meta.model_name, field.name) for model, field in before_collections._iter_supported_fields(ADOPTION_MEDIA_FIELDS)},
            {("feedonlyimage", "image")},
        )
        self.assertIn(
            ("merchcollection", "cover_image"),
            {(model._meta.model_name, field.name) for model, field in at_boundary._iter_supported_fields(ADOPTION_MEDIA_FIELDS)},
        )

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


class SchemaAdoptionPermissionTests(TestCase):
    def test_permission_names_are_adopted_and_restored_without_identity_drift(self):
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get(
            app_label="product_catalog",
            model="colorprofile",
        )
        permission = Permission.objects.get(
            content_type=content_type,
            codename="add_colorprofile",
        )
        retired_name = "Can add Retired editor: profile"
        Permission.objects.filter(pk=permission.pk).update(name=retired_name)

        adopter = object.__new__(SchemaAdoption)
        adopter.app_config = apps.get_app_config("product_catalog")
        adopter.connection_alias = "default"
        content_types = [{"id": content_type.pk, "model": content_type.model}]
        permissions = [
            {
                "id": permission.pk,
                "content_type_id": content_type.pk,
                "codename": permission.codename,
                "name": retired_name,
            }
        ]

        changes = adopter._build_permission_name_changes(
            content_types,
            permissions,
        )
        self.assertEqual(changes[0]["before"], retired_name)
        self.assertEqual(changes[0]["after"], "Can add Каталог: профіль кольору")

        adopter._apply_permission_name_changes(changes)
        permission.refresh_from_db()
        self.assertEqual(permission.name, changes[0]["after"])

        adopter._apply_permission_name_changes(changes, reverse=True)
        permission.refresh_from_db()
        self.assertEqual(permission.name, retired_name)


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

    def test_adoption_invariants_require_innodb_for_catalog_tables(self):
        before = {
            "legacy_catalog_item": {
                "table": "legacy_catalog_item",
                "count": 1,
                "engine": "MyISAM",
                "collation": "utf8mb4_unicode_ci",
                "auto_increment": 2,
                "constraints": [],
            }
        }
        after = {
            "product_catalog_item": {
                "table": "product_catalog_item",
                "count": 1,
                "engine": "MyISAM",
                "collation": "utf8mb4_unicode_ci",
                "auto_increment": 2,
                "constraints": [],
            }
        }

        with self.assertRaisesMessage(SchemaAdoptionError, "must use InnoDB"):
            verify_adoption_invariants(
                before,
                after,
                table_map={"legacy_catalog_item": "product_catalog_item"},
            )

    def test_write_adoption_refuses_non_mysql_before_preflight(self):
        adopter = object.__new__(SchemaAdoption)
        adopter.connection = Mock(vendor="sqlite")
        adopter.preflight = Mock()

        with self.assertRaisesMessage(SchemaAdoptionError, "requires MySQL"):
            adopter.apply(last_migration=ADOPTION_LAST_MIGRATION)

        adopter.preflight.assert_not_called()

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
    def _mock_adopter_for_apply(self, *, saved_progress=None):
        adopter = object.__new__(SchemaAdoption)
        adopter.manifest = ()
        adopter.legacy_app_label = "legacy_catalog"
        adopter.current_app_label = "product_catalog"
        initial = {
            "state": "legacy",
            "metadata_state": "legacy",
            "tables": [],
            "legacy_migrations": [],
            "legacy_content_types": [],
            "legacy_permissions": [],
            "identifier_renames": [],
        }
        current = {
            "state": "adopted",
            "metadata_state": "adopted",
            "tables": [],
            "current_migrations": [],
            "current_content_types": [],
            "current_permissions": [],
            "identifier_renames": [],
        }
        adopter.preflight = Mock(side_effect=[initial, current])
        adopter._rename_tables = Mock()
        adopter._apply_identifier_renames = Mock()
        adopter._collect_data_changes = Mock(return_value=[])
        adopter._collect_media_changes = Mock(return_value=[])
        adopter._adopt_recorder = Mock()
        adopter._adopt_content_types = Mock()
        adopter._apply_data_changes = Mock()
        adopter._apply_media_changes = Mock()
        adopter._verify_metadata_invariants = Mock()
        return adopter, initial, saved_progress

    def test_apply_checkpoints_pending_manifests_before_first_table_ddl(self):
        adopter, initial, _ = self._mock_adopter_for_apply()
        checkpoints = []

        def rename_tables(report, *, checkpoint):
            self.assertEqual(report["data_media_manifest_state"], "pending")
            self.assertEqual(report["data_changes"], [])
            self.assertEqual(report["media_changes"], [])
            self.assertEqual(checkpoints[-1]["phase"], "manifests-pending")

        adopter._rename_tables.side_effect = rename_tables

        adopter.apply(initial_preflight=initial, checkpoint=checkpoints.append)

        self.assertEqual(checkpoints[0]["data_media_manifest_state"], "pending")
        self.assertEqual(checkpoints[0]["data_changes"], [])
        self.assertEqual(checkpoints[0]["media_changes"], [])

    def test_apply_captures_manifests_before_identifier_ddl(self):
        adopter, initial, _ = self._mock_adopter_for_apply()
        data_changes = [
            {
                "model": "example.Model",
                "field": "payload",
                "before": {"app": "legacy_catalog"},
                "after": {"app": "product_catalog"},
            }
        ]
        media_changes = [{"model": "example.Model", "field": "image"}]
        adopter._collect_data_changes.return_value = data_changes
        adopter._collect_media_changes.return_value = media_changes

        def rename_identifiers(_rows, report, **_kwargs):
            self.assertEqual(report["data_media_manifest_state"], "captured")
            self.assertEqual(report["data_changes"], data_changes)
            self.assertEqual(report["media_changes"], media_changes)

        adopter._apply_identifier_renames.side_effect = rename_identifiers

        adopter.apply(initial_preflight=initial)

    def test_apply_recaptures_pending_manifests_on_resume(self):
        saved = {
            "phase": "table-renamed",
            "data_media_manifest_state": "pending",
            "data_changes": [],
            "media_changes": [],
        }
        adopter, initial, _ = self._mock_adopter_for_apply(saved_progress=saved)
        expected_data = [
            {
                "model": "example.Model",
                "field": "payload",
                "before": {"app": "legacy_catalog"},
                "after": {"app": "product_catalog"},
            }
        ]
        expected_media = [{"model": "example.Model", "field": "image"}]
        adopter._collect_data_changes.return_value = expected_data
        adopter._collect_media_changes.return_value = expected_media

        result = adopter.apply(initial_preflight=initial, saved_progress=saved)

        adopter._collect_data_changes.assert_called_once()
        adopter._collect_media_changes.assert_called_once()
        self.assertEqual(result["data_media_manifest_state"], "captured")
        self.assertEqual(result["data_changes"], expected_data)
        self.assertEqual(result["media_changes"], expected_media)

    def test_reverse_identifier_rename_skips_legacy_table_with_old_identifier(self):
        adopter = object.__new__(SchemaAdoption)
        adopter.connection = Mock()
        adopter.connection.vendor = "mysql"
        adopter.connection.ops.quote_name.side_effect = lambda name: f"`{name}`"
        cursor = Mock()
        adopter.connection.cursor.return_value.__enter__ = Mock(return_value=cursor)
        adopter.connection.cursor.return_value.__exit__ = Mock(return_value=False)
        adopter.connection.introspection.get_constraints.return_value = {
            "legacy_index": {"index": True}
        }
        adopter._table_names = Mock(return_value={"legacy_table"})
        row = DatabaseIdentifierRename(
            model_label="example.Model",
            legacy_table="legacy_table",
            current_table="current_table",
            kind="index",
            old_name="legacy_index",
            new_name="current_index",
            columns=("value",),
        )
        report = {}

        adopter._apply_identifier_renames([row], report, reverse=True)

        adopter.connection.introspection.get_constraints.assert_called_once_with(
            cursor,
            "legacy_table",
        )
        cursor.execute.assert_not_called()
        self.assertEqual(
            report["identifier_renames_skipped"],
            [{"table": "legacy_table", "name": "legacy_index"}],
        )

    def test_forward_identifier_rename_rejects_an_unrenamed_legacy_table(self):
        adopter = object.__new__(SchemaAdoption)
        adopter.connection = Mock()
        adopter.connection.vendor = "mysql"
        adopter._table_names = Mock(return_value={"legacy_table"})
        row = DatabaseIdentifierRename(
            model_label="example.Model",
            legacy_table="legacy_table",
            current_table="current_table",
            kind="index",
            old_name="legacy_index",
            new_name="current_index",
            columns=("value",),
        )

        with self.assertRaisesMessage(
            SchemaAdoptionError,
            "forward identifier rename requires current table",
        ):
            adopter._apply_identifier_renames([row], {}, reverse=False)

    def test_rollback_accepts_empty_pending_manifests(self):
        adopter = object.__new__(SchemaAdoption)
        adopter.manifest = ()
        adopter.preflight = Mock(
            side_effect=[
                {"state": "resumable", "metadata_state": "resumable"},
                {"state": "legacy", "metadata_state": "legacy"},
            ]
        )
        adopter._assert_rollback_boundary = Mock()
        adopter._assert_saved_permissions = Mock()
        adopter._apply_identifier_renames = Mock()
        adopter._rollback_recorder = Mock()
        adopter._rollback_content_types = Mock()
        adopter._apply_saved_data_changes = Mock()
        adopter._apply_saved_media_changes = Mock()
        adopter._rename_tables_back = Mock()

        result = adopter.rollback(
            identifier_renames=[],
            data_media_manifest_state="pending",
            data_changes=[],
            media_changes=[],
            migrations=[],
            content_types=[],
            permissions=[],
        )

        self.assertEqual(result["phase"], "rolled-back")
        adopter._apply_saved_data_changes.assert_called_once_with([], reverse=True)
        adopter._apply_saved_media_changes.assert_called_once_with([], reverse=True)

    def test_rollback_rejects_captured_state_without_saved_manifests(self):
        adopter = object.__new__(SchemaAdoption)
        adopter.preflight = Mock(
            return_value={"state": "adopted", "metadata_state": "adopted"}
        )

        with self.assertRaisesMessage(
            SchemaAdoptionError,
            "captured data/media manifest is incomplete",
        ):
            adopter.rollback(
                identifier_renames=[],
                data_media_manifest_state="captured",
                data_changes=None,
                media_changes=[],
                migrations=[],
                content_types=[],
                permissions=[],
            )

    def test_apply_snapshot_refuses_to_overwrite_existing_recovery_evidence(self):
        command = Command()
        with TemporaryDirectory() as temp_dir:
            snapshot = Path(temp_dir) / "adoption.json"
            snapshot.write_text('{"phase":"failed"}', encoding="utf-8")
            snapshot.chmod(0o600)

            with self.assertRaisesMessage(CommandError, "already exists"):
                command._write_snapshot(
                    str(snapshot),
                    {"phase": "preflight-complete"},
                    must_not_exist=True,
                )

            self.assertEqual(snapshot.read_text(encoding="utf-8"), '{"phase":"failed"}')

    def test_atomic_snapshot_fsyncs_file_and_parent_directory(self):
        with TemporaryDirectory() as temp_dir:
            snapshot = Path(temp_dir) / "adoption.json"
            with patch(
                "product_catalog.schema_adoption.os.fsync",
                wraps=__import__("os").fsync,
            ) as fsync:
                write_snapshot(snapshot, {"phase": "manifests-pending"})

            self.assertGreaterEqual(fsync.call_count, 2)
            self.assertEqual(
                json.loads(snapshot.read_text(encoding="utf-8"))["phase"],
                "manifests-pending",
            )

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
        adopter.legacy_app_label = "legacy_catalog"
        adopter.current_app_label = "product_catalog"
        adopter._expected_migration_names = Mock(return_value=("0010_example", "0011_boundary"))
        adopter._migration_rows = Mock(
            side_effect=[
                [],
                [
                    {"name": "0010_example", "applied": "2026-08-10T00:00:00"},
                    {"name": "0011_boundary", "applied": "2026-08-10T00:00:01"},
                    {"name": "0012_post_adoption", "applied": "2026-08-10T00:00:02"},
                ],
            ]
        )

        with self.assertRaisesMessage(SchemaAdoptionError, "post-adoption migrations"):
            adopter._assert_rollback_boundary("0011_boundary")

    def test_apply_resumes_saved_data_and_media_after_metadata_is_already_adopted(self):
        from product_catalog.schema_adoption import SchemaAdoption

        adopter = object.__new__(SchemaAdoption)
        adopter.manifest = ()
        adopter.legacy_app_label = "legacy_catalog"
        adopter.current_app_label = "product_catalog"
        current = {
            "state": "adopted",
            "metadata_state": "adopted",
            "tables": [],
            "current_migrations": [],
            "current_content_types": [],
            "current_permissions": [],
            "identifier_renames": [],
        }
        initial = {
            "state": "legacy",
            "metadata_state": "legacy",
            "tables": [],
            "legacy_migrations": [],
            "legacy_content_types": [],
            "legacy_permissions": [],
            "identifier_renames": [],
        }
        saved = {
            "phase": "content-types-adopted",
            "data_changes": [{"model": "example.Model", "field": "payload"}],
            "media_changes": [{"model": "example.Model", "field": "image"}],
        }
        adopter.preflight = Mock(side_effect=[current, current])
        adopter._rename_tables = Mock()
        adopter._apply_identifier_renames = Mock()
        adopter._adopt_recorder = Mock()
        adopter._adopt_content_types = Mock()
        adopter._apply_data_changes = Mock()
        adopter._apply_media_changes = Mock()
        adopter._verify_metadata_invariants = Mock()

        result = adopter.apply(
            initial_preflight=initial,
            saved_progress=saved,
        )

        adopter._apply_data_changes.assert_called_once_with(saved["data_changes"])
        adopter._apply_media_changes.assert_called_once_with(saved["media_changes"])
        self.assertEqual(result["phase"], "complete")

    def test_resume_refuses_fresh_state_after_a_legacy_preflight(self):
        from product_catalog.schema_adoption import SchemaAdoption

        adopter = object.__new__(SchemaAdoption)
        adopter.preflight = Mock(
            return_value={
                "state": "fresh",
                "metadata_state": "fresh",
                "tables": [],
            }
        )

        with self.assertRaisesMessage(
            SchemaAdoptionError,
            "catalog tables disappeared",
        ):
            adopter.apply(
                initial_preflight={
                    "state": "legacy",
                    "metadata_state": "legacy",
                    "tables": [{"table": "legacy_catalog_example"}],
                },
                saved_progress={"phase": "table-renamed"},
            )

    def test_rollback_can_resume_after_metadata_and_data_phases(self):
        from product_catalog.schema_adoption import SchemaAdoption

        adopter = object.__new__(SchemaAdoption)
        adopter.manifest = ()
        adopter.preflight = Mock(
            side_effect=[
                {"state": "resumable", "metadata_state": "resumable"},
                {"state": "legacy", "metadata_state": "legacy"},
            ]
        )
        adopter._assert_rollback_boundary = Mock()
        adopter._assert_saved_permissions = Mock()
        adopter._apply_identifier_renames = Mock()
        adopter._rollback_recorder = Mock()
        adopter._rollback_content_types = Mock()
        adopter._apply_saved_data_changes = Mock()
        adopter._apply_saved_media_changes = Mock()
        adopter._rename_tables_back = Mock()
        checkpoint = Mock()

        result = adopter.rollback(
            identifier_renames=[],
            data_media_manifest_state="captured",
            data_changes=[],
            media_changes=[],
            migrations=[],
            content_types=[],
            permissions=[],
            saved_progress={
                "rollback_identifiers_complete": True,
                "rollback_metadata_complete": True,
                "rollback_data_complete": True,
                "rollback_media_complete": True,
            },
            checkpoint=checkpoint,
        )

        adopter._apply_identifier_renames.assert_not_called()
        adopter._rollback_recorder.assert_not_called()
        adopter._apply_saved_data_changes.assert_not_called()
        adopter._rename_tables_back.assert_called_once()
        self.assertEqual(result["phase"], "rolled-back")

    @patch(
        "product_catalog.management.commands.adopt_product_catalog_schema.current_git_sha",
        return_value="a" * 40,
    )
    @patch(
        "product_catalog.management.commands.adopt_product_catalog_schema.SchemaAdoption"
    )
    def test_management_command_resumes_the_original_snapshot(
        self, adopter_class, current_sha
    ):
        adopter = adopter_class.return_value
        adopter.connection.vendor = "sqlite"
        adopter.media_root = None
        adopter.apply.return_value = {"phase": "complete"}
        database_name = str(settings.DATABASES["default"]["NAME"] or "")
        with TemporaryDirectory() as temp_dir:
            snapshot = Path(temp_dir) / "adoption.json"
            snapshot.write_text(
                json.dumps(
                    {
                        "adoption": {
                            "legacy_app_label": "legacy_catalog",
                            "legacy_table_prefix": "legacy_catalog",
                            "legacy_last_migration": ADOPTION_LAST_MIGRATION,
                            "expected_database": database_name,
                            "media_root": None,
                            "expected_sha": "a" * 40,
                        },
                        "phase": "failed",
                        "preflight": {"state": "legacy"},
                        "progress": {"phase": "tables-renamed"},
                    }
                ),
                encoding="utf-8",
            )
            snapshot.chmod(0o600)

            call_command(
                "adopt_product_catalog_schema",
                f"--resume-snapshot={snapshot}",
                "--confirm-app-label=legacy_catalog",
                f"--confirm-database={database_name}",
                "--confirm-write=ADOPT_PRODUCT_CATALOG",
                "--confirm-maintenance=STOP_TRAFFIC",
                stdout=StringIO(),
            )

            adopter.apply.assert_called_once_with(
                last_migration=ADOPTION_LAST_MIGRATION,
                checkpoint=adopter.apply.call_args.kwargs["checkpoint"],
                initial_preflight={"state": "legacy"},
                saved_progress={"phase": "tables-renamed"},
            )
            payload = json.loads(snapshot.read_text(encoding="utf-8"))
            self.assertEqual(payload["phase"], "complete")

        current_sha.assert_called_once()

    @patch(
        "product_catalog.management.commands.adopt_product_catalog_schema.current_git_sha",
        return_value="a" * 40,
    )
    @patch(
        "product_catalog.management.commands.adopt_product_catalog_schema.SchemaAdoption"
    )
    def test_management_command_refuses_forward_resume_after_rollback_started(
        self, adopter_class, current_sha
    ):
        adopter_class.return_value.apply.return_value = {"phase": "complete"}
        database_name = str(settings.DATABASES["default"]["NAME"] or "")
        with TemporaryDirectory() as temp_dir:
            snapshot = Path(temp_dir) / "adoption.json"
            snapshot.write_text(
                json.dumps(
                    {
                        "adoption": {
                            "legacy_app_label": "legacy_catalog",
                            "legacy_table_prefix": "legacy_catalog",
                            "legacy_last_migration": ADOPTION_LAST_MIGRATION,
                            "expected_database": database_name,
                            "media_root": None,
                            "expected_sha": "a" * 40,
                        },
                        "phase": "rollback-failed",
                        "preflight": {"state": "legacy"},
                        "progress": {"phase": "complete"},
                        "rollback_progress": {
                            "phase": "rollback-identifiers-complete",
                            "rollback_identifiers_complete": True,
                        },
                    }
                ),
                encoding="utf-8",
            )
            snapshot.chmod(0o600)

            with self.assertRaisesMessage(
                CommandError,
                "rollback has already started",
            ):
                call_command(
                    "adopt_product_catalog_schema",
                    f"--resume-snapshot={snapshot}",
                    "--confirm-app-label=legacy_catalog",
                    f"--confirm-database={database_name}",
                    "--confirm-write=ADOPT_PRODUCT_CATALOG",
                    "--confirm-maintenance=STOP_TRAFFIC",
                    stdout=StringIO(),
                )

        adopter_class.assert_not_called()
        current_sha.assert_not_called()

    @patch(
        "product_catalog.management.commands.adopt_product_catalog_schema.current_git_sha",
        return_value="a" * 40,
    )
    @patch(
        "product_catalog.management.commands.adopt_product_catalog_schema.SchemaAdoption"
    )
    def test_management_command_passes_captured_manifests_to_rollback(
        self, adopter_class, current_sha
    ):
        adopter = adopter_class.return_value
        adopter.connection.vendor = "sqlite"
        adopter.rollback.return_value = {"phase": "rolled-back"}
        database_name = str(settings.DATABASES["default"]["NAME"] or "")
        preflight = {
            "identifier_renames": [],
            "legacy_migrations": [],
            "legacy_content_types": [],
            "legacy_permissions": [],
        }
        progress = {
            "phase": "data-manifest-captured",
            "data_media_manifest_state": "captured",
            "data_changes": [],
            "media_changes": [],
        }
        with TemporaryDirectory() as temp_dir:
            snapshot = Path(temp_dir) / "adoption.json"
            snapshot.write_text(
                json.dumps(
                    {
                        "adoption": {
                            "legacy_app_label": "legacy_catalog",
                            "legacy_table_prefix": "legacy_catalog",
                            "legacy_last_migration": ADOPTION_LAST_MIGRATION,
                            "expected_database": database_name,
                            "media_root": None,
                            "expected_sha": "a" * 40,
                        },
                        "phase": "failed",
                        "preflight": preflight,
                        "progress": progress,
                    }
                ),
                encoding="utf-8",
            )
            snapshot.chmod(0o600)

            call_command(
                "adopt_product_catalog_schema",
                f"--rollback-snapshot={snapshot}",
                "--confirm-app-label=legacy_catalog",
                f"--confirm-database={database_name}",
                "--confirm-write=ADOPT_PRODUCT_CATALOG",
                "--confirm-maintenance=STOP_TRAFFIC",
                stdout=StringIO(),
            )

            adopter.rollback.assert_called_once_with(
                last_migration=ADOPTION_LAST_MIGRATION,
                identifier_renames=[],
                data_media_manifest_state="captured",
                data_changes=[],
                media_changes=[],
                migrations=[],
                content_types=[],
                permissions=[],
                checkpoint=adopter.rollback.call_args.kwargs["checkpoint"],
                initial_preflight=preflight,
                saved_progress=None,
            )
            payload = json.loads(snapshot.read_text(encoding="utf-8"))
            self.assertEqual(payload["phase"], "rolled-back")

        current_sha.assert_called_once()

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

        def fail_after_checkpoint(*, last_migration, checkpoint, initial_preflight):
            self.assertEqual(initial_preflight, preflight)
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
