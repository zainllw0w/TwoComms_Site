# Static Customer Pages: Localization Audit

**Scope:** public static/customer pages and shared storefront chrome only: UA, RU, and EN home; ProBrand; delivery/payment; cooperation; contacts; size and care guides; help/FAQ; wholesale/pricelist; account chrome when it is visible to customers. Catalog, PDP, Custom Print, cart, checkout, and admin are excluded.

**Status:** audit complete for this ownership slice (read-only; no application,
gettext, database, Git, or deployment changes were made).

## Evidence Rules

- A finding is recorded only after live HTTPS inspection and/or source confirmation.
- `Template/gettext` means the string is owned by deployable source and should be corrected through the shared locale design.
- `Database-backed` means production content may differ from local data; it requires production MariaDB inspection before declaring a backfill scope complete.
- `SEO/GEO` covers document title, description, headings, canonical/hreflang/schema, and crawlable language consistency.

## Confirmed Findings

### SP-01 - Cooperation FAQ falls back to Ukrainian in RU and EN

- **Priority:** P1 customer-facing B2B conversion and crawlable FAQ inconsistency.
- **Routes/locales:** `https://twocomms.shop/en/cooperation/` and `https://twocomms.shop/ru/cooperation/`; UA is canonical and correct.
- **Live evidence:** both foreign-language pages render Ukrainian FAQ questions: `Чи робите спільні колекції...`, `Які умови...`, `Як працюєте...`, and `Чи продаєте...`. Their surrounding hero, CTA, and FAQ heading are localized, making the fallback conspicuous in the partnership decision path.
- **Source evidence:** `twocomms/storefront/views/legacy_stubs.py:131-144` defines the four `gettext` strings. The matching entries in `twocomms/locale/en/LC_MESSAGES/django.po:10119-10144` and `twocomms/locale/ru/LC_MESSAGES/django.po:10163-10188` have empty `msgstr` values.
- **Ownership:** Template/gettext, not database-backed.
- **SEO/GEO impact:** the untranslated questions are visible and crawlable FAQ content under localized canonical URLs. They dilute language consistency for English/Russian visitors and language-targeted crawlers.
- **Suggested fix boundary:** add reviewed RU and EN question/answer translations to the existing gettext catalogs, compile catalogs, and leave the UA canonical copy unchanged. Do not create a page-specific translation system for this isolated source-owned list.
- **Exact verification:** on desktop and `390x844` mobile, load both routes; assert all seven FAQ questions and expanded answers match the route language, then confirm `html[lang]`, canonical URL, and `hreflang` remain unchanged.

### SP-02 - Contacts conversion page has untranslated RU/EN service and shipping copy

- **Priority:** P1 customer-facing contact conversion.
- **Routes/locales:** `https://twocomms.shop/en/contacts/` and `https://twocomms.shop/ru/contacts/`; UA is canonical and correct.
- **Live evidence:** both routes show Ukrainian `Як ми працюємо`, `Онлайн-магазин з відправкою з Харкова по всій Україні`, `Звідки відправляємо`, `Харків, Україна`, `Нова Пошта по Україні: 1–3 дні`, and the free-shipping threshold next to otherwise localized contact and form CTA copy.
- **Source evidence:** all visible strings are wrapped in gettext in `twocomms/twocomms_django_theme/templates/pages/contacts.html:193-227`, but the relevant EN and RU entries are empty, for example `twocomms/locale/en/LC_MESSAGES/django.po:12438-12459` and `twocomms/locale/ru/LC_MESSAGES/django.po:12488-12509`.
- **Ownership:** Template/gettext, not database-backed.
- **SEO/GEO impact:** the metadata and canonical are localized, but the live on-page Kharkiv/shipping proof is not. This weakens language consistency for local-intent users and crawlers evaluating the ContactPage.
- **Suggested fix boundary:** translate the existing EN/RU gettext entries for the complete locations/shipping block; retain the factual city, carrier, threshold, phone, and schema values. No routing or contact-form behavior change is required.
- **Exact verification:** desktop and `390x844` mobile on both routes must show route-language headings, shipping text, and form labels. Verify `ContactPage`/`ClothingStore` JSON-LD parses and the canonical/hreflang values remain self-consistent.

### SP-03 - Care-guide FAQ and FAQPage schema remain Ukrainian in RU and EN

- **Priority:** P1 service conversion and SEO/GEO.
- **Routes/locales:** `https://twocomms.shop/en/doglyad-za-odyagom/` and `https://twocomms.shop/ru/doglyad-za-odyagom/`.
- **Live evidence:** the surrounding hero and care instructions are localized, but all eight FAQ summaries and answers remain Ukrainian. On English, the `FAQPage` JSON-LD also exposes Ukrainian `name` and `acceptedAnswer.text`, including `При якій температурі прати одяг TwoComms?` and its answer.
- **Source evidence:** canonical list is `CARE_FAQ_ITEMS` in `twocomms/storefront/support_content.py:265-298`; the EN/RU `msgstr` entries are empty, including EN `django.po:8046-8051` and RU `django.po:8090-8095`. `twocomms/storefront/support_translations.py:775-810` overrides hero/sections/CTA for English but intentionally has no `faq_items` replacement, leaving gettext fallback exposed.
- **Ownership:** Template/gettext, not database-backed.
- **SEO/GEO impact:** the page emits FAQPage and HowTo JSON-LD from its customer content. Foreign-language canonical URLs currently publish Ukrainian FAQ entities to search and answer engines.
- **Suggested fix boundary:** complete reviewed RU/EN translations for all `CARE_FAQ_ITEMS` strings and compile catalogs; preserve the factual care guidance and existing HowTo/FAQ JSON-LD shape.
- **Exact verification:** on desktop and `390x844` mobile, check every FAQ summary and an expanded answer on each locale. Parse JSON-LD and assert both FAQPage and HowTo texts use the route language; retain canonical/hreflang/schema type values.

### SP-04 - Wholesale FAQ falls back to Ukrainian after its first localized entry

- **Priority:** P1 B2B conversion and crawlable commercial FAQ.
- **Routes/locales:** `https://twocomms.shop/en/wholesale/` and `https://twocomms.shop/ru/wholesale/`.
- **Live evidence:** English and Russian pages render the first question in the selected locale, then seven Ukrainian questions starting with `Які знижки діють на оптові партії?`. English page JSON-LD contains Ukrainian FAQ content under the English canonical URL.
- **Source evidence:** `WHOLESALE_FAQ_ITEMS` in `twocomms/storefront/views/legacy_stubs.py:79-112`; corresponding EN/RU entries such as `Які знижки діють на оптові партії?` have empty translations (`locale/en/.../django.po:10070-10072`, `locale/ru/.../django.po:10114-10116`).
- **Ownership:** Template/gettext, not database-backed.
- **SEO/GEO impact:** FAQPage contains wholesale pricing, dropshipping, production, VAT, and volunteer-program language. A mixed locale is especially damaging on a B2B lead path and for language-targeted FAQ extraction.
- **Suggested fix boundary:** complete all seven missing RU/EN question/answer pairs in the existing gettext catalogs. Keep price tiers and commercial facts unchanged pending business confirmation.
- **Exact verification:** desktop and mobile must show eight route-language FAQ entries, including opened answers; parse FAQPage JSON-LD and verify no Ukrainian fallback appears on the RU/EN canonical routes.

### SP-05 - Size guide has source-owned raw English chrome and two incorrect semantic translations

- **Priority:** P1 purchase-assistance module.
- **Routes/locales:** UA `/rozmirna-sitka/`, RU `/ru/rozmirna-sitka/`, and EN `/en/rozmirna-sitka/`.
- **Live evidence:** UA and RU expose English UI tokens such as `FIT GUIDE`, `garment measurements`, `CONFIRMED GUIDES`, `HOODIE FIT GUIDE`, `Length`, `Width`, `BASIC TEE FIT GUIDE`, and `ADDITIONAL VISUALS`. EN labels are readable, but the basic T-shirt block is called `Wholesale t-shirts`; RU calls it `Футболки опт`, neither of which means the intended basic T-shirt size guide.
- **Source evidence:** raw source labels are not gettext-wrapped in `twocomms/storefront/services/size_guides.py:32,47-49,57,74,102,134` and `twocomms/twocomms_django_theme/templates/pages/support_page.html:224,307,348`. The semantic error is in existing catalog entries: `Футболка базова` maps to `Wholesale t-shirts` at `locale/en/.../django.po:7593-7594` and `Футболки опт` at `locale/ru/.../django.po:7637-7638`.
- **Ownership:** Template/gettext, not database-backed for the raw labels and the wrong `Футболка базова` translations.
- **SEO/GEO impact:** this mid-funnel, schema-bearing HowTo page carries inconsistent labels in visible copy and image alternatives, making its localized size intent less trustworthy to customers and crawlers.
- **Suggested fix boundary:** move source-owned guide labels/eyebrows/legend terms into gettext (or explicit language payload owned by the shared locale contract), translate UA/RU/EN consistently, and correct the two `Футболка базова` entries to basic T-shirt equivalents. Do not mutate fit/cart state or product-selection behavior.
- **Exact verification:** desktop and `390x844` mobile for all three locales must show localized hero/section/guide chrome, `Футболка базова` as a basic-T-shirt term, and no wrong `Wholesale/опт` label. Validate table headers, image `alt`, FAQ/HowTo JSON-LD, canonical, and hreflang.

### SP-06 - Production size-guide records leak untranslated names/descriptions into localized pages

- **Priority:** P1 content-data localization; implementation requires production MariaDB inspection.
- **Routes/locales:** all variants of `/rozmirna-sitka/`, notably EN where extra visuals include Ukrainian titles and RU/UA where `Standard size chart for hoodies` is shown unchanged.
- **Live evidence:** EN currently shows extra visual titles `Класична футболка — CRC FS-101` and `Оверсайз — футболка (стандарт)`; RU/UA show `Standard size chart for hoodies`. These are distinct from the source-owned labels in SP-05.
- **Source evidence:** the support page reads active `SizeGrid` rows from the database in `twocomms/storefront/views/static_pages.py:1215-1221`; `build_public_size_guide_blocks` exposes `grid.name` and `grid.description` directly at `twocomms/storefront/services/size_guides.py:533-568`. `SizeGrid.name`, `description`, and `guide_data` are single language-neutral fields at `twocomms/storefront/models.py:522-539`.
- **Ownership:** Database-backed and schema/design-bound. Local SQLite cannot establish the production row inventory.
- **SEO/GEO impact:** generated visible guide descriptions and image alternatives can mix Ukrainian/English on a localized HowTo page. The source page's own metadata is localized, so the data leak is the remaining language-quality gap.
- **Suggested fix boundary:** first inspect production active `SizeGrid` rows and all rendered values per locale. Then choose an explicit locale-aware content model/payload for grid name, description, structured guide copy, and image alt, with a controlled backfill. Do not overwrite live DB records before that inventory.
- **Exact verification:** after the data migration/backfill, compare every active grid and rendered extra visual across UA/RU/EN on desktop/mobile; assert image `alt`, title, description, and schema-visible text follow the active locale.

### SP-07 - Home product-card titles fall back to Ukrainian on English and Russian home pages

- **Priority:** P1 primary storefront conversion and SEO/GEO; title-only data backfill should precede lower-priority product-description work.
- **Routes/locales:** `https://twocomms.shop/en/` and `https://twocomms.shop/ru/`.
- **Live evidence:** English homepage cards start with Ukrainian titles such as `Футболка «Правил немає»`, `Футболка «Бойова квіточка»`, and `Футболка «Харків Вокзальна»`; Russian shows the same Ukrainian titles. The English homepage `ItemList` JSON-LD repeats these Ukrainian names while its list title is English.
- **Source evidence:** home cards render `p.title` directly in `twocomms/twocomms_django_theme/templates/partials/product_card.html` (including title, data attributes, alt fallback, and CTA). The home schema also emits `p.title` at `templates/pages/index.html` inside `itemListElement`. `storefront/translation.py:43-57` registers Product title translations, while `storefront/services/locale_publication.py:1-18` documents that modeltranslation deliberately falls back to Ukrainian; the card queryset keeps cards navigable even when localized fields are absent (`storefront/views/catalog.py:1421-1428`).
- **Ownership:** Production database-backed Product `title_en` and `title_ru` coverage. Source behavior is deliberate fallback, so code should not silently fabricate or hide products without an agreed policy.
- **SEO/GEO impact:** English/Russian homepage canonical URLs publish foreign-language product names in visible cards, accessible labels, image fallback alt, and ItemList JSON-LD. This is a direct language-consistency and extraction defect on the highest-traffic entry path.
- **Suggested fix boundary:** use production MariaDB to inventory published/home-visible Product rows with empty `title_en`/`title_ru`; backfill reviewed title translations first, then separately scope descriptions/SEO fields. Preserve the current availability/navigation behavior until the publication-policy decision is approved.
- **Exact verification:** production query must show zero empty target-language title fields for all homepage-visible products. On desktop and `390x844` mobile, assert visible card names, `data-product-title`, aria labels/image alt fallback, and homepage ItemList names match each selected route language.

### SP-08 - Shared guest account drawer leaks Ukrainian conversion copy in RU and EN

- **Priority:** P1 shared conversion navigation. The drawer is available from
  the account control on every public page, including mobile bottom navigation.
- **Routes/locales:** anonymous `https://twocomms.shop/en/` and
  `https://twocomms.shop/ru/`; the same partial is mounted in both desktop and
  mobile shells. UA is canonical and correct.
- **Live evidence:** both locales render the Ukrainian benefit line
  `Бали • замовлення • обране` below an otherwise localized `Sign in` / `Вход
  в аккаунт` heading. It appears twice in response HTML, once for each shell.
  This was checked without following a login route or using an authenticated
  browser session.
- **Source evidence:**
  `twocomms/twocomms_django_theme/templates/partials/mini_profile.html:114`
  owns the string. Its EN and RU `django.po` entries are empty. The same
  untranslated shared surface includes user-facing accessibility/navigation
  labels such as `Аватар`, `Клієнт`, `Меню профілю`, and `Кількість обраних`.
  Admin-only labels are explicitly out of scope.
- **Ownership:** Template/gettext, not database-backed.
- **SEO/GEO impact:** this is primarily conversion UX rather than indexable
  page content, but an English/Russian visitor reaches a mixed-language
  account entry point from the shared header.
- **Suggested fix boundary:** add reviewed EN/RU translations for the guest
  benefit line and the customer-facing drawer labels in the existing gettext
  catalogs. Preserve URL reversing and do not modify authentication behavior.
- **Exact verification:** anonymous desktop and `390x844` checks on one
  UA/RU/EN page each must show localized guest drawer text after opening the
  account control. A focused render test must cover the EN/RU benefit line and
  preserve locale-prefixed login/register links.

### SP-09 - Footer regional accessibility label remains Ukrainian on RU and EN

- **Priority:** P2 accessibility and structured-locality completeness.
- **Routes/locales:** every RU/EN public route through the shared footer;
  confirmed on `/ru/` and `/en/`.
- **Live evidence:** the visible locality/country are correctly rendered as
  `Kharkiv, Ukraine` and `Харьков, Украина`, but the containing
  `PostalAddress` still has `aria-label="Регіон роботи TwoComms"` in both
  foreign locales.
- **Source evidence:**
  `twocomms/twocomms_django_theme/templates/partials/footer.html:177` wraps
  the label in gettext, while both catalog entries are empty.
- **Ownership:** Template/gettext, not database-backed.
- **SEO/GEO impact:** the visible NAP data remains correct; this is an
  accessibility-language defect on a schema-bearing footer rather than a
  canonical/hreflang defect.
- **Suggested fix boundary:** translate only the existing aria label in EN/RU;
  leave factual place names, postal code, organization schema, and URLs
  unchanged.
- **Exact verification:** inspect rendered footer attributes on UA/RU/EN and
  run the focused shared-footer regression test. Confirm visible locality and
  country remain unchanged in the correct locale.

### SP-10 - ProBrand uses a raw English visual-control label on UA and RU

- **Priority:** P2 user-visible ProBrand completeness.
- **Routes/locales:** `https://twocomms.shop/pro-brand/` and
  `https://twocomms.shop/ru/pro-brand/`; the EN occurrence is correct.
- **Live evidence:** the ProBrand visual-player chrome emits `VISUAL STORY`
  verbatim for RU and EN; the Ukrainian route uses the same raw English token.
  `CODE:01` through `CODE:03`, the brand name, and `FAQ` are identifiers and
  are not part of this finding.
- **Source evidence:** the visible label is a raw span at
  `twocomms/twocomms_django_theme/templates/pages/pro_brand.html:1466`, unlike
  the adjacent localized player status and explanatory copy.
- **Ownership:** Template/source, not database-backed.
- **SEO/GEO impact:** low: the label is visual UI text and not an ownership
  signal. It still violates the requested fully localized reading surface.
- **Suggested fix boundary:** make this one semantic visual label locale-owned
  through gettext or the existing page translation contract. Keep stable brand
  identifiers/codes unchanged.
- **Exact verification:** UA/RU/EN desktop and `390x844` screenshots must
  show the appropriate localized visual-story label, without layout overflow
  or a changed ProBrand JSON-LD payload.

## Coverage Ledger

| Surface | UA live | RU live | EN live | Desktop | Mobile | Source mapped | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Home | checked | checked | checked | checked | checked | yes | SP-07 data, SP-08 shared drawer |
| ProBrand | checked | checked | checked | checked | checked | yes | P1 body/FAQ screened; SP-10 P2 |
| Delivery/payment | checked | checked | checked | checked | checked | yes | no P1 mixed-language finding in this slice |
| Cooperation | checked | checked | checked | checked | checked | yes | SP-01 P1 FAQ |
| Contacts | checked | checked | checked | checked | checked | yes | SP-02 P1 shipping/location block |
| Size guide | checked | checked | checked | checked | checked | yes | SP-05 source, SP-06 production data |
| Care guide | checked | checked | checked | checked | checked | yes | SP-03 P1 FAQ and schema |
| Help/FAQ | checked | checked | checked | checked | checked | yes | no P1 mixed-language finding in this slice |
| Wholesale/pricelist | checked | checked | checked | checked | checked | yes | SP-04 P1 FAQ; locale redirect is correct |
| Shared header/footer/account chrome | checked | checked | checked | checked | checked | yes | SP-08 P1 drawer, SP-09 P2 aria label |

## Tally

| Priority | Confirmed | Template/gettext | Database-backed | Pending live confirmation |
| --- | ---: | ---: | ---: | ---: |
| P0 conversion blocker | 0 | 0 | 0 | 0 |
| P1 customer-facing / SEO | 8 | 6 | 2 | 0 |
| P2 completeness | 2 | 2 | 0 | 0 |

## Implementation Packages

The static-page audit produced **10 exact packages: 0 P0, 8 P1, and 2 P2**.
They should be released in the following dependency order.

1. **P1-SOURCE-FAQ (SP-01 through SP-05):** gettext translations for
   cooperation, contacts, care, wholesale, and source-owned size-guide chrome.
   This is the first safe source-only batch. It requires focused rendering and
   JSON-LD assertions for the FAQ/HowTo pages before catalog compilation.
2. **P1-SHARED-CHROME (SP-08):** guest/customer account-drawer gettext
   translations. It may share one PO compilation with P1-SOURCE-FAQ, but must
   retain anonymous desktop/mobile checks and locale-preserving auth URLs.
3. **P2-SHARED-POLISH (SP-09 and SP-10):** footer accessibility label plus the
   ProBrand visual-player label. This can follow the P1 source batch; stable
   brand codes remain untouched.
4. **P1-DATA-SIZE (SP-06):** production MariaDB inventory, locale ownership
   model, and reviewed SizeGrid backfill. It is blocked until safe SSH access
   is available and must not infer data from SQLite.
5. **P1-DATA-HOME-TITLES (SP-07):** production inventory and reviewed RU/EN
   `Product.title_*` coverage for homepage-visible products. It depends on the
   same safe production access and the cross-cutting locale-publication policy.

## Verified Non-Findings

- `/pricelist/`, `/ru/pricelist/`, and `/en/pricelist/` each return a
  language-preserving permanent redirect to the matching `/wholesale/` route;
  no redirect localization fix is required.
- ProBrand, delivery/payment, help, FAQ, returns, order tracking, privacy, and
  terms were screened on RU/EN public HTML. No additional Ukrainian-distinctive
  P1 body fallback was confirmed beyond the findings recorded here. This is not
  a claim that database-backed product content is complete.
- The shared footer's visible navigation, locality/country, rights text, and
  locale-aware links render in the selected language on the sampled RU/EN
  pages. SP-09 is limited to the untranslated accessibility label.

## Deferred Data-Localization Backlog

Product titles, descriptions, and product-specific SEO are deliberately outside this static-page slice. They need a separate production-authoritative audit and data-backfill plan after the shared source-level P0/P1 locale contract is approved.
