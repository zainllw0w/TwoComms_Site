"""Finance views package."""
from .shell import (  # noqa: F401
    analytics, ai_advisor, calendar, invoices, rules, users, accounts,
)
from .payments import (  # noqa: F401
    payments,
    transaction_create_api,
    transaction_detail_api,
    transaction_update_api,
    transaction_delete_api,
    transaction_duplicate_api,
    transaction_convert_transfer_api,
    transaction_split_api,
    transaction_mark_actual_api,
    transactions_bulk_api,
    dropdowns_api,
    quick_create_entity_api,
)
