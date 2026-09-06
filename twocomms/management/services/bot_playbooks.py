"""Instruction routing for the IG sales bot.

Маршрутизація має два шари. Тут — теги клієнта (зріз CRM-стану), у
`bot_instruction_routing` — тригери поточного ходу, виключення й валідація.
Розділення не косметичне: зріз стану відповідає на «хто цей клієнт», а тригер —
на «про що він питає саме зараз», і плутати їх шкідливо. На проді у клієнта #5
стояв `objection=size` при `intent=payment`, тому розмірний playbook підмішувався
в повідомлення про оплату.
"""
from __future__ import annotations

from dataclasses import dataclass
import logging

from management.models import BotInstruction, IgClient

logger = logging.getLogger(__name__)


def _split_tags(raw: str) -> set[str]:
    return {p.strip().lower() for p in (raw or "").replace(";", ",").split(",") if p.strip()}


def tags_for_client(client: IgClient | None) -> set[str]:
    tags = {"global", "core", "sales"}
    if not client:
        return tags
    # F-CTX-002: `sales` used to be unconditional, so sales instructions were
    # routed into a post-sale conversation. Suppressing the follow-up alone does
    # not help — the bot still knows about discounts and can offer them in a
    # reactive reply.
    service_case = None
    if getattr(client, "pk", None):
        try:
            from management.services.ig_post_sale import open_service_case

            service_case = open_service_case(client)
        except Exception:
            service_case = None
    if service_case is not None:
        tags.discard("sales")
        tags.update({"post_sale", "service", str(service_case.case_type)})
    for value in (
        client.intent,
        client.stage,
        client.primary_objection,
        client.language,
    ):
        if value:
            tags.add(str(value).lower())
    if client.current_product_id:
        tags.add("product")
        tags.add("catalog")
    # Нижче — лише ті теги, яких **немає** серед значень enum-полів: усі
    # значення `intent`/`stage`/`primary_objection`/`language` уже додані циклом
    # вище. Раніше тут стояли ще пʼять гілок (`custom_print`, `payment_pending`,
    # `prepayment`, `price`, `size`), і всі вони були no-op — просто дублювали
    # те, що вже є. Явна таблиця, яка бреше, небезпечніша за відсутність
    # таблиці: саме на ній згоріла правка W3, коли викинули `discount`, а
    # інструкція прийшла через `price`.
    if client.stage == IgClient.Stage.PAYMENT_PENDING:
        tags.add("payment")
    if client.primary_objection == IgClient.Objection.PRICE:
        tags.add("discount")
    if client.primary_objection == IgClient.Objection.SIZE:
        tags.add("fit")
    if service_case is not None:
        # A stale price objection from the pre-purchase phase must not reopen the
        # discount playbook while an exchange is in progress.
        #
        # `price` is dropped together with `discount`, and that is not belt and
        # braces: the rescue instruction on production is tagged `price, discount`,
        # so removing only `discount` left it routed through `price` and the
        # suppression did nothing. Suppression has to be measured on the resulting
        # instruction block, not on the tag we intended to remove.
        for tag in ("sales", "discount", "price"):
            tags.discard(tag)
    try:
        from management.services.ig_objections import objection_tags_for_client

        tags.update(objection_tags_for_client(client))
    except Exception as exc:
        logger.warning("Could not project objection playbook tags: %s", exc)
    return tags


# Стеля на блок інструкцій. У каталогу й бази знань свої ліміти, а тут не було
# жодного: ні на довжину тексту, ні на кількість, ні на підсумковий блок. Сьогодні
# це не болить (7 інструкцій, ~1.8 KB), але це редагований із UI шар, який може
# непомітно з'їсти контекст. У production усі інструкції вже важили 4.5 KB, тому
# для кожної відповіді лишаємо бюджет і ніколи не ріжемо правило посередині.
MAX_INSTRUCTION_BLOCK_CHARS = 3500


@dataclass(frozen=True)
class InstructionModule:
    """A whole editable playbook suitable for optional policy admission."""

    id: str
    body: str
    priority: int
    tags: tuple[str, ...]
    active: bool

    def policy_input(self) -> dict:
        return {
            "id": self.id,
            "body": self.body,
            "priority": self.priority,
            "tags": self.tags,
            "active": self.active,
        }


@dataclass(frozen=True)
class InstructionOmission:
    id: str
    reason: str

    def metadata(self) -> dict[str, str]:
        return {"id": self.id, "reason": self.reason}


@dataclass(frozen=True)
class InstructionSelection:
    """Selection metadata for the legacy prompt wrapper and policy compiler."""

    modules: tuple[InstructionModule, ...]
    omitted: tuple[InstructionOmission, ...]
    visual_trigger_codes: tuple[str, ...]

    @property
    def selected_ids(self) -> tuple[str, ...]:
        return tuple(module.id for module in self.modules)

    def policy_inputs(self) -> list[dict]:
        return [module.policy_input() for module in self.modules]

    def metadata(self) -> dict:
        return {
            "selected_ids": list(self.selected_ids),
            "omitted": [item.metadata() for item in self.omitted],
            "visual_trigger_codes": list(self.visual_trigger_codes),
        }


def active_instruction_selection(
    client: IgClient | None = None,
    *,
    turn_text: str = "",
    budget_chars: int = MAX_INSTRUCTION_BLOCK_CHARS,
    visual_trigger_codes=None,
) -> InstructionSelection:
    """Choose applicable playbooks without cutting any instruction body.

    Visual trigger codes are accepted as explicit future B01.6 inputs. No
    visual fact is inferred here: current ``BotInstruction`` tags only define
    text/CRM routing, so the codes remain metadata until a later explicit
    routing contract exists.
    """
    from management.services.bot_instruction_routing import instruction_matches, turn_triggers

    try:
        budget = int(budget_chars)
    except (TypeError, ValueError) as exc:
        raise ValueError("instruction budget must be an integer") from exc
    if budget < 0:
        raise ValueError("instruction budget cannot be negative")
    visual_codes = tuple(sorted({str(code) for code in (visual_trigger_codes or ()) if str(code)}))
    client_tags = tags_for_client(client)
    active_triggers = turn_triggers(turn_text)
    modules: list[InstructionModule] = []
    omitted: list[InstructionOmission] = []
    used = 0
    for inst in BotInstruction.objects.order_by("priority", "id"):
        module_id = f"instruction:{inst.pk}"
        body = (inst.body or "").strip()
        if not inst.is_active:
            omitted.append(InstructionOmission(module_id, "inactive"))
            continue
        if not body:
            omitted.append(InstructionOmission(module_id, "empty_body"))
            continue
        if client is not None and not instruction_matches(
            inst.intent_tags, client_tags, active_triggers=active_triggers
        ):
            omitted.append(InstructionOmission(module_id, "not_relevant"))
            continue
        title = (inst.title or "").strip()
        rendered = f"• {title}: {body}" if title else f"• {body}"
        cost = len(rendered) + (1 if modules else 0)
        if used + cost > budget:
            omitted.append(InstructionOmission(module_id, "budget_exhausted"))
            continue
        modules.append(InstructionModule(
            id=module_id,
            body=rendered,
            priority=inst.priority,
            tags=tuple(sorted(_split_tags(inst.intent_tags))),
            active=True,
        ))
        used += cost
    return InstructionSelection(tuple(modules), tuple(omitted), visual_codes)


def active_instruction_block(
    client: IgClient | None = None,
    *,
    turn_text: str = "",
) -> str:
    """Інструкції, доречні цьому клієнту на цьому ході.

    Без клієнта (адмінка, тести, ручна генерація) віддаємо всі активні — це
    свідома сумісність: превʼю промпта має показувати повний набір.

    `turn_text` — повідомлення клієнта, від якого рахуються тригери `on:*`.
    Порожній текст означає «тригерів немає», тому інструкція з тригером у такий
    хід не підмішується. Це і є різниця між «клієнт питає про розмір зараз» і
    «в картці лежить objection=size з минулого тижня».
    """
    selection = active_instruction_selection(client, turn_text=turn_text)
    parts = [module.body for module in selection.modules]
    dropped = sum(1 for item in selection.omitted if item.reason == "budget_exhausted")
    if dropped:
        parts.append(
            f"…({dropped} інструкцій не вміщено в бюджет; попроси адміністратора "
            "скоротити або розділити їх)"
        )
    return "\n".join(parts)
