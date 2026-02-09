/**
 * Images Badge — folder icon with preview images that fan out on hover
 * For constructor file state indication
 * Vanilla JS port of Aceternity's ImagesBadge
 * Registered via DTF.registerEffect
 */
(function () {
  'use strict';
  var DTF = (window.DTF = window.DTF || {});

  function initImagesBadge(node, ctx) {
    if (!node) return null;

    var text = node.dataset.badgeText || '';
    var imagesAttr = node.dataset.badgeImages || '';
    var images = [];
    try {
      images = JSON.parse(imagesAttr);
    } catch (e) {
      if (imagesAttr) images = imagesAttr.split(',').map(function (s) { return s.trim(); });
    }
    images = images.slice(0, 3);

    var folderW = parseInt(node.dataset.folderWidth || '32', 10);
    var folderH = parseInt(node.dataset.folderHeight || '24', 10);
    var hoverSpread = parseInt(node.dataset.hoverSpread || '20', 10);
    var hoverRotation = parseInt(node.dataset.hoverRotation || '15', 10);
    var hoverTranslateY = parseInt(node.dataset.hoverTranslateY || '-35', 10);

    var listeners = [];
    var isHovered = false;
    var reducedMotion = ctx && ctx.reducedMotion;

    function on(el, evt, fn, opts) {
      el.addEventListener(evt, fn, opts || false);
      listeners.push([el, evt, fn, opts || false]);
    }

    /* Build DOM structure */
    node.classList.add('images-badge');

    var folder = document.createElement('div');
    folder.className = 'ib-folder';
    folder.style.width = folderW + 'px';
    folder.style.height = folderH + 'px';

    var tabEl = document.createElement('div');
    tabEl.className = 'ib-folder-tab';
    folder.appendChild(tabEl);

    var bodyEl = document.createElement('div');
    bodyEl.className = 'ib-folder-body';
    folder.appendChild(bodyEl);

    /* Image elements inside folder */
    var imgEls = [];
    images.forEach(function (src, idx) {
      var img = document.createElement('img');
      img.className = 'ib-preview-img';
      img.src = src;
      img.alt = '';
      img.loading = 'lazy';
      img.setAttribute('aria-hidden', 'true');
      img.style.zIndex = String(images.length - idx);
      folder.appendChild(img);
      imgEls.push(img);
    });

    var label = document.createElement('span');
    label.className = 'ib-label';
    label.textContent = text;

    node.appendChild(folder);
    if (text) node.appendChild(label);

    /* Hover animation */
    function applyHover() {
      if (reducedMotion) return;
      isHovered = true;
      var count = imgEls.length;
      imgEls.forEach(function (img, idx) {
        var spreadOffset = (idx - (count - 1) / 2) * hoverSpread;
        var rotation = (idx - (count - 1) / 2) * hoverRotation;
        img.style.transition = 'transform 300ms cubic-bezier(0.34, 1.56, 0.64, 1), opacity 200ms ease';
        img.style.transform = 'translateX(' + spreadOffset + 'px) translateY(' + hoverTranslateY + 'px) rotate(' + rotation + 'deg) scale(1.1)';
        img.style.opacity = '1';
      });
    }

    function resetHover() {
      isHovered = false;
      imgEls.forEach(function (img) {
        img.style.transition = 'transform 250ms ease, opacity 200ms ease';
        img.style.transform = '';
        img.style.opacity = '';
      });
    }

    on(node, 'mouseenter', applyHover);
    on(node, 'mouseleave', resetHover);
    on(node, 'touchstart', function () {
      if (isHovered) resetHover(); else applyHover();
    }, { passive: true });

    node.classList.add('images-badge-ready');

    return function cleanup() {
      for (var i = 0; i < listeners.length; i++) {
        var l = listeners[i];
        l[0].removeEventListener(l[1], l[2], l[3]);
      }
      listeners.length = 0;
    };
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('images-badge', '[data-effect~="images-badge"]', initImagesBadge);
  }
})();
