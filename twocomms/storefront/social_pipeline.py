from social_core.pipeline.user import get_username
from social_core.pipeline.social_auth import social_details
from social_core.pipeline.user import create_user
from social_core.pipeline.social_auth import associate_user
from social_core.pipeline.social_auth import load_extra_data
from social_core.pipeline.user import user_details
from social_core.exceptions import AuthException
from django.contrib.auth.models import User
from .models import UserProfile
import logging

logger = logging.getLogger(__name__)

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
        if details.get('email') and not profile.email:
            profile.email = details['email']
        
        # Заполняем полное имя если есть
        if details.get('fullname') and not profile.full_name:
            profile.full_name = details['fullname']
        elif details.get('first_name') and details.get('last_name'):
            full_name = f"{details['first_name']} {details['last_name']}"
            if not profile.full_name:
                profile.full_name = full_name
        
        # Сохраняем аватарку
        avatar_url = kwargs.get('avatar_url')
        if avatar_url and not profile.avatar:
            try:
                import requests
                from django.core.files.base import ContentFile
                from django.core.files.storage import default_storage
                
                # Скачиваем аватарку
                response = requests.get(avatar_url, timeout=10)
                if response.status_code == 200:
                    # Создаем имя файла
                    filename = f"avatar_{user.id}_{user.username}.jpg"
                    file_path = f"avatars/{filename}"
                    
                    # Сохраняем файл
                    profile.avatar.save(
                        filename,
                        ContentFile(response.content),
                        save=True
                    )
                    logger.info(f"Avatar saved for user {user.username}")
            except Exception as e:
                logger.error(f"Failed to save avatar for user {user.username}: {e}")
        
        profile.save()
        logger.info(f"Profile {'created' if created else 'updated'} for user {user.username}")
        
    except Exception as e:
        logger.error(f"Error creating/updating profile for user {user.username}: {e}")

def require_email(strategy, details, backend, user=None, social=None, *args, **kwargs):
    """Требует email для регистрации"""
    if backend.name == 'google-oauth2':
        if not details.get('email'):
            raise AuthException(backend, 'Email is required for registration')
    return kwargs
