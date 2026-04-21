from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from orders.nova_poshta_lookup import (
    NovaPoshtaDirectoryService,
    NovaPoshtaLookupUnavailable,
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


@override_settings(NOVA_POSHTA_FALLBACK_ENABLED=False)
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

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                'ok': True,
                'items': [
                    {
                        'label': 'м. Київ, Київ',
                        'settlement_ref': 'settlement-ref',
                        'city_ref': 'delivery-city-ref',
                        'warehouses': 1473,
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
            'Пошук Нової пошти тимчасово недоступний. Можна ввести дані вручну.'
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
                'error': 'Пошук Нової пошти тимчасово недоступний. Можна ввести дані вручну.',
            },
        )
