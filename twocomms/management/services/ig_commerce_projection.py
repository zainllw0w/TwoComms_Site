"""Projection between durable commerce sessions and legacy ``IgClient`` fields."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction

from management.ig_bot_models import IgCommerceSelectionSession


def _matching_legacy_selection(client) -> dict:
    context = client.sales_context if isinstance(client.sales_context, dict) else {}
    selection = context.get("assisted_checkout_selection")
    if not isinstance(selection, dict):
        return {}
    product_id = selection.get("product_id")
    if not client.current_product_id or str(product_id) != str(client.current_product_id):
        return {}
    return dict(selection)


def _legacy_line(client, generation: int) -> dict:
    product_id = client.current_product_id
    if not product_id:
        return {}
    line = {
        "line_id": f"legacy:{client.pk}:{generation}:0",
        "product_id": int(product_id),
        "size": str(client.current_size or ""),
        "color": str(client.current_color or ""),
        "quantity": max(1, int(client.current_qty or 1)),
        "confidence": str(client.current_product_confidence or "0"),
    }
    selection = _matching_legacy_selection(client)
    for key in ("fit_option_code", "color_variant_id", "option_values", "pay_type"):
        if key in selection and selection[key] not in (None, "", {}, []):
            line[key] = selection[key]
    return line


def bootstrap_session_from_legacy(client) -> IgCommerceSelectionSession:
    """Create the first durable open session from a legacy client snapshot.

    The assisted checkout context is copied only when it points at the same
    current product. Unknown/stale legacy context is deliberately discarded.
    """
    existing = (
        IgCommerceSelectionSession.objects.filter(client_id=client.pk, open_slot=1)
        .order_by("-generation")
        .first()
    )
    if existing is not None:
        return existing
    last_generation = (
        IgCommerceSelectionSession.objects.filter(client_id=client.pk)
        .order_by("-generation")
        .values_list("generation", flat=True)
        .first()
        or 0
    )
    generation = int(last_generation) + 1
    line = _legacy_line(client, generation)
    defaults = {
        "commercial_episode_id": client.current_commercial_episode_id,
        "open_slot": 1,
        "state": IgCommerceSelectionSession.State.OPEN,
        "lines": [line] if line else [],
        "active_index": 0,
    }
    try:
        with transaction.atomic():
            return IgCommerceSelectionSession.objects.create(
                client=client,
                generation=generation,
                **defaults,
            )
    except IntegrityError:
        winner = (
            IgCommerceSelectionSession.objects.filter(client_id=client.pk, open_slot=1)
            .order_by("-generation")
            .first()
        )
        if winner is None:
            raise
        return winner


def authoritative_session_for(client) -> IgCommerceSelectionSession:
    """Return the one open durable session, bootstrapping legacy state once."""
    session = (
        IgCommerceSelectionSession.objects.filter(client_id=client.pk, open_slot=1)
        .order_by("-generation")
        .first()
    )
    return session or bootstrap_session_from_legacy(client)


def start_new_session_for_episode(client, episode) -> IgCommerceSelectionSession:
    """Close the previous selection cycle and open a clean episode session.

    Repeat purchases must not inherit a prior product, configuration, price,
    candidate anchor, or allocation. The caller owns the client's transaction
    lock; the database uniqueness constraint remains the final guard against a
    second open session.
    """
    previous = (
        IgCommerceSelectionSession.objects.select_for_update()
        .filter(client_id=client.pk, open_slot=1)
        .order_by("-generation")
        .first()
    )
    if previous is not None:
        previous.state = IgCommerceSelectionSession.State.CLOSED
        previous.open_slot = None
        previous.save(update_fields=["state", "open_slot", "updated_at"])

    last_generation = (
        IgCommerceSelectionSession.objects.select_for_update()
        .filter(client_id=client.pk)
        .order_by("-generation")
        .values_list("generation", flat=True)
        .first()
        or 0
    )
    session = IgCommerceSelectionSession.objects.create(
        client_id=client.pk,
        commercial_episode_id=episode.pk,
        generation=int(last_generation) + 1,
        open_slot=1,
        state=IgCommerceSelectionSession.State.OPEN,
        lines=[],
        active_index=0,
    )
    project_active_line_to_legacy_client(session, client)
    return session


def _safe_decimal(value) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def project_active_line_to_legacy_client(session, client) -> None:
    """Expose only the durable active line through legacy CRM fields."""
    lines = list(session.lines or [])
    index = int(session.active_index or 0)
    line = (
        lines[index]
        if 0 <= index < len(lines) and isinstance(lines[index], dict)
        else {}
    )
    context = dict(client.sales_context or {}) if isinstance(client.sales_context, dict) else {}
    context.pop("assisted_checkout_selection", None)
    update_fields = [
        "current_product",
        "current_size",
        "current_color",
        "current_qty",
        "current_product_confidence",
        "sales_context",
        "updated_at",
    ]
    if line.get("product_id"):
        client.current_product_id = int(line["product_id"])
        client.current_size = str(line.get("size") or "")[:16]
        client.current_color = str(line.get("color") or "")[:64]
        try:
            client.current_qty = max(1, int(line.get("quantity") or line.get("qty") or 1))
        except (TypeError, ValueError):
            client.current_qty = 1
        client.current_product_confidence = _safe_decimal(line.get("confidence"))
        selection = {
            key: line[key]
            for key in (
                "product_id",
                "fit_option_code",
                "color_variant_id",
                "option_values",
                "pay_type",
            )
            if key in line and line[key] not in (None, "", {}, [])
        }
        if selection:
            context["assisted_checkout_selection"] = selection
    else:
        client.current_product_id = None
        client.current_size = ""
        client.current_color = ""
        client.current_qty = 1
        client.current_product_confidence = Decimal("0")
    client.sales_context = context
    client.save(update_fields=update_fields)
