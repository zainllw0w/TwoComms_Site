"""
Middleware для синхронизации корзины между устройствами для авторизованных пользователей.

* На входящем запросе подтягивает корзину из БД в сессию (если в сессии пусто или
  если в БД есть свежие данные с другого устройства).
* На исходящем ответе сохраняет содержимое сессии обратно в БД.

Middleware работает только для аутентифицированных пользователей и пропускает
запросы статики/админки/AJAX-эндпоинтов, которые не должны влиять на корзину.
"""

from __future__ import annotations

import logging
from typing import Iterable

from django.utils.deprecation import MiddlewareMixin

from .cart_sync import hydrate_session_from_db, persist_session_to_db

logger = logging.getLogger('storefront.cart.sync')

# Префиксы путей, которые пропускаем, чтобы не дёргать БД на каждый ассет/health-чек.
_SKIP_PATH_PREFIXES: tuple[str, ...] = (
    '/static/',
    '/media/',
    '/favicon',
    '/sw.js',
    '/manifest',
    '/robots.txt',
    '/sitemap',
    '/api/rum',
    '/api/track-event',
    '/health',
)


def _should_skip(path: str) -> bool:
    if not path:
        return False
    return any(path.startswith(prefix) for prefix in _SKIP_PATH_PREFIXES)


class CartSyncMiddleware(MiddlewareMixin):
    """
    Подтягивает (на входе) и сохраняет (на выходе) корзину авторизованного пользователя.
    """

    def process_request(self, request):
        try:
            user = getattr(request, 'user', None)
            if not user or not user.is_authenticated:
                return None
            if _should_skip(request.path):
                return None
            hydrate_session_from_db(request)
        except Exception:
            logger.debug('CartSyncMiddleware.process_request failed', exc_info=True)
        return None

    def process_response(self, request, response):
        try:
            user = getattr(request, 'user', None)
            if not user or not user.is_authenticated:
                return response
            if _should_skip(request.path):
                return response
            # Persist only if the response is successful enough that the cart state
            # is meaningful (4xx/5xx may roll back session changes).
            if 200 <= getattr(response, 'status_code', 500) < 400:
                persist_session_to_db(request)
        except Exception:
            logger.debug('CartSyncMiddleware.process_response failed', exc_info=True)
        return response
