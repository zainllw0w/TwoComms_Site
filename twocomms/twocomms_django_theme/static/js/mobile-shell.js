(() => {
  "use strict";

  const shell = document.querySelector("[data-mobile-site-shell]");
  if (!shell) return;

  const header = shell.querySelector("[data-mobile-shell-header]");
  const menu = shell.querySelector("[data-mobile-menu-panel]");
  const menuToggle = shell.querySelector("[data-mobile-menu-toggle]");
  const searchToggle = shell.querySelector("[data-mobile-search-toggle]");
  const searchForm = shell.querySelector("[data-mobile-search-form]");
  const searchInput = searchForm?.querySelector("input");
  const filterTriggers = Array.from(document.querySelectorAll("[data-mobile-open-filters]"));
  const filterCount = shell.querySelector("[data-mobile-filter-count]");
  const rootFilters = document.querySelector("[data-catalog-root-filters]");
  const rootFilterSheet = rootFilters?.querySelector("[role='dialog']");
  const rootFilterClose = rootFilters?.querySelector("[data-catalog-root-filter-close]");
  let menuReturnFocus = null;
  let filterReturnFocus = null;
  let filterCloseTimer = 0;
  let scrollY = 0;

  const lockBody = () => {
    if (document.body.dataset.mobileShellLocked === "1") return;
    scrollY = window.scrollY;
    document.body.dataset.mobileShellLocked = "1";
    document.body.style.position = "fixed";
    document.body.style.top = `-${scrollY}px`;
    document.body.style.width = "100%";
    document.body.style.overflow = "hidden";
  };

  const unlockBody = () => {
    if (document.body.dataset.mobileShellLocked !== "1") return;
    delete document.body.dataset.mobileShellLocked;
    document.body.style.position = "";
    document.body.style.top = "";
    document.body.style.width = "";
    document.body.style.overflow = "";
    window.scrollTo(0, scrollY);
  };

  const setMenuOpen = (open, restoreFocus = true) => {
    if (!menu || !menuToggle) return;
    menu.classList.toggle("is-open", open);
    menu.hidden = !open;
    menu.setAttribute("aria-hidden", String(!open));
    menuToggle.setAttribute("aria-expanded", String(open));
    header?.classList.toggle("is-menu-open", open);
    if (open) {
      menuReturnFocus = document.activeElement;
      lockBody();
      const first = menu.querySelector("a[href], button:not([disabled])");
      window.requestAnimationFrame(() => first?.focus({ preventScroll: true }));
    } else {
      unlockBody();
      if (restoreFocus && menuReturnFocus?.isConnected) menuReturnFocus.focus({ preventScroll: true });
      menuReturnFocus = null;
    }
  };

  menuToggle?.addEventListener("click", () => setMenuOpen(menu?.classList.contains("is-open") !== true));

  const setRootFiltersOpen = (open, restoreFocus = true) => {
    if (!rootFilters || !rootFilterSheet) return false;
    window.clearTimeout(filterCloseTimer);
    if (open) {
      if (menu?.classList.contains("is-open")) setMenuOpen(false, false);
      filterReturnFocus = document.activeElement;
      rootFilters.hidden = false;
      rootFilters.setAttribute("aria-hidden", "false");
      filterTriggers.forEach((trigger) => trigger.setAttribute("aria-expanded", "true"));
      lockBody();
      window.requestAnimationFrame(() => {
        rootFilters.classList.add("is-open");
        rootFilterClose?.focus({ preventScroll: true });
      });
      return true;
    }
    rootFilters.classList.remove("is-open");
    rootFilters.setAttribute("aria-hidden", "true");
    filterTriggers.forEach((trigger) => trigger.setAttribute("aria-expanded", "false"));
    unlockBody();
    filterCloseTimer = window.setTimeout(() => { rootFilters.hidden = true; }, 220);
    if (restoreFocus && filterReturnFocus?.isConnected) {
      filterReturnFocus.focus({ preventScroll: true });
    }
    filterReturnFocus = null;
    return true;
  };

  rootFilterClose?.addEventListener("click", () => setRootFiltersOpen(false));
  rootFilters?.addEventListener("pointerdown", (event) => {
    if (event.target === rootFilters) setRootFiltersOpen(false);
  });

  searchToggle?.addEventListener("click", () => {
    const open = header?.classList.toggle("is-searching");
    searchToggle.setAttribute("aria-expanded", String(Boolean(open)));
    if (open) window.requestAnimationFrame(() => searchInput?.focus({ preventScroll: true }));
    else searchInput?.blur();
  });

  document.addEventListener("pointerdown", (event) => {
    if (!menu?.classList.contains("is-open")) return;
    if (menu.contains(event.target) || menuToggle?.contains(event.target)) return;
    setMenuOpen(false, false);
  }, true);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && rootFilters?.classList.contains("is-open")) {
      event.preventDefault();
      setRootFiltersOpen(false);
      return;
    }
    if (event.key === "Escape" && menu?.classList.contains("is-open")) {
      event.preventDefault();
      setMenuOpen(false);
      return;
    }
    const activePanel = rootFilters?.classList.contains("is-open") ? rootFilterSheet : (menu?.classList.contains("is-open") ? menu : null);
    if (event.key !== "Tab" || !activePanel) return;
    const focusable = Array.from(activePanel.querySelectorAll("a[href], button:not([disabled]), input:not([disabled]), select:not([disabled])"));
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });

  const openExistingFilters = () => {
    if (rootFilters) return setRootFiltersOpen(true);
    const root = document.querySelector("[data-smart-selector]");
    const trigger = root?.querySelector("[data-smart-open-filters]");
    if (!trigger) {
      const categories = document.getElementById("catalog-mobile-reference-categories");
      categories?.scrollIntoView({ behavior: "smooth", block: "start" });
      return Boolean(categories);
    }
    trigger.click();
    return true;
  };

  filterTriggers.forEach((filterTrigger) => filterTrigger.addEventListener("click", (event) => {
    event.preventDefault();
    openExistingFilters();
  }));

  const syncFilterCount = () => {
    if (!filterCount) return;
    const source = document.querySelector("[data-root-active-count], [data-smart-active-count]");
    if (!source || source.hidden) {
      filterCount.hidden = true;
      filterCount.textContent = "0";
      return;
    }
    const count = Number.parseInt(source.textContent || "0", 10);
    filterCount.textContent = String(Number.isFinite(count) ? count : 0);
    filterCount.hidden = !count;
  };
  syncFilterCount();
  const smartRoot = document.querySelector("[data-smart-selector]");
  if (smartRoot && "MutationObserver" in window) {
    new MutationObserver(syncFilterCount).observe(smartRoot, { subtree: true, childList: true, attributes: true, attributeFilter: ["hidden", "aria-pressed"] });
  }

  window.addEventListener("popstate", () => {
    if (menu?.classList.contains("is-open")) setMenuOpen(false, false);
    if (rootFilters?.classList.contains("is-open")) setRootFiltersOpen(false, false);
  });
})();
