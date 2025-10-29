"""
API views для AJAX авторизации в дропшипе
"""
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
import json


@require_http_methods(["POST"])
@ensure_csrf_cookie
def ajax_login(request):
    """AJAX вход для дропшипа"""
    try:
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        if not username or not password:
            return JsonResponse({
                'success': False,
                'error': 'Будь ласка, заповніть всі поля'
            })
        
        # Попытка аутентификации
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if user.is_active:
                login(request, user)
                return JsonResponse({
                    'success': True,
                    'message': 'Успішний вхід!',
                    'redirect': request.POST.get('next', '/orders/dropshipper/')
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Ваш акаунт деактивовано'
                })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Невірний логін або пароль'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'Помилка сервера. Спробуйте пізніше.'
        })


@require_http_methods(["POST"])
@ensure_csrf_cookie
def ajax_register(request):
    """AJAX регистрация для дропшипа"""
    try:
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        
        errors = {}
        
        # Валидация username
        if not username:
            errors['username'] = ['Логін обов\'язковий']
        elif len(username) < 3:
            errors['username'] = ['Логін має бути мінімум 3 символи']
        elif User.objects.filter(username=username).exists():
            errors['username'] = ['Цей логін вже зайнятий']
        elif not username.replace('_', '').isalnum():
            errors['username'] = ['Логін може містити тільки літери, цифри та підкреслення']
        
        # Валидация email
        if not email:
            errors['email'] = ['Email обов\'язковий']
        elif User.objects.filter(email=email).exists():
            errors['email'] = ['Цей email вже зареєстрований']
        
        # Валидация пароля
        if not password1:
            errors['password1'] = ['Пароль обов\'язковий']
        elif password1 != password2:
            errors['password2'] = ['Паролі не співпадають']
        else:
            # Проверка сложности пароля
            try:
                validate_password(password1)
            except ValidationError as e:
                errors['password1'] = list(e.messages)
        
        if errors:
            return JsonResponse({
                'success': False,
                'errors': errors
            })
        
        # Создание пользователя
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password1
        )
        
        # Автоматический вход после регистрации
        login(request, user)
        
        return JsonResponse({
            'success': True,
            'message': 'Реєстрація успішна!',
            'redirect': request.POST.get('next', '/orders/dropshipper/')
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'Помилка сервера. Спробуйте пізніше.'
        })

