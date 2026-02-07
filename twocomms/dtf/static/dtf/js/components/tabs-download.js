(function () {
  const DTF = (window.DTF = window.DTF || {});

  function initTabsDownload(root) {
    const scope = root || document;
    const hosts = [];
    if (scope.matches && scope.matches('[data-template-tabs]')) hosts.push(scope);
    if (scope.querySelectorAll) hosts.push(...scope.querySelectorAll('[data-template-tabs]'));

    hosts.forEach((host) => {
      if (host.dataset.init === '1') return;
      host.dataset.init = '1';
      const tabs = Array.from(host.querySelectorAll('[data-tab-target]'));
      const panels = Array.from(host.querySelectorAll('[data-tab-panel]'));

      function activate(target) {
        tabs.forEach((tab) => {
          const active = tab.getAttribute('data-tab-target') === target;
          tab.classList.toggle('is-active', active);
          tab.setAttribute('aria-selected', active ? 'true' : 'false');
        });
        panels.forEach((panel) => {
          const active = panel.getAttribute('data-tab-panel') === target;
          panel.hidden = !active;
          panel.classList.toggle('is-active', active);
        });
      }

      tabs.forEach((tab) => {
        tab.addEventListener('click', () => activate(tab.getAttribute('data-tab-target')));
      });
      if (tabs[0]) activate(tabs[0].getAttribute('data-tab-target'));
    });
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('tabs-download', initTabsDownload);
  }
})();
