(() => {
  "use strict";

  const root = document.querySelector("[data-smart-selector]");
  if (!root) return;

  const grid = root.querySelector("[data-smart-product-grid]");
  const overlay = root.querySelector("[data-smart-filter-sheet]");
  const sheet = overlay?.querySelector(".smart-selector__sheet");
  const pagination = root.querySelector("[data-smart-pagination]");
  const sentinel = root.querySelector("[data-smart-sentinel]");
  const loadStatus = root.querySelector("[data-smart-load-status]");
  const sortControl = root.querySelector("[data-smart-sort]");
  const sheetTitle = root.querySelector("#smart-selector-sheet-title");
  const sheetEyebrow = sheetTitle?.previousElementSibling;
  const main = root.closest("main");
  const mobileNavigation = document.querySelector(
    "[data-mobile-bottom-nav], .bottom-nav, .mobile-bottom-nav, .bottom-navigation, .mobile-nav"
  );
  const mainContain = main?.style.contain || "";
  const repeatableFilters = new Set([
    "theme",
    "collection",
    "audience",
    "availability",
    "fit",
    "size",
    "thermo",
  ]);
  const resettableFilters = [
    "theme",
    "collection",
    "audience",
    "fit",
    "availability",
    "size",
    "color",
    "thermo",
    "sort",
    "page",
  ];
  const allowedSorts = new Set(["recommended", "price-asc", "price-desc"]);
  const prefersReducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
  const lockState = {};
  let lastFilterTrigger = null;
  let loadingNextPage = false;
  let nextOrder = 0;
  let sheetHistoryActive = false;
  let navWasInert = false;
  let sheetMode = "all";
  const sheetModes = {
    all: { eyebrow: "Каталог", title: "Підібрати модель" },
    theme: { eyebrow: "Швидкий вибір", title: "Оберіть тему" },
    fit: { eyebrow: "Швидкий вибір", title: "Оберіть крій" },
    color: { eyebrow: "Швидкий вибір", title: "Оберіть колір" },
    sort: { eyebrow: "Каталог", title: "Сортування" },
  };

  const emitCatalogAnalytics = (eventName, payload = {}) => {
    if (!eventName) return;
    const detail = {
      category: root.dataset.smartCategory || "",
      language: document.documentElement.lang || "",
      ...payload,
    };
    try {
      if (typeof window.trackEvent === "function") {
        window.trackEvent(eventName, detail);
      } else if (Array.isArray(window.dataLayer)) {
        window.dataLayer.push({ event: eventName, ...detail });
      }
    } catch (_) {
      // Analytics must never interfere with catalog navigation.
    }
  };

  const productItems = () => Array.from(grid?.querySelectorAll("[data-smart-product-item]") || []);

  const assignProductOrder = (items) => {
    items.forEach((item) => {
      if (!item.dataset.smartOrder) {
        nextOrder += 1;
        item.dataset.smartOrder = String(nextOrder);
      }
    });
  };

  const checkFavoriteButton = (button) => {
    const productId = button?.getAttribute("data-product-id");
    if (productId && typeof window.checkFavoriteStatus === "function") {
      window.checkFavoriteStatus(productId, button);
    }
  };

  const favoriteStatusObserver = "IntersectionObserver" in window
    ? new IntersectionObserver(
        (entries, observer) => {
          entries.forEach((entry) => {
            if (!entry.isIntersecting) return;
            checkFavoriteButton(entry.target);
            observer.unobserve(entry.target);
          });
        },
        { rootMargin: "100px 0px", threshold: 0.01 }
      )
    : null;

  const observeFavoriteButtons = (items) => {
    items.forEach((item) => {
      item.querySelectorAll(".favorite-btn").forEach((button) => {
        if (favoriteStatusObserver) favoriteStatusObserver.observe(button);
        else checkFavoriteButton(button);
      });
    });
  };

  const closeColorStacks = ({ restoreFocus = false } = {}) => {
    root.querySelectorAll("[data-smart-color-stack].is-open").forEach((stack) => {
      stack.classList.remove("is-open");
      const toggle = stack.querySelector("[data-smart-color-toggle]");
      toggle?.setAttribute("aria-expanded", "false");
      if (restoreFocus) toggle?.focus();
    });
  };

  const toggleRepeatedParameter = (url, key, value) => {
    const currentValues = url.searchParams.getAll(key);
    const hasValue = currentValues.includes(value);
    url.searchParams.delete(key);

    currentValues.forEach((currentValue) => {
      if (currentValue !== value) url.searchParams.append(key, currentValue);
    });

    if (!hasValue) url.searchParams.append(key, value);
  };

  const buildFacetUrl = (filter, value) => {
    const url = new URL(window.location.href);
    toggleRepeatedParameter(url, filter, value);
    url.searchParams.delete("page");
    return url;
  };

  const navigateToFacet = (filter, value, source = "unknown") => {
    if (!repeatableFilters.has(filter) || !value) return;
    const url = buildFacetUrl(filter, value);
    emitCatalogAnalytics("CatalogFilterApply", {
      facet: filter,
      value,
      values: url.searchParams.getAll(filter),
      source,
    });
    window.location.assign(url.toString());
  };

  const resetUrl = () => {
    const url = new URL(window.location.href);
    resettableFilters.forEach((key) => url.searchParams.delete(key));
    return url;
  };

  const comparePrice = (a, b, direction) => {
    const priceA = Number.parseFloat((a.dataset.smartPrice || "0").replace(",", "."));
    const priceB = Number.parseFloat((b.dataset.smartPrice || "0").replace(",", "."));
    const delta = (Number.isFinite(priceA) ? priceA : 0) - (Number.isFinite(priceB) ? priceB : 0);
    return direction === "price-desc" ? -delta : delta;
  };

  const applySort = (sortValue) => {
    if (!grid || !allowedSorts.has(sortValue)) return;

    const currentItems = productItems();
    const items = [...currentItems].sort((a, b) => {
      if (sortValue === "recommended") {
        return Number(a.dataset.smartOrder) - Number(b.dataset.smartOrder);
      }
      const priceDelta = comparePrice(a, b, sortValue);
      return priceDelta || Number(a.dataset.smartOrder) - Number(b.dataset.smartOrder);
    });

    const orderChanged = items.some((item, index) => item !== currentItems[index]);
    if (orderChanged) {
      const fragment = document.createDocumentFragment();
      items.forEach((item) => fragment.appendChild(item));
      grid.appendChild(fragment);
    }

    if (sortControl && sortControl.value !== sortValue) sortControl.value = sortValue;
    const activeOption = root.querySelector(`[data-smart-sort-value="${CSS.escape(sortValue)}"]`);
    root.querySelectorAll("[data-smart-sort-value]").forEach((option) => {
      option.setAttribute("aria-pressed", String(option === activeOption));
    });
    root.querySelectorAll("[data-smart-sort-label]").forEach((label) => {
      label.textContent = activeOption?.textContent?.trim() || sortControl?.selectedOptions?.[0]?.textContent || "";
    });
  };

  const readInitialSort = () => {
    const requested = new URL(window.location.href).searchParams.get("sort") || "recommended";
    return allowedSorts.has(requested) ? requested : "recommended";
  };

  const updateActiveCount = () => {
    const activeFacets = new Set();
    root.querySelectorAll('[data-smart-filter][aria-pressed="true"]').forEach((control) => {
      const key = control.dataset.smartFilter;
      const value = control.dataset.smartValue;
      if (repeatableFilters.has(key) && value) activeFacets.add(`${key}:${value}`);
    });
    if (root.querySelector(".smart-selector__colors a.is-active, .smart-selector__sheet-colors a.is-active")) {
      activeFacets.add("color:selected");
    }
    const activeCount = activeFacets.size;

    root.querySelectorAll("[data-smart-active-count]").forEach((badge) => {
      badge.textContent = String(activeCount);
      badge.hidden = activeCount === 0;
    });
  };

  const updateQuickFacetValues = () => {
    const labels = { theme: "Усі", fit: "Будь-який", color: "Усі" };
    const themeControls = root.querySelectorAll(
      '[data-smart-filter="theme"][aria-pressed="true"], [data-smart-filter="collection"][aria-pressed="true"]'
    );
    const fitControls = root.querySelectorAll('[data-smart-filter="fit"][aria-pressed="true"]');
    const labelFor = (controls, fallback) => {
      const values = Array.from(controls)
        .map((control) => control.querySelector("span:not([aria-hidden])")?.childNodes?.[0]?.textContent?.trim() || control.textContent.trim())
        .filter(Boolean);
      const unique = Array.from(new Set(values));
      return unique.length > 1 ? `${unique.length} обрано` : unique[0] || fallback;
    };
    labels.theme = labelFor(themeControls, labels.theme);
    labels.fit = labelFor(fitControls, labels.fit);
    const activeColor = root.querySelector(".smart-selector__colors a.is-active, .smart-selector__sheet-colors a.is-active");
    if (activeColor) {
      const colorLabel = activeColor.cloneNode(true);
      colorLabel.querySelectorAll(".smart-selector__choice-count, .visually-hidden").forEach((node) => node.remove());
      labels.color = activeColor.getAttribute("title") || colorLabel.textContent.trim();
    }
    root.querySelectorAll("[data-smart-quick-value]").forEach((value) => {
      const facet = value.dataset.smartQuickValue;
      if (facet && labels[facet]) value.textContent = labels[facet];
    });
  };

  const lockPage = () => {
    const body = document.body;
    const scrollbarWidth = Math.max(0, window.innerWidth - document.documentElement.clientWidth);
    lockState.scrollY = window.scrollY;
    lockState.position = body.style.position;
    lockState.top = body.style.top;
    lockState.width = body.style.width;
    lockState.overflow = body.style.overflow;
    lockState.paddingRight = body.style.paddingRight;
    body.style.position = "fixed";
    body.style.top = `-${lockState.scrollY}px`;
    body.style.width = "100%";
    body.style.overflow = "hidden";
    if (scrollbarWidth) body.style.paddingRight = `${scrollbarWidth}px`;
  };

  const unlockPage = () => {
    const body = document.body;
    body.style.position = lockState.position || "";
    body.style.top = lockState.top || "";
    body.style.width = lockState.width || "";
    body.style.overflow = lockState.overflow || "";
    body.style.paddingRight = lockState.paddingRight || "";
    if (Number.isFinite(lockState.scrollY)) window.scrollTo(0, lockState.scrollY);
  };

  const setBackgroundInert = (inert) => {
    Array.from(root.children).forEach((child) => {
      if (child === overlay) return;
      child.inert = inert;
    });

    if (mobileNavigation) {
      if (inert) navWasInert = Boolean(mobileNavigation.inert);
      mobileNavigation.inert = inert || navWasInert;
    }
  };

  const focusableElements = () => {
    if (!sheet) return [];
    return Array.from(
      sheet.querySelectorAll(
        'a[href], button:not([disabled]), select:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'
      )
    ).filter((element) => element.getClientRects().length > 0);
  };

  const closeFilters = ({ restoreFocus = true, consumeHistory = true } = {}) => {
    if (!overlay?.classList.contains("is-open")) return;
    overlay.classList.remove("is-open");
    overlay.setAttribute("aria-hidden", "true");
    root.classList.remove("is-filter-open");
    root.querySelectorAll("[data-smart-open-filters]").forEach((trigger) => {
      trigger.setAttribute("aria-expanded", "false");
    });
    setBackgroundInert(false);
    unlockPage();

    const trigger = lastFilterTrigger;
    lastFilterTrigger = null;
    emitCatalogAnalytics("CatalogFilterSheetClose", {
      source: trigger?.dataset.smartFocusFilter || "all",
    });
    if (restoreFocus && trigger?.isConnected) trigger.focus({ preventScroll: true });

    if (consumeHistory && sheetHistoryActive && window.history.state?.smartFilterSheet) {
      sheetHistoryActive = false;
      window.history.back();
    } else {
      sheetHistoryActive = false;
    }
  };

  const openFilters = (trigger) => {
    if (!overlay || !sheet || overlay.classList.contains("is-open")) return;
    lastFilterTrigger = trigger;
    sheetMode = trigger?.dataset.smartFocusFilter || "all";
    if (!sheetModes[sheetMode]) sheetMode = "all";
    overlay.dataset.smartSheetMode = sheetMode;
    const modeCopy = sheetModes[sheetMode];
    if (sheetTitle) sheetTitle.textContent = modeCopy.title;
    if (sheetEyebrow) sheetEyebrow.textContent = modeCopy.eyebrow;
    sheet.querySelectorAll("[data-smart-filter-section]").forEach((section) => {
      section.hidden = sheetMode !== "all" && section.dataset.smartFilterSection !== sheetMode;
    });
    emitCatalogAnalytics("CatalogFilterSheetOpen", {
      source: trigger?.dataset.smartFocusFilter || "all",
    });
    overlay.classList.add("is-open");
    overlay.setAttribute("aria-hidden", "false");
    root.classList.add("is-filter-open");
    root.querySelectorAll("[data-smart-open-filters]").forEach((candidate) => {
      candidate.setAttribute("aria-expanded", candidate === trigger ? "true" : "false");
    });
    setBackgroundInert(true);
    lockPage();

    window.history.pushState(
      { ...(window.history.state || {}), smartFilterSheet: true },
      "",
      window.location.href
    );
    sheetHistoryActive = true;

    const focusFilter = sheetMode === "all" ? null : sheetMode;
    const section = focusFilter
      ? sheet.querySelector(`[data-smart-filter-section="${focusFilter}"]`)
      : null;
    const target = section?.querySelector("button, a[href]") || sheet.querySelector("[data-smart-close-filters]") || sheet;
    section?.scrollIntoView({ block: "start" });
    const focusTarget = () => {
      if (!overlay.classList.contains("is-open") || !target.isConnected) return;
      if (sheet.contains(document.activeElement)) return;
      target.focus({ preventScroll: !section });
    };
    // The trigger becomes inert during the opening click. Focus once now for
    // fast user agents, then retry after inert/default-action processing so
    // Chromium cannot leave the active element on <body>.
    focusTarget();
    window.requestAnimationFrame(focusTarget);
    window.setTimeout(focusTarget, 60);
  };

  const setDisclosureState = (value, expanded) => {
    root.querySelectorAll(`[data-smart-disclosure-value="${CSS.escape(value)}"]`).forEach((control) => {
      const targetId = control.getAttribute("aria-controls");
      const target = targetId ? document.getElementById(targetId) : null;
      control.setAttribute("aria-expanded", String(expanded));
      control.closest(".smart-selector__branch")?.classList.toggle("is-open", expanded);
      if (!target) return;

      if (expanded) {
        target.hidden = false;
        window.requestAnimationFrame(() => target.classList.add("is-visible"));
      } else {
        target.classList.remove("is-visible");
        window.setTimeout(() => {
          if (control.getAttribute("aria-expanded") === "false") target.hidden = true;
        }, 160);
      }
    });
  };

  const initializeDisclosures = () => {
    const values = new Set(
      Array.from(root.querySelectorAll("[data-smart-disclosure-value]"))
        .map((control) => control.dataset.smartDisclosureValue)
        .filter(Boolean)
    );

    values.forEach((value) => {
      const branches = Array.from(root.querySelectorAll(`[data-smart-disclosure-value="${CSS.escape(value)}"]`))
        .map((control) => control.closest(".smart-selector__branch"))
        .filter(Boolean);
      const hasSelectedChild = branches.some((branch) =>
        branch.querySelector('.smart-selector__branch-children [aria-pressed="true"]')
      );
      const explicitlyExpanded = Array.from(
        root.querySelectorAll(`[data-smart-disclosure-value="${CSS.escape(value)}"]`)
      ).some((control) => control.getAttribute("aria-expanded") === "true");
      setDisclosureState(value, hasSelectedChild || explicitlyExpanded);
    });
  };

  const measureMobileNavigation = () => {
    if (!mobileNavigation) return;
    const height = Math.ceil(mobileNavigation.getBoundingClientRect().height);
    if (height > 0) root.style.setProperty("--mobile-nav-reserved", `${height}px`);
  };

  root.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (!target) return;

    const colorToggle = target.closest("[data-smart-color-toggle]");
    if (colorToggle && root.contains(colorToggle)) {
      event.preventDefault();
      const stack = colorToggle.closest("[data-smart-color-stack]");
      const willOpen = !stack?.classList.contains("is-open");
      closeColorStacks();
      stack?.classList.toggle("is-open", willOpen);
      colorToggle.setAttribute("aria-expanded", String(willOpen));
      return;
    }

    const colorChoice = target.closest("[data-smart-color-choice]");
    if (colorChoice && root.contains(colorChoice)) {
      closeColorStacks();
      return;
    }

    const cardLink = target.closest(".smart-product-card [data-product-card-link]");
    if (cardLink && root.contains(cardLink)) {
      const card = cardLink.closest(".smart-product-card");
      if (card) {
        emitCatalogAnalytics("CatalogSelectItem", {
          product_id: card.dataset.productId || "",
          offer_id: card.dataset.defaultOfferId || "",
          item_name: card.dataset.productTitle || "",
          item_category: card.dataset.productCategory || "",
          position: productItems().indexOf(card) + 1,
        });
      }
      return;
    }

    const disclosure = target.closest("[data-smart-disclosure]");
    if (disclosure && root.contains(disclosure)) {
      event.preventDefault();
      const value = disclosure.dataset.smartDisclosureValue || "";
      if (value) setDisclosureState(value, disclosure.getAttribute("aria-expanded") !== "true");
      return;
    }

    const filter = target.closest("[data-smart-filter]");
    if (filter && root.contains(filter)) {
      event.preventDefault();
      navigateToFacet(
        filter.dataset.smartFilter || "",
        filter.dataset.smartValue || "",
        filter.dataset.smartSource || "unknown"
      );
      return;
    }

    const clearFilter = target.closest("[data-smart-clear-filter]");
    if (clearFilter && root.contains(clearFilter)) {
      event.preventDefault();
      const facet = clearFilter.dataset.smartClearFilter || "";
      if (!resettableFilters.includes(facet)) return;
      const url = new URL(window.location.href);
      url.searchParams.delete(facet);
      url.searchParams.delete("page");
      emitCatalogAnalytics("CatalogFilterClear", { source: "focused-sheet", facet });
      window.location.assign(url.toString());
      return;
    }

    const reset = target.closest("[data-smart-reset]");
    if (reset && root.contains(reset)) {
      event.preventDefault();
      const url = new URL(window.location.href);
      const focusedKeys = {
        theme: ["theme", "collection"],
        fit: ["fit"],
        color: ["color"],
        sort: ["sort"],
      };
      const keys = focusedKeys[sheetMode];
      if (keys) {
        keys.forEach((key) => url.searchParams.delete(key));
        url.searchParams.delete("page");
      } else {
        resettableFilters.forEach((key) => url.searchParams.delete(key));
      }
      emitCatalogAnalytics("CatalogFilterClear", { source: "reset", mode: sheetMode });
      window.location.assign(url.toString());
      return;
    }

    const opener = target.closest("[data-smart-open-filters]");
    if (opener && root.contains(opener)) {
      event.preventDefault();
      openFilters(opener);
      return;
    }

    const closer = target.closest("[data-smart-close-filters]");
    if (closer && root.contains(closer)) {
      event.preventDefault();
      closeFilters();
      return;
    }

    const sortOption = target.closest("[data-smart-sort-value]");
    if (sortOption && root.contains(sortOption)) {
      event.preventDefault();
      const requested = sortOption.dataset.smartSortValue || "recommended";
      const selected = allowedSorts.has(requested) ? requested : "recommended";
      emitCatalogAnalytics("CatalogSortApply", { value: selected, source: "sheet" });
      const url = new URL(window.location.href);
      if (selected === "recommended") url.searchParams.delete("sort");
      else url.searchParams.set("sort", selected);
      url.searchParams.delete("page");
      window.location.assign(url.toString());
    }
  });

  document.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (target && !target.closest("[data-smart-color-stack]")) closeColorStacks();
  });

  overlay?.addEventListener("click", (event) => {
    if (event.target === overlay) closeFilters();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && root.querySelector("[data-smart-color-stack].is-open")) {
      event.preventDefault();
      closeColorStacks({ restoreFocus: true });
      return;
    }

    if (!overlay?.classList.contains("is-open")) return;

    if (event.key === "Escape") {
      event.preventDefault();
      closeFilters();
      return;
    }

    if (event.key !== "Tab") return;
    const focusable = focusableElements();
    if (!focusable.length) {
      event.preventDefault();
      sheet?.focus();
      return;
    }

    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });

  sortControl?.addEventListener("change", () => {
    const requested = sortControl.value;
    const selected = allowedSorts.has(requested) ? requested : "recommended";
    const url = new URL(window.location.href);
    if (selected === "recommended") url.searchParams.delete("sort");
    else url.searchParams.set("sort", selected);
    url.searchParams.delete("page");
    window.location.assign(url.toString());
  });

  const progressiveLoad = async (observer) => {
    if (!grid || loadingNextPage) return;
    const nextPageUrl = grid.dataset.nextPageUrl;
    if (!nextPageUrl) {
      observer?.disconnect();
      return;
    }

    loadingNextPage = true;
    observer?.unobserve(sentinel);
    grid.setAttribute("aria-busy", "true");
    if (loadStatus) loadStatus.textContent = loadStatus.dataset.loadingText || "";

    try {
      const response = await window.fetch(new URL(nextPageUrl, window.location.href), {
        credentials: "same-origin",
        headers: {
          Accept: "text/html",
          "X-Requested-With": "XMLHttpRequest",
        },
      });
      if (!response.ok) throw new Error(`Catalog page request failed: ${response.status}`);

      const html = await response.text();
      const documentFragment = new DOMParser().parseFromString(html, "text/html");
      const remoteRoot = documentFragment.querySelector("[data-smart-selector]");
      const remoteGrid = remoteRoot?.querySelector("[data-smart-product-grid]");
      if (!remoteGrid) throw new Error("Smart Selector grid missing in next page response");

      const knownIds = new Set(
        productItems()
          .map((item) => item.querySelector("[data-product-id]")?.dataset.productId)
          .filter(Boolean)
      );
      const incoming = Array.from(remoteGrid.querySelectorAll("[data-smart-product-item]")).filter((item) => {
        const productId = item.querySelector("[data-product-id]")?.dataset.productId;
        return !productId || !knownIds.has(productId);
      });

      assignProductOrder(incoming);
      const fragment = document.createDocumentFragment();
      incoming.forEach((item, index) => {
        if (!prefersReducedMotion) {
          const clearReveal = () => {
            item.classList.remove("is-revealing");
            item.style.removeProperty("--smart-reveal-index");
          };
          item.style.setProperty("--smart-reveal-index", String(Math.min(index, 7)));
          item.classList.add("is-revealing");
          item.addEventListener("animationend", clearReveal, { once: true });
          window.setTimeout(clearReveal, 700);
        }
        fragment.appendChild(item);
      });
      grid.appendChild(fragment);
      observeFavoriteButtons(incoming);
      grid.dataset.nextPageUrl = remoteGrid.dataset.nextPageUrl || "";

      const remotePagination = remoteRoot.querySelector("[data-smart-pagination]");
      if (pagination && remotePagination) pagination.innerHTML = remotePagination.innerHTML;

      applySort(sortControl?.value || "recommended");
      if (loadStatus) {
        loadStatus.textContent = incoming.length
          ? loadStatus.dataset.loadedText || ""
          : loadStatus.dataset.completeText || "";
      }
      emitCatalogAnalytics("CatalogProgressiveLoad", {
        loaded: incoming.length,
        total: productItems().length,
      });

      if (grid.dataset.nextPageUrl && sentinel) observer?.observe(sentinel);
      else observer?.disconnect();
    } catch (error) {
      if (loadStatus) loadStatus.textContent = loadStatus.dataset.errorText || "";
      observer?.disconnect();
      if (window.console?.warn) window.console.warn("Smart Selector progressive loading stopped", error);
    } finally {
      grid.removeAttribute("aria-busy");
      loadingNextPage = false;
    }
  };

  assignProductOrder(productItems());
  observeFavoriteButtons(productItems());
  applySort(readInitialSort());
  updateActiveCount();
  updateQuickFacetValues();
  initializeDisclosures();
  measureMobileNavigation();

  if (mobileNavigation && "ResizeObserver" in window) {
    new ResizeObserver(measureMobileNavigation).observe(mobileNavigation);
  }

  if (sentinel && grid?.dataset.nextPageUrl && "IntersectionObserver" in window) {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) progressiveLoad(observer);
      },
      { rootMargin: "420px 0px" }
    );
    observer.observe(sentinel);
  }

  window.addEventListener("popstate", () => {
    if (overlay?.classList.contains("is-open")) {
      closeFilters({ restoreFocus: true, consumeHistory: false });
    }
  });

  window.addEventListener("pageshow", () => {
    if (!overlay?.classList.contains("is-open")) {
      unlockPage();
      setBackgroundInert(false);
    }
    measureMobileNavigation();
  });

  window.addEventListener("pagehide", () => {
    if (main) main.style.contain = mainContain;
  });

  if (main) main.style.contain = "none";
})();
