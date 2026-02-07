(function () {
  const DTF = (window.DTF = window.DTF || {});

  function initCardsOnClick(root) {
    const scope = root || document;
    const modal = document.getElementById('gallery-case-modal');
    if (!modal) return;
    const titleNode = modal.querySelector('[data-case-title]');
    const descNode = modal.querySelector('[data-case-desc]');
    const imgNode = modal.querySelector('[data-case-image]');

    const openButtons = [];
    if (scope.matches && scope.matches('[data-gallery-open]')) openButtons.push(scope);
    if (scope.querySelectorAll) openButtons.push(...scope.querySelectorAll('[data-gallery-open]'));

    const close = () => {
      modal.classList.remove('is-open');
      modal.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('is-modal-open');
    };

    if (!modal.dataset.init) {
      modal.dataset.init = '1';
      modal.addEventListener('click', (event) => {
        if (event.target.dataset.caseClose !== undefined) {
          close();
        }
      });
      document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && modal.classList.contains('is-open')) close();
      });
    }

    openButtons.forEach((button) => {
      if (button.dataset.init === '1') return;
      button.dataset.init = '1';
      button.addEventListener('click', () => {
        if (titleNode) titleNode.textContent = button.dataset.caseTitle || 'Case';
        if (descNode) descNode.textContent = button.dataset.caseDesc || '';
        if (imgNode) {
          imgNode.src = button.dataset.caseImage || '';
          imgNode.alt = button.dataset.caseTitle || 'Case image';
        }
        modal.classList.add('is-open');
        modal.setAttribute('aria-hidden', 'false');
        document.body.classList.add('is-modal-open');
      });
    });
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('cards-on-click', initCardsOnClick);
  }
})();
