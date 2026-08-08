(() => {
  const mobileReference = document.querySelector("[data-catalog-mobile-reference]");

  if (mobileReference) {
    const header = mobileReference.querySelector("[data-catalog-reference-header]");
    const menuButton = mobileReference.querySelector("[data-catalog-reference-menu-button]");
    const menu = mobileReference.querySelector("[data-catalog-reference-menu]");
    const searchButton = mobileReference.querySelector("[data-catalog-reference-search-button]");
    const searchForm = mobileReference.querySelector("[data-catalog-reference-search-form]");
    const searchInput = searchForm?.querySelector("input[type='search']");
    const cartBadge = mobileReference.querySelector("[data-catalog-reference-cart-count]");

    menuButton?.addEventListener("click", () => {
      const isOpen = menu?.classList.toggle("is-open") || false;
      menuButton.setAttribute("aria-expanded", String(isOpen));
    });

    searchButton?.addEventListener("click", () => {
      const isOpen = header?.classList.toggle("is-searching") || false;
      searchButton.setAttribute("aria-expanded", String(isOpen));
      searchButton.setAttribute(
        "aria-label",
        isOpen ? "Закрити пошук" : "Відкрити пошук",
      );
      if (isOpen) {
        searchInput?.focus();
      }
    });

    document.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") {
        return;
      }
      menu?.classList.remove("is-open");
      menuButton?.setAttribute("aria-expanded", "false");
      header?.classList.remove("is-searching");
      searchButton?.setAttribute("aria-expanded", "false");
    });

    const cartCountUrl = mobileReference.dataset.cartCountUrl;
    if (cartBadge && cartCountUrl) {
      fetch(cartCountUrl, { credentials: "same-origin" })
        .then((response) => (response.ok ? response.json() : null))
        .then((payload) => {
          const count = Number(payload?.cart_count);
          if (Number.isFinite(count) && count >= 0) {
            cartBadge.textContent = String(count);
          }
        })
        .catch(() => {});
    }
  }

  const panels = document.querySelectorAll("[data-catalog-print-panel]");

  panels.forEach((panel) => {
    const preview = panel.querySelector("[data-print-preview]");
    const tools = Array.from(panel.querySelectorAll(".catalog-print-tool[data-print-mode]"));

    if (!preview || tools.length === 0) {
      return;
    }

    const activateMode = (mode) => {
      preview.dataset.printMode = mode;
      tools.forEach((tool) => {
        const isActive = tool.dataset.printMode === mode;
        tool.classList.toggle("is-active", isActive);
        tool.setAttribute("aria-pressed", isActive ? "true" : "false");
      });
    };

    tools.forEach((tool) => {
      tool.addEventListener("click", () => {
        activateMode(tool.dataset.printMode || "print");
      });
    });
  });
})();
