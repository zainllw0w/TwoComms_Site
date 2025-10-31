"""
Middleware для обработки OAuth авторизации.
"""


class OAuthAuthSuccessMiddleware:
    """
    Middleware для добавления параметра ?auth=success к redirect URL после успешной OAuth авторизации.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Проверяем, был ли это OAuth callback
        if request.path.startswith('/oauth/complete/') or request.path.startswith('/social/complete/'):
            # Проверяем, авторизован ли пользователь
            if request.user.is_authenticated:
                # Если response - это redirect, добавляем параметр
                from django.http import HttpResponseRedirect, HttpResponsePermanentRedirect
                if isinstance(response, (HttpResponseRedirect, HttpResponsePermanentRedirect)):
                    redirect_url = response.url
                    if redirect_url:
                        # Добавляем параметр ?auth=success к redirect URL
                        if '?' in redirect_url:
                            redirect_url += '&auth=success'
                        else:
                            redirect_url += '?auth=success'
                        # Создаем новый redirect с параметром
                        if isinstance(response, HttpResponsePermanentRedirect):
                            return HttpResponsePermanentRedirect(redirect_url)
                        else:
                            return HttpResponseRedirect(redirect_url)
        
        return response

