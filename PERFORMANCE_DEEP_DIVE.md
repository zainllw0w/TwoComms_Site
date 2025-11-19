# Performance Deep Dive Analysis

## 1. Database Query Analysis (N+1 Problems)

### A. Cart View (`storefront/views/cart.py`)
**Status:** 🔴 CRITICAL
**Analysis:**
The `view_cart` function iterates over session cart items and performs a `Product.objects.get(id=product_id)` for *each* item inside the loop.
```python
# Current Implementation (cart.py)
for item_key, item_data in cart.items():
    product = Product.objects.select_related('category').get(id=product_id) # ❌ N+1 Query
```
**Impact:**
For a cart with 10 items, this results in 10 separate DB queries.
**Recommendation:**
Fetch all products in a single query using `Product.objects.in_bulk(ids)`.

### B. Catalog View (`storefront/views/catalog.py`)
**Status:** 🟡 HIGH
**Analysis:**
The `home` and `catalog` views use `build_color_preview_map`. While `build_color_preview_map` attempts to optimize by fetching variants in bulk, the `Product` model's `display_image` property (used in templates) might trigger additional queries if not carefully prefetched.
**Verification:**
`catalog.py` uses `prefetch_related('images', 'color_variants__images')` in `search` but `home` only uses `select_related('category')`.
**Recommendation:**
Ensure `prefetch_related('images', 'color_variants__images')` is used consistently in `home` and `catalog` views.

## 2. Asset Delivery & Size (Production Verified)

### A. CSS Bundle Size
**Status:** 🔴 CRITICAL
**Verification:**
Verified on production server (`195.191.24.169`):
- `styles.min.css`: **478KB** (Gzipped size will be smaller, but parse time is high).
- `styles.css`: **474KB** (Unminified).
**Observation:**
The "minified" file is larger than the unminified one, or they are effectively the same. This suggests minification is NOT working correctly or the source CSS is extremely bloated.
**Recommendation:**
- Audit `styles.css` for unused CSS (PurgeCSS).
- Ensure `django-compressor` is actually minifying.

### B. Font Loading
**Status:** 🟡 HIGH
**Observation:**
`static/fonts` directory is empty locally. Fonts are likely loaded via CDN (Google Fonts) or hardcoded in CSS.
**Risk:**
Blocking render (FOIT) if fonts are loaded synchronously from external domains.
**Recommendation:**
- Self-host fonts in `static/fonts`.
- Use `font-display: swap`.

## 3. Caching Strategy

### A. Fragment Caching
**Status:** 🟢 GOOD (with caveats)
**Analysis:**
`catalog.html` uses `{% cache 1800 catalog_categories %}` and `{% cache 900 product_card ... %}`.
This is a good practice.
**Risk:**
If `COMPRESS_ENABLED` is False or static files change, cached fragments might contain outdated static URLs if not invalidated correctly.

### B. View Caching
**Status:** 🟡 MEDIUM
**Analysis:**
`@cache_page_for_anon(600)` is used on `catalog`. This caches the *entire* HTML response.
**Issue:**
If the page contains any user-specific data (even for anons, like "recently viewed"), it will be stale or incorrect.
**Recommendation:**
Verify `Vary: Cookie` headers are set correctly.

## 4. Server-Side Configuration (Production)

### A. Compression
**Status:** ❓ PENDING VERIFICATION
**Check:** `COMPRESS_ENABLED` setting on production.
**Impact:**
If False, users download full-size assets.

### B. Database Indexes
**Status:** 🔴 HIGH
**Missing Indexes:**
- `orders_order.phone`
- `orders_order.email`
- `storefront_product.price`
**Impact:**
Slow admin searches and sorting.
