(function () {
  const DTF = (window.DTF = window.DTF || {});

  function initTracingBeam(node, ctx) {
    if (!node) return null;
    const progressNode = node.querySelector('[data-tracing-beam-progress]');
    if (!progressNode) return null;

    if (ctx && ctx.reducedMotion) {
      progressNode.style.height = '100%';
      return null;
    }

    const clamp = (v, min, max) => Math.min(max, Math.max(min, v));
    const update = () => {
      const rect = node.getBoundingClientRect();
      const viewport = window.innerHeight || document.documentElement.clientHeight || 1;
      const visible = clamp((viewport * 0.8 - rect.top) / (rect.height + viewport * 0.8), 0, 1);
      progressNode.style.height = `${Math.round(visible * 100)}%`;
    };

    let rafId = null;
    const onScroll = () => {
      if (rafId !== null) return;
      rafId = window.requestAnimationFrame(() => {
        rafId = null;
        update();
      });
    };

    update();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll, { passive: true });

    return function cleanup() {
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
      if (rafId !== null) {
        window.cancelAnimationFrame(rafId);
      }
    };
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('tracing-beam', '[data-tracing-beam], [data-effect~="tracing-beam"]', initTracingBeam);
  }
})();
