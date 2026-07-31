from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from management.models import IgClient, InstagramBotMessage
from management.ig_bot_models import IgOrderAttribution


MGMT = override_settings(ROOT_URLCONF="twocomms.urls_management")
User = get_user_model()


class PostSaleClassifierTests(SimpleTestCase):
    def test_colloquial_exchange_verbs_are_detected(self):
        from management.services.ig_post_sale import detect_post_sale_type

        self.assertEqual(
            detect_post_sale_type("Хочу поміняти розмір XS на S"),
            "exchange",
        )
        self.assertEqual(
            detect_post_sale_type("Можно поменять оверсайз на regular?"),
            "exchange",
        )

    def test_exchange_noun_is_detected(self):
        from management.services.ig_post_sale import detect_post_sale_type

        self.assertEqual(
            detect_post_sale_type("Футболка вже у вас. Є розміри для заміни?"),
            "exchange",
        )

    def test_english_exchange_and_return_are_detected(self):
        from management.services.ig_post_sale import detect_post_sale_type

        for phrase in (
            "I need to exchange this shirt for size L",
            "Can I return this order?",
            "Please refund order TWC28072026N07",
            "I want a refund for my order",
        ):
            with self.subTest(phrase=phrase):
                expected = "exchange" if "exchange" in phrase else "return"
                self.assertEqual(detect_post_sale_type(phrase), expected)

    def test_english_pre_sale_and_policy_phrases_are_not_post_sale_cases(self):
        from management.services.ig_post_sale import detect_post_sale_type

        for phrase in (
            "What is your return policy?",
            "I am a returning customer and want another shirt",
            "Do you offer exchanges before I order?",
            "If I order and it does not fit, could I return it?",
        ):
            with self.subTest(phrase=phrase):
                self.assertEqual(detect_post_sale_type(phrase), "")

    def test_paid_customer_exchange_takes_priority_over_paid_waiting(self):
        from management.services.bot_sales_classifier import _interaction_type

        client = SimpleNamespace(
            stage=IgClient.Stage.PAID,
            is_blocked=False,
            intent=IgClient.Intent.UNKNOWN,
            primary_objection=IgClient.Objection.NONE,
        )
        result = {
            "opt_out": False,
            "no_buy": False,
            "objection": IgClient.Objection.NONE,
            "intent": IgClient.Intent.UNKNOWN,
            "signals": [],
        }
        with patch(
            "management.services.bot_payment_truth.client_has_verified_payment",
            return_value=True,
        ):
            self.assertEqual(
                _interaction_type(
                    client,
                    result,
                    "Хочу обміняти oversize XS на S, не підійшов розмір",
                    InstagramBotMessage.Role.USER,
                ),
                "support_complaint",
            )


class PostSaleCaseTests(TestCase):
    def setUp(self):
        self.client = IgClient.get_or_create_for_sender("post-sale-client")
        self.message = InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.USER,
            text="Хочу обміняти oversize XS на S, не підійшов розмір",
        )

    def test_exchange_case_is_idempotent_and_needs_details_without_order(self):
        from management.services.ig_post_sale import open_post_sale_case

        first = open_post_sale_case(self.client, self.message)
        second = open_post_sale_case(self.client, self.message)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.case_type, "exchange")
        self.assertEqual(first.status, "needs_details")
        self.assertEqual(first.source_message_id, self.message.id)

    def test_case_links_the_only_existing_order(self):
        from orders.models import Order
        from management.services.ig_post_sale import open_post_sale_case

        order = Order.objects.create(
            full_name="Post Sale",
            phone="0500000000",
            city="Харків",
            np_office="1",
            total_sum=100,
            status="new",
        )
        IgOrderAttribution.objects.create(
            order=order,
            client=self.client,
            creation_mode="linked_existing",
            payment_source="manager_verified",
        )
        case = open_post_sale_case(self.client, self.message, order=order)

        self.assertEqual(case.order_id, order.id)
        self.assertEqual(case.status, "open")

    def test_multiple_orders_are_not_guessed(self):
        from orders.models import Order
        from management.services.ig_post_sale import open_post_sale_case

        for name in ("One", "Two"):
            order = Order.objects.create(
                full_name=name,
                phone="0500000000",
                city="Харків",
                np_office="1",
                total_sum=100,
                status="new",
            )
            IgOrderAttribution.objects.create(
                order=order,
                client=self.client,
                creation_mode="linked_existing",
                payment_source="manager_verified",
            )
        case = open_post_sale_case(self.client, self.message)

        self.assertIsNone(case.order_id)
        self.assertEqual(case.status, "needs_details")

    def test_policy_question_does_not_open_case_for_attributed_order(self):
        from orders.models import Order
        from management.services.ig_post_sale import open_post_sale_case

        order = Order.objects.create(
            full_name="Post Sale",
            phone="0500000000",
            city="Харків",
            np_office="1",
            total_sum=100,
            status="new",
        )
        IgOrderAttribution.objects.create(
            order=order,
            client=self.client,
            creation_mode="linked_existing",
            payment_source="manager_verified",
        )
        policy_question = InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.USER,
            text="What is your return policy?",
        )

        self.assertIsNone(open_post_sale_case(self.client, policy_question))

    def test_second_exchange_message_updates_one_active_case(self):
        from management.services.ig_post_sale import open_post_sale_case

        first = open_post_sale_case(self.client, self.message)
        followup = InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.USER,
            text="Так, обмін саме на розмір M",
        )
        second = open_post_sale_case(self.client, followup)

        self.assertEqual(second.pk, first.pk)
        self.assertEqual(second.source_size, "XS")
        self.assertEqual(second.requested_size, "M")
        self.assertEqual(second.evidence_message_ids, [self.message.pk, followup.pk])

    def test_size_only_followup_updates_the_single_active_case(self):
        from management.services.ig_post_sale import open_post_sale_case

        first = open_post_sale_case(self.client, self.message)
        followup = InstagramBotMessage.objects.create(
            sender_id=self.client.igsid,
            client=self.client,
            role=InstagramBotMessage.Role.USER,
            text="Давайте XL розмір",
        )

        second = open_post_sale_case(self.client, followup)

        self.assertEqual(second.pk, first.pk)
        self.assertEqual(second.requested_size, "XL")
        self.assertEqual(second.evidence_message_ids, [self.message.pk, followup.pk])


@MGMT
class PostSaleApiTests(TestCase):
    def setUp(self):
        from orders.models import Order
        from management.services.ig_post_sale import open_post_sale_case

        self.admin = User.objects.create_user("post-sale-admin", password="x", is_staff=True)
        self.client.force_login(self.admin)
        self.customer = IgClient.get_or_create_for_sender("post-sale-api-client")
        self.message = InstagramBotMessage.objects.create(
            sender_id=self.customer.igsid,
            client=self.customer,
            role=InstagramBotMessage.Role.USER,
            text="Хочу обмін, oversize XS не підійшов",
        )
        self.order = Order.objects.create(
            full_name="Instagram Customer", phone="0500000000", city="Харків",
            np_office="1", total_sum=100, status="done", payment_status="paid",
        )
        IgOrderAttribution.objects.create(
            order=self.order, client=self.customer, creation_mode="linked_existing",
            payment_source="manager_verified",
        )
        self.case = open_post_sale_case(self.customer, self.message)

    def test_client_detail_exposes_post_sale_case_and_order_choices(self):
        data = self.client.get(
            reverse("management_bot_client_detail_api", args=[self.customer.pk])
        ).json()

        self.assertEqual(data["post_sale"]["action_count"], 1)
        self.assertEqual(data["post_sale"]["items"][0]["case_type"], "exchange")
        self.assertEqual(data["post_sale"]["items"][0]["order"]["id"], self.order.pk)
        self.assertEqual(data["post_sale"]["order_choices"][0]["id"], self.order.pk)

    def test_clients_queue_marks_active_post_sale_as_manager_action(self):
        data = self.client.get(reverse("management_bot_clients_api")).json()
        row = next(item for item in data["clients"] if item["id"] == self.customer.pk)
        self.assertTrue(row["manager_action_required"])

    def test_manager_can_update_size_and_status_without_creating_order(self):
        from orders.models import Order

        before = Order.objects.count()
        response = self.client.post(
            reverse("management_bot_post_sale_case_api", args=[self.customer.pk, self.case.pk]),
            {
                "order_id": str(self.order.pk),
                "source_fit": "oversize",
                "source_size": "XS",
                "requested_size": "S",
                "status": "approved",
                "manager_note": "Обмін погоджено",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.case.refresh_from_db()
        self.assertEqual(self.case.requested_size, "S")
        self.assertEqual(self.case.status, "approved")
        self.assertEqual(Order.objects.count(), before)

    def test_manager_cannot_link_another_clients_order(self):
        from orders.models import Order

        other = IgClient.get_or_create_for_sender("post-sale-other-client")
        foreign = Order.objects.create(
            full_name="Other", phone="0500000001", city="Київ", np_office="2",
            total_sum=200, status="new",
        )
        IgOrderAttribution.objects.create(
            order=foreign, client=other, creation_mode="linked_existing", payment_source="manager_verified",
        )

        response = self.client.post(
            reverse("management_bot_post_sale_case_api", args=[self.customer.pk, self.case.pk]),
            {"order_id": str(foreign.pk), "status": "open"},
        )

        self.assertEqual(response.status_code, 400)
        self.case.refresh_from_db()
        self.assertEqual(self.case.order_id, self.order.pk)
