"""Compatibility middleware for retired request-owned Nova Poshta work.

Tracking reconciliation is owned exclusively by ``update_tracking_statuses``
under the guarded production cron. These pass-through classes remain importable
for stale external settings, but they deliberately perform no database or
provider work from the HTTP request path.
"""


class NovaPoshtaFallbackMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)


class NovaPoshtaFallbackSimpleMiddleware(NovaPoshtaFallbackMiddleware):
    pass
