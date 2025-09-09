from social_core.pipeline.user import get_username
from social_core.pipeline.social_auth import social_details
from social_core.pipeline.user import create_user
from social_core.pipeline.social_auth import associate_user
from social_core.pipeline.social_auth import load_extra_data
from social_core.pipeline.user import user_details
from social_core.exceptions import AuthException
from django.contrib.auth.models import User
from accounts.models import UserProfile
import logging

logger = logging.getLogger(__name__)

def get_avatar_url(strategy, details, backend, user=None, social=None, *args, **kwargs):
    """Извлекает URL аватарки из Google"""
    logger.info(f"get_avatar_url called for backend: {backend.name}, response: {kwargs.get('response', {})}")
    
    if backend.name == 'google-oauth2':
        response = kwargs.get('response', {})
        avatar_url = response.get('picture')
        if avatar_url:
            kwargs['avatar_url'] = avatar_url
            logger.info(f"Found avatar URL: {avatar_url}")
        else:
            logger.warning("No avatar URL found in Google response")
    return kwargs

def create_or_update_profile(strategy, details, backend, user=None, social=None, *args, **kwargs):
    """Создает или обновляет профиль пользователя с данными из Google"""
    logger.info(f"create_or_update_profile called for user: {user}, details: {details}, kwargs: {kwargs}")
    
    if not user:
        logger.warning("No user provided to create_or_update_profile")
        return
    
    try:
        profile, created = UserProfile.objects.get_or_create(user=user)
        logger.info(f"Profile {'created' if created else 'found'} for user {user.username}")
        
        # Заполняем email если он есть
        if details.get('email'):
            if not profile.email:
                profile.email = details['email']
                logger.info(f"Set email for user {user.username}: {details['email']}")
            else:
                logger.info(f"Email already exists for user {user.username}: {profile.email}")
        
        # Заполняем полное имя если есть
        if details.get('fullname'):
            if not profile.full_name:
                profile.full_name = details['fullname']
                logger.info(f"Set full_name for user {user.username}: {details['fullname']}")
        elif details.get('first_name') and details.get('last_name'):
            full_name = f"{details['first_name']} {details['last_name']}"
            if not profile.full_name:
                profile.full_name = full_name
                logger.info(f"Set full_name from first/last for user {user.username}: {full_name}")
        
        # Сохраняем аватарку
        avatar_url = kwargs.get('avatar_url')
        if avatar_url:
            if not profile.avatar:
                try:
                    import requests
                    from django.core.files.base import ContentFile
                    
                    logger.info(f"Downloading avatar for user {user.username} from: {avatar_url}")
                    # Скачиваем аватарку
                    response = requests.get(avatar_url, timeout=10)
                    if response.status_code == 200:
                        # Создаем имя файла
                        filename = f"avatar_{user.id}_{user.username}.jpg"
                        
                        # Сохраняем файл
                        profile.avatar.save(
                            filename,
                            ContentFile(response.content),
                            save=False  # Не сохраняем сразу, сохраним в конце
                        )
                        logger.info(f"Avatar saved for user {user.username}")
                    else:
                        logger.error(f"Failed to download avatar, status code: {response.status_code}")
                except Exception as e:
                    logger.error(f"Failed to save avatar for user {user.username}: {e}")
            else:
                logger.info(f"Avatar already exists for user {user.username}")
        
        # Сохраняем все изменения
        profile.save()
        logger.info(f"Profile saved for user {user.username} - email: {profile.email}, full_name: {profile.full_name}, avatar: {bool(profile.avatar)}")
        
    except Exception as e:
        logger.error(f"Error creating/updating profile for user {user.username}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

def require_email(strategy, details, backend, user=None, social=None, *args, **kwargs):
    """Требует email для регистрации"""
    if backend.name == 'google-oauth2':
        if not details.get('email'):
            raise AuthException(backend, 'Email is required for registration')
    return kwargs
