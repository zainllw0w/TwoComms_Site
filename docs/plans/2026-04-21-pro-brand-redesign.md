# Pro Brand Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Убрать хрупкий scroll-stage со страницы `/pro-brand/`, пересобрать её в стабильную premium brand-story композицию с video-stage placeholder, не ломая SEO и существующий route.

**Architecture:** Реализация ограничивается isolated surface страницы `pro_brand`: шаблон, stylesheet, page-specific JS и связанный тестовый контракт. Layout становится линейным и устойчивым, scroll-state логика удаляется, а движение сводится к enhancement-уровню, который не влияет на геометрию страницы.

**Tech Stack:** Django templates, page-scoped CSS, vanilla JS, Django TestCase, browser validation.

---

### Task 1: Зафиксировать новый контракт страницы в тестах

**Files:**
- Modify: `twocomms/storefront/tests/test_static_support_pages.py`
- Modify: `twocomms/storefront/tests/test_seo_regressions.py`

**Step 1: Обновить ожидания about/pro-brand страницы**

- Убрать утверждения, привязанные к старой scroll-механике:
  - `self.assertContains(response, 'data-brand-scroll', html=False)`
- Добавить проверки нового контракта:
  - наличие `class="pro-brand-page"`
  - наличие breadcrumb
  - наличие нового video-stage marker, например `data-pro-brand-video`
  - наличие FAQ schema

**Step 2: Запустить только эти тесты и убедиться, что они падают на старом контракте**

Run:

```bash
pytest twocomms/storefront/tests/test_static_support_pages.py -k about_page_uses_dedicated_brand_layout -v
pytest twocomms/storefront/tests/test_seo_regressions.py -k about_page_uses_brand_story_layout -v
```

Expected:

- FAIL, потому что шаблон всё ещё содержит старые маркеры либо не содержит новый video-stage marker.

**Step 3: Не трогать route/redirect expectations**

- Тесты на `/about/ -> /pro-brand/` redirect не менять.
- Тесты на canonical and llms/sitemap оставить как guardrails.

**Step 4: Commit**

```bash
git add twocomms/storefront/tests/test_static_support_pages.py twocomms/storefront/tests/test_seo_regressions.py
git commit -m "test: update pro-brand page contract"
```

### Task 2: Пересобрать шаблон страницы как линейную brand-story

**Files:**
- Modify: `twocomms/twocomms_django_theme/templates/pages/pro_brand.html`

**Step 1: Удалить старую scroll-storytelling структуру**

- Удалить или полностью переписать блок:
  - `section.pro-brand-scroll`
  - элементы `.pro-brand-stage*`
  - `data-brand-scroll`
  - `data-step`
  - `data-screen`

**Step 2: Вставить новый manifesto/video narrative**

- Сохранить:
  - SEO-блоки в `<head>`
  - breadcrumbs
  - hero, summary, FAQ, CTA как смысловые зоны
- Пересобрать среднюю часть страницы в такой порядок:
  1. manifesto section
  2. video stage section with `data-pro-brand-video`
  3. supporting story sections for origin / Kharkiv / print codes / quality / audience

**Step 3: Переписать текст локально в шаблоне**

- Сократить повторяющиеся абзацы.
- Сохранить ключевые фразы:
  - `Харків`
  - `streetwear / military-adjacent`
  - `не крапка`
  - `продовження`
  - `код`
  - `якість`
- Сделать копирайтинг более плотным, премиальным и scan-friendly.

**Step 4: Подготовить video placeholder под будущий embed**

- Добавить оболочку с:
  - eyebrow / small label
  - заголовком
  - текстом-контекстом
  - media frame
  - play-mark / preview overlay
- Не вставлять реальный iframe на этом этапе.
- Структуру сделать такой, чтобы позже можно было заменить preview-layer на iframe без перестройки всей секции.

**Step 5: Commit**

```bash
git add twocomms/twocomms_django_theme/templates/pages/pro_brand.html
git commit -m "feat: rebuild pro-brand narrative layout"
```

### Task 3: Пересобрать стили и упростить page JS

**Files:**
- Modify: `twocomms/twocomms_django_theme/static/css/pro-brand.css`
- Modify: `twocomms/twocomms_django_theme/static/js/pro-brand.js`

**Step 1: Удалить scroll-stage specific CSS**

- Удалить или переписать правила, обслуживающие:
  - `.pro-brand-scroll__stage`
  - `.pro-brand-stage*`
  - progress-driven 3D transform
  - sticky-dependent layout assumptions

**Step 2: Ввести новый секционный visual system**

- Для hero оставить full-bleed mood, но улучшить spacing и пропорции.
- Для manifesto и story sections использовать более спокойные панели и секционные разрывы вместо одинакового набора карточек.
- Для video-stage задать:
  - framed shell
  - controlled glow
  - responsive `aspect-ratio`
  - desktop/mobile stable min/max sizing
- Проверить, что нет больших пустых vertical gaps.

**Step 3: Привести motion к enhancement-only уровню**

- Reveal и hover оставить лёгкими.
- Любые transform/opacity паттерны не должны влиять на layout height.
- Под `prefers-reduced-motion: reduce` убрать декоративную motion-нагрузку.

**Step 4: Упростить JS**

- Удалить `IntersectionObserver` и любую логику переключения `.is-active` между scroll steps/screens.
- Если нужен JS, оставить только мягкие enhancement-паттерны, не обязательные для корректного рендера.
- Если JS больше не нужен, свести файл к безопасному no-op или удалить подключаемую логику так, чтобы template не ломался.

**Step 5: Commit**

```bash
git add twocomms/twocomms_django_theme/static/css/pro-brand.css twocomms/twocomms_django_theme/static/js/pro-brand.js
git commit -m "feat: stabilize pro-brand visuals and motion"
```

### Task 4: Проверка, браузерная валидация и deploy gate

**Files:**
- Modify if needed: `twocomms/storefront/tests/test_static_support_pages.py`
- Modify if needed: `twocomms/storefront/tests/test_seo_regressions.py`

**Step 1: Прогнать релевантные тесты**

Run:

```bash
pytest twocomms/storefront/tests/test_static_support_pages.py -v
pytest twocomms/storefront/tests/test_seo_regressions.py -v
```

Expected:

- PASS

**Step 2: Выполнить targeted browser validation**

Run local app and verify `/pro-brand/` in browser:

- desktop width
- mobile width
- scroll from hero to CTA
- absence of giant empty block
- stable video-stage proportions
- readable CTA and FAQ

**Step 3: Regression checklist**

- Canonical still points to `/pro-brand/`
- FAQ schema still present
- breadcrumbs still present
- route `/about/` still redirects
- no clipped left/right content
- no layout shift caused by removed sticky stage

**Step 4: Deploy gate**

Deploy only if:

- tests pass,
- browser validation passes,
- template semantics and SEO contract preserved.

If deploy is needed, use existing project deployment flow for Django hosting and then run a post-deploy smoke check on live `/pro-brand/`.

**Step 5: Final commit**

```bash
git add twocomms/twocomms_django_theme/templates/pages/pro_brand.html \
        twocomms/twocomms_django_theme/static/css/pro-brand.css \
        twocomms/twocomms_django_theme/static/js/pro-brand.js \
        twocomms/storefront/tests/test_static_support_pages.py \
        twocomms/storefront/tests/test_seo_regressions.py
git commit -m "feat: redesign and stabilize pro-brand page"
```
