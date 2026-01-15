"""
Tests for survey engine, promo award idempotency, and access rules.
"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from storefront.services.survey_engine import (
    SurveyEngine,
    award_survey_promocode,
    clear_survey_definition_cache,
)


TEST_DEFINITION = {
    "survey_key": "test_survey",
    "reward": {"amount_uah": 200, "expires_in_days": 5, "title_uk": "Reward"},
    "caps": {
        "total_max_questions": 3,
        "max_text_questions_total": 1,
        "max_followups_per_multi_choice": 1,
    },
    "end_conditions": {"required_questions": ["q1"], "min_answered_questions": 2},
    "flow": {"core": ["q1", "q2"], "closing": ["q3"]},
    "questions": [
        {
            "id": "q1",
            "type": "slider_1_10",
            "prompt": "Overall",
            "required": True,
            "scale": {"min": 1, "max": 10},
        },
        {
            "id": "q2",
            "type": "single_choice",
            "prompt": "Pick",
            "options": [
                {"value": "a", "label": "A"},
                {"value": "b", "label": "B"},
            ],
            "show_if": {"var": "answers.q1", "op": "gte", "value": 5},
        },
        {
            "id": "q3",
            "type": "text_short",
            "prompt": "Why",
            "required": False,
        },
    ],
}


class SurveyEngineTests(TestCase):
    def test_next_question_respects_show_if(self):
        engine = SurveyEngine(TEST_DEFINITION)
        first = engine.get_next_question({}, [])
        self.assertEqual(first["id"], "q1")

        answers = {"q1": 4}
        history = ["q1"]
        next_question = engine.get_next_question(answers, history)
        self.assertEqual(next_question["id"], "q3")

    def test_validate_slider_range(self):
        engine = SurveyEngine(TEST_DEFINITION)
        question = engine.get_question("q1")
        valid, _, reason = engine.validate_answer(question, 11)
        self.assertFalse(valid)
        self.assertEqual(reason, "range")


class SurveyPromoCodeTests(TestCase):
    def test_award_promocode_idempotent(self):
        user = User.objects.create_user(username="surveyuser", password="pass1234")
        reward = {"amount_uah": 200, "expires_in_days": 5, "title_uk": "Reward"}

        promo_first, _ = award_survey_promocode(user, "test_survey", reward)
        promo_second, _ = award_survey_promocode(user, "test_survey", reward)

        self.assertEqual(promo_first.id, promo_second.id)
        self.assertEqual(user.promo_grants.count(), 1)


class SurveyViewTests(TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.definition_path = Path(self.temp_dir.name) / "survey.json"
        self.definition_path.write_text(json.dumps(TEST_DEFINITION), encoding="utf-8")
        self.override = override_settings(SURVEY_DEFINITION_PATH=self.definition_path)
        self.override.enable()
        clear_survey_definition_cache()
        self.client = Client()

    def tearDown(self):
        clear_survey_definition_cache()
        self.override.disable()
        self.temp_dir.cleanup()

    def test_start_requires_auth(self):
        response = self.client.post(reverse("survey_start_or_resume"), data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 401)

    def test_authenticated_start_and_answer(self):
        user = User.objects.create_user(username="surveyuser", password="pass1234")
        self.client.force_login(user)

        start_response = self.client.post(reverse("survey_start_or_resume"), data="{}", content_type="application/json")
        self.assertEqual(start_response.status_code, 200)
        payload = start_response.json()
        self.assertTrue(payload.get("success"))
        self.assertEqual(payload["question"]["id"], "q1")

        answer_response = self.client.post(
            reverse("survey_submit_answer"),
            data=json.dumps({
                "question_id": "q1",
                "answer": 3,
                "version": payload["version"],
            }),
            content_type="application/json",
        )
        self.assertEqual(answer_response.status_code, 200)
        answer_payload = answer_response.json()
        self.assertEqual(answer_payload["question"]["id"], "q3")
