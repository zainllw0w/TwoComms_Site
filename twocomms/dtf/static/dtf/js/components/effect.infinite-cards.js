(function () {
  const DTF = (window.DTF = window.DTF || {});

  function initInfiniteCards(node, ctx) {
    if (!node) return null;
    if (ctx && ctx.reducedMotion) {
      node.classList.add('infinite-cards-static');
      return null;
    }
    node.classList.add('infinite-cards-ready');
    return null;
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('infinite-cards', '[data-effect~="infinite-cards"]', initInfiniteCards);
  }
})();
