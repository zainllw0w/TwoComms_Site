"""
Views для обработки Telegram webhook
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from .telegram_bot import telegram_bot


@csrf_exempt
@require_http_methods(["POST"])
def telegram_webhook(request):
    """Обрабатывает webhook от Telegram"""
    try:
        # Получаем данные от Telegram
        update_data = json.loads(request.body.decode('utf-8'))
        
        # Обрабатываем обновление
        result = telegram_bot.process_webhook_update(update_data)
        
        return JsonResponse({'ok': True, 'result': result})
        
    except Exception as e:
        print(f"Ошибка обработки webhook: {e}")
        return JsonResponse({'ok': False, 'error': str(e)})


@csrf_exempt
@require_http_methods(["POST"])
def link_telegram_account(request):
    """Связывает Telegram аккаунт с пользователем"""
    try:
        data = json.loads(request.body.decode('utf-8'))
        telegram_id = data.get('telegram_id')
        telegram_username = data.get('telegram_username')
        
        if not telegram_id or not telegram_username:
            return JsonResponse({'success': False, 'error': 'Missing parameters'})
        
        # Связываем аккаунт
        result = telegram_bot.link_user_account(telegram_id, telegram_username)
        
        return JsonResponse({'success': result})
        
    except Exception as e:
        print(f"Ошибка связывания аккаунта: {e}")
        return JsonResponse({'success': False, 'error': str(e)})
