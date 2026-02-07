(function () {
  const DTF = (window.DTF = window.DTF || {});

  function initVanishInput(root) {
    const scope = root || document;
    const fields = [];
    if (scope.matches && scope.matches('[data-vanish-input]')) fields.push(scope);
    if (scope.querySelectorAll) fields.push(...scope.querySelectorAll('[data-vanish-input]'));

    fields.forEach((field) => {
      if (field.dataset.init === '1') return;
      field.dataset.init = '1';
      const validate = () => {
        if (field.value && field.checkValidity()) {
          field.classList.remove('is-vanish');
          return;
        }
        field.classList.add('is-vanish');
        window.setTimeout(() => field.classList.remove('is-vanish'), 420);
      };
      field.addEventListener('invalid', (evt) => {
        evt.preventDefault();
        validate();
      });
      field.addEventListener('blur', validate);
    });
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('vanish-input', initVanishInput);
  }
})();
