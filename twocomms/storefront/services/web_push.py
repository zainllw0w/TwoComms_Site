import json
from importlib import import_module
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from django.conf import settings
from django.templatetags.static import static
from django.utils import timezone
from django.utils.text import slugify

try:
    from pywebpush import WebPushException, webpush
except ModuleNotFoundError:
    WebPushException = RuntimeError
    webpush = None

_webpush_dependency_resolved = webpush is not None

from storefront.models import (
    PushNotificationCampaign,
    PushNotificationDelivery,
    WebPushDeviceSubscription,
)


class WebPushConfigurationError(RuntimeError):
    pass


def _resolve_webpush_dependency():
    global WebPushException, webpush, _webpush_dependency_resolved

    if webpush is not None:
        return webpush, WebPushException
    if _webpush_dependency_resolved:
        return None, WebPushException

    try:
        module = import_module("pywebpush")
    except ModuleNotFoundError:
        WebPushException = RuntimeError
        _webpush_dependency_resolved = True
        return None, WebPushException

    webpush = getattr(module, "webpush", None)
    WebPushException = getattr(module, "WebPushException", RuntimeError)
    _webpush_dependency_resolved = True
    return webpush, WebPushException


def _resolve_vapid_private_key(private_key):
    normalized_key = (private_key or "").strip()
    if not normalized_key:
        raise WebPushConfigurationError("WEB_PUSH_VAPID_PRIVATE_KEY is not configured")

    if "-----BEGIN" not in normalized_key:
        return normalized_key

    try:
        vapid_module = import_module("py_vapid")
    except ModuleNotFoundError as exc:
        raise WebPushConfigurationError("py_vapid dependency is not installed") from exc

    vapid_class = getattr(vapid_module, "Vapid01", None) or getattr(vapid_module, "Vapid", None)
    if vapid_class is None:
        raise WebPushConfigurationError("py_vapid dependency is not installed")

    try:
        return vapid_class.from_pem(normalized_key.encode("utf-8"))
    except Exception as exc:
        raise WebPushConfigurationError(f"WEB_PUSH_VAPID_PRIVATE_KEY is invalid: {exc}") from exc


def is_web_push_configured():
    webpush_callable, _ = _resolve_webpush_dependency()
    return bool(getattr(settings, "WEB_PUSH_ENABLED", False) and webpush_callable is not None)


def _absolute_site_url(raw_value):
    value = (raw_value or "").strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://")):
        return value
    return urljoin(f"{settings.SITE_BASE_URL.rstrip('/')}/", value.lstrip("/"))


def _notification_icon_url():
    custom_path = (getattr(settings, "WEB_PUSH_ICON_PATH", "") or "").strip()
    return _absolute_site_url(custom_path or static("img/favicon-192x192.png"))


def get_default_notification_icon_url():
    return _notification_icon_url()


def _notification_badge_url():
    custom_path = (getattr(settings, "WEB_PUSH_BADGE_PATH", "") or "").strip()
    return _absolute_site_url(custom_path or static("img/favicon-192x192.png"))


def _notification_image_url(campaign):
    if campaign and campaign.image:
        try:
            return _absolute_site_url(campaign.image.url)
        except Exception:
            pass
    return ""


def _tracked_target_url(campaign):
    target_url = _absolute_site_url(campaign.target_url)
    parsed = urlparse(target_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.setdefault("utm_source", "web_push")
    query.setdefault("utm_medium", "push_notification")
    query.setdefault("utm_campaign", slugify(campaign.title)[:48] or f"push-{campaign.pk}")
    updated_query = urlencode(query, doseq=True)
    return urlunparse(parsed._replace(query=updated_query))


def build_campaign_payload(campaign, delivery):
    payload = {
        "title": campaign.title,
        "body": campaign.body,
        "icon": _notification_icon_url(),
        "badge": _notification_badge_url(),
        "url": _tracked_target_url(campaign),
        "tag": f"twc-push-campaign-{campaign.pk}",
        "campaignId": campaign.pk,
        "deliveryToken": str(delivery.event_token),
    }
    image_url = _notification_image_url(campaign)
    if image_url:
        payload["image"] = image_url
    return payload


def _build_subscription_info(subscription):
    return {
        "endpoint": subscription.endpoint,
        "keys": {
            "auth": subscription.auth_key,
            "p256dh": subscription.p256dh_key,
        },
    }


def _vapid_claims():
    subject = (getattr(settings, "WEB_PUSH_VAPID_SUBJECT", "") or "").strip()
    if not subject:
        raise WebPushConfigurationError("WEB_PUSH_VAPID_SUBJECT is not configured")
    return {"sub": subject}


def send_campaign(campaign):
    webpush_callable, webpush_exception_class = _resolve_webpush_dependency()

    if not getattr(settings, "WEB_PUSH_ENABLED", False):
        raise WebPushConfigurationError("Web Push is not configured")
    if webpush_callable is None:
        raise WebPushConfigurationError("pywebpush dependency is not installed")

    private_key = (getattr(settings, "WEB_PUSH_VAPID_PRIVATE_KEY", "") or "").strip()
    if not private_key:
        raise WebPushConfigurationError("WEB_PUSH_VAPID_PRIVATE_KEY is not configured")
    vapid_private_key = _resolve_vapid_private_key(private_key)

    campaign.status = PushNotificationCampaign.Status.SENDING
    campaign.last_error = ""
    campaign.sent_started_at = timezone.now()
    campaign.sent_finished_at = None
    campaign.save(update_fields=["status", "last_error", "sent_started_at", "sent_finished_at", "updated_at"])

    subscriptions = WebPushDeviceSubscription.objects.filter(is_active=True).order_by("id")
    if campaign.audience_mode != PushNotificationCampaign.AudienceMode.ALL_ACTIVE:
        subscriptions = subscriptions.none()

    if not subscriptions.exists():
        campaign.status = PushNotificationCampaign.Status.FAILED
        campaign.last_error = "Немає активних підписок для надсилання."
        campaign.sent_finished_at = timezone.now()
        campaign.save(
            update_fields=["status", "last_error", "sent_finished_at", "updated_at"]
        )
        return {
            "targeted": 0,
            "sent": 0,
            "failed": 0,
        }

    sent_count = 0
    failed_count = 0
    last_error = ""

    for subscription in subscriptions.iterator(chunk_size=100):
        delivery = PushNotificationDelivery.objects.create(
            campaign=campaign,
            subscription=subscription,
        )
        payload = build_campaign_payload(campaign, delivery)
        try:
            response = webpush_callable(
                subscription_info=_build_subscription_info(subscription),
                data=json.dumps(payload),
                vapid_private_key=vapid_private_key,
                vapid_claims=_vapid_claims(),
                ttl=86400,
                timeout=10,
            )
            delivery.status = PushNotificationDelivery.Status.SENT
            delivery.sent_at = timezone.now()
            delivery.push_service_status_code = getattr(response, "status_code", None)
            delivery.save(update_fields=["status", "sent_at", "push_service_status_code"])
            subscription.mark_delivery_success()
            sent_count += 1
        except webpush_exception_class as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            error_message = str(exc)[:255]
            delivery.push_service_status_code = status_code
            delivery.error_code = str(status_code or "webpush_error")
            delivery.error_message = error_message
            delivery.failed_at = timezone.now()
            if status_code in {404, 410}:
                delivery.status = PushNotificationDelivery.Status.EXPIRED
                subscription.mark_inactive(error_message)
            else:
                delivery.status = PushNotificationDelivery.Status.FAILED
                subscription.register_failure(error_message)
            delivery.save(
                update_fields=[
                    "status",
                    "push_service_status_code",
                    "error_code",
                    "error_message",
                    "failed_at",
                ]
            )
            failed_count += 1
            last_error = error_message
        except Exception as exc:
            error_message = str(exc)[:255]
            delivery.status = PushNotificationDelivery.Status.FAILED
            delivery.error_code = "unexpected_error"
            delivery.error_message = error_message
            delivery.failed_at = timezone.now()
            delivery.save(
                update_fields=["status", "error_code", "error_message", "failed_at"]
            )
            subscription.register_failure(error_message)
            failed_count += 1
            last_error = error_message

    campaign.sent_finished_at = timezone.now()
    campaign.last_error = last_error
    campaign.save(update_fields=["sent_finished_at", "last_error", "updated_at"])
    campaign.sync_delivery_metrics()

    return {
        "targeted": campaign.targeted_count,
        "sent": sent_count,
        "failed": failed_count,
    }


def record_delivery_event(delivery, event_type):
    now = timezone.now()
    update_fields = ["status"]

    if event_type == "displayed" and delivery.displayed_at is None:
        delivery.displayed_at = now
        delivery.status = PushNotificationDelivery.Status.DISPLAYED
        update_fields.append("displayed_at")
    elif event_type == "clicked" and delivery.clicked_at is None:
        delivery.clicked_at = now
        if delivery.displayed_at is None:
            delivery.displayed_at = now
            update_fields.append("displayed_at")
        delivery.status = PushNotificationDelivery.Status.CLICKED
        update_fields.append("clicked_at")
    elif event_type == "closed" and delivery.closed_at is None:
        delivery.closed_at = now
        if delivery.displayed_at is None:
            delivery.displayed_at = now
            update_fields.append("displayed_at")
        if delivery.status != PushNotificationDelivery.Status.CLICKED:
            delivery.status = PushNotificationDelivery.Status.CLOSED
        update_fields.append("closed_at")
    else:
        return False

    delivery.save(update_fields=update_fields)
    delivery.campaign.sync_delivery_metrics()
    return True
