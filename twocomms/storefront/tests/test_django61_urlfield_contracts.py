from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

from django import forms
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import models
from django.forms import modelform_factory
from django.test import SimpleTestCase, TestCase

from storefront.models import UTMSession


APP_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_MODEL_URL_FIELDS = {
    "accounts.UserProfile.website",
    "finance.IntegrationConnection.webhook_url",
    "finance.PushSubscription.endpoint",
    "management.CallRecord.recording_url",
    "management.IgUgcReward.evidence_url",
    "orders.PaymentAttempt.invoice_url",
    "orders.WholesaleInvoice.payment_url",
    "orders.WholesaleInvoice.store_link",
    "product_catalog.ProductOptionProfile.youtube_url",
    "product_catalog.VariantCombinationProfile.youtube_url",
    "product_catalog.VariantDetails.youtube_url",
    "storefront.BlogPost.source_url",
    "storefront.PrintProposal.link_url",
    "storefront.Product.video_url",
    "storefront.UTMSession.referrer",
    "storefront.WebPushDeviceSubscription.endpoint",
}


def _non_dtf_model_url_fields():
    discovered = {}
    for model in apps.get_models():
        if model._meta.app_label == "dtf" or model.__module__.startswith("dtf."):
            continue
        for field in model._meta.fields:
            if isinstance(field, models.URLField):
                key = f"{model._meta.label}.{field.name}"
                discovered[key] = (model, field)
    return discovered


class Django61URLFieldContractTests(SimpleTestCase):
    def test_non_dtf_model_urlfield_inventory_is_complete(self):
        self.assertEqual(set(_non_dtf_model_url_fields()), EXPECTED_MODEL_URL_FIELDS)

    def test_generated_modelform_urlfields_use_https_and_keep_explicit_schemes(self):
        for key, (model, model_field) in _non_dtf_model_url_fields().items():
            with self.subTest(field=key):
                form_class = modelform_factory(model, fields=[model_field.name])
                form_field = form_class.base_fields[model_field.name]

                self.assertIsInstance(form_field, forms.URLField)
                self.assertEqual(form_field.assume_scheme, "https")
                self.assertEqual(
                    form_field.clean("provider.example/resource"),
                    "https://provider.example/resource",
                )
                for explicit_url in (
                    "http://legacy-provider.example/resource",
                    "https://provider.example/resource",
                ):
                    self.assertEqual(form_field.clean(explicit_url), explicit_url)

                with self.assertRaises(ValidationError) as caught:
                    form_field.clean("not a valid url")
                self.assertEqual(caught.exception.error_list[0].code, "invalid")

    def test_model_urlfields_validate_but_do_not_normalize_storage_values(self):
        scheme_less = "provider.example/resource"
        for key, (_, model_field) in _non_dtf_model_url_fields().items():
            with self.subTest(field=key):
                self.assertEqual(model_field.to_python(scheme_less), scheme_less)
                self.assertEqual(model_field.get_prep_value(scheme_less), scheme_less)

                with self.assertRaises(ValidationError) as caught:
                    model_field.run_validators(scheme_less)
                self.assertIn(
                    "invalid",
                    {error.code for error in caught.exception.error_list},
                )

                for explicit_url in (
                    "http://legacy-provider.example/resource",
                    "https://provider.example/resource",
                ):
                    model_field.run_validators(explicit_url)

    def test_project_owned_forms_pin_https_independently_of_framework_default(self):
        environment = os.environ.copy()
        environment.update(
            {
                "DJANGO_SETTINGS_MODULE": "test_settings_no_network_non_dtf",
                "PYTHONPATH": str(APP_ROOT),
                "SECRET_KEY": "django61-urlfield-contract",
            }
        )
        statement = textwrap.dedent(
            """
            import json
            from django import forms

            original_init = forms.URLField.__init__

            def force_http_default(self, *, assume_scheme=None, **kwargs):
                if assume_scheme is None:
                    assume_scheme = "http"
                original_init(self, assume_scheme=assume_scheme, **kwargs)

            forms.URLField.__init__ = force_http_default

            import django
            django.setup()

            from orders.forms import CompanyProfileForm
            from storefront.forms import BlogPostForm, PrintProposalForm

            fields = {
                "orders.CompanyProfileForm.website": CompanyProfileForm.base_fields["website"],
                "storefront.BlogPostForm.source_url": BlogPostForm.base_fields["source_url"],
                "storefront.PrintProposalForm.link_url": PrintProposalForm.base_fields["link_url"],
            }
            print(json.dumps({name: field.assume_scheme for name, field in fields.items()}))
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", statement],
            cwd=APP_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout.strip().splitlines()[-1]),
            {
                "orders.CompanyProfileForm.website": "https",
                "storefront.BlogPostForm.source_url": "https",
                "storefront.PrintProposalForm.link_url": "https",
            },
        )


class StoredLegacyHTTPURLTests(TestCase):
    def test_unrelated_model_save_preserves_stored_legacy_http_url(self):
        legacy_url = "http://legacy-referrer.example/source"
        session = UTMSession.objects.create(
            session_key="django61-urlfield-session",
            referrer=legacy_url,
        )

        session.refresh_from_db()
        self.assertEqual(session.referrer, legacy_url)

        session.visit_count = 2
        session.save(update_fields=["visit_count"])
        session.refresh_from_db()

        self.assertEqual(session.visit_count, 2)
        self.assertEqual(session.referrer, legacy_url)
