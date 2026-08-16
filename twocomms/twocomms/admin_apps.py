from __future__ import annotations

import re
import warnings

from django.contrib.admin.apps import AdminConfig
from django.utils.deprecation import RemovedInDjango70Warning


SOCIAL_AUTH_LIST_SELECT_RELATED_WARNING = (
    "Setting ModelAdmin.list_select_related to True is deprecated. "
    "Use False or a list or tuple of fields to fetch instead."
)


class TwoCommsAdminConfig(AdminConfig):
    """Apply the social-auth admin compatibility shim during autodiscovery."""

    def ready(self):
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=f"^{re.escape(SOCIAL_AUTH_LIST_SELECT_RELATED_WARNING)}$",
                category=RemovedInDjango70Warning,
                module=r"^social_django\.admin$",
            )
            super().ready()

        from twocomms.social_auth_admin import register_social_auth_compat_admin

        register_social_auth_compat_admin()
