# DTF Copy + Localization + SEO Report (v3)

## Scope
Subdomain-only implementation for `dtf.twocomms.shop` based on:
- `CODEX_PROMPT_MASTER_v3.md`
- `CODEX_COPY_SPEC.md`
- `CODEX_LEGAL_TEXTS.md`
- `CODEX_BLOG_10_POSTS_UA.md`
- `CODEX_I18N_DICTIONARY.md`
- `CODEX_ASSETS_BRIEF.md`

## What Was Implemented
1. Home page copy rewrite (UA/RU/EN) with required modules and hooks:
- Hero copy update without touching hero media component.
- Trust bar, "For who", "How it works", "Why us", pricing message, templates/requirements, help block, short FAQ, final CTA.
- Added/updated hooks: `24/7`, `reply up to 10 minutes`, `approved by 12:00 — ship today`, and turnaround logic `0–24h / peak up to 48h`.

2. Contacts and communication details replaced globally:
- Phone: `+380966543212` with clickable `tel:+380966543212`.
- Telegram: `@twocomms` with clickable `https://t.me/twocomms`.
- Availability and SLA text aligned across key pages.

3. Delivery & Payment rewritten (UA/RU/EN):
- Shipping-by-12:00 same-day policy.
- 24/7 support and response SLA.
- Clarified production and dispatch windows.

4. Order + Constructor microcopy/preflight updates:
- Terminology switched to `макет 60 см (ганг‑лист)` / `60 cm layout (gang sheet)`.
- Preflight renamed to user-friendly wording.
- Status legend and explanatory tooltips added/updated (DPI, transparency, thin lines, safe area).
- Risk acknowledgement checkbox is hidden by default and shown for "print as-is" flow.

5. Legal pages updated with full text (no TEMP):
- `/privacy/`
- `/terms/`
- `/returns/`
- `/requisites/`

6. Requisites page updated with exact provided details:
- Recipient, IBAN, tax id, bank, MFO, bank EDRPOU.

7. FAQ page:
- `/faq/` present, localized, linked from navigation/footer.

8. 10 blog SEO posts seeded to DB:
- Added migration `twocomms/dtf/migrations/0008_seed_codex_blog_posts_ua.py`.
- Uses `update_or_create` by slug to avoid duplicates and update placeholders.
- Fills title, slug, excerpt, date, publish status, markdown content, and SEO fields.
- Generates `content_html` from markdown for proper rendering in `/blog/<slug>/`.

9. Technical hygiene:
- Fixed script preload mismatch (`dtf.min.js` -> `dtf.js`) in base template.
- Minor locale text consistency fixes in header/footer and delivery copy.

## Commits
- Added after commit step.

## Verification
- Added after verification step.

## Notes
- Linear integration was requested in prompt, but no Linear MCP resources were available in this session, so tasks could not be created programmatically.
