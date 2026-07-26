from __future__ import annotations

from decimal import Decimal, InvalidOperation


def _money(value) -> Decimal:
    try:
        amount = Decimal(str(value if value is not None else "0"))
    except (InvalidOperation, TypeError, ValueError):
        amount = Decimal("0")
    return amount.quantize(Decimal("0.01"))


def order_amounts(order) -> dict[str, Decimal]:
    """Return the order subtotal, discount and actual payable total.

    ``Order.total_sum`` is the pre-discount subtotal in the current order
    contract. Payment reconciliation must therefore use the final payable
    amount, never a customer-specific constant and never the subtotal alone.
    """
    if order is None:
        zero = Decimal("0.00")
        return {"subtotal": zero, "discount": zero, "payable": zero}
    subtotal = _money(getattr(order, "total_sum", None))
    discount = max(_money(getattr(order, "discount_amount", None)), Decimal("0.00"))
    payable = max(subtotal - discount, Decimal("0.00"))
    return {"subtotal": subtotal, "discount": discount, "payable": payable}
