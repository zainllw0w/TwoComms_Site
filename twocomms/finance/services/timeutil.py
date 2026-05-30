"""Хелпери діапазонів дат, що НЕ залежать від таблиць часових поясів MySQL.

Django при ``USE_TZ=True`` компілює лукап ``date_actual__date`` у
``CONVERT_TZ(col, 'UTC', TIME_ZONE)`` на MySQL. На хостингу без завантажених
іменованих tz-таблиць ця функція повертає ``NULL`` — і будь-який фільтр
``date_actual__date__*`` мовчки не знаходить жодного рядка (звідси «0» у
плановій панелі та «немає даних» у Cash Flow / P&L).

Замість лукапу ``__date`` рахуємо межі доби у Python (``zoneinfo`` коректно
враховує перехід на літній час) і фільтруємо за сирим datetime-стовпцем.
"""
from __future__ import annotations

import datetime as dt

from django.utils import timezone


def day_start(d: dt.date):
    """Aware-datetime на 00:00:00 локальної доби ``d``."""
    naive = dt.datetime.combine(d, dt.time.min)
    if timezone.is_naive(naive):
        return timezone.make_aware(naive)
    return naive


def day_end(d: dt.date):
    """Aware-datetime на 23:59:59.999999 локальної доби ``d``."""
    naive = dt.datetime.combine(d, dt.time.max)
    if timezone.is_naive(naive):
        return timezone.make_aware(naive)
    return naive
