"""Сервіс рахунків-фактур: створення/оновлення з позиціями, оплата, статуси (ТЗ 08)."""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from ..models import Invoice, InvoiceItem, get_default_company
from . import audit as audit_service


def next_invoice_number(company) -> str:
    year = timezone.now().year
    count = company.invoices.filter(issue_date__year=year).count() + 1
    return f'{year}-{count:04d}'


@db_transaction.atomic
def save_invoice(*, user, invoice=None, data) -> Invoice:
    """Створює або оновлює інвойс разом із позиціями. data — dict."""
    company = get_default_company()
    is_new = invoice is None
    if is_new:
        invoice = Invoice(company=company)

    invoice.number = (data.get('number') or '').strip() or next_invoice_number(company)
    invoice.currency = data.get('currency', 'UAH')
    invoice.issue_date = _date(data.get('issue_date')) or timezone.now().date()
    invoice.due_date = _date(data.get('due_date'))
    invoice.vat_enabled = bool(data.get('vat_enabled'))
    invoice.vat_rate = Decimal(str(data.get('vat_rate') or '20'))
    invoice.discount_amount = Decimal(str(data.get('discount_amount') or '0'))
    invoice.delivery_amount = Decimal(str(data.get('delivery_amount') or '0'))
    invoice.notes = data.get('notes', '')
    invoice.payment_terms = data.get('payment_terms', '')

    for prefix in ('supplier', 'payer'):
        for field in ('name', 'edrpou', 'iban', 'country', 'address'):
            key = f'{prefix}_{field}'
            setattr(invoice, key, data.get(key, '') or '')

    if data.get('counterparty'):
        invoice.counterparty = company.counterparties.filter(id=data['counterparty']).first()
    if data.get('project'):
        invoice.project = company.projects.filter(id=data['project']).first()
    if data.get('status'):
        invoice.status = data['status']
    elif is_new:
        invoice.status = Invoice.STATUS_DRAFT

    invoice.save()

    # Позиції: повна заміна.
    invoice.items.all().delete()
    for i, item in enumerate(data.get('items', [])):
        name = (item.get('name') or '').strip()
        if not name:
            continue
        InvoiceItem.objects.create(
            invoice=invoice, name=name,
            quantity=Decimal(str(item.get('quantity') or '1')),
            unit_price=Decimal(str(item.get('unit_price') or '0')),
            sort_order=i,
        )
    invoice.recalc_totals(save=True)

    audit_service.log_action(user, 'create' if is_new else 'update', 'invoice', invoice.id,
                             summary=f'Рахунок №{invoice.number} на {invoice.total_amount}',
                             company=company)
    return invoice


def _date(value):
    if not value:
        return None
    import datetime as dt
    try:
        return dt.date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


@db_transaction.atomic
def create_payment_for_invoice(invoice: Invoice, *, user, account, amount=None, date_actual=None):
    """Створює дохід, пов'язаний з інвойсом; перераховує статус (ТЗ 08 §5)."""
    from . import transactions as txn_service
    amount = Decimal(str(amount)) if amount is not None else invoice.balance_due
    if amount <= 0:
        return None
    txn = txn_service.create_transaction(
        user=user, type='income', amount=amount, account=account,
        currency=invoice.currency, date_actual=date_actual or timezone.now(),
        counterparty=invoice.counterparty, project=invoice.project,
        comment=f'Оплата рахунку №{invoice.number}', source='invoice',
        linked_invoice=invoice,
    )
    return txn


def delete_invoice(invoice: Invoice, *, user):
    num = invoice.number
    iid = invoice.id
    company = invoice.company
    invoice.delete()
    audit_service.log_action(user, 'delete', 'invoice', iid,
                             summary=f'Видалено рахунок №{num}', company=company)


def vat_report(company, params=None):
    """Дані для вкладки ПДВ."""
    rows = []
    for inv in company.invoices.filter(vat_enabled=True).order_by('-issue_date'):
        rows.append({
            'number': inv.number,
            'date': inv.issue_date.isoformat() if inv.issue_date else '',
            'counterparty': inv.payer_name or (inv.counterparty.name if inv.counterparty else '—'),
            'subtotal': inv.subtotal,
            'tax': inv.tax_amount,
            'total': inv.total_amount,
            'status': inv.get_status_display(),
        })
    return rows
