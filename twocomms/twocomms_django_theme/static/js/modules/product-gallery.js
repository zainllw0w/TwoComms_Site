/**
 * Product detail gallery — lazy-mounted на страницах товара (Phase 2.1 ext).
 *
 * Активируется только если в DOM есть одновременно:
 *   - #variant-data  (JSON список color-variants)
 *   - #color-picker  (color swatches)
 *   - #productCarousel (Bootstrap carousel)
 *
 * На главной, каталоге, cart, checkout — эти селекторы отсутствуют,
 * модуль никогда не грузится.
 */

import { escapeHtml } from './shared.js';

export function initProductGallery() {
  const variantTag = document.getElementById('variant-data');
  const colorPicker = document.getElementById('color-picker');
  const carousel = document.getElementById('productCarousel');
  if (!variantTag || !colorPicker || !carousel) return;

  const bindPointsModal = () => {
    const pointsInfoModal = document.getElementById('pointsInfoModal');
    if (pointsInfoModal) {
      pointsInfoModal.addEventListener('show.bs.modal', function (event) {
        const button = event.relatedTarget;
        if (!button) return;
        const title = button.getAttribute('data-product-title');
        const points = button.getAttribute('data-points-amount');
        const t = document.getElementById('modalProductTitle');
        const p = document.getElementById('modalPointsAmount');
        if (t) t.textContent = title || '';
        if (p) p.textContent = points || '0';
      });
    }
  };

  if (carousel.dataset.galleryInitialized === '1') {
    bindPointsModal();
    return;
  }

  let variants = [];
  try { variants = JSON.parse(variantTag.textContent || '[]'); } catch (_) { variants = []; }

  const inner = carousel.querySelector('.carousel-inner');
  const indicators = carousel.querySelector('.carousel-indicators');
  const thumbs = document.getElementById('product-thumbs');

  function rebuild(images) {
    if (!(inner && indicators && thumbs)) return;
    inner.innerHTML = '';
    indicators.innerHTML = '';
    thumbs.innerHTML = '';
    const mainImg = document.getElementById('mainImage');
    const fallbackSrc = mainImg ? mainImg.src : '';
    const list = (images && images.length) ? images : [fallbackSrc];
    list.forEach((url, idx) => {
      const item = document.createElement('div');
      item.className = 'carousel-item' + (idx === 0 ? ' active' : '');
      const safeUrl = escapeHtml(url);
      item.innerHTML = '<img src="' + safeUrl + '" class="d-block w-100 h-100 object-fit-contain" alt="Фото товару">';
      inner.appendChild(item);

      const ind = document.createElement('button');
      ind.type = 'button';
      ind.setAttribute('data-bs-target', '#productCarousel');
      ind.setAttribute('data-bs-slide-to', String(idx));
      if (idx === 0) {
        ind.className = 'active';
        ind.setAttribute('aria-current', 'true');
      }
      indicators.appendChild(ind);

      const th = document.createElement('button');
      th.type = 'button';
      th.className = 'btn p-0 thumb';
      th.setAttribute('data-bs-target', '#productCarousel');
      th.setAttribute('data-bs-slide-to', String(idx));
      th.innerHTML = '<img src="' + safeUrl + '" class="rounded-3 object-fit-cover" style="width:72px;height:72px;" alt="Мініатюра">';
      thumbs.appendChild(th);
    });
  }

  function onColorClick(btn) {
    const id = parseInt(btn.getAttribute('data-variant') || '-1', 10);
    const v = variants.find(x => x.id === id);
    if (!v) return;
    colorPicker.querySelectorAll('.color-swatch').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    rebuild(v.images || []);
  }

  if (variants.length) {
    const def = variants.find(v => v.is_default) || variants[0];
    rebuild(def && def.images ? def.images : []);
  }
  colorPicker.querySelectorAll('.color-swatch').forEach(b => b.addEventListener('click', () => onColorClick(b)));
  carousel.dataset.galleryInitialized = '1';
  bindPointsModal();
}
