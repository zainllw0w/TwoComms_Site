/**
 * Lazy-mount pointsInfoModal from its <template> into <body>.
 * Монтирует модалку на первый клик по триггеру или на idle после LCP —
 * чтобы её DOM (~90 узлов) не раздувал initial render.
 * Вынесено из inline <script> в base.html (Phase 2.2).
 */
(function () {
  var mounted = false;
  var mountPointsModal = function () {
    if (mounted) return null;
    var tpl = document.getElementById('points-modal-template');
    if (!tpl) return null;
    var frag = tpl.content.cloneNode(true);
    document.body.appendChild(frag);
    mounted = true;
    var modal = document.getElementById('pointsInfoModal');
    if (modal) {
      modal.addEventListener('show.bs.modal', function (event) {
        var button = event.relatedTarget;
        if (!button) return;
        var productTitle = button.getAttribute('data-product-title');
        var pointsAmount = button.getAttribute('data-points-amount');
        var titleEl = document.getElementById('modalProductTitle');
        var amountEl = document.getElementById('modalPointsAmount');
        if (titleEl) titleEl.textContent = productTitle || '';
        if (amountEl) amountEl.textContent = pointsAmount || '';
      });
    }
    return modal;
  };
  // Lazy-mount: в первую очередь по клику на триггер (capture перед Bootstrap).
  document.addEventListener('click', function (e) {
    if (mounted) return;
    var t = e.target && e.target.closest && e.target.closest('[data-bs-target="#pointsInfoModal"]');
    if (t) mountPointsModal();
  }, true);
  // Fallback idle-mount: чтобы первое открытие не ждало кодогенерации шаблона.
  var idle = window.requestIdleCallback || function (cb) { return setTimeout(cb, 1500); };
  idle(function () { mountPointsModal(); }, { timeout: 5000 });
})();
