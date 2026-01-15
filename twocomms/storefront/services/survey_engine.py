import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from ..models import PromoCode, PromoCodeGroup, UserPromoCode

logger = logging.getLogger(__name__)

def _default_survey_path() -> Path:
    return Path(
        getattr(
            settings,
            "SURVEY_DEFINITION_PATH",
            settings.BASE_DIR / "surveys" / "print_feedback_v1.json",
        )
    )

_SURVEY_CACHE: Dict[str, Any] = {
    "path": None,
    "mtime": None,
    "data": None,
}


def load_survey_definition(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load survey definition JSON with simple mtime cache."""
    target = Path(path or _default_survey_path())
    try:
        mtime = target.stat().st_mtime
    except FileNotFoundError:
        logger.error("Survey definition not found: %s", target)
        return {}

    if (
        _SURVEY_CACHE["data"]
        and _SURVEY_CACHE["mtime"] == mtime
        and _SURVEY_CACHE["path"] == target
    ):
        return _SURVEY_CACHE["data"]

    try:
        with target.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Failed to load survey definition %s: %s", target, exc)
        return {}

    _SURVEY_CACHE.update({"path": target, "mtime": mtime, "data": data})
    return data


def clear_survey_definition_cache() -> None:
    """Clear cached survey definition (useful in tests)."""
    _SURVEY_CACHE.update({"path": None, "mtime": None, "data": None})


def get_soft_hint(answered_count: int) -> str:
    """Return a soft progress hint without numeric progress."""
    if answered_count <= 3:
        return "Ще трохи — це швидко."
    if answered_count <= 7:
        return "Супер, рухаємось далі."
    if answered_count <= 11:
        return "Майже готово."
    return "Останні штрихи."


class SurveyEngine:
    """Data-driven survey engine using JSON definition."""

    def __init__(self, definition: Dict[str, Any]) -> None:
        self.definition = definition or {}
        self.questions: List[Dict[str, Any]] = self.definition.get("questions", [])
        self.questions_by_id = {
            q.get("id"): q for q in self.questions if isinstance(q, dict) and q.get("id")
        }
        self.questions_by_section: Dict[str, List[Dict[str, Any]]] = {}
        for question in self.questions:
            section = question.get("section", "")
            self.questions_by_section.setdefault(section, []).append(question)
        for section, items in self.questions_by_section.items():
            items.sort(key=lambda item: item.get("order", 0))
        flow = self.definition.get("flow", {})
        self.flow_core = flow.get("core", [])
        self.flow_closing = flow.get("closing", [])
        self.caps = self.definition.get("caps", {})
        self.policy = self.definition.get("policy", {})
        end_conditions = self.definition.get("end_conditions", {})
        self.required_questions = set(end_conditions.get("required_questions", []))

    def get_question(self, question_id: str) -> Optional[Dict[str, Any]]:
        return self.questions_by_id.get(question_id)

    def serialize_question(
        self,
        question: Dict[str, Any],
        answer: Any = None,
    ) -> Dict[str, Any]:
        payload = {
            "id": question.get("id"),
            "type": question.get("type"),
            "prompt": question.get("prompt_uk") or question.get("prompt"),
            "help": question.get("help_uk"),
            "required": bool(question.get("required")),
            "options": [],
            "scale": question.get("scale"),
            "placeholder": question.get("placeholder_uk"),
            "max_select": question.get("max_select"),
            "answer": answer,
        }
        options = question.get("options") or []
        for opt in options:
            payload["options"].append(
                {
                    "value": opt.get("value"),
                    "label": opt.get("label_uk") or opt.get("label"),
                    "help": opt.get("help_uk"),
                }
            )
        return payload

    def evaluate_condition(self, expr: Any, context: Dict[str, Any]) -> bool:
        if expr in (None, {}, []):
            return True
        if isinstance(expr, list):
            return all(self.evaluate_condition(item, context) for item in expr)
        if not isinstance(expr, dict):
            return False

        if "any" in expr:
            return any(self.evaluate_condition(item, context) for item in expr.get("any", []))
        if "all" in expr:
            return all(self.evaluate_condition(item, context) for item in expr.get("all", []))
        if "not" in expr:
            return not self.evaluate_condition(expr.get("not"), context)

        op = expr.get("op")
        var = expr.get("var")
        value = expr.get("value")
        left = self._resolve_var(var, context)

        try:
            if op == "eq":
                return left == value
            if op == "lte":
                return left is not None and left <= value
            if op == "gte":
                return left is not None and left >= value
            if op == "includes":
                if left is None:
                    return False
                if isinstance(left, (list, tuple, set)):
                    return value in left
                if isinstance(left, str):
                    return value in left
                return False
            if op == "in":
                if value is None:
                    return False
                return left in value
            if op == "exists":
                return left not in (None, "", [], {})
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Condition eval failed for %s: %s", expr, exc)
            return False

        if op:
            logger.warning("Unknown operator in survey condition: %s", op)
        return False

    def _resolve_var(self, var: Optional[str], context: Dict[str, Any]) -> Any:
        if not var:
            return None
        parts = var.split('.')
        current = context.get(parts[0])
        for part in parts[1:]:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current

    def select_modules(self, answers: Dict[str, Any], meta: Optional[Dict[str, Any]] = None) -> List[str]:
        modules = self.definition.get("modules", {})
        context = {"answers": answers or {}, "meta": meta or {}}
        activated: List[str] = []
        for key, module in modules.items():
            activation = module.get("activation")
            if activation and self.evaluate_condition(activation, context):
                activated.append(key)

        module_policy = (
            self.policy
            .get("branching", {})
            .get("module_selection", {})
        )
        base_max = module_policy.get("base_max_modules", len(activated))
        low_score_threshold = module_policy.get("low_score_threshold")
        pain_threshold = module_policy.get("pain_threshold")
        max_if_many = module_policy.get("max_modules_if_many_pains", base_max)
        max_modules = base_max

        if low_score_threshold is not None and pain_threshold is not None:
            pain_count = 0
            for qid in self.flow_core:
                value = answers.get(qid)
                if isinstance(value, (int, float)) and value <= low_score_threshold:
                    pain_count += 1
            if pain_count >= pain_threshold:
                max_modules = max_if_many

        return activated[:max_modules]

    def get_next_question(
        self,
        answers: Dict[str, Any],
        history: List[str],
        meta: Optional[Dict[str, Any]] = None,
        module_order: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        answers = answers or {}
        history = history or []
        answered_ids = set(history)
        total_answered = len(history)
        text_max = int(self.caps.get("max_text_questions_total", 999))
        total_max = int(self.caps.get("total_max_questions", 999))
        module_max_map = self.caps.get("module_max_questions", {}) or {}
        max_followups = int(self.caps.get("max_followups_per_multi_choice", 0))

        context = {"answers": answers, "meta": meta or {}}
        text_count = sum(
            1
            for qid in history
            if self.questions_by_id.get(qid, {}).get("type") in ("text_short", "text_long")
        )

        def can_ask(question: Dict[str, Any]) -> bool:
            qid = question.get("id")
            if not qid or qid in answered_ids:
                return False
            if question.get("show_if") and not self.evaluate_condition(question.get("show_if"), context):
                return False
            is_required = qid in self.required_questions or question.get("required")
            qtype = question.get("type")
            if not is_required and total_answered >= total_max:
                return False
            if qtype in ("text_short", "text_long") and not is_required and text_count >= text_max:
                return False
            return True

        for qid in self.flow_core:
            question = self.questions_by_id.get(qid)
            if question and can_ask(question):
                return question

        followups = self._collect_followups(answers, history, context, max_followups)
        for qid in followups:
            question = self.questions_by_id.get(qid)
            if question and can_ask(question):
                return question

        module_order = module_order or self.select_modules(answers, meta)
        module_counts: Dict[str, int] = {}
        for qid in history:
            section = self.questions_by_id.get(qid, {}).get("section")
            if section:
                module_counts[section] = module_counts.get(section, 0) + 1

        for module_key in module_order:
            module_def = self.definition.get("modules", {}).get(module_key, {})
            module_limit = int(module_def.get("max_questions", 999))
            module_cap = module_max_map.get(module_key)
            if module_cap is not None:
                module_limit = min(module_limit, int(module_cap))
            if module_counts.get(module_key, 0) >= module_limit:
                continue

            for question in self.questions_by_section.get(module_key, []):
                if module_counts.get(module_key, 0) >= module_limit:
                    break
                if can_ask(question):
                    return question

        for qid in self.flow_closing:
            question = self.questions_by_id.get(qid)
            if question and can_ask(question):
                return question

        return None

    def _collect_followups(
        self,
        answers: Dict[str, Any],
        history: List[str],
        context: Dict[str, Any],
        max_followups: int,
    ) -> List[str]:
        followup_ids: List[str] = []
        for qid in history:
            question = self.questions_by_id.get(qid)
            if not question:
                continue
            items = question.get("followups") or []
            if not items:
                continue
            answer = answers.get(qid)
            for item in items:
                followup_id, condition = self._parse_followup(item, answer)
                if not followup_id:
                    continue
                if condition and not self.evaluate_condition(condition, context):
                    continue
                followup_ids.append(followup_id)
                if max_followups and len(followup_ids) >= max_followups:
                    return followup_ids
        return followup_ids

    def _parse_followup(
        self, item: Any, answer: Any
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        if isinstance(item, str):
            return item, None
        if not isinstance(item, dict):
            return None, None

        followup_id = item.get("question_id") or item.get("id") or item.get("followup_id")
        condition = item.get("show_if") or item.get("when") or item.get("condition")
        if "value" in item or "values" in item:
            expected = item.get("value") if "value" in item else item.get("values")
            if isinstance(answer, (list, tuple, set)):
                if isinstance(expected, (list, tuple, set)):
                    if not any(val in answer for val in expected):
                        return None, condition
                elif expected not in answer:
                    return None, condition
            elif answer != expected:
                return None, condition
        return followup_id, condition

    def validate_answer(self, question: Dict[str, Any], answer: Any) -> Tuple[bool, Any, str]:
        qtype = question.get("type")
        required = bool(question.get("required"))

        if answer in (None, ""):
            if required:
                return False, None, "required"
            return True, None, "ok"

        if qtype in ("slider_1_10", "slider_0_10"):
            try:
                value = int(answer)
            except (TypeError, ValueError):
                return False, None, "invalid"
            min_value = 1 if qtype == "slider_1_10" else 0
            max_value = 10
            if value < min_value or value > max_value:
                return False, None, "range"
            return True, value, "ok"

        if qtype == "single_choice":
            options = {opt.get("value") for opt in question.get("options", [])}
            if answer not in options:
                return False, None, "invalid"
            return True, answer, "ok"

        if qtype in ("multi_choice", "multi_select"):
            if isinstance(answer, str):
                answers_list = [answer]
            else:
                answers_list = list(answer) if isinstance(answer, (list, tuple, set)) else []
            options = {opt.get("value") for opt in question.get("options", [])}
            answers_list = [item for item in answers_list if item in options]
            if required and not answers_list:
                return False, None, "required"
            max_select = question.get("max_select")
            if max_select and len(answers_list) > int(max_select):
                return False, None, "max_select"
            return True, answers_list, "ok"

        if qtype in ("text_short", "text_long"):
            text_value = str(answer).strip()
            if required and not text_value:
                return False, None, "required"
            limit = 280 if qtype == "text_short" else 1200
            if len(text_value) > limit:
                text_value = text_value[:limit]
            return True, text_value, "ok"

        return True, answer, "ok"

    def format_answer(self, question: Dict[str, Any], answer: Any) -> str:
        if answer in (None, ""):
            return ""
        qtype = question.get("type")
        if qtype in ("single_choice",):
            return self._label_for_option(question, answer) or str(answer)
        if qtype in ("multi_choice", "multi_select"):
            if not isinstance(answer, (list, tuple, set)):
                return str(answer)
            labels = [self._label_for_option(question, item) or str(item) for item in answer]
            return ", ".join(labels)
        if qtype in ("slider_1_10", "slider_0_10"):
            return str(answer)
        return str(answer)

    def _label_for_option(self, question: Dict[str, Any], value: Any) -> Optional[str]:
        for option in question.get("options", []) or []:
            if option.get("value") == value:
                return option.get("label_uk") or option.get("label")
        return None


def award_survey_promocode(
    user,
    survey_key: str,
    reward_def: Dict[str, Any],
) -> Tuple[PromoCode, Optional[datetime]]:
    """Create or reuse a promo code for survey reward (idempotent)."""
    reward_def = reward_def or {}
    amount = reward_def.get("amount_uah", 0)
    expires_in_days = int(reward_def.get("expires_in_days", 5))

    with transaction.atomic():
        existing = (
            UserPromoCode.objects.select_for_update()
            .select_related("promo_code")
            .filter(user=user, survey_key=survey_key)
            .first()
        )
        if existing and existing.promo_code:
            return existing.promo_code, existing.promo_code.valid_until

        group_name = f"Survey: {survey_key}"
        promo_group, _ = PromoCodeGroup.objects.get_or_create(
            name=group_name,
            defaults={
                "description": f"Survey reward for {survey_key}",
                "one_per_account": True,
                "is_active": True,
            },
        )

        now = timezone.now()
        promo_code = PromoCode.objects.create(
            code=PromoCode.generate_code(),
            promo_type="voucher",
            discount_type="fixed",
            discount_value=amount,
            description=reward_def.get("title_uk") or f"Survey reward {survey_key}",
            group=promo_group,
            max_uses=1,
            one_time_per_user=True,
            valid_from=now,
            valid_until=now + timedelta(days=expires_in_days),
            is_active=True,
        )

        try:
            UserPromoCode.objects.create(
                user=user,
                promo_code=promo_code,
                survey_key=survey_key,
                source="survey",
                expires_at=promo_code.valid_until,
            )
        except IntegrityError:
            existing = (
                UserPromoCode.objects.select_related("promo_code")
                .filter(user=user, survey_key=survey_key)
                .first()
            )
            if existing and existing.promo_code:
                promo_code.is_active = False
                promo_code.save(update_fields=["is_active"])
                return existing.promo_code, existing.promo_code.valid_until
            raise

    return promo_code, promo_code.valid_until
