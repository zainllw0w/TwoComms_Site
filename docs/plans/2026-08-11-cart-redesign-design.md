# Cart Redesign Design

## Goal

Restore a reliable cart layout on phones and desktop while keeping the existing Django session, template data attributes, and cart JavaScript behavior unchanged.

## Visual Direction

Use the storefront dark management and finance language with a quiet graphite surface, one warm orange action accent, and restrained green only for earned points or payable totals. The memorable detail is a thin orange status rail and a soft thumbnail frame; no decorative sparks, purple gradients, or nested card noise.

## Responsive Composition

- The header keeps its full height and wraps safely; the clear action becomes icon-first on narrow phones.
- On phones through 1024px, each item is a two-row card: thumbnail and content on top, total plus compact actions below. Metadata chips wrap and never silently disappear.
- At 1025px and wider, the card becomes three columns: thumbnail, flexible details, and a dedicated total/actions rail. This breakpoint matches the page sidebar collapse so the content column is never squeezed by a desktop action rail.
- Product images use contain so garment imagery is not cropped. Remove and manager actions expose visible labels on larger screens and accessible icon-only controls on narrow screens.

## Data and Behavior

No endpoint, data attribute, quantity stepper hook, custom-print moderation hook, or remove handler changes. Text is wrapped only in spans for responsive visibility and aria labels are added to icon-first controls.

## Verification

Run the focused cart template/static contract test with Django test runner, compile and check touched templates, then use Playwright screenshots and DOM measurements at 320, 390, 768, and 1280px. Verify no horizontal overflow, the header is fully visible, and all cart actions remain reachable.
