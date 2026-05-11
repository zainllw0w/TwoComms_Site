from .dashboard import dashboard, today_changes  # noqa: F401
from .categories import (  # noqa: F401
    category_list,
    category_detail,
    stock_adjust,
    stock_bulk_add,
)
from .prints import (  # noqa: F401
    print_list,
    print_detail,
    print_create,
    print_edit,
    print_adjust,
)
from .write_off import write_off_entry, write_off_submit  # noqa: F401
from .history import history_list, history_verify  # noqa: F401
from .finance import finance_dashboard  # noqa: F401
from .auth_views import login_view, logout_view  # noqa: F401
from .errors import handler404, handler500  # noqa: F401
from .settings import (  # noqa: F401
    settings_index,
    settings_categories,
    settings_category_form,
    settings_category_toggle,
    settings_subcategories,
    settings_subcategory_form,
    settings_subcategory_toggle,
    settings_colors,
    settings_color_form,
    settings_color_create_ajax,
)
