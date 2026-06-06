"""Тести Фази 2 адмін-центру: життєвий цикл накладних + онлайн-статус."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from orders.models import WholesaleInvoice
from management.models import ManagerCommissionAccrual, ManagementDailyActivity
from management.services import invoice_center
from management.services.activity_tracking import compute_online_state, ONLINE_THRESHOLD_SECONDS

User = get_user_model()


def _make_invoice(user, *, number, review_status="approved", payment_status="not_paid", **extra):
    return WholesaleInvoice.objects.create(
        invoice_number=number,
        company_name="ТОВ Тест",
        contact_phone="+380000000000",
        delivery_address="Київ",
        total_amount=Decimal("1000.00"),
        order_details={},
        created_by=user,
        review_status=review_status,
        payment_status=payment_status,
        **extra,
    )


class InvoiceLifecycleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(username="mgr", password="x")

    def test_pending_is_review(self):
        inv = _make_invoice(self.manager, number="A-1", review_status="pending", payment_status="not_paid")
        self.assertEqual(invoice_center.derive_lifecycle(inv), "review")

    def test_rejected(self):
        inv = _make_invoice(self.manager, number="A-2", review_status="rejected")
        self.assertEqual(invoice_center.derive_lifecycle(inv), "rejected")

    def test_approved_no_link(self):
        inv = _make_invoice(self.manager, number="A-3", review_status="approved", payment_status="not_paid")
        self.assertEqual(invoice_center.derive_lifecycle(inv), "approved")

    def test_link_created_and_copied(self):
        inv = _make_invoice(
            self.manager, number="A-4", payment_status="not_paid",
            payment_url="https://pay.mono/x", payment_link_created_at=timezone.now(),
        )
        self.assertEqual(invoice_center.derive_lifecycle(inv), "link_created")
        inv.payment_link_copied_at = timezone.now()
        self.assertEqual(invoice_center.derive_lifecycle(inv), "link_copied")

    def test_awaiting_payment(self):
        inv = _make_invoice(self.manager, number="A-5", payment_status="pending", payment_url="https://pay.mono/x")
        self.assertEqual(invoice_center.derive_lifecycle(inv), "awaiting_payment")

    def test_paid_frozen_then_released(self):
        inv = _make_invoice(self.manager, number="A-6", payment_status="paid", paid_at=timezone.now())
        # Сигнал нарахування комісії спрацьовує при створенні paid-накладної,
        # тож використовуємо update_or_create і фіксуємо frozen_until у майбутньому.
        accr, _ = ManagerCommissionAccrual.objects.update_or_create(
            invoice=inv,
            defaults=dict(
                owner=self.manager, base_amount=Decimal("1000"), percent=Decimal("10"),
                amount=Decimal("100"), frozen_until=timezone.now() + timedelta(days=14),
            ),
        )
        self.assertEqual(invoice_center.derive_lifecycle(inv, accr), "paid_frozen")
        accr.frozen_until = timezone.now() - timedelta(days=1)
        self.assertEqual(invoice_center.derive_lifecycle(inv, accr), "paid_released")

    def test_refunded(self):
        inv = _make_invoice(self.manager, number="A-7", payment_status="refunded", returned_at=timezone.now())
        self.assertEqual(invoice_center.derive_lifecycle(inv), "refunded")

    def test_build_payload_counts_and_filter(self):
        _make_invoice(self.manager, number="B-1", review_status="pending", payment_status="not_paid")
        _make_invoice(self.manager, number="B-2", review_status="approved", payment_status="not_paid")
        payload = invoice_center.build_invoices_payload()
        self.assertEqual(payload["total"], 2)
        chips = {c["code"]: c["count"] for c in payload["filter_chips"]}
        self.assertEqual(chips["review"], 1)
        self.assertEqual(chips["approved"], 1)
        # фільтр по статусу
        filtered = invoice_center.build_invoices_payload(status="review")
        self.assertEqual(filtered["total"], 1)
        self.assertEqual(filtered["rows"][0]["number"], "B-1")

    def test_draft_excluded(self):
        _make_invoice(self.manager, number="C-1", review_status="draft")
        payload = invoice_center.build_invoices_payload()
        self.assertEqual(payload["total"], 0)


class OnlineStateTests(TestCase):
    def test_online_within_threshold(self):
        state = compute_online_state(timezone.now())
        self.assertTrue(state["online"])
        self.assertEqual(state["last_seen_label"], "Онлайн")

    def test_offline_beyond_threshold(self):
        seen = timezone.now() - timedelta(seconds=ONLINE_THRESHOLD_SECONDS + 600)
        state = compute_online_state(seen)
        self.assertFalse(state["online"])
        self.assertIn("тому", state["last_seen_label"])

    def test_none_last_seen(self):
        state = compute_online_state(None)
        self.assertFalse(state["online"])
        self.assertEqual(state["last_seen_label"], "Немає даних")


@override_settings(ROOT_URLCONF="twocomms.urls_management",
                   ALLOWED_HOSTS=["testserver", "management.twocomms.shop"])
class AdminInvoicesTabRenderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(username="boss", password="x", is_staff=True)
        cls.manager = User.objects.create_user(username="m1", password="x")
        _make_invoice(cls.manager, number="R-1", review_status="pending", payment_status="not_paid")
        _make_invoice(cls.manager, number="R-2", review_status="approved", payment_status="paid", paid_at=timezone.now())

    def test_invoices_tab_renders_full_lifecycle(self):
        self.client.force_login(self.staff)
        resp = self.client.get("/admin-panel/?tab=invoices", HTTP_HOST="management.twocomms.shop", secure=True)
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode("utf-8")
        self.assertIn("inv-center", body)
        self.assertIn("R-1", body)
        self.assertIn("R-2", body)  # підтверджена/оплачена теж видима (фікс B-INV2)
        self.assertIn("inv-chip", body)


@override_settings(ROOT_URLCONF="twocomms.urls_management",
                   ALLOWED_HOSTS=["testserver", "management.twocomms.shop"])
class AdminRedesignTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(username="rd_boss_t", password="x", is_staff=True)
        cls.manager = User.objects.create_user(username="rd_mgr_t", password="x")
        cls.manager.userprofile.is_manager = True
        cls.manager.userprofile.save()

    def test_overview_tab_renders_dashboard(self):
        self.client.force_login(self.staff)
        resp = self.client.get("/admin-panel/?tab=overview", HTTP_HOST="management.twocomms.shop", secure=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("ov-grid", resp.content.decode())

    def test_managers_tab_renders_cards_and_dossier(self):
        self.client.force_login(self.staff)
        resp = self.client.get("/admin-panel/?tab=managers", HTTP_HOST="management.twocomms.shop", secure=True)
        body = resp.content.decode()
        self.assertEqual(resp.status_code, 200)
        self.assertIn("mgr-grid", body)
        self.assertIn('id="dossier"', body)
        self.assertIn("top-mgr-wrap", body)  # топ-менеджери
        self.assertNotIn("admin-command-board", body)  # стара "статистика зверху" прибрана

    def test_top_managers_period_switch(self):
        from management.services.top_managers import build_top_managers
        for period in ("today", "week", "month", "all"):
            data = build_top_managers(period)
            self.assertEqual(data["period"], period)
            self.assertIn("by_invoices", data)
            self.assertIn("by_processed", data)
            self.assertIn("by_mosaic", data)

    def test_dossier_api_returns_sections(self):
        self.client.force_login(self.staff)
        resp = self.client.get(f"/admin-panel/user/{self.manager.id}/dossier/",
                               HTTP_HOST="management.twocomms.shop", secure=True)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        for key in ("manager", "payouts", "recent_paid_invoices", "contract", "mosaic", "compensation"):
            self.assertIn(key, data)

    def test_assign_level_works(self):
        self.client.force_login(self.staff)
        resp = self.client.post(
            "/admin-panel/levels/assign/",
            {"user_id": self.manager.id, "level": "level_1", "weekly_salary": "1500",
             "commission_percent": "7.5", "start_date": "2026-06-01", "comment": "тест"},
            HTTP_HOST="management.twocomms.shop", secure=True, HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["success"])
        from management.services.manager_levels import get_current_level
        self.assertEqual(get_current_level(self.manager).level, "level_1")
