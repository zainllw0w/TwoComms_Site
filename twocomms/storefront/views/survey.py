"""Survey views - data-driven survey API endpoints."""
import json
import logging
from typing import Any, Dict

from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from ..models import SurveySession
from ..services.survey_engine import (
    SurveyEngine,
    award_survey_promocode,
    get_soft_hint,
    load_survey_definition,
)
from ..tasks import queue_survey_report
from ..utm_utils import parse_user_agent

logger = logging.getLogger(__name__)


def _json_body(request) -> Dict[str, Any]:
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return {}


def _auth_guard(request):
    if not request.user.is_authenticated:
        return JsonResponse({"success": False, "error": "auth_required"}, status=401)
    return None


def _definition_or_error():
    definition = load_survey_definition()
    if not definition:
        return None, JsonResponse({"success": False, "error": "survey_unavailable"}, status=500)
    return definition, None


def _serialize_state(session: SurveySession, engine: SurveyEngine) -> Dict[str, Any]:
    answers = session.answers or {}
    question = engine.get_question(session.current_question_id) if session.current_question_id else None
    payload = {
        "success": True,
        "status": session.status,
        "session_id": session.id,
        "version": session.version,
        "back_used": session.back_used,
        "answered_count": len(session.history or []),
        "soft_hint": get_soft_hint(len(session.history or [])),
        "question": engine.serialize_question(question, answers.get(question.get("id"))) if question else None,
    }
    if session.awarded_promocode:
        payload["promo"] = {
            "code": session.awarded_promocode.code,
            "expires_at": session.awarded_promocode.valid_until.isoformat() if session.awarded_promocode.valid_until else None,
        }
    return payload


def _ensure_current_question(session: SurveySession, engine: SurveyEngine) -> None:
    if session.current_question_id:
        return
    question = engine.get_next_question(
        session.answers or {},
        session.history or [],
        meta=None,
        module_order=session.module_order or None,
    )
    if question:
        session.current_question_id = question.get("id")
        session.save(update_fields=["current_question_id", "last_activity_at"])


def _required_satisfied(engine: SurveyEngine, answers: Dict[str, Any]) -> bool:
    for qid in engine.required_questions:
        value = answers.get(qid)
        if value in (None, "", [], {}):
            return False
    return True


def _complete_session(session: SurveySession, definition: Dict[str, Any]) -> SurveySession:
    if session.status == 'completed':
        return session

    reward_def = definition.get("reward", {})
    promo_code, _ = award_survey_promocode(session.user, session.survey_key, reward_def)
    session.awarded_promocode = promo_code
    session.status = 'completed'
    session.completed_at = timezone.now()
    session.current_question_id = None
    session.save(update_fields=["awarded_promocode", "status", "completed_at", "current_question_id", "last_activity_at"])
    queue_survey_report(session.id, "FINAL")
    return session


@require_http_methods(["POST"])
def survey_start_or_resume(request):
    auth_response = _auth_guard(request)
    if auth_response:
        return auth_response

    definition, error_response = _definition_or_error()
    if error_response:
        return error_response

    engine = SurveyEngine(definition)
    survey_key = definition.get("survey_key", "print_feedback_v1")

    device_data = parse_user_agent(request.META.get("HTTP_USER_AGENT", ""))

    try:
        with transaction.atomic():
            session, created = SurveySession.objects.select_for_update().get_or_create(
                user=request.user,
                survey_key=survey_key,
                defaults={
                    "device_type": device_data.get("device_type"),
                    "user_agent": request.META.get("HTTP_USER_AGENT", "")[:500],
                },
            )
            if not created and not session.device_type:
                session.device_type = device_data.get("device_type")
                session.user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]
                session.save(update_fields=["device_type", "user_agent", "last_activity_at"])
    except IntegrityError:
        session = SurveySession.objects.filter(user=request.user, survey_key=survey_key).first()

    if not session:
        return JsonResponse({"success": False, "error": "session_unavailable"}, status=500)

    if session.status == 'completed':
        return JsonResponse(_serialize_state(session, engine))

    _ensure_current_question(session, engine)
    session.save(update_fields=["last_activity_at"])
    return JsonResponse(_serialize_state(session, engine))


@require_http_methods(["GET"])
def survey_current_question(request):
    auth_response = _auth_guard(request)
    if auth_response:
        return auth_response

    definition, error_response = _definition_or_error()
    if error_response:
        return error_response

    engine = SurveyEngine(definition)
    survey_key = definition.get("survey_key", "print_feedback_v1")
    session = SurveySession.objects.filter(user=request.user, survey_key=survey_key).first()
    if not session:
        return JsonResponse({"success": False, "error": "session_not_found"}, status=404)

    if session.status == 'completed':
        return JsonResponse(_serialize_state(session, engine))

    _ensure_current_question(session, engine)
    return JsonResponse(_serialize_state(session, engine))


@require_http_methods(["POST"])
def survey_submit_answer(request):
    auth_response = _auth_guard(request)
    if auth_response:
        return auth_response

    definition, error_response = _definition_or_error()
    if error_response:
        return error_response

    engine = SurveyEngine(definition)
    survey_key = definition.get("survey_key", "print_feedback_v1")
    payload = _json_body(request)
    question_id = payload.get("question_id")
    client_version = payload.get("version")
    answer = payload.get("answer")

    if not question_id:
        return JsonResponse({"success": False, "error": "missing_question"}, status=400)

    try:
        with transaction.atomic():
            session = SurveySession.objects.select_for_update().get(
                user=request.user,
                survey_key=survey_key,
            )
            if session.status == 'completed':
                return JsonResponse(_serialize_state(session, engine))

            if client_version is not None and int(client_version) != session.version:
                return JsonResponse({"success": False, "error": "version_conflict", "current": _serialize_state(session, engine)}, status=409)

            if session.current_question_id and session.current_question_id != question_id:
                return JsonResponse({"success": False, "error": "question_mismatch", "current": _serialize_state(session, engine)}, status=409)

            question = engine.get_question(question_id)
            if not question:
                return JsonResponse({"success": False, "error": "question_not_found"}, status=404)

            valid, cleaned, reason = engine.validate_answer(question, answer)
            if not valid:
                return JsonResponse({"success": False, "error": reason}, status=400)

            answers = session.answers or {}
            answers[question_id] = cleaned
            history = session.history or []
            if question_id in history:
                history = [qid for qid in history if qid != question_id]
            history.append(question_id)

            session.answers = answers
            session.history = history
            session.version = session.version + 1

            next_question = engine.get_next_question(
                session.answers,
                session.history,
                meta=None,
                module_order=session.module_order or None,
            )

            if next_question:
                session.current_question_id = next_question.get("id")
                session.save(update_fields=[
                    "answers",
                    "history",
                    "current_question_id",
                    "version",
                    "last_activity_at",
                ])
                return JsonResponse(_serialize_state(session, engine))

            min_required = int(definition.get("end_conditions", {}).get("min_answered_questions", 0))
            if len(session.history or []) < min_required and not _required_satisfied(engine, session.answers):
                logger.warning("Survey ended early for session %s", session.id)

            session.save(update_fields=["answers", "history", "version", "last_activity_at"])
            session = _complete_session(session, definition)
            return JsonResponse(_serialize_state(session, engine))

    except SurveySession.DoesNotExist:
        return JsonResponse({"success": False, "error": "session_not_found"}, status=404)


@require_http_methods(["POST"])
def survey_back_one_step(request):
    auth_response = _auth_guard(request)
    if auth_response:
        return auth_response

    definition, error_response = _definition_or_error()
    if error_response:
        return error_response

    engine = SurveyEngine(definition)
    survey_key = definition.get("survey_key", "print_feedback_v1")
    payload = _json_body(request)
    client_version = payload.get("version")

    try:
        with transaction.atomic():
            session = SurveySession.objects.select_for_update().get(
                user=request.user,
                survey_key=survey_key,
            )
            if session.status == 'completed':
                return JsonResponse(_serialize_state(session, engine))
            if session.back_used:
                return JsonResponse({"success": False, "error": "back_used"}, status=400)
            if client_version is not None and int(client_version) != session.version:
                return JsonResponse({"success": False, "error": "version_conflict", "current": _serialize_state(session, engine)}, status=409)

            history = session.history or []
            if not history:
                return JsonResponse({"success": False, "error": "no_history"}, status=400)

            last_question_id = history.pop()
            session.history = history
            session.current_question_id = last_question_id
            session.back_used = True
            session.version = session.version + 1
            session.save(update_fields=[
                "history",
                "current_question_id",
                "back_used",
                "version",
                "last_activity_at",
            ])
            return JsonResponse(_serialize_state(session, engine))

    except SurveySession.DoesNotExist:
        return JsonResponse({"success": False, "error": "session_not_found"}, status=404)


@require_http_methods(["POST"])
def survey_close(request):
    auth_response = _auth_guard(request)
    if auth_response:
        return auth_response

    definition, error_response = _definition_or_error()
    if error_response:
        return error_response

    survey_key = definition.get("survey_key", "print_feedback_v1")
    SurveySession.objects.filter(user=request.user, survey_key=survey_key).update(last_activity_at=timezone.now())
    return JsonResponse({"success": True})


@require_http_methods(["POST"])
def survey_complete(request):
    auth_response = _auth_guard(request)
    if auth_response:
        return auth_response

    definition, error_response = _definition_or_error()
    if error_response:
        return error_response

    engine = SurveyEngine(definition)
    survey_key = definition.get("survey_key", "print_feedback_v1")
    session = SurveySession.objects.filter(user=request.user, survey_key=survey_key).first()
    if not session:
        return JsonResponse({"success": False, "error": "session_not_found"}, status=404)

    if session.status == 'completed':
        return JsonResponse(_serialize_state(session, engine))

    min_required = int(definition.get("end_conditions", {}).get("min_answered_questions", 0))
    if len(session.history or []) < min_required:
        return JsonResponse({"success": False, "error": "not_enough_answers"}, status=400)

    if not _required_satisfied(engine, session.answers or {}):
        return JsonResponse({"success": False, "error": "required_missing"}, status=400)

    session = _complete_session(session, definition)
    return JsonResponse(_serialize_state(session, engine))
