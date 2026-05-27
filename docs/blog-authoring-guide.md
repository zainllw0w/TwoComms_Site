# TwoComms Blog Authoring Guide

This guide is the contract for humans and AI agents creating `/blog/` posts on the main TwoComms site.

Do not edit `dtf` or `dtf.twocomms.shop` for main-site blog work. The canonical implementation is `storefront`.

## Core Rules

- Use the visual block editor in the custom admin. Do not paste custom CSS or page-level HTML into posts.
- Ukrainian is required. Russian and English are optional; empty RU/EN values intentionally fall back to Ukrainian.
- The public H1 is always `BlogPost.title`. Do not add `<h1>` inside article content.
- Keep legacy `content_html` only as fallback for old posts. New posts should use `BlogPostBlock`.
- Veteran Fund metrics, DTF labels, source cards, and CTAs must be explicit blocks on the relevant post. They must not be template defaults.
- Product reviews should only include product/review-specific blocks: product CTA, image/video, quote, specs, FAQ, sources, and social CTA when needed.

## Category Structure

- Parent categories are broad sections, for example `news` or `reviews`.
- Child categories are editorial lanes, for example `news/veteran-fund`, `news/site-updates`, `reviews/product-reviews`.
- Child category URLs render as `/blog/category/<parent_slug>/<child_slug>/`.
- Flat child URLs such as `/blog/category/veteran-fund/` are compatibility redirects only.
- Related posts prioritize the exact child category, then sibling child categories, then the global fallback.

## Block Registry

### `rich_text`

Use for normal article body, H2/H3 sections, bullet lists, and internal links.

Allowed HTML is sanitized backend-side. Use only semantic text tags: paragraphs, links, strong/emphasis, lists, blockquote, H2/H3/H4. Do not add scripts, iframes, inline styles, or H1.

### `image`

Use for one media asset with alt text and an optional caption. The image renderer reserves width and height to avoid CLS. Captions can be different per language.

### `gallery`

Use for several image blocks grouped together. Keep captions short so mobile cards do not become uneven.

### `youtube_video`

Paste a YouTube URL. The public page renders a lightweight thumbnail placeholder and creates the iframe only after the visitor clicks play.

### `cta_group`

Use for Instagram, Telegram, TikTok, internal pages, catalog links, product links, custom print, or external partner links.

Supported layouts:

- `full`: one wide CTA across the article.
- `split`: two equal CTA cards.
- `cards`: one to five equal cards per desktop row, auto-wrapping on smaller screens.
- `compact`: denser CTA cards for short labels.

Every button needs a provider, label, optional caption, and URL. Provider-specific URLs are normalized where possible: Telegram handles become `https://t.me/...`, Instagram handles become profile links, TikTok handles become profile links. External links get safe `target` and `rel`.

### `product_cta`

Use when the article should send the visitor to a specific shop product. Set `product_id`, title, and button label. The renderer uses the product URL and description from the catalog.

### `metric_cards`

Use for progress cards such as `2/4`, DTF, B2B/B2C. This is appropriate for the Veteran Fund article and similar reports, not for ordinary product reviews.

### `table_specs`

Use for specs, sizes, comparison rows, materials, production details, or structured report values.

### `quote`

Use for editorial quotes, reviewer notes, or partner statements. Keep the quote short and add `cite` when the source should be visible.

### `callout`

Use for important notes. Tones are `info` and `tip` in v1. Do not use callouts as a replacement for every paragraph.

### `faq`

Use for question-answer sections. The renderer contributes `FAQPage` schema to the public article.

### `source_list`

Use for primary sources, partner references, or official links. Sources are safe outbound links and should be explicit per post.

### `locked_content`

Use for content visible only to authenticated users. Anonymous visitors see a login/register prompt and do not receive hidden text in the HTML.

### `promo_claim`

Use when an article grants a personal promo code. Anonymous visitors are sent to login/register. Authenticated visitors receive one unique `PromoCode` and one `UserPromoCode` grant per campaign/block, subject to campaign limits.

## Cover Images

- Set `cover_alt` for SEO/accessibility.
- Set `cover_caption` when text should appear under the hero image. This replaces the old hardcoded media badge.
- Do not use Veteran Fund or DTF cover captions on unrelated posts.

## SEO Checklist

- Title target: 45-60 characters. Warning after 65 characters.
- Description target: 120-155 characters. Warning after 160 characters.
- Use one visible H1 from the post title only.
- Use H2/H3 for the article outline.
- Add FAQ only when the questions are real and useful.
- Use internal links in `rich_text` for relevant category, product, catalog, and related article pages.
- Use `source_list` for external references instead of hiding sources inside random paragraphs.

## Performance Checklist

- Cover image is LCP-critical and gets `fetchpriority="high"`.
- Content images and YouTube thumbnails lazy-load.
- Width/height attributes and reserved layout prevent CLS.
- CTA layouts use equal grid tracks, so long labels wrap without resizing neighboring cards.
- Animations are CSS-only and respect `prefers-reduced-motion`.
