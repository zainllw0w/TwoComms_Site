/**
 * Text Generate Effect — word-by-word fade-in
 * For preflight summary recommendation text
 * One-shot on viewport entry
 * Registered via DTF.registerEffect
 */
(function () {
  'use strict';
  var DTF = (window.DTF = window.DTF || {});

  function initTextGenerate(node, ctx) {
    if (!node) return null;

    var text = node.dataset.generateText || node.textContent || '';
    if (!text.trim()) return null;

    var wordDuration = parseInt(node.dataset.generateDuration || '40', 10) || 40;
    var filterEnabled = node.dataset.generateFilter !== 'false';
    var reducedMotion = ctx && ctx.reducedMotion;

    if (reducedMotion) {
      node.classList.add('text-generate-static');
      return null;
    }

    var words = text.trim().split(/\s+/);
    var hasPlayed = false;

    /* Replace content with individual word spans */
    node.textContent = '';
    node.setAttribute('aria-label', text);
    var spans = [];
    words.forEach(function (word, idx) {
      var span = document.createElement('span');
      span.className = 'tg-word';
      span.textContent = word;
      span.style.opacity = '0';
      if (filterEnabled) {
        span.style.filter = 'blur(8px)';
      }
      span.style.transition = 'opacity 300ms ease, filter 300ms ease';
      span.setAttribute('aria-hidden', 'true');
      if (idx > 0) {
        node.appendChild(document.createTextNode(' '));
      }
      node.appendChild(span);
      spans.push(span);
    });

    function play() {
      if (hasPlayed) return;
      hasPlayed = true;
      spans.forEach(function (span, idx) {
        setTimeout(function () {
          span.style.opacity = '1';
          if (filterEnabled) {
            span.style.filter = 'blur(0)';
          }
        }, idx * wordDuration);
      });
      node.classList.add('text-generate-played');
    }

    /* Trigger on viewport entry */
    if ('IntersectionObserver' in window) {
      var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            play();
            observer.disconnect();
          }
        });
      }, { threshold: 0.3 });
      observer.observe(node);
    } else {
      play();
    }

    node.classList.add('text-generate-ready');

    return function cleanup() {
      /* Restore original text */
      node.textContent = text;
      node.removeAttribute('aria-label');
    };
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('text-generate', '[data-effect~="text-generate"]', initTextGenerate);
  }
})();
