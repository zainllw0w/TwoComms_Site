"""Рахунки-фактури (інвойси) та їх позиції."""
from __future__ import annotations

from decimal import Decimal

from django.db import models

from .models_core import Company, Counterparty, Project


class Invoice(models.Model):
    """Рахунок-фактура клієнту."""

    STATUS_DRAFT = 'draft'
    STATUS_ISSUED = 'issued'
    STATUS_SENT = 'sent'
    STATUS_PARTIAL = 'partially_paid'
    STATUS_PAID = 'paid'
    STATUS_OVERDUE = 'overdue'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Чернетка'),
        (STATUS_ISSUED, 'Виставлено'),
        (STATUS_SENT, 'Надіслано'),
        (STATUS_PARTIAL, 'Частково оплачено'),
        (STATUS_PAID, 'Оплачено'),
        (STATUS_OVERDUE, 'Прострочено'),
        (STATUS_CANCELLED, 'Скасовано'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='invoices')
    number = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    currency = models.CharField(max_length=3, default='UAH')
    issue_date = models.DateField()
    due_date = models.DateField(blank=True, null=True)

    logo = models.ImageField(upload_to='finance/invoices/', blank=True, null=True)

    # Реквізити постачальника.
    supplier_name = models.CharField(max_length=255, blank=True, default='')
    supplier_edrpou = models.CharField(max_length=32, blank=True, default='')
    supplier_iban = models.CharField(max_length=64, blank=True, default='')
    supplier_country = models.CharField(max_length=64, blank=True, default='')
    supplier_address = models.CharField(max_length=512, blank=True, default='')

    # Реквізити платника (отримувача).
    payer_name = models.CharField(max_length=255, blank=True, default='')
    payer_edrpou = models.CharField(max_length=32, blank=True, default='')
    payer_iban = models.CharField(max_length=64, blank=True, default='')
    payer_country = models.CharField(max_length=64, blank=True, default='')
    payer_address = models.CharField(max_length=512, blank=True, default='')

    vat_enabled = models.BooleanField(default=False)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('20'))

    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))
    discount_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))
    delivery_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))

    notes = models.TextField(blank=True, default='')
    payment_terms = models.CharField(max_length=512, blank=True, default='')

    counterparty = models.ForeignKey(Counterparty, on_delete=models.SET_NULL, blank=True, null=True,
                                     related_name='invoices')
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, blank=True, null=True,
                                related_name='invoices')
    is_demo = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Рахунок-фактура'
        verbose_name_plural = 'Рахунки-фактури'
        ordering = ['-issue_date', '-id']

    def __str__(self):
        return f'№{self.number} — {self.total_amount} {self.currency}'

    def recalc_totals(self, save: bool = True) -> Decimal:
        """Перерахунок підсумків з позицій: total = subtotal − discount + delivery + tax."""
        items = list(self.items.all())
        subtotal = sum((i.amount for i in items), Decimal('0'))
        if self.vat_enabled:
            tax = (subtotal * self.vat_rate / Decimal('100')).quantize(Decimal('0.01'))
        else:
            tax = Decimal('0')
        total = subtotal - self.discount_amount + self.delivery_amount + tax
        self.subtotal = subtotal
        self.tax_amount = tax
        self.total_amount = total
        if save:
            Invoice.objects.filter(pk=self.pk).update(
                subtotal=subtotal, tax_amount=tax, total_amount=total,
            )
        return total

    @property
    def paid_amount(self) -> Decimal:
        """Сума пов'язаних фактичних платежів."""
        from .models_txn import Transaction
        return self.payments.filter(status=Transaction.STATUS_ACTUAL).aggregate(
            s=models.Sum('amount'))['s'] or Decimal('0')

    @property
    def balance_due(self) -> Decimal:
        return self.total_amount - self.paid_amount

    def recalc_status(self, save: bool = True):
        """Перерахунок статусу за сумою оплат."""
        if self.status in (self.STATUS_DRAFT, self.STATUS_CANCELLED):
            return self.status
        paid = self.paid_amount
        if paid <= 0:
            new_status = self.STATUS_ISSUED if self.status == self.STATUS_PAID else self.status
        elif paid < self.total_amount:
            new_status = self.STATUS_PARTIAL
        else:
            new_status = self.STATUS_PAID
        if new_status != self.status:
            self.status = new_status
            if save:
                Invoice.objects.filter(pk=self.pk).update(status=new_status)
        return self.status


class InvoiceItem(models.Model):
    """Позиція рахунку: товар/послуга."""

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    name = models.CharField(max_length=512)
    quantity = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('1'))
    unit_price = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0'))
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Позиція рахунку'
        verbose_name_plural = 'Позиції рахунку'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.amount = (self.quantity * self.unit_price).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)
