(function () {
  const DTF = (window.DTF = window.DTF || {});

  function setStep(host, value) {
    const steps = host.querySelectorAll('[data-upload-step]');
    steps.forEach((stepNode) => {
      const step = stepNode.getAttribute('data-upload-step');
      const numeric = parseInt(step || '0', 10);
      stepNode.classList.toggle('is-active', numeric === value);
      stepNode.classList.toggle('is-done', numeric < value);
    });
  }

  function initMultiStepLoader(root) {
    const scope = root || document;
    const hosts = [];
    if (scope.matches && scope.matches('[data-upload-flow]')) hosts.push(scope);
    if (scope.querySelectorAll) hosts.push(...scope.querySelectorAll('[data-upload-flow]'));

    hosts.forEach((host) => {
      if (host.dataset.init === '1') return;
      host.dataset.init = '1';
      const input = host.querySelector('input[type="file"]');
      if (!input) return;
      setStep(host, 1);
      input.addEventListener('change', () => {
        if (input.files && input.files.length) {
          setStep(host, 2);
          window.setTimeout(() => setStep(host, 3), 260);
          window.setTimeout(() => setStep(host, 4), 520);
        } else {
          setStep(host, 1);
        }
      });
    });
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('multi-step-loader', initMultiStepLoader);
  }
})();
