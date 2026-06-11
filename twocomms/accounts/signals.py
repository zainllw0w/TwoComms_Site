"""Admin Telegram notifications for new user registrations.

Owner request (2026-06-11): notify admins about EVERY new account,
regardless of the registration path (site form, Google OAuth,
Telegram login).

Implementation: ``post_save`` on ``User`` with ``created=True`` covers
all paths uniformly. The notification is sent from a daemon thread
with a short delay so the social-auth pipeline has time to create the
``UserSocialAuth`` row — that is how we label the signup method.
"""

import threading
import time

from django.contrib.auth.models import User
from django.db import close_old_connections
from django.db.models.signals import post_save
from django.dispatch import receiver

_PROVIDER_LABELS = {
    "google-oauth2": "Google",
    "telegram": "Telegram",
}


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


def _notify_admins(user_id, username, email):
    try:
        # Give the social-auth pipeline a moment to attach the provider row.
        time.sleep(5)
        close_old_connections()

        method = _detect_method(user_id)
        total = User.objects.count()

        from orders.telegram_notifications import telegram_notifier

        message = (
            "👤 <b>Нова реєстрація на сайті</b>\n"
            f"Користувач: <b>{username}</b>\n"
            f"Email: {email or '—'}\n"
            f"Спосіб: {method}\n"
            f"Всього акаунтів: {total}"
        )
        telegram_notifier.send_admin_message(message)
    except Exception:
        # Notifications must never break registration.
        pass
    finally:
        close_old_connections()


@receiver(post_save, sender=User, dispatch_uid="notify_admins_new_user")
def notify_admins_on_registration(sender, instance, created, **kwargs):
    if not created:
        return
    threading.Thread(
        target=_notify_admins,
        args=(instance.pk, instance.username, instance.email),
        daemon=True,
    ).start()
