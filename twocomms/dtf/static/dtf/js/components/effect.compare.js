(function () {
  const DTF = (window.DTF = window.DTF || {});

  function initCompare(node) {
    if (!node) return null;
    const range = node.querySelector('.compare-range');
    const media = node.querySelector('.compare-media');
    if (!range || !media) return null;

    const clamp = (v, min, max) => Math.min(max, Math.max(min, v));
    const apply = (value) => {
      const pct = clamp(Math.round(Number(value) || 0), 0, 100);
      range.value = String(pct);
      media.style.setProperty('--compare', `${pct}%`);
    };

    const onRangeInput = () => apply(range.value);
    range.addEventListener('input', onRangeInput);

    let dragging = false;
    let pointerId = null;
    const valueByX = (clientX) => {
      const rect = media.getBoundingClientRect();
      if (!rect.width) return Number(range.value || 50);
      const ratio = clamp((clientX - rect.left) / rect.width, 0, 1);
      return ratio * 100;
    };

    const stop = () => {
      dragging = false;
      pointerId = null;
      media.classList.remove('is-dragging');
    };

    const onPointerDown = (event) => {
      dragging = true;
      pointerId = event.pointerId;
      media.classList.add('is-dragging');
      if (media.setPointerCapture) media.setPointerCapture(event.pointerId);
      apply(valueByX(event.clientX));
    };
    const onPointerMove = (event) => {
      if (!dragging) return;
      if (pointerId !== null && event.pointerId !== pointerId) return;
      apply(valueByX(event.clientX));
    };
    const onPointerUp = () => stop();

    if ('PointerEvent' in window) {
      media.addEventListener('pointerdown', onPointerDown);
      media.addEventListener('pointermove', onPointerMove);
      media.addEventListener('pointerup', onPointerUp);
      media.addEventListener('pointercancel', onPointerUp);
      media.addEventListener('lostpointercapture', onPointerUp);
    }

    apply(range.value || 50);

    return function cleanup() {
      range.removeEventListener('input', onRangeInput);
      if ('PointerEvent' in window) {
        media.removeEventListener('pointerdown', onPointerDown);
        media.removeEventListener('pointermove', onPointerMove);
        media.removeEventListener('pointerup', onPointerUp);
        media.removeEventListener('pointercancel', onPointerUp);
        media.removeEventListener('lostpointercapture', onPointerUp);
      }
    };
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('compare', '[data-compare], [data-effect~="compare"]', initCompare);
  }
})();
