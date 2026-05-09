/**
 * Phase 8 — Sync the product-detail URL + browser tab title with the
 * user's current colour / size / fit selection without reloading the
 * page.
 *
 * The server-rendered HTML already includes everything we need for
 * variant logic (offer ids, swatches, fit options, etc.). All this
 * module does is observe the existing change events and:
 *
 *   1. Build a path-style URL `/product/<slug>/<color>/<size>/<fit>/`
 *      using the data exposed by the template (slug + base path on
 *      `#product-detail-container`, slug on each `.color-swatch`).
 *   2. Use `history.replaceState` (NOT pushState — we don't want a
 *      back-button entry per click) to keep the address bar honest.
 *   3. Update `document.title` and `<link rel=canonical>` so the
 *      browser tab + share-sheet metadata reflect the selection.
 *
 * Canonical strategy mirrors Phase 7.3:
 *   * 0 segments         → canonical = base path.
 *   * 1 segment          → canonical = current path (self).
 *   * 2 or 3 segments    → canonical = base path (consolidate signal).
 */
(function () {
  'use strict';

  const container = document.getElementById('product-detail-container');
  if (!container) return;

  const basePath = container.getAttribute('data-product-base-path') || '';
  const productSlug = container.getAttribute('data-product-slug') || '';
  const productTitleBase = container.getAttribute('data-product-title-base') || '';
  if (!basePath || !productSlug) return;

  const colorPicker = document.getElementById('color-picker');
  const fitSelector = document.querySelector('[data-fit-selector]');

  function getActiveColorSegment() {
    if (!colorPicker) return '';
    const active = colorPicker.querySelector('.color-swatch.active, .product-color-swatch-compact.active');
    if (!active) return '';
    return (active.getAttribute('data-variant-slug') || '').toLowerCase();
  }

  function getActiveSizeSegment() {
    const checked = document.querySelector('input[name="size"]:checked');
    if (!checked || !checked.value) return '';
    return String(checked.value).toLowerCase();
  }

  function getActiveFitSegment() {
    if (!fitSelector) return '';
    const checked = fitSelector.querySelector('input[name="fit_option"]:checked');
    if (!checked || !checked.value) return '';
    return String(checked.value).toLowerCase();
  }

  function buildVariantPath() {
    const color = getActiveColorSegment();
    const size = getActiveSizeSegment();
    const fit = getActiveFitSegment();
    const segments = [color, size, fit].filter(Boolean);
    if (segments.length === 0) return basePath;
    // Trim trailing slash from base, then re-append.
    const base = basePath.endsWith('/') ? basePath.slice(0, -1) : basePath;
    return `${base}/${segments.join('/')}/`;
  }

  function buildCanonicalPath() {
    const color = getActiveColorSegment();
    const size = getActiveSizeSegment();
    const fit = getActiveFitSegment();
    const segments = [color, size, fit].filter(Boolean);
    // Match Phase 7.3: self for 0/1, base for 2+.
    if (segments.length <= 1) return buildVariantPath();
    return basePath;
  }

  function buildVariantTitle() {
    const colorButton = colorPicker
      ? colorPicker.querySelector('.color-swatch.active, .product-color-swatch-compact.active')
      : null;
    const colorName = colorButton
      ? (colorButton.parentElement && colorButton.parentElement.querySelector('span:not(.tc-color-dot)')
          ? colorButton.parentElement.querySelector('span:not(.tc-color-dot)').textContent.trim()
          : '')
      : '';
    const size = getActiveSizeSegment().toUpperCase();
    const fitInput = fitSelector
      ? fitSelector.querySelector('input[name="fit_option"]:checked')
      : null;
    const fitLabel = fitInput
      ? (fitSelector.querySelector(`label[for="${fitInput.id}"]`)?.textContent || '').trim()
      : '';

    const parts = [];
    if (colorName) parts.push(colorName.toLowerCase());
    if (size) parts.push(`розмір ${size}`);
    if (fitLabel) parts.push(fitLabel.toLowerCase());

    if (!parts.length) return '';
    return `Купити ${productTitleBase} — ${parts.join(', ')} — TwoComms`;
  }

  function syncUrlAndTitle() {
    try {
      const newPath = buildVariantPath();
      const currentSearch = window.location.search || '';
      const currentHash = window.location.hash || '';
      // replaceState — no back-button noise from picking a colour.
      // We DO keep query params (utm/gclid/etc) intact so the user's
      // session keeps its tracking context.
      if (window.location.pathname !== newPath) {
        window.history.replaceState(
          window.history.state,
          '',
          `${newPath}${currentSearch}${currentHash}`
        );
      }

      const variantTitle = buildVariantTitle();
      if (variantTitle) {
        document.title = variantTitle;
      }

      const canonicalLink = document.querySelector('link[rel="canonical"]');
      if (canonicalLink) {
        const origin = window.location.origin;
        canonicalLink.setAttribute('href', `${origin}${buildCanonicalPath()}`);
      }
    } catch (err) {
      // Defensive: pushState in some embedded webviews can throw —
      // we never want to break the variant picker over a URL sync.
      if (window.console && console.debug) {
        console.debug('[Phase 8] URL sync failed:', err);
      }
    }
  }

  // The existing initColorSelection / initSizeSelection / initFitSelection
  // functions in product-detail.js attach their own listeners. We just
  // piggyback on the same DOM events without interfering.
  if (colorPicker) {
    colorPicker.addEventListener('click', (event) => {
      if (event.target.closest('.color-swatch, .product-color-swatch-compact')) {
        // Defer one tick so the existing handler can flip ``.active``
        // before we read it.
        setTimeout(syncUrlAndTitle, 0);
      }
    });
  }

  document.querySelectorAll('input[name="size"]').forEach((input) => {
    input.addEventListener('change', syncUrlAndTitle);
  });

  if (fitSelector) {
    fitSelector.querySelectorAll('input[name="fit_option"]').forEach((input) => {
      input.addEventListener('change', syncUrlAndTitle);
    });
  }
})();
