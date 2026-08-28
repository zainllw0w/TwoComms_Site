"""Один авторитетный ответ про вариант, наличие и медиа (Э3.7).

Три разных потребителя давали три разных ответа на один вопрос:

* compact-каталог (`bot_catalog._build`) суммировал `ProductColorVariant.stock` и
  при нуле писал «під замовлення (відшиваємо 1-3 дні)»;
* checkout readiness решал через `VariantSizeRule` и `resolve_allocation`;
* выбор медиа (`select_catalog_media`) брал `filter(stock__gt=0)`.

Итог: можно было показать generic-фото или «под заказ» для варианта, который
checkout считает доступным — и наоборот. В тексте это выглядит как оговорка; в
карточке с фото и кнопкой это выглядит как официальное обещание бренда, поэтому
Э1.5 без этого пункта выкатывать нельзя.

Здесь один resolver уровня `product + variant + fit + size + quantity`, и
**медиа берётся из того же resolved variant**, а не из независимого запроса.
Агрегированный `stock` остаётся диагностикой и никогда не источником решения.

Модель никогда не объявляет наличие сама: `unknown` — это fail-closed состояние,
видимое оператору, а не разрешение сказать клиенту «є в наявності».
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from management.services.ig_availability import (
    AllocationSpec,
    AvailabilityStatus,
    StockAllocation,
    resolve_allocation,
)


class OfferStatus(StrEnum):
    IN_STOCK = "in_stock"
    MADE_TO_ORDER = "made_to_order"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


# Причины, по которым нулевой остаток означает «пошьём», а не «нет».
_MADE_TO_ORDER_REASONS = frozenset({
    "insufficient_catalog_variant_stock",
    "insufficient_warehouse_stock",
})
# Причины, по которым нулевой остаток означает именно «нет»: отключённый размер
# или неподдерживаемый фасон нельзя «отшить за 1-3 дня».
_HARD_UNAVAILABLE_REASONS = frozenset({
    "size_disabled",
    "fit_not_supported",
    "invalid_quantity",
})
# Отсутствие политики учёта — это «учёт по варианту не ведётся», ровно то, что
# витрина обещает как «під замовлення». Это НЕ повод сказать «є в наявності».
_UNTRACKED_REASONS = frozenset({
    "inventory_policy_missing",
    "inventory_untracked",
})


@dataclass(frozen=True)
class OfferResolution:
    """Единственный ответ, на который опираются все три потребителя."""

    status: OfferStatus
    reason: str
    product_id: int
    color_variant_id: int | None = None
    fit_code: str = ""
    size: str = ""
    quantity: int = 1
    allocation: StockAllocation | None = None
    # Агрегированный остаток — только для оператора. Никогда не основание решения.
    diagnostic_aggregate_stock: int = 0
    media_fallback_reason: str = ""

    @property
    def purchasable(self) -> bool:
        return self.status in {OfferStatus.IN_STOCK, OfferStatus.MADE_TO_ORDER}

    @property
    def customer_visible_availability(self) -> str:
        """Формулировка для клиента. Пустая строка = ничего не утверждаем."""
        if self.status == OfferStatus.IN_STOCK:
            return "в наявності"
        if self.status == OfferStatus.MADE_TO_ORDER:
            return "під замовлення (відшиваємо 1-3 дні)"
        if self.status == OfferStatus.UNAVAILABLE:
            return "зараз недоступно"
        return ""

    @property
    def exact_media_scope(self) -> tuple:
        """Точная область медиа: только этот вариант, если он известен."""
        if self.color_variant_id:
            return (self.product_id, int(self.color_variant_id))
        return (self.product_id, None)


def _aggregate_stock(product_id: int) -> int:
    from productcolors.models import ProductColorVariant

    try:
        return sum(
            int(value or 0)
            for value in ProductColorVariant.objects.filter(
                product_id=product_id
            ).values_list("stock", flat=True)
        )
    except Exception:
        return 0


def _product_is_published(product_id: int) -> bool:
    try:
        from storefront.models import Product, ProductStatus

        return Product.objects.filter(
            pk=product_id, status=ProductStatus.PUBLISHED
        ).exists()
    except Exception:
        return False


def resolve_offer(
    *,
    product_id: int,
    color_variant_id: int | None = None,
    fit_code: str = "",
    size: str = "",
    quantity: int = 1,
) -> OfferResolution:
    """Единственный авторитетный статус предложения.

    Fail-closed по построению: любое сомнение даёт `unknown`, а не «доступно».
    """
    try:
        product_id = int(product_id)
    except (TypeError, ValueError):
        return OfferResolution(
            OfferStatus.UNKNOWN, "invalid_product_id", product_id=0
        )
    if product_id <= 0:
        return OfferResolution(OfferStatus.UNKNOWN, "invalid_product_id", product_id=0)

    base = dict(
        product_id=product_id,
        color_variant_id=int(color_variant_id) if color_variant_id else None,
        fit_code=str(fit_code or ""),
        size=str(size or ""),
        quantity=max(0, int(quantity or 0)),
        diagnostic_aggregate_stock=_aggregate_stock(product_id),
    )

    if not _product_is_published(product_id):
        # Неопубликованный товар не «под заказ» и не «в наличии»: его нельзя
        # предлагать вообще.
        return OfferResolution(OfferStatus.UNAVAILABLE, "product_not_published", **base)

    decision = resolve_allocation(
        AllocationSpec(
            product_id=product_id,
            color_variant_id=base["color_variant_id"],
            size=base["size"],
            fit_code=base["fit_code"],
            quantity=max(1, base["quantity"]),
        )
    )
    if decision.status == AvailabilityStatus.ALLOCATABLE:
        return OfferResolution(
            OfferStatus.IN_STOCK, decision.reason,
            allocation=decision.allocation, **base
        )
    if decision.reason in _HARD_UNAVAILABLE_REASONS:
        return OfferResolution(OfferStatus.UNAVAILABLE, decision.reason, **base)
    if decision.reason in _MADE_TO_ORDER_REASONS:
        return OfferResolution(OfferStatus.MADE_TO_ORDER, decision.reason, **base)
    if decision.reason in _UNTRACKED_REASONS:
        return OfferResolution(OfferStatus.MADE_TO_ORDER, decision.reason, **base)
    # Всё остальное — неизвестность, а не разрешение. Оператор это видит.
    return OfferResolution(OfferStatus.UNKNOWN, decision.reason, **base)


def resolve_product_presentation(product_id: int) -> OfferResolution:
    """Статус товара без выбранного варианта — для строки каталога.

    Используется compact-каталогом вместо самостоятельного суммирования
    `stock`: иначе каталог и checkout снова начнут расходиться.
    """
    return resolve_offer(product_id=product_id)


def resolve_client_color_variant(client, product_id: int) -> tuple:
    """Вариант, выбранный клиентом, — или None с причиной (Э3.7 / NEW-CAT-002).

    Возвращает `(color_variant_id | None, reason)`. `reason` непустая только
    когда точного варианта нет: она попадает в `fallback_reason` медиа, чтобы
    оператор видел, почему отправлено generic-фото, а не догадывался.

    `IgClient` хранит цвет **текстом** (`current_color`), а не ссылкой на
    вариант. Поэтому сопоставление делается только при **однозначном**
    совпадении: два подходящих варианта — это не «возьмём первый», а отсутствие
    точного доказательства. Показать фото не того цвета хуже, чем показать
    generic-фото с честной причиной.
    """
    if client is None or not product_id:
        return None, "no_client_selection"
    color_text = str(getattr(client, "current_color", "") or "").strip().casefold()
    if not color_text:
        return None, "color_not_selected"
    try:
        from productcolors.models import ProductColorVariant

        variants = list(
            ProductColorVariant.objects.filter(product_id=int(product_id))
            .select_related("color")
            .order_by("order", "id")
        )
    except Exception:
        return None, "variant_lookup_failed"
    matches = []
    for variant in variants:
        names = {
            str(getattr(getattr(variant, "color", None), "name", "") or "").strip().casefold(),
            str(getattr(getattr(variant, "color", None), "slug", "") or "").strip().casefold(),
        }
        names.discard("")
        if color_text in names or any(
            name and (name in color_text or color_text in name) for name in names
        ):
            matches.append(variant)
    if len(matches) == 1:
        return int(matches[0].pk), ""
    if len(matches) > 1:
        return None, "color_match_ambiguous"
    return None, "color_match_not_found"
