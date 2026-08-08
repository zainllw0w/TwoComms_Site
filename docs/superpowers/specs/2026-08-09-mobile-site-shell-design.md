# Mobile Site Shell Design

## Goal

Give every public storefront page one consistent mobile shell matching the approved catalog reference: a fixed reference header, a useful contextual bottom navigation, an accessible burger menu with language switching, and stable scroll geometry. Desktop markup and styling remain unchanged.

## Decisions

- Mobile breakpoint is the existing storefront boundary: `< 992px`; the visual reference is tuned for 320, 375, 390, and 430px widths.
- Header is fixed to the viewport top with a reserved `--mobile-shell-header-height` offset. It contains burger, centered TwoComms wordmark, search, and cart. The cart badge is updated by the existing cart-count flow and the existing mobile mini-cart remains the interaction target.
- The burger opens a focusable menu panel with catalog, custom print, delivery, about, contacts, and a compact language switcher generated from `language_switch_links`. Escape, outside press, and the close control dismiss it; body scrolling is locked while it is open.
- Bottom navigation has four equal slots: contextual first action, `Обране`, `Профіль`, `Про нас`. Cart is removed from the dock. On catalog routes the first action is `Фільтри` and opens the existing smart-selector filter sheet; on all other public routes it is `Каталог` and links to `/catalog/`.
- Bottom navigation keeps the existing hide-on-down-scroll/show-on-up-scroll behavior, safe-area padding, and footer reveal behavior. Its visual treatment uses near-black surfaces, warm orange active state, neutral gray inactive state, and no purple gradient.
- Root catalog keeps the approved reference content, but its duplicate local header/menu/dock are hidden because the global shell owns those responsibilities. The content receives the global header offset and bottom-nav padding.
- Catalog filter action delegates to the existing smart-selector sheet. No fake filter choices are introduced: theme/collection, audience, availability, fit, size, thermo, color, and sort are rendered only when their server-provided options exist.
- The root custom-print card gains four low-contrast floating brand marks behind the garment. They use transforms/opacity only, are placed in the image-side negative space, are disabled by `prefers-reduced-motion`, and cannot overlap copy or capture pointer events.
- Hero carousel behavior is unchanged. A small static progress marker is added to the reference hero as a visual affordance only; it has no false interaction until a carousel exists.

## Architecture

`partials/header.html` remains the single global include. Its desktop navbar stays structurally intact. A new mobile shell block is rendered once there and is styled by `static/css/mobile-shell.css`; `static/js/mobile-shell.js` owns menu/search/language state and delegates cart/filter actions to existing modules. The catalog template only exposes a `data-catalog-mobile-reference` content surface and no longer acts as the owner of global header or bottom navigation.

## Accessibility and performance

- All icon-only controls have translated accessible names and visible `:focus-visible` states.
- Menu uses `aria-expanded`, `aria-controls`, `aria-hidden`, and a dialog-like focus trap; language links expose `lang`/`hreflang` and current state.
- Header, bottom nav, hero, category media, and custom-print media have explicit dimensions/aspect ratios to prevent CLS. Images retain width/height attributes and eager/high priority is limited to the hero LCP image.
- Mobile shell CSS is loaded globally but only activates below 992px. Desktop selectors are not changed except for a neutral class on the existing navbar.

## Acceptance criteria

1. Every public storefront route renders exactly one mobile shell header and one mobile bottom dock at widths below 992px.
2. Cart is actionable from the header; no mobile bottom-nav item is labeled `Кошик`.
3. Burger menu links and language links work, close correctly, and do not allow background scroll while open.
4. Catalog dock action opens the existing filter sheet and active filter count stays synchronized.
5. Root catalog content remains visually reference-matched, with no horizontal overflow and stable top/bottom offsets at 320/375/390/430px.
6. Desktop screenshots and existing catalog/PDP/cart/checkout tests remain unchanged.
