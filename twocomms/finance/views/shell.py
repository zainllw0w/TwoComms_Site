"""Каркасні views для розділів + службові ендпоінти (service worker)."""
from __future__ import annotations

from pathlib import Path

from django.contrib.staticfiles import finders
from django.http import Http404, HttpResponse
from django.shortcuts import render

from ..permissions import finance_access_required

_SECTIONS = {
    'finance_users': ('users', 'Користувачі', 'Доступи, ролі та ефективність використання.'),
}


def _shell(request, url_name):
    tab, title, subtitle = _SECTIONS[url_name]
    return render(request, 'finance/coming_soon.html', {
        'section_title': title, 'section_subtitle': subtitle, 'active_tab': tab,
    })


@finance_access_required
def users(request):
    return _shell(request, 'finance_users')


def finance_service_worker(request):
    """Віддає finance-sw.js із кореня субдомену з заголовком Service-Worker-Allowed.

    Service worker, що лежить у /static/js/, не може мати scope '/'. Тому
    віддаємо його файл із кореневого шляху (/finance-sw.js) і дозволяємо
    кореневий scope явним заголовком — інакше реєстрація SW падає, і PWA
    (offline + push) не працює.
    """
    asset = finders.find('js/finance-sw.js')
    if isinstance(asset, (list, tuple)):
        asset = asset[0] if asset else None
    if not asset:
        raise Http404('finance-sw.js not found')
    content = Path(asset).read_text(encoding='utf-8')
    response = HttpResponse(content, content_type='application/javascript; charset=utf-8')
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache, max-age=0'
    return response
