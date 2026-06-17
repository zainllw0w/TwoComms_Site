"""
Онбординг-гейт менеджерів (доступ закрито до підпису згоди/документа).

Серверна блокада (не лише модалка): перехоплює management-вью і веде на
онбординг, поки умови не виконані. Жорсткий whitelist + ніколи не блокує
staff/superuser/вебхуки/static. Вмикається лише за прапором
settings.MANAGEMENT_ONBOARDING_ENABLED (за замовчуванням OFF), щоб не
заблокувати чинних менеджерів до готовності флоу.

Док: twocomms/Management Implementations/03_ONBOARDING_CONTRACTS_DIIA.md
"""
from django.conf import settings
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin

# Шляхи, які гейт НЕ блокує (точні або префікси).
_WHITELIST_PREFIXES = (
    "/onboarding/",
    "/logout/",
    "/accounts/logout",
    "/static/",
    "/media/",
    "/tg-manager/webhook/",
    "/payments/monobank/webhook/",
    "/activity/pulse/",
    "/binotel/webhook/",
)


def manager_is_gated(user) -> bool:
    """Чи треба заблокувати менеджера до проходження онбордингу."""
    from management.models import ManagerOnboardingConsent, ManagerDocument

    profile = getattr(user, "userprofile", None)
    if not profile or not getattr(profile, "is_manager", False):
        return False

    access_status = getattr(profile, "access_status", "active")
    if access_status == "blocked_until_document":
        return True

    # Документ, що блокує доступ і не підписаний.
    if ManagerDocument.objects.filter(
        owner=user, access_blocking=True
    ).exclude(status=ManagerDocument.Status.SIGNED).exists():
        return True

    # Немає свіжої згоди для потрібної версії правил.
    required_version = (getattr(profile, "onboarding_required_version", "") or
                        getattr(settings, "MANAGEMENT_RULES_VERSION", "1"))
    has_consent = ManagerOnboardingConsent.objects.filter(
        owner=user, rules_version=required_version,
        accepted_18plus=True, accepted_rules=True, accepted_pdn=True,
    ).exists()
    return not has_consent


class ManagementOnboardingGate(MiddlewareMixin):
    def process_request(self, request):
        if not getattr(settings, "MANAGEMENT_ONBOARDING_ENABLED", False):
            return None
        # Тільки management-хост.
        if getattr(request, "urlconf", None) != "twocomms.urls_management":
            return None
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None
        # staff/superuser ніколи не блокуються.
        if user.is_staff or user.is_superuser:
            return None

        path = request.path or "/"
        for prefix in _WHITELIST_PREFIXES:
            if path.startswith(prefix):
                return None

        try:
            if manager_is_gated(user):
                return redirect("management_onboarding")
        except Exception:
            # Гейт ніколи не повинен валити сайт — у разі помилки пропускаємо.
            return None
        return None
