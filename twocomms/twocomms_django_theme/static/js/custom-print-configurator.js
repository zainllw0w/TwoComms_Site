/* TwoComms Custom Print Configurator V2 — Waterfall + Stage Receipt
 * - Жодного автовибору. Початковий стан = nulls / [].
 * - Vertical waterfall: завершені кроки згортаються у summary-рядки.
 * - Stage Receipt: прорахунок живе всередині картки виробу.
 * - Per-zone uploads: окрема dropzone для кожної обраної зони.
 * - Smart sizing: qty=1 → chip-row, qty>1 → matrix з валідацією суми.
 * - Gift як платний сервіс +100 грн з полем побажання та промокодом.
 * - B2B живий калькулятор: кожні 5 шт = -10 грн/шт.
 * - Dual final: «Додати в кошик» (сесійний кошик) і «Надіслати менеджеру» (Telegram).
 */
(function () {
  const root = document.querySelector("[data-custom-print-root]");
  const configNode = document.getElementById("customPrintConfiguratorConfig");
  if (!root || !configNode) return;

  let CONFIG;
  try {
    CONFIG = JSON.parse(configNode.textContent || "{}");
  } catch (error) {
    console.error("[custom-print v2] config parse failed", error);
    return;
  }

  const STORAGE_KEY = CONFIG.storage_key || "twocomms.custom_print.v2.draft";
  const STEPS = ["mode", "product", "config", "zones", "artwork", "quantity", "gift", "contact"];
  const STAGE_VISIBLE_AFTER = new Set(STEPS.slice(1));
  const FRONT_SIZE_DEFAULT = CONFIG.front_size_default || "A4";
  const FRONT_SIZE_PRESETS = (CONFIG.front_size_presets || []).reduce((acc, item) => {
    if (item && item.value) acc[item.value] = item;
    return acc;
  }, {});
  const STAGE_LAYOUTS = {
    hoodie: {
      front: {
        front: {
          pin: { top: "43%", left: "50%" },
          plate: { top: "43%", left: "50%", width: "34%", height: "18%", rotate: "0deg" },
        },
        sleeve: {
          pin: { top: "44%", left: "80%" },
          plate: { top: "46%", left: "76%", width: "13%", height: "28%", rotate: "24deg" },
        },
      },
      back: {
        back: {
          pin: { top: "43%", left: "50%" },
          plate: { top: "43%", left: "50%", width: "42%", height: "22%", rotate: "0deg" },
        },
        sleeve: {
          pin: { top: "44%", left: "24%" },
          plate: { top: "46%", left: "28%", width: "13%", height: "28%", rotate: "-24deg" },
        },
      },
    },
    tshirt: {
      front: {
        front: {
          pin: { top: "41%", left: "50%" },
          plate: { top: "42%", left: "50%", width: "32%", height: "18%", rotate: "0deg" },
        },
      },
      back: {
        back: {
          pin: { top: "41%", left: "50%" },
          plate: { top: "42%", left: "50%", width: "40%", height: "22%", rotate: "0deg" },
        },
      },
    },
    longsleeve: {
      front: {
        front: {
          pin: { top: "42%", left: "50%" },
          plate: { top: "42%", left: "50%", width: "33%", height: "17%", rotate: "0deg" },
        },
        sleeve: {
          pin: { top: "44%", left: "81%" },
          plate: { top: "46%", left: "77%", width: "13%", height: "29%", rotate: "21deg" },
        },
      },
      back: {
        back: {
          pin: { top: "42%", left: "50%" },
          plate: { top: "42%", left: "50%", width: "40%", height: "21%", rotate: "0deg" },
        },
        sleeve: {
          pin: { top: "44%", left: "21%" },
          plate: { top: "46%", left: "25%", width: "13%", height: "29%", rotate: "-21deg" },
        },
      },
    },
    customer_garment: {
      front: {
        front: {
          pin: { top: "43%", left: "50%" },
          plate: { top: "43%", left: "50%", width: "32%", height: "18%", rotate: "0deg" },
        },
        custom: {
          pin: { top: "62%", left: "32%" },
          plate: { top: "60%", left: "34%", width: "22%", height: "16%", rotate: "-10deg" },
        },
      },
      back: {
        back: {
          pin: { top: "43%", left: "50%" },
          plate: { top: "43%", left: "50%", width: "38%", height: "20%", rotate: "0deg" },
        },
        custom: {
          pin: { top: "62%", left: "68%" },
          plate: { top: "60%", left: "66%", width: "22%", height: "16%", rotate: "10deg" },
        },
      },
    },
  };

  const STATE = createState();
  const filesByZone = new Map(); // zone -> File[]

  // ── DOM refs ────────────────────────────────────────────────
  const dom = {
    shell: root.querySelector("[data-shell]"),
    form: root.querySelector("#customPrintConfiguratorForm"),
    progressShell: root.querySelector("[data-progress-shell]"),
    progressStrip: root.querySelector("[data-progress-strip]"),
    workbench: root.querySelector("[data-workbench]"),
    waterfall: root.querySelector("[data-waterfall]"),
    stageCard: root.querySelector("[data-stage-card]"),
    stageEyebrow: root.querySelector("[data-stage-eyebrow]"),
    stageTitleSecondary: root.querySelector("[data-stage-title-secondary]"),
    stageNote: root.querySelector("[data-stage-note]"),
    stageZones: root.querySelector("[data-stage-zones]"),
    stageAddons: root.querySelector("[data-stage-addons]"),
    stageLabel: root.querySelector("[data-stage-label]"),
    stagePlaceholder: root.querySelector("[data-stage-placeholder]"),
    stageViewSwitch: root.querySelectorAll("[data-stage-view]"),
    garment: root.querySelector("[data-garment]"),
    garmentHood: root.querySelector("[data-garment-hood]"),
    stageOverlay: root.querySelector("[data-stage-overlay]"),
    zoneLayer: root.querySelector("[data-zone-layer]"),
    receiptTotal: root.querySelector("[data-receipt-total]"),
    receiptList: root.querySelector("[data-receipt-list]"),
    receiptMode: root.querySelector("[data-receipt-mode]"),
    receiptHint: root.querySelector("[data-receipt-hint]"),
    modeList: root.querySelector("[data-mode-list]"),
    productList: root.querySelector("[data-product-list]"),
    fitList: root.querySelector("[data-fit-list]"),
    fabricList: root.querySelector("[data-fabric-list]"),
    fitBlock: root.querySelector("[data-fit-block]"),
    fabricBlock: root.querySelector("[data-fabric-block]"),
    colorList: root.querySelector("[data-color-list]"),
    zoneList: root.querySelector("[data-zone-list]"),
    placementNoteWrap: root.querySelector("[data-placement-note-wrap]"),
    placementNoteInput: root.querySelector("[data-placement-note-input]"),
    frontSizeWrap: root.querySelector("[data-front-size-wrap]"),
    frontSizeList: root.querySelector("[data-front-size-list]"),
    addonsList: root.querySelector("[data-addons-list]"),
    addonsWrap: root.querySelector("[data-addons-wrap]"),
    artworkList: root.querySelector("[data-artwork-service-list]"),
    dropzoneGrid: root.querySelector("[data-dropzone-grid]"),
    dropzoneEmpty: root.querySelector("[data-dropzone-empty]"),
    briefInput: root.querySelector("[data-brief-input]"),
    qtyInput: root.querySelector("[data-quantity-input]"),
    qtyHint: root.querySelector("[data-quantity-hint]"),
    qtySteps: root.querySelectorAll("[data-qty-step]"),
    sizeBlock: root.querySelector("[data-size-block]"),
    sizeGrid: root.querySelector("[data-size-grid]"),
    sizeMatrix: root.querySelector("[data-size-matrix]"),
    sizeWarning: root.querySelector("[data-size-warning]"),
    sizeHint: root.querySelector("[data-size-hint]"),
    sizeManagerBtn: root.querySelector("[data-size-manager]"),
    sizesNoteWrap: root.querySelector("[data-sizes-note-wrap]"),
    sizesNoteInput: root.querySelector("[data-sizes-note-input]"),
    garmentNoteWrap: root.querySelector("[data-garment-note-wrap]"),
    garmentNoteInput: root.querySelector("[data-garment-note-input]"),
    b2bMeta: root.querySelector("[data-b2b-meta]"),
    b2bDiscount: root.querySelector("[data-b2b-discount]"),
    giftToggle: root.querySelector("[data-gift-toggle]"),
    giftTextWrap: root.querySelector("[data-gift-text-wrap]"),
    giftTextInput: root.querySelector("[data-gift-text-input]"),
    contactChannelList: root.querySelector("[data-contact-channel-list]"),
    nameInput: root.querySelector("[data-name-input]"),
    contactValueInput: root.querySelector("[data-contact-value-input]"),
    brandFields: root.querySelector("[data-brand-fields]"),
    brandNameInput: root.querySelector("[data-brand-name-input]"),
    statusBox: root.querySelector("[data-status-box]"),
    addToCartBtn: root.querySelector("[data-action-add-to-cart]"),
    submitLeadBtn: root.querySelector("[data-action-submit-lead]"),
    safeExitBtn: root.querySelector("[data-safe-exit-trigger]"),
    startFlow: root.querySelector("[data-start-flow]"),
    cartActionHint: root.querySelector("[data-cart-action-hint]"),
    leadActionHint: root.querySelector("[data-lead-action-hint]"),
    stepEditButtons: root.querySelectorAll("[data-step-edit]"),
    stepBackButtons: root.querySelectorAll("[data-step-back]"),
    stepNextButtons: root.querySelectorAll("[data-step-next]"),
    stepSkipButtons: root.querySelectorAll("[data-step-skip]"),
  };

  init();

  // ────────────────────────────────────────────────────────────
  function createState() {
    return {
      mode: null, // "personal" | "brand"
      product: {
        type: null, // "hoodie" | "tshirt" | "longsleeve" | "customer_garment"
        fit: null,
        fabric: null,
        color: null,
      },
      print: {
        zones: [],
        add_ons: [],
        placement_note: "",
        zone_options: {},
      },
      artwork: {
        service_kind: null,
        triage_status: null,
      },
      order: {
        quantity: 0,
        size_mode: "single",
        sizes_note: "",
        size_breakdown: {},
        gift_enabled: false,
        gift_text: "",
      },
      notes: {
        brand_name: "",
        brief: "",
        garment_note: "",
      },
      contact: {
        channel: null,
        name: "",
        value: "",
      },
      ui: {
        current_step: "mode",
        done_steps: new Set(),
        stage_view: "front",
      },
    };
  }

  function init() {
    renderModeChips();
    renderProductCards();
    renderArtworkCardModifiers();
    renderContactChannelChips();
    renderZoneChipsForCurrent();
    renderFrontSizeOptions();
    renderAddons();
    renderColorChips();
    renderFitChips();
    renderFabricChips();
    bindWaterfallNav();
    bindStageView();
    bindQuantity();
    bindGiftToggle();
    bindFinalActions();
    bindGenericInputs();
    loadDraft();
    setActiveStep(STATE.ui.current_step || "mode", { silent: true });
    refreshAll();
  }

  function isLobbyPhase() {
    return !STATE.mode && STATE.ui.current_step === "mode";
  }

  function getStepIndex(stepKey) {
    return STEPS.indexOf(stepKey);
  }

  function getStageType() {
    return STATE.product.type || "hoodie";
  }

  function getFrontSizePreset() {
    return (
      STATE.print.zone_options?.front?.size_preset ||
      FRONT_SIZE_DEFAULT
    );
  }

  function getFrontSizeScale() {
    return FRONT_SIZE_PRESETS[getFrontSizePreset()]?.stage_scale || 0.74;
  }

  function ensureFrontZoneOptions() {
    if (!STATE.print.zone_options || typeof STATE.print.zone_options !== "object") {
      STATE.print.zone_options = {};
    }
    if (!STATE.print.zone_options.front || typeof STATE.print.zone_options.front !== "object") {
      STATE.print.zone_options.front = {};
    }
    if (!STATE.print.zone_options.front.size_preset) {
      STATE.print.zone_options.front.size_preset = FRONT_SIZE_DEFAULT;
    }
  }

  function normalizeClientState() {
    if (!STATE.print.zone_options || typeof STATE.print.zone_options !== "object") {
      STATE.print.zone_options = {};
    }

    if (STATE.product.type && !CONFIG.products?.[STATE.product.type]) {
      STATE.product.type = null;
    }

    const cfg = getProductConfig();
    const availableZones = cfg?.zones || [];
    const availableAddons = new Set((cfg?.add_ons || []).map((item) => item.value));
    const legacyAddons = new Map([["grommets", "lacing"], ["inside_label", "lacing"], ["hem_tag", "lacing"]]);

    STATE.print.zones = (STATE.print.zones || []).filter((zone) => availableZones.includes(zone));
    STATE.print.add_ons = (STATE.print.add_ons || [])
      .map((value) => legacyAddons.get(value) || value)
      .filter((value, index, list) => availableAddons.has(value) && list.indexOf(value) === index);

    Object.keys(STATE.print.zone_options).forEach((zone) => {
      if (!STATE.print.zones.includes(zone)) {
        delete STATE.print.zone_options[zone];
      }
    });

    if (STATE.print.zones.includes("front")) {
      ensureFrontZoneOptions();
    } else if (STATE.print.zone_options.front) {
      delete STATE.print.zone_options.front;
    }

    if (STATE.product.fit === "oversize") {
      STATE.product.fabric = "premium";
    }

    const colorValues = new Set((cfg?.colors || []).map((item) => item.value));
    if (cfg && (!STATE.product.color || !colorValues.has(STATE.product.color))) {
      STATE.product.color = cfg.default_color || (cfg.colors || [])[0]?.value || null;
    }

    const currentIndex = Math.max(0, getStepIndex(STATE.ui.current_step));
    if (!(STATE.ui.done_steps instanceof Set)) {
      STATE.ui.done_steps = new Set(Array.isArray(STATE.ui.done_steps) ? STATE.ui.done_steps : []);
    }
    if (!STATE.mode) {
      STATE.ui.done_steps.clear();
      STATE.ui.current_step = "mode";
    } else if (!STATE.ui.done_steps.size && currentIndex > 0) {
      STEPS.slice(0, currentIndex).forEach((step) => STATE.ui.done_steps.add(step));
    }
  }

  function getAvailableZones() {
    return getProductConfig()?.zones || [];
  }

  function getStagePreviewForZone(zone) {
    const scale = zone === "front" ? getFrontSizeScale() : 1;
    return {
      product_type: STATE.product.type || "",
      view: zone === "back" ? "back" : "front",
      color: STATE.product.color || "",
      scale,
    };
  }

  function buildZoneOptionsSnapshot() {
    const zoneOptions = {};
    (STATE.print.zones || []).forEach((zone) => {
      const current = { ...(STATE.print.zone_options?.[zone] || {}) };
      if (zone === "front") {
        current.size_preset = getFrontSizePreset();
      }
      current.scene_preview = getStagePreviewForZone(zone);
      zoneOptions[zone] = current;
    });
    return zoneOptions;
  }

  function collectOrderedFiles() {
    const ordered = [];
    (STATE.print.zones || []).forEach((zone) => {
      (filesByZone.get(zone) || []).forEach((file) => ordered.push({ zone, file }));
    });
    return ordered;
  }

  // ── Renderers ───────────────────────────────────────────────
  function renderModeChips() {
    const container = dom.modeList;
    if (!container) return;
    container.querySelectorAll("[data-choice-value]").forEach((btn) => {
      btn.addEventListener("click", () => {
        STATE.mode = btn.dataset.choiceValue;
        normalizeClientState();
        afterChoice("mode");
      });
    });
  }

  function renderModeChipsActive() {
    dom.modeList?.querySelectorAll("[data-choice-value]").forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.choiceValue === STATE.mode);
    });
  }

  function renderProductCards() {
    if (!dom.productList) return;
    dom.productList.querySelectorAll("[data-choice-value]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const value = btn.dataset.choiceValue;
        const previousType = STATE.product.type;
        STATE.product.type = value;
        STATE.product.fit = null;
        STATE.product.fabric = null;
        STATE.product.color = null;
        STATE.print.zones = [];
        STATE.print.add_ons = [];
        STATE.print.zone_options = {};
        STATE.print.placement_note = "";
        STATE.artwork.service_kind = null;
        STATE.artwork.triage_status = null;
        invalidateAfter("product");
        filesByZone.clear();
        if (previousType !== value) {
          STATE.order.size_breakdown = {};
          STATE.order.sizes_note = "";
        }
        normalizeClientState();
        renderFitChips();
        renderFabricChips();
        renderColorChips();
        renderAddons();
        renderZoneChipsForCurrent();
        renderFrontSizeOptions();
        afterChoice("product");
      });
    });
  }

  function renderProductCardsActive() {
    dom.productList?.querySelectorAll("[data-choice-value]").forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.choiceValue === STATE.product.type);
    });
  }

  function renderArtworkCardModifiers() {
    if (!dom.artworkList) return;
    dom.artworkList.querySelectorAll("[data-choice-value]").forEach((btn) => {
      btn.addEventListener("click", () => {
        STATE.artwork.service_kind = btn.dataset.choiceValue;
        if (STATE.artwork.service_kind === "ready") STATE.artwork.triage_status = "print-ready";
        else if (STATE.artwork.service_kind === "adjust") STATE.artwork.triage_status = "needs-work";
        else STATE.artwork.triage_status = "reference-only";
        renderArtworkActiveState();
        renderDropzones();
        refreshAll();
        persistDraft();
      });
    });
  }

  function renderContactChannelChips() {
    if (!dom.contactChannelList) return;
    dom.contactChannelList.innerHTML = "";
    (CONFIG.contact_channels || []).forEach((ch) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "cp-mini-chip";
      btn.dataset.choiceValue = ch.value;
      btn.textContent = ch.label;
      btn.addEventListener("click", () => {
        STATE.contact.channel = ch.value;
        if (dom.contactValueInput) dom.contactValueInput.placeholder = ch.placeholder || "@username або +380...";
        renderContactChannelChipsActive();
        refreshAll();
        persistDraft();
      });
      dom.contactChannelList.appendChild(btn);
    });
  }

  function renderContactChannelChipsActive() {
    if (!dom.contactChannelList) return;
    dom.contactChannelList.querySelectorAll("[data-choice-value]").forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.choiceValue === STATE.contact.channel);
    });
  }

  function getProductConfig() {
    if (!STATE.product.type) return null;
    return (CONFIG.products || {})[STATE.product.type] || null;
  }

  function renderFitChips() {
    if (!dom.fitList) return;
    dom.fitList.innerHTML = "";
    const cfg = getProductConfig();
    const fits = cfg && cfg.fits ? cfg.fits : [];
    if (!fits.length) {
      if (dom.fitBlock) dom.fitBlock.hidden = true;
      return;
    }
    if (dom.fitBlock) dom.fitBlock.hidden = false;
    fits.forEach((f) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "cp-fit-card";
      if (STATE.product.fit === f.value) btn.classList.add("is-active");
      btn.dataset.choiceValue = f.value;
      btn.innerHTML = `
        <small>Посадка</small>
        <strong>${f.label}</strong>
        <span>${f.description || ""}</span>
        <em>${f.value === "oversize" ? "Преміум-тканина фіксується автоматично" : "Можна обрати базу або преміум"}</em>
      `;
      btn.addEventListener("click", () => {
        STATE.product.fit = f.value;
        STATE.product.fabric = f.value === "oversize" ? "premium" : null;
        renderFabricChips();
        renderFitChips();
        refreshAll();
        persistDraft();
      });
      dom.fitList.appendChild(btn);
    });
  }

  function renderFabricChips() {
    if (!dom.fabricList) return;
    dom.fabricList.innerHTML = "";
    const cfg = getProductConfig();
    const fabricsMap = cfg && cfg.fabrics ? cfg.fabrics : {};
    const fabrics = STATE.product.fit ? fabricsMap[STATE.product.fit] || [] : [];
    if (!fabrics.length) {
      if (dom.fabricBlock) dom.fabricBlock.hidden = true;
      return;
    }
    if (dom.fabricBlock) dom.fabricBlock.hidden = false;
    const isLocked = STATE.product.fit === "oversize";
    fabrics.forEach((fab) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "cp-mini-chip";
      if (STATE.product.fabric === fab.value) btn.classList.add("is-active");
      if (isLocked && fab.value === "premium") btn.classList.add("is-locked");
      btn.dataset.choiceValue = fab.value;
      btn.textContent = fab.label;
      btn.addEventListener("click", () => {
        if (isLocked && fab.value !== "premium") return;
        STATE.product.fabric = fab.value;
        renderFabricChips();
        refreshAll();
        persistDraft();
      });
      dom.fabricList.appendChild(btn);
    });
  }

  function renderColorChips() {
    if (!dom.colorList) return;
    dom.colorList.innerHTML = "";
    const cfg = getProductConfig();
    const colors = cfg && cfg.colors ? cfg.colors : [];
    colors.forEach((c) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "cp-swatch";
      btn.dataset.choiceValue = c.value;
      btn.style.setProperty("--swatch", c.hex);
      if (STATE.product.color === c.value) btn.classList.add("is-active");
      btn.innerHTML = `<span class="cp-swatch-dot" style="background:${c.hex}"></span><span>${c.label}</span>`;
      btn.addEventListener("click", () => {
        STATE.product.color = c.value;
        applyGarmentColor();
        renderColorChips();
        refreshAll();
        persistDraft();
      });
      dom.colorList.appendChild(btn);
    });
  }

  function renderZoneChipsForCurrent() {
    if (!dom.zoneList) return;
    dom.zoneList.innerHTML = "";
    const cfg = getProductConfig();
    const zones = cfg && cfg.zones ? cfg.zones : [];
    if (!zones.length) {
      dom.zoneList.innerHTML = `<small class="cp-empty-hint">Спочатку оберіть виріб.</small>`;
      return;
    }
    zones.forEach((z) => {
      const isActive = STATE.print.zones.includes(z);
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "cp-mini-chip cp-mini-chip--zone";
      if (isActive) btn.classList.add("is-active");
      btn.dataset.choiceValue = z;
      btn.textContent = (CONFIG.zone_labels && CONFIG.zone_labels[z]) || z;
      btn.addEventListener("click", () => {
        toggleZone(z);
      });
      dom.zoneList.appendChild(btn);
    });
    // Show placement_note if "custom" zone is selected
    if (dom.placementNoteWrap) {
      dom.placementNoteWrap.hidden = !STATE.print.zones.includes("custom");
    }
    renderFrontSizeOptions();
    renderZoneOverlay();
  }

  function toggleZone(zone) {
    const current = new Set(STATE.print.zones || []);
    if (current.has(zone)) {
      current.delete(zone);
      filesByZone.delete(zone);
    } else {
      current.add(zone);
      if (zone === "front") ensureFrontZoneOptions();
      if (zone === "front") {
        applyStageView("front");
      } else if (zone === "back") {
        applyStageView("back");
      }
    }
    STATE.print.zones = getAvailableZones().filter((item) => current.has(item));
    if (!STATE.print.zones.includes("front") && STATE.print.zone_options.front) {
      delete STATE.print.zone_options.front;
    }
    invalidateAfter("zones");
    renderZoneChipsForCurrent();
    renderDropzones();
    refreshAll();
    persistDraft();
  }

  function renderFrontSizeOptions() {
    if (!dom.frontSizeList || !dom.frontSizeWrap) return;
    dom.frontSizeList.innerHTML = "";
    const enabled = STATE.print.zones.includes("front");
    dom.frontSizeWrap.hidden = !enabled;
    if (!enabled) return;
    ensureFrontZoneOptions();
    (CONFIG.front_size_presets || []).forEach((preset) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "cp-size-preset";
      btn.dataset.choiceValue = preset.value;
      if (getFrontSizePreset() === preset.value) btn.classList.add("is-active");
      btn.innerHTML = `<strong>${preset.label}</strong><span>Масштаб на сцені</span>`;
      btn.addEventListener("click", () => {
        ensureFrontZoneOptions();
        STATE.print.zone_options.front.size_preset = preset.value;
        applyStageView("front");
        renderFrontSizeOptions();
        refreshAll();
        persistDraft();
      });
      dom.frontSizeList.appendChild(btn);
    });
  }

  function renderAddons() {
    if (!dom.addonsList) return;
    dom.addonsList.innerHTML = "";
    const cfg = getProductConfig();
    const addons = cfg && cfg.add_ons ? cfg.add_ons : [];
    if (!addons.length) {
      if (dom.addonsWrap) dom.addonsWrap.hidden = true;
      return;
    }
    if (dom.addonsWrap) dom.addonsWrap.hidden = false;
    addons.forEach((a) => {
      const isActive = STATE.print.add_ons.includes(a.value);
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "cp-addon-card cp-addon-card--lacing";
      if (isActive) btn.classList.add("is-active");
      btn.dataset.choiceValue = a.value;
      btn.dataset.priceModifier = String(a.price_delta || 0);
      btn.innerHTML = `
        <span class="cp-addon-card-icon" aria-hidden="true">${addonSvg(a.icon)}</span>
        <span class="cp-addon-card-body">
          <strong>${a.label}</strong>
          <span class="cp-addon-card-badge">${a.badge || ""}</span>
          <span class="cp-addon-card-hint">${a.hint || ""}</span>
        </span>
      `;
      btn.addEventListener("click", () => {
        const i = STATE.print.add_ons.indexOf(a.value);
        if (i >= 0) STATE.print.add_ons.splice(i, 1);
        else STATE.print.add_ons.push(a.value);
        renderAddons();
        refreshAll();
        persistDraft();
      });
      dom.addonsList.appendChild(btn);
    });
  }

  function addonSvg(name) {
    if (name === "lacing") return lacingSvg();
    return defaultDotSvg();
  }

  function lacingSvg() {
    return `
      <svg viewBox="0 0 56 56" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <circle cx="18" cy="20" r="4" stroke="currentColor" stroke-width="2"/>
        <circle cx="38" cy="20" r="4" stroke="currentColor" stroke-width="2"/>
        <circle cx="18" cy="36" r="4" stroke="currentColor" stroke-width="2"/>
        <circle cx="38" cy="36" r="4" stroke="currentColor" stroke-width="2"/>
        <path d="M22 20 L34 36 M34 20 L22 36 M22 36 L34 20" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        <path d="M14 24 C 8 28, 8 28, 14 32 M42 24 C 48 28, 48 28, 42 32" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
      </svg>
    `;
  }

  function defaultDotSvg() {
    return `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="6" stroke="currentColor" stroke-width="2"/></svg>`;
  }

  function renderArtworkActiveState() {
    if (!dom.artworkList) return;
    dom.artworkList.querySelectorAll("[data-choice-value]").forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.choiceValue === STATE.artwork.service_kind);
    });
  }

  function renderDropzones() {
    if (!dom.dropzoneGrid) return;
    // Clear all .cp-dropzone children but keep the empty hint
    dom.dropzoneGrid.querySelectorAll(".cp-dropzone").forEach((el) => el.remove());
    const zones = STATE.print.zones;
    if (!zones.length) {
      if (dom.dropzoneEmpty) dom.dropzoneEmpty.hidden = false;
      return;
    }
    if (dom.dropzoneEmpty) dom.dropzoneEmpty.hidden = true;
    zones.forEach((zone) => {
      const wrap = document.createElement("label");
      wrap.className = "cp-dropzone";
      wrap.dataset.zone = zone;
      const label = (CONFIG.zone_labels && CONFIG.zone_labels[zone]) || zone;
      const filesInfo = filesByZone.get(zone) || [];
      wrap.innerHTML = `
        <div class="cp-dropzone-head">
          <small>Зона</small>
          <strong>${label}</strong>
        </div>
        <input type="file" multiple accept="image/*,application/pdf,.ai,.eps,.psd,.tiff,.svg" data-dropzone-input>
        <div class="cp-dropzone-body">
          <span class="cp-dropzone-cta">+ Завантажити файл</span>
          <span class="cp-dropzone-meta" data-dropzone-meta>${filesInfo.length ? filesInfo.length + ' файл(ів) додано' : 'PDF, AI, EPS, PSD, PNG, JPG, TIFF, SVG'}</span>
        </div>
        ${filesInfo.length ? `<ul class="cp-dropzone-list">${filesInfo.map((f) => `<li>${escapeHtml(f.name)} <small>${formatBytes(f.size)}</small></li>`).join("")}</ul>` : ""}
      `;
      const input = wrap.querySelector("[data-dropzone-input]");
      input.addEventListener("change", (event) => {
        const files = Array.from(event.target.files || []);
        if (files.length) {
          filesByZone.set(zone, files);
        } else {
          filesByZone.delete(zone);
        }
        renderDropzones();
        refreshAll();
      });
      dom.dropzoneGrid.appendChild(wrap);
    });
  }

  // ── Stage rendering ─────────────────────────────────────────
  function applyGarmentColor() {
    if (!dom.garment) return;
    const cfg = getProductConfig();
    const color = (cfg?.colors || []).find((c) => c.value === STATE.product.color);
    const gradient = color ? buildGarmentGradient(color.hex) : buildGarmentGradient("#4a454e");
    dom.garment.style.setProperty("--cp-garment-fill", gradient);
  }

  function applyGarmentType() {
    if (!dom.garment) return;
    const type = getStageType();
    dom.garment.classList.remove("cp-garment--hoodie", "cp-garment--tshirt", "cp-garment--longsleeve", "cp-garment--customer_garment", "is-placeholder");
    dom.garment.classList.add(
      type === "tshirt" ? "cp-garment--tshirt" :
      type === "longsleeve" ? "cp-garment--longsleeve" :
      type === "customer_garment" ? "cp-garment--customer_garment" :
      "cp-garment--hoodie"
    );
    dom.garment.classList.toggle("is-placeholder", !STATE.product.type);
    if (dom.garmentHood) dom.garmentHood.style.display = type === "hoodie" ? "" : "none";
  }

  function applyStageView(view) {
    STATE.ui.stage_view = view;
    if (!dom.garment) return;
    dom.garment.classList.toggle("cp-garment--front", view === "front");
    dom.garment.classList.toggle("cp-garment--back", view === "back");
    dom.stageViewSwitch?.forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.stageView === view);
    });
    renderZoneOverlay();
  }

  function renderZoneOverlay() {
    if (!dom.zoneLayer || !dom.stageOverlay) return;
    dom.zoneLayer.innerHTML = "";
    dom.stageOverlay.innerHTML = "";
    if (dom.stagePlaceholder) dom.stagePlaceholder.hidden = !!STATE.product.type;
    if (!STATE.product.type) return;

    const availableZones = getAvailableZones();
    const viewLayouts = (STAGE_LAYOUTS[STATE.product.type] || {})[STATE.ui.stage_view] || {};

    availableZones.forEach((zone) => {
      const layout = viewLayouts[zone];
      if (!layout) return;
      const isActive = STATE.print.zones.includes(zone);
      const pin = document.createElement("button");
      pin.type = "button";
      pin.className = "cp-zone-pin";
      if (isActive) pin.classList.add("is-active");
      pin.style.top = layout.pin.top;
      pin.style.left = layout.pin.left;
      pin.dataset.zone = zone;
      pin.innerHTML = `<span>${escapeHtml((CONFIG.zone_labels && CONFIG.zone_labels[zone]) || zone)}</span>`;
      pin.title = (CONFIG.zone_labels && CONFIG.zone_labels[zone]) || zone;
      pin.addEventListener("click", () => toggleZone(zone));
      dom.zoneLayer.appendChild(pin);

      if (isActive) {
        const plate = document.createElement("button");
        const sizePreset = zone === "front" ? getFrontSizePreset() : "";
        const scale = zone === "front" ? getFrontSizeScale() : 1;
        plate.type = "button";
        plate.className = `cp-stage-print cp-stage-print--${zone}`;
        plate.style.setProperty("--plate-top", layout.plate.top);
        plate.style.setProperty("--plate-left", layout.plate.left);
        plate.style.setProperty("--plate-width", layout.plate.width);
        plate.style.setProperty("--plate-height", layout.plate.height);
        plate.style.setProperty("--plate-rotate", layout.plate.rotate || "0deg");
        plate.style.setProperty("--plate-scale", String(scale));
        plate.style.setProperty("--plate-label-scale", String(scale > 0 ? 1 / scale : 1));
        plate.dataset.zone = zone;
        plate.innerHTML = `
          <span class="cp-stage-print-label">${escapeHtml((CONFIG.zone_labels && CONFIG.zone_labels[zone]) || zone)}</span>
          <span class="cp-stage-print-badge">${zone === "front" ? escapeHtml(sizePreset) : "ON"}</span>
        `;
        plate.addEventListener("click", () => toggleZone(zone));
        dom.stageOverlay.appendChild(plate);
      }
    });
  }

  function buildGarmentGradient(hex) {
    const top = mixHex(hex, "#ffffff", 0.22);
    const middle = mixHex(hex, "#2d2520", 0.16);
    const bottom = mixHex(hex, "#000000", 0.34);
    return `linear-gradient(180deg, ${top} 0%, ${middle} 48%, ${bottom} 100%)`;
  }

  function bindStageView() {
    dom.stageViewSwitch?.forEach((btn) => {
      btn.addEventListener("click", () => applyStageView(btn.dataset.stageView));
    });
  }

  // ── Quantity + Smart sizing ─────────────────────────────────
  function bindQuantity() {
    if (dom.qtyInput) {
      dom.qtyInput.addEventListener("input", () => {
        const v = parseInt(dom.qtyInput.value, 10);
        STATE.order.quantity = isFinite(v) && v > 0 ? v : 0;
        renderSizing();
        refreshAll();
        persistDraft();
      });
    }
    dom.qtySteps?.forEach((btn) => {
      btn.addEventListener("click", () => {
        const delta = parseInt(btn.dataset.qtyStep, 10) || 0;
        const next = Math.max(0, (STATE.order.quantity || 0) + delta);
        STATE.order.quantity = next;
        if (dom.qtyInput) dom.qtyInput.value = next || "";
        renderSizing();
        refreshAll();
        persistDraft();
      });
    });
    dom.sizeManagerBtn?.addEventListener("click", () => {
      STATE.order.size_mode = "manager";
      renderSizing();
      refreshAll();
      persistDraft();
    });
    dom.sizesNoteInput?.addEventListener("input", () => {
      STATE.order.sizes_note = dom.sizesNoteInput.value;
      persistDraft();
    });
    dom.garmentNoteInput?.addEventListener("input", () => {
      STATE.notes.garment_note = dom.garmentNoteInput.value;
      persistDraft();
    });
  }

  function renderSizing() {
    if (!dom.sizeBlock) return;
    const qty = STATE.order.quantity || 0;
    const grid = CONFIG.size_grid || ["XS", "S", "M", "L", "XL", "2XL"];
    if (qty <= 0) {
      dom.sizeBlock.hidden = true;
      if (dom.qtyHint) dom.qtyHint.textContent = "Введіть кількість — ми покажемо адаптивний вибір розмірів.";
      if (dom.b2bMeta) dom.b2bMeta.hidden = true;
      return;
    }
    dom.sizeBlock.hidden = false;
    if (STATE.product.type === "customer_garment") {
      // For customer_garment we hide size grid entirely, keep textarea
      dom.sizeGrid.hidden = true;
      dom.sizeMatrix.hidden = true;
      if (dom.sizeManagerBtn) dom.sizeManagerBtn.hidden = true;
      if (dom.sizesNoteWrap) dom.sizesNoteWrap.hidden = false;
      if (dom.garmentNoteWrap) dom.garmentNoteWrap.hidden = false;
      if (dom.sizeWarning) dom.sizeWarning.hidden = true;
      if (dom.qtyHint) dom.qtyHint.textContent = "Опишіть розміри і характеристики свого виробу нижче.";
    } else if (qty === 1) {
      // Single-size chip row
      STATE.order.size_mode = "single";
      dom.sizeGrid.hidden = false;
      dom.sizeMatrix.hidden = true;
      if (dom.sizeManagerBtn) dom.sizeManagerBtn.hidden = false;
      if (dom.garmentNoteWrap) dom.garmentNoteWrap.hidden = true;
      if (dom.sizesNoteWrap) dom.sizesNoteWrap.hidden = true;
      if (dom.qtyHint) dom.qtyHint.textContent = "Один виріб — один розмір. Натисніть, щоб обрати.";
      // Reset size_breakdown to single
      const currentSingle = grid.find((s) => (STATE.order.size_breakdown || {})[s]) || null;
      dom.sizeGrid.innerHTML = "";
      grid.forEach((s) => {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "cp-mini-chip";
        if (currentSingle === s) chip.classList.add("is-active");
        chip.dataset.choiceValue = s;
        chip.textContent = s;
        chip.addEventListener("click", () => {
          STATE.order.size_breakdown = { [s]: 1 };
          renderSizing();
          refreshAll();
          persistDraft();
        });
        dom.sizeGrid.appendChild(chip);
      });
      if (dom.sizeWarning) dom.sizeWarning.hidden = true;
    } else {
      // Matrix mode
      if (STATE.order.size_mode === "manager") {
        dom.sizeGrid.hidden = true;
        dom.sizeMatrix.hidden = true;
        if (dom.sizeManagerBtn) dom.sizeManagerBtn.hidden = false;
        if (dom.sizesNoteWrap) dom.sizesNoteWrap.hidden = false;
        if (dom.garmentNoteWrap) dom.garmentNoteWrap.hidden = true;
        if (dom.qtyHint) dom.qtyHint.textContent = "Розміри уточнимо разом з менеджером — заповніть примітку.";
        if (dom.sizeWarning) dom.sizeWarning.hidden = true;
        return;
      }
      STATE.order.size_mode = "mixed";
      dom.sizeGrid.hidden = true;
      dom.sizeMatrix.hidden = false;
      if (dom.sizeManagerBtn) dom.sizeManagerBtn.hidden = false;
      if (dom.sizesNoteWrap) dom.sizesNoteWrap.hidden = false;
      if (dom.garmentNoteWrap) dom.garmentNoteWrap.hidden = true;
      if (dom.qtyHint) dom.qtyHint.textContent = `Розподіліть ${qty} шт. по розмірах. Сума має дорівнювати ${qty}.`;

      dom.sizeMatrix.innerHTML = "";
      grid.forEach((s) => {
        const wrap = document.createElement("label");
        wrap.className = "cp-size-matrix-cell";
        wrap.innerHTML = `<span>${s}</span><input type="number" min="0" inputmode="numeric" value="${(STATE.order.size_breakdown || {})[s] || ""}" placeholder="0" data-size-input="${s}">`;
        const input = wrap.querySelector("input");
        input.addEventListener("input", () => {
          const n = parseInt(input.value, 10);
          if (!STATE.order.size_breakdown) STATE.order.size_breakdown = {};
          STATE.order.size_breakdown[s] = isFinite(n) && n > 0 ? n : 0;
          validateSizeMatrix();
          refreshAll();
          persistDraft();
        });
        dom.sizeMatrix.appendChild(wrap);
      });
      validateSizeMatrix();
    }
    // B2B live calc
    updateB2bMeta();
  }

  function validateSizeMatrix() {
    if (!dom.sizeWarning) return;
    const qty = STATE.order.quantity || 0;
    const sum = Object.values(STATE.order.size_breakdown || {}).reduce((a, b) => a + (parseInt(b, 10) || 0), 0);
    if (qty > 1 && STATE.order.size_mode === "mixed" && sum !== qty) {
      dom.sizeWarning.hidden = false;
      dom.sizeWarning.textContent = sum < qty
        ? `Не вистачає ${qty - sum} шт. — додайте розміри.`
        : `Перевищено на ${sum - qty} шт. — зменшіть розміри.`;
      dom.sizeWarning.classList.toggle("is-error", sum !== qty);
    } else {
      dom.sizeWarning.hidden = true;
    }
  }

  function updateB2bMeta() {
    const qty = STATE.order.quantity || 0;
    const isB2b = STATE.mode === "brand";
    if (!isB2b || qty < 5) {
      if (dom.b2bMeta) dom.b2bMeta.hidden = true;
      return;
    }
    const tier = CONFIG.b2b_tier || { unit_step: 5, discount_per_unit: 10 };
    const steps = Math.floor(qty / tier.unit_step);
    const discount = steps * tier.discount_per_unit;
    if (dom.b2bMeta) dom.b2bMeta.hidden = false;
    if (dom.b2bDiscount) dom.b2bDiscount.textContent = `-${discount} грн / шт`;
  }

  // ── Gift toggle ─────────────────────────────────────────────
  function bindGiftToggle() {
    dom.giftToggle?.addEventListener("click", () => {
      STATE.order.gift_enabled = !STATE.order.gift_enabled;
      dom.giftToggle.classList.toggle("is-active", STATE.order.gift_enabled);
      if (dom.giftTextWrap) dom.giftTextWrap.hidden = !STATE.order.gift_enabled;
      refreshAll();
      persistDraft();
    });
    dom.giftTextInput?.addEventListener("input", () => {
      STATE.order.gift_text = dom.giftTextInput.value;
      persistDraft();
    });
  }

  // ── Generic inputs ──────────────────────────────────────────
  function bindGenericInputs() {
    dom.placementNoteInput?.addEventListener("input", () => {
      STATE.print.placement_note = dom.placementNoteInput.value;
      persistDraft();
    });
    dom.briefInput?.addEventListener("input", () => {
      STATE.notes.brief = dom.briefInput.value;
      persistDraft();
    });
    dom.nameInput?.addEventListener("input", () => {
      STATE.contact.name = dom.nameInput.value;
      refreshAll();
      persistDraft();
    });
    dom.contactValueInput?.addEventListener("input", () => {
      STATE.contact.value = dom.contactValueInput.value;
      refreshAll();
      persistDraft();
    });
    dom.brandNameInput?.addEventListener("input", () => {
      STATE.notes.brand_name = dom.brandNameInput.value;
      persistDraft();
    });
    dom.startFlow?.addEventListener("click", () => {
      const target = document.getElementById("cp-step-mode");
      if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  // ── Waterfall step navigation ───────────────────────────────
  function bindWaterfallNav() {
    dom.stepEditButtons?.forEach((btn) => {
      btn.addEventListener("click", () => setActiveStep(btn.dataset.stepEdit));
    });
    dom.stepBackButtons?.forEach((btn) => {
      btn.addEventListener("click", () => setActiveStep(btn.dataset.stepBack));
    });
    dom.stepNextButtons?.forEach((btn) => {
      btn.addEventListener("click", () => {
        const target = btn.dataset.stepNext;
        if (canAdvance(STATE.ui.current_step)) {
          markStepDone(STATE.ui.current_step);
          setActiveStep(target);
        } else {
          showStatus("Заповніть поточний крок, щоб рухатись далі.", "warning");
        }
      });
    });
    dom.stepSkipButtons?.forEach((btn) => {
      btn.addEventListener("click", () => {
        // Skip current step (e.g. gift)
        STATE.order.gift_enabled = false;
        if (dom.giftToggle) dom.giftToggle.classList.remove("is-active");
        if (dom.giftTextWrap) dom.giftTextWrap.hidden = true;
        markStepDone(STATE.ui.current_step);
        setActiveStep(btn.dataset.stepSkip);
        refreshAll();
        persistDraft();
      });
    });
  }

  function setActiveStep(key, opts = {}) {
    if (!STEPS.includes(key)) return;
    STATE.ui.current_step = key;
    const currentIndex = getStepIndex(key);
    document.querySelectorAll("[data-step]").forEach((section) => {
      const stepKey = section.dataset.step;
      const stepIndex = getStepIndex(stepKey);
      const isCurrent = stepKey === key;
      const isDone = STATE.ui.done_steps.has(stepKey);
      const isVisible = isCurrent || (isDone && stepIndex < currentIndex);
      section.hidden = !isVisible;
      section.classList.toggle("is-active", isCurrent);
      section.classList.toggle("is-done", !isCurrent && isDone);
      section.classList.toggle("is-pending", !isCurrent && !isDone && stepIndex > currentIndex);
    });
    refreshAll();
    if (!opts.silent) {
      const target = document.getElementById(`cp-step-${key}`);
      if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    persistDraft();
  }

  function markStepDone(key) {
    if (!STEPS.includes(key)) return;
    STATE.ui.done_steps.add(key);
  }

  function invalidateAfter(stepKey) {
    const stepIndex = getStepIndex(stepKey);
    STEPS.slice(stepIndex + 1).forEach((item) => STATE.ui.done_steps.delete(item));
    if (getStepIndex(STATE.ui.current_step) > stepIndex) {
      STATE.ui.current_step = stepKey;
    }
  }

  function afterChoice(stepKey) {
    markStepDone(stepKey);
    refreshAll();
    // Determine next step
    const next = nextStepAfter(stepKey);
    if (next) setActiveStep(next);
    persistDraft();
  }

  function nextStepAfter(stepKey) {
    let idx = STEPS.indexOf(stepKey);
    if (idx < 0) return null;
    for (let i = idx + 1; i < STEPS.length; i++) {
      return STEPS[i];
    }
    return null;
  }

  function canAdvance(stepKey) {
    switch (stepKey) {
      case "mode": return !!STATE.mode;
      case "product": return !!STATE.product.type;
      case "config":
        if (!STATE.product.type) return false;
        if (STATE.product.type === "hoodie") return !!STATE.product.fit && !!STATE.product.fabric && !!STATE.product.color;
        return !!STATE.product.color;
      case "zones": return STATE.print.zones.length > 0;
      case "artwork": return !!STATE.artwork.service_kind;
      case "quantity":
        if (STATE.order.quantity <= 0) return false;
        if (STATE.product.type === "customer_garment") return true;
        if (STATE.order.size_mode === "manager") return true;
        if (STATE.order.quantity === 1) return Object.values(STATE.order.size_breakdown || {}).some((v) => v > 0);
        const sum = Object.values(STATE.order.size_breakdown || {}).reduce((a, b) => a + (parseInt(b, 10) || 0), 0);
        return sum === STATE.order.quantity;
      case "gift":
        return true; // gift is optional, the next button always works
      case "contact":
        return !!STATE.contact.channel && !!STATE.contact.name && !!STATE.contact.value;
      default:
        return true;
    }
  }

  // ── Refresh: stage card + receipt + summaries + side states ─
  function refreshAll() {
    normalizeClientState();
    updateFlowPhase();
    updateStageVisibility();
    updateStageMeta();
    applyGarmentType();
    applyGarmentColor();
    applyStageView(STATE.ui.stage_view || "front");
    renderModeChipsActive();
    renderProductCardsActive();
    updateBrandFieldsVisibility();
    updateSummaries();
    renderProgressStrip();
    updateB2bMeta();
    renderReceipt();
    updateFinalActionsAvailability();
  }

  function updateFlowPhase() {
    const lobby = isLobbyPhase();
    root.dataset.flowPhase = lobby ? "lobby" : "studio";
    if (dom.shell) dom.shell.dataset.flowPhase = lobby ? "lobby" : "studio";
    if (dom.progressShell) dom.progressShell.hidden = lobby;
    if (dom.workbench) dom.workbench.classList.toggle("is-lobby-mode", lobby);
  }

  function renderProgressStrip() {
    if (!dom.progressStrip) return;
    const steps = CONFIG.progress_steps || STEPS.map((value) => ({ value, label: value }));
    dom.progressStrip.innerHTML = "";
    steps.forEach((step) => {
      const btn = document.createElement("button");
      const stepKey = step.value;
      const isActive = STATE.ui.current_step === stepKey;
      const isDone = STATE.ui.done_steps.has(stepKey);
      btn.type = "button";
      btn.className = "cp-build-chip";
      if (isActive) btn.classList.add("is-active");
      else if (isDone) btn.classList.add("is-done");
      else btn.classList.add("is-pending");
      btn.innerHTML = `
        <small>${getStepIndex(stepKey) + 1}. ${escapeHtml(step.label)}</small>
        <strong>${escapeHtml(getProgressStepValue(stepKey))}</strong>
      `;
      btn.disabled = !isActive && !isDone;
      btn.addEventListener("click", () => {
        if (!btn.disabled) setActiveStep(stepKey);
      });
      dom.progressStrip.appendChild(btn);
    });
  }

  function getProgressStepValue(stepKey) {
    const value = root.querySelector(`[data-step-summary-value="${stepKey}"]`)?.textContent?.trim();
    return value && value !== "—" ? value : "Ще не вибрано";
  }

  function updateStageVisibility() {
    if (!dom.stageCard) return;
    const visible = !isLobbyPhase() && STAGE_VISIBLE_AFTER.has(STATE.ui.current_step);
    dom.stageCard.classList.toggle("is-hidden", !visible);
  }

  function updateStageMeta() {
    const cfg = getProductConfig();
    const placeholder = CONFIG.stage_meta || {};
    if (dom.stageEyebrow) dom.stageEyebrow.textContent = cfg ? (cfg.eyebrow || "Виріб") : "Сцена";
    if (dom.stageLabel) dom.stageLabel.textContent = cfg ? `${cfg.label} на сцені` : (placeholder.placeholder_title || "Виріб на сцені");
    if (dom.stageTitleSecondary) dom.stageTitleSecondary.textContent = cfg ? cfg.label : (placeholder.placeholder_title || "—");
    if (dom.stageNote) dom.stageNote.textContent = cfg ? (cfg.hero_note || cfg.summary || "") : (placeholder.placeholder_note || "Оберіть виріб, щоб побачити деталі.");
    if (dom.stageZones) {
      const zones = STATE.print.zones.map((z) => (CONFIG.zone_labels && CONFIG.zone_labels[z]) || z);
      dom.stageZones.textContent = zones.length ? zones.join(", ") : (cfg ? "Зони ще не активовані" : "Зони зʼявляться після вибору виробу");
    }
    if (dom.stageAddons) {
      const cfgAddons = (cfg && cfg.add_ons) || [];
      const labels = STATE.print.add_ons
        .map((v) => (cfgAddons.find((a) => a.value === v) || {}).label)
        .filter(Boolean);
      if (STATE.print.zones.includes("front")) labels.push(`Спереду · ${getFrontSizePreset()}`);
      const giftLabel = STATE.order.gift_enabled ? `Подарункова упаковка` : null;
      const all = [...labels, giftLabel].filter(Boolean);
      dom.stageAddons.textContent = all.length ? all.join(" · ") : (cfg ? "Без додаткових деталей." : "Поки що без активних деталей.");
    }
  }

  function updateBrandFieldsVisibility() {
    if (!dom.brandFields) return;
    dom.brandFields.hidden = STATE.mode !== "brand";
  }

  function updateSummaries() {
    setStepSummary("mode", STATE.mode === "brand" ? "Для команди / бренду" : STATE.mode === "personal" ? "Для себе" : "—");

    const cfg = getProductConfig();
    setStepSummary("product", cfg ? cfg.label : "—");

    if (STATE.product.type === "hoodie") {
      const parts = [];
      if (STATE.product.fit) parts.push(STATE.product.fit === "oversize" ? "Оверсайз" : "Класичний");
      if (STATE.product.fabric) parts.push(STATE.product.fabric === "premium" ? "Преміум" : "База");
      if (STATE.product.color) {
        const c = (cfg.colors || []).find((x) => x.value === STATE.product.color);
        if (c) parts.push(c.label);
      }
      if (STATE.print.add_ons.includes("lacing")) parts.push("Люверси");
      setStepSummary("config", parts.length ? parts.join(" · ") : "—");
    } else {
      const c = cfg ? (cfg.colors || []).find((x) => x.value === STATE.product.color) : null;
      setStepSummary("config", c ? c.label : "—");
    }

    setStepSummary("zones", STATE.print.zones.length
      ? STATE.print.zones.map((z) => {
        const label = (CONFIG.zone_labels && CONFIG.zone_labels[z]) || z;
        if (z === "front") return `${label} · ${getFrontSizePreset()}`;
        return label;
      }).join(", ")
      : "—");

    if (STATE.artwork.service_kind) {
      const services = CONFIG.artwork_services || [];
      const item = services.find((s) => s.value === STATE.artwork.service_kind);
      const totalFiles = Array.from(filesByZone.values()).reduce((acc, list) => acc + list.length, 0);
      setStepSummary("artwork", `${item ? item.label : "—"}${totalFiles ? ` · ${totalFiles} файл(ів)` : ""}`);
    } else {
      setStepSummary("artwork", "—");
    }

    if (STATE.order.quantity > 0) {
      let breakdown = "";
      if (STATE.product.type !== "customer_garment" && STATE.order.size_mode !== "manager") {
        const entries = Object.entries(STATE.order.size_breakdown || {})
          .filter(([, v]) => v > 0)
          .map(([k, v]) => `${k}×${v}`);
        if (entries.length) breakdown = ` · ${entries.join(", ")}`;
      } else if (STATE.order.size_mode === "manager") {
        breakdown = " · через менеджера";
      }
      setStepSummary("quantity", `${STATE.order.quantity} шт${breakdown}`);
    } else {
      setStepSummary("quantity", "—");
    }

    setStepSummary("gift", STATE.order.gift_enabled ? `Так (+${(CONFIG.gift_service || {}).price || 100} грн)` : "Без подарунку");

    if (STATE.contact.channel || STATE.contact.value) {
      const channelMap = (CONFIG.contact_channels || []).reduce((acc, ch) => { acc[ch.value] = ch.label; return acc; }, {});
      const ch = channelMap[STATE.contact.channel] || "—";
      setStepSummary("contact", `${ch}${STATE.contact.value ? `: ${STATE.contact.value}` : ""}`);
    } else {
      setStepSummary("contact", "—");
    }
  }

  function setStepSummary(key, value) {
    const el = root.querySelector(`[data-step-summary-value="${key}"]`);
    if (el) el.textContent = value;
  }

  // ── Pricing ─────────────────────────────────────────────────
  function computePricing() {
    const cfg = getProductConfig();
    if (!cfg || !cfg.pricing) {
      return {
        base_price: null,
        design_price: 0,
        addons_price: 0,
        gift_price: 0,
        zones_price: 0,
        unit_total: null,
        b2b_discount_per_unit: 0,
        final_total: null,
        estimate_required: !!cfg && (cfg.pricing?.base === null || STATE.product.type === "customer_garment"),
        estimate_reason: STATE.product.type === "customer_garment" ? "Свій одяг — потрібен ручний прорахунок." : "",
        breakdown: [],
      };
    }
    const pricing = cfg.pricing;
    const breakdown = [];

    let base = pricing.base ?? 0;
    if (STATE.product.fabric === "premium") base += pricing.premium_delta || 0;
    if (STATE.product.fit === "oversize") base += pricing.oversize_delta || 0;
    breakdown.push({ label: `База · ${cfg.label}`, value: base });

    const extraZones = Math.max(0, STATE.print.zones.length - 1);
    const zonesPrice = extraZones * (pricing.extra_zone_delta || 0);
    if (extraZones > 0) breakdown.push({ label: `+${extraZones} зон`, value: zonesPrice });

    let designPrice = 0;
    const services = CONFIG.artwork_services || [];
    const svc = services.find((s) => s.value === STATE.artwork.service_kind);
    if (svc && svc.price_delta) {
      designPrice = svc.price_delta;
      breakdown.push({ label: svc.label, value: designPrice });
    }

    let addonsPrice = 0;
    const cfgAddons = cfg.add_ons || [];
    STATE.print.add_ons.forEach((value) => {
      const a = cfgAddons.find((x) => x.value === value);
      if (a && a.price_delta) {
        addonsPrice += a.price_delta;
        breakdown.push({ label: a.label, value: a.price_delta });
      }
    });

    let giftPrice = 0;
    if (STATE.order.gift_enabled) {
      giftPrice = (CONFIG.gift_service || {}).price || 0;
      if (giftPrice) breakdown.push({ label: "Подарункова упаковка", value: giftPrice });
    }

    let unitTotal = base + zonesPrice + designPrice + addonsPrice;
    let b2bDiscountPerUnit = 0;
    const qty = STATE.order.quantity || 0;
    if (STATE.mode === "brand" && qty >= 5) {
      const tier = CONFIG.b2b_tier || { unit_step: 5, discount_per_unit: 10 };
      const steps = Math.floor(qty / tier.unit_step);
      b2bDiscountPerUnit = steps * tier.discount_per_unit;
    }
    const unitAfterDiscount = Math.max(0, unitTotal - b2bDiscountPerUnit);
    const subTotal = unitAfterDiscount * Math.max(1, qty || 1);
    const finalTotal = subTotal + giftPrice;
    if (b2bDiscountPerUnit > 0) {
      breakdown.push({ label: `B2B знижка (-${b2bDiscountPerUnit} грн/шт × ${qty})`, value: -b2bDiscountPerUnit * qty });
    }

    return {
      base_price: base,
      design_price: designPrice,
      addons_price: addonsPrice,
      gift_price: giftPrice,
      zones_price: zonesPrice,
      unit_total: unitAfterDiscount,
      b2b_discount_per_unit: b2bDiscountPerUnit,
      final_total: finalTotal,
      quantity: qty,
      estimate_required: false,
      estimate_reason: "",
      breakdown,
    };
  }

  function renderReceipt() {
    if (!dom.receiptList || !dom.receiptTotal) return;
    const pricing = computePricing();
    if (!STATE.product.type) {
      dom.receiptTotal.textContent = "Ціну побачите після першого вибору";
      dom.receiptList.innerHTML = `<li class="is-empty">Поки що нічого не додано — оберіть виріб, щоб побачити прорахунок.</li>`;
      if (dom.receiptMode) dom.receiptMode.textContent = "Базова конфігурація";
      if (dom.receiptHint) dom.receiptHint.textContent = "Ціна оновлюється в реальному часі.";
      return;
    }
    if (pricing.estimate_required || pricing.base_price === null) {
      dom.receiptTotal.textContent = "Прорахунок з менеджером";
      dom.receiptList.innerHTML = `<li class="is-empty">${escapeHtml(pricing.estimate_reason || "Цей виріб потребує індивідуального прорахунку.")}</li>`;
      if (dom.receiptMode) dom.receiptMode.textContent = STATE.mode === "brand" ? "B2B" : "B2C";
      if (dom.receiptHint) dom.receiptHint.textContent = "Натисніть «Надіслати менеджеру» — підготуємо точну ціну.";
      return;
    }
    dom.receiptList.innerHTML = pricing.breakdown.map((row) => `
      <li><span>${escapeHtml(row.label)}</span><strong>${formatPrice(row.value)}</strong></li>
    `).join("");
    const qty = STATE.order.quantity || 1;
    const totalText = qty > 1
      ? `${formatPrice(pricing.final_total)} <small>· ${formatPrice(pricing.unit_total)}/шт × ${qty}${pricing.gift_price ? " + подарунок" : ""}</small>`
      : `${formatPrice(pricing.final_total)}`;
    dom.receiptTotal.innerHTML = totalText;
    if (dom.receiptMode) dom.receiptMode.textContent = STATE.mode === "brand" ? "B2B · опт" : "B2C · роздріб";
    if (dom.receiptHint) {
      const hints = [];
      if (pricing.b2b_discount_per_unit > 0) hints.push(`B2B: -${pricing.b2b_discount_per_unit} грн/шт`);
      if (STATE.order.gift_enabled) hints.push("Подарунок включено");
      hints.push("Ціна оновлюється в реальному часі.");
      dom.receiptHint.textContent = hints.join(" · ");
    }
  }

  function updateFinalActionsAvailability() {
    const ready = canAdvance("contact");
    const pricing = computePricing();
    const cartReady = ready && STATE.product.type !== "customer_garment" && !pricing.estimate_required;
    if (dom.addToCartBtn) {
      dom.addToCartBtn.disabled = !cartReady;
      dom.addToCartBtn.classList.toggle("is-disabled", !cartReady);
    }
    if (dom.submitLeadBtn) {
      dom.submitLeadBtn.disabled = !ready;
      dom.submitLeadBtn.classList.toggle("is-disabled", !ready);
    }
    if (dom.cartActionHint) {
      dom.cartActionHint.textContent = cartReady
        ? `${formatPrice(pricing.final_total)} · додамо в кошик зі снимком конфігурації`
        : (pricing.estimate_required ? "Цей виріб потребує менеджерського прорахунку" : "Заповніть всі кроки, щоб додати в кошик");
    }
    if (dom.leadActionHint) {
      dom.leadActionHint.textContent = ready
        ? "Бот відправить заявку в Telegram"
        : "Заповніть контакт, щоб менеджер міг відповісти";
    }
  }

  // ── Final actions ───────────────────────────────────────────
  function bindFinalActions() {
    dom.addToCartBtn?.addEventListener("click", handleAddToCart);
    dom.submitLeadBtn?.addEventListener("click", (event) => {
      event.preventDefault();
      handleSubmitLead();
    });
    dom.form?.addEventListener("submit", (event) => {
      event.preventDefault();
      handleSubmitLead();
    });
    dom.safeExitBtn?.addEventListener("click", handleSafeExit);
  }

  function buildSnapshot(submissionType) {
    return {
      version: 2,
      submission_type: submissionType,
      quick_start_mode: "start_blank",
      mode: STATE.mode || "personal",
      starter_style: "",
      product: { ...STATE.product },
      print: {
        zones: [...STATE.print.zones],
        add_ons: [...STATE.print.add_ons],
        placement_note: STATE.print.placement_note || "",
        zone_options: buildZoneOptionsSnapshot(),
      },
      artwork: { ...STATE.artwork, files: serializeFiles() },
      order: {
        quantity: STATE.order.quantity || 0,
        size_mode: STATE.order.size_mode || "single",
        sizes_note: STATE.order.sizes_note || "",
        size_breakdown: { ...STATE.order.size_breakdown },
        gift: { enabled: !!STATE.order.gift_enabled, text: STATE.order.gift_text || "" },
      },
      contact: { ...STATE.contact },
      notes: { ...STATE.notes },
      pricing: computePricing(),
      ui: { current_step: STATE.ui.current_step },
    };
  }

  function serializeFiles() {
    const out = [];
    collectOrderedFiles().forEach(({ zone, file }, index) => {
      out.push({
        name: file.name,
        zone,
        status: STATE.artwork.triage_status || "needs-review",
        role: "design",
        file_index: index,
      });
    });
    return out;
  }

  function buildPlacementSpecs(snapshot) {
    const specs = [];
    const zoneOptions = snapshot.print?.zone_options || {};
    const files = snapshot.artwork?.files || [];
    (snapshot.print?.zones || []).forEach((zone, zoneIndex) => {
      const baseSpec = {
        zone,
        label: (CONFIG.zone_labels && CONFIG.zone_labels[zone]) || zone,
        variant: zoneIndex === 0 && (zone === "front" || zone === "back") ? "standard" : "estimate",
        is_free: zoneIndex === 0 && (zone === "front" || zone === "back"),
        format: zone === "front" || zone === "back" ? "standard" : "custom",
        size: zone === "front" || zone === "back" ? "standard" : "manager_review",
      };
      const options = zoneOptions[zone] || {};
      if (zone === "front" && options.size_preset) {
        baseSpec.size_preset = options.size_preset;
      }
      if (options.scene_preview) {
        baseSpec.scene_preview = options.scene_preview;
      }

      const zoneFiles = files.filter((item) => item.zone === zone);
      if (!zoneFiles.length) {
        specs.push({ ...baseSpec, file_index: zoneIndex, attachment_role: "design" });
        return;
      }
      zoneFiles.forEach((file, fileIndex) => {
        specs.push({
          ...baseSpec,
          file_index: typeof file.file_index === "number" ? file.file_index : fileIndex,
          attachment_role: file.role === "reference" ? "reference" : "design",
        });
      });
    });
    return specs;
  }

  function buildFormData(submissionType) {
    const fd = new FormData();
    const snap = buildSnapshot(submissionType);
    const pricing = snap.pricing || computePricing();
    fd.append("placement_specs_json", JSON.stringify(buildPlacementSpecs(snap)));
    fd.append("pricing_snapshot_json", JSON.stringify(pricing));
    fd.append("config_draft_json", JSON.stringify(snap));

    fd.append("service_kind", STATE.artwork.service_kind || "design");
    fd.append("product_type", STATE.product.type || "hoodie");
    (STATE.print.zones || []).forEach((z) => fd.append("placements", z));
    fd.append("placement_note", STATE.print.placement_note || "");
    fd.append("quantity", String(STATE.order.quantity || 1));
    fd.append("size_mode", STATE.order.size_mode || "single");
    fd.append("sizes_note", STATE.order.sizes_note || "");
    fd.append("client_kind", STATE.mode || "personal");
    fd.append("business_kind", STATE.mode === "brand" ? "branding" : "");
    fd.append("brand_name", STATE.notes.brand_name || "");
    fd.append("fit", STATE.product.fit || "");
    fd.append("fabric", STATE.product.fabric || "");
    fd.append("color_choice", STATE.product.color || "");
    fd.append("garment_note", STATE.notes.garment_note || "");
    fd.append("file_triage_status", STATE.artwork.triage_status || "needs-review");
    fd.append("exit_step", STATE.ui.current_step || "contact");
    fd.append("name", STATE.contact.name || "");
    fd.append("contact_channel", STATE.contact.channel || "");
    fd.append("contact_value", STATE.contact.value || "");
    fd.append("brief", STATE.notes.brief || "");

    collectOrderedFiles().forEach(({ file }) => {
      fd.append("files", file);
    });
    return fd;
  }

  async function handleSubmitLead() {
    if (!canAdvance("contact")) {
      showStatus("Заповніть імʼя, канал звʼязку і контакт.", "error");
      return;
    }
    const url = CONFIG.submit_url;
    if (!url) return;
    setBusy(true);
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "X-CSRFToken": getCsrfToken(), "X-Requested-With": "XMLHttpRequest" },
        body: buildFormData("lead"),
      });
      const data = await safeJson(response);
      if (!response.ok) {
        const msg = data?.errors ? formatErrors(data.errors) : "Не вдалося надіслати заявку. Спробуйте ще раз.";
        showStatus(msg, "error");
        return;
      }
      clearDraft();
      const number = data?.lead_number ? ` №${data.lead_number}` : "";
      showStatus(`Дякуємо! Заявка${number} вже у менеджера.`, "success");
    } catch (error) {
      console.error("[custom-print v2] submit lead failed", error);
      showStatus("Сервер тимчасово недоступний. Спробуйте через кілька хвилин.", "error");
    } finally {
      setBusy(false);
    }
  }

  async function handleAddToCart() {
    if (!canAdvance("contact")) {
      showStatus("Заповніть всі кроки, перш ніж додавати в кошик.", "error");
      return;
    }
    const pricing = computePricing();
    if (pricing.estimate_required) {
      showStatus("Цей виріб потребує менеджерського прорахунку. Натисніть «Надіслати менеджеру».", "warning");
      return;
    }
    const url = CONFIG.add_to_cart_url;
    if (!url) {
      showStatus("Кошик тимчасово недоступний. Скористайтесь Telegram-кнопкою.", "error");
      return;
    }
    setBusy(true);
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "X-CSRFToken": getCsrfToken(), "X-Requested-With": "XMLHttpRequest" },
        body: buildFormData("cart"),
      });
      const data = await safeJson(response);
      if (!response.ok || !data?.ok) {
        const msg = data?.error || "Не вдалося додати в кошик. Спробуйте ще раз.";
        showStatus(msg, "error");
        return;
      }
      clearDraft();
      showStatus(`Додано в кошик · ${formatPrice(pricing.final_total)}. Перейти до оформлення?`, "success");
      if (data.cart_url) {
        setTimeout(() => { window.location.href = data.cart_url; }, 1200);
      }
    } catch (error) {
      console.error("[custom-print v2] add to cart failed", error);
      showStatus("Не вдалося додати в кошик. Спробуйте ще раз.", "error");
    } finally {
      setBusy(false);
    }
  }

  async function handleSafeExit() {
    const url = CONFIG.safe_exit_url;
    if (!url) {
      window.open(CONFIG.telegram_manager_url || "https://t.me/twocomms", "_blank");
      return;
    }
    try {
      const snap = buildSnapshot("safe_exit");
      const response = await fetch(url, {
        method: "POST",
        headers: { "X-CSRFToken": getCsrfToken(), "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest" },
        body: JSON.stringify(snap),
      });
      const data = await safeJson(response);
      const link = data?.manager_url || CONFIG.telegram_manager_url || "https://t.me/twocomms";
      window.open(link, "_blank");
    } catch (error) {
      console.error("[custom-print v2] safe exit failed", error);
      window.open(CONFIG.telegram_manager_url || "https://t.me/twocomms", "_blank");
    }
  }

  function setBusy(busy) {
    [dom.addToCartBtn, dom.submitLeadBtn].forEach((btn) => {
      if (!btn) return;
      btn.classList.toggle("is-busy", busy);
      if (busy) {
        btn.dataset.wasDisabled = btn.disabled ? "1" : "0";
        btn.disabled = true;
      } else {
        btn.disabled = btn.dataset.wasDisabled === "1";
        delete btn.dataset.wasDisabled;
      }
    });
    if (!busy) updateFinalActionsAvailability();
  }

  function showStatus(message, kind) {
    if (!dom.statusBox) return;
    dom.statusBox.textContent = message;
    dom.statusBox.classList.remove("is-success", "is-error", "is-warning");
    if (kind === "success") dom.statusBox.classList.add("is-success");
    if (kind === "error") dom.statusBox.classList.add("is-error");
    if (kind === "warning") dom.statusBox.classList.add("is-warning");
  }

  // ── Helpers ─────────────────────────────────────────────────
  function getCsrfToken() {
    const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  async function safeJson(response) {
    try { return await response.json(); } catch { return null; }
  }

  function formatErrors(errors) {
    const lines = [];
    Object.entries(errors).forEach(([field, list]) => {
      (list || []).forEach((m) => lines.push(`${field}: ${m}`));
    });
    return lines.join("\n");
  }

  function formatPrice(value) {
    if (value === null || value === undefined) return "—";
    return `${Math.round(value).toLocaleString("uk-UA")} грн`;
  }

  function formatBytes(bytes) {
    if (!bytes && bytes !== 0) return "";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }

  function escapeHtml(value) {
    if (!value) return "";
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function mixHex(base, target, weight) {
    const clampWeight = Math.min(Math.max(weight, 0), 1);
    const parse = (hex) => {
      const normalized = String(hex || "").replace("#", "");
      const value = normalized.length === 3
        ? normalized.split("").map((char) => char + char).join("")
        : normalized.padEnd(6, "0").slice(0, 6);
      return {
        r: parseInt(value.slice(0, 2), 16),
        g: parseInt(value.slice(2, 4), 16),
        b: parseInt(value.slice(4, 6), 16),
      };
    };
    const a = parse(base);
    const b = parse(target);
    const mix = (left, right) => Math.round(left + (right - left) * clampWeight);
    return `rgb(${mix(a.r, b.r)}, ${mix(a.g, b.g)}, ${mix(a.b, b.b)})`;
  }

  // ── Draft ───────────────────────────────────────────────────
  function persistDraft() {
    try {
      const draft = {
        v: 2,
        ts: Date.now(),
        mode: STATE.mode,
        product: STATE.product,
        print: STATE.print,
        artwork: STATE.artwork,
        order: STATE.order,
        notes: STATE.notes,
        contact: STATE.contact,
        ui: {
          current_step: STATE.ui.current_step,
          done_steps: Array.from(STATE.ui.done_steps),
          stage_view: STATE.ui.stage_view,
        },
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(draft));
    } catch (err) {
      // ignore quota
    }
  }

  function loadDraft() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const draft = JSON.parse(raw);
      if (!draft || draft.v !== 2) return;
      if (draft.mode) STATE.mode = draft.mode;
      if (draft.product) Object.assign(STATE.product, draft.product);
      if (draft.print) Object.assign(STATE.print, draft.print);
      if (draft.artwork) Object.assign(STATE.artwork, draft.artwork);
      if (draft.order) Object.assign(STATE.order, draft.order);
      if (draft.notes) Object.assign(STATE.notes, draft.notes);
      if (draft.contact) Object.assign(STATE.contact, draft.contact);
      if (draft.ui) {
        STATE.ui.current_step = draft.ui.current_step || "mode";
        STATE.ui.done_steps = new Set(draft.ui.done_steps || []);
        STATE.ui.stage_view = draft.ui.stage_view || "front";
      }
      normalizeClientState();
      // Restore inputs
      if (dom.qtyInput && STATE.order.quantity) dom.qtyInput.value = STATE.order.quantity;
      if (dom.placementNoteInput) dom.placementNoteInput.value = STATE.print.placement_note || "";
      if (dom.briefInput) dom.briefInput.value = STATE.notes.brief || "";
      if (dom.nameInput) dom.nameInput.value = STATE.contact.name || "";
      if (dom.contactValueInput) dom.contactValueInput.value = STATE.contact.value || "";
      if (dom.brandNameInput) dom.brandNameInput.value = STATE.notes.brand_name || "";
      if (dom.giftTextInput) dom.giftTextInput.value = STATE.order.gift_text || "";
      if (dom.giftToggle) dom.giftToggle.classList.toggle("is-active", !!STATE.order.gift_enabled);
      if (dom.giftTextWrap) dom.giftTextWrap.hidden = !STATE.order.gift_enabled;
      if (dom.garmentNoteInput) dom.garmentNoteInput.value = STATE.notes.garment_note || "";
      if (dom.sizesNoteInput) dom.sizesNoteInput.value = STATE.order.sizes_note || "";
      // Re-render dependent UI
      renderFitChips();
      renderFabricChips();
      renderColorChips();
      renderZoneChipsForCurrent();
      renderFrontSizeOptions();
      renderAddons();
      renderArtworkActiveState();
      renderContactChannelChipsActive();
      renderSizing();
      renderDropzones();
    } catch (err) {
      console.warn("[custom-print v2] draft load failed", err);
    }
  }

  function clearDraft() {
    try { localStorage.removeItem(STORAGE_KEY); } catch (_) { /* ignore */ }
  }
})();
