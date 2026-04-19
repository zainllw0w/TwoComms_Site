/**
 * CSS loading enhancement: flips preloaded stylesheets from rel=preload
 * to rel=stylesheet after load, removes body.loading class post-DOMReady.
 * Вынесено из inline <script> в base.html (Phase 2.2).
 */
// Улучшение загрузки CSS для лучшей производительности
(function () {
  // Функция для загрузки CSS асинхронно
  function loadCSS(href, before, media) {
    var doc = window.document;
    var ss = doc.createElement("link");
    var ref;
    if (before) {
      ref = before;
    } else {
      var refs = (doc.body || doc.getElementsByTagName("head")[0]).childNodes;
      ref = refs[refs.length - 1];
    }

    var sheets = doc.styleSheets;
    ss.rel = "stylesheet";
    ss.href = href;
    ss.media = "only x";

    function ready(cb) {
      if (doc.body) cb();
      else if (doc.addEventListener) doc.addEventListener("DOMContentLoaded", cb);
    }

    ready(function () {
      ref.parentNode.insertBefore(ss, (before ? ref : ref.nextSibling));
    });

    var onloadcssdefined = function (cb) {
      var resolvedHref = ss.href;
      var i = sheets.length;
      while (i--) {
        if (sheets[i].href === resolvedHref) {
          return cb();
        }
      }
      setTimeout(function () {
        onloadcssdefined(cb);
      });
    };

    function loadCB() {
      if (ss.addEventListener) {
        ss.removeEventListener("load", loadCB);
      }
      ss.media = media || "all";
    }

    if (ss.addEventListener) {
      ss.addEventListener("load", loadCB);
    }
    ss.onloadcssdefined = onloadcssdefined;
    onloadcssdefined(loadCB);
    return ss;
  }

  // Применяем улучшения для всех preload CSS
  var preloadLinks = document.querySelectorAll('link[rel="preload"][as="style"]');
  preloadLinks.forEach(function (link) {
    link.addEventListener('load', function () {
      this.rel = 'stylesheet';
    });
  });

  // Убираем класс loading после загрузки CSS
  document.addEventListener('DOMContentLoaded', function () {
    setTimeout(function () {
      document.body.classList.remove('loading');
    }, 100);
  });
})();
