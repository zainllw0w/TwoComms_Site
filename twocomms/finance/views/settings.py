"""Views для налаштувань користувача та push-повідомлень."""
import json
from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST

from ..models_settings import UserSettings, PushSubscription, NotificationLog
from ..models_txn import Transaction


@require_http_methods(['GET'])
@login_required
def settings_get_api(request):
    """Отримати налаштування користувача."""
    try:
        settings = UserSettings.objects.get(user=request.user)
        return JsonResponse({
            'push_enabled': settings.push_enabled,
            'push_daily_enabled': settings.push_daily_enabled,
            'push_daily_time': settings.push_daily_time.strftime('%H:%M'),
            'push_weekly_enabled': settings.push_weekly_enabled,
            'push_weekly_day': settings.push_weekly_day,
            'telegram_notifications': settings.telegram_notifications,
        })
    except UserSettings.DoesNotExist:
        # Повертаємо дефолтні налаштування
        return JsonResponse({
            'push_enabled': False,
            'push_daily_enabled': False,
            'push_daily_time': '20:00',
            'push_weekly_enabled': False,
            'push_weekly_day': 1,
            'telegram_notifications': False,
        })


@require_POST
@login_required
def settings_save_api(request):
    """Зберегти налаштування користувача."""
    try:
        data = json.loads(request.body)

        settings, created = UserSettings.objects.get_or_create(user=request.user)

        settings.push_enabled = data.get('push_enabled', False)
        settings.push_daily_enabled = data.get('push_daily_enabled', False)
        settings.push_daily_time = data.get('push_daily_time', '20:00')
        settings.push_weekly_enabled = data.get('push_weekly_enabled', False)
        settings.push_weekly_day = int(data.get('push_weekly_day', 1))
        settings.telegram_notifications = data.get('telegram_notifications', False)

        settings.save()

        return JsonResponse({
            'success': True,
            'message': 'Налаштування збережено',
            'created': created
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@require_POST
@login_required
def push_subscribe_api(request):
    """Зберегти push-підписку користувача."""
    try:
        data = json.loads(request.body)
        subscription = data.get('subscription', {})

        if not subscription:
            return JsonResponse({
                'success': False,
                'error': 'No subscription data'
            }, status=400)

        endpoint = subscription.get('endpoint')
        keys = subscription.get('keys', {})
        p256dh = keys.get('p256dh', '')
        auth = keys.get('auth', '')

        if not endpoint or not p256dh or not auth:
            return JsonResponse({
                'success': False,
                'error': 'Invalid subscription data'
            }, status=400)

        # Зберігаємо або оновлюємо підписку
        push_sub, created = PushSubscription.objects.update_or_create(
            user=request.user,
            endpoint=endpoint,
            defaults={
                'p256dh': p256dh,
                'auth': auth,
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500],
                'is_active': True,
            }
        )

        return JsonResponse({
            'success': True,
            'message': 'Push-підписка збережена',
            'created': created
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@require_POST
@login_required
def push_unsubscribe_api(request):
    """Видалити push-підписку користувача."""
    try:
        data = json.loads(request.body)
        endpoint = data.get('endpoint')

        if endpoint:
            PushSubscription.objects.filter(
                user=request.user,
                endpoint=endpoint
            ).delete()
        else:
            # Видаляємо всі підписки користувача
            PushSubscription.objects.filter(user=request.user).delete()

        return JsonResponse({
            'success': True,
            'message': 'Push-підписка видалена'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@require_http_methods(['GET'])
@login_required
def notification_history_api(request):
    """Отримати історію повідомлень користувача."""
    try:
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))

        logs = NotificationLog.objects.filter(
            user=request.user
        ).order_by('-sent_at')[offset:offset + limit]

        return JsonResponse({
            'success': True,
            'notifications': [
                {
                    'id': log.id,
                    'type': log.notification_type,
                    'title': log.title,
                    'body': log.body,
                    'sent_at': log.sent_at.isoformat(),
                    'success': log.success,
                    'error': log.error_message,
                }
                for log in logs
            ],
            'total': NotificationLog.objects.filter(user=request.user).count()
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


def generate_daily_report(user, date=None):
    """Генерувати щоденний звіт для користувача."""
    if date is None:
        date = datetime.now().date()

    # Отримуємо транзакції за день
    transactions = Transaction.objects.filter(
        account__company__users=user,
        date=date,
        status='actual'
    )

    income = sum(
        t.amount for t in transactions
        if t.transaction_type == 'income'
    )
    expense = sum(
        t.amount for t in transactions
        if t.transaction_type == 'expense'
    )
    balance = income - expense

    return {
        'date': date.isoformat(),
        'income': float(income),
        'expense': float(expense),
        'balance': float(balance),
        'transactions_count': transactions.count(),
    }


def generate_weekly_report(user, end_date=None):
    """Генерувати тижневий звіт для користувача."""
    if end_date is None:
        end_date = datetime.now().date()

    start_date = end_date - timedelta(days=7)

    # Отримуємо транзакції за тиждень
    transactions = Transaction.objects.filter(
        account__company__users=user,
        date__gte=start_date,
        date__lte=end_date,
        status='actual'
    )

    income = sum(
        t.amount for t in transactions
        if t.transaction_type == 'income'
    )
    expense = sum(
        t.amount for t in transactions
        if t.transaction_type == 'expense'
    )
    balance = income - expense

    return {
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'income': float(income),
        'expense': float(expense),
        'balance': float(balance),
        'transactions_count': transactions.count(),
    }
