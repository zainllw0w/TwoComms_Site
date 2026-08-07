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
  const main = root.closest("main");
  const mainContain = main?.style.contain || "";
  const allowedFilters = new Set(["theme", "fit"]);
  const allowedSorts = new Set(["recommended", "price-asc", "price-desc"]);
  const lockState = {};
  let lastFilterTrigger = null;
  let loadingNextPage = false;
  let nextOrder = 0;

  const checkFavoriteButton = (button) => {
    const productId = button?.getAttribute("data-product-id");
    if (productId && typeof window.checkFavoriteStatus === "function") {
      window.checkFavoriteStatus(productId, button);
    }
  };

  const favoriteStatusObserver = "IntersectionObserver" in window
    ? new IntersectionObserver((entries, observer) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          checkFavoriteButton(entry.target);
          observer.unobserve(entry.target);
        });
      }, { rootMargin: "100px 0px", threshold: 0.01 })
    : null;

  const observeFavoriteButtons = (items) => {
    items.forEach((item) => {
      item.querySelectorAll(".favorite-btn").forEach((button) => {
        if (favoriteStatusObserver) favoriteStatusObserver.observe(button);
        else checkFavoriteButton(button);
      });
    });
  };

  if (main) main.style.contain = "none";

  const productItems = () => Array.from(grid?.querySelectorAll("[data-smart-product-item]") || []);

  const assignProductOrder = (items) => {
    items.forEach((item) => {
      if (!item.dataset.smartOrder) {
        nextOrder += 1;
        item.dataset.smartOrder = String(nextOrder);
      }
    });
  };

  assignProductOrder(productItems());

  const buildFacetUrl = (filter, value) => {
    const url = new URL(window.location.href);
    const current = url.searchParams.get(filter) || "";

    if (current === value) url.searchParams.delete(filter);
    else url.searchParams.set(filter, value);

    url.searchParams.delete("page");
    return url;
  };

  const navigateToFacet = (filter, value) => {
    if (!allowedFilters.has(filter) || !value) return;
    window.location.assign(buildFacetUrl(filter, value).toString());
  };

  const resetUrl = () => {
    const url = new URL(window.location.href);
    ["theme", "fit", "color", "sort", "page"].forEach((key) => url.searchParams.delete(key));
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

    const items = productItems();
    items.sort((a, b) => {
      if (sortValue === "recommended") {
        return Number(a.dataset.smartOrder) - Number(b.dataset.smartOrder);
      }
      const priceDelta = comparePrice(a, b, sortValue);
      return priceDelta || Number(a.dataset.smartOrder) - Number(b.dataset.smartOrder);
    });

    const fragment = document.createDocumentFragment();
    items.forEach((item) => fragment.appendChild(item));
    grid.appendChild(fragment);

    if (sortControl && sortControl.value !== sortValue) sortControl.value = sortValue;

  };

  const readInitialSort = () => {
    const requested = new URL(window.location.href).searchParams.get("sort") || "recommended";
    return allowedSorts.has(requested) ? requested : "recommended";
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
  };

  const focusableElements = () => {
    if (!sheet) return [];
    return Array.from(
      sheet.querySelectorAll(
        'a[href], button:not([disabled]), select:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'
      )
    ).filter((element) => element.getClientRects().length > 0);
  };

  const closeFilters = ({ restoreFocus = true } = {}) => {
    if (!overlay?.classList.contains("is-open")) return;
    overlay.classList.remove("is-open");
    overlay.setAttribute("aria-hidden", "true");
    root.querySelectorAll("[data-smart-open-filters]").forEach((trigger) => {
      trigger.setAttribute("aria-expanded", "false");
    });
    setBackgroundInert(false);
    unlockPage();

    const trigger = lastFilterTrigger;
    lastFilterTrigger = null;
    if (restoreFocus && trigger?.isConnected) trigger.focus({ preventScroll: true });
  };

  const openFilters = (trigger) => {
    if (!overlay || !sheet || overlay.classList.contains("is-open")) return;
    lastFilterTrigger = trigger;
    overlay.classList.add("is-open");
    overlay.setAttribute("aria-hidden", "false");
    trigger?.setAttribute("aria-expanded", "true");
    setBackgroundInert(true);
    lockPage();

    const focusFilter = trigger?.dataset.smartFocusFilter;
    window.requestAnimationFrame(() => {
      const section = focusFilter
        ? sheet.querySelector(`[data-smart-filter-section="${focusFilter}"]`)
        : null;
      const target = section?.querySelector("button, a[href]") || sheet.querySelector("[data-smart-close-filters]") || sheet;
      section?.scrollIntoView({ block: "start" });
      const focusTarget = () => {
        if (!overlay.classList.contains("is-open") || !target.isConnected) return;
        target.focus({ preventScroll: !section });
      };
      focusTarget();
      window.setTimeout(() => {
        if (!sheet.contains(document.activeElement)) focusTarget();
      }, 80);
    });
  };

  root.querySelectorAll("[data-smart-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      navigateToFacet(button.dataset.smartFilter || "", button.dataset.smartValue || "");
    });
  });

  root.querySelectorAll("[data-smart-reset]").forEach((button) => {
    button.addEventListener("click", () => window.location.assign(resetUrl().toString()));
  });

  root.querySelectorAll("[data-smart-open-filters]").forEach((trigger) => {
    trigger.addEventListener("click", () => openFilters(trigger));
  });

  root.querySelectorAll("[data-smart-close-filters]").forEach((button) => {
    button.addEventListener("click", () => closeFilters());
  });

  overlay?.addEventListener("click", (event) => {
    if (event.target === overlay) closeFilters();
  });

  document.addEventListener("keydown", (event) => {
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

  applySort(readInitialSort());

  const progressiveLoad = async (observer) => {
    if (!grid || loadingNextPage) return;
    const nextPageUrl = grid.dataset.nextPageUrl;
    if (!nextPageUrl) {
      observer?.disconnect();
      return;
    }

    loadingNextPage = true;
    observer?.unobserve(sentinel);
    if (loadStatus) loadStatus.textContent = "Завантажуємо наступні моделі...";

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
      incoming.forEach((item) => fragment.appendChild(item));
      grid.appendChild(fragment);
      observeFavoriteButtons(incoming);
      grid.dataset.nextPageUrl = remoteGrid.dataset.nextPageUrl || "";

      const remotePagination = remoteRoot.querySelector("[data-smart-pagination]");
      if (pagination && remotePagination) pagination.innerHTML = remotePagination.innerHTML;

      applySort(sortControl?.value || "recommended");
      if (loadStatus) {
        loadStatus.textContent = incoming.length
          ? `Додано ${incoming.length} моделей`
          : "Усі моделі вже показано";
      }

      if (grid.dataset.nextPageUrl && sentinel) observer?.observe(sentinel);
      else observer?.disconnect();
    } catch (error) {
      if (loadStatus) loadStatus.textContent = "Не вдалося завантажити ще товари. Скористайтеся сторінками нижче.";
      observer?.disconnect();
      if (window.console?.warn) window.console.warn("Smart Selector progressive loading stopped", error);
    } finally {
      loadingNextPage = false;
    }
  };

  if (sentinel && grid?.dataset.nextPageUrl && "IntersectionObserver" in window) {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) progressiveLoad(observer);
      },
      { rootMargin: "420px 0px" }
    );
    observer.observe(sentinel);
  }

  window.addEventListener("pageshow", () => {
    if (!overlay?.classList.contains("is-open")) {
      unlockPage();
      setBackgroundInert(false);
    }
  });

  window.addEventListener("pagehide", () => {
    if (main) main.style.contain = mainContain;
  });
})();
