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
      let nearFooter = false;
      const footerSelector = dock.dataset.hideNearFooter || '[data-footer-anchor]';
      const footerAnchor = document.querySelector(footerSelector);
      const syncDockVisibility = () => {
        const body = document.body;
        const modalOpen = !!(body && (body.classList.contains('is-modal-open') || body.classList.contains('is-drawer-open')));
        dock.classList.toggle('dock-hidden', nearFooter || modalOpen);
      };
      const onScroll = () => {
        dock.classList.toggle('dock-scrolled', (window.scrollY || 0) > 180);
        syncDockVisibility();
      };
      onScroll();
      window.addEventListener('scroll', onScroll, { passive: true });
      if (footerAnchor && 'IntersectionObserver' in window) {
        const observer = new IntersectionObserver(
          (entries) => {
            entries.forEach((entry) => {
              nearFooter = entry.isIntersecting;
              syncDockVisibility();
            });
          },
          { threshold: 0, rootMargin: '0px 0px 120px 0px' }
        );
        observer.observe(footerAnchor);
      }
    });
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('floating-dock', initFloatingDock);
  }
})();
