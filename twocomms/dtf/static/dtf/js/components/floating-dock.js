/**
 * Floating Dock — macOS-like magnification, constructor local dock, image badge
 * Visibility contract: hides near footer, on modal/drawer, on mobile
 * Constructor dock: separate action bar for file ops
 * Registered via DTF.registerEffect
 */
(function () {
  'use strict';
  var DTF = (window.DTF = window.DTF || {});
  var MAGNIFY_DISTANCE = 140;
  var MAGNIFY_SCALE = 1.35;

  function initFloatingDock(root) {
    var scope = root || document;
    var docks = [];
    if (scope.matches && scope.matches('[data-floating-dock]')) docks.push(scope);
    if (scope.querySelectorAll) docks.push.apply(docks, scope.querySelectorAll('[data-floating-dock]'));

    docks.forEach(function (dock) {
      if (dock.dataset.dockInit === '1') return;
      dock.dataset.dockInit = '1';

      var isConstructor = dock.dataset.dockType === 'constructor';
      var isMobile = DTF.motion && DTF.motion.isMobile ? DTF.motion.isMobile() : (window.innerWidth < 900);
      var listeners = [];

      function on(el, evt, fn, opts) {
        el.addEventListener(evt, fn, opts || false);
        listeners.push([el, evt, fn, opts || false]);
      }

      /* Hide on mobile for global dock (constructor dock may stay) */
      if (isMobile && !isConstructor) {
        dock.hidden = true;
        return;
      }

      dock.classList.add('dock-ready');
      var items = dock.querySelectorAll('.dock-item, a, button');

      /* --- Mac-like magnification on desktop --- */
      var reducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      var isCoarse = window.matchMedia && window.matchMedia('(pointer: coarse)').matches;

      function resetMagnification() {
        for (var i = 0; i < items.length; i++) {
          items[i].style.transform = '';
          items[i].style.transition = 'transform 200ms ease';
        }
      }

      if (!reducedMotion && !isCoarse && !isMobile) {
        on(dock, 'mousemove', function (e) {
          var dockRect = dock.getBoundingClientRect();
          for (var i = 0; i < items.length; i++) {
            var itemRect = items[i].getBoundingClientRect();
            var itemCenterX = itemRect.left + itemRect.width / 2;
            var itemCenterY = itemRect.top + itemRect.height / 2;
            var distX = e.clientX - itemCenterX;
            var distY = e.clientY - itemCenterY;
            var dist = Math.sqrt(distX * distX + distY * distY);
            var scale = 1;
            if (dist < MAGNIFY_DISTANCE) {
              var ratio = 1 - (dist / MAGNIFY_DISTANCE);
              scale = 1 + (MAGNIFY_SCALE - 1) * ratio * ratio;
            }
            items[i].style.transform = 'scale(' + scale.toFixed(3) + ')';
            items[i].style.transition = 'transform 100ms ease-out';
          }
        });

        on(dock, 'mouseleave', resetMagnification);
      }

      /* --- Visibility contract (global dock only) --- */
      if (!isConstructor) {
        var nearFooter = false;
        var footerSelector = dock.dataset.hideNearFooter || '[data-footer-anchor]';
        var footerAnchor = document.querySelector(footerSelector);

        /* Unified visibility: accounts for FAB modal, drawer, footer */
        function syncDockVisibility() {
          var body = document.body;
          var modalOpen = !!(body && (body.classList.contains('is-modal-open') || body.classList.contains('is-drawer-open')));
          /* Hide when FAB is open */
          var fabOpen = !!(document.getElementById('dtf-fab-modal') && !document.getElementById('dtf-fab-modal').getAttribute('aria-hidden'));
          dock.classList.toggle('dock-hidden', nearFooter || modalOpen || fabOpen);
        }

        function onScroll() {
          dock.classList.toggle('dock-scrolled', (window.scrollY || 0) > 180);
          syncDockVisibility();
        }

        onScroll();
        on(window, 'scroll', onScroll, { passive: true });

        /* Observe footer */
        if (footerAnchor && 'IntersectionObserver' in window) {
          var observer = new IntersectionObserver(
            function (entries) {
              entries.forEach(function (entry) {
                nearFooter = entry.isIntersecting;
                syncDockVisibility();
              });
            },
            { threshold: 0, rootMargin: '0px 0px 120px 0px' }
          );
          observer.observe(footerAnchor);
        }

        /* Listen for FAB modal changes */
        var fabModal = document.getElementById('dtf-fab-modal');
        if (fabModal) {
          var fabObserver = new MutationObserver(syncDockVisibility);
          fabObserver.observe(fabModal, { attributes: true, attributeFilter: ['aria-hidden'] });
        }
      }

      /* --- Image badge support for constructor dock --- */
      if (isConstructor) {
        var badge = dock.querySelector('.dock-badge');
        if (badge) {
          DTF.updateDockBadge = function (count, status) {
            badge.textContent = count > 0 ? String(count) : '';
            badge.className = 'dock-badge' + (status ? ' badge-' + status : '');
            badge.hidden = count <= 0;
          };
        }
      }
    });
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('floating-dock', initFloatingDock);
  }
})();
