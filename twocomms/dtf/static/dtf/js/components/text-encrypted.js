(function () {
  const DTF = (window.DTF = window.DTF || {});
  const CHARS = '01ABCDEF#@';

  function scramble(source, progress) {
    const keep = Math.floor(source.length * progress);
    return source
      .split('')
      .map((ch, idx) => {
        if (idx <= keep || ch === ' ') return ch;
        return CHARS[Math.floor(Math.random() * CHARS.length)];
      })
      .join('');
  }

  function animate(el) {
    const target = el.dataset.encryptedText || el.textContent || '';
    if (!target) return;
    if (DTF.motion && DTF.motion.isReducedMotion()) {
      el.textContent = target;
      return;
    }
    let tick = 0;
    const steps = Math.max(12, Math.min(36, target.length * 2));
    const timer = window.setInterval(() => {
      tick += 1;
      el.textContent = scramble(target, tick / steps);
      if (tick >= steps) {
        window.clearInterval(timer);
        el.textContent = target;
      }
    }, 34);
  }

  function initEncrypted(root) {
    const scope = root || document;
    const nodes = [];
    if (scope.matches && scope.matches('[data-effect~="encrypted-text"]')) nodes.push(scope);
    if (scope.querySelectorAll) nodes.push(...scope.querySelectorAll('[data-effect~="encrypted-text"]'));

    nodes.forEach((node) => {
      if (node.dataset.init === '1') return;
      node.dataset.init = '1';
      animate(node);
    });
  }

  if (DTF.registerEffect) {
    DTF.registerEffect('text-encrypted', initEncrypted);
  }
})();
