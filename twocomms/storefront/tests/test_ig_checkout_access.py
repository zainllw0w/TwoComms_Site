import hashlib
from decimal import Decimal
from datetime import timedelta
from urllib.parse import urlparse

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from management.models import IgCheckoutAccessToken, IgCheckoutProposal, IgClient, IgDeal
from management.services.ig_commercial_episodes import ensure_episode_for_deal


class InstagramCheckoutAccessTests(TestCase):
    def setUp(self):
        self.client_profile = IgClient.get_or_create_for_sender("ig-access-tests")
        self.deal = IgDeal.objects.create(
            client=self.client_profile,
            status=IgDeal.Status.QUOTED,
            amount=Decimal("790.00"),
            requested_payment_amount=Decimal("790.00"),
        )
        self.episode = ensure_episode_for_deal(self.deal)
        self.proposal = IgCheckoutProposal.objects.create_current(
            deal=self.deal,
            commercial_episode=self.episode,
            catalog_total=Decimal("790.00"),
            quoted_total=Decimal("790.00"),
            requested_payment_amount=Decimal("790.00"),
            items_digest=hashlib.sha256(b"access-test").hexdigest(),
        )
        self.raw_token, self.token = IgCheckoutAccessToken.issue(proposal=self.proposal)

    def test_bearer_entry_redirects_to_clean_granted_page(self):
        response = self.client.get(
            reverse("ig_checkout_token_entry", kwargs={"token": self.raw_token})
        )

        self.assertEqual(response.status_code, 302)
        clean_url = reverse(
            "ig_checkout_proposal",
            kwargs={"proposal_id": self.proposal.public_id},
        )
        self.assertEqual(response["Location"], clean_url)
        self.assertNotIn(self.raw_token, response["Location"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("no-referrer", response["Referrer-Policy"])
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")

        clean = self.client.get(clean_url)
        self.assertEqual(clean.status_code, 200)
        self.assertNotContains(clean, self.raw_token)
        self.assertIn("no-store", clean["Cache-Control"])
        self.assertEqual(clean["X-Robots-Tag"], "noindex, nofollow")
        self.token.refresh_from_db()
        self.assertEqual(self.token.use_count, 1)

    def test_clean_page_requires_a_granted_session(self):
        response = self.client.get(
            reverse(
                "ig_checkout_proposal",
                kwargs={"proposal_id": self.proposal.public_id},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_expired_token_does_not_grant_access(self):
        self.token.expires_at = timezone.now() - timedelta(seconds=1)
        self.token.save(update_fields=["expires_at"])

        response = self.client.get(
            reverse("ig_checkout_token_entry", kwargs={"token": self.raw_token})
        )

        self.assertEqual(response.status_code, 410)
        self.token.refresh_from_db()
        self.assertEqual(self.token.use_count, 0)

    def test_revoked_token_does_not_grant_access(self):
        self.token.revoked_at = timezone.now()
        self.token.save(update_fields=["revoked_at"])

        response = self.client.get(
            reverse("ig_checkout_token_entry", kwargs={"token": self.raw_token})
        )

        self.assertEqual(response.status_code, 410)
        self.token.refresh_from_db()
        self.assertEqual(self.token.use_count, 0)

    def test_share_endpoint_is_csrf_protected_and_issues_separate_token(self):
        strict_client = Client(enforce_csrf_checks=True)
        entry = strict_client.get(
            reverse("ig_checkout_token_entry", kwargs={"token": self.raw_token})
        )
        strict_client.get(entry["Location"])
        share_url = reverse(
            "ig_checkout_share_token",
            kwargs={"proposal_id": self.proposal.public_id},
        )

        response = strict_client.post(share_url)
        self.assertEqual(response.status_code, 403)

        strict_client.get(reverse("analytics_bootstrap"))
        csrf_token = strict_client.cookies["csrftoken"].value
        response = strict_client.post(
            share_url,
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        raw_share_token = urlparse(payload["url"]).path.rstrip("/").split("/")[-1]
        self.assertTrue(raw_share_token)
        self.assertNotIn(raw_share_token, {
            token.token_digest
            for token in IgCheckoutAccessToken.objects.filter(proposal=self.proposal)
        })
        self.assertEqual(
            IgCheckoutAccessToken.objects.filter(
                proposal=self.proposal,
                kind=IgCheckoutAccessToken.Kind.SHARE,
            ).count(),
            1,
        )
