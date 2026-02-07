(function () {
  const DTF = (window.DTF = window.DTF || {});

  function initPointerHighlight(node, ctx) {
    if (!node) return null;
    node.classList.add('pointer-highlight');
    if (ctx && ctx.coarsePointer) return null;

    const onEnter = () => node.classList.add('is-pointed');
    const onLeave = () => node.classList.remove('is-pointed');

    node.addEventListener('mouseenter', onEnter);
    node.addEventListener('mouseleave', onLeave);
    node.addEventListener('focus', onEnter);
    node.addEventListener('blur', onLeave);

    return function cleanup() {
      node.removeEventListener('mouseenter', onEnter);
      node.removeEventListener('mouseleave', onLeave);
      node.removeEventListener('focus', onEnter);
      node.removeEventListener('blur', onLeave);
    };
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('pointer-highlight', '[data-pointer], [data-effect~="pointer-highlight"]', initPointerHighlight);
  }
})();
