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
            user_id = message['from']['id']
            username = message['from'].get('username', 'unknown')
            text = message.get('text', '')
            print(f"📱 Telegram webhook: user_id={user_id}, username=@{username}, text='{text}'")
        
        # Обрабатываем обновление
        result = telegram_bot.process_webhook_update(update_data)
        
        if result:
            print(f"✅ Telegram webhook: успешно обработано для user_id={user_id}")
        else:
            print(f"⚠️ Telegram webhook: не удалось обработать для user_id={user_id}")
        
        return JsonResponse({'ok': True, 'result': result})
        
    except Exception as e:
        print(f"❌ Ошибка обработки webhook: {e}")
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


@require_http_methods(["GET"])
def check_telegram_status(request):
    """Проверяет статус подтверждения Telegram для текущего пользователя"""
    if not request.user.is_authenticated:
        print(f"❌ Пользователь не авторизован")
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    try:
        profile = request.user.userprofile
        is_confirmed = bool(profile.telegram_id)
        
        # Логируем проверку статуса для отладки
        print(f"🔍 API: user={request.user.username}, confirmed={is_confirmed}, telegram_id={profile.telegram_id}, telegram_username='{profile.telegram}'")
        
        return JsonResponse({
            'is_confirmed': is_confirmed,
            'telegram_username': profile.telegram or '',
            'telegram_id': profile.telegram_id
        })
        
    except Exception as e:
        print(f"❌ Ошибка проверки статуса Telegram: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def debug_user_info(request):
    """Отладочный endpoint для проверки пользователя"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    try:
        profile = request.user.userprofile
        return JsonResponse({
            'username': request.user.username,
            'email': request.user.email,
            'telegram': profile.telegram or '',
            'telegram_id': profile.telegram_id,
            'is_confirmed': bool(profile.telegram_id)
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


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
            
            print(f"📱 Получен Telegram ID: user_id={user_id}, username=@{username}, name={first_name} {last_name}, text='{text}'")
            
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
        print(f"❌ Ошибка получения Telegram ID: {e}")
        return JsonResponse({'ok': False, 'error': str(e)})
