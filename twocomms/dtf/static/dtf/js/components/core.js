(function () {
  const DTF = (window.DTF = window.DTF || {});
  const registry = (DTF.effects = DTF.effects || []);

  function makeAttrKey(name) {
    return String(name || '')
      .replace(/[^a-z0-9]+/gi, '-')
      .replace(/^-+|-+$/g, '')
      .toLowerCase();
  }

  function prefersReducedMotion() {
    return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }

  function isCoarsePointer() {
    return !!(window.matchMedia && window.matchMedia('(pointer: coarse)').matches);
  }

  function oncePerEl(el, key) {
    if (!el || !key) return false;
    const attr = `init-${key}`;
    if (el.dataset && el.dataset[attr]) return false;
    if (el.dataset) el.dataset[attr] = '1';
    return true;
  }

  function collectNodes(root, selector) {
    if (!root || !selector) return [];
    const nodes = [];
    if (root.matches && root.matches(selector)) nodes.push(root);
    if (root.querySelectorAll) nodes.push(...root.querySelectorAll(selector));
    return nodes;
  }

  function getCleanupStore(el) {
    if (!el) return [];
    if (!Array.isArray(el._dtfCleanup)) {
      el._dtfCleanup = [];
    }
    return el._dtfCleanup;
  }

  function registerEffect(name, selectorOrInitFn, maybeInitFn) {
    if (!name) return;
    let selector = '';
    let initFn = null;
    let legacy = false;

    if (typeof selectorOrInitFn === 'string' && typeof maybeInitFn === 'function') {
      selector = selectorOrInitFn;
      initFn = maybeInitFn;
    } else if (typeof selectorOrInitFn === 'function') {
      selector = `[data-effect~="${name}"]`;
      initFn = selectorOrInitFn;
      legacy = true;
    } else {
      return;
    }

    const exists = registry.some((item) => item && item.name === name && item.selector === selector);
    if (exists) return;

    registry.push({
      name,
      selector,
      initFn,
      legacy,
      key: makeAttrKey(name),
    });
  }

  function initEffects(root) {
    const targetRoot = root || document;
    const reducedMotion = DTF.utils && typeof DTF.utils.prefersReducedMotion === 'function'
      ? DTF.utils.prefersReducedMotion()
      : prefersReducedMotion();
    const coarsePointer = DTF.utils && typeof DTF.utils.isCoarsePointer === 'function'
      ? DTF.utils.isCoarsePointer()
      : isCoarsePointer();

    registry.forEach((entry) => {
      if (!entry || typeof entry.initFn !== 'function') return;
      try {
        if (entry.legacy) {
          entry.initFn(targetRoot);
          return;
        }
        const nodes = collectNodes(targetRoot, entry.selector);
        nodes.forEach((node) => {
          const canInit = DTF.utils && typeof DTF.utils.oncePerEl === 'function'
            ? DTF.utils.oncePerEl(node, entry.key)
            : oncePerEl(node, entry.key);
          if (!canInit) return;
          const cleanup = entry.initFn(node, {
            root: targetRoot,
            reducedMotion,
            coarsePointer,
          });
          if (typeof cleanup === 'function') {
            getCleanupStore(node).push(cleanup);
          }
        });
      } catch (err) {
        if (window.console && typeof console.warn === 'function') {
          console.warn('[DTF effect init failed]', entry.name, err);
        }
      }
    });
  }

  function cleanupNodeTree(node) {
    if (!node) return;
    const nodes = [];
    if (node.nodeType === 1) nodes.push(node);
    if (node.querySelectorAll) nodes.push(...node.querySelectorAll('*'));
    nodes.forEach((el) => {
      const cleanupList = el._dtfCleanup;
      if (!Array.isArray(cleanupList) || !cleanupList.length) return;
      while (cleanupList.length) {
        const fn = cleanupList.pop();
        try {
          if (typeof fn === 'function') fn();
        } catch (err) {
          // Intentionally swallow cleanup errors to preserve app stability.
        }
      }
    });
  }

  DTF.registerEffect = registerEffect;
  DTF.initEffects = initEffects;
  DTF.cleanupNodeTree = cleanupNodeTree;

  if (document.body && !DTF.__effectsHooksBound) {
    DTF.__effectsHooksBound = true;
    document.body.addEventListener('htmx:afterSwap', (evt) => {
      const target = (evt && evt.detail && evt.detail.target) || evt.target;
      if (target) DTF.initEffects(target);
    });
    document.body.addEventListener('htmx:beforeCleanupElement', (evt) => {
      const target = (evt && evt.detail && evt.detail.elt) || evt.target;
      if (target) DTF.cleanupNodeTree(target);
    });
  }
})();
