(function () {
  const DTF = (window.DTF = window.DTF || {});

  function createDot(index) {
    const dot = document.createElement('span');
    dot.className = 'sparkle-dot';
    dot.style.setProperty('--sparkle-index', String(index));
    dot.style.left = `${12 + index * 18}%`;
    dot.style.top = `${20 + (index % 3) * 18}%`;
    return dot;
  }

  function initSparkles(root) {
    const scope = root || document;
    const nodes = [];
    if (scope.matches && scope.matches('[data-effect~="sparkles"]')) nodes.push(scope);
    if (scope.querySelectorAll) nodes.push(...scope.querySelectorAll('[data-effect~="sparkles"]'));

    nodes.forEach((node) => {
      if (node.dataset.init === '1') return;
      node.dataset.init = '1';
      if (DTF.motion && DTF.motion.isReducedMotion()) {
        node.classList.add('sparkles-static');
        return;
      }
      node.classList.add('sparkles-ready');
      for (let i = 0; i < 4; i += 1) {
        node.appendChild(createDot(i));
      }
    });
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('sparkles', initSparkles);
  }
})();
