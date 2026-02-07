(function () {
  const DTF = (window.DTF = window.DTF || {});

  function initDottedGlow(node, ctx) {
    if (!node) return null;
    if (ctx && ctx.reducedMotion) {
      node.classList.add('dotted-static');
      node.classList.remove('dotted-active');
      return null;
    }
    if (!('IntersectionObserver' in window)) {
      node.classList.add('dotted-active');
      return null;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          node.classList.toggle('dotted-active', entry.isIntersecting);
        });
      },
      { threshold: 0.2 }
    );
    observer.observe(node);
    return function cleanup() {
      observer.disconnect();
    };
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('dotted-glow', '[data-effect~="dotted-glow"]', initDottedGlow);
  }
})();
