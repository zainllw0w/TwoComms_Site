# OpenGraph Image Refresh Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Publish the approved TwoComms artwork as the versioned global OpenGraph fallback while retaining correct entity-specific previews.

**Architecture:** A single cache-busting JPEG becomes the canonical generic social image and the locale resolver returns it for every language. Existing product, category, and blog overrides stay in place; their structured image properties are made truthful by preventing fallback MIME/dimension values from leaking onto dynamic assets.

**Tech Stack:** Django 6.1 templates and template tags, Pillow/sips image inspection, WhiteNoise `CompressedManifestStaticFilesStorage`, Django TestCase.

---

### Task 1: Lock the fallback and dynamic-preview contracts with tests

**Files:**
- Modify: `twocomms/storefront/tests/test_seo_regressions.py`
- Modify: `twocomms/storefront/tests/test_blog.py`

**Step 1: Write the failing tests**

Add focused assertions that:

- default/localized social-image resolution returns `img/social-preview-2026-08.jpg`;
- fallback HTML emits the versioned URL, JPEG MIME, 1200x630, alt, and matching Twitter URL;
- schema fallbacks use `static/img/social-preview-2026-08.jpg`;
- a product with its own image keeps that URL and alt without false `image/jpeg`/1200x630 structured properties;
- a blog with a cover continues to emit its own WebP URL and 1600x1000 properties.

**Step 2: Run tests to verify RED**

Run:

```bash
TWC_PYTHON="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)/.venv/bin/python"
"$TWC_PYTHON" twocomms/manage.py test \
  storefront.tests.test_seo_regressions.ProductPageSeoRegressionTests.test_product_social_image_does_not_inherit_fallback_dimensions \
  storefront.tests.test_seo_regressions.SocialImageFallbackTests \
  storefront.tests.test_blog.BlogSchemaTests.test_article_without_cover_uses_versioned_social_fallback \
  --settings=test_settings --verbosity 2
```

Expected: FAIL because the versioned path and dynamic metadata isolation do not exist yet.

### Task 2: Publish and validate the optimized JPEG

**Files:**
- Create: `twocomms/twocomms_django_theme/static/img/social-preview-2026-08.jpg`

**Step 1: Deterministically crop and resize**

Center-crop the user source to the exact 1200:630 ratio, resample to 1200x630, convert to sRGB JPEG, strip unnecessary metadata, and use progressive encoding. Do not redraw or generatively alter the artwork.

**Step 2: Verify the binary contract**

Inspect with Pillow/sips and assert:

```text
format=JPEG
size=(1200, 630)
mode=RGB
progressive=true
```

Also require a practical crawler download size and visually inspect the final crop.

### Task 3: Centralize the versioned fallback

**Files:**
- Modify: `twocomms/storefront/seo_utils.py`
- Modify: `twocomms/storefront/templatetags/i18n_links.py`
- Modify: `twocomms/twocomms_django_theme/templates/base.html`
- Modify: `twocomms/twocomms_django_theme/templates/pages/index.html`
- Modify: `twocomms/twocomms_django_theme/templates/pages/contacts.html`
- Modify: static-page templates that hard-code `img/social-preview.jpg`

**Step 1: Implement the minimal path change**

Change `DEFAULT_SOCIAL_IMAGE_PATH` to `static/img/social-preview-2026-08.jpg`. Make `localized_social_image_path` return the single approved card for UA/RU/EN. Replace hard-coded fallback references in templates.

**Step 2: Keep the fallback descriptor truthful**

Retain JPEG/1200x630 metadata only for the base fallback and make the brand page inherit the new fallback instead of its square favicon.

### Task 4: Prevent false metadata on dynamic images

**Files:**
- Modify: `twocomms/twocomms_django_theme/templates/base.html`
- Modify: `twocomms/twocomms_django_theme/templates/pages/product_detail.html`
- Modify: `twocomms/twocomms_django_theme/templates/pages/product_detail_new.html`
- Modify: `twocomms/twocomms_django_theme/templates/pages/catalog.html`
- Modify: `twocomms/twocomms_django_theme/templates/pages/category_color_landing.html`
- Verify: `twocomms/twocomms_django_theme/templates/pages/blog/post.html`

**Step 1: Add a structured-property override boundary**

Wrap the fallback's `og:image:alt`, type, width, and height tags in a dedicated template block.

**Step 2: Override the boundary for dynamic sources**

Product and category templates emit their entity-specific alt where available but omit unknown MIME/dimensions. Blog templates retain the known WebP 1600x1000 descriptor.

**Step 3: Run GREEN tests**

Run the focused tests from Task 1 and expect PASS.

### Task 5: Verify staticfiles and regressions

**Files:**
- Test only

**Step 1: Run focused suites**

Run `test_blog.py`, `test_blog_structured.py`, the new fallback tests, product image tests, and template-tag tests with `--settings=test_settings`.

Expected: all task-owned tests pass. Record the four pre-existing failures in the full `test_seo_regressions` module separately; they exist on untouched `origin/main`.

**Step 2: Run Django checks**

```bash
"$TWC_PYTHON" twocomms/manage.py check --settings=test_settings
```

Expected: zero issues.

**Step 3: Verify the production static manifest path**

Run `collectstatic --noinput` using production storage and an isolated temporary `STATIC_ROOT`. Confirm the manifest maps the new file and no template references an absent asset.

**Step 4: Review the scoped diff and commit**

Stage only the design, plan, tests, templates, Python helpers, and new JPEG. Confirm the user's unrelated primary-worktree changes are absent.

### Task 6: Push, deploy, and verify production

**Step 1: Push the reviewed branch commit to GitHub main**

```bash
git push origin HEAD:main
```

**Step 2: Deploy through the authorized SSH path**

Use `TWOCOMMS_DEPLOY_PASSWORD` through `sshpass -e`, activate the production Python 3.14 virtualenv, and run `git pull --ff-only origin main` in the canonical checkout.

**Step 3: Publish static assets and restart**

Run production `collectstatic --noinput`, then touch `tmp/restart.txt` so templates and the new manifest are loaded.

**Step 4: Verify live behavior**

Confirm deployed SHA, image HTTP 200, `Content-Type: image/jpeg`, 1200x630 bytes, and cache headers. Fetch representative fallback, product, category, and blog pages and verify:

- fallback pages use the new versioned card;
- product/category/blog pages keep their owned images;
- DTF pages keep their dedicated square image with absolute OG/Twitter URLs and truthful 1024x1024 metadata;
- OG and Twitter URLs match;
- structured properties describe the selected image truthfully;
- schema fallbacks use the new versioned URL.
