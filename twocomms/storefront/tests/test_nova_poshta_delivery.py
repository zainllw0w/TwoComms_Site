from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from orders.forms import TelegramNovaPoshtaWaybillForm
from orders.nova_poshta_documents import (
    TELEGRAM_CREATE_NP_WAYBILL_ACTION,
    NovaPoshtaDocumentService,
    NovaPoshtaResolvedPoint,
    build_waybill_description,
)
from orders.telegram_notifications import TelegramNotifier
from orders.telegram_status_links import (
    build_order_action_token,
    build_order_action_url,
    verify_order_action_token,
)
from orders.nova_poshta_lookup import (
    NovaPoshtaDirectoryService,
    NovaPoshtaLookupUnavailable,
)
from orders.nova_poshta_checkout import (
    NovaPoshtaSelectionError,
    build_city_choice_token,
    build_warehouse_choice_token,
    resolve_delivery_selection,
)


class NovaPoshtaDirectoryServiceTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @override_settings(
        NOVA_POSHTA_API_KEY='test-key',
        NOVA_POSHTA_API_URL='https://api.novaposhta.ua/v2.0/json/',
    )
    @patch('orders.nova_poshta_lookup.requests.post')
    def test_search_settlements_parses_search_response(self, mock_post):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'success': True,
            'data': [
                {
                    'TotalCount': 1,
                    'Addresses': [
                        {
                            'Present': 'м. Київ, Київ',
                            'MainDescription': 'Київ',
                            'Area': 'Київська',
                            'Region': 'Київ',
                            'SettlementTypeDescription': 'місто',
                            'SettlementRef': 'settlement-ref',
                            'DeliveryCity': 'delivery-city-ref',
                            'Ref': 'legacy-city-ref',
                            'Warehouses': '1473',
                        }
                    ],
                }
            ],
            'errors': [],
            'warnings': [],
        }
        mock_post.return_value = mock_response

        service = NovaPoshtaDirectoryService()
        items = service.search_settlements('Київ', limit=5)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['label'], 'м. Київ, Київ')
        self.assertEqual(items[0]['settlement_ref'], 'settlement-ref')
        self.assertEqual(items[0]['city_ref'], 'delivery-city-ref')
        self.assertEqual(items[0]['warehouses'], 1473)

    @override_settings(NOVA_POSHTA_API_KEY='test-key')
    def test_search_warehouses_uses_full_directory_for_text_query(self):
        service = NovaPoshtaDirectoryService()

        with (
            patch.object(service, '_get_warehouse_type_map', return_value={}),
            patch.object(service, '_request') as mock_request,
        ):
            mock_request.return_value = [
                {
                    'Ref': 'branch-ref',
                    'ShortAddress': 'Київ, вул. Петра Калнишевського, 2',
                    'Description': 'Відділення №7',
                    'CategoryOfWarehouse': 'Branch',
                    'Number': '7',
                },
                {
                    'Ref': 'postomat-ref-id',
                    'ShortAddress': 'Київ, вул. Петра Калнишевського, 2',
                    'Description': 'Пункт видачі',
                    'CategoryOfWarehouse': 'Postomat',
                    'Number': '22',
                },
            ]

            items = service.search_warehouses(
                settlement_ref='settlement-ref',
                city_ref='delivery-city-ref',
                query='Петра',
                kind='postomat',
                limit=20,
            )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['ref'], 'postomat-ref-id')
        self.assertEqual(items[0]['kind'], 'postomat')
        self.assertEqual(
            mock_request.call_args.args,
            ('Address', 'getWarehouses', {'CityRef': 'delivery-city-ref'}),
        )

    @override_settings(NOVA_POSHTA_API_KEY='test-key')
    def test_search_warehouses_ranks_exact_number_first_for_text_query(self):
        service = NovaPoshtaDirectoryService()

        with (
            patch.object(service, '_get_warehouse_type_map', return_value={}),
            patch.object(service, '_request') as mock_request,
        ):
            mock_request.return_value = [
                {
                    'Ref': 'street-match',
                    'ShortAddress': 'Київ, вул. Тестова, 22',
                    'Description': 'Відділення №7',
                    'CategoryOfWarehouse': 'Branch',
                    'Number': '7',
                },
                {
                    'Ref': 'exact-number',
                    'ShortAddress': 'Київ, вул. Інша, 1',
                    'Description': 'Відділення №22',
                    'CategoryOfWarehouse': 'Branch',
                    'Number': '22',
                },
            ]

            items = service.search_warehouses(
                settlement_ref='settlement-ref',
                city_ref='delivery-city-ref',
                query='22',
                kind='branch',
                limit=20,
            )

        self.assertEqual([item['ref'] for item in items[:2]], ['exact-number', 'street-match'])

    @override_settings(NOVA_POSHTA_API_KEY='test-key')
    def test_search_warehouses_uses_fast_postomat_lookup_without_query(self):
        service = NovaPoshtaDirectoryService()

        with (
            patch.object(service, '_get_warehouse_type_map', return_value={'postomat-type': 'Поштомат'}),
            patch.object(service, '_request') as mock_request,
        ):
            mock_request.return_value = [
                {
                    'Ref': 'postomat-ref-id',
                    'ShortAddress': 'Поштомат №22: ТЦ Тест',
                    'Description': 'Поштомат №22',
                    'TypeOfWarehouse': 'postomat-type',
                    'Number': '22',
                }
            ]

            items = service.search_warehouses(
                settlement_ref='settlement-ref',
                city_ref='delivery-city-ref',
                query='',
                kind='postomat',
                limit=20,
            )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['ref'], 'postomat-ref-id')
        self.assertEqual(
            mock_request.call_args.args,
            (
                'Address',
                'getWarehouses',
                {
                    'Page': '1',
                    'FindByString': 'поштомат',
                    'Limit': '50',
                    'CityRef': 'delivery-city-ref',
                },
            ),
        )

    def test_resolve_delivery_selection_accepts_signed_city_and_warehouse(self):
        selection = resolve_delivery_selection(
            {
                'np_city_token': build_city_choice_token(
                    {
                        'label': 'м. Київ, Київ',
                        'settlement_ref': 'settlement-ref',
                        'city_ref': 'delivery-city-ref',
                    }
                ),
                'np_warehouse_token': build_warehouse_choice_token(
                    {
                        'label': 'Відділення №22, Київ, вул. Тестова, 1',
                        'ref': 'warehouse-ref',
                        'kind': 'branch',
                        'city_ref': 'delivery-city-ref',
                    }
                ),
            }
        )

        self.assertEqual(selection.city, 'м. Київ, Київ')
        self.assertEqual(selection.np_office, 'Відділення №22, Київ, вул. Тестова, 1')
        self.assertEqual(selection.city_ref, 'delivery-city-ref')
        self.assertEqual(selection.warehouse_ref, 'warehouse-ref')

    def test_resolve_delivery_selection_rejects_mismatched_city(self):
        with self.assertRaises(NovaPoshtaSelectionError) as exc_info:
            resolve_delivery_selection(
                {
                    'np_city_token': build_city_choice_token(
                        {
                            'label': 'м. Київ, Київ',
                            'settlement_ref': 'settlement-ref',
                            'city_ref': 'delivery-city-ref',
                        }
                    ),
                    'np_warehouse_token': build_warehouse_choice_token(
                        {
                            'label': 'Поштомат №22, Львів',
                            'ref': 'warehouse-ref-2',
                            'kind': 'postomat',
                            'city_ref': 'other-city-ref',
                        }
                    ),
                }
            )

        self.assertEqual(exc_info.exception.field, 'np_office')


@override_settings(NOVA_POSHTA_FALLBACK_ENABLED=False, RATELIMIT_ENABLE=False)
class NovaPoshtaLookupEndpointTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @patch('storefront.views.cart.NovaPoshtaDirectoryService.search_settlements')
    def test_city_lookup_endpoint_returns_items(self, mock_search):
        mock_search.return_value = [
            {
                'label': 'м. Київ, Київ',
                'settlement_ref': 'settlement-ref',
                'city_ref': 'delivery-city-ref',
                'warehouses': 1473,
            }
        ]

        response = self.client.get(reverse('cart_np_city_search'), {'q': 'Київ'}, secure=True)
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            payload,
            {
                'ok': True,
                'items': [
                    {
                        'label': 'м. Київ, Київ',
                        'settlement_ref': 'settlement-ref',
                        'city_ref': 'delivery-city-ref',
                        'warehouses': 1473,
                        'token': payload['items'][0]['token'],
                    }
                ],
            },
        )
        mock_search.assert_called_once_with('Київ', limit=10)

    def test_warehouse_lookup_endpoint_requires_city_reference(self):
        response = self.client.get(reverse('cart_np_warehouse_search'), secure=True)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {
                'ok': False,
                'error': 'Спочатку оберіть місто зі списку Нової пошти.',
            },
        )

    @patch('storefront.views.cart.NovaPoshtaDirectoryService.search_warehouses')
    def test_warehouse_lookup_endpoint_handles_unavailable_service(self, mock_search):
        mock_search.side_effect = NovaPoshtaLookupUnavailable(
            'Довідник Нової пошти тимчасово недоступний. Спробуйте ще раз трохи пізніше.'
        )

        response = self.client.get(
            reverse('cart_np_warehouse_search'),
            {
                'settlement_ref': 'settlement-ref',
                'kind': 'all',
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {
                'ok': False,
                'available': False,
                'error': 'Довідник Нової пошти тимчасово недоступний. Спробуйте ще раз трохи пізніше.',
            },
        )


class _FakeItems:
    def __init__(self, items):
        self._items = list(items)

    def all(self):
        return list(self._items)

    def count(self):
        return len(self._items)


class NovaPoshtaWaybillServiceTests(SimpleTestCase):
    def _build_order(self, **overrides):
        item = SimpleNamespace(title='Худі TwoComms', qty=1)
        payload = {
            'pk': 101,
            'full_name': 'Тестовий клієнт',
            'phone': '+380991112233',
            'city': 'Київ',
            'np_office': 'Відділення №4',
            'np_settlement_ref': 'recipient-settlement-ref',
            'np_city_ref': 'recipient-city-ref',
            'np_warehouse_ref': 'recipient-warehouse-ref',
            'total_sum': '1499.00',
            'pay_type': 'prepay_200',
            'items': _FakeItems([item]),
            'tracking_number': None,
            'nova_poshta_document_ref': None,
            'status': 'new',
        }
        payload.update(overrides)
        total_sum = Decimal(str(payload['total_sum']))
        payload.setdefault('get_remaining_amount', lambda total=total_sum: total - Decimal('200.00'))
        return SimpleNamespace(**payload)

    def test_build_waybill_description_uses_single_item_title(self):
        order = self._build_order()
        self.assertEqual(build_waybill_description(order), 'Одяг бренду TwoComms, Худі TwoComms')

    def test_build_waybill_description_uses_quantity_for_multiple_items(self):
        items = _FakeItems([
            SimpleNamespace(title='Футболка', qty=2),
            SimpleNamespace(title='Худі', qty=1),
        ])
        order = self._build_order(items=items)
        self.assertEqual(build_waybill_description(order), 'Одяг бренду TwoComms, у кількості 3 шт.')

    @patch.object(NovaPoshtaDocumentService, '_resolve_default_sender_point')
    def test_build_initial_payload_prefills_sender_and_prepay_cod(self, mock_sender_point):
        mock_sender_point.return_value = NovaPoshtaResolvedPoint(
            city_label='м. Харків, Харків',
            warehouse_label='Відділення №138 (до 200 кг): Проїзд Стадіонний, 13',
            settlement_ref='sender-settlement-ref',
            city_ref='sender-city-ref',
            warehouse_ref='sender-warehouse-ref',
            warehouse_kind='branch',
        )
        order = self._build_order()
        service = NovaPoshtaDocumentService()

        payload = service.build_initial_payload(order)

        self.assertEqual(payload['recipient_full_name'], 'Тестовий клієнт')
        self.assertEqual(payload['recipient_city_ref'], 'recipient-city-ref')
        self.assertEqual(payload['sender_city_ref'], 'sender-city-ref')
        self.assertEqual(payload['sender_warehouse_ref'], 'sender-warehouse-ref')
        self.assertEqual(payload['description'], 'Одяг бренду TwoComms, Худі TwoComms')
        self.assertEqual(payload['cod_amount'], '1299.00')
        self.assertEqual(payload['payer_type'], 'Recipient')
        self.assertEqual(payload['payment_method'], 'Cash')

    @patch.object(NovaPoshtaDocumentService, '_resolve_default_sender_point')
    def test_build_initial_payload_sets_full_cod_for_cod_orders(self, mock_sender_point):
        mock_sender_point.return_value = NovaPoshtaResolvedPoint(
            city_label='м. Харків, Харків',
            warehouse_label='Відділення №138',
            settlement_ref='sender-settlement-ref',
            city_ref='sender-city-ref',
            warehouse_ref='sender-warehouse-ref',
            warehouse_kind='branch',
        )
        order = self._build_order(pay_type='cod', total_sum='990.00')
        service = NovaPoshtaDocumentService()

        payload = service.build_initial_payload(order)

        self.assertEqual(payload['cod_amount'], '990.00')


class NovaPoshtaWaybillFormTests(SimpleTestCase):
    def test_form_normalizes_recipient_phone(self):
        form = TelegramNovaPoshtaWaybillForm(
            data={
                'recipient_full_name': 'Тест Клієнт',
                'recipient_phone': '+38 (099) 111-22-33',
                'recipient_city': 'Київ',
                'recipient_settlement_ref': '',
                'recipient_city_ref': '',
                'recipient_warehouse': 'Відділення №4',
                'recipient_warehouse_ref': '',
                'sender_city': 'Харків',
                'sender_settlement_ref': '',
                'sender_city_ref': '',
                'sender_warehouse': 'Відділення №138',
                'sender_warehouse_ref': '',
                'description': 'Одяг бренду TwoComms',
                'declared_cost': '1499',
                'weight': '1',
                'seats_amount': '1',
                'length_cm': '30',
                'width_cm': '20',
                'height_cm': '8',
                'cod_amount': '',
                'payer_type': 'Recipient',
                'payment_method': 'Cash',
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['recipient_phone'], '380991112233')
        self.assertEqual(form.cleaned_data['cod_amount'], 0)


@override_settings(ROOT_URLCONF='storefront.urls', SITE_BASE_URL='https://twocomms.shop')
class TelegramOrderActionLinkTests(SimpleTestCase):
    def test_generic_action_token_roundtrip(self):
        token = build_order_action_token(77, TELEGRAM_CREATE_NP_WAYBILL_ACTION)
        self.assertTrue(
            verify_order_action_token(
                token,
                order_id=77,
                action=TELEGRAM_CREATE_NP_WAYBILL_ACTION,
            )
        )
        self.assertFalse(
            verify_order_action_token(
                token,
                order_id=77,
                action='ship',
            )
        )

    def test_build_waybill_action_url_uses_new_route(self):
        order = SimpleNamespace(pk=33)
        url = build_order_action_url(
            order,
            TELEGRAM_CREATE_NP_WAYBILL_ACTION,
            route_name='telegram_order_np_waybill_action',
        )

        self.assertIn('/orders/telegram-waybill/33/create-np-waybill/', url)
        self.assertIn('token=', url)

    @patch('orders.telegram_notifications.build_order_status_action_url', return_value='https://example.com/ship')
    @patch('orders.telegram_notifications.build_order_action_url', return_value='https://example.com/create')
    def test_order_notification_markup_contains_create_waybill_and_ship_buttons(self, *_mocks):
        order = SimpleNamespace(
            pk=1,
            status='new',
            tracking_number='',
            nova_poshta_document_ref='',
        )
        notifier = TelegramNotifier(bot_token='token', admin_id='1', async_enabled=False)

        markup = notifier._build_order_management_reply_markup(order)

        self.assertEqual(markup['inline_keyboard'][0][0]['text'], '📦 Створити ТТН НП')
        self.assertEqual(markup['inline_keyboard'][0][0]['url'], 'https://example.com/create')
        self.assertEqual(markup['inline_keyboard'][1][0]['text'], '🚚 Відправлено + ТТН')
        self.assertEqual(markup['inline_keyboard'][1][0]['url'], 'https://example.com/ship')
