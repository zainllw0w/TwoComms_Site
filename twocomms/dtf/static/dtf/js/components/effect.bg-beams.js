(function () {
  const DTF = (window.DTF = window.DTF || {});

  function initBeamEffect(node, ctx) {
    if (!node) return null;
    if (ctx && ctx.reducedMotion) {
      node.classList.add('beams-static');
      node.classList.remove('beams-active');
      return null;
    }

    if (!('IntersectionObserver' in window)) {
      node.classList.add('beams-active');
      return null;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          node.classList.toggle('beams-active', entry.isIntersecting);
        });
      },
      { threshold: 0.15 }
    );
    observer.observe(node);
    return function cleanup() {
      observer.disconnect();
    };
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('bg-beams', '[data-effect~="bg-beams"]', initBeamEffect);
  }
})();
