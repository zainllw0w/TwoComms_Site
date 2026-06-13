"""Тести розпізнавання та збереження карток контрагентів (services/cards.py).

Покриває: витяг реквізитів картки з платежу, сильний матч (IBAN/повна маска),
слабкий матч за останніми 4 цифрами (колізії → перепитати, не привʼязувати молча),
дедуп при upsert.
"""
from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .models import (Account, Company, Counterparty, CounterpartyCard,
                     Transaction)
from .services import cards as cards_service


class CardsServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name='T', base_currency='UAH')
        cls.user = get_user_model().objects.create_user('u', password='x')
        cls.acc = Account.objects.create(company=cls.company, name='Mono', currency='UAH')
        cls.vlada = Counterparty.objects.create(company=cls.company, name='Влада Мама',
                                                type='landlord_personal')
        cls.other = Counterparty.objects.create(company=cls.company, name='Інший',
                                                type='supplier')

    def _expense(self, *, comment='', external_data=None, amount='1700'):
        return Transaction.objects.create(
            company=self.company, type=Transaction.TYPE_EXPENSE,
            status=Transaction.STATUS_ACTUAL, amount=Decimal(amount),
            currency='UAH', account=self.acc, date_actual=timezone.now(),
            comment=comment, external_data=external_data or {})

    def test_extract_card_hint_from_comment_mask(self):
        txn = self._expense(comment='Переказ на картку 537541******1234')
        hint = cards_service.extract_card_hint(txn)
        self.assertEqual(hint['last4'], '1234')
        self.assertEqual(hint['pan_mask'], '537541******1234')

    def test_extract_card_hint_from_external_iban(self):
        txn = self._expense(external_data={'counter_iban': 'UA213223130000026007233566001',
                                           'counter_name': 'VLADA M'})
        hint = cards_service.extract_card_hint(txn)
        self.assertEqual(hint['iban'], 'UA213223130000026007233566001')
        self.assertEqual(hint['counter_name'], 'VLADA M')

    def test_strong_match_by_iban(self):
        CounterpartyCard.objects.create(company=self.company, counterparty=self.vlada,
                                        iban='UA213223130000026007233566001', bank='monobank')
        txn = self._expense(external_data={'counter_iban': 'UA213223130000026007233566001'})
        res = cards_service.match_counterparty_by_payment(self.company, txn)
        self.assertIsNotNone(res['strong'])
        self.assertEqual(res['strong'].id, self.vlada.id)

    def test_weak_match_by_last4_returns_candidates_not_strong(self):
        # Дві картки з однаковими останніми 4 у різних контрагентів — колізія.
        CounterpartyCard.objects.create(company=self.company, counterparty=self.vlada,
                                        last4='1234', pan_mask='537541******1234')
        CounterpartyCard.objects.create(company=self.company, counterparty=self.other,
                                        last4='1234', pan_mask='444455******1234')
        txn = self._expense(comment='переказ 0000 0000 0000 1234')
        res = cards_service.match_counterparty_by_payment(self.company, txn)
        self.assertIsNone(res['strong'])
        ids = {c.id for c in res['candidates']}
        self.assertEqual(ids, {self.vlada.id, self.other.id})

    def test_upsert_dedup_by_iban(self):
        c1 = cards_service.upsert_card(self.vlada, iban='UA111', bank='monobank')
        c2 = cards_service.upsert_card(self.vlada, iban='UA111', label='Основна')
        self.assertEqual(c1.id, c2.id)
        self.assertEqual(CounterpartyCard.objects.filter(counterparty=self.vlada).count(), 1)

    def test_upsert_distinct_last4_not_merged(self):
        cards_service.upsert_card(self.vlada, last4='1234', pan_mask='537541******1234')
        cards_service.upsert_card(self.vlada, last4='9999', pan_mask='537541******9999')
        self.assertEqual(CounterpartyCard.objects.filter(counterparty=self.vlada).count(), 2)
