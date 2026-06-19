"""Тести Phase 2 / Task 7 — візуальні відбитки товарів (bot_vision).

Для кожного варіанту товару Gemini-vision генерує стислий опис принта/теми/
кольорів/напису і ми кладемо його в ProductColorVariant.metadata['bot_vision'].
Це база для матчингу пересланого поста з каталогом (кейс «Харків з єнотом»).
"""
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from management.services import bot_vision


class ParseFingerprintTests(SimpleTestCase):
    def test_plain_json(self):
        fp = bot_vision._parse_fingerprint('{"theme":"military","print_subject":"єнот"}')
        self.assertEqual(fp["theme"], "military")
        self.assertEqual(fp["print_subject"], "єнот")

    def test_fenced_json(self):
        raw = "```json\n{\"theme\":\"streetwear\"}\n```"
        self.assertEqual(bot_vision._parse_fingerprint(raw)["theme"], "streetwear")

    def test_garbage_returns_empty(self):
        self.assertEqual(bot_vision._parse_fingerprint("no json here"), {})

    def test_empty_returns_empty(self):
        self.assertEqual(bot_vision._parse_fingerprint(""), {})


class BuildPayloadTests(SimpleTestCase):
    def test_payload_has_json_mime_and_image_and_text(self):
        payload = bot_vision.build_fingerprint_payload([("image/jpeg", b"x")])
        self.assertEqual(
            payload["generationConfig"]["responseMimeType"], "application/json"
        )
        parts = payload["contents"][0]["parts"]
        self.assertTrue(any("inline_data" in p for p in parts))
        self.assertTrue(any("text" in p for p in parts))


class DescribeImagesTests(TestCase):
    @patch("management.services.bot_vision.gemini_generate_text")
    def test_describe_parses_model_output(self, mock_gen):
        mock_gen.return_value = {"parsed": '{"theme":"patriotic"}', "model": "x"}
        fp = bot_vision.describe_images([("image/jpeg", b"x")])
        self.assertEqual(fp["theme"], "patriotic")

    def test_describe_empty_images_returns_none(self):
        self.assertIsNone(bot_vision.describe_images([]))


class StoreAndFingerprintTests(TestCase):
    def setUp(self):
        from productcolors.models import Color, ProductColorVariant
        from storefront.models import Category, Product

        cat = Category.objects.create(name="Худі", slug="hudi")
        self.product = Product.objects.create(
            title="Худі Kharkiv", slug="hoodie-kharkiv", category=cat, price=950
        )
        color = Color.objects.create(name="чорний", primary_hex="#000000")
        self.variant = ProductColorVariant.objects.create(product=self.product, color=color)

    def test_store_writes_metadata(self):
        bot_vision.store_fingerprint(self.variant, {"theme": "patriotic", "print_subject": "єнот"})
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.metadata["bot_vision"]["theme"], "patriotic")
        self.assertIn("updated_at", self.variant.metadata["bot_vision"])

    @patch("management.services.bot_vision._variant_images")
    @patch("management.services.bot_vision.describe_images")
    def test_fingerprint_variant_stores(self, mock_desc, mock_imgs):
        mock_imgs.return_value = [("image/jpeg", b"x")]
        mock_desc.return_value = {"theme": "military"}
        self.assertTrue(bot_vision.fingerprint_variant(self.variant))
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.metadata["bot_vision"]["theme"], "military")

    @patch("management.services.bot_vision._variant_images")
    def test_fingerprint_variant_false_when_no_images(self, mock_imgs):
        mock_imgs.return_value = []
        self.assertFalse(bot_vision.fingerprint_variant(self.variant))

    @patch("management.services.bot_vision.fingerprint_variant")
    def test_fingerprint_product_skips_existing_unless_force(self, mock_fv):
        self.variant.metadata = {"bot_vision": {"theme": "x"}}
        self.variant.save(update_fields=["metadata"])
        mock_fv.return_value = True
        # без force — варіант із відбитком пропускається
        bot_vision.fingerprint_product(self.product, force=False)
        self.assertEqual(mock_fv.call_count, 0)
        # з force — обробляється
        bot_vision.fingerprint_product(self.product, force=True)
        self.assertEqual(mock_fv.call_count, 1)


class GenerateFingerprintsCommandTests(TestCase):
    def test_runs_with_no_products(self):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command("generate_bot_fingerprints", stdout=out)
        self.assertIn("Готово", out.getvalue())


class FormatCandidatesTests(SimpleTestCase):
    def test_includes_id_price_and_fingerprint(self):
        cands = [{"id": 7, "title": "Худі Kharkiv", "category": "Худі", "price": 950,
                  "fingerprint": "єнот, напис Харків"}]
        text = bot_vision._format_candidates(cands)
        self.assertIn("id=7", text)
        self.assertIn("950", text)
        self.assertIn("Харків", text)


class BuildMatchCandidatesTests(TestCase):
    def test_includes_published_with_fingerprint(self):
        from productcolors.models import Color, ProductColorVariant
        from storefront.models import Category, Product, ProductStatus

        cat = Category.objects.create(name="Худі", slug="hudi-bmc")
        p = Product.objects.create(
            title="Худі Kharkiv", slug="hk-bmc", category=cat, price=950,
            status=ProductStatus.PUBLISHED,
        )
        color = Color.objects.create(name="чорний", primary_hex="#000000")
        ProductColorVariant.objects.create(
            product=p, color=color, metadata={"bot_vision": {"summary": "худі з єнотом і написом Харків"}}
        )
        cands = bot_vision.build_match_candidates()
        ids = {c["id"] for c in cands}
        self.assertIn(p.id, ids)
        c = next(c for c in cands if c["id"] == p.id)
        self.assertIn("Харків", c["fingerprint"])


class MatchTests(TestCase):
    def _cands(self):
        return [
            {"id": 1, "title": "Худі Kharkiv", "category": "Худі", "price": 950, "fingerprint": "єнот, Харків"},
            {"id": 2, "title": "Футболка Military", "category": "Футболки", "price": 600, "fingerprint": "хакі"},
        ]

    @patch("management.services.bot_vision.gemini_generate_text")
    def test_match_returns_valid_product(self, mock_gen):
        mock_gen.return_value = {"parsed": '{"product_id":1,"confidence":0.85,"reason":"єнот збігається"}'}
        res = bot_vision.match([("image/jpeg", b"x")], candidates=self._cands())
        self.assertEqual(res["product_id"], 1)
        self.assertAlmostEqual(res["confidence"], 0.85, places=2)

    @patch("management.services.bot_vision.gemini_generate_text")
    def test_match_rejects_hallucinated_id(self, mock_gen):
        # модель повернула id, якого немає серед кандидатів → не вигадуємо
        mock_gen.return_value = {"parsed": '{"product_id":999,"confidence":0.9}'}
        res = bot_vision.match([("image/jpeg", b"x")], candidates=self._cands())
        self.assertIsNone(res["product_id"])
        self.assertEqual(res["confidence"], 0.0)

    def test_match_no_images(self):
        res = bot_vision.match([], candidates=self._cands())
        self.assertIsNone(res["product_id"])

    def test_match_no_candidates(self):
        res = bot_vision.match([("image/jpeg", b"x")], candidates=[])
        self.assertIsNone(res["product_id"])
