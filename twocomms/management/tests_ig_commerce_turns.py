from django.test import SimpleTestCase, TestCase

from management.services.ig_commerce_turns import parse_turn, understand_turn
from storefront.models import Category, Product, ProductFitOption, ProductStatus


class CommerceTurnParserTests(SimpleTestCase):
    def test_size_guide_topic_does_not_change_payable_fit(self):
        result = parse_turn("Покажи на оверсайз размерную сетку")

        self.assertEqual(result.field_updates, {})
        self.assertEqual(result.info_topics, ("size_guide:oversize",))
        self.assertFalse(result.checkout_requested)

    def test_without_print_requires_placement_but_explicit_placement_is_exact(self):
        self.assertEqual(parse_turn("без принта").pending_clarification, "print_placement")
        exact = parse_turn("логотип спереди, без принта сзади")
        self.assertEqual(exact.hard_constraints["front_decoration"], "logo")
        self.assertEqual(exact.hard_constraints["back_decoration"], "none")

    def test_mixed_language_constraints_are_composed_without_product_guess(self):
        result = parse_turn("давай black класичну M")

        self.assertEqual(
            result.field_updates,
            {"color": "black", "fit": "classic", "size": "M"},
        )
        self.assertIsNone(result.exact_product_id)

    def test_new_purchase_exchange_and_ambiguous_change_are_distinct(self):
        self.assertTrue(parse_turn("хочу еще одну черную M").new_purchase_requested)
        self.assertTrue(parse_turn("хочу поменять размер в полученной").exchange_requested)
        self.assertEqual(parse_turn("хочу другую").pending_clarification, "new_purchase_or_exchange")

    def test_invalid_model_payload_falls_back_to_one_safe_clarification(self):
        result = understand_turn("давай другую обычную", model_payload={"product_id": 999999})
        self.assertIsNone(result.exact_product_id)
        self.assertEqual(result.pending_clarification, "which_product")


class TrustedUrlTurnTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="T-shirts", slug="turn-shirts")
        self.product = Product.objects.create(
            title="Classic shirt",
            slug="turn-classic-shirt",
            category=category,
            price=700,
            status=ProductStatus.PUBLISHED,
        )
        ProductFitOption.objects.create(
            product=self.product, code="classic", label="Classic", is_active=True
        )

    def test_exact_url_wins_and_negated_url_is_a_rejection(self):
        url = f"https://twocomms.shop/product/{self.product.slug}/"
        exact = parse_turn(url)
        self.assertEqual(exact.exact_product_id, self.product.pk)

        rejected = parse_turn(f"не хочу {url}")
        self.assertIsNone(rejected.exact_product_id)
        self.assertEqual(rejected.rejected_product_ids, (self.product.pk,))
