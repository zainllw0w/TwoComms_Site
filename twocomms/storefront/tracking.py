from __future__ import annotations
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
from django.db import transaction
from django.conf import settings
import os
from .models import SiteSession, PageView


BOT_SIGNALS = (
    'bot', 'crawl', 'spider', 'slurp', 'bingpreview', 'crawler', 'baiduspider', 'petalbot', 'duckduckbot', 'semrush'
)


def is_bot(ua: str | None) -> bool:
    if not ua:
        return False
    ua_l = ua.lower()
    return any(sig in ua_l for sig in BOT_SIGNALS)


class SimpleAnalyticsMiddleware(MiddlewareMixin):
    """Очень лёгкая мидлварь для учёта сессий и просмотров страниц."""

    def process_request(self, request):
        try:
            # Проверяем, включена ли аналитика
            analytics_enabled = os.environ.get('ENABLE_ANALYTICS', 'true').lower() in ('true', '1', 'yes')
            if not analytics_enabled:
                return
                
            # Не трекаем ботов и служебные пути
            ua = request.META.get('HTTP_USER_AGENT', '')
            path = request.path or ''
            if is_bot(ua) or path.startswith('/admin') or path.startswith('/static') or path.startswith('/media'):
                return

            # Создаем сессию для всех пользователей (включая анонимных)
            if not request.session.session_key:
                request.session.save()
            session_key = request.session.session_key

            ip = request.META.get('REMOTE_ADDR')
            bot = is_bot(ua)

            with transaction.atomic():
                sess, _ = SiteSession.objects.select_for_update().get_or_create(
                    session_key=session_key,
                    defaults={
                        'user': request.user if request.user.is_authenticated else None,
                        'ip_address': ip,
                        'user_agent': ua,
                        'is_bot': bot,
                        'last_path': path,
                        'pageviews': 0,
                    }
                )
                # Обновляем
                sess.last_seen = timezone.now()
                if request.user.is_authenticated and sess.user_id != request.user.id:
                    sess.user = request.user
                sess.last_path = path
                sess.pageviews = (sess.pageviews or 0) + 1
                sess.is_bot = sess.is_bot or bot
                sess.save(update_fields=['user', 'last_seen', 'last_path', 'pageviews', 'is_bot'])

                PageView.objects.create(
                    session=sess,
                    user=request.user if request.user.is_authenticated else None,
                    path=path,
                    referrer=request.META.get('HTTP_REFERER', '')[:512],
                    is_bot=bot,
                )
        except Exception:
            # Никогда не ломаем страницу из-за аналитики
            pass


