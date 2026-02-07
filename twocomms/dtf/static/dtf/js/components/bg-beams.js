(function () {
  const DTF = (window.DTF = window.DTF || {});

  function initBeams(root) {
    const scope = root || document;
    const nodes = [];
    if (scope.matches && scope.matches('[data-effect~="bg-beams"]')) nodes.push(scope);
    if (scope.querySelectorAll) nodes.push(...scope.querySelectorAll('[data-effect~="bg-beams"]'));

    nodes.forEach((node) => {
      if (node.dataset.init === '1') return;
      node.dataset.init = '1';
      if (!DTF.motion || DTF.motion.isReducedMotion() || DTF.motion.isMobile()) {
        node.classList.add('beams-static');
        return;
      }
      if (!('IntersectionObserver' in window)) {
        node.classList.add('beams-active');
        return;
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
    });
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('bg-beams', initBeams);
  }
})();
