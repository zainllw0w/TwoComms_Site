(function () {
  const DTF = (window.DTF = window.DTF || {});

  function rememberLabel(el) {
    if (!el || el.dataset.stateLabelDefault) return;
    el.dataset.stateLabelDefault = (el.textContent || '').trim();
  }

  function setState(el, state) {
    if (!el) return;
    rememberLabel(el);
    const nextState = state || 'idle';
    const idleLabel = el.dataset.stateLabelDefault || '';
    const loadingLabel = el.dataset.stateLoading || 'Надсилаємо...';
    const successLabel = el.dataset.stateSuccess || 'Готово';
    const errorLabel = el.dataset.stateError || 'Помилка';

    el.classList.remove('is-loading', 'is-success', 'is-error');
    el.removeAttribute('aria-busy');

    if (nextState === 'loading') {
      el.classList.add('is-loading');
      el.setAttribute('aria-busy', 'true');
      if (el.tagName === 'BUTTON') el.disabled = true;
      el.textContent = loadingLabel;
      return;
    }
    if (nextState === 'success') {
      el.classList.add('is-success');
      if (el.tagName === 'BUTTON') el.disabled = false;
      el.textContent = successLabel;
      return;
    }
    if (nextState === 'error') {
      el.classList.add('is-error');
      if (el.tagName === 'BUTTON') el.disabled = false;
      el.textContent = errorLabel;
      return;
    }
    if (el.tagName === 'BUTTON') el.disabled = false;
    el.textContent = idleLabel;
  }

  function findStatefulTarget(source) {
    if (!source) return null;
    if (source.matches && source.matches('[data-stateful], [data-stateful-link], [data-effect~="stateful-button"]')) {
      return source;
    }
    if (source.closest) {
      const direct = source.closest('[data-stateful], [data-stateful-link], [data-effect~="stateful-button"]');
      if (direct) return direct;
      const form = source.closest('form');
      if (form) {
        return form.querySelector('button[type="submit"][data-stateful], button[type="submit"][data-effect~="stateful-button"]');
      }
    }
    return null;
  }

  function bindGlobalHtmxHandlers() {
    if (!document.body || DTF.__statefulHtmxBound || !window.htmx) return;
    DTF.__statefulHtmxBound = true;

    document.body.addEventListener('htmx:beforeRequest', (event) => {
      const source = (event.detail && event.detail.elt) || event.target;
      const target = findStatefulTarget(source);
      if (!target) return;
      setState(target, 'loading');
    });

    document.body.addEventListener('htmx:afterRequest', (event) => {
      const source = (event.detail && event.detail.elt) || event.target;
      const target = findStatefulTarget(source);
      if (!target) return;
      const successful = !!(event.detail && event.detail.successful);
      setState(target, successful ? 'success' : 'error');
      window.setTimeout(() => setState(target, 'idle'), successful ? 900 : 1400);
    });
  }

  function initStatefulButton(node) {
    if (!node) return null;
    rememberLabel(node);

    const isLink = node.tagName === 'A';
    const onClick = () => {
      if (!isLink) return;
      setState(node, 'loading');
      window.setTimeout(() => setState(node, 'idle'), 1200);
    };

    const onFormSubmit = () => {
      if (isLink) return;
      setState(node, 'loading');
    };

    if (isLink) {
      node.addEventListener('click', onClick);
    } else {
      const form = node.closest('form');
      if (form) {
        form.addEventListener('submit', onFormSubmit);
      }
    }

    return function cleanup() {
      if (isLink) {
        node.removeEventListener('click', onClick);
      } else {
        const form = node.closest('form');
        if (form) {
          form.removeEventListener('submit', onFormSubmit);
        }
      }
    };
  }

  DTF.Button = DTF.Button || {};
  DTF.Button.setState = setState;

  if (DTF.registerEffect) {
    DTF.registerEffect(
      'stateful-button',
      '[data-stateful], [data-stateful-link], [data-effect~="stateful-button"]',
      initStatefulButton
    );
  }

  bindGlobalHtmxHandlers();
})();
