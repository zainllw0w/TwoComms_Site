/**
 * Tooltip Card — rich tooltip that follows mouse pointer
 * For preflight terms (DPI, safe margin, tiny lines)
 * Touch support, viewport boundary detection
 * Registered via DTF.registerEffect
 */
(function () {
  'use strict';
  var DTF = (window.DTF = window.DTF || {});

  function initTooltipCard(node, ctx) {
    if (!node) return null;

    var content = node.dataset.tooltipContent || node.getAttribute('title') || '';
    var htmlContent = node.dataset.tooltipHtml || '';
    if (!content && !htmlContent) return null;

    /* Remove native title to prevent double tooltip */
    if (node.getAttribute('title')) {
      node.removeAttribute('title');
    }

    var tooltip = null;
    var visible = false;
    var listeners = [];
    var hideTimeout = null;

    function on(el, evt, fn, opts) {
      el.addEventListener(evt, fn, opts || false);
      listeners.push([el, evt, fn, opts || false]);
    }

    function createTooltip() {
      if (tooltip) return;
      tooltip = document.createElement('div');
      tooltip.className = 'dtf-tooltip-card';
      tooltip.setAttribute('role', 'tooltip');
      tooltip.setAttribute('aria-hidden', 'true');

      var inner = document.createElement('div');
      inner.className = 'dtf-tooltip-inner';
      if (htmlContent) {
        inner.innerHTML = htmlContent;
      } else {
        inner.textContent = content;
      }
      tooltip.appendChild(inner);
      document.body.appendChild(tooltip);
    }

    function positionTooltip(mouseX, mouseY) {
      if (!tooltip) return;
      var offset = 12;
      var rect = tooltip.getBoundingClientRect();
      var vw = window.innerWidth;
      var vh = window.innerHeight;

      var x = mouseX + offset;
      var y = mouseY + offset;

      /* Boundary check */
      if (x + rect.width > vw - 10) {
        x = mouseX - rect.width - offset;
      }
      if (y + rect.height > vh - 10) {
        y = mouseY - rect.height - offset;
      }
      if (x < 10) x = 10;
      if (y < 10) y = 10;

      tooltip.style.left = x + 'px';
      tooltip.style.top = y + 'px';
    }

    function show(mouseX, mouseY) {
      if (hideTimeout) { clearTimeout(hideTimeout); hideTimeout = null; }
      createTooltip();
      visible = true;
      tooltip.setAttribute('aria-hidden', 'false');
      tooltip.classList.add('dtf-tooltip-visible');
      positionTooltip(mouseX, mouseY);
    }

    function hide() {
      if (!tooltip) return;
      visible = false;
      tooltip.classList.remove('dtf-tooltip-visible');
      tooltip.setAttribute('aria-hidden', 'true');
    }

    on(node, 'mouseenter', function (e) {
      show(e.clientX, e.clientY);
    });

    on(node, 'mousemove', function (e) {
      if (visible) positionTooltip(e.clientX, e.clientY);
    });

    on(node, 'mouseleave', function () {
      hide();
    });

    /* Touch: toggle on tap */
    on(node, 'touchstart', function (e) {
      if (visible) {
        hide();
      } else {
        var touch = e.touches[0];
        if (touch) show(touch.clientX, touch.clientY);
        hideTimeout = setTimeout(hide, 3000);
      }
    }, { passive: true });

    /* ARIA: node points to tooltip via describedby */
    node.style.cursor = 'help';

    return function cleanup() {
      for (var i = 0; i < listeners.length; i++) {
        var l = listeners[i];
        l[0].removeEventListener(l[1], l[2], l[3]);
      }
      listeners.length = 0;
      if (tooltip && tooltip.parentNode) {
        tooltip.parentNode.removeChild(tooltip);
      }
      tooltip = null;
    };
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('tooltip-card', '[data-effect~="tooltip-card"], [data-tooltip-content]', initTooltipCard);
  }
})();
