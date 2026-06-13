"""Тести керування плановими платежами: повторення, згортання (без дублів),
погашення з вибором рахунку/контрагента, редагування плану, історія контрагента."""
from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from finance.models import (
    Account, Category, Counterparty, RecurrenceRule, Transaction, get_default_company,
)
from finance.services import obligations as obligations_service
from finance.services import recurring as recurring_service
from finance.services import counterparty as cp_service
from finance.services import transactions as txn_service

User = get_user_model()


class RecurrenceLifecycleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('fin_rec', 'r@x.com', 'x')
        self.company = get_default_company()
        self.acc = Account.objects.create(company=self.company, name='ФОП', currency='UAH',
                                          initial_balance=Decimal('0'), is_business=True)
        self.cat = Category.objects.create(company=self.company, name='Комуналка', type='expense')
        self.cp = Counterparty.objects.create(company=self.company, name='Водоканал', type='supplier')

    def _seed_expense(self, *, status=Transaction.STATUS_PLANNED, date=None):
        return txn_service.create_transaction(
            user=self.user, type=Transaction.TYPE_EXPENSE, amount=Decimal('3000'),
            account=self.acc, currency='UAH', category=self.cat, counterparty=self.cp,
            status=status, date_actual=date or timezone.now(), comment='Комуналка',
        )

    def test_rule_created_and_materialized_indefinite(self):
        """Безстрокове щомісячне правило матеріалізує кілька планових наперед."""
        txn = self._seed_expense()
        rule = recurring_service.create_rule_from_transaction(
            txn, user=self.user, frequency='monthly', end_mode=RecurrenceRule.END_NEVER)
        self.assertTrue(rule.is_active)
        # Початкова транзакція стала першим екземпляром.
        txn.refresh_from_db()
        self.assertEqual(txn.recurrence_rule_id, rule.id)
        self.assertTrue(txn.is_recurring)
        # Матеріалізовано наступні (горизонт 120 дн → щонайменше ще 1).
        total = rule.transactions.count()
        self.assertGreaterEqual(total, 2)

    def test_remaining_count_mode(self):
        """Режим «N разів» рахує, скільки лишилось."""
        txn = self._seed_expense()
        rule = recurring_service.create_rule_from_transaction(
            txn, user=self.user, frequency='monthly',
            end_mode=RecurrenceRule.END_COUNT, count=3)
        # Усього рівно 3 екземпляри (не більше).
        self.assertEqual(rule.transactions.exclude(status=Transaction.STATUS_CANCELLED).count(), 3)
        rem = recurring_service.remaining(rule)
        self.assertEqual(rem['mode'], 'count')
        self.assertEqual(rem['done'], 0)
        self.assertEqual(rem['left'], 3)
        self.assertEqual(rem['left_amount'], Decimal('9000'))

    def test_obligations_collapse_no_duplication(self):
        """Повторюване зобов'язання — ОДИН рядок, а не копія за кожен місяць."""
        txn = self._seed_expense()
        recurring_service.create_rule_from_transaction(
            txn, user=self.user, frequency='monthly', end_mode=RecurrenceRule.END_NEVER)
        # У БД кілька планових, але зобов'язання має бути одне.
        planned_count = Transaction.objects.filter(
            company=self.company, status=Transaction.STATUS_PLANNED,
            type=Transaction.TYPE_EXPENSE).count()
        self.assertGreaterEqual(planned_count, 1)
        data = obligations_service.planned_obligations(self.company)
        self.assertEqual(len(data['expense']), 1)
        oblig = data['expense'][0]
        self.assertEqual(oblig['kind'], 'recurring')
        self.assertEqual(oblig['title'], 'Комуналка')
        self.assertIn('щомісяця', oblig['frequency_label'])
        self.assertEqual(oblig['per_amount'], Decimal('3000'))

    def test_settle_with_account_and_counterparty_advances(self):
        """Погашення проводить платіж на рахунок, фіксує контрагента й підтягує наступний."""
        txn = self._seed_expense()
        rule = recurring_service.create_rule_from_transaction(
            txn, user=self.user, frequency='monthly', end_mode=RecurrenceRule.END_NEVER)
        # Найближчий планований (= перший екземпляр).
        first = rule.transactions.filter(status=Transaction.STATUS_PLANNED).order_by('date_actual').first()
        pay_acc = Account.objects.create(company=self.company, name='Картка', currency='UAH')
        recurring_service.settle_occurrence(
            first, user=self.user, account=pay_acc, counterparty=self.cp, link_account_cp=True)
        first.refresh_from_db()
        self.assertEqual(first.status, Transaction.STATUS_ACTUAL)
        self.assertEqual(first.account_id, pay_acc.id)
        self.assertEqual(first.counterparty_id, self.cp.id)
        # Рахунок прив'язано до контрагента (для історії).
        pay_acc.refresh_from_db()
        self.assertEqual(pay_acc.counterparty_id, self.cp.id)
        # Проведення зменшило фактичний баланс картки.
        self.assertEqual(pay_acc.current_balance, Decimal('-3000'))

    def test_update_plan_changes_future_not_past(self):
        """Зміна суми плану переносить її на майбутні, не чіпаючи проведені."""
        txn = self._seed_expense(status=Transaction.STATUS_ACTUAL,
                                 date=timezone.now() - dt.timedelta(days=2))
        rule = recurring_service.create_rule_from_transaction(
            txn, user=self.user, frequency='monthly', end_mode=RecurrenceRule.END_NEVER)
        recurring_service.update_plan(rule, user=self.user, amount=Decimal('4200'))
        txn.refresh_from_db()
        # Проведена (фактична) лишилась 3000.
        self.assertEqual(txn.amount, Decimal('3000'))
        # Майбутні планові стали 4200.
        future = rule.transactions.filter(status=Transaction.STATUS_PLANNED)
        self.assertTrue(future.exists())
        for f in future:
            self.assertEqual(f.amount, Decimal('4200'))
        rule.refresh_from_db()
        self.assertEqual(rule.template_amount, Decimal('4200'))

    def test_change_frequency_rebuilds_future_no_stale(self):
        """Зміна періодичності перебудовує майбутні екземпляри під новий графік."""
        txn = self._seed_expense(status=Transaction.STATUS_ACTUAL,
                                 date=timezone.now() - dt.timedelta(days=2))
        rule = recurring_service.create_rule_from_transaction(
            txn, user=self.user, frequency='monthly', end_mode=RecurrenceRule.END_NEVER)
        monthly_future = set(rule.transactions
                             .filter(status=Transaction.STATUS_PLANNED)
                             .values_list('id', flat=True))
        self.assertTrue(monthly_future)
        # Перемикаємо на щотижня — старі місячні планові мають зникнути.
        recurring_service.update_plan(rule, user=self.user, frequency='weekly')
        rule.refresh_from_db()
        self.assertEqual(rule.frequency, 'weekly')
        remaining_ids = set(rule.transactions
                            .filter(status=Transaction.STATUS_PLANNED)
                            .values_list('id', flat=True))
        # Жодного «осиротілого» місячного планового не лишилось.
        self.assertFalse(monthly_future & remaining_ids)
        # Новий тижневий графік згенерував більше екземплярів у межах горизонту.
        self.assertGreater(len(remaining_ids), len(monthly_future))
        # Фактична (проведена) не зачеплена.
        txn.refresh_from_db()
        self.assertEqual(txn.status, Transaction.STATUS_ACTUAL)

    def test_estimated_amount_flag_propagates_and_settles_with_actual(self):
        """Орієнтовна сума переноситься на екземпляри; при оплаті вводять фактичну."""
        txn = self._seed_expense()
        rule = recurring_service.create_rule_from_transaction(
            txn, user=self.user, frequency='monthly', end_mode=RecurrenceRule.END_NEVER,
            amount_is_estimated=True)
        self.assertTrue(rule.amount_is_estimated)
        for f in rule.transactions.filter(status=Transaction.STATUS_PLANNED):
            self.assertTrue(f.amount_is_estimated)
        # Погашення з фактичною сумою знімає позначку «орієнтовна».
        nxt = rule.transactions.filter(status=Transaction.STATUS_PLANNED).order_by('date_actual').first()
        recurring_service.settle_occurrence(nxt, user=self.user, account=self.acc,
                                            amount=Decimal('3450'))
        nxt.refresh_from_db()
        self.assertEqual(nxt.amount, Decimal('3450'))
        self.assertFalse(nxt.amount_is_estimated)
        self.assertEqual(nxt.status, Transaction.STATUS_ACTUAL)

    def test_obligation_exposes_schedule_for_edit(self):
        """Згорнуте зобов'язання віддає поточний графік для прелоаду модалки."""
        txn = self._seed_expense()
        recurring_service.create_rule_from_transaction(
            txn, user=self.user, frequency='monthly', interval=2,
            end_mode=RecurrenceRule.END_COUNT, count=6, amount_is_estimated=True)
        data = obligations_service.planned_obligations(self.company)
        g = data['expense'][0]
        self.assertEqual(g['frequency'], 'monthly')
        self.assertEqual(g['interval'], 2)
        self.assertEqual(g['end_mode'], RecurrenceRule.END_COUNT)
        self.assertEqual(g['count'], 6)
        self.assertTrue(g['amount_is_estimated'])
        self.assertEqual(g['repeat_badge'], '×6')


class PlannedTimelineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('fin_tl', 't@x.com', 'x')
        self.company = get_default_company()
        self.acc = Account.objects.create(company=self.company, name='ФОП', currency='UAH',
                                          is_business=True)

    def _planned(self, *, ttype, amount, days):
        return txn_service.create_transaction(
            user=self.user, type=ttype, amount=Decimal(amount), account=self.acc,
            currency='UAH', status=Transaction.STATUS_PLANNED,
            date_actual=timezone.now() + dt.timedelta(days=days), comment=f'{ttype}{days}')

    def test_timeline_segments_overdue_thismonth_future(self):
        """Прострочене → цей місяць → майбутні по місяцях, у хронології."""
        import calendar
        today = timezone.localdate()
        # Прострочене (вчора).
        self._planned(ttype=Transaction.TYPE_EXPENSE, amount='1000', days=-5)
        # Точно цей місяць: завтра, але якщо завтра вже наступний місяць — беремо
        # перший день цього місяця у минулому не можна (overdue), тож сьогодні+0.
        days_left = calendar.monthrange(today.year, today.month)[1] - today.day
        # Платіж за кілька днів, але в межах цього місяця.
        in_month_days = 1 if days_left >= 1 else 0
        self._planned(ttype=Transaction.TYPE_INCOME, amount='500', days=in_month_days)
        # Майбутній місяць (через 40 днів — гарантовано інший місяць).
        self._planned(ttype=Transaction.TYPE_EXPENSE, amount='2000', days=40)

        tl = obligations_service.planned_timeline(self.company)
        keys = [s['key'] for s in tl['segments']]
        self.assertEqual(keys[0], 'overdue')
        self.assertIn('this_month', keys)
        self.assertEqual(tl['overdue_count'], 1)
        # Є хоча б один майбутній місячний сегмент (формат YYYY-MM).
        self.assertTrue(any(k not in ('overdue', 'this_month') for k in keys))

    def test_timeline_sorted_by_date_within_segment(self):
        """Усередині сегмента — за датою (раніше першим)."""
        self._planned(ttype=Transaction.TYPE_EXPENSE, amount='100', days=-2)
        self._planned(ttype=Transaction.TYPE_EXPENSE, amount='200', days=-8)
        tl = obligations_service.planned_timeline(self.company)
        overdue = [s for s in tl['segments'] if s['key'] == 'overdue'][0]
        dates = [g['next_due_iso'] for g in overdue['items']]
        self.assertEqual(dates, sorted(dates))


class CounterpartyHistoryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('fin_cp', 'c@x.com', 'x')
        self.company = get_default_company()
        self.acc = Account.objects.create(company=self.company, name='Банк', currency='UAH')
        self.cp = Counterparty.objects.create(company=self.company, name='ТОВ Ромашка')

    def test_history_aggregates_received_paid_planned(self):
        txn_service.create_transaction(
            user=self.user, type=Transaction.TYPE_INCOME, amount=Decimal('5000'),
            account=self.acc, counterparty=self.cp, date_actual=timezone.now())
        txn_service.create_transaction(
            user=self.user, type=Transaction.TYPE_EXPENSE, amount=Decimal('1200'),
            account=self.acc, counterparty=self.cp, date_actual=timezone.now())
        txn_service.create_transaction(
            user=self.user, type=Transaction.TYPE_INCOME, amount=Decimal('8000'),
            account=self.acc, counterparty=self.cp, status=Transaction.STATUS_PLANNED,
            date_actual=timezone.now() + dt.timedelta(days=10))
        data = cp_service.counterparty_history(self.company, self.cp)
        self.assertEqual(data['counterparty']['name'], 'ТОВ Ромашка')
        self.assertEqual(len(data['transactions']), 3)
        self.assertEqual(len(data['accounts']), 1)
        self.assertIn('5 000', data['totals']['received'])
        self.assertIn('1 200', data['totals']['paid'])
        self.assertIn('8 000', data['totals']['planned_in'])


class RecurrenceApiWiringTests(TestCase):
    FIN_HOST = 'fin.twocomms.shop'

    def setUp(self):
        self.user = User.objects.create_superuser('fin_api', 'a@x.com', 'x')
        self.company = get_default_company()
        self.acc = Account.objects.create(company=self.company, name='ФОП', currency='UAH',
                                          is_business=True)
        self.cat = Category.objects.create(company=self.company, name='Оренда', type='expense')
        self.client.force_login(self.user)

    # У тестовому середовищі DEBUG=False → STORAGES['staticfiles'] вмикає
    # manifest-сховище (потрібен collectstatic). Для рендеру сторінок у тестах
    # підміняємо на просте сховище, а також знімаємо SSL-redirect (інакше 301).
    _TEST_STORAGES = {
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }

    def _post(self, path, payload):
        from django.test import override_settings
        with override_settings(ALLOWED_HOSTS=[self.FIN_HOST, 'testserver'],
                               SECURE_SSL_REDIRECT=False, STORAGES=self._TEST_STORAGES):
            return self.client.post(path, data=json.dumps(payload),
                                    content_type='application/json', HTTP_HOST=self.FIN_HOST)

    def _get(self, path):
        from django.test import override_settings
        with override_settings(ALLOWED_HOSTS=[self.FIN_HOST, 'testserver'],
                               SECURE_SSL_REDIRECT=False, STORAGES=self._TEST_STORAGES):
            return self.client.get(path, HTTP_HOST=self.FIN_HOST)

    def test_create_api_creates_recurrence_rule(self):
        """POST у журнал з recurrence створює правило (раніше поле ігнорувалося)."""
        future = (timezone.now() + dt.timedelta(days=3)).strftime('%Y-%m-%dT%H:%M')
        resp = self._post('/api/transactions/create/', {
            'type': 'expense', 'amount': '15000', 'account': self.acc.id,
            'category': self.cat.id, 'date_actual': future,
            'recurrence': 'monthly', 'recurrence_end_mode': 'never',
            'recurrence_title': 'Оренда офісу',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])
        rule = RecurrenceRule.objects.filter(company=self.company, title='Оренда офісу').first()
        self.assertIsNotNone(rule)
        self.assertEqual(rule.frequency, 'monthly')
        self.assertTrue(rule.transactions.exists())

    def test_update_api_enables_recurrence_on_existing_payment(self):
        """Редагування наявного разового платежу з recurrence створює правило.

        Регресія: «Зробити повторюваним» на існуючому платежі (як Оренда «Влада
        мама») раніше ігнорувалось — update_api не читав recurrence.
        """
        future = timezone.now() + dt.timedelta(days=4)
        txn = txn_service.create_transaction(
            user=self.user, type=Transaction.TYPE_EXPENSE, amount=Decimal('2500'),
            account=self.acc, currency='UAH', category=self.cat,
            status=Transaction.STATUS_PLANNED, date_actual=future, comment='Оренда квартиры')
        self.assertIsNone(txn.recurrence_rule_id)
        resp = self._post(f'/api/transactions/{txn.id}/update/', {
            'type': 'expense', 'amount': '2500', 'account': self.acc.id,
            'category': self.cat.id,
            'date_actual': future.strftime('%Y-%m-%dT%H:%M'),
            'recurrence': 'monthly', 'recurrence_end_mode': 'never',
            'recurrence_title': 'Оренда', 'recurrence_amount_estimated': '1',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])
        txn.refresh_from_db()
        self.assertIsNotNone(txn.recurrence_rule_id)
        rule = txn.recurrence_rule
        self.assertEqual(rule.frequency, 'monthly')
        self.assertTrue(rule.amount_is_estimated)
        # Матеріалізувалися майбутні екземпляри (горизонт 120 дн).
        self.assertGreaterEqual(rule.transactions.count(), 2)

    def test_update_api_changes_existing_rule_schedule(self):
        """Повторне редагування повторюваного платежу оновлює графік правила."""
        future = timezone.now() + dt.timedelta(days=4)
        txn = txn_service.create_transaction(
            user=self.user, type=Transaction.TYPE_EXPENSE, amount=Decimal('2500'),
            account=self.acc, currency='UAH', category=self.cat,
            status=Transaction.STATUS_PLANNED, date_actual=future, comment='Оренда')
        recurring_service.create_rule_from_transaction(
            txn, user=self.user, frequency='monthly', end_mode=RecurrenceRule.END_NEVER)
        txn.refresh_from_db()
        self._post(f'/api/transactions/{txn.id}/update/', {
            'type': 'expense', 'amount': '2700', 'account': self.acc.id,
            'category': self.cat.id,
            'date_actual': future.strftime('%Y-%m-%dT%H:%M'),
            'recurrence': 'monthly', 'recurrence_interval': '2',
            'recurrence_end_mode': 'count', 'recurrence_count': '5',
        })
        rule = RecurrenceRule.objects.get(id=txn.recurrence_rule_id)
        self.assertEqual(rule.interval, 2)
        self.assertEqual(rule.end_mode, RecurrenceRule.END_COUNT)
        self.assertEqual(rule.count, 5)
        # Інваріант стабільності оцінки: редагування графіка (і суми ОКРЕМОГО
        # екземпляра) НЕ змінює плановану суму шаблону. template_amount лишається
        # початковим, доки не передано явний plan_amount.
        self.assertEqual(rule.template_amount, Decimal('2500'))

    def test_editing_occurrence_amount_keeps_template_stable(self):
        """Кейс Віктора: повернення нетипової суми НЕ змінює плановану щомісячну.

        Дебіторка 13000/міс. Один раз повернули 17000 → план на наступні місяці
        має лишитися 13000 (інакше ламається аналітика й «скільки лишилось»).
        """
        future = timezone.now() + dt.timedelta(days=4)
        txn = txn_service.create_transaction(
            user=self.user, type=Transaction.TYPE_INCOME, amount=Decimal('13000'),
            account=self.acc, currency='UAH',
            status=Transaction.STATUS_PLANNED, date_actual=future, comment='Віктор Вікторович')
        recurring_service.create_rule_from_transaction(
            txn, user=self.user, frequency='monthly', end_mode=RecurrenceRule.END_NEVER)
        txn.refresh_from_db()
        # Редагуємо суму саме цього екземпляра на 17000 (без plan_amount).
        resp = self._post(f'/api/transactions/{txn.id}/update/', {
            'type': 'income', 'amount': '17000', 'account': self.acc.id,
            'date_actual': future.strftime('%Y-%m-%dT%H:%M'),
            'recurrence': 'monthly', 'recurrence_end_mode': 'never',
        })
        self.assertEqual(resp.status_code, 200)
        rule = RecurrenceRule.objects.get(id=txn.recurrence_rule_id)
        self.assertEqual(rule.template_amount, Decimal('13000'))
        # Наступні матеріалізовані планові — теж 13000, не 17000.
        future_planned = rule.transactions.filter(
            status=Transaction.STATUS_PLANNED).exclude(id=txn.id)
        for f in future_planned:
            self.assertEqual(f.amount, Decimal('13000'))

    def test_explicit_plan_amount_changes_template(self):
        """Явний plan_amount (модалка «Редагувати план») змінює плановану суму."""
        future = timezone.now() + dt.timedelta(days=4)
        txn = txn_service.create_transaction(
            user=self.user, type=Transaction.TYPE_EXPENSE, amount=Decimal('2500'),
            account=self.acc, currency='UAH', category=self.cat,
            status=Transaction.STATUS_PLANNED, date_actual=future, comment='Оренда')
        recurring_service.create_rule_from_transaction(
            txn, user=self.user, frequency='monthly', end_mode=RecurrenceRule.END_NEVER)
        txn.refresh_from_db()
        self._post(f'/api/transactions/{txn.id}/update/', {
            'type': 'expense', 'amount': '2500', 'account': self.acc.id,
            'category': self.cat.id,
            'date_actual': future.strftime('%Y-%m-%dT%H:%M'),
            'recurrence': 'monthly', 'recurrence_end_mode': 'never',
            'plan_amount': '3200',
        })
        rule = RecurrenceRule.objects.get(id=txn.recurrence_rule_id)
        self.assertEqual(rule.template_amount, Decimal('3200'))

    def test_settle_api_marks_actual_with_account(self):
        txn = txn_service.create_transaction(
            user=self.user, type=Transaction.TYPE_EXPENSE, amount=Decimal('500'),
            account=None, currency='UAH', status=Transaction.STATUS_PLANNED,
            date_actual=timezone.now() + dt.timedelta(days=1))
        resp = self._post(f'/api/transactions/{txn.id}/settle/', {'account_id': self.acc.id})
        self.assertEqual(resp.status_code, 200)
        txn.refresh_from_db()
        self.assertEqual(txn.status, Transaction.STATUS_ACTUAL)
        self.assertEqual(txn.account_id, self.acc.id)

    def test_planned_page_renders(self):
        resp = self._get('/planned/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Планові платежі')

    def test_obligation_settle_context_api(self):
        """Контекст модалки погашення: кандидати, рахунки, оцінка."""
        future = timezone.now() + dt.timedelta(days=2)
        cp = Counterparty.objects.create(company=self.company, name='Влада Мама', type='landlord_personal')
        txn = txn_service.create_transaction(
            user=self.user, type=Transaction.TYPE_EXPENSE, amount=Decimal('2500'),
            account=self.acc, currency='UAH', category=self.cat, counterparty=cp,
            status=Transaction.STATUS_PLANNED, date_actual=future, comment='Комуналка',
            amount_is_estimated=True)
        recurring_service.create_rule_from_transaction(
            txn, user=self.user, frequency='monthly', end_mode=RecurrenceRule.END_NEVER,
            amount_is_estimated=True)
        # Готовий фактичний платіж цьому контрагенту.
        pay = txn_service.create_transaction(
            user=self.user, type=Transaction.TYPE_EXPENSE, amount=Decimal('1724'),
            account=self.acc, currency='UAH', counterparty=cp,
            status=Transaction.STATUS_ACTUAL, date_actual=timezone.now(), comment='Переказ')
        resp = self._get(f'/api/obligations/{txn.id}/settle-context/')
        self.assertEqual(resp.status_code, 200)
        d = resp.json()
        self.assertTrue(d['ok'])
        self.assertTrue(d['estimated'])
        self.assertEqual(d['counterparty']['name'], 'Влада Мама')
        cand_ids = [c['id'] for c in d['candidates']]
        self.assertIn(pay.id, cand_ids)

    def test_obligation_settle_pick_txn_api(self):
        """POST settle pick_txn: привʼязує наявний платіж без подвійного розходу."""
        future = timezone.now() + dt.timedelta(days=2)
        cp = Counterparty.objects.create(company=self.company, name='Влада', type='supplier')
        txn = txn_service.create_transaction(
            user=self.user, type=Transaction.TYPE_EXPENSE, amount=Decimal('2500'),
            account=self.acc, currency='UAH', counterparty=cp,
            status=Transaction.STATUS_PLANNED, date_actual=future, comment='Комуналка',
            amount_is_estimated=True)
        recurring_service.create_rule_from_transaction(
            txn, user=self.user, frequency='monthly', end_mode=RecurrenceRule.END_NEVER,
            amount_is_estimated=True)
        pay = txn_service.create_transaction(
            user=self.user, type=Transaction.TYPE_EXPENSE, amount=Decimal('1724'),
            account=self.acc, currency='UAH', counterparty=cp,
            status=Transaction.STATUS_ACTUAL, date_actual=timezone.now())
        self.acc.refresh_from_db()
        balance = self.acc.current_balance
        resp = self._post(f'/api/obligations/{txn.id}/settle/', {
            'mode': 'pick_txn', 'payment_txn_id': pay.id, 'full_period': '1'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])
        self.acc.refresh_from_db()
        self.assertEqual(self.acc.current_balance, balance)  # без подвійного розходу
        txn.refresh_from_db()
        self.assertEqual(txn.status, Transaction.STATUS_CANCELLED)

    def test_payment_reverse_candidates_api(self):
        """Обернений потік: для платежу повертає зобов'язання того ж контрагента."""
        future = timezone.now() + dt.timedelta(days=2)
        cp = Counterparty.objects.create(company=self.company, name='Орендодавець', type='landlord_personal')
        txn = txn_service.create_transaction(
            user=self.user, type=Transaction.TYPE_EXPENSE, amount=Decimal('2500'),
            account=self.acc, currency='UAH', counterparty=cp,
            status=Transaction.STATUS_PLANNED, date_actual=future, comment='Оренда',
            amount_is_estimated=True)
        recurring_service.create_rule_from_transaction(
            txn, user=self.user, frequency='monthly', end_mode=RecurrenceRule.END_NEVER)
        pay = txn_service.create_transaction(
            user=self.user, type=Transaction.TYPE_EXPENSE, amount=Decimal('2500'),
            account=self.acc, currency='UAH', counterparty=cp,
            status=Transaction.STATUS_ACTUAL, date_actual=timezone.now())
        resp = self._get(f'/api/payments/{pay.id}/reverse-candidates/')
        self.assertEqual(resp.status_code, 200)
        d = resp.json()
        self.assertTrue(d['ok'])
        cp_ids = [o['counterparty_id'] for o in d['obligations']]
        self.assertIn(cp.id, cp_ids)
