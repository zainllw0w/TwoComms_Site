import uuid

from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase, override_settings

from orders.checkout_series import (
    AssistedCheckoutV2Disabled,
    assisted_checkout_v2_enabled,
    assisted_checkout_v2_mode,
    build_checkout_series_identity,
    stable_checkout_series_key,
    stable_order_idempotency_key,
)
from orders.models import PaymentAttempt


class CheckoutSeriesIdentityTests(SimpleTestCase):
    def setUp(self):
        self.proposal_id = uuid.UUID("aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee")

    @override_settings(IG_ASSISTED_CHECKOUT_V2="off")
    def test_default_off_contract_performs_no_identity_activation(self):
        self.assertFalse(assisted_checkout_v2_enabled())
        with self.assertRaises(AssistedCheckoutV2Disabled):
            build_checkout_series_identity(self.proposal_id, generation=1)

    @override_settings(IG_ASSISTED_CHECKOUT_V2="unknown")
    def test_unknown_mode_fails_closed_to_off(self):
        self.assertEqual(assisted_checkout_v2_mode(), "off")
        self.assertFalse(assisted_checkout_v2_enabled())

    @override_settings(IG_ASSISTED_CHECKOUT_V2="shadow")
    def test_series_and_order_keys_are_stable_opaque_and_generation_independent(self):
        first = build_checkout_series_identity(self.proposal_id, generation=1)
        second = build_checkout_series_identity(str(self.proposal_id), generation=2)

        self.assertEqual(first.series_key, second.series_key)
        self.assertEqual(first.order_idempotency_key, second.order_idempotency_key)
        self.assertNotEqual(first.generation, second.generation)
        self.assertEqual(len(first.series_key), 64)
        self.assertEqual(len(first.order_idempotency_key), 64)
        self.assertNotIn(str(self.proposal_id), first.series_key)

    @override_settings(IG_ASSISTED_CHECKOUT_V2="enforced")
    def test_different_proposals_have_different_barriers(self):
        other = uuid.UUID("11111111-2222-4333-8444-555555555555")
        first = build_checkout_series_identity(self.proposal_id, generation=1)
        second = build_checkout_series_identity(other, generation=1)

        self.assertNotEqual(first.series_key, second.series_key)
        self.assertNotEqual(
            first.order_idempotency_key,
            second.order_idempotency_key,
        )

    @override_settings(IG_ASSISTED_CHECKOUT_V2="shadow")
    def test_invalid_uuid_generation_and_series_key_fail_closed(self):
        for proposal_id in ("", "not-a-uuid", None):
            with self.subTest(proposal_id=proposal_id):
                with self.assertRaises(ValueError):
                    stable_checkout_series_key(proposal_id)
        for generation in (
            0,
            -1,
            True,
            1.0,
            1.9,
            "1",
            "01",
            "+1",
            "bad",
            None,
        ):
            with self.subTest(generation=generation):
                with self.assertRaises(ValueError):
                    build_checkout_series_identity(
                        self.proposal_id,
                        generation=generation,
                    )
        for series_key in ("", "g" * 64, "a" * 63):
            with self.subTest(series_key=series_key):
                with self.assertRaises(ValueError):
                    stable_order_idempotency_key(series_key)


class CheckoutSeriesSchemaContractTests(TestCase):
    def _attempt(self, suffix, **values):
        return PaymentAttempt.objects.create(
            fingerprint=(suffix * 64)[:64],
            full_name="Schema Buyer",
            phone=f"+38050000{suffix:0>4}"[-13:],
            city="Kyiv",
            np_office="Branch 1",
            pay_type=PaymentAttempt.PayType.ONLINE_FULL,
            **values,
        )

    def test_legacy_rows_remain_all_null_and_not_winner(self):
        attempt = self._attempt("1")

        self.assertIsNone(attempt.checkout_series_key)
        self.assertIsNone(attempt.checkout_generation)
        self.assertFalse(attempt.checkout_winner_claimed)

    def test_complete_series_identity_and_winner_are_valid(self):
        attempt = self._attempt(
            "2",
            checkout_series_key="a" * 64,
            checkout_generation=1,
            checkout_winner_claimed=True,
        )

        self.assertEqual(attempt.checkout_generation, 1)
        self.assertTrue(attempt.checkout_winner_claimed)

    def test_partial_empty_zero_and_orphan_winner_shapes_are_rejected(self):
        invalid_rows = (
            {"checkout_series_key": "b" * 64},
            {"checkout_generation": 1},
            {"checkout_winner_claimed": True},
            {"checkout_series_key": "", "checkout_generation": 1},
            {"checkout_series_key": "c" * 64, "checkout_generation": 0},
        )
        for index, values in enumerate(invalid_rows, start=3):
            with self.subTest(values=values), self.assertRaises(IntegrityError):
                with transaction.atomic():
                    self._attempt(str(index), **values)

    def test_series_generation_is_unique_but_null_legacy_rows_coexist(self):
        self._attempt(
            "8",
            checkout_series_key="d" * 64,
            checkout_generation=2,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._attempt(
                "9",
                checkout_series_key="d" * 64,
                checkout_generation=2,
            )

        self._attempt("a")
        self._attempt("b")
