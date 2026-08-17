"""Admin Telegram notifications for new user registrations.

Owner request (2026-06-11): notify admins about EVERY new account,
regardless of the registration path (site form, Google OAuth,
Telegram login).

Implementation: ``post_save`` on ``User`` with ``created=True`` covers
all paths uniformly. The signal commits an idempotent outbox intent; the
outbox worker resolves the user and social-auth association immediately
before delivery, so the signup method is not guessed in the request.
"""

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

_PROVIDER_LABELS = {
    "google-oauth2": "Google",
    "telegram": "Telegram",
}

_SOCIAL_AUTH_ASSOCIATION_DELAY_SECONDS = 5


def _detect_method(user_id):
    try:
        from social_django.models import UserSocialAuth

        social = (
            UserSocialAuth.objects.filter(user_id=user_id)
            .values_list("provider", flat=True)
            .first()
        )
        if social:
            return _PROVIDER_LABELS.get(social, social)
    except Exception:
        pass
    return "сайт (email/пароль)"


def registration_notification_text(user_id):
    """Build registration text from committed rows at delivery time.

    The outbox payload intentionally contains only ``user_id``. This keeps
    personal data out of deferred task metadata and lets social-auth finish
    associating the provider before the method is classified.
    """
    user = User.objects.filter(pk=user_id).first()
    if user is None:
        return None
    method = _detect_method(user.pk)
    total = User.objects.count()
    return (
        "👤 <b>Нова реєстрація на сайті</b>\n"
        f"Користувач: <b>{user.username}</b>\n"
        f"Email: {user.email or '—'}\n"
        f"Спосіб: {method}\n"
        f"Всього акаунтів: {total}"
    )


def _notify_admins(user_id, *_legacy_args):
    try:
        from management.services.instagram_bot import notify_manager

        notify_manager(
            "registration pending",
            dedupe_key=f"registration:{int(user_id)}",
            event_type="registration",
            metadata={
                "transport": "site_registration",
                "registration_user_id": str(user_id),
            },
            deliver_immediately=False,
            not_before_seconds=_SOCIAL_AUTH_ASSOCIATION_DELAY_SECONDS,
        )
    except Exception:
        # Notifications must never break registration.
        pass


@receiver(post_save, sender=User, dispatch_uid="notify_admins_new_user")
def notify_admins_on_registration(sender, instance, created, **kwargs):
    if not created or getattr(settings, "TESTING", False):
        return
    # Persist the outbox intent in the same transaction as the User row.
    # Delivery and provider lookup remain deferred to the notification worker.
    _notify_admins(instance.pk)
