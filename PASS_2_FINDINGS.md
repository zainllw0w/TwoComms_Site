# Pass 2: Additional Problems Findings

## 1. Database: Missing Indexes
**Priority:** 🟡 HIGH
**Location:** `orders/models.py`, `storefront/models.py`

*   **Problem:** The `Order` model lacks indexes on `phone` and `email` fields.
    *   **Context:** These fields are likely used for looking up customer orders, especially in admin or support scenarios.
    *   **Risk:** Full table scans when searching for orders by customer contact info.
*   **Problem:** The `Product` model lacks an index on `price`.
    *   **Context:** Sorting by price is a common e-commerce feature.
    *   **Risk:** Slow sorting on large catalogs.

## 2. Images: Potential CLS (Cumulative Layout Shift)
**Priority:** 🟡 HIGH
**Location:** `storefront/templatetags/image_optimization.py`

*   **Problem:** The `optimized_image` template tag allows rendering images without `width` and `height` attributes.
    *   **Verification:** Need to confirm if templates like `product_card.html` actually pass these arguments.
    *   **Risk:** Layout shifts during page load, negatively affecting Core Web Vitals (CLS) and SEO.

## 3. CSS: Excessive Bundle Size
**Priority:** 🔴 CRITICAL (Re-confirmed)
**Location:** `static/css/styles.min.css`

*   **Observation:** File size is 477KB.
*   **Hypothesis:** Likely includes full Bootstrap source or other large libraries without purging unused styles.
*   **Action:** Need to analyze source SCSS/CSS files to identify the source of bloat.

## 4. JS: Bundle Size
**Priority:** 🟢 MEDIUM
**Location:** `static/js/main.js`

*   **Observation:** File size is 99KB.
*   **Status:** Acceptable, but could likely be optimized or split.
