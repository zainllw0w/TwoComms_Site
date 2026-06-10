from django.contrib.auth import get_user_model
from django.test import TestCase

from management.forms import CommercialOfferEmailForm


class CommercialOfferFormTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="cp_mgr", password="x")

    def test_form_cta_choices_simplified(self):
        self.assertLessEqual(len(CommercialOfferEmailForm.CTA_TYPE_CHOICES), 4)

    def test_form_valid_minimal(self):
        form = CommercialOfferEmailForm(
            data={"recipient_email": "client@example.com"}, user=self.user
        )
        self.assertTrue(form.is_valid(), form.errors)
