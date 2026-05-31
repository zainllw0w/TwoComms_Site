"""Finance views package."""
from .dashboard import (  # noqa: F401
    financial_health,
)
from .users import (  # noqa: F401
    users,
)
from .ai import (  # noqa: F401
    ai_advisor_page,
    ai_chat_api,
    ai_check_payments_api,
    ai_check_report_api,
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
from .invoices import (  # noqa: F401
    invoices,
    invoice_form,
    invoice_save_api,
    invoice_print,
    invoice_delete_api,
    invoice_pay_api,
)
from .rules import (  # noqa: F401
    rules,
    rule_save_api,
    rule_toggle_api,
    rule_delete_api,
    rule_preview_api,
    rule_apply_api,
)
from .payments import (  # noqa: F401
    payments,
    payments_export,
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
from .integrations_mono import (  # noqa: F401
    mono_connect_api,
    mono_accounts_api,
    mono_link_api,
    mono_sync_api,
    mono_account_settings_api,
    mono_disconnect_api,
    mono_connections_api,
    mono_webhook,
)
from .settings import (  # noqa: F401
    settings_get_api,
    settings_save_api,
    push_subscribe_api,
    push_unsubscribe_api,
    notification_history_api,
)
