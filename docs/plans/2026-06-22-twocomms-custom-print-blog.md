# TwoComms Custom Print Blog Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Publish ten Ukrainian/Russian custom-print blog post-landings with reusable blog blocks, SEO metadata, FAQ schema, and production deployment.

**Architecture:** Use the existing `BlogPost`, `BlogCategory`, and `BlogPostBlock` models. Add an idempotent management command that stores the article corpus as structured Python data and creates/updates posts and deterministic block sequences. Add only small renderer/style improvements needed for reusable post-landing classes.

**Tech Stack:** Django 5, django-modeltranslation, MySQL in production, existing blog block renderer, CSS in `twocomms_django_theme/static/css/styles.css` and `styles.purged.css`.

---

### Task 1: Publication Command Tests

**Files:**
- Modify: `twocomms/storefront/tests/test_blog_structured.py`
- Create: `twocomms/storefront/management/commands/publish_custom_print_blog.py`

**Step 1: Write failing tests**

Add tests that call the command and assert:

- ten published posts exist with expected slugs;
- each post has `title_uk`, `title_ru`, `seo_title_uk`, `seo_title_ru`, `seo_description_uk`, `seo_description_ru`;
- each post has blocks for early CTA, metric cards, FAQ, and related/internal links;
- category `custom-print-guides` exists under `guides`;
- a rendered article returns `index, follow` and contains `/custom-print/`;
- the FAQ block contributes `FAQPage` schema.

**Step 2: Verify red**

Run:

```bash
SECRET_KEY=test_local_secret /Users/zainllw0w/TwoComms/site/.venv/bin/python twocomms/manage.py test storefront.tests.test_blog_structured --settings=test_settings
```

Expected: fail because the command does not exist.

**Step 3: Implement minimal command shell**

Create `publish_custom_print_blog.py` with a `BaseCommand`, constants for category and article data, and `update_or_create` logic.

**Step 4: Verify green or next red**

Run the same test command. Fix only the failures from the command surface.

### Task 2: Article Corpus And Blocks

**Files:**
- Modify: `twocomms/storefront/management/commands/publish_custom_print_blog.py`

**Step 1: Add the complete article data**

For each of the ten briefs, add:

- UA/RU title, slug, excerpt, SEO title, description, keywords;
- CTA labels and captions;
- article-specific rich text sections;
- trust cards, scenarios, process, table/checklist, FAQ, internal links, final CTA;
- collaborator brief as a non-public admin/source note only if useful, not as visible ad copy.

**Step 2: Implement deterministic block creation**

For each post:

- delete/recreate managed blocks for that post, or replace all blocks in deterministic order;
- use payloads with `uk` and `ru` localized values;
- set CSS classes in rich text where needed, sanitized by existing renderer.

**Step 3: Run targeted tests**

Run:

```bash
SECRET_KEY=test_local_secret /Users/zainllw0w/TwoComms/site/.venv/bin/python twocomms/manage.py test storefront.tests.test_blog_structured --settings=test_settings
```

Expected: pass targeted structured blog tests.

### Task 3: Reusable Blog Landing Styling

**Files:**
- Modify: `twocomms/twocomms_django_theme/static/css/styles.css`
- Modify: `twocomms/twocomms_django_theme/static/css/styles.purged.css`
- Modify: `twocomms/storefront/tests/test_blog_structured.py`

**Step 1: Write CSS coverage test**

Extend the built CSS test to assert the reusable classes exist in `styles.purged.css`, for example:

- `.article-mini-landing`
- `.article-scenario-grid`
- `.article-checklist-grid`
- `.article-keyword-cloud`
- `.article-final-cta`

**Step 2: Verify red**

Run `test_blog_structured` and confirm the CSS class test fails.

**Step 3: Add CSS**

Append a scoped `/* === Blog Custom Print Landing Blocks === */` section to both CSS files. Keep classes responsive and compatible with existing dark blog styling.

**Step 4: Verify green**

Run the targeted test again.

### Task 4: Local Integration Checks

**Files:**
- No new files unless tests require a narrow adjustment.

**Step 1: Run command locally**

Run:

```bash
SECRET_KEY=test_local_secret /Users/zainllw0w/TwoComms/site/.venv/bin/python twocomms/manage.py publish_custom_print_blog --settings=test_settings
```

Expected: command reports 10 posts created/updated.

**Step 2: Run broader blog and SEO tests**

Run:

```bash
SECRET_KEY=test_local_secret /Users/zainllw0w/TwoComms/site/.venv/bin/python twocomms/manage.py test storefront.tests.test_blog storefront.tests.test_blog_structured storefront.tests.test_seo_multilingual_index_2026_05_15 --settings=test_settings
```

Expected: all pass.

**Step 3: Run Django checks**

Run:

```bash
SECRET_KEY=test_local_secret /Users/zainllw0w/TwoComms/site/.venv/bin/python twocomms/manage.py check --settings=test_settings
SECRET_KEY=test_local_secret /Users/zainllw0w/TwoComms/site/.venv/bin/python twocomms/manage.py makemigrations --check --dry-run --settings=test_settings
git diff --check
```

Expected: all pass and no migrations required.

### Task 5: Commit, Push, Deploy, Publish Content

**Files:**
- Stage only files touched by this task.

**Step 1: Inspect status**

Run `git status --short`.

**Step 2: Commit scoped changes**

Stage only:

- docs/plans files;
- command file;
- blog tests;
- CSS files.

Commit with a scoped message.

**Step 3: Push**

Push current branch.

**Step 4: Deploy code**

Use the user-provided SSH workflow without saving secrets. On production:

```bash
git pull --ff-only
python manage.py collectstatic --no-input
python manage.py compress --force
python manage.py check
touch tmp/restart.txt
```

No migrate is expected unless migrations appear unexpectedly.

**Step 5: Publish content on production**

Run in the same production venv/repo:

```bash
python manage.py publish_custom_print_blog
touch tmp/restart.txt
```

**Step 6: Live verification**

Verify:

- `/blog/` returns 200;
- one UA article route returns 200 and includes `index, follow`, `/custom-print/`, FAQ schema;
- one RU article route returns 200 and Russian content;
- `/sitemap-blog.xml` includes the new article URLs;
- category `/blog/category/guides/custom-print-guides/` returns 200 and is not `noindex`.

