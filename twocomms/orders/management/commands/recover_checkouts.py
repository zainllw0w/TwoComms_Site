"""Abandoned-checkout recovery: admin Telegram alerts + optional emails.

Runs from cron every 30 minutes. Picks up CheckoutCapture rows that:
- were last touched 45min..7days ago,
- are not converted into an order,
- have at least a phone or an email.

For each capture:
1. Sends a one-time Telegram alert to admins (name + phone + cart) so
   they can reach out manually (Instagram/phone workflow).
2. If SMTP is configured (EMAIL_HOST_PASSWORD set) and the capture has
   an email — sends a one-time friendly recovery email.
"""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from orders.models import CheckoutCapture


def _cart_lines(snapshot):
    """Resolve cart snapshot into human-readable lines."""
    lines = []
    try:
        from storefront.models import Product

        ids = []
        for item in (snapshot or {}).values():
            pid = item.get('product_id')
            if pid:
                ids.append(pid)
        products = {p.id: p for p in Product.objects.filter(id__in=ids)}
        for item in (snapshot or {}).values():
            p = products.get(item.get('product_id'))
            title = p.title if p else f"товар #{item.get('product_id')}"
            qty = item.get('qty', 1)
            size = item.get('size') or ''
            extra = f" ({size})" if size else ''
            lines.append(f"• {title}{extra} ×{qty}")
    except Exception:
        pass
    return lines


class Command(BaseCommand):
    help = 'Notify admins about abandoned checkouts and send recovery emails'

    def handle(self, *args, **options):
        now = timezone.now()
        candidates = CheckoutCapture.objects.filter(
            converted=False,
            updated_at__lt=now - timedelta(minutes=45),
            updated_at__gt=now - timedelta(days=7),
        ).exclude(phone='', email='')

        notified = emailed = 0
        for cap in candidates:
            lines = _cart_lines(cap.cart_snapshot)
            cart_text = "\n".join(lines) if lines else "(кошик не зберігся)"

            if cap.admin_notified_at is None:
                try:
                    from orders.telegram_notifications import telegram_notifier

                    msg = (
                        "🛒 <b>Покинуте оформлення замовлення!</b>\n"
                        f"Ім'я: <b>{cap.full_name or '—'}</b>\n"
                        f"Телефон: {cap.phone or '—'}\n"
                        f"Email: {cap.email or '—'}\n"
                        f"Сума: <b>{cap.cart_total} грн</b>\n"
                        f"{cart_text}\n"
                        f"<i>Останнія активність: {timezone.localtime(cap.updated_at).strftime('%d.%m %H:%M')}. "
                        "Можна написати/подзвонити та допомогти завершити.</i>"
                    )
                    telegram_notifier.send_admin_message(msg)
                    cap.admin_notified_at = now
                    cap.save(update_fields=['admin_notified_at'])
                    notified += 1
                except Exception as exc:
                    self.stderr.write(f"TG fail for {cap.pk}: {exc}")

            if (
                cap.recovery_sent_at is None
                and cap.email
                and getattr(settings, 'EMAIL_HOST_PASSWORD', '')
            ):
                try:
                    from django.core.mail import send_mail

                    name = (cap.full_name or '').split(' ')[0] or 'друже'
                    plain_lines = "\n".join(lines) if lines else ""
                    body = (
                        f"Привіт, {name}!\n\n"
                        "Ти майже оформив замовлення на TwoComms, але щось пішло не так "
                        "(буває — зв'язок, банк, життя).\n\n"
                        f"Твій кошик чекає:\n{plain_lines}\n\n"
                        "Повернутися до оформлення: https://twocomms.shop/cart/\n\n"
                        "Якщо виникли питання чи щось не працювало — просто відповідай "
                        "на цей лист або напиши нам в Instagram @twocomms, допоможемо.\n\n"
                        "Дякуємо, що ти з нами 🖤\nTwoComms — Stay Strong"
                    )
                    send_mail(
                        "Твоє замовлення на TwoComms майже готове 🖤",
                        body,
                        settings.DEFAULT_FROM_EMAIL,
                        [cap.email],
                        fail_silently=False,
                    )
                    cap.recovery_sent_at = now
                    cap.save(update_fields=['recovery_sent_at'])
                    emailed += 1
                except Exception as exc:
                    self.stderr.write(f"Email fail for {cap.pk}: {exc}")

        # Housekeeping: drop stale rows older than 30 days.
        CheckoutCapture.objects.filter(updated_at__lt=now - timedelta(days=30)).delete()
        self.stdout.write(f"recover_checkouts: tg={notified} email={emailed}")
