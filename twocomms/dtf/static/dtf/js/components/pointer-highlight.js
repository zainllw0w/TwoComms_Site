(function () {
  const DTF = (window.DTF = window.DTF || {});

  function initPointerHighlight(root) {
    const scope = root || document;
    const nodes = [];
    if (scope.matches && scope.matches('[data-pointer]')) nodes.push(scope);
    if (scope.querySelectorAll) nodes.push(...scope.querySelectorAll('[data-pointer]'));

    nodes.forEach((node) => {
      if (node.dataset.init === '1') return;
      node.dataset.init = '1';
      node.classList.add('pointer-highlight');
      node.addEventListener('mouseenter', () => node.classList.add('is-pointed'));
      node.addEventListener('mouseleave', () => node.classList.remove('is-pointed'));
      node.addEventListener('focus', () => node.classList.add('is-pointed'));
      node.addEventListener('blur', () => node.classList.remove('is-pointed'));
    });
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('pointer-highlight', initPointerHighlight);
  }
})();
