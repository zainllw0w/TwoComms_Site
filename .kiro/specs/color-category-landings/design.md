# Color-Category Landing Pages — Design

**Date:** 2026-05-15  
**Spec:** color-category-landings  
**Status:** draft

## Architecture overview

```
            HTTP request
                 │
                 ▼
       /catalog/<cat>/<color>/
                 │
                 ▼
    storefront.urls.catalog_by_cat_color
                 │
                 ▼
   storefront.views.catalog.category_color_landing
                 │
   ┌─────────────┴─────────────┐
   │                           │
   ▼                           ▼
CategoryColorLanding       Product queryset
  (if published)            (filtered by cat+color)
   │                           │
   └─────────────┬─────────────┘
                 ▼
       Render category_color_landing.html
                 │
                 ▼
      schema.org @graph + product grid
```

## Data model

### `CategoryColorLanding`

```python
class CategoryColorLanding(models.Model):
    """SEO landing page combining a category with a colour."""

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="color_landings",
        verbose_name="Категорія",
    )
    color = models.ForeignKey(
        "productcolors.Color",
        on_delete=models.CASCADE,
        related_name="category_landings",
        verbose_name="Колір",
    )
    color_slug = models.SlugField(
        max_length=64,
        verbose_name="URL slug кольору",
        help_text=(
            "Англійський slug кольору (наприклад 'black' або "
            "'navy-blue'). Заповнюється автоматично з імені кольору."
        ),
    )

    # SEO meta
    seo_title = models.CharField(max_length=180, verbose_name="SEO Title")
    seo_h1 = models.CharField(max_length=180, blank=True, verbose_name="SEO H1")
    seo_description = models.CharField(max_length=320, verbose_name="SEO Description")

    # Content
    editorial_html = models.TextField(
        verbose_name="Editorial copy (HTML)",
        help_text="≥800 символів (мінімум для публікації).",
    )
    faq_items = models.JSONField(
        blank=True, default=list,
        verbose_name="FAQ Q/A пари",
        help_text="Список словників: [{'question': '...', 'answer': '...'}, ...]",
    )

    # Publishing
    is_published = models.BooleanField(default=False, verbose_name="Опубліковано")
    order = models.PositiveIntegerField(default=0)

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Color-category landing"
        verbose_name_plural = "Color-category landings"
        ordering = ["category__order", "order", "color_slug"]
        unique_together = (("category", "color_slug"),)
        indexes = [
            models.Index(fields=["is_published"], name="idx_cclanding_published"),
            models.Index(fields=["category", "is_published"], name="idx_cclanding_cat_pub"),
        ]
```

### Anti-thin guard

In `clean()`:

```python
def clean(self):
    super().clean()
    if self.is_published and len(self.editorial_html or "") < 800:
        raise ValidationError({
            "editorial_html":
                "Для публікації потрібно мінімум 800 символів editorial copy."
        })
```

### Auto-derive `color_slug`

In `save()`:

```python
def save(self, *args, **kwargs):
    if not self.color_slug and self.color_id:
        from productcolors.color_slug_map import english_slug_for_color_name
        derived = english_slug_for_color_name(self.color.name) if self.color.name else ""
        if not derived:
            derived = build_slug(self.color.name or "", fallback=self.color.primary_hex.lstrip("#"))
        self.color_slug = derived
    super().save(*args, **kwargs)
```

## URL routing

In `storefront/urls.py`:

```python
path(
    "catalog/<slug:cat_slug>/<slug:color_slug>/",
    views.category_color_landing,
    name="catalog_by_cat_color",
),
```

Order: must be **after** `catalog/<slug:cat_slug>/` — Django's path matcher is greedy on each segment, so `/catalog/tshirts/black/` requires the two-segment pattern. There's no risk of collision with `catalog/<slug:cat_slug>/`.

## View

```python
def category_color_landing(request, cat_slug, color_slug):
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
        raise Http404

    # Anti-thin: zero matching products → 404 (not soft fallback).
    products_qs = (
        _product_cards_queryset()
        .filter(category=landing.category, status="published",
                color_variants__color=landing.color)
        .distinct()
    )
    if not products_qs.exists():
        raise Http404

    products = list(apply_public_product_order(products_qs))
    paginator = Paginator(products, PRODUCTS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))

    breadcrumb_items = [
        {"name": "Головна", "url": "/"},
        {"name": "Каталог", "url": reverse("catalog")},
        {"name": landing.category.name,
         "url": reverse("catalog_by_cat", kwargs={"cat_slug": landing.category.slug})},
        {"name": landing.seo_h1 or landing.seo_title,
         "url": request.path},
    ]

    return render(request, "pages/category_color_landing.html", {
        "landing": landing,
        "category": landing.category,
        "color": landing.color,
        "products": products,
        "page_obj": page_obj,
        "paginator": paginator,
        "breadcrumb_items": breadcrumb_items,
        "canonical_url": absolute_url(request.path),
        "faq_items": landing.faq_items,
    })
```

## Template

`pages/category_color_landing.html` extends `base.html`. Key blocks:

- `{% block title %}{{ landing.seo_title }}{% endblock %}`
- `{% block description %}{{ landing.seo_description }}{% endblock %}`
- `{% block canonical %}{{ canonical_url }}{% endblock %}`
- `{% block hreflang_uk %}{{ canonical_url }}{% endblock %}`
- `{% block og_title %}{{ landing.seo_title }}{% endblock %}`
- `{% block structured_data %}` — `@graph` with `BreadcrumbList`, `CollectionPage`, `FAQPage`.
- Body order:
  1. Breadcrumbs (visible).
  2. `<h1>` (uses `seo_h1` with `seo_title` fallback).
  3. Editorial paragraph (`{{ landing.editorial_html | safe }}`).
  4. Product grid (re-uses `partials/product_card.html`).
  5. FAQ block (visible details/summary, FAQPage schema mirrored).
  6. Internal-links footer:
     - "Інші кольори у категорії" → up to 5 sibling colour landings.
     - "Цей колір в інших категоріях" → up to 3 cross-category landings.
     - "Усі {category}" → `/catalog/<cat_slug>/`.

## Sitemap

New `CategoryColorLandingSitemap` in `storefront/sitemaps.py`:

```python
class CategoryColorLandingSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return (
            CategoryColorLanding.objects
            .filter(is_published=True, category__is_active=True)
            .select_related("category", "color")
        )

    def location(self, obj):
        return f"/catalog/{obj.category.slug}/{obj.color_slug}/"

    def lastmod(self, obj):
        return obj.updated_at
```

Add `/sitemap-color-categories.xml` view + register in sitemap-index.

## Internal linking

Update `available_colors` chip generator on `/catalog/<cat_slug>/`:

- Resolve published landing slugs for category once per render: `set(CategoryColorLanding.objects.filter(category=category, is_published=True).values_list("color_slug", flat=True))`
- For each chip, compare `chip.slug` with the published set. If matched, set `chip.url = /catalog/<cat_slug>/<chip.slug>/`. Otherwise, retain `?color=<slug>`.

This keeps the existing `?color=` filter working for unpublished colours **and** redirects organic traffic to the dedicated landing once it is live.

## IndexNow integration

Signal in `storefront/signals.py`:

```python
@receiver(post_save, sender=CategoryColorLanding)
def enqueue_indexnow_for_color_landing(sender, instance, **kwargs):
    if instance.is_published:
        url = f"/catalog/{instance.category.slug}/{instance.color_slug}/"
        enqueue_indexnow_urls([url])
```

## Tests

- `test_color_category_landing_model.py` — model anti-thin guard, default unpublished, color_slug auto-derive, unique_together.
- `test_color_category_landing_view.py` — 200 happy path, 404 unpublished, 404 zero products, canonical, breadcrumbs, hreflang, structured-data presence.
- `test_color_category_landing_sitemap.py` — sitemap section returns published only, lastmod, location format.
- `test_color_category_chips.py` — chips link to landing for published, fall back to `?color=` for unpublished.

## Migration plan

1. **Migration A — model + admin:** create the table, expose admin. `is_published=False` default. Safe to deploy alone (zero traffic impact).
2. **Migration B — seed data:** insert 9 unpublished landings with editorial copy already drafted (`tshirts × {black, white, khaki}`, `hoodie × {black, khaki, grey}`, `long-sleeve × {black, white, navy}`). Content team reviews in admin and toggles `is_published=True` per-row.
3. **Code release — routing/template/sitemap/signals.** Until any landing is published, the URL pattern returns 404, so this is also safe.
4. **Content release** — content team flips landings live one at a time. Each flip ships an IndexNow ping.

## Rollback

- If a landing causes ranking issues: `is_published=False` from admin → page returns 404, sitemap drops the entry on next render. No code rollback needed.
- If the entire feature needs to disappear: revert the URL pattern + the migration. Clean and self-contained.
