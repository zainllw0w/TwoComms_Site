# Responsive Mini-Cart Design

## Objective

Make the TwoComms mini-cart visually consistent, compact, and stable from small phones through tablets and desktop. The drawer must keep product imagery bounded, preserve readable product information, make the route to checkout unmistakable, and keep the return-to-shopping action clear but secondary.

## Current Failure

Commit `6441828b` moved the product-row dimensions from inline styles into semantic classes, but defined those classes only under `#mini-cart-panel-mobile`. On desktop, `.mini-cart-row__media` has no stable width or height. Its `w-100 h-100` image therefore participates in an unresolved flex sizing loop and expands to roughly 130-177px while leaving only 66-83px for product copy.

The production 1440x900 baseline confirms the result: the 380px drawer grows to 1300px tall, the content to 972px, and checkout actions render below the viewport. The 390x844 mobile drawer bounds its images correctly at 48px, but its outer grid overflows by 88px, so delivery and information rows are clipped behind the bottom dock.

## Considered Approaches

### 1. Shared restrained drawer (selected)

Use one mini-cart content structure and one dedicated stylesheet. Desktop remains an anchored drawer; mobile and tablet remain a full-width drawer between the fixed header and dock. Both use the same row, list, summary, and action hierarchy.

This directly removes the divergent geometry while preserving the interaction model users already know.

### 2. Patch desktop dimensions only

Add desktop width and height rules to the current CSS and leave the mobile shell unchanged. This is smaller, but it preserves three overlapping CTA style layers, separate layout ownership, and the mobile clipping defect.

### 3. Full-screen cart on every viewport

Use the mobile sheet pattern everywhere. This is structurally consistent but unnecessarily interrupts desktop shopping and makes the mini-cart feel like a full page.

## Visual Direction

The mini-cart becomes a quiet graphite commerce tool. It uses the existing black and off-white storefront palette, thin neutral separators, and the brand orange `#f15a0b` only for the primary checkout action, active focus, and small status accents. Purple and pink gradients, pulsing orange halos, spark decorations, shimmer, nested decorative cards, and competing action colors are removed from this surface.

Typography remains the current Inter stack, with Roboto Condensed reserved for the panel title and total. Text uses normal letter spacing. Product titles clamp to two lines; metadata remains readable and wraps naturally.

## Structure

The desktop and mobile shells both contain:

1. A compact fixed header with the cart icon, title, and close control.
2. A content view with a separately scrollable product list.
3. A fixed action region containing total, the primary checkout link, and the secondary continue-shopping button.

The old direct mono checkout tile is removed from the mini-cart. Mono checkout remains available on the full cart page, where delivery, order contents, and payment context are visible. The outer delivery link and explanatory information block are also removed from the drawer because they consume height and dilute the two main decisions.

## Product Rows

Rows are unframed list items separated by a thin border rather than cards inside the drawer. Each row uses stable tracks:

- media: 56x56px on standard viewports, 48x48px on phones at or below 350px;
- copy: `minmax(0, 1fr)` with a two-line title and wrapping metadata;
- actions: a stable price/remove column with tabular numerals.

Images use `display: block`, explicit dimensions, and `object-fit: cover`. The template no longer relies on generic `w-100 h-100` utilities for ownership of thumbnail geometry.

Custom-print rows use the same grid and dimensions, with a restrained amber border/icon treatment instead of a separate visual system.

## Action Hierarchy

The primary action remains `Оформити замовлення` with the existing explanatory line `Перейти до оплати та доставки`. It is a solid orange, full-width button with a cart icon and forward arrow.

`Продовжити покупки` becomes a full-width neutral secondary button below it, with a left arrow and no pulse, gradient, glow, or explanatory subtitle. It stays at least 44px high and uses the existing delegated close handler.

An empty cart shows a concise empty state and promotes `Перейти до покупок` as its only action.

## Responsive Geometry

Desktop (`min-width: 992px`) uses a 420px anchored drawer with a hard viewport maximum. Its content is a `grid` with `minmax(0, 1fr)` so only the product list scrolls. The panel never extends beyond the visible viewport.

Mobile and tablet (`max-width: 991.98px`) use the existing area between `--mobile-shell-header-height` and `--mobile-shell-dock-height`, including safe-area insets. The panel is a two-row grid: fixed header and `minmax(0, 1fr)` content. Removed outer footer blocks eliminate the current 88px overflow. Short-height layouts compact gaps and copy while keeping both actions reachable.

## Motion And Accessibility

Only the existing drawer open/close transform and small hover/press feedback remain. Item entry animation, checkout shine, continue-button pulse, and sparks are removed. `prefers-reduced-motion` disables remaining transitions.

Buttons retain visible focus states, descriptive accessible names, and 44px minimum targets. The scroll area uses `overscroll-behavior: contain`, and titles/meta are allowed to wrap without horizontal overflow.

## Verification

Automated contracts will assert:

- one dedicated mini-cart stylesheet loaded after the mobile shell;
- shared row geometry for both panel IDs;
- explicit image dimensions and absence of `w-100 h-100` thumbnail sizing;
- separate scroll and action regions;
- no direct mono checkout, spark container, delivery menu, or information footer in either drawer;
- primary and secondary action semantics plus an actionable empty state;
- desktop viewport bounds and mobile/short-height grid contracts.

Browser QA will cover populated and empty states at 320x568, 375x667, 390x844, 430x932, 768x1024, 1024x768, 1280x800, and 1440x900. It will measure panel, content, row, media, and action bounds; verify zero horizontal overflow; exercise open, close, Escape, continue-shopping, and cart navigation; and inspect console errors.
