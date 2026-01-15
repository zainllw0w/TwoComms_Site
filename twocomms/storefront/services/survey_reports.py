from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from accounts.models import UserProfile
from .survey_engine import SurveyEngine


def build_survey_report(
    session,
    definition: Dict[str, Any],
    status: str,
    file_path: Path,
) -> Path:
    """Build or update Excel report for a survey session."""
    engine = SurveyEngine(definition)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1F2937", end_color="1F2937", fill_type="solid")
    label_font = Font(bold=True)

    def write_row(row: int, label: str, value: str) -> None:
        ws.cell(row=row, column=1, value=label).font = label_font
        ws.cell(row=row, column=2, value=value)

    ws.append(["Field", "Value"])
    ws["A1"].font = header_font
    ws["B1"].font = header_font
    ws["A1"].fill = header_fill
    ws["B1"].fill = header_fill

    profile = None
    try:
        profile = UserProfile.objects.filter(user=session.user).first()
    except Exception:
        profile = None

    created = timezone.localtime(session.started_at).strftime("%d.%m.%Y %H:%M")
    last_activity = timezone.localtime(session.last_activity_at).strftime("%d.%m.%Y %H:%M")
    completed = (
        timezone.localtime(session.completed_at).strftime("%d.%m.%Y %H:%M")
        if session.completed_at
        else "–"
    )

    values = [
        ("Survey key", session.survey_key),
        ("Status", status),
        ("User ID", str(session.user_id)),
        ("Username", session.user.username),
        ("Email", session.user.email or (profile.email if profile else "")),
        ("Phone", profile.phone if profile else ""),
        ("Device", session.device_type or ""),
        ("Started at", created),
        ("Last activity", last_activity),
        ("Completed at", completed),
        ("Promo code", session.awarded_promocode.code if session.awarded_promocode else ""),
        (
            "Promo expires",
            timezone.localtime(session.awarded_promocode.valid_until).strftime("%d.%m.%Y %H:%M")
            if session.awarded_promocode and session.awarded_promocode.valid_until
            else "",
        ),
    ]

    row = 2
    for label, value in values:
        write_row(row, label, value)
        row += 1

    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 60
    for cell in ws["B"]:
        cell.alignment = Alignment(wrap_text=True, vertical="top")

    ws_answers = wb.create_sheet("Answers")
    ws_answers.append(["Question ID", "Question", "Answer"])
    for col in range(1, 4):
        cell = ws_answers.cell(row=1, column=col)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    for qid in session.history or []:
        question = engine.get_question(qid)
        if not question:
            continue
        answer = (session.answers or {}).get(qid)
        ws_answers.append([
            qid,
            question.get("prompt_uk") or question.get("prompt") or "",
            engine.format_answer(question, answer),
        ])

    ws_answers.column_dimensions[get_column_letter(1)].width = 22
    ws_answers.column_dimensions[get_column_letter(2)].width = 70
    ws_answers.column_dimensions[get_column_letter(3)].width = 60
    for row_cells in ws_answers.iter_rows(min_row=2, max_col=3):
        for cell in row_cells:
            cell.alignment = Alignment(wrap_text=True, vertical="top")

    wb.save(file_path)
    return file_path


def _safe_filename_component(value: Optional[str], fallback: str, allow_unicode: bool = False) -> str:
    if not value:
        return fallback
    slug = slugify(str(value), allow_unicode=allow_unicode)
    return slug or fallback


def get_survey_title(definition: Optional[Dict[str, Any]]) -> str:
    """Resolve a human-friendly survey title for notifications/files."""
    definition = definition or {}
    ui = definition.get("ui_copy", {}) or {}
    modal_title = (ui.get("modal") or {}).get("title_uk")
    home_title = (ui.get("homepage_block") or {}).get("title_uk")
    return modal_title or home_title or definition.get("survey_key", "Survey")


def resolve_report_path(session, definition: Optional[Dict[str, Any]] = None) -> Path:
    """Resolve report path for a session, using a stable human-friendly filename."""
    base_dir = Path(getattr(settings, "SURVEY_REPORTS_DIR", settings.MEDIA_ROOT / "survey_reports"))
    title = get_survey_title(definition)
    title_slug = _safe_filename_component(title, "survey", allow_unicode=True)
    username = _safe_filename_component(session.user.username, f"user{session.user_id}", allow_unicode=True)
    email = _safe_filename_component(session.user.email, "", allow_unicode=False)
    parts = [title_slug, username]
    if email:
        parts.append(email)
    parts.append(f"s{session.id}")
    filename = f"opituvannia_{'_'.join(parts)}.xlsx"
    return base_dir / filename
