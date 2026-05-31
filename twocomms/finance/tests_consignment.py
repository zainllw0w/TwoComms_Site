"""Тести модуля «Магазини під реалізацію» (consignment)."""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from finance.models import (
    Account, Company, Counterparty, Transaction,
    Reseller, ConsignmentShipment, ConsignmentItem, ResellerPayment, ConsignmentSale,
)


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
