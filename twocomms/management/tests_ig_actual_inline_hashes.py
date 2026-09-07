import base64
import hashlib
import json
from unittest.mock import patch

from django.test import SimpleTestCase

from management.services import call_ai_analysis as ai
from management.tests_ig_provider_dispatch_budget import _Response


class ActualInlineHashTests(SimpleTestCase):
    def test_hashes_describe_exact_final_body_after_suffix_trim(self):
        first, second = b"actually transmitted", b"trimmed away"
        payload = {"contents": [{"role": "user", "parts": [
            {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(body).decode()}}
            for body in (first, second)
        ]}]}
        final_payload = {"contents": [{"role": "user", "parts": payload["contents"][0]["parts"][:1]}]}
        final_body = json.dumps(final_payload).encode()
        with (
            patch("management.services.call_ai_analysis._final_provider_body", return_value=(final_body, 1, 1)),
            patch("management.services.ig_db_circuit.release_idle_connection"),
            patch("management.services.call_ai_analysis.requests.post", return_value=_Response('{"reply_text":"ok"}')) as http,
        ):
            _parsed, usage = ai._gemini_call_once("gemini-3.7-flash", payload, "fixture-key")
        self.assertEqual(http.call_args.kwargs["data"], final_body)
        self.assertEqual(usage["_request_inline_content_hashes"], [hashlib.sha256(first).hexdigest()])
        self.assertEqual(usage["_request_inline_count"], 1)
        self.assertNotIn(hashlib.sha256(second).hexdigest(), usage["_request_inline_content_hashes"])
