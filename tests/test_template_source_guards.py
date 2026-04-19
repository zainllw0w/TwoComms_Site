import re
import unittest
from pathlib import Path


BASE_TEMPLATE = Path(
    "/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/base.html"
)
HOME_TEMPLATE = Path(
    "/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/templates/pages/index.html"
)


class BaseTemplateSourceGuardsTests(unittest.TestCase):
    def _multiline_hash_comments(self, template_path: Path):
        content = template_path.read_text(encoding="utf-8")
        multiline_comments = []
        cursor = 0

        while True:
            start = content.find("{#", cursor)
            if start == -1:
                break
            end = content.find("#}", start + 2)
            if end == -1:
                break

            comment = content[start : end + 2]
            if "\n" in comment:
                multiline_comments.append(comment)
            cursor = end + 2

        return multiline_comments

    def test_base_template_avoids_multiline_django_hash_comments(self):
        multiline_comments = self._multiline_hash_comments(BASE_TEMPLATE)

        self.assertEqual(
            multiline_comments,
            [],
            "base.html must not use multiline {# ... #} comments because they leak into rendered HTML",
        )

    def test_home_template_avoids_multiline_django_hash_comments(self):
        multiline_comments = self._multiline_hash_comments(HOME_TEMPLATE)

        self.assertEqual(
            multiline_comments,
            [],
            "index.html must not use multiline {# ... #} comments because they leak into rendered HTML",
        )

    def test_base_template_keeps_homepage_footer_and_rum_assets(self):
        content = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("css/support-hub.css", content)
        self.assertIn("js/rum.js", content)
        self.assertIn("js/ui-fallback.js", content)


if __name__ == "__main__":
    unittest.main()
