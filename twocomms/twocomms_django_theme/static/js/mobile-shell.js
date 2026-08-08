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
  let menuReturnFocus = null;
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
    if (event.key === "Escape" && menu?.classList.contains("is-open")) {
      event.preventDefault();
      setMenuOpen(false);
      return;
    }
    if (event.key !== "Tab" || !menu?.classList.contains("is-open")) return;
    const focusable = Array.from(menu.querySelectorAll("a[href], button:not([disabled]), input:not([disabled])"));
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });

  const openExistingFilters = () => {
    const root = document.querySelector("[data-smart-selector]");
    const trigger = root?.querySelector("[data-smart-open-filters]");
    if (!trigger) {
      // The general catalog intentionally keeps its legacy category showcase
      // (the smart selector is category-scoped). Keep its filter affordance
      // useful by taking the shopper to the three primary choices.
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
    const source = document.querySelector("[data-smart-active-count]");
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
  });
})();
