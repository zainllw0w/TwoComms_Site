"""Розділ «AI радник»: чат (rule-based) та інструменти перевірки."""
from __future__ import annotations

import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from ..models import get_default_company
from ..permissions import finance_access_required
from ..services import ai_advisor


@finance_access_required
def ai_advisor_page(request):
    return render(request, 'finance/ai.html', {
        'active_tab': 'ai',
        'quick_prompts': ai_advisor.QUICK_PROMPTS,
    })


@finance_access_required(api=True)
@require_POST
def ai_chat_api(request):
    company = get_default_company()
    try:
        data = json.loads(request.body or '{}')
    except (ValueError, TypeError):
        data = {}
    question = (data.get('question') or '').strip()
    if not question:
        return JsonResponse({'ok': False, 'error': 'Порожнє питання'}, status=400)
    result = ai_advisor.answer(company, question)
    return JsonResponse({'ok': True, **result})


@finance_access_required(api=True)
@require_POST
def ai_check_payments_api(request):
    company = get_default_company()
    return JsonResponse({'ok': True, 'issues': ai_advisor.check_payments(company)})


@finance_access_required(api=True)
@require_POST
def ai_check_report_api(request):
    company = get_default_company()
    return JsonResponse({'ok': True, 'issues': ai_advisor.check_report(company)})
