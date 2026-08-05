import re
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from orders.models import Order
from orders.nova_poshta_documents import (
    TELEGRAM_CREATE_NP_WAYBILL_ACTION,
    TELEGRAM_DELETE_NP_WAYBILL_ACTION,
)
from warehouse.models import WriteOffRequest


@override_settings(
    NOVA_POSHTA_FALLBACK_ENABLED=False,
    RATELIMIT_ENABLE=False,
    COMPRESS_ENABLED=False,
    COMPRESS_OFFLINE=False,
)
class AdminOrderOperationRedirectTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="order-operations-staff",
            password="pass1234",
            is_staff=True,
        )
        self.order = Order.objects.create(
            user=self.staff,
            order_number="OPS-0001",
            full_name="Операторський клієнт",
            phone="+380991112233",
            city="Київ",
            np_office="Відділення №1",
            status="new",
            payment_status="paid",
        )

    @staticmethod
    def _shipping_fragment(response):
        html = response.content.decode()
        start = html.index('class="oadm-shipping order-delivery')
        return html[start:html.index("<!-- Payment -->", start)]

    def test_anonymous_user_cannot_open_order_operation_redirects(self):
        for route_name in (
            "admin_order_nova_poshta_action",
            "admin_order_warehouse_action",
        ):
            with self.subTest(route_name=route_name):
                response = self.client.get(
                    reverse(route_name, args=[self.order.pk]),
                    secure=True,
                )

                self.assertEqual(response.status_code, 302)
                self.assertIn("/admin/login/", response["Location"])

    @patch(
        "storefront.views.admin_order_actions.build_order_action_url",
        return_value="https://twocomms.shop/orders/telegram-waybill/1/create-np-waybill/?token=create",
    )
    def test_staff_ttn_action_redirects_to_canonical_create_url(self, build_url):
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("admin_order_nova_poshta_action", args=[self.order.pk]),
            secure=True,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://twocomms.shop/orders/telegram-waybill/1/create-np-waybill/?token=create")
        build_url.assert_called_once_with(
            self.order,
            TELEGRAM_CREATE_NP_WAYBILL_ACTION,
            route_name="telegram_order_np_waybill_action",
        )

    @patch(
        "storefront.views.admin_order_actions.build_order_action_url",
        return_value="https://twocomms.shop/orders/telegram-waybill/1/delete-np-waybill/?token=delete",
    )
    def test_staff_ttn_action_redirects_to_canonical_delete_url(self, build_url):
        self.order.nova_poshta_document_ref = "document-ref-1"
        self.order.tracking_number = "20450012345678"
        self.order.save(update_fields=["nova_poshta_document_ref", "tracking_number"])
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("admin_order_nova_poshta_action", args=[self.order.pk]),
            secure=True,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://twocomms.shop/orders/telegram-waybill/1/delete-np-waybill/?token=delete")
        build_url.assert_called_once_with(
            self.order,
            TELEGRAM_DELETE_NP_WAYBILL_ACTION,
            route_name="telegram_order_np_waybill_action",
            token_scope="document-ref-1",
        )

    @patch(
        "storefront.views.admin_order_actions.build_storage_writeoff_url",
        return_value="https://storage.twocomms.shop/order/writeoff-token/write-off/",
    )
    def test_staff_warehouse_action_delegates_to_writeoff_link_builder(self, build_url):
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("admin_order_warehouse_action", args=[self.order.pk]),
            secure=True,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://storage.twocomms.shop/order/writeoff-token/write-off/")
        build_url.assert_called_once_with(self.order)

    def test_staff_warehouse_action_reuses_the_same_pending_request(self):
        self.client.force_login(self.staff)

        first = self.client.get(
            reverse("admin_order_warehouse_action", args=[self.order.pk]),
            secure=True,
        )
        pending = WriteOffRequest.objects.get(
            order=self.order,
            status=WriteOffRequest.STATUS_PENDING,
        )
        second = self.client.get(
            reverse("admin_order_warehouse_action", args=[self.order.pk]),
            secure=True,
        )

        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(
            first["Location"],
            f"https://storage.twocomms.shop/order/{pending.token}/write-off/",
        )
        self.assertEqual(second["Location"], first["Location"])
        self.assertEqual(
            WriteOffRequest.objects.filter(
                order=self.order,
                status=WriteOffRequest.STATUS_PENDING,
            ).count(),
            1,
        )

    @patch(
        "storefront.views.admin_order_actions.build_storage_cancel_sale_url",
        return_value="https://storage.twocomms.shop/order/writeoff-token/cancel-sale/",
    )
    def test_staff_warehouse_action_redirects_to_cancel_sale_after_completion(self, build_url):
        WriteOffRequest.objects.create(
            order=self.order,
            status=WriteOffRequest.STATUS_COMPLETED,
        )
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("admin_order_warehouse_action", args=[self.order.pk]),
            secure=True,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://storage.twocomms.shop/order/writeoff-token/cancel-sale/")
        build_url.assert_called_once_with(self.order)

    def test_order_card_shows_create_ttn_and_writeoff_without_side_effects(self):
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("admin_panel"),
            {"section": "orders"},
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([order.pk for order in response.context["orders"]], [self.order.pk])
        self.assertContains(
            response,
            'class="oadm-action-bar order-cancel-actions"',
            count=1,
        )
        self.assertContains(
            response,
            ".oadm-action-bar { display:flex; align-items:stretch; flex-wrap:wrap;",
        )
        self.assertContains(response, 'data-admin-operation="nova-poshta-create"')
        self.assertContains(response, 'data-admin-operation="warehouse-writeoff"')
        html = response.content.decode()
        action_bar = html[
            html.index('class="oadm-action-bar order-cancel-actions"'):
            html.index("</div>", html.index('class="oadm-action-bar order-cancel-actions"'))
        ]
        self.assertEqual(
            action_bar.count("<button") + action_bar.count('<a class="oadm-operation'),
            4,
        )
        self.assertLess(action_bar.index("data-edit-order"), action_bar.index("oadm-cancel-btn"))
        self.assertLess(
            action_bar.index('data-admin-operation="nova-poshta-create"'),
            action_bar.index('data-admin-operation="warehouse-writeoff"'),
        )
        self.assertNotContains(response, 'class="oadm-operations"')
        shipping = self._shipping_fragment(response)
        self.assertIn('class="delivery-item" data-field="ttn"', shipping)
        self.assertIn('class="ttn-pending">очікується</span>', shipping)
        self.assertNotIn('<span class="k">Доставка</span>', shipping)
        self.assertNotIn('<span class="k">НП</span>', shipping)
        self.assertContains(
            response,
            ".oadm .oadm-shipping .delivery-item { display:flex; flex-direction:row;",
        )
        self.assertContains(
            response,
            "gap:6px 8px; min-width:0; min-height:0; padding:0; border:0;",
        )
        self.assertContains(
            response,
            ".oadm .oadm-shipping .delivery-item:hover::before { content:none; display:none; }",
        )
        self.assertRegex(
            shipping,
            re.compile(
                r'class="delivery-item" data-field="ttn">\s*'
                r'<span class="oadm-shipping__label">ТТН</span>\s*'
                r'<span class="ttn-info">'
            ),
        )
        self.assertRegex(
            shipping,
            re.compile(
                r'class="order-delivery__address"[^>]*>.*?</span>\s*</div>\s*'
                r'<div class="oadm-shipping__tracking">',
                re.DOTALL,
            ),
        )
        self.assertEqual(
            WriteOffRequest.objects.filter(order=self.order).count(),
            0,
        )

    def test_order_card_replaces_create_ttn_with_unlink_for_api_waybill(self):
        self.order.nova_poshta_document_ref = "document-ref-1"
        self.order.tracking_number = "20450012345678"
        self.order.save(update_fields=["nova_poshta_document_ref", "tracking_number"])
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("admin_panel"),
            {"section": "orders"},
            secure=True,
        )

        self.assertContains(response, 'data-admin-operation="nova-poshta-unlink"')
        self.assertNotContains(response, 'data-admin-operation="nova-poshta-create"')
        self.assertContains(response, "20450012345678")
        shipping = self._shipping_fragment(response)
        self.assertIn('class="oadm-badge oadm-badge--web">API</span>', shipping)

    def test_order_card_does_not_offer_api_unlink_for_manual_ttn(self):
        self.order.tracking_number = "20450012345678"
        self.order.save(update_fields=["tracking_number"])
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("admin_panel"),
            {"section": "orders"},
            secure=True,
        )

        self.assertContains(response, "Ручна ТТН")
        self.assertNotContains(response, 'data-admin-operation="nova-poshta-create"')
        self.assertNotContains(response, 'data-admin-operation="nova-poshta-unlink"')
        shipping = self._shipping_fragment(response)
        self.assertIn('class="oadm-badge oadm-badge--manual">Ручна ТТН</span>', shipping)
        html = response.content.decode()
        action_start = html.index('class="oadm-action-bar order-cancel-actions"')
        action_bar = html[action_start:html.index("</div>", action_start)]
        self.assertEqual(
            action_bar.count("<button") + action_bar.count('<a class="oadm-operation'),
            3,
        )
        self.assertContains(
            response,
            ".oadm-action-bar > :is(.oadm-edit-btn, .oadm-cancel-btn, .oadm-operation):nth-child(odd):not(:has(~ :is(.oadm-edit-btn, .oadm-cancel-btn, .oadm-operation))) { grid-column:1 / -1; }",
        )

    def test_order_card_places_shipment_status_below_ttn_in_shipping_component(self):
        self.order.tracking_number = "20450012345678"
        self.order.shipment_status = "Відправлення прямує до міста одержувача"
        self.order.shipment_status_updated = timezone.now()
        self.order.save(
            update_fields=[
                "tracking_number",
                "shipment_status",
                "shipment_status_updated",
            ]
        )
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("admin_panel"),
            {"section": "orders"},
            secure=True,
        )

        shipping = self._shipping_fragment(response)
        self.assertIn('class="oadm-shipping__status oadm-np-status"', shipping)
        self.assertIn('class="oadm-np-status__dot"', shipping)
        self.assertIn(self.order.shipment_status, shipping)
        self.assertLess(
            shipping.index('class="order-delivery__address"'),
            shipping.index('class="delivery-item" data-field="ttn"'),
        )
        self.assertLess(
            shipping.index('class="delivery-item" data-field="ttn"'),
            shipping.index('class="oadm-shipping__status oadm-np-status"'),
        )

    def test_manual_ship_updater_preserves_safe_direct_child_ttn_hook(self):
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("admin_panel"),
            {"section": "orders"},
            secure=True,
        )

        self.assertContains(
            response,
            '.delivery-item[data-field="ttn"] > .ttn-info`);',
            html=False,
        )
        self.assertContains(response, "trackingLink.textContent = normalizedTtn;", html=False)
        self.assertContains(response, "sourceBadge.textContent = 'Ручна ТТН';", html=False)
        self.assertNotContains(response, "ttnElement.innerHTML =", html=False)

    def test_order_card_switches_writeoff_control_to_cancel_after_completion(self):
        WriteOffRequest.objects.create(
            order=self.order,
            status=WriteOffRequest.STATUS_COMPLETED,
        )
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("admin_panel"),
            {"section": "orders"},
            secure=True,
        )

        self.assertContains(response, 'data-admin-operation="warehouse-cancel"')
        self.assertNotContains(response, 'data-admin-operation="warehouse-writeoff"')

    def test_cancelled_order_has_no_operation_controls(self):
        self.order.status = "cancelled"
        self.order.save(update_fields=["status"])
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("admin_panel"),
            {"section": "orders"},
            secure=True,
        )

        self.assertContains(
            response,
            'class="oadm-action-bar order-cancel-actions oadm-action-bar--single"',
            count=1,
        )
        self.assertContains(response, f'data-edit-order="{self.order.pk}"')
        self.assertNotContains(response, 'data-admin-operation="nova-poshta-create"')
        self.assertNotContains(response, 'data-admin-operation="nova-poshta-unlink"')
        self.assertNotContains(response, 'data-admin-operation="warehouse-writeoff"')
        self.assertNotContains(response, 'data-admin-operation="warehouse-cancel"')
