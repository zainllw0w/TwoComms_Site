(() => {
  const isShell = document.body?.dataset?.mgmtShell === '1';
  if (!isShell) return;

  const contentArea = document.querySelector('.content-area');
  const navMenu = document.querySelector('.nav-menu');
  const sidebarRail = document.getElementById('sidebar-rail');
  const sidebarNavSlot = document.getElementById('sidebar-nav-slot');
  const sidebarNavPanel = document.querySelector('.sidebar-nav-panel');
  const sidebarScroll = document.getElementById('sidebar-rail-scroll');
  const sidebarCollapseToggle = document.getElementById('sidebar-collapse-toggle');
  const sidebarCollapsedLauncher = document.getElementById('sidebar-collapsed-launcher');
  const globalHeader = document.querySelector('.global-header');
  if (!contentArea || !navMenu) return;

  const getUrlKey = (u) => `${u.pathname}${u.search || ''}`;
  const SIDEBAR_COLLAPSE_KEY = 'management_shell_sidebar_collapsed';

  const readStoredCollapseState = () => {
    try {
      return window.localStorage?.getItem(SIDEBAR_COLLAPSE_KEY) === '1';
    } catch (e) {
      return false;
    }
  };

  const writeStoredCollapseState = (collapsed) => {
    try {
      if (collapsed) {
        window.localStorage?.setItem(SIDEBAR_COLLAPSE_KEY, '1');
      } else {
        window.localStorage?.removeItem(SIDEBAR_COLLAPSE_KEY);
      }
    } catch (e) {
      // ignore storage errors
    }
  };

  let currentUrl = getUrlKey(new URL(window.location.href));
  const cache = new Map();
  const titleCache = new Map();
  const scrollCache = new Map();
  let userCollapsed = readStoredCollapseState();
  let navigationRequestId = 0;
  let activeNavigationController = null;

  if (sidebarRail && sidebarNavSlot && sidebarNavPanel && sidebarCollapsedLauncher) {
    sidebarRail.dataset.sidebarReady = 'true';
  }

  const initialRoot = document.getElementById('mgmt-page-root');
  if (!initialRoot) return;
  cache.set(currentUrl, initialRoot);
  titleCache.set(currentUrl, document.title || '');

  const isStackedShell = () => (window.innerWidth || document.documentElement.clientWidth || 0) <= 1080;
  const getActiveScrollTop = () => (
    isStackedShell()
      ? (window.scrollY || document.documentElement.scrollTop || 0)
      : (contentArea.scrollTop || 0)
  );
  const setActiveScrollTop = (value) => {
    if (isStackedShell()) {
      window.scrollTo(0, typeof value === 'number' ? value : 0);
      return;
    }
    contentArea.scrollTop = typeof value === 'number' ? value : 0;
  };

  const setActiveNav = (targetUrl) => {
    const targetPath = targetUrl.pathname;
    navMenu.querySelectorAll('a.nav-item').forEach((a) => {
      const href = a.getAttribute('href') || '';
      if (!href || href.startsWith('#')) return;
      try {
        const u = new URL(href, window.location.origin);
        a.classList.toggle('active', u.pathname === targetPath);
      } catch (e) {
        // ignore
      }
    });
  };

  const loadedSrc = new Set(Array.from(document.scripts).map((s) => s.src).filter(Boolean));

  const syncSidebarScrollCue = () => {
    if (!sidebarScroll) return;

    if (isStackedShell()) {
      sidebarScroll.dataset.scrollCue = 'hidden';
      return;
    }

    const overflow = sidebarScroll.scrollHeight - sidebarScroll.clientHeight;
    if (overflow <= 18) {
      sidebarScroll.dataset.scrollCue = 'hidden';
      return;
    }

    const remaining = overflow - sidebarScroll.scrollTop;
    sidebarScroll.dataset.scrollCue = remaining > 18 ? 'visible' : 'hidden';
  };

  const syncSidebarCollapseState = (stackedShell) => {
    if (!sidebarRail) return false;

    const collapsed = !stackedShell && userCollapsed;
    sidebarRail.dataset.sidebarCollapsed = collapsed ? 'true' : 'false';
    document.body.dataset.sidebarCollapsed = collapsed ? 'true' : 'false';

    if (sidebarCollapseToggle) {
      sidebarCollapseToggle.hidden = stackedShell;
      sidebarCollapseToggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    }
    if (sidebarCollapsedLauncher) {
      sidebarCollapsedLauncher.hidden = stackedShell;
      sidebarCollapsedLauncher.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    }
    return collapsed;
  };

  const measureNavLayerHeight = (node) => {
    if (!node) return 0;
    const rect = node.getBoundingClientRect();
    return Math.ceil(rect.height || node.scrollHeight || node.offsetHeight || 0);
  };

  const syncSidebarNavSlotHeight = (stackedShell, collapsed) => {
    if (!sidebarNavSlot) return;

    if (stackedShell) {
      sidebarNavSlot.style.removeProperty('height');
      return;
    }

    const target = collapsed ? sidebarCollapsedLauncher : sidebarNavPanel;
    const targetHeight = measureNavLayerHeight(target);
    if (targetHeight > 0) {
      sidebarNavSlot.style.height = `${targetHeight}px`;
    }
  };

  const syncShellResponsiveState = () => {
    const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
    const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
    const stackedShell = isStackedShell();

    document.body.dataset.shellLayout = stackedShell ? 'stacked' : 'rail';
    if (globalHeader) {
      const headerHeight = Math.ceil(globalHeader.getBoundingClientRect().height || 0);
      document.documentElement.style.setProperty('--shell-header-offset', `${headerHeight || 76}px`);
    }

    let rowMode = 'table';
    if (viewportWidth < 1180) rowMode = 'card';
    else if (viewportWidth < 1400) rowMode = 'condensed';
    document.body.dataset.rowMode = rowMode;

    if (!sidebarRail) return;

    const collapsed = syncSidebarCollapseState(stackedShell);
    syncSidebarNavSlotHeight(stackedShell, collapsed);

    if (stackedShell) {
      sidebarRail.dataset.railTier = 'stacked';
      sidebarRail.dataset.railProgress = 'deep';
      syncSidebarScrollCue();
      return;
    }

    let railTier = 'expanded';
    if (viewportWidth < 1280 || viewportHeight < 780) railTier = 'collapsed';
    else if (viewportWidth < 1440 || viewportHeight < 900) railTier = 'compact';
    sidebarRail.dataset.railTier = railTier;

    const scrollTop = getActiveScrollTop();
    let railProgress = 'top';
    if (scrollTop > 320) railProgress = 'deep';
    else if (scrollTop > 72) railProgress = 'mid';
    sidebarRail.dataset.railProgress = railProgress;
    syncSidebarScrollCue();
  };

  let syncFrame = null;
  const scheduleShellResponsiveState = () => {
    if (syncFrame !== null) return;
    syncFrame = window.requestAnimationFrame(() => {
      syncFrame = null;
      syncShellResponsiveState();
    });
  };

  const isCurrentNavigation = (requestId, signal) => {
    if (requestId !== navigationRequestId) return false;
    return !(signal && signal.aborted);
  };

  const abortActiveNavigation = () => {
    if (!activeNavigationController) return;
    activeNavigationController.abort();
    activeNavigationController = null;
  };

  const execScriptsIn = async (rootEl, shouldContinue = () => true) => {
    const jsBox = rootEl.querySelector('#mgmt-page-js');
    if (!jsBox) return;

    const scripts = Array.from(jsBox.querySelectorAll('script'));
    for (const s of scripts) {
      if (!shouldContinue()) return;
      const type = (s.getAttribute('type') || '').toLowerCase();
      const src = s.getAttribute('src');

      if (type && type !== 'text/javascript' && type !== 'application/javascript' && type !== 'module') {
        // application/json etc.
        continue;
      }

      if (src) {
        let abs = src;
        try {
          abs = new URL(src, window.location.origin).href;
        } catch (e) {}

        if (loadedSrc.has(abs)) continue;

        await new Promise((resolve) => {
          if (!shouldContinue()) {
            resolve(false);
            return;
          }
          const ns = document.createElement('script');
          ns.src = abs;
          ns.async = false;
          ns.onload = () => resolve(true);
          ns.onerror = () => resolve(false);
          document.head.appendChild(ns);
          loadedSrc.add(abs);
        });
        continue;
      }

      const code = (s.textContent || '').trim();
      if (!code || !shouldContinue()) continue;
      const ns = document.createElement('script');
      ns.type = 'text/javascript';
      ns.textContent = code;
      document.head.appendChild(ns);
      document.head.removeChild(ns);
    }
  };

  const swapToRoot = (nextUrlKey, nextRoot, nextTitle, pushHistory) => {
    // Save scroll for current tab
    scrollCache.set(currentUrl, getActiveScrollTop());

    // Detach current root
    const currentRoot = cache.get(currentUrl);
    // Ensure we don't keep "loading dim" when this page is cached and later revisited
    if (currentRoot) currentRoot.style.opacity = '';
    if (currentRoot && currentRoot.isConnected) currentRoot.remove();

    // Attach next
    if (nextRoot) nextRoot.style.opacity = '';
    contentArea.appendChild(nextRoot);
    currentUrl = nextUrlKey;

    if (typeof nextTitle === 'string' && nextTitle) document.title = nextTitle;
    if (pushHistory) history.pushState({ url: nextUrlKey }, '', nextUrlKey);

    // Restore scroll
    const prevScroll = scrollCache.get(nextUrlKey);
    setActiveScrollTop(prevScroll);

    setActiveNav(new URL(nextUrlKey, window.location.origin));
    scheduleShellResponsiveState();
  };

  const fetchAndBuild = async (targetUrl, signal) => {
    const urlKey = getUrlKey(targetUrl);
    const res = await fetch(urlKey, { credentials: 'same-origin', signal });
    if (!res.ok) return null;
    const html = await res.text();
    if (signal && signal.aborted) return null;

    const doc = new DOMParser().parseFromString(html, 'text/html');
    const newRoot = doc.getElementById('mgmt-page-root');
    if (!newRoot) return null;

    const adopted = document.importNode(newRoot, true);
    const title = (doc.title || '').trim();
    return { urlKey, root: adopted, title };
  };

  const navigate = async (href, pushHistory = true) => {
    let targetUrl;
    try {
      targetUrl = new URL(href, window.location.origin);
    } catch (e) {
      window.location.href = href;
      return;
    }

    const urlKey = getUrlKey(targetUrl);
    if (urlKey === currentUrl) {
      abortActiveNavigation();
      navigationRequestId += 1;
      const visibleRoot = cache.get(currentUrl);
      if (visibleRoot) visibleRoot.style.opacity = '';
      return;
    }

    abortActiveNavigation();
    const requestId = ++navigationRequestId;
    const controller = typeof AbortController === 'function' ? new AbortController() : null;
    const signal = controller ? controller.signal : null;
    activeNavigationController = controller;

    if (cache.has(urlKey)) {
      if (isCurrentNavigation(requestId, signal)) {
        swapToRoot(urlKey, cache.get(urlKey), titleCache.get(urlKey) || '', pushHistory);
      }
      if (activeNavigationController === controller) activeNavigationController = null;
      return;
    }

    // Loading fallback
    const currentRoot = cache.get(currentUrl);
    if (currentRoot) currentRoot.style.opacity = '0.6';

    let built = null;
    try {
      built = await fetchAndBuild(targetUrl, signal);
    } catch (e) {
      if (signal && signal.aborted) return;
      if (currentRoot) currentRoot.style.opacity = '';
      window.location.href = urlKey;
      return;
    } finally {
      if (activeNavigationController === controller && signal && signal.aborted) {
        activeNavigationController = null;
      }
    }

    if (!isCurrentNavigation(requestId, signal)) {
      if (currentRoot) currentRoot.style.opacity = '';
      return;
    }

    if (!built) {
      if (currentRoot) currentRoot.style.opacity = '';
      if (signal && signal.aborted) return;
      if (activeNavigationController === controller) activeNavigationController = null;
      window.location.href = urlKey;
      return;
    }

    cache.set(built.urlKey, built.root);
    titleCache.set(built.urlKey, built.title || built.urlKey);

    // Attach first so scripts can find DOM
    if (!isCurrentNavigation(requestId, signal)) {
      if (currentRoot) currentRoot.style.opacity = '';
      return;
    }
    swapToRoot(built.urlKey, built.root, built.title, pushHistory);
    await execScriptsIn(built.root, () => isCurrentNavigation(requestId, signal));
    if (!isCurrentNavigation(requestId, signal)) return;

    // Restore opacity
    const newCurrentRoot = cache.get(currentUrl);
    if (newCurrentRoot) newCurrentRoot.style.opacity = '';
    scheduleShellResponsiveState();
    if (activeNavigationController === controller) activeNavigationController = null;
  };

  navMenu.addEventListener('click', (e) => {
    const link = e.target.closest('a.nav-item');
    if (!link) return;
    const href = link.getAttribute('href') || '';
    if (!href || href.startsWith('#')) return;
    e.preventDefault();
    navigate(href, true);
  });

  window.addEventListener('popstate', () => {
    const urlKey = getUrlKey(new URL(window.location.href));
    if (urlKey === currentUrl) return;
    navigate(urlKey, false);
  });

  contentArea.addEventListener('scroll', scheduleShellResponsiveState, { passive: true });
  window.addEventListener('scroll', scheduleShellResponsiveState, { passive: true });
  window.addEventListener('resize', scheduleShellResponsiveState);
  window.addEventListener('load', scheduleShellResponsiveState);
  if (sidebarScroll) {
    sidebarScroll.addEventListener('scroll', syncSidebarScrollCue, { passive: true });
  }
  if (sidebarCollapseToggle) {
    sidebarCollapseToggle.addEventListener('click', () => {
      userCollapsed = true;
      writeStoredCollapseState(true);
      scheduleShellResponsiveState();
    });
  }
  if (sidebarCollapsedLauncher) {
    sidebarCollapsedLauncher.addEventListener('click', () => {
      userCollapsed = false;
      writeStoredCollapseState(false);
      scheduleShellResponsiveState();
    });
  }
  scheduleShellResponsiveState();
})();
