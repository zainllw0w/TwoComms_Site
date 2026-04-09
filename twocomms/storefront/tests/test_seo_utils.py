from types import SimpleNamespace

from django.test import SimpleTestCase

from storefront.seo_utils import _extract_openai_message_content


class ExtractOpenAIMessageContentTests(SimpleTestCase):
    def test_reads_dict_message_content(self):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message={"content": "dict-content"})]
        )

        self.assertEqual(_extract_openai_message_content(response), "dict-content")

    def test_reads_object_message_string_content(self):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="object-content"))]
        )

        self.assertEqual(_extract_openai_message_content(response), "object-content")

    def test_reads_object_message_parts_content(self):
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=[
                            SimpleNamespace(text="Hello"),
                            {"text": " world"},
                        ]
                    )
                )
            ]
        )

        self.assertEqual(_extract_openai_message_content(response), "Hello world")
