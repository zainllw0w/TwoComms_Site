from decimal import Decimal

from django.test import TestCase

from fable5.models import ProductInventoryPolicy, VariantBlankLink
from management.models import IgClient, IgCheckoutInventoryReservation
from management.services.ig_checkout import CheckoutConfigurationError, create_or_update_proposal
from orders.models import Order
from productcolors.models import Color, ProductColorVariant
from storefront.models import Category, Product, ProductFitOption, ProductStatus
from warehouse.models import StockItem, StorageCategory, StorageSubcategory, WriteOffRequest
from warehouse.services.inventory import adjust_stock_item, reverse_write_off


class IgInventoryAllocationTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Allocation shirts", slug="allocation-shirts")
        self.product = Product.objects.create(
            title="Allocation shirt",
            slug="allocation-shirt",
            category=category,
            price=Decimal("1090.00"),
            status=ProductStatus.PUBLISHED,
        )
        self.classic = ProductFitOption.objects.create(
            product=self.product,
            code="classic",
            label="Класичний",
            is_active=True,
        )
        self.oversize = ProductFitOption.objects.create(
            product=self.product,
            code="oversize",
            label="Оверсайз",
            is_active=True,
        )
        self.color = Color.objects.create(name="Білий", primary_hex="#FFFFFF")
        self.variant = ProductColorVariant.objects.create(
            product=self.product,
            color=self.color,
            stock=0,
            sku="ALLOC-WHITE",
        )
        ProductInventoryPolicy.objects.create(
            product=self.product,
            source=ProductInventoryPolicy.Source.WAREHOUSE,
        )
        storage_category = StorageCategory.objects.create(
            name="Allocation stock",
            slug="allocation-stock",
            linked_storefront_category=category,
        )
        self.subcategory = StorageSubcategory.objects.create(
            category=storage_category,
            name="Classic blank",
            slug="classic-blank",
        )
        self.stock_item = StockItem.objects.create(
            subcategory=self.subcategory,
            color=self.color,
            size="M",
            quantity=1,
        )
        for fit in ("classic", "oversize"):
            VariantBlankLink.objects.create(
                variant=self.variant,
                option_key=f"fit={fit}",
                storage_subcategory=self.subcategory,
            )
        self.client = IgClient.get_or_create_for_sender("ig-allocation-a")

    def _item(self, *, fit="classic", quantity=1):
        return {
            "product_id": self.product.pk,
            "color_variant_id": self.variant.pk,
            "qty": quantity,
            "size": "M",
            "fit_option_code": fit,
        }

    def test_proposal_creation_reserves_exact_warehouse_stock_item(self):
        proposal = create_or_update_proposal(
            client=self.client,
            pay_type="online_full",
            item_specs=[self._item()],
        )

        reservation = proposal.inventory_reservations.get()
        self.assertEqual(reservation.allocation_source, "warehouse")
        self.assertEqual(reservation.stock_item_id, self.stock_item.pk)
        self.assertEqual(reservation.quantity, 1)
        self.assertEqual(reservation.state, IgCheckoutInventoryReservation.State.ACTIVE)
        self.stock_item.refresh_from_db()
        self.assertEqual(self.stock_item.quantity, 1)

    def test_two_lines_mapped_to_one_stock_item_are_aggregated_before_reserving(self):
        with self.assertRaises(CheckoutConfigurationError) as ctx:
            create_or_update_proposal(
                client=self.client,
                pay_type="online_full",
                item_specs=[self._item(fit="classic"), self._item(fit="oversize")],
            )

        self.assertEqual(ctx.exception.code, "insufficient_stock")
        self.assertFalse(IgCheckoutInventoryReservation.objects.exists())

    def test_second_proposal_cannot_reserve_last_warehouse_unit(self):
        create_or_update_proposal(
            client=self.client,
            pay_type="online_full",
            item_specs=[self._item()],
        )
        other_client = IgClient.get_or_create_for_sender("ig-allocation-b")

        with self.assertRaises(CheckoutConfigurationError) as ctx:
            create_or_update_proposal(
                client=other_client,
                pay_type="online_full",
                item_specs=[self._item()],
            )

        self.assertEqual(ctx.exception.code, "insufficient_stock")
        self.assertEqual(
            IgCheckoutInventoryReservation.objects.filter(
                proposal__client=other_client,
            ).count(),
            0,
        )

    def test_warehouse_payment_commit_keeps_physical_quantity_until_writeoff(self):
        from management.services.ig_inventory import commit_proposal_inventory

        proposal = create_or_update_proposal(
            client=self.client,
            pay_type="online_full",
            item_specs=[self._item()],
        )

        self.assertEqual(commit_proposal_inventory(proposal), 1)
        reservation = proposal.inventory_reservations.get()
        self.assertEqual(
            reservation.state,
            IgCheckoutInventoryReservation.State.PAID_COMMITTED,
        )
        self.stock_item.refresh_from_db()
        self.assertEqual(self.stock_item.quantity, 1)
        self.assertEqual(commit_proposal_inventory(proposal), 0)

    def test_late_payment_after_release_is_reviewed_without_negative_stock(self):
        from management.services.ig_inventory import (
            commit_proposal_inventory,
            release_proposal_inventory,
        )

        proposal = create_or_update_proposal(
            client=self.client,
            pay_type="online_full",
            item_specs=[self._item()],
        )
        self.assertEqual(release_proposal_inventory(proposal, reason="expired"), 1)

        self.assertEqual(commit_proposal_inventory(proposal), 1)
        reservation = proposal.inventory_reservations.get()
        self.assertEqual(
            reservation.state,
            IgCheckoutInventoryReservation.State.OVERBOOKED_REVIEW,
        )
        self.stock_item.refresh_from_db()
        self.assertEqual(self.stock_item.quantity, 1)

    def test_fulfillment_shortfall_marks_review_without_negative_stock(self):
        from management.services.ig_inventory import (
            InventoryReservationError,
            commit_proposal_inventory,
            fulfill_order_inventory_reservations,
        )

        proposal, order = self._paid_proposal_with_order()
        self.stock_item.quantity = 0
        self.stock_item.save(update_fields=["quantity", "updated_at"])

        with self.assertRaises(InventoryReservationError) as ctx:
            fulfill_order_inventory_reservations(order)

        self.assertEqual(ctx.exception.reason, "fulfillment_stock_shortfall")
        reservation = proposal.inventory_reservations.get()
        self.assertEqual(
            reservation.state,
            IgCheckoutInventoryReservation.State.OVERBOOKED_REVIEW,
        )
        self.stock_item.refresh_from_db()
        self.assertEqual(self.stock_item.quantity, 0)

    def _paid_proposal_with_order(self):
        from management.services.ig_inventory import commit_proposal_inventory

        proposal = create_or_update_proposal(
            client=self.client,
            pay_type="online_full",
            item_specs=[self._item()],
        )
        order = Order.objects.create(
            full_name="Instagram buyer",
            phone="+380501112233",
            city="Київ",
            np_office="Відділення 1",
            pay_type="online_full",
            payment_status="paid",
            total_sum=Decimal("1090.00"),
        )
        commit_proposal_inventory(proposal, order=order)
        return proposal, order

    def test_fulfillment_links_one_writeoff_movement_and_marks_reservation_fulfilled(self):
        from management.services.ig_inventory import fulfill_order_inventory_reservations

        proposal, order = self._paid_proposal_with_order()
        writeoff = WriteOffRequest.objects.create(order=order)
        movement = adjust_stock_item(
            stock_item=self.stock_item,
            delta=-1,
            reason="order_write_off",
            order=order,
            write_off_request=writeoff,
        )

        self.assertEqual(
            fulfill_order_inventory_reservations(order, write_off_request=writeoff),
            1,
        )
        reservation = proposal.inventory_reservations.get()
        self.assertEqual(reservation.state, IgCheckoutInventoryReservation.State.FULFILLED)
        self.assertEqual(reservation.stock_movement_id, movement.pk)
        self.assertEqual(reservation.write_off_request_id, writeoff.pk)
        self.assertEqual(
            fulfill_order_inventory_reservations(order, write_off_request=writeoff),
            0,
        )

    def test_reversing_completed_writeoff_reopens_paid_reservation_without_second_movement(self):
        from management.services.ig_inventory import fulfill_order_inventory_reservations

        proposal, order = self._paid_proposal_with_order()
        writeoff = WriteOffRequest.objects.create(
            order=order,
            status=WriteOffRequest.STATUS_COMPLETED,
        )
        adjust_stock_item(
            stock_item=self.stock_item,
            delta=-1,
            reason="order_write_off",
            order=order,
            write_off_request=writeoff,
        )
        fulfill_order_inventory_reservations(order, write_off_request=writeoff)

        reverse_write_off(write_off_request=writeoff)
        reservation = proposal.inventory_reservations.get()
        self.assertEqual(reservation.state, IgCheckoutInventoryReservation.State.PAID_COMMITTED)
        self.assertIsNone(reservation.stock_movement_id)
        self.assertIsNone(reservation.write_off_request_id)
        self.assertEqual(
            fulfill_order_inventory_reservations(order, write_off_request=writeoff),
            0,
        )
