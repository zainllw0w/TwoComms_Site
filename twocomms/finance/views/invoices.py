"""Розділ «Рахунки-фактури»: список, ПДВ, форма створення/редагування, друк."""
from __future__ import annotations

import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from ..models import Invoice, get_default_company
from ..permissions import finance_access_required
from ..services import invoices as inv_service
from ..services import serializers as ser


def _body(request):
    if request.content_type and 'application/json' in request.content_type:
        try:
            return json.loads(request.body or '{}')
        except (ValueError, TypeError):
            return {}
    return request.POST


@finance_access_required
def invoices(request):
    company = get_default_company()
    tab = request.GET.get('tab', 'invoices')
    rows = []
    for inv in company.invoices.select_related('counterparty', 'project').order_by('-issue_date', '-id'):
        rows.append({
            'id': inv.id, 'number': inv.number, 'status': inv.status,
            'status_display': inv.get_status_display(),
            'issue_date': inv.issue_date, 'due_date': inv.due_date,
            'payer': inv.payer_name or (inv.counterparty.name if inv.counterparty else '—'),
            'currency': inv.currency,
            'total': ser.money(inv.total_amount, inv.currency),
            'paid': ser.money(inv.paid_amount, inv.currency),
            'due': ser.money(inv.balance_due, inv.currency),
            'project': inv.project.name if inv.project else '',
        })
    context = {
        'active_tab': 'invoices', 'tab': tab,
        'invoices': rows,
        'vat_rows': inv_service.vat_report(company) if tab == 'vat' else [],
    }
    return render(request, 'finance/invoices.html', context)


@finance_access_required
def invoice_form(request, invoice_id=None):
    company = get_default_company()
    invoice = None
    items = []
    if invoice_id:
        invoice = get_object_or_404(Invoice, id=invoice_id, company=company)
        items = list(invoice.items.all())
    return render(request, 'finance/invoice_form.html', {
        'active_tab': 'invoices',
        'invoice': invoice,
        'items': items,
        'dropdowns': ser.serialize_dropdowns(company),
        'currencies': ['UAH', 'USD', 'EUR', 'PLN', 'GBP'],
        'statuses': Invoice.STATUS_CHOICES,
        'next_number': inv_service.next_invoice_number(company),
    })


@finance_access_required(api=True)
@require_POST
def invoice_save_api(request, invoice_id=None):
    company = get_default_company()
    invoice = get_object_or_404(Invoice, id=invoice_id, company=company) if invoice_id else None
    data = _body(request)
    if isinstance(data.get('items'), str):
        try:
            data['items'] = json.loads(data['items'])
        except ValueError:
            data['items'] = []
    inv = inv_service.save_invoice(user=request.user, invoice=invoice, data=data)
    return JsonResponse({'ok': True, 'id': inv.id, 'total': str(inv.total_amount)})


@finance_access_required
def invoice_print(request, invoice_id):
    company = get_default_company()
    invoice = get_object_or_404(Invoice, id=invoice_id, company=company)
    return render(request, 'finance/invoice_print.html', {
        'invoice': invoice, 'items': invoice.items.all(),
    })


@finance_access_required(api=True)
@require_POST
def invoice_delete_api(request, invoice_id):
    company = get_default_company()
    invoice = get_object_or_404(Invoice, id=invoice_id, company=company)
    inv_service.delete_invoice(invoice, user=request.user)
    return JsonResponse({'ok': True})


@finance_access_required(api=True)
@require_POST
def invoice_pay_api(request, invoice_id):
    company = get_default_company()
    invoice = get_object_or_404(Invoice, id=invoice_id, company=company)
    data = _body(request)
    account = company.accounts.filter(id=data.get('account')).first()
    if not account:
        return JsonResponse({'ok': False, 'error': 'Оберіть рахунок'}, status=400)
    txn = inv_service.create_payment_for_invoice(
        invoice, user=request.user, account=account, amount=data.get('amount') or None)
    invoice.refresh_from_db()
    return JsonResponse({'ok': True, 'status': invoice.get_status_display(),
                         'paid': str(invoice.paid_amount), 'due': str(invoice.balance_due)})
