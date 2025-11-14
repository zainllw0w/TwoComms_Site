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
        
        # Логируем входящее сообщение для отладки
        if 'message' in update_data:
            message = update_data['message']
            user_id = message.get('from', {}).get('id', 'unknown')
            username = message.get('from', {}).get('username', 'unknown')
            text = message.get('text', '')
            print(f"📥 Webhook received: user_id={user_id}, username={username}, text={text}")
        
        # Обрабатываем обновление
        result = telegram_bot.process_webhook_update(update_data)
        
        if result:
            return JsonResponse({'ok': True, 'result': result})
        else:
            # Не возвращаем ошибку, чтобы Telegram не повторял запрос
            # Просто логируем и возвращаем ok=True
            print(f"⚠️ Webhook processing returned False, but returning ok=True to prevent retries")
            return JsonResponse({'ok': True, 'result': False})
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error in webhook: {e}")
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"❌ Error in telegram_webhook: {e}")
        import traceback
        traceback.print_exc()
        # Возвращаем ok=True чтобы Telegram не повторял запрос при ошибках
        return JsonResponse({'ok': True, 'error': str(e)})


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
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["GET"])
def check_telegram_status(request):
    """Проверяет статус подтверждения Telegram для текущего пользователя"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    try:
        profile = request.user.userprofile
        is_confirmed = bool(profile.telegram_id)
        
        # Логируем проверку статуса для отладки
        
        return JsonResponse({
            'is_confirmed': is_confirmed,
            'telegram_username': profile.telegram or '',
            'telegram_id': profile.telegram_id
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)




@require_http_methods(["POST"])
def unlink_telegram(request):
    """Отвязывает Telegram от профиля пользователя"""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
    
    try:
        profile = request.user.userprofile
        profile.telegram_id = None
        # Оставляем telegram username для повторной привязки
        profile.save()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def get_telegram_id(request):
    """Получает Telegram ID из сообщения бота для отладки"""
    try:
        # Получаем данные от Telegram
        update_data = json.loads(request.body.decode('utf-8'))
        
        if 'message' in update_data:
            message = update_data['message']
            user_id = message['from']['id']
            username = message['from'].get('username', 'unknown')
            first_name = message['from'].get('first_name', '')
            last_name = message['from'].get('last_name', '')
            text = message.get('text', '')
            
            
            return JsonResponse({
                'ok': True,
                'telegram_id': user_id,
                'username': username,
                'first_name': first_name,
                'last_name': last_name,
                'text': text
            })
        
        return JsonResponse({'ok': False, 'error': 'No message in update'})
        
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)})
