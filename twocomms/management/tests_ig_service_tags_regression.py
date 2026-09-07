"""Регресс правки W3: подавление продажных инструкций было неполным.

Найдено разведкой W5 на живых данных. `tags_for_client` при открытом сервисном
кейсе выбрасывал `discount`, но оставлял `price`. А инструкция «Price Objection /
Rescue» на проде размечена обоими тегами (`price, discount`), поэтому она
продолжала проходить в промпт по `price` — то есть подавление не работало.

Это ровно та же ошибка, что в IMP-013: правка сделана по имени тега, а не по
фактической разметке данных.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from management.ig_bot_models import IgClient, IgPostSaleCase
from management.models import BotInstruction, InstagramBotMessage
from orders.models import Order


class ServiceCaseInstructionRoutingTests(TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            "service-tags-manager", password="x", is_staff=True
        )
        self.client_row = IgClient.get_or_create_for_sender("service-tags-client")
        self.client_row.primary_objection = IgClient.Objection.PRICE
        self.client_row.save(update_fields=["primary_objection", "updated_at"])
        # Дословная разметка инструкции #5 с прода.
        self.rescue = BotInstruction.objects.create(
            title="Price Objection / Rescue",
            body="Якщо клієнт каже дорого — запропонуй знижку 5%.",
            intent_tags="price, discount",
            is_active=True,
        )
        from management.tests_ig_policy_helpers import publish_current_instructions

        publish_current_instructions()

    def _open_case(self):
        order = Order.objects.create(
            order_number="TWC-SERVICE-TAGS",
            full_name="Buyer",
            phone="380500000000",
            total_sum=Decimal("2100.00"),
            payment_status="paid",
            status="ship",
        )
        return IgPostSaleCase.objects.create(
            client=self.client_row,
            order=order,
            source_message=InstagramBotMessage.objects.create(
                client=self.client_row,
                role=InstagramBotMessage.Role.USER,
                text="хочу обмін",
            ),
            case_type=IgPostSaleCase.CaseType.EXCHANGE,
            status=IgPostSaleCase.Status.IN_TRANSIT,
        )

    def test_price_tag_is_dropped_during_a_service_case(self):
        from management.services.bot_playbooks import tags_for_client

        self._open_case()

        tags = tags_for_client(self.client_row)

        self.assertNotIn("price", tags)
        self.assertNotIn("discount", tags)

    def test_rescue_instruction_does_not_reach_the_prompt_during_a_service_case(self):
        """Главная проверка: подавление измеряется по итоговому блоку, не по тегам."""
        from management.services.bot_playbooks import active_instruction_block

        self._open_case()

        block = active_instruction_block(self.client_row)

        self.assertNotIn("знижку 5%", block)

    def test_rescue_instruction_still_reaches_a_normal_price_objection(self):
        from management.services.bot_playbooks import active_instruction_block

        block = active_instruction_block(self.client_row)

        self.assertIn("знижку 5%", block)

    def test_untagged_instruction_still_reaches_everyone(self):
        """202 из 289 клиентов матчат только инструкцию с тегом core/global."""
        from management.services.bot_playbooks import active_instruction_block

        BotInstruction.objects.create(
            title="FAQ",
            body="Доставка Новою Поштою 1-3 дні.",
            intent_tags="",
            is_active=True,
        )
        from management.tests_ig_policy_helpers import publish_current_instructions

        publish_current_instructions()
        self._open_case()

        block = active_instruction_block(self.client_row)

        self.assertIn("1-3 дні", block)

    def test_service_case_tags_are_exposed_for_routing(self):
        from management.services.bot_playbooks import tags_for_client

        self._open_case()

        tags = tags_for_client(self.client_row)

        self.assertIn("post_sale", tags)
        self.assertIn("service", tags)
        self.assertIn("exchange", tags)
