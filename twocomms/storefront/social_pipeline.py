from social_core.pipeline.user import get_username
from social_core.pipeline.social_auth import social_details
from social_core.pipeline.user import create_user
from social_core.pipeline.social_auth import associate_user
from social_core.pipeline.social_auth import load_extra_data
from social_core.pipeline.user import user_details
from social_core.exceptions import AuthException
from django.contrib.auth.models import User
from accounts.models import UserProfile

def get_avatar_url(strategy, details, backend, user=None, social=None, *args, **kwargs):
    """Извлекает URL аватарки из Google"""
    if backend.name == 'google-oauth2':
        response = kwargs.get('response', {})
        avatar_url = response.get('picture')
        if avatar_url:
            kwargs['avatar_url'] = avatar_url
    return kwargs

def create_or_update_profile(strategy, details, backend, user=None, social=None, *args, **kwargs):
    """Создает или обновляет профиль пользователя с данными из Google"""
    if not user:
        return
    
    try:
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        # Заполняем email если он есть
        if details.get('email'):
            if not profile.email:
                profile.email = details['email']
        
        # Заполняем полное имя если есть
        if details.get('fullname'):
            if not profile.full_name:
                profile.full_name = details['fullname']
        elif details.get('first_name') and details.get('last_name'):
            full_name = f"{details['first_name']} {details['last_name']}"
            if not profile.full_name:
                profile.full_name = full_name
        
        # Сохраняем аватарку (заменяем существующую)
        avatar_url = kwargs.get('avatar_url')
        if avatar_url:
            try:
                import requests
                from django.core.files.base import ContentFile
                
                # Скачиваем аватарку
                response = requests.get(avatar_url, timeout=10)
                if response.status_code == 200:
                    # Удаляем старую аватарку если есть
                    if profile.avatar:
                        try:
                            profile.avatar.delete(save=False)
                        except Exception as e:
                            pass
                    
                    # Создаем имя файла
                    filename = f"avatar_{user.id}_{user.username}.jpg"
                    
                    # Сохраняем новый файл
                    profile.avatar.save(
                        filename,
                        ContentFile(response.content),
                        save=False  # Не сохраняем сразу, сохраним в конце
                    )
            except Exception as e:
                pass
        
        # Сохраняем все изменения
        profile.save()
        
    except Exception as e:
        pass

def require_email(strategy, details, backend, user=None, social=None, *args, **kwargs):
    """Требует email для регистрации"""
    if backend.name == 'google-oauth2':
        if not details.get('email'):
            raise AuthException(backend, 'Email is required for registration')
    return kwargs

def set_auth_redirect(strategy, details, backend, user=None, social=None, *args, **kwargs):
    """
    Добавляет параметр ?auth=success к redirect URL после успешной авторизации.
    Это позволяет JavaScript определить, что авторизация прошла успешно.
    """
    from django.conf import settings
    
    # Получаем redirect URL из настроек
    redirect_url = settings.SOCIAL_AUTH_LOGIN_REDIRECT_URL
    
    # Если пользователь новый, используем специальный URL для настройки профиля
    if user and hasattr(user, 'userprofile'):
        try:
            profile = user.userprofile
            if not profile.phone:
                redirect_url = settings.SOCIAL_AUTH_NEW_USER_REDIRECT_URL
        except:
            redirect_url = settings.SOCIAL_AUTH_NEW_USER_REDIRECT_URL
    else:
        # Если пользователь еще не создан, будет использован NEW_USER_REDIRECT_URL
        try:
            redirect_url = settings.SOCIAL_AUTH_NEW_USER_REDIRECT_URL
        except:
            pass
    
    # Добавляем параметр ?auth=success
    if '?' in redirect_url:
        redirect_url += '&auth=success'
    else:
        redirect_url += '?auth=success'
    
    # Сохраняем в kwargs для использования в redirect
    kwargs['redirect_url'] = redirect_url
    
    return kwargs
