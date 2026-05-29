"""Адмінка фінансового кабінету: реєстрація основних сутностей."""
from __future__ import annotations

from django.contrib import admin

from .models import (
    Account, AuditLog, AutomationRule, BudgetPlan, Category, Company,
    Counterparty, CurrencyRate, FinancialMetric, IntegrationConnection,
    Invoice, InvoiceItem, Project, Tag, Transaction,
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


for _model in (CurrencyRate, Category, Counterparty, Project, Tag,
               IntegrationConnection, BudgetPlan, FinancialMetric):
    admin.site.register(_model)
