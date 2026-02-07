(function () {
  const DTF = (window.DTF = window.DTF || {});

  function initFloatingDock(root) {
    const scope = root || document;
    const docks = [];
    if (scope.matches && scope.matches('[data-floating-dock]')) docks.push(scope);
    if (scope.querySelectorAll) docks.push(...scope.querySelectorAll('[data-floating-dock]'));

    docks.forEach((dock) => {
      if (dock.dataset.init === '1') return;
      dock.dataset.init = '1';
      if (DTF.motion && DTF.motion.isMobile()) {
        dock.hidden = true;
        return;
      }
      dock.classList.add('dock-ready');
      const onScroll = () => {
        dock.classList.toggle('dock-scrolled', (window.scrollY || 0) > 180);
      };
      onScroll();
      window.addEventListener('scroll', onScroll, { passive: true });
    });
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('floating-dock', initFloatingDock);
  }
})();
