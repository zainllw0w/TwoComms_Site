from __future__ import annotations

from django.conf import settings
from django.core.mail import send_mail


def _manager_emails() -> list[str]:
    configured = getattr(settings, "DTF_MANAGER_EMAILS", None)
    if configured:
        return [email for email in configured if email]
    fallback = getattr(settings, "DEFAULT_FROM_EMAIL", "")
    return [fallback] if fallback else []


def notify_manager_new_order(order, quote=None) -> bool:
    recipients = _manager_emails()
    if not recipients:
        return False

    subject = f"[DTF] New order {order.order_number}"
    payload = [
        f"Order: {order.order_number}",
        f"Customer: {order.name}",
        f"Phone: {order.phone}",
        f"Lifecycle: {order.lifecycle_status}",
    ]
    if quote:
        payload.append(f"Quote total: {quote.total} {quote.currency}")
    payload.append(f"Source: {order.order_type}")

    send_mail(
        subject=subject,
        message="\n".join(payload),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=recipients,
        fail_silently=True,
    )
    return True


def notify_customer_status_change(order, public_message: str = "") -> bool:
    email = ""
    if getattr(order, "contact_handle", "") and "@" in order.contact_handle:
        email = order.contact_handle.strip()
    if not email:
        return False

    subject = f"DTF order update: {order.order_number}"
    payload = [
        f"Status: {order.lifecycle_status}",
        public_message or "Order status updated.",
    ]
    send_mail(
        subject=subject,
        message="\n".join(payload),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[email],
        fail_silently=True,
    )
    return True
