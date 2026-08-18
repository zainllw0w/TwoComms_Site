import json
from io import BytesIO
from pathlib import Path
from datetime import timedelta
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from storefront.models import Category, Product, ProductImage

from product_catalog.models import FeedImageRule, FeedOnlyImage, FeedProfile
from product_catalog.models import ImageOptimizationJob
from product_catalog.services import feed_image_urls


class ProductCatalogEditorAccessTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Test", slug="test")
        self.product = Product.objects.create(
            title="Test product",
            slug="test-product",
            category=self.category,
            price=500,
        )
        self.staff = get_user_model().objects.create_user(
            username="product_catalog-staff",
            password="test-password",
            is_staff=True,
        )

    def test_editor_rejects_anonymous_users(self):
        response = self.client.get(reverse("product_catalog_product_new"))

        self.assertEqual(response.status_code, 403)

    def test_editor_bootstrap_cannot_break_out_of_json_script(self):
        self.product.title = '</script><script id="injected">alert(1)</script>'
        self.product.save(update_fields=["title"])
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("product_catalog_product_edit", args=[self.product.pk])
        )
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('<script id="injected">', content)
        self.assertIn(r"\u003C/script\u003E", content)

    def test_editor_uses_fresh_dirty_tracking_javascript_asset(self):
        self.client.force_login(self.staff)

        content = self.client.get(
            reverse("product_catalog_product_edit", args=[self.product.pk])
        ).content.decode()

        self.assertIn("product_catalog/editor-inventory.js?v=20260716-inventory-v3", content)
        self.assertIn("product_catalog/editor.js?v=20260811-catalog-editor-v6", content)

    def test_staff_can_create_product_with_unified_save_endpoint(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("product_catalog_api_product_save"),
            data={
                "payload": json.dumps(
                    {
                        "title": "Нова термо футболка",
                        "category_id": self.category.pk,
                        "price": 1200,
                        "status": "draft",
                    }
                )
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        created = Product.objects.get(pk=body["product"]["id"])
        self.assertEqual(created.title, "Нова термо футболка")
        self.assertEqual(created.price, 1200)
        self.assertEqual(created.status, "draft")

    def test_product_save_rejects_discount_percent_above_server_limit(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("product_catalog_api_product_save"),
            data={
                "payload": json.dumps(
                    {
                        "id": self.product.pk,
                        "title": self.product.title,
                        "category_id": self.category.pk,
                        "price": self.product.price,
                        "discount_percent": 101,
                    }
                )
            },
        )

        self.assertEqual(response.status_code, 400)
        self.product.refresh_from_db()
        self.assertNotEqual(self.product.discount_percent, 101)

    def test_product_save_rejects_negative_discount_percent(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("product_catalog_api_product_save"),
            data={
                "payload": json.dumps(
                    {
                        "id": self.product.pk,
                        "title": self.product.title,
                        "category_id": self.category.pk,
                        "price": self.product.price,
                        "discount_percent": -1,
                    }
                )
            },
        )

        self.assertEqual(response.status_code, 400)
        self.product.refresh_from_db()
        self.assertNotEqual(self.product.discount_percent, -1)

    def test_feed_rule_rejects_an_image_owned_by_another_product(self):
        other = Product.objects.create(
            title="Other product",
            slug="other-product",
            category=self.category,
            price=700,
        )
        foreign_image = ProductImage.objects.create(
            product=other,
            image="products/extra/foreign.webp",
        )
        feed = FeedProfile.objects.create(name="Google", slug="google")
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("product_catalog_api_feed_rule_save"),
            data=json.dumps(
                {
                    "product_id": self.product.pk,
                    "feed_id": feed.pk,
                    "image_rules": [{"product_image_id": foreign_image.pk}],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            FeedImageRule.objects.filter(feed=feed, product=self.product).exists()
        )

    def test_gallery_upload_rejects_non_image_content(self):
        self.client.force_login(self.staff)
        fake_image = SimpleUploadedFile(
            "payload.php",
            b"<?php echo 'not an image'; ?>",
            content_type="image/png",
        )

        response = self.client.post(
            reverse("product_catalog_api_images_upload"),
            data={
                "product_id": self.product.pk,
                "kind": "product",
                "files": [fake_image],
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(ProductImage.objects.filter(product=self.product).exists())

    def test_setting_gallery_image_as_cover_records_its_source(self):
        from product_catalog.models import CoverSource

        image = ProductImage.objects.create(
            product=self.product,
            image="products/extra/cover-source.webp",
            alt_text="Cover source",
        )
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("product_catalog_api_set_cover"),
            data=json.dumps({
                "product_id": self.product.pk,
                "kind": "product",
                "image_id": image.pk,
                "target": "main",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        source = CoverSource.objects.get(product=self.product)
        self.assertEqual(source.source_type, CoverSource.SourceType.PRODUCT_IMAGE)
        self.assertEqual(source.product_image, image)
        self.assertEqual(response.json()["cover_source"]["product_image_id"], image.pk)

    @patch("product_catalog.image_jobs.schedule_image_optimization")
    def test_deleting_home_card_only_gallery_image_clears_the_override(self, schedule):
        image = ProductImage.objects.create(
            product=self.product,
            image="products/extra/home-card-only.webp",
        )
        self.product.home_card_image = image.image.name
        self.product.save(update_fields=["home_card_image"])
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("product_catalog_api_image_update"),
            data=json.dumps({
                "product_id": self.product.pk,
                "kind": "product",
                "id": image.pk,
                "delete": True,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.product.refresh_from_db()
        self.assertFalse(self.product.home_card_image)
        self.assertEqual(response.json()["home_card_image_url"], "")

    def test_home_card_override_can_be_reset_to_the_main_cover(self):
        self.product.main_image = "products/qa/main.webp"
        self.product.home_card_image = "products/qa/home.webp"
        self.product.save(update_fields=["main_image", "home_card_image"])
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("product_catalog_api_set_cover"),
            data=json.dumps({
                "product_id": self.product.pk,
                "target": "home_card",
                "reset": True,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.product.refresh_from_db()
        self.assertFalse(self.product.home_card_image)
        self.assertEqual(response.json()["home_card_image_url"], "")
        self.assertTrue(response.json()["main_image_url"].endswith("/products/qa/main.webp"))

    def test_home_card_reset_control_is_wired_instead_of_disabled(self):
        template = (
            Path(__file__).resolve().parents[1]
            / "templates"
            / "product_catalog"
            / "editor.html"
        ).read_text(encoding="utf-8")
        javascript = (
            Path(__file__).resolve().parents[1]
            / "static"
            / "product_catalog"
            / "editor.js"
        ).read_text(encoding="utf-8")

        self.assertIn('id="f-home-image-reset"', template)
        self.assertNotIn("Скидання буде доступне після підключення", template)
        self.assertIn("resetHomeCardOverride", javascript)

    def test_editor_css_preserves_hidden_buttons_and_wraps_mobile_actions(self):
        css = (
            Path(__file__).resolve().parents[1]
            / "static"
            / "product_catalog"
            / "editor.css"
        ).read_text(encoding="utf-8")

        self.assertIn(".catalog-editor-btn[hidden]", css)
        self.assertIn(".catalog-editor-topbar__actions { width: 100%; flex-wrap: wrap; }", css)

    def test_editor_price_fields_can_shrink_inside_desktop_card(self):
        css = (
            Path(__file__).resolve().parents[1]
            / "static"
            / "product_catalog"
            / "editor.css"
        ).read_text(encoding="utf-8")
        template = (
            Path(__file__).resolve().parents[1]
            / "templates"
            / "product_catalog"
            / "editor.html"
        ).read_text(encoding="utf-8")

        self.assertIn(".catalog-editor-price-fields .catalog-editor-field { min-width: 0; }", css)
        self.assertIn("product_catalog/editor.css' %}?v=20260811-catalog-editor-v8", template)

    def test_print_picker_uses_only_print_artwork_and_marks_selection_state(self):
        javascript = (
            Path(__file__).resolve().parents[1]
            / "static"
            / "product_catalog"
            / "editor.js"
        ).read_text(encoding="utf-8")
        helper = (
            Path(__file__).resolve().parents[1]
            / "static"
            / "product_catalog"
            / "editor-catalog.js"
        ).read_text(encoding="utf-8")

        self.assertNotIn('image_source === "product"', javascript)
        self.assertNotIn('image_source === "product"', helper)
        self.assertIn('image_source === "print"', helper)
        self.assertIn('selected ? "Вибрано"', javascript)
        self.assertIn('selectedPrintIds', javascript)

    def test_collection_parent_state_rerenders_immediately_after_leaf_selection(self):
        javascript = (
            Path(__file__).resolve().parents[1]
            / "static"
            / "product_catalog"
            / "editor.js"
        ).read_text(encoding="utf-8")

        self.assertIn("renderCollectionOptions();", javascript)
        self.assertIn("data-collection-derived", javascript)


class ProductCatalogImageJobTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Images", slug="images")
        self.product = Product.objects.create(
            title="Image job product",
            slug="image-job-product",
            category=self.category,
            price=500,
        )
        self.other_product = Product.objects.create(
            title="Other image job product",
            slug="other-image-job-product",
            category=self.category,
            price=500,
        )
        self.staff = get_user_model().objects.create_user(
            username="image-job-staff",
            password="test-password",
            is_staff=True,
        )

    def _png(self, name="gallery.png"):
        # A valid one-pixel PNG keeps the API test independent from Pillow's encoders.
        return SimpleUploadedFile(
            name,
            (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
                b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
                b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
            ),
            content_type="image/png",
        )

    def _oversized_png(self, name="oversized.png"):
        return SimpleUploadedFile(
            name,
            b"x" * ((15 * 1024 * 1024) + 1),
            content_type="image/png",
        )

    def _high_pixel_png(self, name="too-many-pixels.png"):
        from PIL import Image

        payload = BytesIO()
        Image.new("1", (10_000, 6_000)).save(payload, format="PNG")
        return SimpleUploadedFile(
            name,
            payload.getvalue(),
            content_type="image/png",
        )

    def test_request_path_never_starts_an_image_worker(self):
        from product_catalog import image_jobs

        self.assertFalse(hasattr(image_jobs, "_IMAGE_JOB_EXECUTOR"))
        self.assertFalse(hasattr(image_jobs, "_IMAGE_JOB_SCHEDULED"))
        self.assertIsNone(image_jobs.schedule_image_optimization(123))

    def test_image_jobs_persist_a_runner_lease(self):
        self.assertIn(
            "lease_token",
            {field.name for field in ImageOptimizationJob._meta.local_fields},
        )

    @patch("storefront.tasks.optimize_image_field_task", side_effect=RuntimeError("AVIF encoder failed"))
    def test_failed_job_keeps_the_last_backend_stage_for_diagnostics(self, optimize):
        image = ProductImage.objects.create(
            product=self.product,
            image=self._png("failed-stage.png"),
        )
        job = ImageOptimizationJob.objects.filter(
            model_label="storefront.productimage",
            object_id=image.pk,
            field_name="image",
        ).latest("id")

        from product_catalog.image_jobs import run_image_optimization_job

        run_image_optimization_job(job.pk)

        job.refresh_from_db()
        self.assertEqual(job.status, ImageOptimizationJob.Status.ERROR)
        self.assertEqual(job.stage, "loading")
        self.assertEqual(job.progress, 5)
        self.assertIn("AVIF encoder failed", job.error_message)

    def test_image_job_model_indexes_the_reconciliation_queue(self):
        indexes = {
            index.name: tuple(index.fields)
            for index in ImageOptimizationJob._meta.indexes
        }
        self.assertEqual(
            indexes["pc_job_status_upd_9f3d_idx"],
            ("status", "-updated_at"),
        )
        self.assertEqual(
            indexes["pc_job_status_crt_9f3d_idx"],
            ("status", "created_at"),
        )

    def test_reconcile_command_cleans_only_old_terminal_jobs(self):
        old_completed = ImageOptimizationJob.objects.create(
            model_label="storefront.productimage",
            object_id=self.product.pk,
            field_name="image",
            status=ImageOptimizationJob.Status.COMPLETED,
            stage="ready",
        )
        old_cancelled = ImageOptimizationJob.objects.create(
            model_label="storefront.productimage",
            object_id=self.product.pk,
            field_name="image",
            status=ImageOptimizationJob.Status.CANCELLED,
            stage="cancelled",
        )
        recent_error = ImageOptimizationJob.objects.create(
            model_label="storefront.productimage",
            object_id=self.product.pk,
            field_name="image",
            status=ImageOptimizationJob.Status.ERROR,
            stage="avif",
        )
        old_cutoff = timezone.now() - timedelta(days=31)
        ImageOptimizationJob.objects.filter(
            pk__in=(old_completed.pk, old_cancelled.pk)
        ).update(updated_at=old_cutoff)

        call_command(
            "reconcile_image_optimization_jobs",
            max_jobs=1,
            retention_days=30,
            cleanup_limit=10,
            verbosity=0,
        )

        self.assertFalse(
            ImageOptimizationJob.objects.filter(
                pk__in=(old_completed.pk, old_cancelled.pk)
            ).exists()
        )
        self.assertTrue(ImageOptimizationJob.objects.filter(pk=recent_error.pk).exists())

    def test_reconcile_command_retains_latest_job_for_derivative_health_checks(self):
        image = ProductImage.objects.create(
            product=self.product,
            image="products/extra/retained-health-check.webp",
        )
        job = ImageOptimizationJob.objects.filter(
            model_label="storefront.productimage",
            object_id=image.pk,
            field_name="image",
        ).latest("id")
        ImageOptimizationJob.objects.filter(pk=job.pk).update(
            status=ImageOptimizationJob.Status.COMPLETED,
            stage="ready",
            progress=100,
            completed_at=timezone.now() - timedelta(days=31),
            updated_at=timezone.now() - timedelta(days=31),
        )

        call_command(
            "reconcile_image_optimization_jobs",
            max_jobs=1,
            retention_days=30,
            cleanup_limit=10,
            verbosity=0,
        )

        self.assertTrue(ImageOptimizationJob.objects.filter(pk=job.pk).exists())
        from product_catalog.image_jobs import image_job_payload

        payload = image_job_payload(image, "image")
        self.assertEqual(payload["status"], ImageOptimizationJob.Status.ERROR)
        self.assertIn("відсутні", payload["error_message"])

    @patch("product_catalog.management.commands.reconcile_image_optimization_jobs.run_image_optimization_job")
    def test_reconcile_command_requeues_stale_jobs_and_processes_pending(self, run_job):
        stale = ImageOptimizationJob.objects.create(
            model_label="storefront.productimage",
            object_id=self.product.pk,
            field_name="image",
            status=ImageOptimizationJob.Status.RUNNING,
            stage="optimizing",
            updated_at=timezone.now() - timedelta(minutes=31),
        )
        ImageOptimizationJob.objects.filter(pk=stale.pk).update(
            updated_at=timezone.now() - timedelta(minutes=31)
        )
        pending = ImageOptimizationJob.objects.create(
            model_label="storefront.productimage",
            object_id=self.product.pk,
            field_name="image",
            status=ImageOptimizationJob.Status.PENDING,
            stage="queued",
        )

        call_command("reconcile_image_optimization_jobs", max_jobs=2, verbosity=0)

        stale.refresh_from_db()
        self.assertEqual(stale.status, ImageOptimizationJob.Status.PENDING)
        self.assertEqual(stale.stage, "queued")
        self.assertEqual(
            {call.args[0] for call in run_job.call_args_list},
            {stale.pk, pending.pk},
        )

    @patch("product_catalog.image_jobs.schedule_image_optimization")
    def test_editor_poll_does_not_requeue_a_job_before_the_cron_timeout(self, schedule):
        from product_catalog.image_jobs import resume_image_optimization

        self.product.main_image = "products/qa/slow-avif.png"
        self.product.save(update_fields=["main_image"])
        running = ImageOptimizationJob.objects.create(
            model_label="storefront.product",
            object_id=self.product.pk,
            field_name="main_image",
            source_name=self.product.main_image.name,
            status=ImageOptimizationJob.Status.RUNNING,
            stage="avif",
            progress=50,
        )
        ImageOptimizationJob.objects.filter(pk=running.pk).update(
            updated_at=timezone.now() - timedelta(minutes=10)
        )

        resumed = resume_image_optimization(self.product, "main_image")

        resumed.refresh_from_db()
        self.assertEqual(resumed.status, ImageOptimizationJob.Status.RUNNING)
        self.assertEqual(resumed.stage, "avif")
        schedule.assert_not_called()

    @patch("product_catalog.image_jobs.schedule_image_optimization")
    def test_gallery_upload_returns_persisted_pending_job(self, schedule):
        self.client.force_login(self.staff)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("product_catalog_api_images_upload"),
                data={"product_id": self.product.pk, "target": "product", "files": [self._png()]},
            )

        self.assertEqual(response.status_code, 200)
        image_payload = response.json()["images"][0]
        job_payload = image_payload["job"]
        job = ImageOptimizationJob.objects.get(pk=job_payload["id"])
        self.assertEqual(job.status, ImageOptimizationJob.Status.PENDING)
        self.assertEqual(job.object_id, image_payload["id"])
        self.assertEqual(job_payload["stage"], "queued")
        schedule.assert_called_once_with(job.pk)

    @patch("product_catalog.image_jobs.schedule_image_optimization")
    def test_product_save_with_cover_uploads_uses_signal_jobs_without_legacy_runner(
        self, schedule
    ):
        self.client.force_login(self.staff)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("product_catalog_api_product_save"),
                data={
                    "payload": json.dumps(
                        {
                            "id": self.product.pk,
                            "title": self.product.title,
                            "category_id": self.category.pk,
                            "price": self.product.price,
                            "status": "draft",
                        }
                    ),
                    "main_image": self._png("main-cover.png"),
                    "home_card_image": self._png("home-cover.png"),
                },
            )

        self.assertEqual(response.status_code, 200)
        jobs = ImageOptimizationJob.objects.filter(
            model_label="storefront.product", object_id=self.product.pk
        ).order_by("field_name")
        self.assertEqual(
            list(jobs.values_list("field_name", "status")),
            [
                ("home_card_image", ImageOptimizationJob.Status.PENDING),
                ("main_image", ImageOptimizationJob.Status.PENDING),
            ],
        )
        self.assertEqual(schedule.call_count, 2)

    @patch(
        "product_catalog.image_jobs.schedule_image_optimization",
        side_effect=RuntimeError("executor unavailable"),
    )
    def test_scheduler_failure_after_commit_does_not_turn_created_product_into_500(
        self, schedule
    ):
        self.client.force_login(self.staff)
        before = Product.objects.count()

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("product_catalog_api_product_save"),
                data={
                    "payload": json.dumps(
                        {
                            "title": "Committed despite scheduler outage",
                            "category_id": self.category.pk,
                            "price": 700,
                            "status": "draft",
                        }
                    ),
                    "main_image": self._png("commit-safe-cover.png"),
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Product.objects.count(), before + 1)
        self.assertTrue(response.json()["created"])
        schedule.assert_called_once()

    def test_gallery_rejects_images_larger_than_advertised_limit(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("product_catalog_api_images_upload"),
            data={
                "product_id": self.product.pk,
                "target": "product",
                "files": [self._oversized_png()],
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("15 МБ", response.json()["error"])
        self.assertFalse(self.product.images.exists())

    def test_product_cover_rejects_images_larger_than_advertised_limit(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("product_catalog_api_product_save"),
            data={
                "payload": json.dumps(
                    {
                        "id": self.product.pk,
                        "title": self.product.title,
                        "category_id": self.category.pk,
                        "price": self.product.price,
                    }
                ),
                "main_image": self._oversized_png("oversized-cover.png"),
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("15 МБ", response.json()["error"])

    def test_feed_only_upload_rejects_images_larger_than_advertised_limit(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("product_catalog_api_feed_image_upload"),
            data={
                "product_id": self.product.pk,
                "files": [self._oversized_png("oversized-feed.png")],
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("15 МБ", response.json()["error"])
        self.assertFalse(FeedOnlyImage.objects.filter(product=self.product).exists())

    def test_gallery_rejects_excessive_pixel_dimensions_before_intake(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("product_catalog_api_images_upload"),
            data={
                "product_id": self.product.pk,
                "target": "product",
                "files": [self._high_pixel_png()],
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("50 мегапікселів", response.json()["error"])
        self.assertFalse(self.product.images.exists())

    def test_enqueue_cancels_an_older_active_job_for_the_same_image_field(self):
        image = ProductImage.objects.create(
            product=self.product,
            image="products/extra/replaced-source.webp",
        )
        first_job = ImageOptimizationJob.objects.filter(
            model_label="storefront.productimage",
            object_id=image.pk,
            field_name="image",
        ).latest("id")

        from product_catalog.image_jobs import enqueue_image_optimization

        second_job = enqueue_image_optimization(image, "image")

        first_job.refresh_from_db()
        self.assertEqual(first_job.status, ImageOptimizationJob.Status.CANCELLED)
        self.assertEqual(second_job.status, ImageOptimizationJob.Status.PENDING)
        self.assertEqual(
            ImageOptimizationJob.objects.filter(
                model_label="storefront.productimage",
                object_id=image.pk,
                field_name="image",
                status__in=(
                    ImageOptimizationJob.Status.PENDING,
                    ImageOptimizationJob.Status.RUNNING,
                ),
            ).count(),
            1,
        )

    @patch("storefront.tasks.optimize_image_field_task")
    def test_runner_does_not_start_a_job_that_is_already_running(self, optimize):
        image = ProductImage.objects.create(
            product=self.product,
            image="products/extra/already-running.webp",
        )
        job = ImageOptimizationJob.objects.filter(
            model_label="storefront.productimage",
            object_id=image.pk,
            field_name="image",
        ).latest("id")
        job.status = ImageOptimizationJob.Status.RUNNING
        job.stage = "optimizing"
        job.save(update_fields=("status", "stage", "updated_at"))

        from product_catalog.image_jobs import run_image_optimization_job

        run_image_optimization_job(job.pk)

        optimize.assert_not_called()

    @patch(
        "storefront.services.image_variants.optimized_variants_are_current",
        return_value=True,
    )
    @patch("storefront.tasks.optimize_image_field_task")
    def test_cancellation_wins_over_a_late_optimizer_completion(
        self, optimize, variants_are_current
    ):
        image = ProductImage.objects.create(
            product=self.product,
            image=self._png("cancel-during-optimization.png"),
        )
        job = ImageOptimizationJob.objects.filter(
            model_label="storefront.productimage",
            object_id=image.pk,
            field_name="image",
        ).latest("id")

        from product_catalog.image_jobs import cancel_image_jobs, run_image_optimization_job

        optimize.side_effect = lambda *args: cancel_image_jobs(image, "image")
        run_image_optimization_job(job.pk)

        job.refresh_from_db()
        self.assertEqual(job.status, ImageOptimizationJob.Status.CANCELLED)
        variants_are_current.assert_called_once()

    @patch(
        "storefront.services.image_variants.optimized_variants_are_current",
        return_value=True,
    )
    @patch("storefront.tasks.optimize_image_field_task")
    def test_reclaimed_job_ignores_a_late_runner_completion(
        self, optimize, variants_are_current
    ):
        image = ProductImage.objects.create(
            product=self.product,
            image=self._png("reclaimed-during-optimization.png"),
        )
        job = ImageOptimizationJob.objects.filter(
            model_label="storefront.productimage",
            object_id=image.pk,
            field_name="image",
        ).latest("id")

        def reclaim(*_args, **_kwargs):
            ImageOptimizationJob.objects.filter(pk=job.pk).update(
                status=ImageOptimizationJob.Status.RUNNING,
                stage="replacement-runner",
                progress=15,
                lease_token="replacement-lease",
                attempts=2,
            )

        optimize.side_effect = reclaim

        from product_catalog.image_jobs import run_image_optimization_job

        run_image_optimization_job(job.pk)

        job.refresh_from_db()
        self.assertEqual(job.status, ImageOptimizationJob.Status.RUNNING)
        self.assertEqual(job.stage, "replacement-runner")
        self.assertEqual(job.lease_token, "replacement-lease")
        variants_are_current.assert_called_once()

    @patch("product_catalog.image_jobs.schedule_image_optimization")
    def test_completed_job_with_missing_derivatives_exposes_retry(self, schedule):
        image = ProductImage.objects.create(
            product=self.product,
            image=self._png("missing-derivatives.png"),
        )
        job = ImageOptimizationJob.objects.filter(
            model_label="storefront.productimage",
            object_id=image.pk,
            field_name="image",
        ).latest("id")
        ImageOptimizationJob.objects.filter(pk=job.pk).update(
            status=ImageOptimizationJob.Status.COMPLETED,
            stage="ready",
            progress=100,
            completed_at=timezone.now(),
        )

        from product_catalog.image_jobs import image_job_payload, retry_image_optimization

        payload = image_job_payload(image, "image")
        self.assertEqual(payload["status"], ImageOptimizationJob.Status.ERROR)
        self.assertIn("відсутні", payload["error_message"])

        with self.captureOnCommitCallbacks(execute=True):
            retried = retry_image_optimization(image, "image")

        retried.refresh_from_db()
        self.assertEqual(retried.status, ImageOptimizationJob.Status.PENDING)
        schedule.assert_called_once_with(job.pk)

    @patch("product_catalog.image_jobs.schedule_image_optimization")
    def test_legacy_image_without_job_exposes_retry_when_derivatives_are_missing(
        self, schedule
    ):
        image = ProductImage.objects.create(
            product=self.product,
            image=self._png("legacy-without-job.png"),
        )
        ImageOptimizationJob.objects.filter(
            model_label="storefront.productimage",
            object_id=image.pk,
            field_name="image",
        ).delete()

        from product_catalog.image_jobs import image_job_payload, retry_image_optimization

        payload = image_job_payload(image, "image")
        self.assertIsNone(payload["id"])
        self.assertEqual(payload["status"], ImageOptimizationJob.Status.ERROR)
        self.assertIn("відсутні", payload["error_message"])

        with self.captureOnCommitCallbacks(execute=True):
            retried = retry_image_optimization(image, "image")

        self.assertEqual(retried.status, ImageOptimizationJob.Status.PENDING)
        schedule.assert_called_once_with(retried.pk)

    def test_image_job_status_enforces_product_ownership(self):
        image = ProductImage.objects.create(
            product=self.other_product,
            image="products/extra/owned-by-other.webp",
        )
        job = ImageOptimizationJob.objects.create(
            model_label="storefront.productimage",
            object_id=image.pk,
            field_name="image",
        )
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("product_catalog_api_image_optimization_status"),
            {"product_id": self.product.pk, "kind": "product", "image_id": image.pk},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(ImageOptimizationJob.objects.get(pk=job.pk).status, job.status)

    @patch("product_catalog.image_jobs.schedule_image_optimization")
    def test_cover_job_status_resumes_a_persisted_pending_job(self, schedule):
        self.product.main_image = self._png("cover-status.png")
        self.product.save(update_fields=["main_image"])
        job = ImageOptimizationJob.objects.filter(
            model_label="storefront.product",
            object_id=self.product.pk,
            field_name="main_image",
        ).latest("id")
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("product_catalog_api_image_optimization_status"),
            {
                "product_id": self.product.pk,
                "kind": "cover",
                "field_name": "main_image",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["job"]["id"], job.pk)
        schedule.assert_called_once_with(job.pk)

    @patch("product_catalog.image_jobs.schedule_image_optimization")
    def test_retry_resets_failed_job_and_schedules_once(self, schedule):
        image = ProductImage.objects.create(
            product=self.product,
            image="products/extra/retry.webp",
        )
        job = ImageOptimizationJob.objects.create(
            model_label="storefront.productimage",
            object_id=image.pk,
            field_name="image",
            status=ImageOptimizationJob.Status.ERROR,
            progress=35,
            stage="error",
            error_message="optimizer unavailable",
        )
        self.client.force_login(self.staff)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("product_catalog_api_image_optimization_retry"),
                data=json.dumps({"product_id": self.product.pk, "kind": "product", "image_id": image.pk}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.status, ImageOptimizationJob.Status.PENDING)
        self.assertEqual(job.progress, 0)
        self.assertEqual(job.error_message, "")
        schedule.assert_called_once_with(job.pk)

    @patch("product_catalog.image_jobs.schedule_image_optimization")
    def test_retry_does_not_duplicate_an_already_pending_job(self, schedule):
        image = ProductImage.objects.create(
            product=self.product,
            image="products/extra/pending-retry.webp",
        )
        job = ImageOptimizationJob.objects.filter(
            model_label="storefront.productimage",
            object_id=image.pk,
            field_name="image",
        ).latest("id")
        self.client.force_login(self.staff)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("product_catalog_api_image_optimization_retry"),
                data=json.dumps(
                    {
                        "product_id": self.product.pk,
                        "kind": "product",
                        "image_id": image.pk,
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["job"]["id"], job.pk)
        self.assertEqual(
            ImageOptimizationJob.objects.filter(
                model_label="storefront.productimage",
                object_id=image.pk,
                field_name="image",
            ).count(),
            1,
        )
        schedule.assert_not_called()

    def test_feed_only_delete_cancels_its_active_optimization_job(self):
        image = FeedOnlyImage.objects.create(
            product=self.product,
            image="product_catalog/feed_images/delete-me.webp",
        )
        job = ImageOptimizationJob.objects.filter(
            model_label="product_catalog.feedonlyimage",
            object_id=image.pk,
            field_name="image",
        ).latest("id")

        image.delete()

        job.refresh_from_db()
        self.assertEqual(job.status, ImageOptimizationJob.Status.CANCELLED)

    def test_feed_bootstrap_restores_image_optimization_state(self):
        feed = FeedProfile.objects.create(name="Google jobs", slug="google-jobs")
        image = FeedOnlyImage.objects.create(
            product=self.product,
            feed=feed,
            image="product_catalog/feed_images/persisted-job.webp",
        )
        job = ImageOptimizationJob.objects.filter(
            model_label="product_catalog.feedonlyimage",
            object_id=image.pk,
            field_name="image",
        ).latest("id")
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("product_catalog_api_feeds"),
            {"product_id": self.product.pk},
        )

        self.assertEqual(response.status_code, 200)
        image_payload = response.json()["feed_only_images"][0]
        self.assertEqual(image_payload["job"]["id"], job.pk)
        self.assertEqual(image_payload["job"]["status"], job.status)

    @patch("product_catalog.image_jobs.schedule_image_optimization")
    def test_feed_only_image_job_status_uses_product_ownership(self, schedule):
        feed = FeedProfile.objects.create(name="Google status", slug="google-status")
        image = FeedOnlyImage.objects.create(
            product=self.product,
            feed=feed,
            image="product_catalog/feed_images/status.webp",
        )
        job = ImageOptimizationJob.objects.filter(
            model_label="product_catalog.feedonlyimage",
            object_id=image.pk,
            field_name="image",
        ).latest("id")
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("product_catalog_api_image_optimization_status"),
            {
                "product_id": self.product.pk,
                "kind": "feed",
                "image_id": image.pk,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["job"]["id"], job.pk)
        schedule.assert_called_once_with(job.pk)

    @patch("storefront.tasks.optimize_image_field_task", return_value=True)
    def test_late_runner_marks_deleted_image_job_cancelled(self, optimize):
        image = ProductImage.objects.create(
            product=self.product,
            image="products/extra/deleted.webp",
        )
        job = ImageOptimizationJob.objects.create(
            model_label="storefront.productimage",
            object_id=image.pk,
            field_name="image",
        )
        image.delete()

        from product_catalog.image_jobs import run_image_optimization_job

        run_image_optimization_job(job.pk)

        job.refresh_from_db()
        self.assertEqual(job.status, ImageOptimizationJob.Status.CANCELLED)
        optimize.assert_not_called()

    def test_editor_taxonomy_visual_states_have_focus_and_derived_styles(self):
        css = (
            Path(__file__).resolve().parents[1]
            / "static"
            / "product_catalog"
            / "editor.css"
        ).read_text(encoding="utf-8")

        self.assertIn(".catalog-editor-audience-option.is-derived", css)
        self.assertIn(".catalog-editor-collection-option.is-derived", css)
        self.assertIn(".catalog-editor-print-card:focus-within", css)
        self.assertNotIn("Light workspace controls", css)
        self.assertIn(".catalog-editor-cover__retry", css)

    def test_active_variant_rail_stays_dark_with_warm_operational_signal(self):
        css = (
            Path(__file__).resolve().parents[1]
            / "static"
            / "product_catalog"
            / "editor.css"
        ).read_text(encoding="utf-8")
        active_rule = css.split(".catalog-editor-rail-item.is-active", 1)[1].split("}", 1)[0]

        self.assertNotIn("#edf4ff", active_rule)
        self.assertIn("rgba(255,126,41", active_rule)

    def test_main_panel_uses_balanced_desktop_working_grids(self):
        root = Path(__file__).resolve().parents[1]
        template = (root / "templates" / "product_catalog" / "editor.html").read_text(
            encoding="utf-8"
        )
        css = (root / "static" / "product_catalog" / "editor.css").read_text(
            encoding="utf-8"
        )
        javascript = (root / "static" / "product_catalog" / "editor.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("catalog-editor-card--identity", template)
        self.assertIn("catalog-editor-card--commerce", template)
        self.assertIn("catalog-editor-essentials-board", template)
        self.assertIn(
            ".catalog-editor-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));",
            css,
        )
        self.assertIn(
            ".catalog-editor-taxonomy-grid { min-width: 0; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));",
            css,
        )
        self.assertIn(".catalog-editor-essentials-board {", css)
        self.assertIn("border: 1px solid var(--catalog-editor-line);", css)
        self.assertIn(".catalog-editor-essentials-board .catalog-editor-card--commerce { border-left: 1px solid var(--catalog-editor-line);", css)
        self.assertIn(
            ".catalog-editor-taxonomy-grid { min-width: 0; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; align-items: stretch; }",
            css,
        )
        self.assertIn('class="catalog-editor-row catalog-editor-row--catalog-meta"', template)
        self.assertIn(
            ".catalog-editor-row--catalog-meta { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); align-items: start; gap: 12px; }",
            css,
        )
        self.assertIn("catalog-editor-hint catalog-editor-row-note", template)
        self.assertIn(".catalog-editor-row-note { grid-column: 3;", css)
        self.assertIn("max-height: 172px;", css)
        self.assertIn('data-kind-label="${esc(collectionKindLabel(item))}"', javascript)
        self.assertIn('theme: "Тема"', javascript)
        self.assertNotIn('data-kind="${esc(item.kind)}"', javascript)
        self.assertIn(".catalog-editor-collection-option.is-derived { border-style: solid;", css)
        self.assertIn(".catalog-editor-audience-option.is-derived { border-style: solid;", css)

    def test_main_taxonomy_controls_are_compact_and_use_the_current_stylesheet(self):
        root = Path(__file__).resolve().parents[1]
        template = (root / "templates" / "product_catalog" / "editor.html").read_text(
            encoding="utf-8"
        )
        css = (root / "static" / "product_catalog" / "editor.css").read_text(
            encoding="utf-8"
        )

        self.assertIn("catalog-editor-collection-library", template)
        self.assertIn("Змінити теми та підкатегорії", template)
        self.assertIn("product_catalog/editor.css' %}?v=20260811-catalog-editor-v8", template)
        self.assertIn(
            ".catalog-editor-collection-library summary::after { content: \"+\";",
            css,
        )
        self.assertIn(".catalog-editor-collection-options {", css)
        self.assertIn("max-height: 172px;", css)

    def test_unisex_is_a_master_selection_with_compact_derived_audiences(self):
        root = Path(__file__).resolve().parents[1]
        javascript = (root / "static" / "product_catalog" / "editor.js").read_text(
            encoding="utf-8"
        )
        css = (root / "static" / "product_catalog" / "editor.css").read_text(
            encoding="utf-8"
        )

        self.assertIn("catalog-editor-audience-option--master", javascript)
        self.assertIn("catalog-editor-audience-derived-group", javascript)
        self.assertIn("Автоматично в каталоги", javascript)
        self.assertIn(".catalog-editor-audience-derived-group", css)
        self.assertIn(".catalog-editor-audience-grid:has(.catalog-editor-audience-derived-group)", css)

    def test_variant_rerender_preserves_the_active_inner_pane(self):
        javascript = (
            Path(__file__).resolve().parents[1]
            / "static"
            / "product_catalog"
            / "editor.js"
        ).read_text(encoding="utf-8")

        self.assertIn('const activePane = variant._activePane || "overview";', javascript)
        self.assertIn(
            "variant._activePane = paneButton.dataset.variantPane;",
            javascript,
        )
        self.assertIn('variantPaneAttributes("photos", activePane)', javascript)
        self.assertNotIn('tabIndex === 0 ? " is-active"', javascript)

    def test_feed_images_use_the_same_progress_polling_pipeline(self):
        javascript = (
            Path(__file__).resolve().parents[1]
            / "static"
            / "product_catalog"
            / "editor.js"
        ).read_text(encoding="utf-8")

        self.assertIn("watchFeedImageJob", javascript)
        self.assertIn('kind: "feed"', javascript)
        self.assertIn("postFormWithProgress(urls.feed_image_upload", javascript)
        self.assertIn('const canRemove = !image.provisional || ui.status === "error";', javascript)

    def test_collection_picker_renders_depth_as_a_visual_hierarchy(self):
        javascript = (
            Path(__file__).resolve().parents[1]
            / "static"
            / "product_catalog"
            / "editor.js"
        ).read_text(encoding="utf-8")
        css = (
            Path(__file__).resolve().parents[1]
            / "static"
            / "product_catalog"
            / "editor.css"
        ).read_text(encoding="utf-8")

        self.assertIn('data-depth="${Math.max(0, Number(item.depth) || 0)}"', javascript)
        self.assertIn("groupCollections(rows)", javascript)
        self.assertIn("catalog-editor-collection-group", javascript)
        self.assertIn(".catalog-editor-collection-group", css)
        self.assertIn('.catalog-editor-collection-option[data-depth="1"]', css)

    def test_javascript_transliteration_matches_server_for_russian_yo(self):
        javascript = (
            Path(__file__).resolve().parents[1]
            / "static"
            / "product_catalog"
            / "editor.js"
        ).read_text(encoding="utf-8")

        self.assertIn('"ё": "yo"', javascript)

    def test_global_save_persists_only_dirty_or_unsaved_variant_drafts(self):
        javascript = (
            Path(__file__).resolve().parents[1]
            / "static"
            / "product_catalog"
            / "editor.js"
        ).read_text(encoding="utf-8")

        self.assertIn("pendingVariantDrafts", javascript)
        self.assertIn("for (const draft of pendingVariantDrafts)", javascript)
        self.assertIn("!variant.id || variant._dirty || card.dataset.dirty", javascript)
        self.assertIn('data-dirty="${variant._dirty ? "true" : "false"}"', javascript)
        self.assertIn(
            "state.variants[draft.index] = variantResp.variant",
            javascript,
        )

    def test_variant_payload_only_includes_sizes_after_inventory_changes(self):
        javascript = (
            Path(__file__).resolve().parents[1]
            / "static"
            / "product_catalog"
            / "editor.js"
        ).read_text(encoding="utf-8")

        self.assertIn('card.dataset.sizesDirty === "true"', javascript)
        self.assertIn("variant._sizesDirty", javascript)
        self.assertIn(
            "if (includeSizes) data.sizes = snapshotInventoryDraft(variant)",
            javascript,
        )
        self.assertIn('card.dataset.sizesDirty = "true"', javascript)
        self.assertIn("variant._sizesDirty = true", javascript)

    def test_global_save_keeps_changes_made_after_revision_snapshot_dirty(self):
        javascript = (
            Path(__file__).resolve().parents[1]
            / "static"
            / "product_catalog"
            / "editor.js"
        ).read_text(encoding="utf-8")

        self.assertIn("revision: 0", javascript)
        self.assertIn("state.revision += 1", javascript)
        self.assertIn("const saveRevision = state.revision", javascript)
        self.assertIn("revision: variant._revision || 0", javascript)
        self.assertIn("currentVariant._revision === draft.revision", javascript)
        self.assertIn(
            "const changedDuringSave = state.revision !== saveRevision",
            javascript,
        )
        changed_branch = javascript.index("if (changedDuringSave)")
        full_render = javascript.index("renderHeader()", changed_branch)
        self.assertLess(changed_branch, full_render)

    def test_individual_variant_save_preserves_late_draft_and_only_merges_new_id(self):
        javascript = (
            Path(__file__).resolve().parents[1]
            / "static"
            / "product_catalog"
            / "editor.js"
        ).read_text(encoding="utf-8")
        start = javascript.index("async function saveVariant(card, index)")
        end = javascript.index("function refreshColorLibrary", start)
        variant_save = javascript[start:end]

        self.assertIn("snapshotVariantDraftRevision(variant)", variant_save)
        self.assertIn(
            "isVariantDraftRevisionCurrent(currentVariant, draftRevision)",
            variant_save,
        )
        self.assertIn("if (!variantUnchanged)", variant_save)
        self.assertIn("currentVariant.id = resp.variant.id", variant_save)
        late_branch = variant_save.index("if (!variantUnchanged)")
        render = variant_save.index("renderVariants()")
        self.assertLess(late_branch, render)
        self.assertNotIn("clearVariantDirty(card, resp.variant);\n\t\t\tstate.variants[index]", variant_save)

    def test_individual_variant_save_does_not_render_over_other_variant_late_edits(self):
        javascript = (
            Path(__file__).resolve().parents[1]
            / "static"
            / "product_catalog"
            / "editor.js"
        ).read_text(encoding="utf-8")
        start = javascript.index("async function saveVariant(card, index)")
        end = javascript.index("function refreshColorLibrary", start)
        variant_save = javascript[start:end]

        self.assertIn("const editorRevision = state.revision", variant_save)
        self.assertIn(
            "const editorChanged = state.revision !== editorRevision",
            variant_save,
        )
        changed_start = variant_save.index("if (editorChanged)")
        changed_end = variant_save.index("return;", changed_start)
        changed_branch = variant_save[changed_start:changed_end]
        self.assertIn('syncInventorySurfaces(currentIndex, "server")', changed_branch)
        self.assertNotIn("renderVariants()", changed_branch)
        self.assertNotIn("setDirty(false)", changed_branch)
        self.assertLess(changed_end, variant_save.index("renderVariants()"))

    def test_new_variant_initializes_inventory_draft_before_first_render(self):
        javascript = (
            Path(__file__).resolve().parents[1]
            / "static"
            / "product_catalog"
            / "editor.js"
        ).read_text(encoding="utf-8")
        start = javascript.index("function emptyVariant()")
        end = javascript.index("function sizeRule", start)
        empty_variant = javascript[start:end]

        self.assertIn("buildDefaultInventoryRows(", empty_variant)
        self.assertIn("state.fits.filter((fit) => fit.is_enabled)", empty_variant)
        self.assertIn("sizesList()", empty_variant)

    def test_stock_only_save_merges_inventory_without_clearing_content_draft(self):
        javascript = (
            Path(__file__).resolve().parents[1]
            / "static"
            / "product_catalog"
            / "editor.js"
        ).read_text(encoding="utf-8")
        start = javascript.index('$("#f-stock").addEventListener("click"')
        end = javascript.index("/* ---------------- фіди", start)
        stock_save = javascript[start:end]

        self.assertIn("const sizes = snapshotInventoryDraft(variant)", stock_save)
        self.assertNotIn("is_default: variant.is_default", stock_save)
        self.assertIn(
            'syncInventorySurfaces(index, "server")',
            stock_save,
        )
        self.assertIn("variant._sizesDirty = false", stock_save)
        self.assertIn("variant._dirty = Boolean(variant._contentDirty)", stock_save)
        self.assertNotIn("clearVariantDirty", stock_save)
        self.assertNotIn("state.variants[index] = resp.variant", stock_save)
        self.assertNotIn("renderVariants()", stock_save)

    def test_variant_size_surfaces_share_one_revisioned_inventory_draft(self):
        javascript = (
            Path(__file__).resolve().parents[1]
            / "static"
            / "product_catalog"
            / "editor.js"
        ).read_text(encoding="utf-8")

        self.assertIn("function syncInventorySurface(surface, sizes)", javascript)
        self.assertIn("function updateInventoryDraftFromSurface(", javascript)
        self.assertIn("replaceInventoryDraft(variant, collectInventoryRows(surface))", javascript)
        self.assertIn('syncInventorySurfaces(index, source)', javascript)
        self.assertIn("cell.classList.toggle(\"is-off\", !enabled)", javascript)
        self.assertIn("stock.value = rule.stock == null ? \"\"", javascript)
        self.assertIn(
            "if ((variant._sizesRevision || 0) !== sizesRevision)",
            javascript,
        )

    def test_editor_uses_shared_general_inventory_resolution_and_canonicalization(self):
        javascript = (
            Path(__file__).resolve().parents[1]
            / "static"
            / "product_catalog"
            / "editor.js"
        ).read_text(encoding="utf-8")

        self.assertIn("window.productCatalogInventory.resolveInventoryRule", javascript)
        self.assertIn("window.productCatalogInventory.canonicalizeInventoryRows", javascript)
        self.assertIn("window.productCatalogInventory.replaceInventoryDraft", javascript)
        self.assertIn("window.productCatalogInventory.snapshotInventoryDraft", javascript)

    def test_global_save_uses_shared_inventory_snapshot_without_stock_overlay(self):
        javascript = (
            Path(__file__).resolve().parents[1]
            / "static"
            / "product_catalog"
            / "editor.js"
        ).read_text(encoding="utf-8")

        self.assertIn("data.sizes = snapshotInventoryDraft(variant)", javascript)
        self.assertNotIn("draft.data.sizes = collectStockSizes(block)", javascript)
        self.assertIn("pendingFeedDrafts", javascript)
        self.assertIn("for (const draft of pendingFeedDrafts)", javascript)

    def test_unknown_feed_does_not_append_feed_specific_images(self):
        feed = FeedProfile.objects.create(name="Meta", slug="meta")
        FeedOnlyImage.objects.create(
            product=self.product,
            feed=feed,
            image="product_catalog/feed_images/meta-only.webp",
        )

        urls = feed_image_urls("unknown", self.product, ["/default.webp"])

        self.assertEqual(urls, ["/default.webp"])

    def test_inactive_feed_keeps_legacy_default_images(self):
        feed = FeedProfile.objects.create(
            name="Inactive",
            slug="inactive",
            is_active=False,
        )
        FeedOnlyImage.objects.create(
            product=self.product,
            feed=feed,
            image="product_catalog/feed_images/inactive-only.webp",
        )

        urls = feed_image_urls("inactive", self.product, ["/default.webp"])

        self.assertEqual(urls, ["/default.webp"])

    def test_missing_api_resource_returns_404_without_internal_details(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("product_catalog_api_images_reorder"),
            data=json.dumps({"product_id": 999999, "ids": []}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertNotIn("DoesNotExist", response.content.decode())

    def test_legacy_myisam_relations_do_not_create_database_constraints(self):
        external_relations = (
            ("ColorProfile", "color"),
            ("VariantDetails", "variant"),
            ("ProductFitNote", "product"),
            ("VariantFitRule", "variant"),
            ("VariantSizeRule", "variant"),
            ("VariantFAQ", "variant"),
            ("FeedProductRule", "product"),
            ("FeedImageRule", "product"),
            ("FeedImageRule", "product_image"),
            ("FeedImageRule", "color_image"),
            ("FeedOnlyImage", "product"),
        )

        for model_name, field_name in external_relations:
            field = apps.get_model("product_catalog", model_name)._meta.get_field(field_name)
            self.assertFalse(
                field.db_constraint,
                f"{model_name}.{field_name} must remain compatible with legacy MyISAM tables",
            )

    def test_legacy_admin_panel_links_to_product_catalog_editor(self):
        template = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "templates"
            / "pages"
            / "admin_panel.html"
        ).read_text(encoding="utf-8")
        taxonomy_partial = (
            Path(__file__).resolve().parents[2]
            / "twocomms_django_theme"
            / "templates"
            / "partials"
            / "catalog_taxonomy_row.html"
        ).read_text(encoding="utf-8")
        template += "\n" + taxonomy_partial

        self.assertIn("{% url 'product_catalog_product_new' %}", template)
        self.assertIn("{% url 'product_catalog_product_edit' product.id %}", template)
        self.assertIn("Редактор товару", template)
        self.assertNotIn("Старий редактор", template)
        self.assertNotIn("admin_product_", template)
        self.assertIn('aria-label="Редагувати товар', template)
        self.assertIn('aria-label="Видалити товар', template)
        self.assertIn('data-index-state', template)
        self.assertIn('catalog-category-list', template)
        self.assertIn('aria-label="Категорії товарів"', template)
        self.assertIn('aria-level="{{ collection.depth|add:\'1\' }}"', template)
        self.assertIn('data-taxonomy-depth="{{ collection.depth }}"', template)
        self.assertIn('role="tabpanel"', template)
        self.assertIn('data-taxonomy-preview="icon"', template)
        self.assertIn('textarea name="description_', template)
        self.assertIn("grid.addEventListener('keydown', onHandleKeyDown);", template)
        self.assertIn("dialog.addEventListener('cancel'", template)
        self.assertIn('data-print-empty', Path(__file__).resolve().parents[2].joinpath("product_catalog", "static", "product_catalog", "editor.js").read_text(encoding="utf-8"))
