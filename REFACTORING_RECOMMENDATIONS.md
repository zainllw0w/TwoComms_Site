# Refactoring Recommendations

## 1. Extract Service Layer for Cart and Orders
**Priority:** 🔴 HIGH
**Location:** `storefront/views/cart.py`, `storefront/views/monobank.py`

*   **Problem:** `view_cart` and `monobank_create_invoice` are "fat views" containing complex business logic.
*   **Recommendation:**
    *   Create `storefront/services/cart_service.py`:
        *   `get_cart_details(request)`: Return structured cart data (items, totals, discount).
        *   `add_item_to_cart(...)`: Handle addition logic.
        *   `update_cart_item(...)`: Handle update logic.
    *   Create `orders/services/order_service.py`:
        *   `create_order_from_cart(...)`: Handle order creation, including `OrderItem` creation and promo code usage.
        *   `calculate_order_totals(...)`: Centralize calculation logic.

## 2. Extract Monobank Integration Logic
**Priority:** 🟡 MEDIUM
**Location:** `storefront/views/monobank.py`

*   **Problem:** `monobank.py` mixes view logic (HTTP handling) with integration logic (API calls, signature verification) and business logic (basket construction).
*   **Recommendation:**
    *   Create `orders/services/monobank_service.py` (or `integrations/monobank.py`):
        *   `MonobankClient` class to handle API requests.
        *   `build_basket_for_order(order)`: Pure function to generate the basket structure.
        *   `create_invoice(order)`: Orchestrate the API call.

## 3. Centralize Configuration
**Priority:** 🟢 LOW
**Location:** `twocomms/settings.py`

*   **Problem:** Hardcoded defaults for environment variables (e.g., `TIKTOK_PIXEL_ID`, `MONOBANK_CHECKOUT_DELIVERY_METHODS`) are scattered in `settings.py`.
*   **Recommendation:**
    *   Use a library like `django-environ` for more robust env var handling.
    *   Move business-logic constants (like `MONOBANK_SUCCESS_STATUSES`) to a dedicated `constants.py` or the service layer.

## 4. Optimize `get_offer_id` usage
**Priority:** 🟡 MEDIUM
**Location:** `storefront/models.py`, `storefront/views/cart.py`

*   **Problem:** `get_offer_id` is called repeatedly in loops.
*   **Recommendation:**
    *   Ensure `analytics_helpers` are efficient.
    *   Consider caching offer IDs if they are expensive to compute (though they seem string-based, so low cost).

## 5. Unify User Profile Logic
**Priority:** 🟢 LOW
**Location:** `storefront/views/cart.py`

*   **Problem:** Profile update logic inside `view_cart` (POST request) is messy.
*   **Recommendation:**
    *   Move profile update logic to `accounts/services/profile_service.py`.
    *   Use a dedicated API endpoint or FormView for profile updates instead of mixing it into the cart view.
