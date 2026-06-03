"""Розсилка фінансових push-звітів за розкладом (cron).

Запускати раз на 5–15 хв через cron. Команда сама вирішує, кому що слати:
  • щоденний звіт — якщо ввімкнено і поточний час співпав із push_daily_time;
  • тижневий звіт — якщо ввімкнено, сьогодні push_weekly_day і час push_weekly_time;
  • сповіщення про ризики — якщо ввімкнено і є critical alerts (не частіше 1/день).

Прив'язка до часу — у вікні ±DELTA хвилин, щоб не залежати від точного cron-тіку.
Дедуплікація — через NotificationLog (тип+дата).

Приклад cron (кожні 10 хв):
    */10 * * * * cd /path/twocomms && python manage.py finance_send_reports
"""
from __future__ import annotations

import datetime as dt

from django.core.management.base import BaseCommand
from django.utils import timezone

from finance.models import get_default_company
from finance.models_settings import UserSettings, NotificationLog
from finance.services import push as push_service


WINDOW_MIN = 10  # вікно збігу за часом (хв)


class Command(BaseCommand):
    help = 'Надсилає фінансові push-звіти за розкладом користувачів'

    def add_arguments(self, parser):
        parser.add_argument('--force-daily', action='store_true',
                            help='Примусово надіслати щоденний звіт усім (тест)')
        parser.add_argument('--dry-run', action='store_true',
                            help='Не слати, лише показати що було б надіслано')

    def handle(self, *args, **opts):
        if not push_service.is_configured():
            self.stdout.write(self.style.WARNING('Web Push не налаштований — вихід'))
            return

        company = get_default_company()
        now = timezone.localtime()
        today = now.date()
        force_daily = opts.get('force_daily')
        dry = opts.get('dry_run')

        sent_total = 0
        for st in UserSettings.objects.filter(push_enabled=True).select_related('user'):
            user = st.user
            jobs = []

            # Щоденний.
            if (force_daily or (st.push_daily_enabled and self._time_match(now, st.push_daily_time))):
                if force_daily or not self._already_sent(user, 'daily', today):
                    jobs.append(('daily', push_service.build_daily_report(company)))

            # Тижневий.
            if (st.push_weekly_enabled
                    and self._weekday_match(today, st.push_weekly_day)
                    and self._time_match(now, st.push_weekly_time)
                    and not self._already_sent(user, 'weekly', today)):
                jobs.append(('weekly', push_service.build_weekly_report(company)))

            # Сповіщення про ризики (раз на день максимум).
            if st.push_health_alerts and not self._already_sent(user, 'custom', today, tag='risk'):
                alert = push_service.build_health_alert_report(company)
                if alert:
                    jobs.append(('custom', alert))

            for ntype, report in jobs:
                if report is None:
                    continue
                if dry:
                    self.stdout.write(f'[dry] {user.username}: {ntype} — {report["title"]}')
                    continue
                res = push_service.send_to_user(
                    user, report['title'], report['body'],
                    url='/health/', tag=f'finance-{ntype}',
                    notification_type=ntype, report_data=report.get('data'))
                sent_total += res.get('sent', 0)
                self.stdout.write(f'{user.username}: {ntype} → sent={res.get("sent")} '
                                  f'failed={res.get("failed")}')

        self.stdout.write(self.style.SUCCESS(f'Готово. Надіслано push: {sent_total}'))

    def _time_match(self, now, target_time) -> bool:
        if not target_time:
            return False
        target = now.replace(hour=target_time.hour, minute=target_time.minute,
                             second=0, microsecond=0)
        delta = abs((now - target).total_seconds()) / 60.0
        return delta <= WINDOW_MIN

    def _weekday_match(self, today, weekly_day) -> bool:
        # push_weekly_day: 0=Неділя..6=Субота (як у моделі). Python weekday(): 0=Пн..6=Нд.
        py_wd = today.weekday()  # 0=Mon..6=Sun
        # Мапа моделі → python.
        model_to_py = {0: 6, 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5}
        return model_to_py.get(weekly_day) == py_wd

    def _already_sent(self, user, ntype, day, tag=None) -> bool:
        qs = NotificationLog.objects.filter(
            user=user, notification_type=ntype, sent_at__date=day, success=True)
        return qs.exists()
