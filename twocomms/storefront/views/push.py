import json

from django.conf import settings
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from accounts.models import UserProfile
from storefront.models import PushNotificationDelivery, WebPushDeviceSubscription
from storefront.services.web_push import is_web_push_configured, record_delivery_event


def _read_json_body(request):
    try:
        return json.loads((request.body or b"{}").decode("utf-8") or "{}")
    except (TypeError, ValueError, UnicodeDecodeError):
        return None


def _validate_subscription_payload(payload):
    if not isinstance(payload, dict):
        return None

    subscription = payload.get("subscription") or {}
    endpoint = (subscription.get("endpoint") or "").strip()
    keys = subscription.get("keys") or {}
    auth_key = (keys.get("auth") or "").strip()
    p256dh_key = (keys.get("p256dh") or "").strip()

    if not endpoint or not auth_key or not p256dh_key:
        return None

    device_type = (payload.get("device_type") or "").strip().lower()
    if device_type not in {choice[0] for choice in WebPushDeviceSubscription.DeviceType.choices}:
        device_type = WebPushDeviceSubscription.DeviceType.UNKNOWN

    metadata = payload.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}

    return {
        "endpoint": endpoint,
        "auth_key": auth_key,
        "p256dh_key": p256dh_key,
        "installation_id": (payload.get("installation_id") or "").strip()[:64],
        "language": (payload.get("language") or "").strip()[:16],
        "timezone": (payload.get("timezone") or "").strip()[:64],
        "browser_family": (payload.get("browser_family") or "").strip()[:64],
        "operating_system": (payload.get("operating_system") or "").strip()[:64],
        "device_type": device_type,
        "user_agent": (payload.get("user_agent") or request_user_agent(payload)).strip()[:4000],
        "last_seen_path": (payload.get("last_seen_path") or "").strip()[:512],
        "metadata": metadata,
    }


def request_user_agent(payload):
    return payload.get("userAgent") or payload.get("user_agent") or ""


def _user_preference_snapshot(user):
    if not getattr(user, "is_authenticated", False):
        return {}

    try:
        profile = user.userprofile
    except UserProfile.DoesNotExist:
        return {}

    return {
        "marketing_enabled": bool(profile.push_marketing_enabled),
        "order_updates_enabled": bool(profile.push_order_updates_enabled),
    }


@require_http_methods(["POST"])
def push_subscribe(request):
    if not is_web_push_configured():
        return JsonResponse({"ok": False, "error": "Web Push is not configured."}, status=400)

    payload = _read_json_body(request)
    normalized = _validate_subscription_payload(payload)
    if normalized is None:
        return JsonResponse({"ok": False, "error": "Invalid push subscription payload."}, status=400)

    preference_snapshot = _user_preference_snapshot(request.user)
    if preference_snapshot:
        normalized["metadata"] = {
            **normalized["metadata"],
            "user_preferences": preference_snapshot,
        }

    installation_id = normalized["installation_id"]
    endpoint = normalized["endpoint"]

    subscription, created = WebPushDeviceSubscription.objects.get_or_create(
        endpoint=endpoint,
        defaults={
            "user": request.user if request.user.is_authenticated else None,
            **normalized,
        },
    )

    if not created:
        for field, value in normalized.items():
            setattr(subscription, field, value)
        if request.user.is_authenticated:
            subscription.user = request.user

    subscription.is_active = True
    subscription.unsubscribed_at = None
    subscription.last_error = ""
    subscription.last_seen_at = timezone.now()
    subscription.save()

    if installation_id:
        WebPushDeviceSubscription.objects.filter(
            installation_id=installation_id,
            is_active=True,
        ).exclude(endpoint=endpoint).update(
            is_active=False,
            unsubscribed_at=timezone.now(),
            last_error="Replaced by a newer subscription on the same browser installation.",
        )

    return JsonResponse(
        {
            "ok": True,
            "subscription_id": subscription.pk,
            "installation_id": subscription.installation_id,
            "is_new": created,
        }
    )


@require_http_methods(["POST"])
def push_unsubscribe(request):
    payload = _read_json_body(request)
    if payload is None:
        return JsonResponse({"ok": False, "error": "Invalid payload."}, status=400)

    endpoint = (payload.get("endpoint") or "").strip()
    installation_id = (payload.get("installation_id") or "").strip()

    queryset = WebPushDeviceSubscription.objects.filter(is_active=True)
    if endpoint:
        queryset = queryset.filter(endpoint=endpoint)
    elif installation_id:
        queryset = queryset.filter(installation_id=installation_id)
    else:
        return JsonResponse({"ok": False, "error": "No subscription identifier provided."}, status=400)

    if request.user.is_authenticated:
        queryset = queryset.filter(Q(user=request.user) | Q(user__isnull=True))

    updated = queryset.update(
        is_active=False,
        unsubscribed_at=timezone.now(),
        last_error="Unsubscribed from client.",
    )
    return JsonResponse({"ok": True, "updated": updated})


@csrf_exempt
@require_http_methods(["POST"])
def push_delivery_event(request):
    payload = _read_json_body(request)
    if payload is None:
        return JsonResponse({}, status=204)

    event_type = (payload.get("event_type") or "").strip().lower()
    event_token = (payload.get("delivery_token") or "").strip()
    if event_type not in {"displayed", "clicked", "closed"} or not event_token:
        return JsonResponse({}, status=204)

    try:
        delivery = PushNotificationDelivery.objects.select_related("campaign").get(
            event_token=event_token
        )
    except PushNotificationDelivery.DoesNotExist:
        return JsonResponse({}, status=204)

    record_delivery_event(delivery, event_type)
    return JsonResponse({}, status=204)
