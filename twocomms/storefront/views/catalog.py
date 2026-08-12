"""
Catalog views - Каталог товаров и категорий.

Содержит views для:
- Главной страницы (home)
- Каталога товаров (catalog)
- Поиска
- Фильтрации
- AJAX подгрузки товаров
"""

from collections import defaultdict
from decimal import Decimal
from functools import wraps
from urllib.parse import urlencode

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, Http404, HttpResponsePermanentRedirect
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.db.models import Case, Count, ExpressionWrapper, F, IntegerField, Min, Prefetch, Q, Value, When
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _

from ..models import (
    CategoryColorLanding,
    Product,
    ProductFitOption,
    Category,
    SurveySession,
    UserPromoCode,
    UserAction,
)
from ..pagination import build_homepage_pagination_items
from ..services.card_preview import (
    attach_preferred_card_image,
    enrich_color_preview_with_slugs,
)
from ..services.catalog_facets import (
    FACET_ALLOWED,
    SELLABLE_SIZE_ORDER,
    active_collection_descendant_slugs,
    filter_products_by_facets,
    normalize_catalog_facet_state,
)
from ..services.catalog_helpers import (
    apply_public_product_order,
    build_color_preview_key,
    build_color_preview_map,
    get_categories_cached,
    get_public_category_version,
    get_public_product_order_version,
)
from ..services.category_seo_blocks import (
    get_category_seo_blocks,
    get_category_seo_layout,
)
from ..services.general_catalog_seo import get_general_catalog_seo_layout
from ..services.color_seo_copy import build_catalog_color_seo
from ..services.color_filter import (
    apply_color_filter,
    build_available_colors,
    build_home_color_chips,
    build_reset_url,
    canonical_color_filter,
    normalise_color_slugs,
    parse_color_filter,
)
from ..services.survey_engine import load_survey_definition
from ..utm_tracking import record_search
from cache_utils import get_fragment_cache
from .utils import (
    _build_query_string,
    cache_page_for_anon,
    HOME_PRODUCTS_PER_PAGE,
    PRODUCTS_PER_PAGE,
    public_product_listing_cache_prefix,
)


# ==================== CATALOG VIEWS ====================

CATALOG_SHOWCASE_CARD_CONFIG = (
    {
        'key': 'longsleeves',
        'number': '01',
        'title': _('Лонгсліви'),
        'subtitle': _('Функціональність. Стиль. Характер.'),
        'starting_price': 1090,
        'fallback_slug': 'long-sleeve',
        'image': 'img/catalog/catalog-longsleeves.webp',
        'mobile_order': 3,
        'mobile_image_avif': 'img/catalog/catalog-longsleeve-cutout.avif',
        'mobile_image_webp': 'img/catalog/catalog-longsleeve-cutout.webp',
        'mobile_image_width': 1107,
        'mobile_image_height': 1200,
        'slugs': ('longslivy', 'longsleeves', 'longsleeve', 'longslivi'),
        'tokens': ('лонг', 'long'),
        'swatches': ('#050505', '#6a6b60', '#e7e1d3', '#8c8f79'),
    },
    {
        'key': 'tshirts',
        'number': '02',
        'title': _('Футболки'),
        'subtitle': _('Графіка, що говорить гучніше за слова.'),
        'starting_price': 790,
        'fallback_slug': 'tshirts',
        'image': 'img/catalog/catalog-tshirts.webp',
        'mobile_order': 1,
        'mobile_image_webp': 'img/configurator/custom-ref/tshirt-bej-oversize.webp',
        'mobile_image_width': 1200,
        'mobile_image_height': 1400,
        'slugs': ('futbolki', 'futbolky', 'tshirts', 't-shirts', 'tshirt', 'tees'),
        'tokens': ('футбол', 'tshirt', 'shirt', 'tee'),
        'swatches': ('#050505', '#3a3d3f', '#62684a', '#ede8dc'),
    },
    {
        'key': 'hoodies',
        'number': '03',
        'title': _('Худі'),
        'subtitle': _('Тепло. Захист. Нічого зайвого.'),
        'starting_price': 1790,
        'fallback_slug': 'hoodie',
        'image': 'img/catalog/catalog-hoodies.webp',
        'mobile_order': 2,
        'mobile_image_webp': 'img/configurator/custom-ref/hoodie-black.webp',
        'mobile_image_width': 1200,
        'mobile_image_height': 1400,
        'slugs': ('hudi', 'hoodie', 'hoodies', 'khudi'),
        'tokens': ('худі', 'hood'),
        'swatches': ('#050505', '#303436', '#6a6f48', '#efe9dc'),
    },
)


def _pagination_query_prefix(request):
    params = request.GET.copy()
    params.pop('page', None)
    encoded = params.urlencode()
    return f'{encoded}&' if encoded else ''


_CATALOG_FACET_KEYS = {
    "theme",
    "collection",
    "audience",
    "availability",
    "fit",
    "size",
    "color",
    "thermo",
}

_CATALOG_QUERY_KEYS = _CATALOG_FACET_KEYS | {"page", "sort", "category"}
_CATALOG_TRACKING_QUERY_KEYS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_content",
        "utm_term",
        "fbclid",
        "gbraid",
        "gclid",
        "msclkid",
        "ref",
        "ref_",
        "ttclid",
        "wbraid",
        "yclid",
    }
)
_CATALOG_ROOT_CATEGORY_SLUGS = frozenset({"tshirts", "hoodie", "long-sleeve"})
_CATALOG_ROOT_SORT_VALUES = frozenset(
    {"recommended", "newest", "price-asc", "price-desc"}
)
_CATALOG_SMART_SORT_VALUES = frozenset(
    {"recommended", "price-asc", "price-desc"}
)
_CATALOG_PAGINATION_KEY_ORDER = (
    "category",
    "sort",
    "theme",
    "collection",
    "audience",
    "availability",
    "fit",
    "size",
    "color",
    "thermo",
)
_CATALOG_CACHE_VERSION = "catalog-pagination-v2-20260812"


def _catalog_route_scope(kwargs):
    cat_slug = str(kwargs.get("cat_slug") or "").strip().lower()
    if cat_slug:
        return "smart" if cat_slug in SMART_SELECTOR_CATEGORY_SLUGS else "category"
    if kwargs.get("collection_slug"):
        return "smart"
    return "root"


def _catalog_query_value(value, key):
    value = str(value or "").strip()
    if key == "size":
        return value.upper()
    if key == "page" and value.isdecimal():
        return str(int(value))
    if key == "fit":
        value = value.lower()
        return SMART_SELECTOR_FIT_ALIASES.get(value, value)
    return value.lower()


def _validate_catalog_query_shape(request, *, scope):
    """Reject query aliases before page-cache lookup can serve an old 200."""
    unknown = set(request.GET) - _CATALOG_QUERY_KEYS - _CATALOG_TRACKING_QUERY_KEYS
    if unknown:
        raise Http404("Unknown catalog query parameter.")

    supported = {
        "page",
        "color",
    }
    if scope == "root":
        supported.update({"sort", "category", "availability", "size"})
    elif scope == "smart":
        supported.update(
            {
                "sort",
                "theme",
                "collection",
                "audience",
                "availability",
                "fit",
                "size",
                "thermo",
            }
        )

    unsupported = {
        key
        for key in set(request.GET)
        if key not in supported and key not in _CATALOG_TRACKING_QUERY_KEYS
    }
    if unsupported:
        raise Http404("Catalog query parameter is not supported on this route.")

    for key in ("page", "sort"):
        values = request.GET.getlist(key)
        if len(values) > 1:
            raise Http404(f"Duplicate {key} parameters are not valid.")

    raw_pages = request.GET.getlist("page")
    if raw_pages:
        raw_page = str(raw_pages[0] or "").strip()
        if (
            not raw_page.isdecimal()
            or len(raw_page) > 10
            or int(raw_page) < 1
        ):
            raise Http404("Page number is not valid.")

    raw_sorts = request.GET.getlist("sort")
    if raw_sorts:
        value = _catalog_query_value(raw_sorts[0], "sort")
        allowed = _CATALOG_ROOT_SORT_VALUES if scope == "root" else _CATALOG_SMART_SORT_VALUES
        if value not in allowed:
            raise Http404("Sort value is not valid.")

    raw_categories = request.GET.getlist("category")
    if raw_categories:
        if scope != "root":
            raise Http404("Category facet is not supported on this route.")
        values = [_catalog_query_value(value, "category") for value in raw_categories]
        if any(not value or value not in _CATALOG_ROOT_CATEGORY_SLUGS for value in values):
            raise Http404("Category value is not valid.")
        if len(values) != len(set(values)):
            raise Http404("Duplicate category values are not valid.")

    for key in _CATALOG_FACET_KEYS - {"color"}:
        values = request.GET.getlist(key)
        if not values:
            continue
        canonical_values = [_catalog_query_value(value, key) for value in values]
        if any(not value for value in canonical_values):
            raise Http404(f"Facet '{key}' contains an empty value.")
        if len(canonical_values) != len(set(canonical_values)):
            raise Http404(f"Facet '{key}' contains a duplicate value.")


def _catalog_query_alias_redirect(request):
    raw_pages = request.GET.getlist("page")
    params = request.GET.copy()
    changed = False
    if raw_pages:
        raw_page = str(raw_pages[0] or "").strip()
        canonical_page = str(int(raw_page))
        if canonical_page == "1":
            params.pop("page", None)
            changed = True
        elif raw_page != canonical_page:
            params.setlist("page", [canonical_page])
            changed = True

    raw_sorts = request.GET.getlist("sort")
    if raw_sorts and _catalog_query_value(raw_sorts[0], "sort") == "recommended":
        params.pop("sort", None)
        changed = True

    if not changed:
        return None
    query = _build_query_string(params)
    target = request.path + (f"?{query}" if query else "")
    return HttpResponsePermanentRedirect(target)


def _build_catalog_cache_query(
    request,
    *,
    exclude_keys=frozenset(),
    key_order=None,
):
    parts = []
    query_items = request.GET.lists()
    if key_order is None:
        query_items = sorted(query_items)
    else:
        order = {key: index for index, key in enumerate(key_order)}
        query_items = sorted(
            query_items,
            key=lambda item: (order.get(item[0], len(order)), item[0]),
        )
    for key, values in query_items:
        if key in exclude_keys or key in _CATALOG_TRACKING_QUERY_KEYS:
            continue
        if key == "color":
            values = [",".join(normalise_color_slugs(values))]
            if not values[0]:
                continue
        else:
            values = [_catalog_query_value(value, key) for value in values]
            if key in _CATALOG_FACET_KEYS | {"category"}:
                values = sorted(values)
        parts.extend((key, value) for value in values)
    return urlencode(parts, doseq=True)


def _build_catalog_pagination_query_prefix(request):
    """Build stable pagination links without changing tracking propagation."""
    if _catalog_cacheable_request(request):
        query = _build_catalog_cache_query(
            request,
            exclude_keys={"page"},
            key_order=_CATALOG_PAGINATION_KEY_ORDER,
        )
        return f"{query}&" if query else ""
    return _pagination_query_prefix(request)


def _catalog_cacheable_request(request):
    return not any(key in request.GET for key in _CATALOG_TRACKING_QUERY_KEYS)


def _catalog_cache_prefix(request, view_func):
    """Bust old full-page catalog responses after pagination serialization changes."""
    return (
        f"{public_product_listing_cache_prefix(request, view_func)}:"
        f"{_CATALOG_CACHE_VERSION}"
    )


def _catalog_cache_policy(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        scope = _catalog_route_scope(kwargs)
        _validate_catalog_query_shape(request, scope=scope)
        redirect = _catalog_query_alias_redirect(request)
        if redirect is not None:
            return redirect
        request._catalog_cache_query = _build_catalog_cache_query(request)
        request._catalog_fragment_identity = request._catalog_cache_query
        request._catalog_pagination_query_prefix = (
            _build_catalog_pagination_query_prefix(request)
        )
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def _validate_catalog_facet_query(request, *, category=None):
    """Reject facet aliases that would otherwise render an equivalent 200.

    Interactive selectors still use repeated keys for distinct values and the
    colour decorator still owns its legacy comma-separated normalization. This
    guard only rejects empty/unknown values, repeated copies of one value, and
    facet axes that the current route does not implement.
    """
    smart_category = bool(
        category and category.slug in SMART_SELECTOR_CATEGORY_SLUGS
    )
    supported = {"color"}
    if category is None:
        supported.update({"availability", "size"})
    elif smart_category:
        supported.update(
            {"theme", "collection", "audience", "availability", "fit", "size", "thermo"}
        )

    normalized = normalize_catalog_facet_state(request.GET)
    for facet in _CATALOG_FACET_KEYS:
        raw_values = request.GET.getlist(facet)
        if not raw_values:
            continue
        if facet not in supported:
            raise Http404(f"Facet '{facet}' is not supported on this route.")
        if facet == "color":
            # ``canonical_color_filter`` owns color aliases, ordering and the
            # historical comma-separated format. Category-level empty-result
            # validation happens after the real product queryset is built.
            continue
        canonical_values = []
        for raw_value in raw_values:
            value = str(raw_value or "").strip()
            if not value:
                raise Http404(f"Facet '{facet}' contains an empty value.")
            if facet == "fit":
                value = SMART_SELECTOR_FIT_ALIASES.get(value.lower(), value.lower())
            elif facet == "size":
                value = value.upper()
            else:
                value = value.lower()
            canonical_values.append(value)
        if len(canonical_values) != len(set(canonical_values)):
            raise Http404(f"Facet '{facet}' contains a duplicate value.")
        accepted_values = set(normalized.get(facet, ()))
        if facet == "theme":
            # Keep the published built-in theme vocabulary valid even when a
            # test/staging database has not seeded MerchCollection rows yet.
            accepted_values.update(FACET_ALLOWED["theme"])
        if any(value not in accepted_values for value in canonical_values):
            raise Http404(f"Facet '{facet}' contains an unknown value.")

    return normalized


def _paginate_catalog_queryset(product_qs, request):
    """Use strict public pagination semantics for catalog HTML routes."""
    paginator = Paginator(product_qs, PRODUCTS_PER_PAGE)
    raw_pages = request.GET.getlist("page")
    if not raw_pages:
        page_number = 1
    elif len(raw_pages) != 1:
        raise Http404("Duplicate page parameters are not valid.")
    else:
        raw_page = str(raw_pages[0] or "").strip()
        if not raw_page or not raw_page.isdecimal():
            raise Http404("Page number is not valid.")
        page_number = int(raw_page)
        if page_number < 1:
            raise Http404("Page number is not valid.")
    try:
        page_obj = paginator.page(page_number)
    except InvalidPage as exc:
        raise Http404("Page does not exist.") from exc
    return paginator, page_obj


SMART_SELECTOR_CATEGORY_SLUGS = ('tshirts', 'hoodie', 'long-sleeve')
SMART_SELECTOR_FIT_QUERY_CODES = {
    'classic': ('classic', 'класичн'),
    'oversize': ('oversize', 'оверсайз'),
    'standard': ('standard', 'regular', 'стандартн'),
}
SMART_SELECTOR_FIT_LABELS = {
    'classic': _('Класичний'),
    'oversize': _('Оверсайз'),
    'standard': _('Стандартний'),
}
SMART_SELECTOR_FIT_ALIASES = {
    'classic': 'classic',
    'класичний': 'classic',
    'regular': 'standard',
    'standard': 'standard',
    'стандартний': 'standard',
    'oversize': 'oversize',
    'оверсайз': 'oversize',
}
SMART_SELECTOR_SORT_VALUES = ('recommended', 'price-asc', 'price-desc')
SMART_SELECTOR_SIZE_CODES = ('XS', 'S', 'M', 'L', 'XL', '2XL')
SMART_SELECTOR_SIZE_LABELS = {code: code for code in SMART_SELECTOR_SIZE_CODES}
SMART_SELECTOR_AVAILABILITY_LABELS = {
    'in_stock': _('В наявності'),
}
SMART_SELECTOR_THERMO_LABEL = _('Термохромна тканина')
ROOT_CATALOG_SORT_VALUES = ('recommended', 'newest', 'price-asc', 'price-desc')
ROOT_CATALOG_CATEGORY_LABELS = {
    'tshirts': _('Футболки'),
    'hoodie': _('Худі'),
    'long-sleeve': _('Лонгсліви'),
}


def _smart_selector_fit_codes(category, product_queryset):
    if category.slug == 'long-sleeve':
        return ['standard']

    allowed = {'classic', 'oversize'}

    option_codes = (
        ProductFitOption.objects
        .filter(
            product_id__in=product_queryset.values_list('pk', flat=True).order_by(),
            is_active=True,
        )
        .values_list('code', flat=True)
        .distinct()
    )
    normalized = {
        SMART_SELECTOR_FIT_ALIASES.get((code or '').strip().lower())
        for code in option_codes
    }
    normalized.discard(None)
    return [code for code in ('classic', 'oversize', 'standard') if code in allowed and code in normalized]


def _smart_selector_facet_state(request, category, fit_codes):
    """Return the normalized public state supported by the current selector."""
    if not category or category.slug not in SMART_SELECTOR_CATEGORY_SLUGS:
        return {}
    state = normalize_catalog_facet_state(request.GET)
    supported = {
        key: tuple(values)
        for key, values in state.items()
        if key in {
            "theme", "collection", "audience", "availability", "fit",
            "size", "thermo",
        }
    }
    selected_fits = tuple(
        code for code in supported.get("fit", ()) if code in set(fit_codes or ())
    )
    if selected_fits:
        supported["fit"] = selected_fits
    else:
        supported.pop("fit", None)
    return supported


def _smart_selector_fit_query(fit):
    query = Q()
    for code in SMART_SELECTOR_FIT_QUERY_CODES.get(fit, ()):
        query |= Q(fit_options__code__istartswith=code)
    return query


def _smart_selector_sort_state(request):
    requested = (request.GET.get('sort') or '').strip().lower()
    return requested if requested in SMART_SELECTOR_SORT_VALUES else 'recommended'


def _apply_smart_selector_sort(product_queryset, selected_sort):
    if selected_sort not in ('price-asc', 'price-desc'):
        return product_queryset

    discounted_price = ExpressionWrapper(
        F('price') * (Value(100) - F('discount_percent')) / Value(100),
        output_field=IntegerField(),
    )
    product_queryset = product_queryset.annotate(
        smart_selector_sort_price=Case(
            When(discount_percent__gt=0, then=discounted_price),
            default=F('price'),
            output_field=IntegerField(),
        )
    )
    direction = '' if selected_sort == 'price-asc' else '-'
    return product_queryset.order_by(
        f'{direction}smart_selector_sort_price',
        '-priority',
        '-id',
    )


def _root_catalog_sort_state(request):
    requested = (request.GET.get('sort') or '').strip().lower()
    return requested if requested in ROOT_CATALOG_SORT_VALUES else 'recommended'


def _apply_root_catalog_sort(product_queryset, selected_sort):
    if selected_sort == 'newest':
        return product_queryset.order_by('-published_at', '-created_at', '-id')
    return _apply_smart_selector_sort(product_queryset, selected_sort)


def _root_catalog_selected_categories(request):
    requested = {
        str(value or '').strip().lower()
        for value in request.GET.getlist('category')
    }
    return tuple(slug for slug in SMART_SELECTOR_CATEGORY_SLUGS if slug in requested)


def _sort_smart_selector_products_by_visible_price(product_queryset, selected_sort):
    """Sort the complete filtered category by the price rendered on cards."""
    if selected_sort not in ('price-asc', 'price-desc'):
        return product_queryset

    products = list(product_queryset)
    build_color_preview_map(products)
    descending = selected_sort == 'price-desc'

    def sort_key(product):
        price = Decimal(str(
            getattr(product, 'card_price_min', None)
            or getattr(product, 'final_price', 0)
            or 0
        ))
        return (
            -price if descending else price,
            -int(getattr(product, 'priority', 0) or 0),
            -int(getattr(product, 'id', 0) or 0),
        )

    products.sort(key=sort_key)
    return products


def _smart_selector_product_fits(product):
    options = [option for option in product.fit_options.all() if option.is_active]
    if not options:
        category = getattr(product, 'category', None)
        return ['standard'] if getattr(category, 'slug', '') == 'long-sleeve' else []

    fits = []
    for option in options:
        code = (option.code or '').strip().lower()
        normalized = SMART_SELECTOR_FIT_ALIASES.get(code, code)
        if normalized and normalized not in fits:
            fits.append(normalized)
    return fits


def _smart_selector_product_fit(product):
    """Keep the legacy scalar value for data attributes and older consumers."""
    fits = _smart_selector_product_fits(product)
    return fits[0] if fits else ''


def _smart_selector_language():
    language = (get_language() or "uk").lower().replace("_", "-").split("-", 1)[0]
    return language if language in {"uk", "ru", "en"} else "uk"


def _localized_collection_label(collection, language):
    return next(
        (
            str(value).strip()
            for value in (
                getattr(collection, f"name_{language}", ""),
                collection.name_uk,
                collection.name_ru,
                collection.name_en,
                collection.slug,
            )
            if str(value or "").strip()
        ),
        collection.slug,
    )


def _localized_collection_value(collection, field, language):
    return next(
        (
            str(value).strip()
            for value in (
                getattr(collection, f"{field}_{language}", ""),
                getattr(collection, f"{field}_uk", ""),
                getattr(collection, f"{field}_ru", ""),
                getattr(collection, f"{field}_en", ""),
            )
            if str(value or "").strip()
        ),
        "",
    )


def _build_merch_collection_page(collection):
    language = _smart_selector_language()
    label = _localized_collection_label(collection, language)
    description = _localized_collection_value(collection, "description", language)
    if language == "en":
        fallback_title = f"{label} merch — TwoComms"
        fallback_description = f"Explore {label} apparel and prints by TwoComms."
    elif language == "ru":
        fallback_title = f"Мерч для {label} — TwoComms"
        fallback_description = f"Мерч {label}: доступные модели и принты TwoComms."
    else:
        fallback_title = f"Мерч для {label} — TwoComms"
        fallback_description = f"Мерч {label}: доступні моделі та принти TwoComms."
    return {
        "slug": collection.slug,
        "kind": collection.kind,
        "label": label,
        "h1": _localized_collection_value(collection, "seo_h1", language) or fallback_title,
        "title": _localized_collection_value(collection, "seo_title", language) or fallback_title,
        "description": _localized_collection_value(collection, "seo_description", language) or description or fallback_description,
        "intro": description or fallback_description,
        "canonical_path": f"/merch/{collection.slug}/",
        "accent_token": collection.accent_token,
    }


def _smart_selector_merchandising_contract(facet_state):
    """Load the active taxonomy once for filters and card presentation."""
    from product_catalog.models import AudienceTag, MerchCollection

    language = _smart_selector_language()
    collections = list(
        MerchCollection.objects.filter(is_active=True).order_by("order", "slug")
    )
    by_id = {collection.pk: collection for collection in collections}
    by_parent = defaultdict(list)
    for collection in collections:
        by_parent[collection.parent_id].append(collection)

    selected_themes = set(facet_state.get("theme", ()))
    selected_collections = set(facet_state.get("collection", ()))

    def public_row(collection, ancestors=(), seen=()):
        label = _localized_collection_label(collection, language)
        row = {
            "code": collection.slug,
            "slug": collection.slug,
            "kind": collection.kind,
            "label": label,
            "selected": (
                collection.slug in selected_themes
                if collection.parent_id is None
                else collection.slug in selected_collections
            ),
            "path_label": " / ".join((*ancestors, label)),
            "public_path": (
                f"/merch/{collection.slug}/" if collection.indexable else ""
            ),
            "children": [],
        }
        branch_seen = (*seen, collection.pk)
        row["children"] = [
            public_row(child, (*ancestors, label), branch_seen)
            for child in by_parent.get(collection.pk, ())
            if child.pk not in branch_seen
        ]
        return row

    theme_options = [
        public_row(collection)
        for collection in by_parent.get(None, ())
        if collection.kind in {MerchCollection.Kind.THEME, MerchCollection.Kind.CITY}
    ]
    audiences = list(
        AudienceTag.objects.filter(is_active=True).order_by("order", "code")
    )
    selected_audiences = set(facet_state.get("audience", ()))
    audience_options = [
        {
            "code": tag.code,
            "label": (
                getattr(tag, f"label_{language}", "")
                or tag.label_uk
                or tag.label_ru
                or tag.label_en
                or tag.code
            ),
            "selected": tag.code in selected_audiences,
        }
        for tag in audiences
    ]
    audience_by_id = {tag.pk: row for tag, row in zip(audiences, audience_options)}
    return {
        "language": language,
        "collections": collections,
        "collection_by_id": by_id,
        "theme_options": theme_options,
        "audience_options": audience_options,
        "audience_by_id": audience_by_id,
    }


def _attach_smart_selector_product_context(products, merchandising):
    """Attach presentation-safe prefetched audience and leaf collection facts."""
    by_id = merchandising["collection_by_id"]
    language = merchandising["language"]
    audience_by_id = merchandising["audience_by_id"]
    for product in products:
        product.smart_selector_fits = _smart_selector_product_fits(product)
        product.smart_selector_fit_options = [
            {
                'code': code,
                'label': SMART_SELECTOR_FIT_LABELS.get(code, code.replace('-', ' ').title()),
            }
            for code in product.smart_selector_fits
        ]
        product.smart_selector_fit = product.smart_selector_fits[0] if product.smart_selector_fits else ''
        product.smart_selector_fits_key = ','.join(product.smart_selector_fits)
        assignments = sorted(
            (
                row
                for row in product.merch_collection_assignments.all()
                if row.collection.is_active
            ),
            key=lambda row: (row.order, row.collection.order, row.collection.slug),
        )
        selected_ids = {row.collection_id for row in assignments}
        implied_parent_ids = set()
        for assignment in assignments:
            seen = {assignment.collection_id}
            parent_id = assignment.collection.parent_id
            while parent_id and parent_id not in seen:
                seen.add(parent_id)
                if parent_id in selected_ids:
                    implied_parent_ids.add(parent_id)
                parent = by_id.get(parent_id)
                parent_id = parent.parent_id if parent is not None else None

        collection_rows = []
        root_theme_slugs = []
        for assignment in assignments:
            collection = assignment.collection
            if collection.pk in implied_parent_ids:
                continue
            label = assignment.display_label.strip() or _localized_collection_label(
                collection, language
            )
            collection_rows.append(
                {
                    "slug": collection.slug,
                    "kind": collection.kind,
                    "label": label,
                    "public_path": (
                        f"/merch/{collection.slug}/" if collection.indexable else ""
                    ),
                }
            )
            root = collection
            seen = {root.pk}
            while root.parent_id and root.parent_id not in seen:
                seen.add(root.parent_id)
                root = by_id.get(root.parent_id) or root
            if root.parent_id is None and root.slug not in root_theme_slugs:
                root_theme_slugs.append(root.slug)

        audience_rows = []
        for assignment in product.audience_assignments.all():
            row = audience_by_id.get(assignment.tag_id)
            if row is not None:
                audience_rows.append(dict(row))

        product.smart_selector_collections = collection_rows
        product.smart_selector_audiences = audience_rows
        product.smart_selector_theme = root_theme_slugs[0] if root_theme_slugs else ""
        preview_rows = list(getattr(product, "colors_preview", []) or [])
        product.smart_selector_has_thermo = any(
            bool(row.get("is_thermo")) for row in preview_rows
        )
        product.smart_selector_available = bool(
            getattr(product, "is_dropship_available", True)
            and (preview_rows or not getattr(product, "color_variants", None))
        )
        product.smart_selector_availability_label = (
            _("В наявності")
            if product.smart_selector_available
            else _("Немає в наявності")
        )


def _build_smart_selector_context(
    request,
    category,
    categories,
    products,
    product_queryset,
    *,
    fit_codes=None,
    selected_sort=None,
    facet_state=None,
    merchandising=None,
):
    if not category or category.slug not in SMART_SELECTOR_CATEGORY_SLUGS:
        return {'smart_selector_enabled': False}

    category_tabs = [
        item for item in categories
        if item.slug in SMART_SELECTOR_CATEGORY_SLUGS
    ]
    category_tabs.sort(key=lambda item: SMART_SELECTOR_CATEGORY_SLUGS.index(item.slug))
    if fit_codes is None:
        fit_codes = _smart_selector_fit_codes(category, product_queryset)
    if selected_sort is None:
        selected_sort = _smart_selector_sort_state(request)
    if facet_state is None:
        facet_state = _smart_selector_facet_state(request, category, fit_codes)
    if merchandising is None:
        merchandising = _smart_selector_merchandising_contract(facet_state)
    _attach_smart_selector_product_context(products, merchandising)
    selected_themes = facet_state.get("theme", ())
    selected_fits = facet_state.get("fit", ())

    return {
        'smart_selector_enabled': True,
        'smart_selector_active_category': category,
        'smart_selector_category_tabs': category_tabs,
        'smart_selector_theme_options': merchandising["theme_options"],
        'smart_selector_audience_options': merchandising["audience_options"],
        'smart_selector_facet_state': facet_state,
        'smart_selector_fit_codes': fit_codes,
        'smart_selector_fit_options': [
            {
                'code': code,
                'label': SMART_SELECTOR_FIT_LABELS[code],
                'selected': code in selected_fits,
            }
            for code in fit_codes
        ],
        'smart_selector_availability_options': [
            {
                'code': code,
                'label': label,
                'selected': code in facet_state.get('availability', ()),
            }
            for code, label in SMART_SELECTOR_AVAILABILITY_LABELS.items()
        ],
        'smart_selector_size_options': [
            {
                'code': code,
                'label': SMART_SELECTOR_SIZE_LABELS[code],
                'selected': code in facet_state.get('size', ()),
            }
            for code in SMART_SELECTOR_SIZE_CODES
        ],
        'smart_selector_thermo_options': [
            {
                'code': 'thermo',
                'label': SMART_SELECTOR_THERMO_LABEL,
                'selected': 'thermo' in facet_state.get('thermo', ()),
            }
        ],
        'smart_selector_selected_theme': selected_themes[0] if selected_themes else '',
        'smart_selector_selected_fit': selected_fits[0] if selected_fits else '',
        'smart_selector_selected_sort': selected_sort,
    }


def _match_showcase_category(categories, config):
    slugs = {slug.lower() for slug in config['slugs']}
    tokens = tuple(token.lower() for token in config['tokens'])

    for category in categories:
        slug = (getattr(category, 'slug', '') or '').lower()
        name = (getattr(category, 'name', '') or '').lower()
        if slug in slugs or any(token in slug or token in name for token in tokens):
            return category

    return None


def _compute_showcase_swatches(category_ids, fallback_per_category, *, min_usage=1):
    """Phase 19i (2026-05-10): showcase swatches reflect REAL DB colours.

    For each category, return ALL distinct colours stocked across
    *published* products, ordered by usage (most-stocked first), as
    rich dicts ``{primary, secondary}`` so the template can render
    split swatches for two-tone colours like "white-burgundy" (where
    secondary_hex is set on ``Color``).

    Design decisions:
    * No usage threshold by default (``min_usage=1``) — even a single
      product's colour is shown so the card is honest about inventory.
      Phase 19h's threshold caused the card to fall back to fake grey
      ramps; the user wants real DB output even if it's only 1–2
      swatches.
    * No fallback padding when the category has any real colours;
      cards visually adapt to 1–N swatches. Fallback is only used as
      the very last resort for empty categories so the layout doesn't
      break before any product exists.
    * Up to 4 swatches per card to keep the visual rhythm consistent.

    Args:
        category_ids: iterable of category PKs to compute for.
        fallback_per_category: ``{cat_id: tuple(hex, ...)}`` defaults
            used ONLY when a category has zero published variants
            (keeps an empty category card from rendering blank).
        min_usage: minimum number of products required for a colour
            to appear; defaults to 1 (no filtering).

    Returns:
        ``{cat_id: tuple({'primary': hex, 'secondary': hex|None}, ...)}``
        with at most 4 entries per category.
    """
    if not category_ids:
        return {}

    from productcolors.models import ProductColorVariant

    # One query grouped by (category_id, primary_hex, secondary_hex).
    # Distinct-product count drives ordering — when one product carries
    # multiple variants of the same colour we still want product-level
    # usage to win, mirroring the chip counts above the catalog grid.
    rows = (
        ProductColorVariant.objects
        .filter(
            product__category_id__in=list(category_ids),
            product__status='published',
        )
        .values(
            'product__category_id',
            'color__primary_hex',
            'color__secondary_hex',
        )
        .annotate(usage=Count('product_id', distinct=True))
        .order_by('product__category_id', '-usage')
    )

    by_category: dict[int, list[dict]] = defaultdict(list)
    seen_per_category: dict[int, set[tuple[str, str]]] = defaultdict(set)
    for row in rows:
        cat_id = row['product__category_id']
        primary = (row['color__primary_hex'] or '').strip()
        secondary = (row['color__secondary_hex'] or '').strip() or None
        if not primary:
            continue
        if (row.get('usage') or 0) < min_usage:
            continue
        key = (primary.lower(), (secondary or '').lower())
        if key in seen_per_category[cat_id]:
            continue
        if len(by_category[cat_id]) >= 4:
            continue
        by_category[cat_id].append({'primary': primary, 'secondary': secondary})
        seen_per_category[cat_id].add(key)

    result: dict[int, tuple[dict, ...]] = {}
    for cat_id in category_ids:
        live = by_category.get(cat_id, [])
        if live:
            # Honest reflection of inventory — no fake fallback padding.
            result[cat_id] = tuple(live)
        else:
            # Empty category: keep the legacy palette so the layout
            # doesn't break for a not-yet-stocked category.
            fallback = list(fallback_per_category.get(cat_id, ('#050505',)))[:4]
            result[cat_id] = tuple(
                {'primary': hex_value, 'secondary': None} for hex_value in fallback
            )
    return result


def _build_catalog_showcase_cards(categories):
    matched_categories = {}
    for config in CATALOG_SHOWCASE_CARD_CONFIG:
        category = _match_showcase_category(categories, config)
        if category and getattr(category, 'id', None):
            matched_categories[config['key']] = category

    category_ids = [category.id for category in matched_categories.values()]
    product_stats = {}
    if category_ids:
        product_stats = {
            item['category_id']: item
            for item in Product.objects.filter(
                category_id__in=category_ids,
                status='published',
            ).values('category_id').annotate(total=Count('id'), min_price=Min('price'))
        }

    # Phase 19g: build per-category fallback map from the legacy
    # hard-coded palettes so categories with no published variants
    # still render visually identical to the pre-fix design.
    fallback_swatches = {
        category.id: next(
            (cfg['swatches'] for cfg in CATALOG_SHOWCASE_CARD_CONFIG if cfg['key'] == key),
            ('#050505',),
        )
        for key, category in matched_categories.items()
    }
    live_swatches = _compute_showcase_swatches(category_ids, fallback_swatches)

    cards = []
    for config in CATALOG_SHOWCASE_CARD_CONFIG:
        category = matched_categories.get(config['key'])
        # Override the static config swatches with live ones when
        # available; preserve the rest of the config unchanged.
        card = {**config, 'category': category}
        # Phase 19i: legacy ``swatches`` (tuple of hex strings) →
        # ``swatch_specs`` (list of {primary, secondary}). Convert any
        # static config palette so the template only needs one shape.
        legacy_hexes = config.get('swatches') or ()
        card['swatch_specs'] = [
            {'primary': h, 'secondary': None} for h in legacy_hexes[:4]
        ]
        if category:
            # Phase 19h: admin override wins over live; live wins over
            # legacy fallback. Empty override → fall through to live.
            manual = _normalize_swatch_overrides(
                getattr(category, 'showcase_swatch_hexes', None)
            )
            if manual:
                card['swatch_specs'] = list(manual[:4])
            elif category.id in live_swatches:
                card['swatch_specs'] = list(live_swatches[category.id][:4])
        # Keep the legacy ``swatches`` key as a tuple of primaries for
        # any code path that still consumes it (back-compat).
        card['swatches'] = tuple(s['primary'] for s in card['swatch_specs'])
        stats = product_stats.get(category.id, {}) if category else {}
        card['product_count'] = stats.get('total', 0) if category else None
        card['starting_price'] = stats.get('min_price') or config.get('starting_price')
        cards.append(card)
    return cards


def _normalize_swatch_overrides(value):
    """Phase 19h/i: sanitize admin-entered swatch override.

    Accepts:
    * list of hex strings: ``["#000000", "#fafafa"]``
    * list of objects: ``[{"primary":"#fafafa","secondary":"#c1382f"}]``
    * mixed.

    Returns up to 4 ``{'primary', 'secondary'}`` dicts with normalised
    lowercase hexes; invalid entries are dropped.
    """
    if not value or not isinstance(value, (list, tuple)):
        return ()

    def _norm_hex(raw):
        if not isinstance(raw, str):
            return None
        candidate = raw.strip()
        if not candidate:
            return None
        if not candidate.startswith('#'):
            candidate = '#' + candidate
        candidate = candidate.lower()
        if len(candidate) not in (4, 7):  # #abc or #aabbcc
            return None
        # Hex digits validation.
        if any(ch not in '0123456789abcdef' for ch in candidate[1:]):
            return None
        return candidate

    out = []
    seen = set()
    for raw in value:
        primary = secondary = None
        if isinstance(raw, dict):
            primary = _norm_hex(raw.get('primary') or raw.get('hex') or '')
            secondary = _norm_hex(raw.get('secondary') or '')
        else:
            primary = _norm_hex(raw)
        if not primary:
            continue
        key = (primary, secondary or '')
        if key in seen:
            continue
        seen.add(key)
        out.append({'primary': primary, 'secondary': secondary})
        if len(out) >= 4:
            break
    return tuple(out)


# Legacy alias kept for any external test imports.
_normalize_swatch_hexes = _normalize_swatch_overrides

def _product_cards_queryset(*, include_fit_options=False, include_merchandising=False):
    prefetches = ['images', 'color_variants__images']
    if include_fit_options:
        prefetches.append('fit_options')
    if include_merchandising:
        from product_catalog.models import ProductAudience, ProductMerchCollection

        prefetches.extend(
            (
                Prefetch(
                    'audience_assignments',
                    queryset=(
                        ProductAudience.objects
                        .filter(tag__is_active=True)
                        .select_related('tag')
                        .order_by('tag__order', 'tag__code')
                    ),
                ),
                Prefetch(
                    'merch_collection_assignments',
                    queryset=(
                        ProductMerchCollection.objects
                        .filter(collection__is_active=True)
                        .select_related('collection')
                        .order_by('order', 'collection__order', 'collection__slug')
                    ),
                ),
            )
        )
    return Product.objects.select_related('category').prefetch_related(*prefetches).defer(
        'description', 'full_description', 'short_description', 'ai_description', 'ai_keywords',
        'seo_title', 'seo_description', 'seo_keywords', 'seo_schema', 'recommendation_tags',
        'dropship_note', 'unpublished_reason'
    )


HOME_SURVEY_VISIBILITY_CACHE_VERSION = "survey-visible-20260530"


def homepage_cache_prefix(request, view_func):
    base_prefix = public_product_listing_cache_prefix(request, view_func)
    return f"{base_prefix}:{HOME_SURVEY_VISIBILITY_CACHE_VERSION}"


# W3-3: @ensure_csrf_cookie снят — Set-Cookie на каждом анонимном GET
# выключал LiteSpeed page cache; csrftoken выдаётся лениво (/api/bootstrap/).
@cache_page_for_anon(
    300,
    key_prefix=homepage_cache_prefix,
)  # Phase 4.1: 5-мин кэш для анонимов; cart/favs-бейджи идут AJAX, не в кэше
def home(request):
    """
    Главная страница сайта.

    Features:
    - Показывает featured товар
    - Список последних товаров с пагинацией
    - Категории товаров
    - Предпросмотр цветовых вариантов
    """
    # SEO 2026-06-04 — Search Console flagged ``/?page=1`` as a duplicate of
    # the homepage root (it renders identical content with canonical → "/").
    # Collapse it with a 301 so Google retires the duplicate URL and
    # consolidates signal on "/". Only ``page=1`` is redirected; ``page>=2``
    # are legitimate paginator states that stay 200.
    if request.GET.get('page') == '1':
        return HttpResponsePermanentRedirect(reverse('home'))

    # Оптимизированные запросы с select_related и prefetch_related
    featured = apply_public_product_order(
        _product_cards_queryset().filter(
            featured=True,
            status='published'
        )
    ).first()

    fragment_cache = get_fragment_cache()
    categories = get_categories_cached(fragment_cache)
    public_product_order_version = get_public_product_order_version()
    public_category_version = get_public_category_version()

    # Пагинация
    page_number = request.GET.get('page', '1')
    product_qs = apply_public_product_order(
        _product_cards_queryset().filter(status='published')
    )
    paginator = Paginator(product_qs, HOME_PRODUCTS_PER_PAGE)

    try:
        page_obj = paginator.get_page(page_number)
    except EmptyPage:
        page_obj = paginator.get_page(paginator.num_pages)

    products = list(page_obj.object_list)

    # Подготавливаем цветовые превью
    preview_products = list(products)
    if featured:
        preview_products.append(featured)

    color_previews = build_color_preview_map(preview_products)
    featured_variants = color_previews.get(featured.id, []) if featured else []

    for product in products:
        colors_preview = color_previews.get(product.id, [])
        setattr(product, 'colors_preview', colors_preview)
        setattr(product, 'colors_preview_key', build_color_preview_key(colors_preview))

    # Проверяем есть ли еще товары для пагинации
    total_products = paginator.count
    has_more = page_obj.has_next()
    homepage_pagination_items = build_homepage_pagination_items(
        current_page=page_obj.number,
        total_pages=paginator.num_pages,
        base_path=reverse("home"),
    )

    survey_def = load_survey_definition()
    survey_ui_home = survey_def.get('ui_copy', {}).get('homepage_block', {}) if survey_def else {}
    survey_ui_modal = survey_def.get('ui_copy', {}).get('modal', {}) if survey_def else {}
    survey_reward = survey_def.get('reward', {}) if survey_def else {}
    survey_key = survey_def.get('survey_key', 'print_feedback_v1') if survey_def else 'print_feedback_v1'
    survey_has_active = False
    survey_block_hidden = False
    if request.user.is_authenticated and survey_def:
        survey_has_active = SurveySession.objects.filter(
            user=request.user,
            survey_key=survey_key,
            status='in_progress',
        ).exists()
        # Hide the homepage survey block for signed-in users who already
        # finished it (completed session) or already hold the reward
        # (UserPromoCode). For anonymous visitors the page is cached for
        # everyone, so their visibility is handled client-side in survey.js
        # via localStorage instead.
        already_completed = SurveySession.objects.filter(
            user=request.user,
            survey_key=survey_key,
            status='completed',
        ).exists()
        already_granted = UserPromoCode.objects.filter(
            user=request.user,
            survey_key=survey_key,
        ).exists()
        already_dismissed = UserAction.objects.filter(
            user=request.user,
            action_type='survey_dismiss',
        ).exists()
        survey_block_hidden = already_completed or already_granted or already_dismissed
    survey_cta_text = survey_ui_home.get(
        'cta_continue_uk' if survey_has_active else 'cta_start_uk',
        'Пройти опитування',
    )

    # ``expires_in_days`` drives the client-side "show again after the promo
    # expired" rule for anonymous visitors (see survey.js).
    survey_expires_in_days = int(survey_reward.get('expires_in_days', 5)) if survey_reward else 5

    # Phase 9 — colour chips near the categories block. Each chip
    # links to ``/catalog/?color=<slug>``; no filter is applied to
    # the homepage itself.
    home_color_chips = build_home_color_chips(
        apply_public_product_order(
            _product_cards_queryset().filter(status='published')
        ),
        reverse('catalog'),
    )

    return render(
        request,
        'pages/index.html',
        {
            'featured': featured,
            'categories': categories,
            'products': products,
            'featured_variants': featured_variants,
            'has_more_products': has_more,
            'current_page': page_obj.number,
            'paginator': paginator,
            'page_obj': page_obj,
            'homepage_pagination_items': homepage_pagination_items,
            'total_products': total_products,
            'survey_ui_home': survey_ui_home,
            'survey_ui_modal': survey_ui_modal,
            'survey_reward': survey_reward,
            'survey_key': survey_key,
            'survey_cta_text': survey_cta_text,
            'survey_has_active': survey_has_active,
            'survey_block_hidden': survey_block_hidden,
            'survey_expires_in_days': survey_expires_in_days,
            'public_product_order_version': public_product_order_version,
            'public_category_version': public_category_version,
            'home_color_chips': home_color_chips,
        }
    )


def load_more_products(request):
    """
    AJAX view для загрузки дополнительных товаров.

    Используется для бесконечной прокрутки на главной странице.

    Returns:
        JsonResponse: HTML фрагмент с товарами + метаданные пагинации
    """
    if request.method == 'GET':
        page = request.GET.get('page', 1)
        per_page = HOME_PRODUCTS_PER_PAGE

        product_qs = apply_public_product_order(
            _product_cards_queryset().filter(status='published')
        )
        paginator = Paginator(product_qs, per_page)

        page_obj = paginator.get_page(page)

        products = list(page_obj.object_list)

        # Подготавливаем цвета для товаров
        color_previews = build_color_preview_map(products)
        for product in products:
            product.colors_preview = color_previews.get(product.id, [])
            product.colors_preview_key = build_color_preview_key(product.colors_preview)

        # Проверяем есть ли еще товары
        total_products = paginator.count
        has_more = page_obj.has_next()
        homepage_pagination_items = build_homepage_pagination_items(
            current_page=page_obj.number,
            total_pages=paginator.num_pages,
            base_path=reverse("home"),
        )

        # Рендерим HTML для товаров
        products_html = render_to_string('partials/products_list.html', {
            'products': products,
            'page': page_obj.number
        })
        pagination_html = render_to_string(
            'partials/home_pagination.html',
            {
                'homepage_pagination_items': homepage_pagination_items,
                'page_obj': page_obj,
                'paginator': paginator,
                'homepage_pagination_base_path': reverse("home"),
            },
            request=request,
        )

        return JsonResponse({
            'html': products_html,
            'has_more': has_more,
            'next_page': page_obj.next_page_number() if has_more else None,
            'total_pages': paginator.num_pages,
            'current_page': page_obj.number,
            'pagination_html': pagination_html,
            'total_products': total_products,
        })

    return JsonResponse({'error': 'Invalid request'}, status=400)


# W3-3: @ensure_csrf_cookie снят (см. комментарий у home)
@canonical_color_filter
@_catalog_cache_policy
@cache_page_for_anon(
    600,
    key_prefix=_catalog_cache_prefix,
    cache_identity=_build_catalog_cache_query,
    cache_condition=_catalog_cacheable_request,
)  # Кэшируем каталог на 10 минут только для анонимов
def catalog(request, cat_slug=None, collection_slug=None):
    """
    Страница каталога товаров.

    Args:
        cat_slug (str, optional): Slug категории для фильтрации

    Features:
    - Показывает все товары или фильтрует по категории
    - Цветовые варианты товаров
    - Карточки категорий (если не выбрана конкретная категория)
    """
    merch_collection = None
    merch_collection_page = None
    merch_category_slugs = ()
    if collection_slug:
        from product_catalog.models import MerchCollection

        merch_collection = get_object_or_404(
            MerchCollection,
            slug=collection_slug,
            is_active=True,
            indexable=True,
        )
        descendant_slugs = active_collection_descendant_slugs(merch_collection.slug)
        assigned_category_slugs = set(
            Product.objects.filter(
                status='published',
                category__is_active=True,
                merch_collection_assignments__collection__slug__in=descendant_slugs,
                merch_collection_assignments__collection__is_active=True,
            ).values_list('category__slug', flat=True)
        )
        merch_category_slugs = tuple(
            slug for slug in SMART_SELECTOR_CATEGORY_SLUGS
            if slug in assigned_category_slugs
        )
        cat_slug = merch_category_slugs[0] if merch_category_slugs else 'tshirts'
        merch_collection_page = _build_merch_collection_page(merch_collection)

    fragment_cache = get_fragment_cache()
    categories = get_categories_cached(fragment_cache)
    public_product_order_version = get_public_product_order_version()
    public_category_version = get_public_category_version()
    smart_selector_fit_codes = None
    smart_selector_selected_theme = ''
    smart_selector_selected_fit = ''
    smart_selector_selected_sort = 'recommended'
    smart_selector_facet_state = {}
    smart_selector_merchandising = None
    selected_color_slugs = parse_color_filter(request)
    root_catalog_selected_categories = ()
    root_catalog_facet_state = {}
    root_catalog_selected_sort = 'recommended'
    root_catalog_filter_active_count = 0

    if cat_slug:
        category = get_object_or_404(Category, slug=cat_slug, is_active=True)
        is_smart_selector_category = category.slug in SMART_SELECTOR_CATEGORY_SLUGS
        product_scope = {
            'category__slug__in': merch_category_slugs,
            'category__is_active': True,
        } if merch_category_slugs else {'category': category}
        base_product_qs = apply_public_product_order(
            _product_cards_queryset(
                include_fit_options=is_smart_selector_category,
                include_merchandising=is_smart_selector_category,
            ).filter(status='published', **product_scope)
        )
        show_category_cards = False
    else:
        category = None
        root_catalog_selected_categories = _root_catalog_selected_categories(request)
        base_product_qs = apply_public_product_order(
            _product_cards_queryset().filter(status='published')
        )
        if root_catalog_selected_categories:
            base_product_qs = base_product_qs.filter(
                category__slug__in=root_catalog_selected_categories,
                category__is_active=True,
            )
        show_category_cards = True

    _validate_catalog_facet_query(request, category=category)

    if category and category.slug in SMART_SELECTOR_CATEGORY_SLUGS:
        smart_selector_fit_codes = _smart_selector_fit_codes(category, base_product_qs)
        smart_selector_facet_state = _smart_selector_facet_state(
            request,
            category,
            smart_selector_fit_codes,
        )
        if merch_collection is not None:
            selected_collections = set(
                smart_selector_facet_state.get('collection', ())
            )
            selected_collections.add(merch_collection.slug)
            smart_selector_facet_state['collection'] = tuple(
                sorted(selected_collections)
            )
        base_product_qs = filter_products_by_facets(
            base_product_qs,
            smart_selector_facet_state,
        )
        for selected_fit in smart_selector_facet_state.get('fit', ()):
            fit_query = _smart_selector_fit_query(selected_fit)
            if category.slug == 'long-sleeve' and selected_fit == 'standard':
                fit_query |= Q(fit_options__isnull=True)
            base_product_qs = base_product_qs.filter(fit_query).distinct()
        selected_themes = smart_selector_facet_state.get('theme', ())
        selected_fits = smart_selector_facet_state.get('fit', ())
        smart_selector_selected_theme = selected_themes[0] if selected_themes else ''
        smart_selector_selected_fit = selected_fits[0] if selected_fits else ''
        smart_selector_merchandising = _smart_selector_merchandising_contract(
            smart_selector_facet_state
        )
        smart_selector_selected_sort = _smart_selector_sort_state(request)
        base_product_qs = _apply_smart_selector_sort(
            base_product_qs,
            smart_selector_selected_sort,
        )

    # Phase 9 — colour filter (?color=black,red). Build chips from the
    # *unfiltered* queryset so users can always OR-in another colour.
    # Smart Selector owns the concrete category experience. Keep its colour
    # chips on the same query-string route so theme/fit state and the bottom
    # sheet remain available; dedicated SEO colour landings keep serving
    # direct organic links but are not used as an in-page navigation jump.
    color_landing_category = (
        None
        if category and category.slug in SMART_SELECTOR_CATEGORY_SLUGS
        else category
    )
    available_colors = build_available_colors(
        base_product_qs, request, selected_color_slugs, category=color_landing_category,
    )
    if category is None:
        allowed_root_colors = {
            str(option.get('slug') or '').strip().lower()
            for option in available_colors
            if option.get('slug')
        }
        # ``parse_color_filter`` still accepts the legacy comma-separated
        # form (``?color=black,red``). Feed its canonical values back as
        # repeated keys so the aggregate facet normalizer preserves both
        # legacy links and the new checkbox form.
        root_facet_query = request.GET.copy()
        root_facet_query.setlist('color', selected_color_slugs)
        normalized_root_state = normalize_catalog_facet_state(
            root_facet_query,
            allowed_colors=allowed_root_colors,
        )
        root_catalog_facet_state = {
            key: tuple(values)
            for key, values in normalized_root_state.items()
            if key in {'availability', 'size', 'color'}
        }
        selected_color_slugs = list(root_catalog_facet_state.get('color', ()))
        root_catalog_selected_sort = _root_catalog_sort_state(request)
        product_qs = filter_products_by_facets(
            base_product_qs,
            root_catalog_facet_state,
        )
        product_qs = _apply_root_catalog_sort(
            product_qs,
            root_catalog_selected_sort,
        )
        root_catalog_filter_active_count = (
            len(root_catalog_selected_categories)
            + sum(len(values) for values in root_catalog_facet_state.values())
            + int(root_catalog_selected_sort != 'recommended')
        )
        if root_catalog_filter_active_count:
            show_category_cards = False
    elif category.slug in SMART_SELECTOR_CATEGORY_SLUGS:
        if selected_color_slugs:
            smart_selector_facet_state["color"] = tuple(selected_color_slugs)
            product_qs = filter_products_by_facets(
                base_product_qs,
                {"color": tuple(selected_color_slugs)},
            )
        else:
            product_qs = base_product_qs
    else:
        product_qs = apply_color_filter(base_product_qs, selected_color_slugs)
    has_active_color_filter = bool(selected_color_slugs)
    color_filter_reset_url = build_reset_url(request) if has_active_color_filter else ''
    suppress_hreflang = bool(
        has_active_color_filter
        or root_catalog_filter_active_count
        or any(
            request.GET.get(key)
            for key in (
                'sort', 'theme', 'collection', 'audience', 'availability',
                'fit', 'size', 'thermo',
            )
        )
    )
    if category and category.slug in SMART_SELECTOR_CATEGORY_SLUGS:
        product_qs = _sort_smart_selector_products_by_visible_price(
            product_qs,
            smart_selector_selected_sort,
        )

    # When a colour filter is active on the catalog root we hide the
    # category showcase cards and surface the matching products list
    # instead — otherwise the user would see no products at all.
    if has_active_color_filter:
        show_category_cards = False

    # Pagination
    paginator, page_obj = _paginate_catalog_queryset(product_qs, request)

    products = list(page_obj.object_list)
    color_previews = build_color_preview_map(products)

    for product in products:
        colors_preview = color_previews.get(product.id, [])
        product.colors_preview = colors_preview
        product.colors_preview_key = build_color_preview_key(colors_preview)

    # Phase 14 — color-filter-aware preview: when ``?color=...`` is set,
    # show the matching variant's image on each card (instead of the
    # default ``homepage_image``).
    enrich_color_preview_with_slugs(products)
    attach_preferred_card_image(products, selected_color_slugs)
    smart_selector_context = _build_smart_selector_context(
        request,
        category,
        categories,
        products,
        base_product_qs,
        fit_codes=smart_selector_fit_codes,
        selected_sort=smart_selector_selected_sort,
        facet_state=smart_selector_facet_state,
        merchandising=smart_selector_merchandising,
    )
    catalog_showcase_cards = (
        _build_catalog_showcase_cards(categories) if show_category_cards else []
    )
    catalog_mobile_showcase_cards = sorted(
        catalog_showcase_cards,
        key=lambda card: card.get('mobile_order', 99),
    )

    return render(
        request,
        'pages/catalog.html',
        {
            'categories': categories,
            'category': category,
            'products': products,
            'show_category_cards': show_category_cards,
            'catalog_showcase_cards': catalog_showcase_cards,
            'catalog_mobile_showcase_cards': catalog_mobile_showcase_cards,
            'cat_slug': cat_slug or '',
            'page_obj': page_obj,
            'paginator': paginator,
            'public_product_order_version': public_product_order_version,
            'public_category_version': public_category_version,
            'catalog_fragment_identity': getattr(
                request,
                '_catalog_fragment_identity',
                request.get_full_path(),
            ),
            'available_colors': available_colors,
            'selected_color_slugs': selected_color_slugs,
            'has_active_color_filter': has_active_color_filter,
            'color_filter_reset_url': color_filter_reset_url,
            'root_catalog_selected_categories': root_catalog_selected_categories,
            'root_catalog_facet_state': root_catalog_facet_state,
            'root_catalog_selected_color_slugs': root_catalog_facet_state.get('color', ()),
            'root_catalog_selected_sizes': root_catalog_facet_state.get('size', ()),
            'root_catalog_selected_availability': root_catalog_facet_state.get('availability', ()),
            'root_catalog_selected_sort': root_catalog_selected_sort,
            'root_catalog_filter_active_count': root_catalog_filter_active_count,
            'root_catalog_filters_active': bool(root_catalog_filter_active_count),
            'suppress_hreflang': suppress_hreflang,
            'root_catalog_size_options': SELLABLE_SIZE_ORDER,
            'root_catalog_category_options': [
                {
                    'slug': slug,
                    'label': next(
                        (item.name for item in categories if item.slug == slug),
                        ROOT_CATALOG_CATEGORY_LABELS[slug],
                    ),
                    'selected': slug in root_catalog_selected_categories,
                }
                for slug in SMART_SELECTOR_CATEGORY_SLUGS
            ] if category is None else [],
            'merch_collection_page': merch_collection_page,
            'smart_selector_request_has_facets': any(
                key in request.GET
                for key in (
                    'theme', 'collection', 'audience', 'availability', 'fit',
                    'size', 'color', 'thermo', 'sort',
                )
            ),
            'pagination_query_prefix': getattr(
                request,
                '_catalog_pagination_query_prefix',
                _pagination_query_prefix(request),
            ),
            # Phase 10 — structured SEO blocks shown after the products grid.
            'category_seo_blocks': get_category_seo_blocks(category) if category else [],
            # Phase 10b — split layout: tabs (top_menu/top_filters/top_queries/
            # top_cards) vs. best_prices pricing table. Per-category catalogs
            # pull from CategorySeoBlock rows; the general /catalog/ root
            # synthesises an in-memory layout (top_menu = all categories,
            # top_filters = available colours, top_queries = curated set)
            # so the same partial renders on every catalog screen.
            'category_seo_layout': (
                get_category_seo_layout(category) if category
                else get_general_catalog_seo_layout(
                    categories=categories,
                    available_colors=available_colors,
                )
            ),
            # Phase 19g — colour-aware SEO copy. Renders on /catalog/ root
            # (brand-level landing) and on any catalog screen with an
            # active colour filter (cross-category or per-category x
            # colour). Returns None for /catalog/<cat>/ without a colour
            # filter so we don't double-up on the existing
            # ``category.description`` SEO text.
            'color_seo_copy': build_catalog_color_seo(
                category=category,
                selected_color_slugs=selected_color_slugs,
                available_colors=available_colors,
            ),
            **smart_selector_context,
        }
    )


_SEARCH_SYNONYMS = {
    # Latin-keyboard / English / transliterated → UA canonical tokens
    "tshirt":     ["футболк", "тішк", "t-shirt", "tee", "ts"],
    "t-shirt":    ["футболк", "тішк", "tee", "ts"],
    "tee":        ["футболк", "тішк"],
    "hoodie":     ["худі", "hoody", "hd"],
    "hoody":      ["худі", "hoodie", "hd"],
    "longsleeve": ["лонгслів", "long-sleeve", "ls"],
    "long-sleeve": ["лонгслів", "longsleeve", "ls"],
    "sweatshirt": ["світшот", "светшот", "пуловер"],
    "twocomms":   ["twocomms", "ту комс", "ту-комс", "тукомс", "twcomms"],
    "streetwear": ["стрітвеар", "стрітвір", "стрит", "streetwear"],
    "military":   ["мілітарі", "військов"],
    # Generic transliteration shortcuts users type after Cyrillic auto-
    # complete fails (e.g. iOS QWERTY → typed «futbolka»).
    "futbolka":   ["футболк"],
    "khudi":      ["худі"],
    "longsliv":   ["лонгслів"],
}


def _build_search_tokens(query: str) -> list[str]:
    """Expand a free-text query into a list of search tokens.

    SEO v1.0 Phase 11 (2026-05-12) — finding (B5). The original search
    only matched the literal query string against UA fields; English
    tokens (tshirt/hoodie/longsleeve/twocomms) returned 0 results.
    Expand each query word against ``_SEARCH_SYNONYMS`` to reach the UA
    catalogue with the same query. Always include the raw query as
    fallback so existing matches still work.
    """
    raw = (query or "").strip()
    if not raw:
        return []
    tokens: list[str] = [raw]
    for word in raw.lower().split():
        synonyms = _SEARCH_SYNONYMS.get(word)
        if synonyms:
            tokens.extend(synonyms)
        # Also try a hyphen-stripped variant (long-sleeve → longsleeve).
        if "-" in word:
            normalized = word.replace("-", "")
            if normalized in _SEARCH_SYNONYMS:
                tokens.extend(_SEARCH_SYNONYMS[normalized])
    # Deduplicate, preserve order.
    seen: set[str] = set()
    deduped: list[str] = []
    for tok in tokens:
        key = tok.strip().lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(tok.strip())
    return deduped


@canonical_color_filter
def search(request):
    """
    Поиск товаров.

    Query params:
        q (str): Поисковый запрос
        category (str, optional): Фильтр по категории

    Features:
    - Поиск по названию и описанию
    - Фильтрация по категории
    - Выделение результатов
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Search function called from catalog.py")

    try:
        query = (request.GET.get('q') or '').strip()
        category_slug = request.GET.get('category', '').strip()

        # Используем тот же подход, что и в рабочей версии из views.py
        product_qs = _product_cards_queryset().filter(status='published')

        if query:
            # SEO v1.0 Phase 11 (2026-05-12) — finding (B5). The previous
            # search only ran ICONTAINS against UA-only text fields, so
            # users with the English keyboard layout (Windows default)
            # who typed «tshirt» / «hoodie» / «longsleeve» / «twocomms»
            # got zero results — even though the catalogue has matching
            # products under «футболка» / «худі» / «лонгслів». That's a
            # textbook 0-results spike in Google Search Console «Site
            # search» queries. Build the lookup over a synonym-expanded
            # token set so the search box behaves like the public-facing
            # brand search the audit assumes.
            tokens = _build_search_tokens(query)
            search_q = Q()
            for token in tokens:
                search_q |= (
                    Q(title__icontains=token)
                    | Q(slug__icontains=token)
                    | Q(description__icontains=token)
                    | Q(full_description__icontains=token)
                    | Q(short_description__icontains=token)
                )
            product_qs = product_qs.filter(search_q)
            record_search(request, query)

        # Фильтрация по категории
        selected_category = None
        if category_slug:
            try:
                selected_category = Category.objects.get(slug=category_slug, is_active=True)
                product_qs = product_qs.filter(category=selected_category)
            except Category.DoesNotExist:
                selected_category = None

        fragment_cache = get_fragment_cache()
        categories = get_categories_cached(fragment_cache)
        public_product_order_version = get_public_product_order_version()
        public_category_version = get_public_category_version()

        # Phase 9 — colour filter on search results.
        base_search_qs = apply_public_product_order(product_qs)
        selected_color_slugs = parse_color_filter(request)
        available_colors = build_available_colors(
            base_search_qs, request, selected_color_slugs,
            category=selected_category,
        )
        has_active_color_filter = bool(selected_color_slugs)
        color_filter_reset_url = build_reset_url(request) if has_active_color_filter else ''
        filtered_search_qs = apply_color_filter(base_search_qs, selected_color_slugs)

        paginator = Paginator(filtered_search_qs, PRODUCTS_PER_PAGE)
        page_obj = paginator.get_page(request.GET.get('page'))
        product_list = list(page_obj.object_list)
        color_previews = build_color_preview_map(product_list)

        for product in product_list:
            colors_preview = color_previews.get(product.id, [])
            product.colors_preview = colors_preview
            product.colors_preview_key = build_color_preview_key(colors_preview)

        # Phase 14 — color-filter-aware preview on search results too.
        enrich_color_preview_with_slugs(product_list)
        attach_preferred_card_image(product_list, selected_color_slugs)

        return render(
            request,
            'pages/catalog.html',
            {
                'categories': categories,
                'products': product_list,
                'show_category_cards': False,
                'selected_category': selected_category,
                'query': query,
                'results_count': paginator.count,
                'is_search_page': True,
                'page_obj': page_obj,
                'paginator': paginator,
                'public_product_order_version': public_product_order_version,
                'public_category_version': public_category_version,
                'catalog_fragment_identity': request.get_full_path(),
                'available_colors': available_colors,
                'selected_color_slugs': selected_color_slugs,
                'has_active_color_filter': has_active_color_filter,
                'color_filter_reset_url': color_filter_reset_url,
                'suppress_hreflang': True,
                'pagination_query_prefix': _pagination_query_prefix(request),
            }
        )
    except Exception as e:
        # Логируем ошибку для отладки
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in search view: {e}", exc_info=True)

        # Возвращаем пустую страницу с ошибкой
        try:
            fragment_cache = get_fragment_cache()
            categories = get_categories_cached(fragment_cache) if fragment_cache else []
            public_product_order_version = get_public_product_order_version()
            public_category_version = get_public_category_version()
        except Exception:
            categories = []
            public_product_order_version = 1
            public_category_version = 1

        return render(
            request,
            'pages/catalog.html',
            {
                'query': request.GET.get('q', ''),
                'products': [],
                'categories': categories,
                'selected_category': None,
                'show_category_cards': False,
                'results_count': 0,
                'is_search_page': True,
                'error': 'Произошла ошибка при поиске. Попробуйте еще раз.',
                'public_product_order_version': public_product_order_version,
                'public_category_version': public_category_version,
                'catalog_fragment_identity': request.get_full_path(),
                'suppress_hreflang': True,
            }
        )



# ==================== COLOR × CATEGORY LANDING ====================

def category_color_landing(request, cat_slug, color_slug):
    """Render an indexable colour×category SEO landing page.

    URL: ``/catalog/<cat_slug>/<color_slug>/`` (e.g. ``/catalog/tshirts/black/``).

    Behaviour:
        * 404 if the landing is not published, the category is inactive,
          the colour slug doesn't match a stored landing, or there are
          zero matching live products (anti-thin-content guard).
        * Renders ``pages/category_color_landing.html`` with the
          editorial copy, a paginated product grid filtered to the
          ``(category, colour)`` slice, FAQ, and structured data.
    """
    landing = (
        CategoryColorLanding.objects
        .select_related("category", "color")
        .filter(
            category__slug=cat_slug,
            color_slug=color_slug,
            is_published=True,
            category__is_active=True,
        )
        .first()
    )
    if landing is None:
        raise Http404("Color-category landing not found.")

    base_qs = (
        _product_cards_queryset()
        .filter(
            category=landing.category,
            status="published",
            color_variants__color=landing.color,
        )
        .distinct()
    )
    product_qs = apply_public_product_order(base_qs)

    if not product_qs.exists():
        # Empty grids would create a thin-content / soft-404 risk — refuse
        # to render the page until inventory is replenished.
        raise Http404("No products available for this colour-category combination.")

    paginator, page_obj = _paginate_catalog_queryset(product_qs, request)

    products = list(page_obj.object_list)
    color_previews = build_color_preview_map(products)
    for product in products:
        colors_preview = color_previews.get(product.id, [])
        product.colors_preview = colors_preview
        product.colors_preview_key = build_color_preview_key(colors_preview)
    enrich_color_preview_with_slugs(products)
    # Pin every card preview to the landing's colour, so the grid reads
    # as a coherent collection at a glance.
    attach_preferred_card_image(products, [landing.color_slug])

    breadcrumb_items = [
        {"name": _("Головна"), "url": "/"},
        {"name": _("Каталог"), "url": reverse("catalog")},
        {
            "name": landing.category.name,
            "url": reverse("catalog_by_cat", kwargs={"cat_slug": landing.category.slug}),
        },
        {"name": landing.display_h1, "url": request.path},
    ]

    # Surface up to 5 sibling colours of the same category, plus up to 3
    # cross-category landings for the same colour. Cheap queries — both
    # use the (category, is_published) and (color, is_published) indexes.
    sibling_landings = list(
        CategoryColorLanding.objects
        .filter(
            category=landing.category,
            is_published=True,
            category__is_active=True,
        )
        .exclude(pk=landing.pk)
        .select_related("color")
        .order_by("order", "color_slug")[:5]
    )
    cross_category_landings = list(
        CategoryColorLanding.objects
        .filter(
            color=landing.color,
            is_published=True,
            category__is_active=True,
        )
        .exclude(pk=landing.pk)
        .select_related("category")
        .order_by("category__order", "order")[:3]
    )

    canonical_path = request.path
    if page_obj.number > 1:
        canonical_path = f"{canonical_path}?page={page_obj.number}"
    site_base = request.build_absolute_uri("/").rstrip("/")
    canonical_url = f"{site_base}{canonical_path}"

    return render(
        request,
        "pages/category_color_landing.html",
        {
            "landing": landing,
            "category": landing.category,
            "color": landing.color,
            "products": products,
            "page_obj": page_obj,
            "paginator": paginator,
            "breadcrumb_items": breadcrumb_items,
            "canonical_url": canonical_url,
            "canonical_path": canonical_path,
            "faq_items": landing.faq_items or [],
            "sibling_landings": sibling_landings,
            "cross_category_landings": cross_category_landings,
        },
    )


# ==================== THEMATIC LANDINGS (US-5) ====================
#
# Lightweight thematic SEO landings — `/catalog/theme/<theme_slug>/`.
# No new model, no migration: products are filtered by slug / title /
# topic_keywords keywords using the same topic-detection logic that
# powers ``storefront.services.product_seo_block`` (US-3).
#
# Four indexable themes ship out of the box:
#   * military       → military / тактичний / 225 / штурмовий
#   * streetwear     → streetwear / стріт / urban
#   * patriotic      → glory of ukraine / patriotic / ЗСУ / 225
#   * kharkiv-edition → kharkiv / kha-style / харків / pokrovsk
#
# Each landing reuses the existing /catalog/ template stack but
# injects a custom ``thematic_landing`` context with editorial copy and
# a curated breadcrumb so the page is unique enough to index without a
# new template/landing model.

THEMATIC_LANDINGS_CONFIG = {
    "military": {
        "h1": "Військовий стрітвір TwoComms — мілітарі-одяг із харківським кодом",
        "title": "Купити мілітарі футболки, худі та лонгсліви — TwoComms",
        "description": (
            "Військовий streetwear від ветеранського бренду TwoComms: футболки, "
            "худі і лонгсліви з мілітарі-кодом, авторськими принтами 225-го ОШП "
            "і Pokrovsk Girl. Виробництво в Харкові."
        ),
        "intro": (
            "Військова естетика TwoComms — це не косплей і не агітка. Це "
            "щоденний одяг для людей, які тримають форму зсередини: бойових "
            "ветеранів, активних резервістів, цивільних, які знають контекст. "
            "Принти серії 225-го ОШП, харківські відсилки, патріотичні мотиви "
            "без галасу. Виробництво у Харкові, контроль якості у одному цеху, "
            "тираж не масштабується заради знижок."
        ),
        "keywords": (
            "мілітарі, military, тактичний, 225, штурмовий, ошп, kharkiv, "
            "pokrovsk, glory-of-ukraine, war, soldier, "
            "патріотичний, патриотический"
        ),
        "match_keywords": [
            "military", "мілітар", "милитар", "tactical", "тактич", "225",
            "ошп", "штурм", "war", "soldier", "armed", "warrior", "warfare",
        ],
    },
    "streetwear": {
        "h1": "Стрітвір TwoComms — авторський streetwear із Харкова",
        "title": "Купити streetwear футболки, худі, лонгсліви — TwoComms",
        "description": (
            "Streetwear від TwoComms: футболки, худі та лонгсліви з авторським "
            "DTF-друком, oversize-кроєм, харківським ДНК. Streetwear як код, не "
            "декорація. Доставка по Україні."
        ),
        "intro": (
            "Streetwear-крило TwoComms — це чистий міський код без військових "
            "цитат і політичних маркерів. Авторські принти, акуратні графіки, "
            "сильні шрифти, продумана посадка. Streetwear як шифр, який "
            "зчитують ті, хто розуміє контекст. Тут немає випадкових "
            "колаборацій з невідомими виробниками: усе шиється у Харкові, "
            "перевіряється у одному цеху, пакується вручну."
        ),
        "keywords": (
            "стрітвір, streetwear, urban, street, культовий одяг, авторський "
            "принт, oversize, харківський streetwear"
        ),
        "match_keywords": [
            "street", "стрит", "стріт", "urban", "skate", "punk", "graff",
            "reality-bends", "future", "business",
        ],
    },
    "patriotic": {
        "h1": "Патріотичний одяг TwoComms — український streetwear із характером",
        "title": "Патріотичні футболки і худі з принтом ЗСУ — TwoComms",
        "description": (
            "Патріотичний одяг TwoComms: футболки, худі та лонгсліви з "
            "принтами Glory of Ukraine, ЗСУ, харківської серії. Без галасу, "
            "без фейку — реальна підтримка ветеранських проєктів."
        ),
        "intro": (
            "Патріотична лінія TwoComms — це спокійна українська ідентичність "
            "без агітки. Ми не пишемо «слава Україні» гігантськими літерами — "
            "ми вкладаємо знак у графіку, яку зчитують свої. Принти серії "
            "Glory of Ukraine, харківські відсилки, мотиви, повʼязані з "
            "225-м ОШП. Частина прибутку — на підтримку ветеранських "
            "ініціатив через Український ветеранський фонд."
        ),
        "keywords": (
            "патріотичний одяг, glory of ukraine, патриотический, ЗСУ, "
            "слава україні, kharkiv edition"
        ),
        "match_keywords": [
            "glory", "ukraine", "україн", "украин", "патріот", "патриот",
            "kha", "harkiv", "харків", "харьков", "pokrovsk", "покров",
        ],
    },
    "kharkiv-edition": {
        "h1": "Харківський одяг TwoComms — Kharkiv Edition streetwear",
        "title": "Купити одяг із принтом «Харків» — TwoComms Kharkiv Edition",
        "description": (
            "Колекція Kharkiv Edition від TwoComms: футболки, худі та "
            "лонгсліви з харківськими принтами, Pokrovsk Girl, Kha Style. "
            "Виробництво у Харкові."
        ),
        "intro": (
            "Kharkiv Edition — це харківський бренд про харківську оптику. "
            "TwoComms виріс у місті, де зараз і щодня тестується. У серії — "
            "принти, які працюють як знаки для тих, хто розуміє контекст: "
            "Pokrovsk Girl, Kha Style, харківська обласна графіка. Це не "
            "туристичний мерч і не патріотична агітка, а щоденний код міста."
        ),
        "keywords": (
            "харківський одяг, kharkiv edition, харків стрітвір, "
            "kha-style, pokrovsk girl"
        ),
        "match_keywords": [
            "kharkiv", "kha-", "харків", "харьков", "pokrovsk", "покров",
            "district",
        ],
    },
}


@canonical_color_filter
@cache_page_for_anon(600, key_prefix=public_product_listing_cache_prefix)
def thematic_landing(request, theme_slug):
    """Render an indexable thematic SEO landing.

    URL: ``/catalog/theme/<theme_slug>/``.

    Filters published products by slug / title keyword match against
    ``THEMATIC_LANDINGS_CONFIG[theme]["match_keywords"]``. The landing
    reuses the existing catalog template but injects a thematic intro
    + curated breadcrumb so the URL stays unique-enough to index.
    """
    config = THEMATIC_LANDINGS_CONFIG.get(theme_slug)
    if not config:
        raise Http404("Unknown theme")

    fragment_cache = get_fragment_cache()
    categories = get_categories_cached(fragment_cache)
    public_product_order_version = get_public_product_order_version()
    public_category_version = get_public_category_version()

    # Build keyword-OR filter from match_keywords.
    keyword_q = Q()
    for keyword in config["match_keywords"]:
        keyword_q |= Q(slug__icontains=keyword) | Q(title__icontains=keyword)
    base_qs = apply_public_product_order(
        _product_cards_queryset().filter(status="published").filter(keyword_q)
    )

    # Fall back to all products if the theme matches nothing — surface
    # at least the catalogue rather than a 404, and never show an empty
    # SEO landing (would be flagged as soft-404 by Google).
    if not base_qs.exists():
        base_qs = apply_public_product_order(
            _product_cards_queryset().filter(status="published")
        )

    # Phase 9 colour filter still works on top of the theme.
    selected_color_slugs = parse_color_filter(request)
    available_colors = build_available_colors(
        base_qs, request, selected_color_slugs, category=None
    )
    has_active_color_filter = bool(selected_color_slugs)
    color_filter_reset_url = build_reset_url(request) if has_active_color_filter else ''
    product_qs = apply_color_filter(base_qs, selected_color_slugs)

    paginator, page_obj = _paginate_catalog_queryset(product_qs, request)

    products = list(page_obj.object_list)
    color_previews = build_color_preview_map(products)
    for product in products:
        colors_preview = color_previews.get(product.id, [])
        product.colors_preview = colors_preview
        product.colors_preview_key = build_color_preview_key(colors_preview)
    enrich_color_preview_with_slugs(products)
    attach_preferred_card_image(products, selected_color_slugs)

    canonical_path = f"/catalog/theme/{theme_slug}/"
    canonical_url = (
        request.build_absolute_uri(canonical_path)
        .split('?', 1)[0]
        .rstrip('/') + '/'
    )

    return render(
        request,
        'pages/catalog.html',
        {
            'categories': categories,
            'category': None,
            'thematic_landing': {
                'slug': theme_slug,
                'h1': config["h1"],
                'title': config["title"],
                'description': config["description"],
                'intro': config["intro"],
                'keywords': config["keywords"],
            },
            'products': products,
            'show_category_cards': False,
            'catalog_showcase_cards': [],
            'cat_slug': '',
            'page_obj': page_obj,
            'paginator': paginator,
            'public_product_order_version': public_product_order_version,
            'public_category_version': public_category_version,
            'catalog_fragment_identity': request.get_full_path(),
            'available_colors': available_colors,
            'selected_color_slugs': selected_color_slugs,
            'has_active_color_filter': has_active_color_filter,
            'color_filter_reset_url': color_filter_reset_url,
            'category_seo_blocks': [],
            'category_seo_layout': None,
            'color_seo_copy': None,
            'thematic_canonical_url': canonical_url,
            'thematic_canonical_path': canonical_path,
            'breadcrumb_items': [
                {'name': 'Головна', 'url': '/'},
                {'name': 'Каталог', 'url': '/catalog/'},
                {'name': config["h1"], 'url': canonical_path},
            ],
        }
    )
