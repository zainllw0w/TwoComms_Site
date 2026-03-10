from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


_TWOPLACES = Decimal("0.01")

_WHOLESALE_PRICE_CONTEXT = {
    "tshirt": {
        "drop": 570,
        "wholesale": [540, 520, 500, 490, 480],
        "ranges": ["8–15 шт.", "16–31 шт.", "32–63 шт.", "64–99 шт.", "100+ шт."],
    },
    "hoodie": {
        "drop": 1350,
        "wholesale": [1300, 1250, 1200, 1175, 1150],
        "ranges": ["8–15 шт.", "16–31 шт.", "32–63 шт.", "64–99 шт.", "100+ шт."],
    },
}


class InvoicePayloadError(ValueError):
    pass


def get_management_wholesale_price_context() -> dict[str, dict[str, Any]]:
    return deepcopy(_WHOLESALE_PRICE_CONTEXT)


def _quantize_money(value: Decimal) -> Decimal:
    return value.quantize(_TWOPLACES, rounding=ROUND_HALF_UP)


def _parse_money(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return _quantize_money(value)
    if isinstance(value, int):
        return _quantize_money(Decimal(value))
    if isinstance(value, float):
        return _quantize_money(Decimal(str(value)))

    text = str(value).strip()
    if not text:
        return None
    text = (
        text.replace("грн", "")
        .replace("₴", "")
        .replace("\u00a0", "")
        .replace(" ", "")
        .replace(",", ".")
    )
    try:
        return _quantize_money(Decimal(text))
    except InvalidOperation:
        return None


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _parse_quantity(value: Any) -> int:
    try:
        quantity = int(value)
    except (TypeError, ValueError):
        raise InvoicePayloadError("Некоректна кількість товару") from None
    if quantity <= 0:
        raise InvoicePayloadError("Кількість товару повинна бути більшою за нуль")
    return quantity


def _guess_product_type(product_type: str, title: str) -> str:
    cleaned_type = _clean_text(product_type).lower()
    if cleaned_type in {"tshirt", "hoodie"}:
        return cleaned_type

    title_lower = _clean_text(title).lower()
    if any(token in title_lower for token in ("худі", "hoodie", "фліс", "флис", "fleece")):
        return "hoodie"
    if any(token in title_lower for token in ("футбол", "t-shirt", "tshirt", "tee")):
        return "tshirt"
    raise InvoicePayloadError("Не вдалося визначити тип товару для накладної")


def _wholesale_price_for_quantity(product_type: str, quantity: int) -> Decimal:
    prices = _WHOLESALE_PRICE_CONTEXT[product_type]["wholesale"]
    if quantity >= 100:
        return Decimal(str(prices[4]))
    if quantity >= 64:
        return Decimal(str(prices[3]))
    if quantity >= 32:
        return Decimal(str(prices[2]))
    if quantity >= 16:
        return Decimal(str(prices[1]))
    return Decimal(str(prices[0]))


def _compose_display_title(title: str, extra_description: str) -> str:
    if not extra_description:
        return title
    return f"{title} [{extra_description}]"


def normalize_management_invoice_payload(*, company_data: dict[str, Any], order_items: list[dict[str, Any]]) -> dict[str, Any]:
    normalized_company = {
        "companyName": _clean_text(company_data.get("companyName")),
        "companyNumber": _clean_text(company_data.get("companyNumber")),
        "contactPhone": _clean_text(company_data.get("contactPhone")),
        "deliveryAddress": _clean_text(company_data.get("deliveryAddress")),
        "storeLink": _clean_text(company_data.get("storeLink")),
    }

    required_fields = [
        ("companyName", "назву компанії"),
        ("contactPhone", "номер телефону"),
        ("deliveryAddress", "адресу доставки"),
    ]
    missing = [label for key, label in required_fields if not normalized_company[key]]
    if missing:
        raise InvoicePayloadError(f"Заповніть: {', '.join(missing)}")

    if not order_items:
        raise InvoicePayloadError("Немає товарів для накладної")

    prepared_items: list[dict[str, Any]] = []
    totals_by_type = {"tshirt": 0, "hoodie": 0}

    for raw_item in order_items:
        product = (raw_item or {}).get("product") or {}
        raw_title = _clean_text(product.get("title"))
        if not raw_title:
            raise InvoicePayloadError("У позиції відсутня назва товару")

        product_type = _guess_product_type(product.get("type"), raw_title)
        quantity = _parse_quantity((raw_item or {}).get("quantity"))
        totals_by_type[product_type] += quantity

        pricing_mode = _clean_text((raw_item or {}).get("pricing_mode") or (raw_item or {}).get("pricingMode")).lower()
        pricing_mode = "manual" if pricing_mode == "manual" else "auto"

        manual_price = _parse_money((raw_item or {}).get("manual_price") or (raw_item or {}).get("manualPrice"))
        extra_description = _clean_text(
            (raw_item or {}).get("extra_description") or (raw_item or {}).get("extraDescription")
        )

        prepared_items.append(
            {
                "product": {
                    "id": product.get("id"),
                    "type": product_type,
                    "title": raw_title,
                    "image": product.get("image") or product.get("main_image") or "",
                },
                "size": _clean_text((raw_item or {}).get("size")),
                "color": _clean_text((raw_item or {}).get("color")) or "Чорний",
                "quantity": quantity,
                "pricing_mode": pricing_mode,
                "manual_price": manual_price,
                "extra_description": extra_description,
            }
        )

    normalized_items: list[dict[str, Any]] = []
    total_amount = Decimal("0.00")

    for item in prepared_items:
        product_type = item["product"]["type"]
        base_unit_price = _quantize_money(_wholesale_price_for_quantity(product_type, totals_by_type[product_type]))
        use_manual_price = item["pricing_mode"] == "manual" and item["manual_price"] is not None and item["manual_price"] > 0
        unit_price = _quantize_money(item["manual_price"] if use_manual_price else base_unit_price)
        line_total = _quantize_money(unit_price * Decimal(item["quantity"]))
        display_title = _compose_display_title(item["product"]["title"], item["extra_description"])

        normalized_items.append(
            {
                "product": dict(item["product"]),
                "size": item["size"],
                "color": item["color"],
                "quantity": item["quantity"],
                "pricing_mode": "manual" if use_manual_price else "auto",
                "extra_description": item["extra_description"],
                "display_title": display_title,
                "title": display_title,
                "base_unit_price": base_unit_price,
                "unit_price": unit_price,
                "line_total": line_total,
                "price": unit_price,
                "total": line_total,
            }
        )
        total_amount += line_total

    return {
        "company_data": normalized_company,
        "items": normalized_items,
        "totals": {
            "total_tshirts": totals_by_type["tshirt"],
            "total_hoodies": totals_by_type["hoodie"],
            "total_amount": _quantize_money(total_amount),
        },
    }


def serialize_management_invoice_payload(normalized_payload: dict[str, Any]) -> dict[str, Any]:
    def _serialize_money(value: Decimal) -> str:
        return f"{_quantize_money(value):.2f}"

    serialized_items = []
    for item in normalized_payload["items"]:
        serialized_items.append(
            {
                "product": dict(item["product"]),
                "size": item["size"],
                "color": item["color"],
                "quantity": item["quantity"],
                "pricing_mode": item["pricing_mode"],
                "extra_description": item["extra_description"],
                "display_title": item["display_title"],
                "title": item["title"],
                "base_unit_price": _serialize_money(item["base_unit_price"]),
                "unit_price": _serialize_money(item["unit_price"]),
                "line_total": _serialize_money(item["line_total"]),
                "price": _serialize_money(item["price"]),
                "total": _serialize_money(item["total"]),
            }
        )

    totals = normalized_payload["totals"]
    return {
        "company_data": dict(normalized_payload["company_data"]),
        "order_items": serialized_items,
        "totals": {
            "total_tshirts": totals["total_tshirts"],
            "total_hoodies": totals["total_hoodies"],
            "total_amount": _serialize_money(totals["total_amount"]),
        },
    }


def build_management_invoice_workbook(
    *,
    company_data: dict[str, Any],
    normalized_items: list[dict[str, Any]],
    totals: dict[str, Any],
    invoice_number: str,
    created_at_label: str,
) -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "Оптова накладна"

    title_fill = PatternFill("solid", fgColor="1F4E78")
    section_fill = PatternFill("solid", fgColor="DDEBF7")
    header_fill = PatternFill("solid", fgColor="2F75B5")
    zebra_fill = PatternFill("solid", fgColor="F7FBFF")
    summary_fill = PatternFill("solid", fgColor="E2F0D9")
    link_fill = PatternFill("solid", fgColor="FFF2CC")
    thin = Side(style="thin", color="D0D7DE")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    title_font = Font(name="Arial", size=16, bold=True, color="FFFFFF")
    section_font = Font(name="Arial", size=11, bold=True, color="1F1F1F")
    header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    body_font = Font(name="Arial", size=10, color="1F1F1F")
    emphasis_font = Font(name="Arial", size=10, bold=True, color="1F1F1F")
    link_font = Font(name="Arial", size=10, underline="single", color="0563C1")

    center = Alignment(horizontal="center", vertical="center")
    left = Alignment(horizontal="left", vertical="center", wrapText=True)
    right = Alignment(horizontal="right", vertical="center")

    ws.merge_cells("A1:G1")
    ws["A1"] = "ОПТОВА НАКЛАДНА"
    ws["A1"].font = title_font
    ws["A1"].fill = title_fill
    ws["A1"].alignment = center
    ws["A1"].border = border
    ws.row_dimensions[1].height = 26

    info_rows = [
        (3, "Назва компанії/ФОП/ПІБ", company_data.get("companyName") or "—"),
        (4, "Номер компанії/ЄДРПОУ/ІПН", company_data.get("companyNumber") or "—"),
        (5, "Номер телефону", company_data.get("contactPhone") or "—"),
        (6, "Посилання на магазин", company_data.get("storeLink") or "—"),
        (7, "Адреса доставки", company_data.get("deliveryAddress") or "—"),
    ]
    for row_index, label, value in info_rows:
        ws[f"A{row_index}"] = label
        ws[f"A{row_index}"].font = section_font
        ws[f"A{row_index}"].fill = section_fill
        ws[f"A{row_index}"].alignment = left
        ws[f"A{row_index}"].border = border

        ws.merge_cells(f"B{row_index}:D{row_index}")
        value_cell = ws[f"B{row_index}"]
        value_cell.value = value
        value_cell.font = link_font if row_index == 6 and value not in {"", "—"} else body_font
        value_cell.alignment = left
        value_cell.border = border
        value_cell.fill = link_fill if row_index == 6 else PatternFill(fill_type=None)
        if row_index == 6 and value not in {"", "—"}:
            value_cell.hyperlink = value
        for col in ("C", "D"):
            ws[f"{col}{row_index}"].border = border

    side_meta = [
        (3, "Номер накладної", invoice_number),
        (4, "Дата створення", created_at_label),
        (5, "Футболки", totals["total_tshirts"]),
        (6, "Худі", totals["total_hoodies"]),
        (7, "Загальна сума", totals["total_amount"]),
    ]
    for row_index, label, value in side_meta:
        ws[f"E{row_index}"] = label
        ws[f"E{row_index}"].font = section_font
        ws[f"E{row_index}"].fill = section_fill
        ws[f"E{row_index}"].alignment = left
        ws[f"E{row_index}"].border = border

        ws.merge_cells(f"F{row_index}:G{row_index}")
        value_cell = ws[f"F{row_index}"]
        value_cell.value = value
        value_cell.font = emphasis_font
        value_cell.alignment = right if row_index == 7 else left
        value_cell.border = border
        if row_index == 7:
            value_cell.number_format = '#,##0.00 "₴"'
            value_cell.fill = summary_fill
        for col in ("G",):
            ws[f"{col}{row_index}"].border = border

    ws.merge_cells("A9:G9")
    ws["A9"] = "Позиції накладної"
    ws["A9"].font = section_font
    ws["A9"].fill = section_fill
    ws["A9"].alignment = left
    ws["A9"].border = border

    header_row = 10
    headers = ["№", "Назва товару", "Розмір", "Колір", "Кількість", "Ціна за од.", "Сума"]
    for column, header in enumerate(headers, start=1):
        cell = ws.cell(row=header_row, column=column, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
        cell.border = border

    current_row = header_row + 1
    for index, item in enumerate(normalized_items, start=1):
        ws.cell(row=current_row, column=1, value=index)
        ws.cell(row=current_row, column=2, value=item["display_title"])
        ws.cell(row=current_row, column=3, value=item["size"])
        ws.cell(row=current_row, column=4, value=item["color"])
        ws.cell(row=current_row, column=5, value=item["quantity"])
        ws.cell(row=current_row, column=6, value=float(item["unit_price"]))
        ws.cell(row=current_row, column=7, value=float(item["line_total"]))

        for column in range(1, 8):
            cell = ws.cell(row=current_row, column=column)
            cell.font = body_font
            cell.border = border
            if column in {1, 5}:
                cell.alignment = center
            elif column in {6, 7}:
                cell.alignment = right
                cell.number_format = '#,##0.00 "₴"'
            else:
                cell.alignment = left
            if index % 2 == 0:
                cell.fill = zebra_fill

        estimated_lines = max(1, len(str(item["display_title"])) // 34 + 1)
        ws.row_dimensions[current_row].height = max(22, estimated_lines * 16)
        current_row += 1

    summary_row = current_row
    ws.merge_cells(f"A{summary_row}:F{summary_row}")
    ws[f"A{summary_row}"] = "Разом"
    ws[f"A{summary_row}"].font = emphasis_font
    ws[f"A{summary_row}"].fill = summary_fill
    ws[f"A{summary_row}"].alignment = right
    ws[f"A{summary_row}"].border = border
    ws[f"G{summary_row}"] = float(totals["total_amount"])
    ws[f"G{summary_row}"].font = emphasis_font
    ws[f"G{summary_row}"].fill = summary_fill
    ws[f"G{summary_row}"].alignment = right
    ws[f"G{summary_row}"].border = border
    ws[f"G{summary_row}"].number_format = '#,##0.00 "₴"'

    ws.freeze_panes = "A10"
    ws.auto_filter.ref = f"A10:G{summary_row - 1}"
    ws.sheet_view.showGridLines = False
    ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0

    ws.column_dimensions["A"].width = 6
    ws.column_dimensions["B"].width = 40
    ws.column_dimensions["C"].width = 18
    ws.column_dimensions["D"].width = 18
    ws.column_dimensions["E"].width = 12
    ws.column_dimensions["F"].width = 14
    ws.column_dimensions["G"].width = 16

    for row_index in range(3, 8):
        ws.row_dimensions[row_index].height = 24 if row_index != 7 else 36

    for column in range(1, 8):
        letter = get_column_letter(column)
        if ws.column_dimensions[letter].width < 12:
            ws.column_dimensions[letter].width = 12

    return wb
