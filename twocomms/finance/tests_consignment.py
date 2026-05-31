"""Тести модуля «Магазини під реалізацію» (consignment)."""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from finance.models import (
    Account, Company, Counterparty, Transaction,
    Reseller, ConsignmentShipment, ConsignmentItem, ResellerPayment, ConsignmentSale,
)
from finance.services import consignment as svc
from finance.services import reports_debt


class ConsignmentModelsTestCase(TestCase):
    """КРОК 1: моделі та property."""

    def setUp(self):
        self.company = Company.objects.create(name='Test Co', base_currency='UAH')
        self.cp = Counterparty.objects.create(company=self.company, name='Військторг', type='client')
        self.reseller = Reseller.objects.create(
            company=self.company, name='Військторг магазин',
            counterparty=self.cp, terms_kind=Reseller.TERMS_INSTALLMENT,
            terms={'period': 'month', 'every': 1, 'amount': '12000.00', 'periods': 6, 'anchor_day': 5},
        )
        self.shipment = ConsignmentShipment.objects.create(
            company=self.company, reseller=self.reseller,
            number='TTN-001', date=timezone.localdate(), debt_amount=Decimal('0'),
        )

    def test_item_frozen_value(self):
        """frozen_value = (qty - sold_qty) * unit_cost, лише консигнаційні."""
        item = ConsignmentItem.objects.create(
            company=self.company, shipment=self.shipment, reseller=self.reseller,
            title='Худі Sphynx', size='M', qty=10, sold_qty=3,
            unit_cost=Decimal('500'), is_consignment=True,
        )
        self.assertEqual(item.frozen_value, Decimal('3500'))  # (10-3)*500
        self.assertEqual(item.remaining_qty, 7)

    def test_item_frozen_zero_when_not_consignment(self):
        """Боргова позиція не заморожує гроші."""
        item = ConsignmentItem.objects.create(
            company=self.company, shipment=self.shipment, reseller=self.reseller,
            title='Футболка', size='L', qty=5, unit_cost=Decimal('300'),
            is_consignment=False,
        )
        self.assertEqual(item.frozen_value, Decimal('0'))
        self.assertEqual(item.line_total, Decimal('1500'))  # 5*300

    def test_item_revenue(self):
        item = ConsignmentItem.objects.create(
            company=self.company, shipment=self.shipment, reseller=self.reseller,
            title='Худі', size='S', qty=10, sold_qty=4,
            unit_cost=Decimal('500'), unit_price=Decimal('900'), is_consignment=True,
        )
        self.assertEqual(item.revenue, Decimal('3600'))  # 4*900

    def test_shipment_total_debt(self):
        """total_debt = debt_amount + сума боргових позицій."""
        self.shipment.debt_amount = Decimal('1000')
        self.shipment.save()
        ConsignmentItem.objects.create(
            company=self.company, shipment=self.shipment, reseller=self.reseller,
            title='Боргова', qty=2, unit_cost=Decimal('250'), is_consignment=False,
        )
        ConsignmentItem.objects.create(
            company=self.company, shipment=self.shipment, reseller=self.reseller,
            title='Консигнація', qty=5, unit_cost=Decimal('500'), is_consignment=True,
        )
        # 1000 (manual) + 500 (2*250 боргова), консигнаційна не рахується в борг
        self.assertEqual(self.shipment.total_debt, Decimal('1500'))

    def test_account_counterparty_field(self):
        """Нове поле Account.counterparty."""
        acc = Account.objects.create(
            company=self.company, name='Картка дівчини', type='card',
            currency='UAH', counterparty=self.cp,
        )
        self.assertEqual(acc.counterparty, self.cp)
        self.assertIn(acc, self.cp.accounts.all())

    def test_transaction_reseller_field(self):
        """Нове поле Transaction.reseller."""
        txn = Transaction.objects.create(
            company=self.company, type=Transaction.TYPE_INCOME,
            status=Transaction.STATUS_PLANNED, amount=Decimal('72000'),
            currency='UAH', date_actual=timezone.now(), reseller=self.reseller,
        )
        self.assertEqual(txn.reseller, self.reseller)
        self.assertIn(txn, self.reseller.transactions.all())


class ConsignmentServiceTestCase(TestCase):
    """КРОК 2: сервіс ядро (умови, поставки, борг, заморожено, статистика)."""

    def setUp(self):
        self.company = Company.objects.create(name='Test Co', base_currency='UAH')
        self.cp = Counterparty.objects.create(company=self.company, name='Військторг', type='client')
        self.reseller = svc.create_reseller(
            user=None, name='Військторг', counterparty=self.cp,
            terms_kind=Reseller.TERMS_INSTALLMENT,
            terms={'period': 'month', 'every': 1, 'amount': '12000', 'periods': 6, 'anchor_day': 5},
        )

    def test_validate_terms(self):
        self.assertEqual(svc.validate_terms('onetime', {'due_days': 14}), {'due_days': 14})
        with self.assertRaises(ValueError):
            svc.validate_terms('onetime', {'due_days': 0})
        with self.assertRaises(ValueError):
            svc.validate_terms('installment', {'period': 'year'})
        out = svc.validate_terms('installment', {'period': 'month', 'amount': '12000', 'periods': 6})
        self.assertEqual(out['amount'], '12000')
        self.assertEqual(out['periods'], 6)

    def test_payment_schedule_installment(self):
        sched = svc.payment_schedule(self.reseller)
        # periods=6 → 6 платежів
        self.assertEqual(len(sched), 6)
        self.assertEqual(sched[0]['amount'], '12000')

    def test_payment_schedule_onetime(self):
        r = svc.create_reseller(user=None, name='Тест', terms_kind='onetime', terms={'due_days': 14})
        sched = svc.payment_schedule(r)
        self.assertEqual(len(sched), 1)
        self.assertEqual(sched[0]['kind'], 'onetime')

    def test_create_shipment_makes_planned_debt(self):
        """Поставка з ручним боргом створює планову income-транзакцію."""
        ship = svc.create_shipment(
            user=None, reseller=self.reseller, date=timezone.localdate(),
            number='TTN-1', debt_amount=Decimal('72000'),
        )
        self.assertIsNotNone(ship.debt_txn)
        self.assertEqual(ship.debt_txn.type, Transaction.TYPE_INCOME)
        self.assertEqual(ship.debt_txn.status, Transaction.STATUS_PLANNED)
        self.assertEqual(ship.debt_txn.amount, Decimal('72000'))
        self.assertEqual(ship.debt_txn.reseller_id, self.reseller.id)
        # Борг магазину = 72000
        self.assertEqual(svc.reseller_debt(self.reseller), Decimal('72000'))

    def test_shipment_debt_from_items(self):
        """Боргові позиції формують борг, консигнаційні — ні."""
        ship = svc.create_shipment(
            user=None, reseller=self.reseller, date=timezone.localdate(),
            items=[
                {'title': 'Футболка', 'qty': 10, 'unit_cost': '300', 'is_consignment': False},
                {'title': 'Худі', 'qty': 5, 'unit_cost': '500', 'is_consignment': True},
            ],
        )
        # борг = 10*300 = 3000 (худі під реалізацію не в борг)
        self.assertEqual(ship.debt_txn.amount, Decimal('3000'))
        # заморожено = 5*500 = 2500
        self.assertEqual(svc.reseller_frozen(self.reseller), Decimal('2500'))
        self.assertEqual(svc.reseller_frozen_qty(self.reseller), 5)

    def test_consignment_in_receivables(self):
        """Борг магазину з'являється в дебіторці з полем reseller."""
        svc.create_shipment(
            user=None, reseller=self.reseller, date=timezone.localdate(),
            debt_amount=Decimal('72000'),
        )
        data = reports_debt.receivables(self.company)
        reseller_rows = [r for r in data['rows'] if r.get('reseller_id') == self.reseller.id]
        self.assertEqual(len(reseller_rows), 1)
        self.assertEqual(reseller_rows[0]['reseller'], 'Військторг')
        self.assertEqual(reseller_rows[0]['amount'], Decimal('72000'))

    def test_shipment_does_not_touch_balance(self):
        """Планова поставка не змінює баланс рахунків."""
        acc = Account.objects.create(company=self.company, name='Каса', type='cash',
                                     currency='UAH', initial_balance=Decimal('5000'))
        acc.recalc_balance(save=True)
        before = acc.current_balance
        svc.create_shipment(user=None, reseller=self.reseller, date=timezone.localdate(),
                            debt_amount=Decimal('72000'))
        acc.refresh_from_db()
        self.assertEqual(acc.current_balance, before)

    def test_frozen_total_and_breakdown(self):
        svc.create_shipment(
            user=None, reseller=self.reseller, date=timezone.localdate(),
            items=[{'title': 'Худі', 'qty': 5, 'unit_cost': '500', 'is_consignment': True}],
        )
        self.assertEqual(svc.consignment_frozen_total(self.company), Decimal('2500'))
        bd = svc.consignment_frozen_breakdown(self.company)
        self.assertEqual(bd['total'], Decimal('2500'))
        self.assertEqual(bd['qty'], 5)
        self.assertEqual(len(bd['by_reseller']), 1)

    def test_delete_reseller_blocked_with_debt(self):
        svc.create_shipment(user=None, reseller=self.reseller, date=timezone.localdate(),
                            debt_amount=Decimal('1000'))
        self.assertFalse(svc.delete_reseller(self.reseller, user=None))
        # force=True видаляє
        self.assertTrue(svc.delete_reseller(self.reseller, user=None, force=True))

    def test_reseller_stats(self):
        svc.create_shipment(
            user=None, reseller=self.reseller, date=timezone.localdate(),
            debt_amount=Decimal('72000'),
            items=[{'title': 'Худі', 'qty': 5, 'unit_cost': '500', 'is_consignment': True}],
        )
        stats = svc.reseller_stats(self.reseller)
        self.assertEqual(stats['debt'], Decimal('72000'))
        self.assertEqual(stats['frozen'], Decimal('2500'))
        self.assertEqual(stats['frozen_qty'], 5)
        self.assertTrue(len(stats['timeline']) >= 1)
