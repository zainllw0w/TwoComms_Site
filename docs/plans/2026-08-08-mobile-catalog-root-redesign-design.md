# Mobile Catalog Root Redesign Design

## Decision

Redesign only the mobile presentation of the root `/catalog/` experience. The first viewport becomes category-first: T-shirts, hoodies, and long sleeves are all visible in one row immediately below the site header. The existing large editorial hero, three trust claims, and large custom-print configurator no longer block category discovery on phones. Desktop keeps the current composition.

The live `/catalog/tshirts/` page is the density and interaction reference. The root page remains a destination chooser, not a duplicate product listing or a filter questionnaire.

## Shared Mobile Contract

- Show all three real category links without horizontal scrolling at 320-430px widths.
- Keep each category target at least 44px high and make the entire visual tile tappable.
- Use the current Ukrainian names and live category URLs.
- Keep one concise H1 and, at most, one short supporting line above the categories.
- Keep real TwoComms category imagery and the existing dark storefront identity.
- Move custom print below category selection as one compact secondary CTA, not a competing hero.
- Keep color filters, SEO sections, structured data, and crawlable links available below the primary choice.
- Do not change the category-page product cards, filters, URLs, data models, or desktop catalog layout.
- Preserve safe-area spacing so the fixed bottom navigation never covers a useful action.

## Variant 1: Visual Triptych

Three equal image-led tiles form one compact row. Each tile uses a distinct garment crop, a direct category name, and a restrained product count. A thin orange/gold state line and clear arrow affordance borrow from the current category selector without turning the row into generic tabs.

Below the row, a slim custom-print strip combines one garment crop, the label `Свій принт`, one short value statement, and a single arrow button. This is the recommended direction because it makes all primary paths visually obvious in one glance while retaining the brand's editorial photography.

## Variant 2: Smart Tabs

The category selector from `/catalog/tshirts/` becomes the root-page anchor. Three equal segmented links use the same typography, borders, and active feedback as the live category pages. A shallow visual rail under the labels gives each category a garment cue without requiring large cards.

The custom-print CTA becomes a quiet inline action beneath the selector. This direction has the lowest learning cost and strongest consistency, but it is less visually distinctive than Variant 1.

## Variant 3: Editorial Deck

Three narrow fashion panels sit in one row with stronger art direction: oversized category numerals, cropped garments, concise names, and subtle motion on press. The composition is intentionally more editorial while remaining one-tap navigation.

The custom-print prompt becomes a contrasting compact band with a small print-zone motif and no configurator controls. This is the most memorable direction, but text and crop quality require the strictest QA at 320px.

## Responsive Behavior

At 320-430px the category row always remains three columns. Typography and internal spacing change through fixed breakpoints rather than viewport-scaled font sizes. At tablet widths the tiles may gain height and supporting copy. At 768px and above the existing desktop hero, print panel, and showcase remain unchanged.

Images use stable aspect ratios and `object-fit` crops. Text is limited to category names and counts so it cannot collide with media. Reduced-motion users receive no entrance or press animation.

## Conversion And Analytics

The root page measures direct category intent. Existing category URLs remain canonical and crawlable. Production implementation should add or preserve a single analytics event for category selection with the category slug and source `catalog_root_mobile`; no new funnel step is introduced.

Custom print remains discoverable but visually secondary. Its click source should remain attributable as `catalog_root_mobile_secondary` without changing the custom-print application flow.

## Verification

Before shipping, verify 320x568, 375x812, 390x844, 430x932, 768x1024, and 1440x1000. Acceptance requires all three category links in the first mobile viewport, no horizontal overflow, no bottom-nav overlap, readable 44px targets, working category navigation, unchanged desktop composition, valid semantic heading order, and no console/image failures.

