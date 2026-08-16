from __future__ import annotations

from django.contrib import admin
from django.contrib.admin.sites import NotRegistered
from social_django.admin import UserSocialAuthOption
from social_django.models import UserSocialAuth


class UserSocialAuthCompatAdmin(UserSocialAuthOption):
    """Django 6.1-compatible social-auth admin with an explicit join."""

    list_select_related = ("user",)


def register_social_auth_compat_admin() -> None:
    try:
        admin.site.unregister(UserSocialAuth)
    except NotRegistered:
        pass
    admin.site.register(UserSocialAuth, UserSocialAuthCompatAdmin)
