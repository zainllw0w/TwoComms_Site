"""Каркасні views для розділів, що наповнюються у наступних блоках."""
from __future__ import annotations

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
