"""ЭА.22 — tests for the fault-injection harness itself."""
import time
import unittest
from unittest.mock import patch

from management.services import call_ai_analysis as ai
from management.services import ig_fault_injection as faults


class FaultScenarioContractTests(unittest.TestCase):
    """Verify fault scenario contract invariants hold."""

    def test_injected_outcome_requires_exactly_one_field(self):
        with self.assertRaisesRegex(ValueError, "exactly one outcome"):
            faults.InjectedOutcome()
        with self.assertRaisesRegex(ValueError, "exactly one outcome"):
            faults.InjectedOutcome(
                success_response=("text", {}),
                exception=RuntimeError("both"),
            )

    def test_fault_scenario_requires_at_least_one_outcome(self):
        with self.assertRaisesRegex(ValueError, "at least one outcome"):
            faults.FaultScenario(name="empty", outcomes=())

    def test_all_named_scenarios_are_valid(self):
        for factory in faults.ALL_SCENARIOS:
            scenario = factory()
            self.assertIsInstance(scenario, faults.FaultScenario)
            self.assertTrue(scenario.name)
            self.assertGreater(len(scenario.outcomes), 0)
            for outcome in scenario.outcomes:
                self.assertIsInstance(outcome, faults.InjectedOutcome)

    def test_exception_builders_return_typed_gemini_exceptions(self):
        exc = faults._make_exception("quota_429", retry_after=60)
        self.assertIsInstance(exc, ai._Gemini429)
        self.assertEqual(exc.http_code, 429)
        self.assertEqual(exc.retry_after_seconds, 60)

        exc = faults._make_exception("http_503")
        self.assertIsInstance(exc, ai._GeminiTransient)
        self.assertEqual(exc.http_code, 503)

        exc = faults._make_exception("timeout")
        self.assertIsInstance(exc, ai._GeminiTransient)
        self.assertIsNone(exc.http_code)

        exc = faults._make_exception("invalid_payload")
        self.assertIsInstance(exc, ai._GeminiFatal)
        self.assertEqual(exc.http_code, 400)

        with self.assertRaisesRegex(ValueError, "unsupported exception kind"):
            faults._make_exception("unknown_kind")


class InjectorBehaviorTests(unittest.TestCase):
    """Verify injector tracks attempt count and repeats final outcome."""

    def test_injector_returns_success_response_tuple(self):
        scenario = faults.FaultScenario(
            name="test",
            outcomes=(faults._success("hello"),)
        )
        injector = faults.build_injector(scenario)
        result = injector("gemini-3.6-flash", {}, "test-key")
        self.assertEqual(result[0]["reply_text"], "hello")
        self.assertIn("promptTokenCount", result[1])
        self.assertIn("candidatesTokenCount", result[1])

    def test_injector_raises_typed_exception(self):
        scenario = faults.FaultScenario(
            name="test",
            outcomes=(faults._failure("http_503"),)
        )
        injector = faults.build_injector(scenario)
        with self.assertRaises(ai._GeminiTransient) as ctx:
            injector("gemini-3.6-flash", {}, "test-key")
        self.assertEqual(ctx.exception.http_code, 503)

    def test_injector_advances_through_sequence(self):
        scenario = faults.FaultScenario(
            name="test",
            outcomes=(
                faults._failure("http_503"),
                faults._success("recovered"),
            )
        )
        injector = faults.build_injector(scenario)
        with self.assertRaises(ai._GeminiTransient):
            injector("model", {}, "key")
        result = injector("model", {}, "key")
        self.assertEqual(result[0]["reply_text"], "recovered")

    def test_injector_repeats_final_outcome_when_exhausted(self):
        scenario = faults.FaultScenario(
            name="test",
            outcomes=(faults._success("once"),)
        )
        injector = faults.build_injector(scenario)
        self.assertEqual(injector("m", {}, "k")[0]["reply_text"], "once")
        self.assertEqual(injector("m", {}, "k")[0]["reply_text"], "once")
        self.assertEqual(injector("m", {}, "k")[0]["reply_text"], "once")

    def test_delayed_outcome_sleeps_then_returns(self):
        inner = faults._success("delayed")
        scenario = faults.FaultScenario(
            name="test",
            outcomes=(
                faults.InjectedOutcome(delay_then_outcome=(0.01, inner)),
            )
        )
        injector = faults.build_injector(scenario)
        start = time.monotonic()
        result = injector("model", {}, "key")
        elapsed = time.monotonic() - start
        self.assertGreater(elapsed, 0.009)
        self.assertEqual(result[0]["reply_text"], "delayed")


class NamedScenarioSemanticTests(unittest.TestCase):
    """Verify each named scenario matches its documented intent."""

    def test_full_429_all_aliases_repeats_quota_error(self):
        scenario = faults.full_429_all_aliases()
        injector = faults.build_injector(scenario)
        for _ in range(5):
            with self.assertRaises(ai._Gemini429):
                injector("model", {}, "key")

    def test_http_503_first_then_success_fails_once_recovers(self):
        scenario = faults.http_503_first_then_success()
        injector = faults.build_injector(scenario)
        with self.assertRaises(ai._GeminiTransient) as ctx:
            injector("model", {}, "key")
        self.assertEqual(ctx.exception.http_code, 503)
        result = injector("model", {}, "key")
        self.assertIn("recovered after 503", result[0]["reply_text"])

    def test_read_timeout_all_models_raises_transient_no_http_code(self):
        scenario = faults.read_timeout_all_models()
        injector = faults.build_injector(scenario)
        with self.assertRaises(ai._GeminiTransient) as ctx:
            injector("model", {}, "key")
        self.assertIsNone(ctx.exception.http_code)
        self.assertIn("timeout", str(ctx.exception))

    def test_invalid_payload_400_raises_fatal(self):
        scenario = faults.invalid_payload_400()
        injector = faults.build_injector(scenario)
        with self.assertRaises(ai._GeminiFatal) as ctx:
            injector("model", {}, "key")
        self.assertEqual(ctx.exception.http_code, 400)

    def test_slow_success_30_seconds_delays_and_succeeds(self):
        scenario = faults.slow_success_30_seconds()
        # Verify structure without sleeping 30 seconds in tests.
        self.assertEqual(len(scenario.outcomes), 1)
        outcome = scenario.outcomes[0]
        self.assertIsNotNone(outcome.delay_then_outcome)
        delay, inner = outcome.delay_then_outcome
        self.assertEqual(delay, 30.0)
        self.assertIsNotNone(inner.success_response)

    def test_success_between_two_failures_flaps(self):
        scenario = faults.success_between_two_failures()
        injector = faults.build_injector(scenario)
        with self.assertRaises(ai._GeminiTransient):
            injector("m", {}, "k")
        result = injector("m", {}, "k")
        self.assertIn("transient recovery", result[0]["reply_text"])
        with self.assertRaises(ai._GeminiTransient):
            injector("m", {}, "k")

    def test_flapping_success_and_failure_alternates(self):
        scenario = faults.flapping_success_and_failure()
        injector = faults.build_injector(scenario)
        outcomes = []
        for _ in range(5):
            try:
                result = injector("m", {}, "k")
                outcomes.append(("success", result[0]["reply_text"]))
            except ai._GeminiTransient:
                outcomes.append(("failure", None))
        self.assertEqual(outcomes[0][0], "failure")
        self.assertEqual(outcomes[1][0], "success")
        self.assertEqual(outcomes[2][0], "failure")
        self.assertEqual(outcomes[3][0], "success")
        self.assertEqual(outcomes[4][0], "failure")

    def test_valid_http_200_invalid_application_schema_succeeds_with_wrong_shape(self):
        scenario = faults.valid_http_200_invalid_application_schema()
        injector = faults.build_injector(scenario)
        result = injector("m", {}, "k")
        self.assertNotIn("reply", result[0])
        self.assertIn("unexpected_field", result[0])

    def test_model_replies_wrong_language_succeeds_with_english(self):
        scenario = faults.model_replies_wrong_language()
        injector = faults.build_injector(scenario)
        result = injector("m", {}, "k")
        self.assertIn("Hello", result[0]["reply_text"])
        self.assertIn("English", result[0]["reply_text"])

    def test_model_returns_empty_text_succeeds_with_empty_string(self):
        scenario = faults.model_returns_empty_text()
        injector = faults.build_injector(scenario)
        result = injector("m", {}, "k")
        self.assertEqual(result[0]["reply_text"], "")

    def test_auth_403_permission_denied_raises_fatal(self):
        scenario = faults.auth_403_permission_denied()
        injector = faults.build_injector(scenario)
        with self.assertRaises(ai._GeminiFatal) as ctx:
            injector("m", {}, "k")
        self.assertEqual(ctx.exception.http_code, 403)

    def test_not_found_404_unknown_model_raises_fatal(self):
        scenario = faults.not_found_404_unknown_model()
        injector = faults.build_injector(scenario)
        with self.assertRaises(ai._GeminiModelUnavailable) as ctx:
            injector("m", {}, "k")
        self.assertEqual(ctx.exception.http_code, 404)


class InjectorPatchUsageExampleTests(unittest.TestCase):
    """Document how tests should use the injector with patch.object."""

    @patch.object(ai, "_gemini_call_once")
    def test_patch_gemini_call_once_with_injector_side_effect(self, mock_once):
        scenario = faults.http_503_first_then_success()
        mock_once.side_effect = faults.build_injector(scenario)

        # First call raises, second succeeds — exactly as the scenario declares.
        with self.assertRaises(ai._GeminiTransient):
            ai._gemini_call_once("gemini-3.6-flash", {}, "test-key", parse=False)
        
        result = ai._gemini_call_once("gemini-3.6-flash", {}, "test-key", parse=False)
        self.assertIn("recovered", result[0]["reply_text"])

    def test_all_scenarios_registry_discoverable(self):
        # Tests can iterate ALL_SCENARIOS to verify coverage or build a matrix.
        names = {factory().name for factory in faults.ALL_SCENARIOS}
        self.assertIn("full_429_all_aliases", names)
        self.assertIn("http_503_first_then_success", names)
        self.assertIn("flapping_success_and_failure", names)
        self.assertIn("model_returns_empty_text", names)
        self.assertEqual(len(names), len(faults.ALL_SCENARIOS))


class FaultScenarioDocumentationTests(unittest.TestCase):
    """Each scenario has a clear docstring matching its intent."""

    def test_every_scenario_has_docstring(self):
        for factory in faults.ALL_SCENARIOS:
            doc = factory.__doc__
            self.assertIsNotNone(doc, f"{factory.__name__} missing docstring")
            self.assertGreater(len(doc.strip()), 20, f"{factory.__name__} docstring too short")

    def test_scenario_names_match_function_names(self):
        for factory in faults.ALL_SCENARIOS:
            scenario = factory()
            # Name should match or be derived from function name.
            self.assertTrue(
                scenario.name.replace("_", "") in factory.__name__.replace("_", "").lower(),
                f"{scenario.name} does not match {factory.__name__}"
            )
