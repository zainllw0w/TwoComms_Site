import json
import os
import subprocess
import sys
import tempfile
import textwrap

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.utils import timezone

from storefront.admin import ProductSalesSemanticProfileRevisionAdmin
from storefront.models import (
    Category,
    Product,
    ProductSalesSemanticProfile,
    ProductSalesSemanticProfileRevision,
)
from storefront.services.product_sales_semantics import (
    create_semantic_revision,
    get_effective_verified_revision,
    validate_semantic_revision,
)


class ProductSalesSemanticRevisionTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="Semantic products",
            slug="semantic-products",
        )
        self.product = Product.objects.create(
            title="Verified semantic product",
            slug="verified-semantic-product",
            category=self.category,
            price=1200,
        )
        self.verifier = get_user_model().objects.create_user(
            username="semantic-verifier",
            password="test-password",
            is_staff=True,
        )
        self.profile = ProductSalesSemanticProfile.objects.create(product=self.product)

    def create_verified_revision(self, **overrides):
        values = {
            "profile": self.profile,
            "revision": 1,
            "status": ProductSalesSemanticProfileRevision.Status.VERIFIED,
            "schema_version": 1,
            "aliases": {"uk": ["чорна футболка Raven"], "ru": ["черная футболка Raven"]},
            "traits": {
                "front_decoration": "logo",
                "back_decoration": "none",
                "hem_construction": "standard",
            },
            "source": ProductSalesSemanticProfileRevision.Source.MANAGER,
            "verified_by": self.verifier,
            "verified_at": timezone.now(),
        }
        values.update(overrides)
        return ProductSalesSemanticProfileRevision.objects.create(**values)

    def test_existing_revision_instance_cannot_be_mutated_or_deleted(self):
        revision = self.create_verified_revision()
        revision.traits = {"back_decoration": "print"}

        with self.assertRaisesMessage(ValidationError, "append-only"):
            revision.save()
        with self.assertRaisesMessage(ValueError, "append-only"):
            revision.delete()

    def test_revision_queryset_update_and_delete_are_blocked(self):
        revision = self.create_verified_revision()
        queryset = ProductSalesSemanticProfileRevision.objects.filter(pk=revision.pk)

        with self.assertRaisesMessage(ValueError, "append-only"):
            queryset.update(traits={})
        with self.assertRaisesMessage(ValueError, "append-only"):
            queryset.delete()

    def test_bulk_create_cannot_bypass_effective_revision_transition(self):
        revision = ProductSalesSemanticProfileRevision(
            profile=self.profile,
            revision=1,
            status=ProductSalesSemanticProfileRevision.Status.VERIFIED,
            aliases={"en": ["Black Raven T-shirt"]},
            traits={"back_decoration": "none"},
            source=ProductSalesSemanticProfileRevision.Source.MANAGER,
            verified_by=self.verifier,
            verified_at=timezone.now(),
        )

        with self.assertRaisesMessage(ValueError, "transactional semantic revision service"):
            ProductSalesSemanticProfileRevision.objects.bulk_create([revision])

        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.effective_revision_id)
        self.assertFalse(self.profile.revisions.exists())

    def test_bulk_create_keeps_valid_draft_import_available(self):
        revisions = [
            ProductSalesSemanticProfileRevision(
                profile=self.profile,
                revision=1,
                status=ProductSalesSemanticProfileRevision.Status.DRAFT,
                aliases={"EN": ["  Black   Raven T-shirt  "]},
                traits={"back_decoration": "none"},
                source=ProductSalesSemanticProfileRevision.Source.FREE_TEXT,
            )
        ]

        ProductSalesSemanticProfileRevision.objects.bulk_create(revisions)

        created = self.profile.revisions.get()
        self.assertEqual(created.aliases, {"en": ["black raven t-shirt"]})
        self.assertIsNone(self.profile.effective_revision_id)

    def test_non_authoritative_sources_cannot_create_verified_revision(self):
        for source in (
            "bot_vision",
            "free_text",
            "generated_description",
        ):
            with self.subTest(source=source), self.assertRaises(ValidationError):
                validate_semantic_revision(
                    status="verified",
                    source=source,
                    aliases={"uk": ["футболка"]},
                    traits={"back_decoration": "none"},
                    verified_by=self.verifier,
                    verified_at=timezone.now(),
                )

    def test_revocation_requires_authoritative_source_and_verification_evidence(self):
        for source, verified_by, verified_at in (
            ("bot_vision", self.verifier, timezone.now()),
            ("manager", None, timezone.now()),
            ("manager", self.verifier, None),
        ):
            with self.subTest(source=source, verified_by=bool(verified_by), verified_at=bool(verified_at)), self.assertRaises(ValidationError):
                validate_semantic_revision(
                    status="revoked",
                    source=source,
                    aliases={},
                    traits={},
                    verified_by=verified_by,
                    verified_at=verified_at,
                )

    def test_verified_revision_requires_trustworthy_verification_evidence(self):
        for missing in ("verified_by", "verified_at"):
            values = {
                "status": "verified",
                "source": "manager",
                "aliases": {"uk": ["футболка"]},
                "traits": {"back_decoration": "none"},
                "verified_by": self.verifier,
                "verified_at": timezone.now(),
            }
            values[missing] = None
            with self.subTest(missing=missing), self.assertRaises(ValidationError):
                validate_semantic_revision(**values)

    def test_verified_alias_cannot_be_generic_fit_garment_color_or_size_vocabulary(self):
        generic_aliases = {
            "en": ("classic", "oversize", "t-shirt", "black", "elastic", "s", "xxl"),
            "uk": ("класична", "оверсайз", "футболка", "чорний", "еластична", "m", "xl"),
            "ru": ("классика", "оверсайз", "футболка", "черный", "эластичная", "l", "2xl"),
        }

        for locale, aliases in generic_aliases.items():
            for alias in aliases:
                with self.subTest(locale=locale, alias=alias), self.assertRaises(ValidationError):
                    validate_semantic_revision(
                        status="verified",
                        source="manager",
                        aliases={locale: [alias]},
                        traits={"back_decoration": "none"},
                        verified_by=self.verifier,
                        verified_at=timezone.now(),
                    )

    def test_multiword_generic_constraints_cannot_be_verified_as_product_identity(self):
        for locale, alias in (
            ("en", "black classic t-shirt"),
            ("uk", "чорна класична футболка"),
            ("ru", "черная футболка оверсайз"),
        ):
            with self.subTest(locale=locale), self.assertRaises(ValidationError):
                validate_semantic_revision(
                    status="verified",
                    source="manager",
                    aliases={locale: [alias]},
                    traits={"back_decoration": "none"},
                    verified_by=self.verifier,
                    verified_at=timezone.now(),
                )

    def test_verified_alias_requires_a_non_connector_identity_token(self):
        for locale, alias in (
            ("en", "and"),
            ("uk", "і та"),
            ("ru", "без"),
            ("en", "!!!"),
        ):
            with self.subTest(locale=locale, alias=alias), self.assertRaises(ValidationError):
                validate_semantic_revision(
                    status="verified",
                    source="manager",
                    aliases={locale: [alias]},
                    traits={"back_decoration": "none"},
                    verified_by=self.verifier,
                    verified_at=timezone.now(),
                )

    def test_multiword_product_alias_is_valid_for_verification(self):
        normalized = validate_semantic_revision(
            status="verified",
            source="manager",
            aliases={
                "en": ["Black Raven classic T-shirt"],
                "uk": ["Чорна футболка Бойова квіточка"],
                "ru": ["Черная футболка Боевая ромашка"],
            },
            traits={"front_decoration": "logo", "back_decoration": "none"},
            verified_by=self.verifier,
            verified_at=timezone.now(),
        )

        self.assertEqual(normalized["aliases"]["en"], ["black raven classic t-shirt"])

    def test_generic_alias_may_remain_an_unverified_draft_suggestion(self):
        normalized = validate_semantic_revision(
            status="draft",
            source="bot_vision",
            aliases={"en": ["black"]},
            traits={"back_decoration": "none"},
        )

        self.assertEqual(normalized["aliases"], {"en": ["black"]})

    def test_revocation_tombstone_removes_verified_revision_from_effective_truth(self):
        verified = self.create_verified_revision()

        revoked = create_semantic_revision(
            profile=self.profile,
            status="revoked",
            source="manager",
            aliases=verified.aliases,
            traits=verified.traits,
            supersedes=verified,
            verified_by=self.verifier,
            verified_at=timezone.now(),
        )

        self.assertEqual(revoked.supersedes, verified)
        self.assertIsNone(get_effective_verified_revision(self.profile))

    def test_new_verified_revision_supersedes_old_effective_revision(self):
        first = self.create_verified_revision()

        second = create_semantic_revision(
            profile=self.profile,
            status="verified",
            source="manager",
            aliases={"en": ["Raven black T-shirt"]},
            traits={"front_decoration": "print", "back_decoration": "none"},
            verified_by=self.verifier,
            verified_at=timezone.now(),
        )

        self.assertEqual(second.supersedes, first)
        self.assertEqual(get_effective_verified_revision(self.profile), second)

    def test_invalid_or_cross_profile_revocation_is_rejected(self):
        first = self.create_verified_revision()
        other_product = Product.objects.create(
            title="Other semantic product",
            slug="other-semantic-product",
            category=self.category,
            price=1000,
        )
        other_profile = ProductSalesSemanticProfile.objects.create(product=other_product)

        with self.assertRaises(ValidationError):
            create_semantic_revision(
                profile=other_profile,
                status="revoked",
                source="manager",
                aliases=first.aliases,
                traits=first.traits,
                supersedes=first,
                verified_by=self.verifier,
                verified_at=timezone.now(),
            )
        with self.assertRaises(ValidationError):
            create_semantic_revision(
                profile=other_profile,
                status="revoked",
                source="manager",
                aliases={},
                traits={},
                verified_by=self.verifier,
                verified_at=timezone.now(),
            )

    def test_stale_concurrent_verified_target_cannot_create_second_effective_head(self):
        first = self.create_verified_revision()
        second = create_semantic_revision(
            profile=self.profile,
            status="verified",
            source="manager",
            aliases={"en": ["Raven black T-shirt"]},
            traits={"back_decoration": "none"},
            supersedes=first,
            verified_by=self.verifier,
            verified_at=timezone.now(),
        )

        with self.assertRaises(ValidationError):
            create_semantic_revision(
                profile=self.profile,
                status="verified",
                source="manager",
                aliases={"en": ["Raven white T-shirt"]},
                traits={"back_decoration": "none"},
                supersedes=first,
                verified_by=self.verifier,
                verified_at=timezone.now(),
            )
        self.assertEqual(get_effective_verified_revision(self.profile), second)

    def test_draft_suggestions_are_normalized_but_are_not_commerce_truth(self):
        revision = create_semantic_revision(
            profile=self.profile,
            status="draft",
            source="bot_vision",
            aliases={
                "UK": ["  Чорна   Футболка ", "чорна футболка"],
                "ru": ["  ЧЕРНАЯ ФУТБОЛКА  "],
                "en": [" Black   T-Shirt "],
            },
            traits={"front_decoration": "logo", "back_decoration": "none"},
        )

        self.assertEqual(
            revision.aliases,
            {
                "uk": ["чорна футболка"],
                "ru": ["черная футболка"],
                "en": ["black t-shirt"],
            },
        )
        self.assertEqual(revision.status, "draft")
        self.assertIsNone(revision.verified_by)
        self.assertIsNone(revision.verified_at)

    def test_aliases_accept_only_supported_locales_and_nonempty_string_lists(self):
        invalid_aliases = (
            [],
            {"de": ["shirt"]},
            {"uk": "футболка"},
            {"uk": [""]},
            {"uk": [123]},
        )

        for aliases in invalid_aliases:
            with self.subTest(aliases=aliases), self.assertRaises(ValidationError):
                validate_semantic_revision(
                    status="draft",
                    source="free_text",
                    aliases=aliases,
                    traits={"back_decoration": "none"},
                )

    def test_traits_accept_only_controlled_keys_and_codes(self):
        invalid_traits = (
            [],
            {"unknown_trait": "none"},
            {"back_decoration": "maybe"},
            {"hem_construction": "drawstring"},
        )

        for traits in invalid_traits:
            with self.subTest(traits=traits), self.assertRaises(ValidationError):
                validate_semantic_revision(
                    status="draft",
                    source="manager",
                    aliases={"uk": ["футболка"]},
                    traits=traits,
                )


class ProductSalesSemanticRevisionAdminTests(ProductSalesSemanticRevisionTests):
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.model_admin = ProductSalesSemanticProfileRevisionAdmin(
            ProductSalesSemanticProfileRevision,
            admin.site,
        )

    def request(self):
        request = self.factory.post("/admin/storefront/semantics/")
        request.user = self.verifier
        return request

    def test_admin_edit_creates_a_new_draft_revision(self):
        original = self.create_verified_revision()
        original_pk = original.pk
        original.aliases = {"en": ["Black logo shirt"]}

        self.model_admin.save_model(self.request(), original, form=None, change=True)

        self.assertEqual(self.profile.revisions.count(), 2)
        original = self.profile.revisions.get(pk=original_pk)
        created = self.profile.revisions.get(revision=2)
        self.assertEqual(original.status, "verified")
        self.assertEqual(
            original.aliases,
            {"uk": ["чорна футболка raven"], "ru": ["черная футболка raven"]},
        )
        self.assertEqual(created.status, "draft")
        self.assertEqual(created.aliases, {"en": ["black logo shirt"]})
        self.assertIsNone(created.verified_by)

    def test_admin_change_form_validates_before_cloning_revision(self):
        original = self.create_verified_revision()
        request = self.request()
        form_class = self.model_admin.get_form(request, original)
        form = form_class(
            data={
                "schema_version": 1,
                "aliases": json.dumps({"en": ["Black Raven logo shirt"]}),
                "traits": json.dumps({"front_decoration": "logo"}),
                "source": "manager",
            },
            instance=original,
        )

        self.assertTrue(form.is_valid(), form.errors.as_text())

    def test_admin_verify_and_revoke_actions_append_new_revisions(self):
        draft = create_semantic_revision(
            profile=self.profile,
            status="draft",
            source="free_text",
            aliases={"uk": ["футболка Raven з лого"]},
            traits={"front_decoration": "logo"},
        )

        self.model_admin.verify_revisions(
            self.request(),
            ProductSalesSemanticProfileRevision.objects.filter(pk=draft.pk),
        )
        verified = self.profile.revisions.get(revision=2)
        self.assertEqual(verified.status, "verified")
        self.assertEqual(verified.source, "manager")
        self.assertEqual(verified.verified_by, self.verifier)
        self.assertIsNotNone(verified.verified_at)

        self.model_admin.revoke_revisions(
            self.request(),
            ProductSalesSemanticProfileRevision.objects.filter(pk=verified.pk),
        )
        revoked = self.profile.revisions.get(revision=3)
        self.assertEqual(revoked.status, "revoked")
        self.assertEqual(verified.status, "verified")


class ProductSalesSemanticMigrationTests(SimpleTestCase):
    def test_migration_installs_working_append_only_triggers(self):
        script = textwrap.dedent(
            """
            import json
            import os
            import sys

            os.environ["DJANGO_SETTINGS_MODULE"] = "twocomms.settings"
            from django.conf import settings

            settings.DATABASES["default"] = {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": sys.argv[1],
            }

            import django
            django.setup()

            from django.db import DatabaseError, connection
            from django.db.migrations.executor import MigrationExecutor

            target = ("storefront", "0088_product_sales_semantic_profiles")
            executor = MigrationExecutor(connection)
            executor.migrate([target])

            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='trigger' "
                    "AND name IN ('sf_sem_rev_no_update', 'sf_sem_rev_no_delete') "
                    "ORDER BY name"
                )
                trigger_names = [row[0] for row in cursor.fetchall()]
                cursor.execute(
                    "INSERT INTO storefront_productsalessemanticprofile "
                    "(product_id, created_at, effective_revision_id) "
                    "VALUES (%s, CURRENT_TIMESTAMP, NULL)",
                    [999999],
                )
                profile_id = cursor.lastrowid
                cursor.execute(
                    "INSERT INTO storefront_productsalessemanticprofilerevision "
                    "(profile_id, supersedes_id, revision, status, schema_version, "
                    "aliases, traits, source, verified_by_id, verified_at, created_at) "
                    "VALUES (%s, NULL, 1, 'draft', 1, '{}', '{}', 'migration', "
                    "NULL, NULL, CURRENT_TIMESTAMP)",
                    [profile_id],
                )
                revision_id = cursor.lastrowid

            guarded = {}
            for operation, sql in (
                (
                    "update",
                    "UPDATE storefront_productsalessemanticprofilerevision "
                    "SET traits = '{}' WHERE id = %s",
                ),
                (
                    "delete",
                    "DELETE FROM storefront_productsalessemanticprofilerevision "
                    "WHERE id = %s",
                ),
            ):
                try:
                    with connection.cursor() as cursor:
                        cursor.execute(sql, [revision_id])
                except DatabaseError:
                    guarded[operation] = True
                else:
                    guarded[operation] = False

            print("MIGRATION_RESULT=" + json.dumps({
                "triggers": trigger_names,
                "guarded": guarded,
            }, sort_keys=True))
            """
        )
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        env = os.environ.copy()
        for key in ("DB_ENGINE", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT"):
            env.pop(key, None)
        env["PYTHONPATH"] = os.pathsep.join(
            filter(None, (project_root, env.get("PYTHONPATH", "")))
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            result = subprocess.run(
                [sys.executable, "-c", script, os.path.join(temp_dir, "migration.sqlite3")],
                cwd=project_root,
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        marker = next(
            line for line in result.stdout.splitlines() if line.startswith("MIGRATION_RESULT=")
        )
        payload = json.loads(marker.removeprefix("MIGRATION_RESULT="))
        self.assertEqual(
            payload,
            {
                "guarded": {"delete": True, "update": True},
                "triggers": ["sf_sem_rev_no_delete", "sf_sem_rev_no_update"],
            },
        )
