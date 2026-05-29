"""Finance app models — агрегатор.

Доменні моделі розкладені по тематичних модулях у межах застосунку
(``models_core``, ``models_txn``, ``models_billing``, ``models_ops``) і
ре-експортуються тут, щоб Django бачив їх як ``finance.models.*``.
Усі моделі належать застосунку ``finance`` (app_label визначається
автоматично за розташуванням файлів у пакеті).
"""
from __future__ import annotations

from .models_core import (  # noqa: F401
    Account,
    Category,
    Company,
    Counterparty,
    CurrencyRate,
    Project,
    Tag,
    get_default_company,
)
from .models_txn import (  # noqa: F401
    Attachment,
    RecurrenceRule,
    Transaction,
)
from .models_billing import (  # noqa: F401
    Invoice,
    InvoiceItem,
)
from .models_ops import (  # noqa: F401
    AuditLog,
    AutomationRule,
    BudgetPlan,
    FinancialMetric,
    IntegrationConnection,
    RuleApplication,
)

__all__ = [
    'Account', 'Category', 'Company', 'Counterparty', 'CurrencyRate',
    'Project', 'Tag', 'get_default_company',
    'Attachment', 'RecurrenceRule', 'Transaction',
    'Invoice', 'InvoiceItem',
    'AuditLog', 'AutomationRule', 'BudgetPlan', 'FinancialMetric',
    'IntegrationConnection', 'RuleApplication',
]
