"""Finance views package."""
from .shell import (  # noqa: F401
    ai_advisor, invoices, rules, users,
)
from .calendar_views import (  # noqa: F401
    calendar,
    calendar_day_api,
)
from .analytics import (  # noqa: F401
    analytics,
    report,
    report_export,
    metric_create_api,
    debt_settle_api,
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
from .accounts import (  # noqa: F401
    accounts,
    account_create_api,
    account_update_api,
    account_archive_api,
    account_delete_api,
    accounts_reorder_api,
    account_correct_balance_api,
    integration_providers_api,
    integration_start_api,
    integration_status_api,
    integration_refresh_qr_api,
    integration_link_api,
    integration_cancel_api,
    import_preview_api,
    import_confirm_api,
)
