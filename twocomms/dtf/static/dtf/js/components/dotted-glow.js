(function () {
  const DTF = (window.DTF = window.DTF || {});

  function initDottedGlow(root) {
    const scope = root || document;
    const nodes = [];
    if (scope.matches && scope.matches('[data-effect~="dotted-glow"]')) nodes.push(scope);
    if (scope.querySelectorAll) nodes.push(...scope.querySelectorAll('[data-effect~="dotted-glow"]'));

    nodes.forEach((node) => {
      if (node.dataset.init === '1') return;
      node.dataset.init = '1';
      if (DTF.motion && DTF.motion.isReducedMotion()) {
        node.classList.add('dotted-static');
        return;
      }
      node.classList.add('dotted-ready');
      if (!('IntersectionObserver' in window)) {
        node.classList.add('dotted-active');
        return;
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
    });
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('dotted-glow', initDottedGlow);
  }
})();
