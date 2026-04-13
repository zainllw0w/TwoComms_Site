(function () {
  const root = document.querySelector("[data-custom-print-root]");
  const configNode = document.getElementById("customPrintConfiguratorConfig");

  if (!root || !configNode) {
    return;
  }

  let config;
  try {
    config = JSON.parse(configNode.textContent || "{}");
  } catch (error) {
    console.error("Custom print config parse failed", error);
    return;
  }

  const storageKey = config.storage_key || "twocomms.custom_print.v2.draft";
  const defaultState = deepCopy(config.defaults || {});
  const stepOrder = ["quickstart", "mode", "product", "artwork", "quantity", "review"];
  const stagePositions = {
    hoodie: {
      front: {
        front: { top: "44%", left: "50%" },
        sleeve: { top: "42%", left: "73%" },
      },
      back: {
        back: { top: "44%", left: "50%" },
        sleeve: { top: "42%", left: "28%" },
      },
    },
    tshirt: {
      front: {
        front: { top: "42%", left: "50%" },
      },
      back: {
        back: { top: "42%", left: "50%" },
      },
    },
    longsleeve: {
      front: {
        front: { top: "43%", left: "50%" },
        sleeve: { top: "42%", left: "75%" },
      },
      back: {
        back: { top: "43%", left: "50%" },
        sleeve: { top: "42%", left: "25%" },
      },
    },
    customer_garment: {
      front: {
        front: { top: "44%", left: "50%" },
        custom: { top: "62%", left: "50%" },
      },
      back: {
        back: { top: "44%", left: "50%" },
        custom: { top: "62%", left: "50%" },
      },
    },
  };

  const form = document.getElementById("customPrintConfiguratorForm");
  const dom = {
    buildStrip: document.querySelector(".cp-build-strip"),
    stepSections: Array.from(root.querySelectorAll("[data-step]")),
    heroDynamicLabel: root.querySelector("[data-hero-dynamic-label]"),
    heroDynamicCopy: root.querySelector("[data-hero-dynamic-copy]"),
    quickStartList: root.querySelector("[data-quick-start-list]"),
    starterStyleWrap: root.querySelector("[data-starter-style-wrap]"),
    starterStyleList: root.querySelector("[data-starter-style-list]"),
    modeList: root.querySelector("[data-mode-list]"),
    brandFields: root.querySelector("[data-brand-fields]"),
    brandNameInput: root.querySelector("[data-brand-name-input]"),
    productList: root.querySelector("[data-product-list]"),
    hoodieConfig: root.querySelector("[data-hoodie-config]"),
    fitList: root.querySelector("[data-fit-list]"),
    fabricList: root.querySelector("[data-fabric-list]"),
    colorList: root.querySelector("[data-color-list]"),
    zoneList: root.querySelector("[data-zone-list]"),
    placementNoteWrap: root.querySelector("[data-placement-note-wrap]"),
    placementNoteInput: root.querySelector("[data-placement-note-input]"),
    addonsWrap: root.querySelector("[data-addons-wrap]"),
    addonsList: root.querySelector("[data-addons-list]"),
    artworkServiceList: root.querySelector("[data-artwork-service-list]"),
    triageList: root.querySelector("[data-triage-list]"),
    fileInput: root.querySelector("[data-file-input]"),
    fileList: root.querySelector("[data-file-list]"),
    briefInput: root.querySelector("[data-brief-input]"),
    quantityInput: root.querySelector("[data-quantity-input]"),
    giftInput: root.querySelector("[data-gift-input]"),
    sizeModeList: root.querySelector("[data-size-mode-list]"),
    sizesNoteInput: root.querySelector("[data-sizes-note-input]"),
    garmentNoteWrap: root.querySelector("[data-garment-note-wrap]"),
    garmentNoteInput: root.querySelector("[data-garment-note-input]"),
    reviewBox: root.querySelector("[data-review-box]"),
    nameInput: root.querySelector("[data-name-input]"),
    brandShortcutInput: root.querySelector("[data-brand-shortcut-input]"),
    contactChannelList: root.querySelector("[data-contact-channel-list]"),
    contactValueInput: root.querySelector("[data-contact-value-input]"),
    statusBox: root.querySelector("[data-status-box]"),
    garment: root.querySelector("[data-garment]"),
    zoneLayer: root.querySelector("[data-zone-layer]"),
    stageEyebrow: root.querySelector("[data-stage-eyebrow]"),
    stageLabel: root.querySelector("[data-stage-label]"),
    stageNote: root.querySelector("[data-stage-note]"),
    stageZones: root.querySelector("[data-stage-zones]"),
    stageAddons: root.querySelector("[data-stage-addons]"),
    stageViewButtons: Array.from(root.querySelectorAll("[data-stage-view]")),
    inlinePriceSummary: root.querySelector("[data-inline-price-summary]"),
    priceCapsule: root.querySelector("[data-price-capsule]"),
    capsuleTitle: root.querySelector("[data-capsule-title]"),
    priceMain: root.querySelector("[data-price-main]"),
    priceSub: root.querySelector("[data-price-sub]"),
    priceBreakdown: root.querySelector("[data-price-breakdown]"),
    mobileBar: root.querySelector("[data-mobile-bar]"),
    mobilePrice: root.querySelector("[data-mobile-price]"),
    mobilePriceNote: root.querySelector("[data-mobile-price-note]"),
    safeExitButtons: Array.from(root.querySelectorAll("[data-safe-exit-trigger]")),
    mobileSummaryToggleButtons: Array.from(root.querySelectorAll("[data-mobile-summary-toggle]")),
    submitShortcut: root.querySelector("[data-submit-shortcut]"),
    stepNavButtons: Array.from(root.querySelectorAll("[data-step-nav]")),
    startFlowButtons: Array.from(root.querySelectorAll("[data-start-flow]")),
  };

  let selectedFiles = [];
  let stageView = "front";

  const draft = readDraft();
  const state = normalizeState(draft || defaultState);
  syncInputsFromState();
  bindEvents();
  renderAll();

  if (draft) {
    showStatus("Локальну чернетку відновлено. Можна продовжити збір або передати її менеджеру.", "success");
  }

  function deepCopy(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function readDraft() {
    try {
      const raw = window.localStorage.getItem(storageKey);
      return raw ? JSON.parse(raw) : null;
    } catch (error) {
      return null;
    }
  }

  function persistDraft() {
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(buildSnapshot()));
    } catch (error) {
      console.warn("Custom print draft save failed", error);
    }
  }

  function clearDraft() {
    try {
      window.localStorage.removeItem(storageKey);
    } catch (error) {
      console.warn("Custom print draft clear failed", error);
    }
  }

  function allowedValues(items) {
    return new Set((items || []).map((item) => item.value));
  }

  function getProductConfig(type) {
    return (config.products || {})[type] || (config.products || {}).hoodie;
  }

  function normalizeState(raw) {
    const base = deepCopy(defaultState);
    const draftState = raw || {};

    base.quick_start_mode = allowedValues(config.quick_start_modes).has(draftState.quick_start_mode)
      ? draftState.quick_start_mode
      : base.quick_start_mode;
    base.mode = draftState.mode === "brand" ? "brand" : "personal";
    base.starter_style = allowedValues(config.starter_styles).has(draftState.starter_style)
      ? draftState.starter_style
      : (base.starter_style || "minimal");

    const productType = ((draftState.product || {}).type || base.product.type || "hoodie");
    base.product.type = (config.products || {})[productType] ? productType : "hoodie";

    const productConfig = getProductConfig(base.product.type);
    const fitChoices = (productConfig.fits || []).map((item) => item.value);
    const requestedFit = (draftState.product || {}).fit || base.product.fit || "";
    base.product.fit = fitChoices.includes(requestedFit) ? requestedFit : (productConfig.default_fit || "");

    const fabricChoices = ((productConfig.fabrics || {})[base.product.fit] || []).map((item) => item.value);
    const requestedFabric = (draftState.product || {}).fabric || base.product.fabric || "";
    base.product.fabric = fabricChoices.includes(requestedFabric)
      ? requestedFabric
      : (productConfig.default_fabric || fabricChoices[0] || "");

    const colorChoices = (productConfig.colors || []).map((item) => item.value);
    const requestedColor = (draftState.product || {}).color || base.product.color || "";
    base.product.color = colorChoices.includes(requestedColor)
      ? requestedColor
      : (productConfig.default_color || colorChoices[0] || "");

    const requestedZones = Array.isArray((draftState.print || {}).zones) ? (draftState.print || {}).zones : base.print.zones;
    const availableZones = new Set(productConfig.zones || []);
    base.print.zones = (requestedZones || []).filter((zone, index, list) => availableZones.has(zone) && list.indexOf(zone) === index);
    if (!base.print.zones.length) {
      base.print.zones = deepCopy(productConfig.default_zones || ["front"]);
    }

    const requestedAddOns = Array.isArray((draftState.print || {}).add_ons) ? (draftState.print || {}).add_ons : [];
    const addOnChoices = new Set((productConfig.add_ons || []).map((item) => item.value));
    base.print.add_ons = requestedAddOns.filter((value, index, list) => addOnChoices.has(value) && list.indexOf(value) === index);
    base.print.placement_note = ((draftState.print || {}).placement_note || base.print.placement_note || "").trim();

    base.artwork.service_kind = allowedValues(config.artwork_services).has((draftState.artwork || {}).service_kind)
      ? (draftState.artwork || {}).service_kind
      : (base.quick_start_mode === "have_file" ? "ready" : "design");
    base.artwork.triage_status = allowedValues(config.triage_statuses).has((draftState.artwork || {}).triage_status)
      ? (draftState.artwork || {}).triage_status
      : deriveTriageStatus(base.artwork.service_kind, Array.isArray((draftState.artwork || {}).files) ? (draftState.artwork || {}).files : []);
    base.artwork.files = Array.isArray((draftState.artwork || {}).files) ? (draftState.artwork || {}).files : [];

    base.order.quantity = positiveInt((draftState.order || {}).quantity, base.order.quantity || 1);
    base.order.size_mode = allowedValues(config.size_modes).has((draftState.order || {}).size_mode)
      ? (draftState.order || {}).size_mode
      : (base.order.size_mode || "single");
    base.order.sizes_note = ((draftState.order || {}).sizes_note || base.order.sizes_note || "").trim();
    base.order.gift = Boolean((draftState.order || {}).gift);

    base.contact.channel = allowedValues(config.contact_channels).has((draftState.contact || {}).channel)
      ? (draftState.contact || {}).channel
      : (base.contact.channel || "");
    base.contact.name = ((draftState.contact || {}).name || base.contact.name || "").trim();
    base.contact.value = ((draftState.contact || {}).value || base.contact.value || "").trim();

    base.notes = base.notes || {};
    base.notes.brand_name = ((draftState.notes || {}).brand_name || (base.notes || {}).brand_name || "").trim();
    base.notes.brief = ((draftState.notes || {}).brief || (base.notes || {}).brief || "").trim();
    base.notes.garment_note = ((draftState.notes || {}).garment_note || (base.notes || {}).garment_note || "").trim();

    base.ui = base.ui || {};
    const requestedStep = ((draftState.ui || {}).current_step || base.ui.current_step || "quickstart").trim();
    base.ui.current_step = stepOrder.includes(requestedStep) ? requestedStep : "quickstart";

    stageView = inferStageView(base.print.zones[0] || "front");
    return base;
  }

  function positiveInt(value, fallback) {
    const parsed = Number.parseInt(value, 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
  }

  function inferStageView(zone) {
    return zone === "back" ? "back" : "front";
  }

  function deriveTriageStatus(serviceKind, files) {
    if (serviceKind === "ready") {
      return files.length ? "print-ready" : "needs-review";
    }
    if (serviceKind === "adjust") {
      return "needs-work";
    }
    return files.length ? "reference-only" : "needs-review";
  }

  function bindEvents() {
    delegateChoice(dom.quickStartList, (value) => {
      state.quick_start_mode = value;
      if (value === "have_file" && state.artwork.service_kind === "design") {
        state.artwork.service_kind = "ready";
        state.artwork.triage_status = deriveTriageStatus("ready", state.artwork.files);
      }
      if (value === "starter_style" && !state.starter_style) {
        state.starter_style = "minimal";
      }
      setCurrentStep("mode");
      renderAll();
    });

    delegateChoice(dom.starterStyleList, (value) => {
      state.starter_style = value;
      setCurrentStep("quickstart");
      renderAll();
    });

    delegateChoice(dom.modeList, (value) => {
      state.mode = value;
      setCurrentStep("product");
      renderAll();
    });

    delegateChoice(dom.productList, (value) => {
      state.product.type = value;
      const productConfig = getProductConfig(value);
      state.product.fit = productConfig.default_fit || "";
      state.product.fabric = productConfig.default_fabric || "";
      state.product.color = productConfig.default_color || "";
      state.print.zones = deepCopy(productConfig.default_zones || ["front"]);
      state.print.add_ons = [];
      state.print.placement_note = "";
      if (value === "customer_garment" && state.artwork.service_kind === "ready") {
        state.artwork.service_kind = "design";
      }
      stageView = inferStageView(state.print.zones[0]);
      setCurrentStep("product");
      renderAll();
    });

    delegateChoice(dom.fitList, (value) => {
      state.product.fit = value;
      const productConfig = getProductConfig(state.product.type);
      const fabrics = ((productConfig.fabrics || {})[value] || []).map((item) => item.value);
      if (fabrics.length && !fabrics.includes(state.product.fabric)) {
        state.product.fabric = fabrics[0];
      }
      setCurrentStep("product");
      renderAll();
    });

    delegateChoice(dom.fabricList, (value) => {
      state.product.fabric = value;
      setCurrentStep("product");
      renderAll();
    });

    delegateChoice(dom.colorList, (value) => {
      state.product.color = value;
      setCurrentStep("product");
      renderAll();
    });

    delegateChoice(dom.zoneList, (value) => {
      toggleSelection(state.print.zones, value, getProductConfig(state.product.type).default_zones || ["front"]);
      if (value === "back") {
        stageView = "back";
      }
      if (value === "front") {
        stageView = "front";
      }
      setCurrentStep("product");
      renderAll();
    });

    delegateChoice(dom.addonsList, (value) => {
      toggleSelection(state.print.add_ons, value, []);
      setCurrentStep("product");
      renderAll();
    });

    delegateChoice(dom.artworkServiceList, (value) => {
      state.artwork.service_kind = value;
      state.artwork.triage_status = deriveTriageStatus(value, state.artwork.files);
      setCurrentStep("artwork");
      renderAll();
    });

    delegateChoice(dom.triageList, (value) => {
      state.artwork.triage_status = value;
      setCurrentStep("artwork");
      renderAll();
    });

    delegateChoice(dom.sizeModeList, (value) => {
      state.order.size_mode = value;
      setCurrentStep("quantity");
      renderAll();
    });

    delegateChoice(dom.contactChannelList, (value) => {
      state.contact.channel = value;
      updateContactPlaceholder();
      setCurrentStep("review");
      renderAll();
    });

    dom.brandNameInput.addEventListener("input", () => {
      state.notes.brand_name = dom.brandNameInput.value.trim();
      setCurrentStep("mode");
      persistDraft();
    });

    dom.placementNoteInput.addEventListener("input", () => {
      state.print.placement_note = dom.placementNoteInput.value.trim();
      setCurrentStep("product");
      persistDraft();
    });

    dom.fileInput.addEventListener("change", () => {
      selectedFiles = Array.from(dom.fileInput.files || []);
      state.artwork.files = selectedFiles.map((file, index) => ({
        name: file.name,
        zone: state.print.zones[index] || state.print.zones[0] || "front",
        status: state.artwork.triage_status,
        role: state.artwork.triage_status === "reference-only" ? "reference" : "design",
      }));
      state.artwork.triage_status = deriveTriageStatus(state.artwork.service_kind, state.artwork.files);
      setCurrentStep("artwork");
      renderAll();
    });

    dom.briefInput.addEventListener("input", () => {
      state.notes.brief = dom.briefInput.value.trim();
      setCurrentStep("artwork");
      persistDraft();
    });

    dom.quantityInput.addEventListener("input", () => {
      state.order.quantity = positiveInt(dom.quantityInput.value, 1);
      setCurrentStep("quantity");
      renderAll();
    });

    dom.giftInput.addEventListener("change", () => {
      state.order.gift = Boolean(dom.giftInput.checked);
      setCurrentStep("quantity");
      renderAll();
    });

    dom.sizesNoteInput.addEventListener("input", () => {
      state.order.sizes_note = dom.sizesNoteInput.value.trim();
      setCurrentStep("quantity");
      persistDraft();
    });

    dom.garmentNoteInput.addEventListener("input", () => {
      state.notes.garment_note = dom.garmentNoteInput.value.trim();
      setCurrentStep("quantity");
      persistDraft();
    });

    dom.nameInput.addEventListener("input", () => {
      state.contact.name = dom.nameInput.value.trim();
      setCurrentStep("review");
      persistDraft();
    });

    dom.brandShortcutInput.addEventListener("input", () => {
      if (!state.notes.brand_name) {
        state.notes.brand_name = dom.brandShortcutInput.value.trim();
      }
      setCurrentStep("review");
      persistDraft();
    });

    dom.contactValueInput.addEventListener("input", () => {
      state.contact.value = dom.contactValueInput.value.trim();
      setCurrentStep("review");
      persistDraft();
    });

    dom.stageViewButtons.forEach((button) => {
      button.addEventListener("click", () => {
        stageView = button.dataset.stageView || "front";
        renderStage();
      });
    });

    dom.buildStrip.addEventListener("click", (event) => {
      const button = event.target.closest("[data-step-link]");
      if (!button) {
        return;
      }
      focusStep(button.dataset.stepLink);
    });

    dom.stepSections.forEach((section) => {
      section.addEventListener("click", () => {
        setCurrentStep(section.dataset.step || "quickstart");
        renderBuildStrip();
      });
    });

    dom.stepNavButtons.forEach((button) => {
      button.addEventListener("click", () => {
        focusStep(button.dataset.stepNav);
      });
    });

    dom.startFlowButtons.forEach((button) => {
      button.addEventListener("click", () => {
        focusStep("quickstart");
      });
    });

    dom.safeExitButtons.forEach((button) => {
      button.addEventListener("click", handleSafeExit);
    });

    dom.mobileSummaryToggleButtons.forEach((button) => {
      button.addEventListener("click", () => {
        const expanded = root.dataset.mobileExpanded === "true";
        root.dataset.mobileExpanded = expanded ? "false" : "true";
      });
    });

    dom.submitShortcut.addEventListener("click", () => {
      form.requestSubmit();
    });

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const errors = validateBeforeSubmit();
      if (errors.length) {
        showStatus(errors.join(" "), "error");
        return;
      }

      const snapshot = buildSnapshot();
      const pricing = computePricing();
      const formData = buildFormData(snapshot, pricing);

      setBusy(true);
      try {
        const response = await fetch(config.submit_url, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "X-Requested-With": "fetch",
            "X-CSRFToken": getCsrfToken(),
          },
          body: formData,
        });

        const payload = await response.json();
        if (!response.ok || !payload.ok) {
          const messages = flattenErrors(payload.errors || {});
          showStatus(messages.length ? messages.join(" ") : "Не вдалося відправити заявку. Перевірте поля або спробуйте ще раз.", "error");
          return;
        }

        clearDraft();
        showStatus(payload.message || "Заявку прийнято. Менеджер зв'яжеться найближчим часом.", "success");
        root.dataset.mobileExpanded = "false";
      } catch (error) {
        showStatus("Мережевий збій під час відправки. Ви можете спробувати ще раз або передати чернетку менеджеру.", "error");
      } finally {
        setBusy(false);
      }
    });
  }

  function renderAll() {
    renderQuickStart();
    renderModes();
    renderProducts();
    renderProductConfig();
    renderArtwork();
    renderQuantity();
    renderReview();
    renderStage();
    renderStepPanels();
    renderBuildStrip();
    renderPriceCapsule();
    syncInputsFromState();
    persistDraft();
  }

  function renderQuickStart() {
    dom.quickStartList.innerHTML = (config.quick_start_modes || []).map((item) => (
      `<button type="button" class="cp-option-card ${state.quick_start_mode === item.value ? "is-active" : ""}" data-choice-value="${escapeHtml(item.value)}">
        <small>Старт</small>
        <strong>${escapeHtml(item.label)}</strong>
        <span>${escapeHtml(item.hint)}</span>
      </button>`
    )).join("");

    dom.starterStyleWrap.hidden = state.quick_start_mode !== "starter_style";
    dom.starterStyleList.innerHTML = (config.starter_styles || []).map((item) => (
      `<button type="button" class="cp-mini-chip ${state.starter_style === item.value ? "is-active" : ""}" data-choice-value="${escapeHtml(item.value)}">
        ${escapeHtml(item.label)}
      </button>`
    )).join("");

    const active = (config.quick_start_modes || []).find((item) => item.value === state.quick_start_mode) || config.quick_start_modes[0];
    dom.heroDynamicLabel.textContent = active ? active.label : "Почати з нуля";
    dom.heroDynamicCopy.textContent = active ? active.hint : "";
  }

  function renderModes() {
    dom.modeList.innerHTML = (config.modes || []).map((item) => (
      `<button type="button" class="cp-option-card ${state.mode === item.value ? "is-active" : ""}" data-choice-value="${escapeHtml(item.value)}">
        <small>Формат</small>
        <strong>${escapeHtml(item.label)}</strong>
        <span>${escapeHtml(item.hint || "")}</span>
      </button>`
    )).join("");
    dom.brandFields.hidden = state.mode !== "brand";
  }

  function renderProducts() {
    dom.productList.innerHTML = Object.entries(config.products || {}).map(([value, product]) => (
      `<button type="button" class="cp-product-card ${state.product.type === value ? "is-active" : ""}" data-choice-value="${escapeHtml(value)}">
        <small>${escapeHtml(product.eyebrow || "product")}</small>
        <strong>${escapeHtml(product.label)}</strong>
        <span>${escapeHtml(product.summary || "")}</span>
      </button>`
    )).join("");
  }

  function renderProductConfig() {
    const product = getProductConfig(state.product.type);
    dom.hoodieConfig.hidden = state.product.type !== "hoodie";
    dom.garmentNoteWrap.hidden = state.product.type !== "customer_garment";
    dom.addonsWrap.hidden = !(product.add_ons || []).length;

    dom.fitList.innerHTML = (product.fits || []).map((item) => (
      `<button type="button" class="cp-mini-chip ${state.product.fit === item.value ? "is-active" : ""}" data-choice-value="${escapeHtml(item.value)}">
        ${escapeHtml(item.label)}
      </button>`
    )).join("");

    const fabrics = (product.fabrics || {})[state.product.fit] || [];
    dom.fabricList.innerHTML = fabrics.map((item) => (
      `<button type="button" class="cp-mini-chip ${state.product.fabric === item.value ? "is-active" : ""}" data-choice-value="${escapeHtml(item.value)}">
        ${escapeHtml(item.label)}
      </button>`
    )).join("");

    dom.colorList.innerHTML = (product.colors || []).map((item) => (
      `<button type="button" class="cp-swatch ${state.product.color === item.value ? "is-active" : ""}" data-choice-value="${escapeHtml(item.value)}">
        <span class="cp-swatch-dot" style="background:${escapeHtml(item.hex || "#444")}"></span>
        ${escapeHtml(item.label)}
      </button>`
    )).join("");

    dom.zoneList.innerHTML = (product.zones || []).map((zone) => (
      `<button type="button" class="cp-mini-chip ${state.print.zones.includes(zone) ? "is-active" : ""}" data-choice-value="${escapeHtml(zone)}">
        ${escapeHtml((config.zone_labels || {})[zone] || zone)}
      </button>`
    )).join("");

    dom.addonsList.innerHTML = (product.add_ons || []).map((item) => (
      `<button type="button" class="cp-mini-chip ${state.print.add_ons.includes(item.value) ? "is-active" : ""}" data-choice-value="${escapeHtml(item.value)}">
        ${escapeHtml(item.label)}
      </button>`
    )).join("");

    const showPlacementNote = state.print.zones.includes("custom") || state.product.type === "customer_garment";
    dom.placementNoteWrap.hidden = !showPlacementNote;
  }

  function renderArtwork() {
    dom.artworkServiceList.innerHTML = (config.artwork_services || []).map((item) => (
      `<button type="button" class="cp-option-card ${state.artwork.service_kind === item.value ? "is-active" : ""}" data-choice-value="${escapeHtml(item.value)}">
        <small>Макет</small>
        <strong>${escapeHtml(item.label)}</strong>
        <span>${escapeHtml(item.hint || "")}</span>
      </button>`
    )).join("");

    dom.triageList.innerHTML = (config.triage_statuses || []).map((item) => (
      `<button type="button" class="cp-mini-chip ${state.artwork.triage_status === item.value ? "is-active" : ""}" data-choice-value="${escapeHtml(item.value)}">
        ${escapeHtml(item.label)}
      </button>`
    )).join("");

    if (!state.artwork.files.length) {
      dom.fileList.textContent = "Файли ще не додані.";
      return;
    }

    const restoreNotice = state.artwork.files.length && !selectedFiles.length
      ? `<div class="cp-file-item"><div><strong>Чернетку відновлено</strong><div>Назви файлів збережено, але самі файли потрібно вибрати повторно перед відправкою.</div></div></div>`
      : "";

    dom.fileList.innerHTML = restoreNotice + state.artwork.files.map((file, index) => (
      `<div class="cp-file-item">
        <div>
          <strong>${escapeHtml(file.name || `file-${index + 1}`)}</strong>
          <div>${escapeHtml((config.zone_labels || {})[file.zone] || file.zone || "front")} · ${escapeHtml(labelForValue(config.triage_statuses, file.status || state.artwork.triage_status))}</div>
        </div>
        <span>${escapeHtml(labelForFileRole(file.role || "design"))}</span>
      </div>`
    )).join("");
  }

  function renderQuantity() {
    dom.sizeModeList.innerHTML = (config.size_modes || []).map((item) => (
      `<button type="button" class="cp-mini-chip ${state.order.size_mode === item.value ? "is-active" : ""}" data-choice-value="${escapeHtml(item.value)}">
        ${escapeHtml(item.label)}
      </button>`
    )).join("");

    dom.contactChannelList.innerHTML = (config.contact_channels || []).map((item) => (
      `<button type="button" class="cp-mini-chip ${state.contact.channel === item.value ? "is-active" : ""}" data-choice-value="${escapeHtml(item.value)}">
        ${escapeHtml(item.label)}
      </button>`
    )).join("");
  }

  function renderReview() {
    const product = getProductConfig(state.product.type);
    const pricing = computePricing();
    const contactLabel = ((config.contact_channels || []).find((item) => item.value === state.contact.channel) || {}).label || "Не вказано";
    const lines = [
      `<ul>
        <li><strong>Старт:</strong> ${escapeHtml(labelForValue(config.quick_start_modes, state.quick_start_mode))}</li>
        <li><strong>Формат:</strong> ${escapeHtml(state.mode === "brand" ? "Для команди / бренду" : "Для себе")}</li>
        <li><strong>Виріб:</strong> ${escapeHtml(product.label || "Худі")}</li>
        <li><strong>Зони:</strong> ${escapeHtml(formatZones())}</li>
        <li><strong>Макет:</strong> ${escapeHtml(labelForValue(config.artwork_services, state.artwork.service_kind))} / ${escapeHtml(labelForValue(config.triage_statuses, state.artwork.triage_status))}</li>
        <li><strong>Кількість:</strong> ${escapeHtml(String(state.order.quantity))}</li>
        <li><strong>Контакт:</strong> ${escapeHtml(contactLabel)}${state.contact.value ? ` — ${escapeHtml(state.contact.value)}` : ""}</li>
        <li><strong>Ціна зараз:</strong> ${pricing.estimate_required ? "Ціну уточнюємо" : `${formatPrice(pricing.final_total)} / шт`}</li>
      </ul>`,
    ];

    if (state.notes.brand_name) {
      lines.push(`<div><strong>Бренд / команда:</strong> ${escapeHtml(state.notes.brand_name)}</div>`);
    }
    if (state.notes.brief) {
      lines.push(`<div><strong>Бриф:</strong> ${escapeHtml(state.notes.brief)}</div>`);
    }
    if (state.order.gift) {
      lines.push("<div><strong>Подарунок:</strong> так</div>");
    }
    dom.reviewBox.innerHTML = lines.join("");
  }

  function renderBuildStrip() {
    const summary = {
      quickstart: labelForValue(config.quick_start_modes, state.quick_start_mode),
      mode: state.mode === "brand" ? "Для команди / бренду" : "Для себе",
      product: getProductConfig(state.product.type).label || "Худі",
      artwork: labelForValue(config.artwork_services, state.artwork.service_kind),
      review: state.contact.value || "Контакт не вказано",
    };

    root.querySelectorAll("[data-step-summary]").forEach((node) => {
      const step = node.dataset.stepSummary;
      node.textContent = summary[step] || "—";
    });

    root.querySelectorAll("[data-step-link]").forEach((button) => {
      const buttonStep = button.dataset.stepLink;
      button.classList.toggle("is-active", buttonStep === state.ui.current_step);
      button.classList.toggle("is-done", stepOrder.indexOf(buttonStep) < stepOrder.indexOf(state.ui.current_step));
    });
  }

  function renderStepPanels() {
    dom.stepSections.forEach((section) => {
      const isCurrent = section.dataset.step === state.ui.current_step;
      section.hidden = !isCurrent;
      section.classList.toggle("is-current", isCurrent);
    });
  }

  function renderStage() {
    const product = getProductConfig(state.product.type);
    const color = (product.colors || []).find((item) => item.value === state.product.color) || {};
    dom.garment.className = `cp-garment cp-garment--${state.product.type} cp-garment--${stageView}`;
    dom.garment.style.setProperty("--cp-garment-fill", color.hex || "#46424a");
    dom.stageEyebrow.textContent = product.eyebrow || "Виріб";
    dom.stageLabel.textContent = product.label || "Худі";
    dom.stageNote.textContent = product.hero_note || "";
    dom.stageZones.textContent = formatZones();
    dom.stageAddons.textContent = state.print.add_ons.length
      ? `Додаткові деталі: ${(state.print.add_ons || []).map((value) => labelForAddOn(value)).join(", ")}.`
      : "Без додаткових деталей.";

    dom.stageViewButtons.forEach((button) => {
      button.classList.toggle("is-active", button.dataset.stageView === stageView);
    });

    renderStagePins();
  }

  function renderStagePins() {
    const productType = state.product.type;
    const productConfig = getProductConfig(productType);
    const viewPositions = (((stagePositions[productType] || {})[stageView]) || {});

    dom.zoneLayer.innerHTML = (productConfig.zones || []).map((zone) => {
      const position = viewPositions[zone];
      const hidden = !position;
      return `
        <button
          type="button"
          class="cp-zone-pin ${state.print.zones.includes(zone) ? "is-active" : ""}"
          data-stage-zone="${escapeHtml(zone)}"
          ${hidden ? "hidden" : ""}
          style="${hidden ? "" : `top:${position.top};left:${position.left};transform:translate(-50%, -50%);`}"
        >
          ${escapeHtml((config.zone_labels || {})[zone] || zone)}
        </button>
      `;
    }).join("");

    dom.zoneLayer.querySelectorAll("[data-stage-zone]").forEach((button) => {
      button.addEventListener("click", () => {
        toggleSelection(state.print.zones, button.dataset.stageZone, getProductConfig(state.product.type).default_zones || ["front"]);
        setCurrentStep("product");
        renderAll();
      });
    });
  }

  function renderPriceCapsule() {
    const pricing = computePricing();
    const product = getProductConfig(state.product.type);
    let title = "Ціну уточнюємо";
    let priceMain = "Прорахунок";
    let priceSub = "Один або кілька параметрів потребують ручного прорахунку.";

    if (!pricing.estimate_required && pricing.final_total !== null) {
      title = `Від ${formatPrice(pricing.final_total)} / шт`;
      priceMain = formatPrice(pricing.final_total);
      priceSub = "Попередня ціна для одного стандартного розміщення принта.";
    } else if (pricing.base_price !== null) {
      title = `База від ${formatPrice(pricing.base_price)}`;
      priceMain = "Уточнюємо";
      priceSub = "Бачимо базу, але фінальний прорахунок потребує менеджерської валідації.";
    }

    dom.capsuleTitle.textContent = title;
    dom.priceMain.textContent = priceMain;
    dom.priceSub.textContent = priceSub;
    dom.inlinePriceSummary.textContent = `${product.label}: ${title}`;
    dom.mobilePrice.textContent = pricing.estimate_required ? title : `${priceMain} / шт`;
    dom.mobilePriceNote.textContent = pricing.estimate_required ? "Відкрити деталі" : "Ціна вже порахована";

    const breakdown = [
      `<ul>
        <li><strong>База:</strong> ${pricing.base_price !== null ? escapeHtml(formatPrice(pricing.base_price)) : "менеджерський прорахунок"}</li>
        <li><strong>Макет:</strong> ${pricing.design_price ? escapeHtml(`+${formatPrice(pricing.design_price)}`) : "без доплати"}</li>
        <li><strong>Зони:</strong> ${escapeHtml(formatZones())}</li>
        <li><strong>Деталі:</strong> ${state.print.add_ons.length ? escapeHtml((state.print.add_ons || []).map((value) => labelForAddOn(value)).join(", ")) : "немає"}</li>
        <li><strong>Кількість:</strong> ${escapeHtml(String(state.order.quantity))}</li>
      </ul>`,
    ];

    if (pricing.discount_percent) {
      breakdown.push(`<div><strong>Знижка:</strong> ${escapeHtml(String(pricing.discount_percent))}%</div>`);
    }
    if (pricing.estimate_required && pricing.estimate_reason) {
      breakdown.push(`<div><strong>Чому уточнюємо:</strong> ${escapeHtml(formatEstimateReason(pricing.estimate_reason))}</div>`);
    }
    dom.priceBreakdown.innerHTML = breakdown.join("");
  }

  function computePricing() {
    const product = getProductConfig(state.product.type);
    const matrix = product.pricing || {};
    const result = {
      base_price: null,
      design_price: 0,
      discount_percent: 0,
      discount_amount: 0,
      final_total: null,
      estimate_required: false,
      estimate_reason: "",
    };

    if (matrix.base === null || state.product.type === "customer_garment") {
      result.estimate_required = true;
      result.estimate_reason = "customer_garment";
    } else {
      let base = Number(matrix.base || 0);
      if (state.product.fit === "oversize") {
        base += Number(matrix.oversize_delta || 0);
      }
      if (state.product.fit !== "oversize" && state.product.fabric === "premium") {
        base += Number(matrix.premium_delta || 0);
      }
      base += Math.max(0, state.print.zones.length - 1) * Number(matrix.extra_zone_delta || 0);
      base += state.print.add_ons.length * Number(matrix.add_on_delta || 0);
      result.base_price = base;
    }

    if (state.artwork.service_kind === "adjust") {
      result.design_price = 300;
    }
    if (state.artwork.service_kind === "design") {
      result.design_price = 500;
    }

    if (state.mode === "brand" && state.order.quantity >= 20) {
      result.discount_percent = 10;
    } else if (state.mode === "brand" && state.order.quantity >= 10) {
      result.discount_percent = 5;
    }

    const subtotal = (result.base_price || 0) + result.design_price;
    result.discount_amount = result.discount_percent ? Math.round(subtotal * result.discount_percent / 100) : 0;

    if (state.print.zones.includes("custom")) {
      result.estimate_required = true;
      result.estimate_reason = "custom_zone";
    } else if (state.print.zones.length > 1) {
      result.estimate_required = true;
      result.estimate_reason = "multi_zone";
    } else if (state.artwork.service_kind !== "ready") {
      result.estimate_required = true;
      result.estimate_reason = state.artwork.service_kind;
    }

    if (!result.estimate_required) {
      result.final_total = Math.max(subtotal - result.discount_amount, 0);
    }

    return result;
  }

  function buildSnapshot() {
    const pricing = computePricing();
    return {
      version: 2,
      quick_start_mode: state.quick_start_mode,
      mode: state.mode,
      starter_style: state.starter_style,
      product: {
        type: state.product.type,
        fit: state.product.fit,
        fabric: state.product.fabric,
        color: state.product.color,
      },
      print: {
        zones: deepCopy(state.print.zones),
        add_ons: deepCopy(state.print.add_ons),
        placement_note: state.print.placement_note,
      },
      artwork: {
        service_kind: state.artwork.service_kind,
        triage_status: state.artwork.triage_status,
        files: deepCopy(state.artwork.files),
      },
      order: {
        quantity: state.order.quantity,
        size_mode: state.order.size_mode,
        sizes_note: state.order.sizes_note,
        gift: state.order.gift,
      },
      contact: {
        channel: state.contact.channel,
        name: state.contact.name,
        value: state.contact.value,
      },
      pricing,
      notes: {
        brand_name: state.notes.brand_name,
        brief: state.notes.brief,
        garment_note: state.notes.garment_note,
      },
      ui: {
        current_step: state.ui.current_step,
      },
    };
  }

  function buildPlacementSpecs(snapshot) {
    return (snapshot.print.zones || []).map((zone, index) => {
      const file = snapshot.artwork.files.find((item) => item.zone === zone) || snapshot.artwork.files[index] || null;
      const isStandardZone = zone === "front" || zone === "back";
      const spec = {
        zone,
        label: (config.zone_labels || {})[zone] || zone,
        variant: index === 0 && isStandardZone ? "standard" : "estimate",
        is_free: index === 0 && isStandardZone,
        format: isStandardZone ? "standard" : "custom",
        size: isStandardZone ? "standard" : "manager_review",
      };
      if (file) {
        spec.file_index = snapshot.artwork.files.indexOf(file);
        spec.attachment_role = file.role === "reference" ? "reference" : "design";
      }
      return spec;
    });
  }

  function buildFormData(snapshot, pricing) {
    const data = new FormData();
    data.append("service_kind", state.artwork.service_kind);
    data.append("product_type", state.product.type);
    (state.print.zones || []).forEach((zone) => data.append("placements", zone));
    data.append("placement_note", state.print.placement_note || "");
    data.append("quantity", String(state.order.quantity || 1));
    data.append("size_mode", state.order.size_mode || "single");
    data.append("sizes_note", state.order.sizes_note || "");
    data.append("client_kind", state.mode === "brand" ? "brand" : "personal");
    data.append("business_kind", state.mode === "brand" ? "branding" : "");
    data.append("brand_name", state.notes.brand_name || "");
    data.append("garment_note", state.notes.garment_note || "");
    data.append("fit", state.product.fit || "");
    data.append("fabric", state.product.fabric || "");
    data.append("color_choice", state.product.color || "");
    data.append("file_triage_status", state.artwork.triage_status || "");
    data.append("exit_step", state.ui.current_step || "");
    data.append("placement_specs_json", JSON.stringify(buildPlacementSpecs(snapshot)));
    data.append("pricing_snapshot_json", JSON.stringify(pricing));
    data.append("config_draft_json", JSON.stringify(snapshot));
    data.append("name", state.contact.name || "");
    data.append("contact_channel", state.contact.channel || "");
    data.append("contact_value", state.contact.value || "");
    data.append("brief", state.notes.brief || "");
    selectedFiles.forEach((file) => data.append("files", file));
    return data;
  }

  async function handleSafeExit() {
    const snapshot = buildSnapshot();
      showStatus("Передаю чернетку менеджеру…", "success");
    setBusy(true);

    try {
      const response = await fetch(config.safe_exit_url, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify(snapshot),
      });

      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        showStatus("Не вдалося передати чернетку менеджеру. Спробуйте ще раз або надішліть заявку повністю.", "error");
        return;
      }

      const leadLabel = payload.lead_number ? ` Чернетка зафіксована як ${payload.lead_number}.` : "";
      showStatus(`Чернетку передано менеджеру.${leadLabel} Відкриваю Telegram для прямого контакту.`, "success");
      window.setTimeout(() => {
        window.open(payload.manager_url || config.telegram_manager_url, "_blank", "noopener");
      }, 180);
      root.dataset.mobileExpanded = "false";
    } catch (error) {
      showStatus("Не вдалося передати чернетку через мережеву помилку.", "error");
    } finally {
      setBusy(false);
    }
  }

  function validateBeforeSubmit() {
    const errors = [];

    if (state.mode === "brand" && !state.notes.brand_name) {
      errors.push("Вкажіть назву бренду або команди.");
    }
    if (state.print.zones.includes("custom") && !state.print.placement_note) {
      errors.push("Опишіть нестандартне розміщення принта.");
    }
    if (state.product.type === "customer_garment" && !state.notes.garment_note) {
      errors.push("Опишіть свій виріб для попереднього прорахунку.");
    }
    if (state.artwork.service_kind === "ready" && !selectedFiles.length) {
      errors.push("Додайте готовий файл для друку.");
    }
    if (state.artwork.service_kind === "adjust") {
      if (!selectedFiles.length) {
        errors.push("Додайте файл, який потрібно підготувати.");
      }
      if (!state.notes.brief) {
        errors.push("Опишіть, що саме потрібно змінити у файлі.");
      }
    }
    if (state.artwork.service_kind === "design" && !state.notes.brief) {
      errors.push("Опишіть ідею, стиль або референси для дизайну.");
    }
    if (!state.contact.name) {
      errors.push("Вкажіть ім'я для менеджера.");
    }
    if (!state.contact.channel) {
      errors.push("Оберіть канал зв'язку.");
    }
    if (!state.contact.value) {
      errors.push("Вкажіть контакт для зв'язку.");
    }

    return errors;
  }

  function flattenErrors(errors) {
    return Object.values(errors || {}).reduce((result, list) => result.concat(list || []), []);
  }

  function syncInputsFromState() {
    dom.brandNameInput.value = state.notes.brand_name || "";
    dom.placementNoteInput.value = state.print.placement_note || "";
    dom.briefInput.value = state.notes.brief || "";
    dom.quantityInput.value = String(state.order.quantity || 1);
    dom.giftInput.checked = Boolean(state.order.gift);
    dom.sizesNoteInput.value = state.order.sizes_note || "";
    dom.garmentNoteInput.value = state.notes.garment_note || "";
    dom.nameInput.value = state.contact.name || "";
    dom.brandShortcutInput.value = state.mode === "brand" ? (state.notes.brand_name || "") : "";
    dom.contactValueInput.value = state.contact.value || "";
    updateContactPlaceholder();
  }

  function updateContactPlaceholder() {
    const channel = (config.contact_channels || []).find((item) => item.value === state.contact.channel);
    dom.contactValueInput.placeholder = (channel && channel.placeholder) || "@username або +380...";
  }

  function labelForValue(items, value) {
    const match = (items || []).find((item) => item.value === value);
    return match ? match.label : value;
  }

  function labelForAddOn(value) {
    const product = getProductConfig(state.product.type);
    return labelForValue(product.add_ons || [], value);
  }

  function formatZones() {
    return (state.print.zones || []).map((zone) => (config.zone_labels || {})[zone] || zone).join(", ");
  }

  function formatPrice(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
      return "Ціну уточнюємо";
    }
    return `${new Intl.NumberFormat("uk-UA").format(Number(value))} грн`;
  }

  function labelForFileRole(value) {
    if (value === "reference") {
      return "Референс";
    }
    return "Робочий файл";
  }

  function formatEstimateReason(reason) {
    const labels = {
      customer_garment: "свій виріб потребує окремого прорахунку",
      custom_zone: "обрано нестандартну зону друку",
      multi_zone: "обрано кілька зон друку",
      design: "потрібна допомога з дизайном",
      adjust: "файл потрібно допрацювати",
      ready: "файл потрібно перевірити",
    };
    return labels[reason] || "потрібна ручна перевірка";
  }

  function toggleSelection(list, value, fallback) {
    const index = list.indexOf(value);
    if (index >= 0) {
      list.splice(index, 1);
      if (!list.length) {
        fallback.forEach((item) => list.push(item));
      }
      return;
    }
    list.push(value);
  }

  function showStatus(message, tone) {
    dom.statusBox.classList.remove("is-error", "is-success");
    if (tone === "error") {
      dom.statusBox.classList.add("is-error");
    }
    if (tone === "success") {
      dom.statusBox.classList.add("is-success");
    }
    dom.statusBox.innerHTML = message;
  }

  function setBusy(isBusy) {
    root.dataset.busy = isBusy ? "true" : "false";
    form.querySelectorAll("button, input, textarea").forEach((element) => {
      if (element.dataset.safeExitTrigger || element.dataset.mobileSummaryToggle) {
        return;
      }
      if (element.type !== "hidden") {
        element.disabled = isBusy;
      }
    });
  }

  function setCurrentStep(step) {
    state.ui.current_step = stepOrder.includes(step) ? step : "quickstart";
  }

  function focusStep(step) {
    if (!stepOrder.includes(step)) {
      return;
    }
    setCurrentStep(step);
    renderAll();
    const target = document.getElementById(`cp-step-${step}`);
    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  function delegateChoice(container, handler) {
    if (!container) {
      return;
    }
    container.addEventListener("click", (event) => {
      const button = event.target.closest("[data-choice-value]");
      if (!button) {
        return;
      }
      handler(button.dataset.choiceValue);
    });
  }

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) {
      return meta.content;
    }
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }
})();
