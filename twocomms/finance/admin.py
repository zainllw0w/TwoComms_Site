"""Адмінка фінансового кабінету: реєстрація основних сутностей."""
from __future__ import annotations

from django.contrib import admin

from .models import (
    Account, AuditLog, AutomationRule, BudgetPlan, Category, Company,
    Counterparty, CounterpartyCard, CurrencyRate, FinancialMetric,
    IntegrationConnection, Invoice, InvoiceItem, ObligationSettlement,
    Project, Tag, Transaction,
    Reseller, ConsignmentShipment, ConsignmentItem, ResellerPayment,
    ConsignmentSale,
)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'base_currency', 'is_demo', 'created_at')


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'currency', 'current_balance', 'is_active', 'is_archived')
    list_filter = ('type', 'currency', 'is_active', 'is_archived')
    search_fields = ('name',)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'type', 'status', 'amount', 'currency', 'account', 'date_actual', 'category')
    list_filter = ('type', 'status', 'currency', 'source')
    search_fields = ('comment', 'external_id')
    date_hierarchy = 'date_actual'
    raw_id_fields = ('account', 'to_account', 'category', 'counterparty', 'project',
                     'parent_transaction', 'recurrence_rule', 'linked_invoice')


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('number', 'status', 'total_amount', 'currency', 'issue_date', 'due_date')
    list_filter = ('status', 'currency', 'vat_enabled')
    search_fields = ('number', 'payer_name')
    inlines = [InvoiceItemInline]


@admin.register(AutomationRule)
class AutomationRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'transaction_type', 'is_enabled', 'priority', 'applied_count')
    list_filter = ('is_enabled', 'transaction_type')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'action', 'entity_type', 'entity_id', 'summary')
    list_filter = ('action', 'entity_type', 'source')
    search_fields = ('summary', 'entity_id')
    date_hierarchy = 'created_at'


class ConsignmentItemInline(admin.TabularInline):
    model = ConsignmentItem
    extra = 0
    raw_id_fields = ('stock_item', 'reseller')


@admin.register(Reseller)
class ResellerAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'terms_kind', 'counterparty', 'created_at')
    list_filter = ('status', 'terms_kind')
    search_fields = ('name',)
    raw_id_fields = ('counterparty',)


@admin.register(ConsignmentShipment)
class ConsignmentShipmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'reseller', 'number', 'date', 'debt_amount', 'currency')
    list_filter = ('currency', 'external_source')
    search_fields = ('number',)
    raw_id_fields = ('reseller', 'debt_txn')
    inlines = [ConsignmentItemInline]


@admin.register(ResellerPayment)
class ResellerPaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'reseller', 'date', 'amount', 'currency')
    raw_id_fields = ('reseller', 'txn')
    date_hierarchy = 'date'


@admin.register(ConsignmentSale)
class ConsignmentSaleAdmin(admin.ModelAdmin):
    list_display = ('id', 'reseller', 'item', 'qty', 'date', 'unit_price', 'creates_debt')
    raw_id_fields = ('reseller', 'item', 'debt_txn')
    date_hierarchy = 'date'


@admin.register(ObligationSettlement)
class ObligationSettlementAdmin(admin.ModelAdmin):
    list_display = ('id', 'period_label', 'amount', 'currency', 'rule', 'payment', 'created_at')
    raw_id_fields = ('payment', 'rule', 'planned_txn')
    date_hierarchy = 'created_at'


@admin.register(CounterpartyCard)
class CounterpartyCardAdmin(admin.ModelAdmin):
    list_display = ('id', 'counterparty', 'bank', 'last4', 'pan_mask', 'is_primary', 'last_used_at')
    list_filter = ('bank', 'is_primary')
    search_fields = ('pan_mask', 'last4', 'iban', 'label')
    raw_id_fields = ('counterparty',)


for _model in (CurrencyRate, Category, Counterparty, Project, Tag,
               IntegrationConnection, BudgetPlan, FinancialMetric):
    admin.site.register(_model)
