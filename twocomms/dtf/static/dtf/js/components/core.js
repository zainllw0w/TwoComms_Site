(function () {
  const DTF = (window.DTF = window.DTF || {});
  const registry = (DTF.__effectsRegistry = DTF.__effectsRegistry || new Map());

  function registerEffect(name, initFn) {
    if (!name || typeof initFn !== 'function') return;
    if (!registry.has(name)) {
      registry.set(name, initFn);
    }
  }

  function initEffects(root) {
    const targetRoot = root || document;
    registry.forEach((fn) => {
      try {
        fn(targetRoot);
      } catch (err) {
        // Isolate failures per effect and keep the page usable.
        if (window.console && typeof console.warn === 'function') {
          console.warn('[DTF effect init failed]', err);
        }
      }
    });
  }

  DTF.registerEffect = registerEffect;
  DTF.initEffects = initEffects;
})();
