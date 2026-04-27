(function () {
  'use strict';

  const prefersReducedMotion = window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  document.addEventListener('DOMContentLoaded', initProductDetail);

  function initProductDetail() {
    const root = document.querySelector('[data-pdp]');
    const container = document.getElementById('product-detail-container');
    if (!root || !container) return;

    const state = {
      root,
      container,
      variants: readJsonScript('variant-data', []),
      extraImages: readJsonScript('product-extra-images', []),
      offerIdMap: readOfferMap(container),
      mainImage: document.getElementById('mainProductImage'),
      thumbs: document.getElementById('productThumbnails'),
      viewContentTracked: false,
    };

    initGallery(state);
    initColorSelection(state);
    initSizeSelection(state);
    initFitSelection(root);
    initTabs(root);
    initShare(root, container);
    initZoom(state);
    initStickyAdd(root);
    updateCurrentOfferId(state);
    trackViewContent(state);
  }

  function readJsonScript(id, fallback) {
    const node = document.getElementById(id);
    if (!node) return fallback;
    try {
      const parsed = JSON.parse(node.textContent || '');
      return parsed == null ? fallback : parsed;
    } catch (_) {
      return fallback;
    }
  }

  function readOfferMap(container) {
    const scriptMap = readJsonScript('offer-id-map', null);
    if (scriptMap && typeof scriptMap === 'object') return scriptMap;
    try {
      return JSON.parse(container.getAttribute('data-offer-id-map') || '{}') || {};
    } catch (_) {
      return {};
    }
  }

  function uniqueImages(images) {
    const seen = new Set();
    return (images || []).filter((url) => {
      if (!url || seen.has(url)) return false;
      seen.add(url);
      return true;
    });
  }

  function baseImages(state) {
    const initial = state.mainImage
      ? (state.mainImage.getAttribute('data-initial-image') || state.mainImage.currentSrc || state.mainImage.src)
      : '';
    return uniqueImages([initial].concat(state.extraImages || []));
  }

  function activeVariant(state) {
    const active = state.root.querySelector('#color-picker .color-swatch.active');
    if (!active) return null;
    const id = Number(active.getAttribute('data-variant') || 0);
    return (state.variants || []).find((variant) => Number(variant.id) === id) || null;
  }

  function imagesForCurrentSelection(state) {
    const variant = activeVariant(state);
    if (variant && Array.isArray(variant.images) && variant.images.length) {
      return uniqueImages(variant.images);
    }
    return baseImages(state);
  }

  function initGallery(state) {
    if (!state.mainImage || !state.thumbs) return;
    const images = imagesForCurrentSelection(state);
    renderThumbnails(state, images);
    initThumbnailNav(state);
    if (images[0]) {
      setMainImage(state, images[0], { immediate: true });
    }
  }

  function renderThumbnails(state, images) {
    if (!state.thumbs) return;
    state.thumbs.innerHTML = '';

    images.forEach((url, index) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `tc-thumbnail${index === 0 ? ' active' : ''}`;
      button.setAttribute('aria-label', `Фото товару ${index + 1}`);
      button.dataset.image = url;

      const img = document.createElement('img');
      img.src = url;
      img.alt = '';
      img.loading = index === 0 ? 'eager' : 'lazy';
      img.decoding = 'async';

      button.appendChild(img);
      button.addEventListener('click', () => {
        state.thumbs.querySelectorAll('.tc-thumbnail').forEach((item) => item.classList.remove('active'));
        button.classList.add('active');
        setMainImage(state, url);
      });
      state.thumbs.appendChild(button);
    });
  }

  function initThumbnailNav(state) {
    const prev = state.root.querySelector('[data-thumb-prev]');
    const next = state.root.querySelector('[data-thumb-next]');
    if (!prev || !next || prev.dataset.bound === '1') return;
    prev.dataset.bound = '1';
    next.dataset.bound = '1';

    const scrollByThumb = (direction) => {
      if (!state.thumbs) return;
      const firstThumb = state.thumbs.querySelector('.tc-thumbnail');
      const amount = firstThumb ? firstThumb.getBoundingClientRect().width + 12 : 124;
      state.thumbs.scrollBy({ left: direction * amount, behavior: prefersReducedMotion ? 'auto' : 'smooth' });
    };

    prev.addEventListener('click', () => scrollByThumb(-1));
    next.addEventListener('click', () => scrollByThumb(1));
  }

  function setMainImage(state, url, options) {
    if (!state.mainImage || !url) return;
    const immediate = options && options.immediate;
    if (state.mainImage.getAttribute('src') === url && !immediate) return;

    const apply = () => {
      if (!immediate) {
        clearResponsiveSources(state.mainImage);
      }
      state.mainImage.src = url;
      state.mainImage.setAttribute('data-zoom', url);
      state.mainImage.classList.remove('is-switching');
    };

    if (immediate || prefersReducedMotion) {
      apply();
      return;
    }

    state.mainImage.classList.add('is-switching');
    preloadImage(url)
      .then(() => window.setTimeout(apply, 60))
      .catch(() => window.setTimeout(apply, 90));
  }

  function clearResponsiveSources(image) {
    const picture = image && image.closest ? image.closest('picture') : null;
    if (!picture) return;
    picture.querySelectorAll('source').forEach((source) => {
      source.removeAttribute('srcset');
      source.removeAttribute('sizes');
    });
  }

  function preloadImage(url) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        if (img.decode) {
          img.decode().then(resolve).catch(resolve);
        } else {
          resolve();
        }
      };
      img.onerror = reject;
      img.src = url;
    });
  }

  function initColorSelection(state) {
    const swatches = Array.from(state.root.querySelectorAll('#color-picker .color-swatch'));
    if (!swatches.length) return;

    swatches.forEach((button) => {
      button.addEventListener('click', () => {
        swatches.forEach((item) => item.classList.remove('active'));
        button.classList.add('active');
        state.container.dataset.currentVariant = button.getAttribute('data-variant') || 'default';
        const images = imagesForCurrentSelection(state);
        renderThumbnails(state, images);
        if (images[0]) setMainImage(state, images[0]);
        const offerId = updateCurrentOfferId(state);
        trackCustomizeProduct(state, button.getAttribute('data-variant'), offerId);
      });
    });
  }

  function initSizeSelection(state) {
    selectSizeFromURL();
    state.root.querySelectorAll('input[name="size"]').forEach((input) => {
      input.addEventListener('change', () => {
        updateCurrentOfferId(state);
      });
    });
  }

  function selectSizeFromURL() {
    const sizeParam = new URLSearchParams(window.location.search).get('size');
    if (!sizeParam) return;
    const wanted = sizeParam.toUpperCase();
    const input = Array.from(document.querySelectorAll('input[name="size"]'))
      .find((item) => String(item.value || '').toUpperCase() === wanted);
    if (input && !input.checked) {
      input.checked = true;
      input.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }

  function currentSelection(state) {
    const color = state.root.querySelector('#color-picker .color-swatch.active');
    const sizeInput = state.root.querySelector('input[name="size"]:checked');
    const colorVariantId = color ? color.getAttribute('data-variant') : null;
    const size = sizeInput ? String(sizeInput.value || '').toUpperCase() : '';
    const key = `${colorVariantId || 'default'}:${size}`;
    const fallback = state.container.getAttribute('data-current-offer-id') ||
      state.container.getAttribute('data-default-offer-id') ||
      '';

    return {
      colorVariantId,
      size,
      key,
      offerId: state.offerIdMap[key] || fallback,
    };
  }

  function updateCurrentOfferId(state) {
    const selection = currentSelection(state);
    if (selection.offerId) {
      state.container.setAttribute('data-current-offer-id', selection.offerId);
    }
    return selection.offerId;
  }

  function initFitSelection(root) {
    const selector = root.querySelector('[data-fit-selector]');
    if (!selector) return;

    const options = Array.from(selector.querySelectorAll('[data-fit-option]'));
    selector.querySelectorAll('input[name="fit_option"]').forEach((input) => {
      input.addEventListener('change', () => {
        options.forEach((option) => option.classList.remove('active'));
        const label = selector.querySelector(`label[for="${input.id}"]`);
        if (label) label.classList.add('active');
        const container = document.getElementById('product-detail-container');
        if (container) container.dataset.currentFit = input.value || '';
      });
    });
  }

  function initTabs(root) {
    const tabs = Array.from(root.querySelectorAll('[data-pdp-tab]'));
    const panels = Array.from(root.querySelectorAll('[data-pdp-panel]'));
    if (!tabs.length || !panels.length) return;

    const activateTab = (tab, focus) => {
        const target = tab.getAttribute('data-pdp-tab');
        tabs.forEach((item) => {
          const active = item === tab;
          item.classList.toggle('active', active);
          item.setAttribute('aria-selected', active ? 'true' : 'false');
          item.setAttribute('tabindex', active ? '0' : '-1');
        });
        panels.forEach((panel) => {
          const active = panel.getAttribute('data-pdp-panel') === target;
          panel.classList.toggle('active', active);
          panel.hidden = !active;
        });
        tab.scrollIntoView({ block: 'nearest', inline: 'nearest' });
        if (focus) tab.focus();
    };

    tabs.forEach((tab, index) => {
      tab.setAttribute('tabindex', tab.classList.contains('active') ? '0' : '-1');
      tab.addEventListener('click', () => activateTab(tab, false));
      tab.addEventListener('keydown', (event) => {
        const keys = ['ArrowLeft', 'ArrowRight', 'Home', 'End'];
        if (!keys.includes(event.key)) return;
        event.preventDefault();
        let nextIndex = index;
        if (event.key === 'ArrowLeft') nextIndex = (index - 1 + tabs.length) % tabs.length;
        if (event.key === 'ArrowRight') nextIndex = (index + 1) % tabs.length;
        if (event.key === 'Home') nextIndex = 0;
        if (event.key === 'End') nextIndex = tabs.length - 1;
        activateTab(tabs[nextIndex], true);
      });
    });

    root.querySelectorAll('[data-pdp-tab-trigger]').forEach((button) => {
      button.addEventListener('click', () => {
        const target = button.getAttribute('data-pdp-tab-trigger');
        const tab = tabs.find((item) => item.getAttribute('data-pdp-tab') === target);
        if (tab) activateTab(tab, true);
      });
    });
  }

  function initShare(root, container) {
    const buttons = root.querySelectorAll('[data-share-action], [data-share-copy]');
    if (!buttons.length) return;

    buttons.forEach((button) => {
      if (button.dataset.shareBound === '1') return;
      button.dataset.shareBound = '1';
      button.addEventListener('click', async () => {
        const action = button.getAttribute('data-share-action') || 'copy';
        const shareData = buildShareData(root, container);

        if (action === 'native') {
          const shared = await tryNativeShare(shareData);
          if (shared) {
            trackShareAction('native', shareData.url);
            pulseShareButton(button, 'is-shared');
            return;
          }
          await copyShareUrl(button, shareData.url);
          return;
        }

        if (action === 'copy') {
          await copyShareUrl(button, shareData.url);
          return;
        }

        if (action === 'telegram') {
          trackShareAction(action, shareData.url);
          openTelegramShare(shareData);
          return;
        }

        const providerUrl = buildProviderShareUrl(action, shareData);
        if (!providerUrl) return;
        trackShareAction(action, shareData.url);
        openShareTarget(providerUrl);
      });
    });
  }

  function buildShareData(root, container) {
    const title = decodeDataValue(container.getAttribute('data-product-title')) || cleanDocumentTitle();
    const category = decodeDataValue(container.getAttribute('data-product-category'));
    const text = category ? `${title} — ${category} від TwoComms` : `${title} — TwoComms`;
    return {
      title,
      text,
      url: buildShareUrl(root, container),
    };
  }

  function buildShareUrl(root, container) {
    const canonical = document.querySelector('link[rel="canonical"]');
    const rawUrl = (canonical && canonical.href) ||
      container.getAttribute('data-share-url') ||
      window.location.href;
    let url;
    try {
      url = new URL(rawUrl, window.location.href);
    } catch (_) {
      return window.location.href;
    }

    url.hash = '';
    url.search = '';

    const sizeInput = root.querySelector('input[name="size"]:checked');
    const size = sizeInput ? String(sizeInput.value || '').toUpperCase() : '';
    if (size) url.searchParams.set('size', size);

    const color = root.querySelector('#color-picker .color-swatch.active');
    const colorId = color ? color.getAttribute('data-variant') : '';
    if (colorId && colorId !== 'default') url.searchParams.set('color', colorId);

    return url.toString();
  }

  async function tryNativeShare(shareData) {
    if (!navigator.share) return false;
    const payload = {
      title: shareData.title,
      text: shareData.text,
      url: shareData.url,
    };

    try {
      if (navigator.canShare && !navigator.canShare(payload)) return false;
    } catch (_) { }

    try {
      await navigator.share(payload);
      return true;
    } catch (_) {
      return false;
    }
  }

  function buildProviderShareUrl(action, shareData) {
    const url = encodeURIComponent(shareData.url);
    const text = encodeURIComponent(shareData.text);

    if (action === 'telegram') {
      return `https://t.me/share/url?url=${url}&text=${text}`;
    }
    if (action === 'facebook') {
      return `https://www.facebook.com/sharer/sharer.php?u=${url}`;
    }
    if (action === 'x') {
      return `https://twitter.com/intent/tweet?url=${url}&text=${text}`;
    }
    return '';
  }

  function openTelegramShare(shareData) {
    const webUrl = buildProviderShareUrl('telegram', shareData);
    if (!isLikelyMobile()) {
      openShareTarget(webUrl);
      return;
    }

    const appUrl = `tg://msg_url?url=${encodeURIComponent(shareData.url)}&text=${encodeURIComponent(shareData.text)}`;
    window.location.href = appUrl;
    window.setTimeout(() => {
      if (document.visibilityState === 'visible') {
        window.location.href = webUrl;
      }
    }, 850);
  }

  function isLikelyMobile() {
    return window.matchMedia && window.matchMedia('(max-width: 767.98px), (pointer: coarse)').matches;
  }

  function openShareTarget(url) {
    const popup = window.open(url, '_blank', 'width=760,height=620');
    if (popup && typeof popup.focus === 'function') {
      try {
        popup.opener = null;
      } catch (_) { }
      popup.focus();
      return;
    }
    window.location.href = url;
  }

  async function copyShareUrl(button, url) {
    const copied = await copyToClipboard(url);
    if (!copied) return;
    trackShareAction('copy', url);
    pulseShareButton(button, 'is-copied');
  }

  function pulseShareButton(button, className) {
    button.classList.add(className);
    window.setTimeout(() => button.classList.remove(className), 1400);
  }

  function trackShareAction(method, url) {
    try {
      window.dataLayer = window.dataLayer || [];
      window.dataLayer.push({
        event: 'share_product',
        event_id: makeEventId(),
        method,
        product_url: url,
      });
    } catch (_) { }
  }

  function cleanDocumentTitle() {
    return String(document.title || 'TwoComms').replace(/\s*[|—-]\s*TwoComms.*$/i, '').trim() || 'TwoComms';
  }

  function decodeDataValue(value) {
    if (!value) return '';
    return String(value)
      .replace(/\\u([0-9a-fA-F]{4})/g, (_, code) => String.fromCharCode(Number.parseInt(code, 16)))
      .replace(/\\x27/g, "'")
      .replace(/\\"/g, '"')
      .replace(/\\\\/g, '\\')
      .trim();
  }

  async function copyToClipboard(value) {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(value);
        return true;
      }
    } catch (_) { }

    const input = document.createElement('textarea');
    input.value = value;
    input.setAttribute('readonly', '');
    input.style.position = 'fixed';
    input.style.top = '-1000px';
    document.body.appendChild(input);
    input.select();
    let ok = false;
    try {
      ok = document.execCommand('copy');
    } catch (_) {
      ok = false;
    }
    input.remove();
    return ok;
  }

  function initZoom(state) {
    const buttons = state.root.querySelectorAll('[data-gallery-zoom]');
    if (!buttons.length || !state.mainImage) return;

    buttons.forEach((button) => {
      button.addEventListener('click', () => openLightbox(state.mainImage.getAttribute('data-zoom') || state.mainImage.src, state.mainImage.alt));
    });
  }

  function openLightbox(src, alt) {
    if (!src) return;
    const overlay = document.createElement('div');
    overlay.className = 'tc-lightbox';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');

    const close = document.createElement('button');
    close.type = 'button';
    close.setAttribute('aria-label', 'Закрити фото');
    close.textContent = '×';

    const img = document.createElement('img');
    img.src = src;
    img.alt = alt || '';

    overlay.appendChild(close);
    overlay.appendChild(img);
    document.body.appendChild(overlay);
    document.body.style.overflow = 'hidden';

    const remove = () => {
      overlay.classList.remove('is-visible');
      window.setTimeout(() => {
        overlay.remove();
        document.body.style.overflow = '';
      }, prefersReducedMotion ? 0 : 160);
      document.removeEventListener('keydown', onKeydown);
    };
    const onKeydown = (event) => {
      if (event.key === 'Escape') remove();
    };

    overlay.addEventListener('click', (event) => {
      if (event.target === overlay) remove();
    });
    close.addEventListener('click', remove);
    document.addEventListener('keydown', onKeydown);
    window.requestAnimationFrame(() => overlay.classList.add('is-visible'));
  }

  function initStickyAdd(root) {
    const stickyBar = root.querySelector('#productStickyMobile');
    const stickyButton = root.querySelector('[data-pdp-sticky-add]');
    const mainButton = root.querySelector('.tc-add-btn[data-add-to-cart]');
    if (!stickyButton || !mainButton) return;

    stickyButton.addEventListener('click', () => {
      mainButton.click();
    });

    if (!stickyBar) return;

    const mediaPanel = root.querySelector('.tc-gallery-card') || root.querySelector('.tc-media-stage');
    const purchaseBar = root.querySelector('#product-action-bar');
    const mobileQuery = window.matchMedia('(max-width: 767.98px)');

    const updateStickyVisibility = () => {
      if (!mobileQuery.matches) {
        stickyBar.classList.remove('is-visible');
        return;
      }

      const mediaBottom = mediaPanel ? mediaPanel.getBoundingClientRect().bottom : 0;
      const purchaseRect = purchaseBar ? purchaseBar.getBoundingClientRect() : null;
      const purchaseVisible = purchaseRect && purchaseRect.top < window.innerHeight - 110 && purchaseRect.bottom > 0;
      const hasPassedMedia = mediaBottom < 88;
      stickyBar.classList.toggle('is-visible', hasPassedMedia && !purchaseVisible);
    };

    updateStickyVisibility();
    window.addEventListener('scroll', updateStickyVisibility, { passive: true });
    window.addEventListener('resize', updateStickyVisibility);
    if (mobileQuery.addEventListener) {
      mobileQuery.addEventListener('change', updateStickyVisibility);
    }
  }

  function trackCustomizeProduct(state, variantId, offerId) {
    try {
      if (!window.trackEvent || !offerId) return;
      const payload = document.getElementById('product-analytics-payload');
      const price = parsePrice(payload && payload.dataset.price);
      window.trackEvent('CustomizeProduct', {
        content_ids: [offerId],
        content_type: 'product',
        variant_id: variantId || null,
        value: price,
        currency: 'UAH',
      });
    } catch (_) { }
  }

  function trackViewContent(state) {
    window.setTimeout(() => {
      if (state.viewContentTracked) return;
      const payload = document.getElementById('product-analytics-payload');
      if (!payload || !window.trackEvent) return;

      const selection = currentSelection(state);
      const offerId = selection.offerId || payload.dataset.id;
      const price = parsePrice(payload.dataset.price);
      const title = payload.dataset.title || state.container.getAttribute('data-product-title') || '';
      const category = payload.dataset.category || state.container.getAttribute('data-product-category') || '';
      const eventId = makeEventId();
      const trackingCtx = (typeof window.getTrackingContext === 'function' && window.getTrackingContext()) || {};
      const item = {
        item_id: offerId,
        item_name: title,
        item_brand: 'TwoComms',
        item_category: category || '',
        item_variant: selection.size || '',
        price,
        quantity: 1,
        currency: 'UAH',
      };

      state.viewContentTracked = true;
      window.dataLayer = window.dataLayer || [];
      window.dataLayer.push({
        event: 'view_item',
        event_id: eventId,
        fbp: trackingCtx.fbp || null,
        fbc: trackingCtx.fbc || null,
        ecommerce: {
          currency: 'UAH',
          value: price,
          items: [item],
        },
        eventModel: {
          event_id: eventId,
          value: price,
          currency: 'UAH',
          content_name: title,
          items: [{ id: offerId, name: title, price, quantity: 1 }],
          ecomm_prodid: [offerId],
          ecomm_pagetype: 'product',
          ecomm_totalvalue: price,
        },
      });

      const metaOptions = { event_id: eventId };
      try {
        if (typeof window.buildUserDataForEvent === 'function') {
          const ctx = window.buildUserDataForEvent();
          if (ctx && typeof ctx === 'object') {
            if (ctx.user_data && Object.keys(ctx.user_data).length) metaOptions.user_data = ctx.user_data;
            if (ctx.external_id) metaOptions.external_id = ctx.external_id;
            if (ctx.fbp) metaOptions.fbp = ctx.fbp;
            if (ctx.fbc) metaOptions.fbc = ctx.fbc;
          }
        }
      } catch (_) { }

      window.trackEvent('ViewContent', {
        content_ids: [offerId],
        content_name: title,
        content_type: 'product',
        content_category: category,
        value: price,
        currency: 'UAH',
        contents: [{
          id: offerId,
          quantity: 1,
          item_price: price,
        }],
        event_id: eventId,
        __meta: metaOptions,
      });
    }, 240);
  }

  function parsePrice(value) {
    const parsed = Number.parseFloat(value || '0');
    return Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
  }

  function makeEventId() {
    if (window.__twcAnalytics && typeof window.__twcAnalytics.safeGenerateEventId === 'function') {
      return window.__twcAnalytics.safeGenerateEventId();
    }
    if (typeof window.generateEventId === 'function') {
      return window.generateEventId();
    }
    return `${Date.now()}_${Math.random().toString(36).slice(2, 11)}`;
  }
})();
