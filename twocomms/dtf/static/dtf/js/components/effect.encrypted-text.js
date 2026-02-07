(function () {
  const DTF = (window.DTF = window.DTF || {});
  const CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#@$%';

  function scrambleStep(target, progress) {
    const keep = Math.floor(target.length * progress);
    return target
      .split('')
      .map((char, index) => {
        if (char === ' ' || index <= keep) return char;
        return CHARS[Math.floor(Math.random() * CHARS.length)];
      })
      .join('');
  }

  function initEncryptedText(node, ctx) {
    if (!node) return null;
    const finalText = (node.dataset.encryptedText || node.dataset.encrypted || node.textContent || '').trim();
    if (!finalText) return null;
    node.setAttribute('aria-label', finalText);

    if (ctx && ctx.reducedMotion) {
      node.textContent = finalText;
      return null;
    }

    let rafId = null;
    let started = false;
    const duration = Math.min(900, Math.max(500, finalText.length * 18));
    const startAnimation = () => {
      if (started) return;
      started = true;
      const startedAt = performance.now();
      const frame = (time) => {
        const progress = Math.min(1, (time - startedAt) / duration);
        node.textContent = scrambleStep(finalText, progress);
        if (progress < 1) {
          rafId = window.requestAnimationFrame(frame);
        } else {
          rafId = null;
          node.textContent = finalText;
        }
      };
      rafId = window.requestAnimationFrame(frame);
    };

    if (!('IntersectionObserver' in window)) {
      startAnimation();
      return null;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          startAnimation();
          observer.disconnect();
        });
      },
      { threshold: 0.2 }
    );
    observer.observe(node);

    return function cleanup() {
      observer.disconnect();
      if (rafId !== null) {
        window.cancelAnimationFrame(rafId);
      }
    };
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('encrypted-text', '[data-effect~="encrypted-text"]', initEncryptedText);
  }
})();
