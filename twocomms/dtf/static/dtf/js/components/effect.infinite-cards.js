/**
 * Infinite Moving Cards — SEO-safe infinite scroll
 * Clone protocol: clones are aria-hidden, inert, no active links
 * Pause on hover/focus, reduced-motion fallback
 * Registered via DTF.registerEffect
 */
(function () {
  'use strict';
  var DTF = (window.DTF = window.DTF || {});

  var SPEED_MAP = {
    slow: 60,
    normal: 36,
    fast: 18,
  };

  function initInfiniteCards(node, ctx) {
    if (!node) return null;

    var track = node.querySelector('.infinite-track');
    if (!track) return null;

    var direction = (node.dataset.direction || 'left').toLowerCase();
    var speedName = (node.dataset.speed || 'normal').toLowerCase();
    var pauseOnHover = node.dataset.pauseOnHover !== 'false';
    var duration = SPEED_MAP[speedName] || SPEED_MAP.normal;
    var reducedMotion = ctx && ctx.reducedMotion;
    var listeners = [];
    var paused = false;

    function on(el, evt, fn, opts) {
      el.addEventListener(evt, fn, opts || false);
      listeners.push([el, evt, fn, opts || false]);
    }

    /* Reduced motion: static layout, no animation */
    if (reducedMotion) {
      node.classList.add('infinite-cards-static');
      return null;
    }

    /* Clone the track items for seamless loop */
    var originalItems = track.querySelectorAll('.infinite-item');
    if (!originalItems.length) return null;

    var clone = track.cloneNode(true);
    /* Make clones decorative: aria-hidden, inert, strip links */
    clone.setAttribute('aria-hidden', 'true');
    if ('inert' in clone) clone.inert = true;
    clone.setAttribute('role', 'presentation');
    /* Remove active links from clones */
    var cloneLinks = clone.querySelectorAll('a[href]');
    for (var i = 0; i < cloneLinks.length; i++) {
      cloneLinks[i].removeAttribute('href');
      cloneLinks[i].setAttribute('tabindex', '-1');
      cloneLinks[i].setAttribute('aria-hidden', 'true');
    }
    /* Remove IDs from clones to avoid duplicates */
    var cloneIds = clone.querySelectorAll('[id]');
    for (var j = 0; j < cloneIds.length; j++) {
      cloneIds[j].removeAttribute('id');
    }
    /* Wrap both original and clone in an outer track */
    var wrapper = document.createElement('div');
    wrapper.className = 'infinite-track-wrapper';
    wrapper.setAttribute('aria-live', 'off');

    /* Move original track into wrapper */
    track.parentNode.insertBefore(wrapper, track);
    wrapper.appendChild(track);
    wrapper.appendChild(clone);

    /* Animation CSS custom properties */
    wrapper.style.setProperty('--infinite-duration', duration + 's');
    wrapper.style.setProperty('--infinite-direction', direction === 'right' ? 'reverse' : 'normal');

    node.classList.add('infinite-cards-ready');

    /* Pause on hover */
    if (pauseOnHover) {
      on(node, 'mouseenter', function () {
        paused = true;
        wrapper.style.animationPlayState = 'paused';
        wrapper.classList.add('is-paused');
      });
      on(node, 'mouseleave', function () {
        paused = false;
        wrapper.style.animationPlayState = 'running';
        wrapper.classList.remove('is-paused');
      });
    }

    /* Pause on focus within (for keyboard navigation) */
    on(node, 'focusin', function () {
      paused = true;
      wrapper.style.animationPlayState = 'paused';
      wrapper.classList.add('is-paused');
    });
    on(node, 'focusout', function (e) {
      if (!node.contains(e.relatedTarget)) {
        paused = false;
        wrapper.style.animationPlayState = 'running';
        wrapper.classList.remove('is-paused');
      }
    });

    return function cleanup() {
      for (var k = 0; k < listeners.length; k++) {
        var l = listeners[k];
        l[0].removeEventListener(l[1], l[2], l[3]);
      }
      listeners.length = 0;
      /* Restore DOM: move track back, remove wrapper and clone */
      if (wrapper.parentNode) {
        wrapper.parentNode.insertBefore(track, wrapper);
        wrapper.parentNode.removeChild(wrapper);
      }
      node.classList.remove('infinite-cards-ready');
    };
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('infinite-cards', '[data-effect~="infinite-cards"]', initInfiniteCards);
  }
})();
