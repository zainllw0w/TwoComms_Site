(() => {
  const VERSION = '20251021';
  const BASE_PATH = '/static/js/';
  const loadedScripts = new Map();

  function buildUrl(name) {
    return `${BASE_PATH}${name}?v=${VERSION}`;
  }

  function loadScript(name) {
    if (loadedScripts.has(name)) {
      return loadedScripts.get(name);
    }

    const url = buildUrl(name);
    const promise = new Promise((resolve, reject) => {
      const existing = Array.from(document.scripts).find((script) => script.dataset.dsLazy === name || script.src.includes(url));
      if (existing) {
        resolve();
        return;
      }

      const script = document.createElement('script');
      script.src = url;
      script.async = true;
      script.dataset.dsLazy = name;
      script.onload = () => resolve();
      script.onerror = (error) => {
        loadedScripts.delete(name);
        reject(error);
      };
      document.head.appendChild(script);
    });

    loadedScripts.set(name, promise);
    return promise;
  }

  function scheduleDashboardLoad() {
    if (!document.getElementById('ds-order-modal')) {
      return;
    }

    const load = () => {
      loadScript('dropshipper.dashboard.js').catch((error) => {
        console.error('Не вдалося завантажити dropshipper.dashboard.js', error);
      });
    };

    if ('requestIdleCallback' in window) {
      window.requestIdleCallback(load, { timeout: 2000 });
    } else {
      setTimeout(load, 300);
    }
  }

  function setupModalLazyLoading() {
    let productModalReady = false;

    document.addEventListener('click', (event) => {
      const trigger = event.target.closest('.js-open-product-modal, .js-open-order-modal');
      if (!trigger) {
        return;
      }

      if (productModalReady) {
        return;
      }

      event.preventDefault();

      loadScript('dropshipper-product-modal.js')
        .then(() => {
          productModalReady = true;
          setTimeout(() => {
            if (trigger.isConnected) {
              trigger.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
            }
          }, 0);
        })
        .catch((error) => {
          productModalReady = false;
          console.error('Не вдалося завантажити dropshipper-product-modal.js', error);
        });
    }, true);
  }

  document.addEventListener('DOMContentLoaded', () => {
    const path = window.location.pathname;
    if (path.startsWith('/orders/dropshipper')) {
      scheduleDashboardLoad();
      setupModalLazyLoading();
    }
  });
})();
