def build_homepage_page_url(base_path: str, page: int) -> str:
    safe_base_path = base_path or "/"
    return safe_base_path if page <= 1 else f"{safe_base_path}?page={page}"


def _build_page_item(page: int, current_page: int, base_path: str) -> dict:
    return {
        "type": "page",
        "page": page,
        "url": build_homepage_page_url(base_path, page),
        "is_current": page == current_page,
    }


def _build_visible_pages(current_page: int, total_pages: int, expand_all_threshold: int) -> list[int]:
    if total_pages <= expand_all_threshold:
        return list(range(1, total_pages + 1))

    if current_page <= 3:
        return [1, 2, 3, total_pages]

    if current_page >= total_pages - 2:
        return [1, total_pages - 2, total_pages - 1, total_pages]

    return [1, current_page - 1, current_page, current_page + 1, total_pages]


def build_homepage_pagination_items(
    *,
    current_page: int,
    total_pages: int,
    base_path: str,
    expand_all_threshold: int = 7,
    boundary_count: int = 1,
    sibling_count: int = 1,
) -> list[dict]:
    del boundary_count, sibling_count

    if total_pages <= 0:
        return []

    current_page = max(1, min(current_page, total_pages))
    visible_pages = sorted(set(_build_visible_pages(current_page, total_pages, expand_all_threshold)))

    items = [
        {
            "type": "prev",
            "page": current_page - 1 if current_page > 1 else None,
            "url": build_homepage_page_url(base_path, current_page - 1) if current_page > 1 else "#",
            "is_disabled": current_page <= 1,
        }
    ]

    previous_page = None
    for page in visible_pages:
        if previous_page is not None:
            gap = page - previous_page
            if gap == 2:
                items.append(_build_page_item(previous_page + 1, current_page, base_path))
            elif gap > 2:
                items.append({"type": "ellipsis", "label": "…"})

        items.append(_build_page_item(page, current_page, base_path))
        previous_page = page

    items.append(
        {
            "type": "next",
            "page": current_page + 1 if current_page < total_pages else None,
            "url": build_homepage_page_url(base_path, current_page + 1) if current_page < total_pages else "#",
            "is_disabled": current_page >= total_pages,
        }
    )

    return items
