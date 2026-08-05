from datetime import timedelta
from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

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

    def test_proposal_without_inventory_policy_keeps_legacy_untracked_checkout(self):
        ProductInventoryPolicy.objects.filter(product=self.product).delete()

        proposal = create_or_update_proposal(
            client=self.client,
            pay_type="online_full",
            item_specs=[self._item()],
        )

        self.assertEqual(proposal.items.count(), 1)
        self.assertFalse(IgCheckoutInventoryReservation.objects.exists())

    def test_revision_releases_old_reservation_before_replacing_protected_item(self):
        first = create_or_update_proposal(
            client=self.client,
            pay_type="online_full",
            item_specs=[self._item()],
        )
        old_reservation = first.inventory_reservations.get()

        second = create_or_update_proposal(
            client=self.client,
            pay_type="online_full",
            item_specs=[self._item(fit="oversize")],
        )

        self.assertEqual(second.pk, first.pk)
        old_reservation.refresh_from_db()
        self.assertEqual(old_reservation.state, IgCheckoutInventoryReservation.State.RELEASED)
        self.assertIsNone(old_reservation.item_id)
        self.assertEqual(second.inventory_reservations.filter(state="active").count(), 1)

    def test_two_lines_mapped_to_one_stock_item_are_aggregated_before_reserving(self):
        with self.assertRaises(CheckoutConfigurationError) as ctx:
            create_or_update_proposal(
                client=self.client,
                pay_type="online_full",
                item_specs=[self._item(fit="classic"), self._item(fit="oversize")],
            )

        self.assertEqual(ctx.exception.code, "insufficient_stock")
        self.assertEqual(ctx.exception.reason, "insufficient_reserved_stock")
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
        self.assertEqual(ctx.exception.reason, "insufficient_reserved_stock")
        self.assertEqual(
            IgCheckoutInventoryReservation.objects.filter(
                proposal__client=other_client,
            ).count(),
            0,
        )

    def test_expired_paid_commitment_still_blocks_last_warehouse_unit(self):
        from management.services.ig_inventory import commit_proposal_inventory

        proposal = create_or_update_proposal(
            client=self.client,
            pay_type="online_full",
            item_specs=[self._item()],
        )
        commit_proposal_inventory(proposal)
        proposal.inventory_reservations.update(
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        other_client = IgClient.get_or_create_for_sender("ig-allocation-paid-expired")

        with self.assertRaises(CheckoutConfigurationError) as ctx:
            create_or_update_proposal(
                client=other_client,
                pay_type="online_full",
                item_specs=[self._item()],
            )

        self.assertEqual(ctx.exception.code, "insufficient_stock")
        self.assertEqual(ctx.exception.reason, "insufficient_reserved_stock")

    def test_manual_writeoff_cannot_consume_active_and_paid_commitments(self):
        from management.services.ig_inventory import commit_proposal_inventory

        self.stock_item.quantity = 3
        self.stock_item.save(update_fields=["quantity", "updated_at"])
        paid = create_or_update_proposal(
            client=self.client,
            pay_type="online_full",
            item_specs=[self._item()],
        )
        commit_proposal_inventory(paid)
        active_client = IgClient.get_or_create_for_sender("ig-allocation-active-protected")
        create_or_update_proposal(
            client=active_client,
            pay_type="online_full",
            item_specs=[self._item()],
        )

        with self.assertRaises(ValueError):
            adjust_stock_item(stock_item=self.stock_item, delta=-2)

        self.stock_item.refresh_from_db()
        self.assertEqual(self.stock_item.quantity, 3)

    def test_matching_order_writeoff_can_consume_own_paid_commitment(self):
        _proposal, order = self._paid_proposal_with_order()

        movement = adjust_stock_item(
            stock_item=self.stock_item,
            delta=-1,
            reason="order_write_off",
            order=order,
        )

        self.stock_item.refresh_from_db()
        self.assertEqual(self.stock_item.quantity, 0)
        self.assertEqual(movement.quantity_after, 0)

    def test_matching_order_writeoff_cannot_consume_other_paid_commitment(self):
        from management.services.ig_inventory import commit_proposal_inventory

        self.stock_item.quantity = 2
        self.stock_item.save(update_fields=["quantity", "updated_at"])
        _first_proposal, first_order = self._paid_proposal_with_order()
        other_client = IgClient.get_or_create_for_sender("ig-allocation-other-paid")
        other_proposal = create_or_update_proposal(
            client=other_client,
            pay_type="online_full",
            item_specs=[self._item()],
        )
        other_order = Order.objects.create(
            full_name="Other Instagram buyer",
            phone="+380501112244",
            city="Київ",
            np_office="Відділення 2",
            pay_type="online_full",
            payment_status="paid",
            total_sum=Decimal("1090.00"),
        )
        commit_proposal_inventory(other_proposal, order=other_order)

        with self.assertRaises(ValueError):
            adjust_stock_item(
                stock_item=self.stock_item,
                delta=-2,
                reason="order_write_off",
                order=first_order,
            )

        self.stock_item.refresh_from_db()
        self.assertEqual(self.stock_item.quantity, 2)

    def test_expired_unpaid_active_reservation_does_not_block_new_proposal(self):
        proposal = create_or_update_proposal(
            client=self.client,
            pay_type="online_full",
            item_specs=[self._item()],
        )
        proposal.inventory_reservations.update(
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        other_client = IgClient.get_or_create_for_sender("ig-allocation-expired-active")

        other_proposal = create_or_update_proposal(
            client=other_client,
            pay_type="online_full",
            item_specs=[self._item()],
        )

        self.assertEqual(
            other_proposal.inventory_reservations.filter(
                state=IgCheckoutInventoryReservation.State.ACTIVE,
            ).count(),
            1,
        )

    def test_payment_after_active_reservation_expiry_requires_review(self):
        from management.services.ig_inventory import (
            mark_overbooked_proposal_inventory,
        )

        proposal = create_or_update_proposal(
            client=self.client,
            pay_type="online_full",
            item_specs=[self._item()],
        )
        paid_at = timezone.now()
        proposal.inventory_reservations.update(
            expires_at=paid_at - timedelta(seconds=1),
        )

        self.assertEqual(
            mark_overbooked_proposal_inventory(
                proposal,
                paid_at=paid_at,
            ),
            1,
        )
        reservation = proposal.inventory_reservations.get()
        self.assertEqual(
            reservation.state,
            IgCheckoutInventoryReservation.State.OVERBOOKED_REVIEW,
        )

    def test_timely_provider_payment_is_reviewed_when_stock_was_reallocated(self):
        from management.services.ig_inventory import (
            mark_overbooked_proposal_inventory,
        )

        proposal = create_or_update_proposal(
            client=self.client,
            pay_type="online_full",
            item_specs=[self._item()],
        )
        expires_at = timezone.now() - timedelta(minutes=1)
        proposal.inventory_reservations.update(expires_at=expires_at)
        other_client = IgClient.get_or_create_for_sender(
            "ig-allocation-reallocated-before-callback"
        )
        create_or_update_proposal(
            client=other_client,
            pay_type="online_full",
            item_specs=[self._item()],
        )

        self.assertEqual(
            mark_overbooked_proposal_inventory(
                proposal,
                paid_at=expires_at - timedelta(seconds=1),
            ),
            1,
        )
        reservation = proposal.inventory_reservations.get()
        self.assertEqual(
            reservation.state,
            IgCheckoutInventoryReservation.State.OVERBOOKED_REVIEW,
        )

    def test_timely_catalog_payment_is_reviewed_when_stock_was_reallocated(self):
        from management.services.ig_inventory import (
            mark_overbooked_proposal_inventory,
        )

        policy = ProductInventoryPolicy.objects.get(product=self.product)
        policy.source = ProductInventoryPolicy.Source.CATALOG_VARIANT
        policy.save(update_fields=["source", "updated_at"])
        self.variant.stock = 1
        self.variant.save(update_fields=["stock"])
        proposal = create_or_update_proposal(
            client=self.client,
            pay_type="online_full",
            item_specs=[self._item()],
        )
        expires_at = timezone.now() - timedelta(minutes=1)
        proposal.inventory_reservations.update(expires_at=expires_at)
        other_client = IgClient.get_or_create_for_sender(
            "ig-catalog-reallocated-before-callback"
        )
        create_or_update_proposal(
            client=other_client,
            pay_type="online_full",
            item_specs=[self._item()],
        )

        self.assertEqual(
            mark_overbooked_proposal_inventory(
                proposal,
                paid_at=expires_at - timedelta(seconds=1),
            ),
            1,
        )
        reservation = proposal.inventory_reservations.get()
        self.assertEqual(
            reservation.state,
            IgCheckoutInventoryReservation.State.OVERBOOKED_REVIEW,
        )

    def test_catalog_commit_does_not_consume_stock_reallocated_after_expiry(self):
        from management.services.ig_inventory import commit_proposal_inventory

        policy = ProductInventoryPolicy.objects.get(product=self.product)
        policy.source = ProductInventoryPolicy.Source.CATALOG_VARIANT
        policy.save(update_fields=["source", "updated_at"])
        self.variant.stock = 1
        self.variant.save(update_fields=["stock"])
        proposal = create_or_update_proposal(
            client=self.client,
            pay_type="online_full",
            item_specs=[self._item()],
        )
        expires_at = timezone.now() - timedelta(minutes=1)
        proposal.inventory_reservations.update(expires_at=expires_at)
        other_client = IgClient.get_or_create_for_sender(
            "ig-catalog-commit-reallocated-before-callback"
        )
        create_or_update_proposal(
            client=other_client,
            pay_type="online_full",
            item_specs=[self._item()],
        )

        self.assertEqual(
            commit_proposal_inventory(
                proposal,
                paid_at=expires_at - timedelta(seconds=1),
            ),
            1,
        )
        reservation = proposal.inventory_reservations.get()
        self.assertEqual(
            reservation.state,
            IgCheckoutInventoryReservation.State.OVERBOOKED_REVIEW,
        )
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 1)

    def test_timely_provider_payment_can_commit_after_callback_delay(self):
        from management.services.ig_inventory import (
            commit_proposal_inventory,
            mark_overbooked_proposal_inventory,
        )

        proposal = create_or_update_proposal(
            client=self.client,
            pay_type="online_full",
            item_specs=[self._item()],
        )
        expires_at = timezone.now() - timedelta(minutes=1)
        proposal.inventory_reservations.update(expires_at=expires_at)
        paid_at = expires_at - timedelta(seconds=1)

        self.assertEqual(
            mark_overbooked_proposal_inventory(proposal, paid_at=paid_at),
            0,
        )
        self.assertEqual(
            commit_proposal_inventory(proposal, paid_at=paid_at),
            1,
        )
        reservation = proposal.inventory_reservations.get()
        self.assertEqual(
            reservation.state,
            IgCheckoutInventoryReservation.State.PAID_COMMITTED,
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
            mark_overbooked_proposal_inventory,
            release_proposal_inventory,
        )

        proposal = create_or_update_proposal(
            client=self.client,
            pay_type="online_full",
            item_specs=[self._item()],
        )
        self.assertEqual(release_proposal_inventory(proposal, reason="expired"), 1)

        self.assertEqual(commit_proposal_inventory(proposal), 1)
        self.assertEqual(mark_overbooked_proposal_inventory(proposal), 1)
        reservation = proposal.inventory_reservations.get()
        self.assertEqual(
            reservation.state,
            IgCheckoutInventoryReservation.State.OVERBOOKED_REVIEW,
        )
        self.stock_item.refresh_from_db()
        self.assertEqual(self.stock_item.quantity, 1)

    def test_late_payment_review_creates_one_manager_task(self):
        from management.services.ig_inventory import (
            mark_overbooked_proposal_inventory,
            release_proposal_inventory,
        )
        from management.models import IgFollowUpTask

        proposal = create_or_update_proposal(
            client=self.client,
            pay_type="online_full",
            item_specs=[self._item()],
        )
        release_proposal_inventory(proposal, reason="expired")

        self.assertEqual(mark_overbooked_proposal_inventory(proposal), 1)
        self.assertEqual(mark_overbooked_proposal_inventory(proposal), 1)
        reservation = proposal.inventory_reservations.get()
        self.assertEqual(
            reservation.state,
            IgCheckoutInventoryReservation.State.OVERBOOKED_REVIEW,
        )
        task = IgFollowUpTask.objects.get(event_key=f"inventory-overbooked:{proposal.pk}")
        self.assertEqual(task.status, IgFollowUpTask.Status.SKIPPED)
        self.assertEqual(task.reason, "inventory_overbooked_review")
        self.assertTrue(
            proposal.deal.followup_tasks.filter(
                reason="inventory_overbooked_review",
            ).exists()
        )
        self.assertEqual(
            IgFollowUpTask.objects.filter(
                event_key=f"inventory-overbooked:{proposal.pk}",
            ).count(),
            1,
        )

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


class VerifiedPaymentTimestampTests(SimpleTestCase):
    def test_provider_modified_date_wins_over_local_callback_time(self):
        from types import SimpleNamespace

        from management.services.ig_checkout_payment import _verified_payment_at

        local_callback_at = timezone.now()
        provider_paid_at = local_callback_at - timedelta(minutes=2)
        attempt = SimpleNamespace(
            payment_history=[
                {
                    "status": "success",
                    "payload": {"modifiedDate": provider_paid_at.isoformat()},
                }
            ],
            last_status_at=local_callback_at,
        )

        self.assertEqual(
            _verified_payment_at(attempt, fallback=local_callback_at),
            provider_paid_at,
        )
