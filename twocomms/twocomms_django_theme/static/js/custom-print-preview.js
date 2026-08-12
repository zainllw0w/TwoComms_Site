(function (global) {
  function formatCm(valueMm) {
    return (valueMm / 10).toLocaleString(document.documentElement.lang || "uk-UA", {
      maximumFractionDigits: 1,
    });
  }

  function profileKey(state) {
    const type = state.product.type || "hoodie";
    if (type === "longsleeve") return "longsleeve:regular";
    const fit = state.product.fit || "regular";
    return `${type}:${fit}`;
  }

  const COLOR_ALIASES = {
    black: "black",
    beige: "beige",
    coyote: "beige",
    pink: "pink",
    thermo_pink: "pink",
    white: "white",
  };

  const FORMAT_SCALES = {
    A6: 0.28,
    A5: 0.4,
    A4: 0.58,
    A3: 0.74,
    "A3+": 0.86,
    "A6+": 0.36,
  };

  function viewForPlacement(placement = {}) {
    const key = String(placement.placement_key || "");
    if (key === "back" || key === "hem_back") return "back";
    return "front";
  }

  function requirementsForPlacement(placement = {}) {
    return { requiresFile: !(placement.zone === "hem" && placement.mode === "text") };
  }

  function boxForFormat(format) {
    return { format, scale: FORMAT_SCALES[format] || FORMAT_SCALES.A4 };
  }

  function resolveGarmentRender(assets, requestedProfile, selectedColor) {
    const profile = assets?.[requestedProfile] || assets?.["tshirt:regular"] || {};
    const requestedRenderColor = COLOR_ALIASES[selectedColor] || selectedColor || "black";
    const previewColor = profile[requestedRenderColor]
      ? requestedRenderColor
      : (["white", "black"].find((color) => profile[color]) || Object.keys(profile)[0]);
    if (!previewColor || !profile[previewColor]) return null;
    return {
      selectedColor: selectedColor || "black",
      previewColor,
      fallbackUsed: previewColor !== requestedRenderColor,
      sources: profile[previewColor],
    };
  }

  function resolveAsset(config, state) {
    const profiles = config.custom_ref_preview_assets || {};
    const requestedProfile = profileKey(state);
    const render = resolveGarmentRender(profiles, requestedProfile, state.product.color);
    if (!render) return null;
    const view = state.ui.stage_view === "back" ? "back" : "front";
    return {
      ...(render.sources[view] || render.sources.front),
      selectedColor: render.selectedColor,
      color: render.previewColor,
      fallbackUsed: render.fallbackUsed,
      profile: requestedProfile,
      view,
    };
  }

  function computeZoneBox(dimensions, calibration, canvas = { width: 1200, height: 1400 }) {
    const bodyWidth = calibration.zones.body.width;
    const width = (dimensions.width_mm / calibration.garment_width_mm) * bodyWidth;
    const height = (dimensions.height_mm / calibration.garment_width_mm) * bodyWidth * (canvas.width / canvas.height);
    return { width, height, dimensions };
  }

  // Render state is deliberately kept outside the DOM.  The configurator can
  // request a refresh for unrelated controls, so the preview should only
  // touch the nodes whose source or overlay actually changed.
  function stableSignature(value) {
    const renderPlan = global.CustomPrintRenderPlan;
    if (typeof renderPlan?.stable === "function") return renderPlan.stable(value);
    if (value == null) return "";
    if (Array.isArray(value)) return `[${value.map(stableSignature).join(",")}]`;
    if (typeof value === "object") {
      return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableSignature(value[key])}`).join(",")}}`;
    }
    return JSON.stringify(value);
  }

  function create({ root, config, getState }) {
    const previewNodes = Array.from(root.querySelectorAll("[data-png-preview]"));
    const warmedAssets = new Set();
    const renderMeta = new WeakMap();

    function appendPreload(url) {
      if (!url || warmedAssets.has(url)) return;
      warmedAssets.add(url);
      const preload = document.createElement("link");
      preload.rel = "preload";
      preload.as = "image";
      preload.type = "image/avif";
      preload.href = url;
      document.head.appendChild(preload);
    }

    function warmCurrentProfile(state) {
      const profiles = config.custom_ref_preview_assets || {};
      const render = resolveGarmentRender(profiles, profileKey(state), state.product.color);
      const variant = render?.sources;
      const view = state.ui.stage_view === "back" ? "back" : "front";
      // Warm the source that resolveAsset will actually display.  This also
      // covers a declared front fallback when an incomplete profile lacks a
      // back file.
      const currentAsset = resolveAsset(config, state);
      appendPreload(currentAsset?.avif);
      ["front", "back"].forEach((side) => {
        const sources = variant?.[side];
        if (!sources?.avif) return;
        if (side === view) {
          // The source currently visible must be available immediately.
          appendPreload(sources.avif);
        }
      });
    }

    function zoneBox(format, calibration) {
      const dimensions = config.format_dimensions?.[format];
      if (!dimensions) return null;
      return computeZoneBox(dimensions, calibration, calibration.canvas);
    }

    function appendZone(container, placement, calibration, view) {
      if (placement.zone === "custom") return;
      if (viewForPlacement(placement) !== view) return;
      const isBody = placement.zone === "front" || placement.zone === "back";
      if (isBody && placement.zone !== view) return;
      if (placement.zone === "sleeve" && view !== "front") return;
      const format = placement.zone === "sleeve" || placement.zone === "shoulder"
        ? "A6"
        : (placement.mode === "text" ? "TEXT" : (placement.size_preset || placement.mode || "A4"));
      if (placement.zone === "shoulder") {
        const side = placement.side === "right" ? "right" : "left";
        const marker = document.createElement("div");
        marker.className = `cp-preview-zone cp-preview-zone--shoulder cp-preview-zone--shoulder-${side}`;
        marker.innerHTML = `<i class="cp-preview-zone-leader" aria-hidden="true"></i><strong>A6</strong><span>${side === "left" ? "L" : "R"}</span>`;
        container.appendChild(marker);
        return;
      }
      if (format === "TEXT") {
        const marker = document.createElement("div");
        marker.className = "cp-preview-zone cp-preview-zone--hem cp-preview-zone--text";
        marker.innerHTML = `<strong>TEXT</strong><span>${String(placement.text || "").slice(0, 24)}</span>`;
        container.appendChild(marker);
        return;
      }
      const box = zoneBox(format, calibration);
      if (!box) return;
      if (placement.zone === "hem") {
        const marker = document.createElement("div");
        marker.className = "cp-preview-zone cp-preview-zone--hem";
        marker.style.setProperty("--cp-hem-width", `${Math.min(Math.max(box.width, 12), format === "A6+" ? 30 : 20)}%`);
        marker.innerHTML = `<strong>${format}</strong><span>${formatCm(box.dimensions.width_mm)} × ${formatCm(box.dimensions.height_mm)} см</span>`;
        container.appendChild(marker);
        return;
      }
      const anchorKey = placement.zone === "sleeve" || placement.zone === "shoulder"
        ? `sleeve_${placement.side || "left"}`
        : placement.zone === "hem" ? view : placement.zone;
      const anchor = calibration.zones[anchorKey] || calibration.zones[view];
      if (!anchor) return;

      const zone = document.createElement("div");
      zone.className = `cp-preview-zone cp-preview-zone--${placement.zone}`;
      zone.style.left = `${anchor.x}%`;
      zone.style.top = `${anchor.y}%`;
      zone.style.width = `${box.width}%`;
      zone.style.height = `${box.height}%`;
      if (anchor.rotate) zone.style.rotate = `${anchor.rotate}deg`;
      zone.innerHTML = `<strong>${format}</strong><span>${formatCm(box.dimensions.width_mm)} × ${formatCm(box.dimensions.height_mm)} см</span>`;
      container.appendChild(zone);
    }

    function expandedPlacements(state) {
      const result = [];
      for (const zone of state.print.zones || []) {
        const options = state.print.zone_options?.[zone] || {};
        if (zone === "sleeve") {
          if (options.left_enabled !== false) result.push({ zone, side: "left" });
          if (options.right_enabled) result.push({ zone, side: "right" });
        } else if (zone === "shoulder") {
          if (options.left_enabled) result.push({ zone, side: "left", placement_key: "shoulder_left", size_preset: "A6" });
          if (options.right_enabled) result.push({ zone, side: "right", placement_key: "shoulder_right", size_preset: "A6" });
        } else if (zone === "hem" && options.side) {
          result.push({
            zone,
            side: options.side,
            placement_key: `hem_${options.side}`,
            mode: options.mode || "A6",
            size_preset: options.mode === "text" ? "" : (options.mode || "A6"),
            text: options.text || "",
          });
        } else {
          result.push({ zone, size_preset: options.size_preset || "A4" });
        }
      }
      return result;
    }

    function render() {
      const state = getState();
      const key = profileKey(state);
      const assets = config.preview_assets?.[key] || config.preview_assets?.["hoodie:regular"];
      const calibration = config.preview_calibration?.[key] || config.preview_calibration?.["hoodie:regular"];
      const asset = resolveAsset(config, state);
      if (!assets || !calibration || !asset) return;
      const view = state.ui.stage_view === "back" ? "back" : "front";
      warmCurrentProfile(state);
      const productConfig = config.products?.[state.product.type] || {};
      const selectedFabric = (productConfig.fabrics?.[state.product.fit] || []).find((item) => item.value === state.product.fabric);
      const palette = selectedFabric?.colors || productConfig.fit_colors?.[state.product.fit] || productConfig.colors || [];
      const colorLabel = palette.find((item) => item.value === state.product.color)?.label || asset.color;
      const placements = expandedPlacements(state);
      const alt = state.product.type ? `${productConfig.label || state.product.type} · ${colorLabel} · ${view}` : "";
      const assetSignature = stableSignature({
        avif: asset.avif || "",
        webp: asset.webp || "",
        profile: asset.profile,
        view: asset.view,
        color: asset.color,
        selectedColor: asset.selectedColor,
        alt,
      });
      const assetSourceSignature = stableSignature({ avif: asset.avif || "", webp: asset.webp || "" });
      const overlaySignature = stableSignature({
        view,
        profile: asset.profile,
        placements,
        calibration,
        formatDimensions: config.format_dimensions || {},
      });
      state.ui.preview_render = {
        selected_color: asset.selectedColor,
        preview_color: asset.color,
        fallback_used: asset.fallbackUsed,
        profile: asset.profile,
      };

      previewNodes.forEach((preview) => {
        const garment = preview.querySelector("[data-preview-garment]");
        const avif = preview.querySelector("[data-preview-avif]");
        const webp = preview.querySelector("[data-preview-webp]");
        const lacing = preview.querySelector("[data-preview-lacing]");
        const zones = preview.querySelector("[data-preview-zones]");
        const previous = renderMeta.get(preview);
        const assetChanged = !previous || previous.assetSourceSignature !== assetSourceSignature;
        const assetDetailsChanged = !previous || previous.assetSignature !== assetSignature;
        const overlayChanged = !previous || previous.overlaySignature !== overlaySignature;

        if (assetChanged) {
          preview.classList.remove("is-refreshing");
          const scheduleFrame = global.requestAnimationFrame || ((callback) => global.setTimeout?.(callback, 0));
          scheduleFrame?.(() => preview.classList.add("is-refreshing"));
        }
        if (assetDetailsChanged && garment) {
          if (garment.getAttribute("src") !== (asset.webp || "")) garment.src = asset.webp || "";
          if (garment.alt !== alt) garment.alt = alt;
        }
        if (assetDetailsChanged && avif && avif.getAttribute("srcset") !== (asset.avif || "")) {
          avif.srcset = asset.avif || "";
        }
        if (assetDetailsChanged && webp && webp.getAttribute("srcset") !== (asset.webp || "")) {
          webp.srcset = asset.webp || "";
        }
        if (lacing && !lacing.hidden) {
          lacing.hidden = true;
        }
        if (overlayChanged && zones) {
          zones.replaceChildren();
          placements.forEach((placement) => appendZone(zones, placement, calibration, view));
        }
        renderMeta.set(preview, { assetSignature, assetSourceSignature, overlaySignature });
      });
    }

    function bindPreviewMotion(preview) {
      const motionQuery = globalThis.matchMedia?.("(prefers-reduced-motion: reduce)") || null;
      if (motionQuery?.matches) return;
      preview.addEventListener("pointermove", (event) => {
        const rect = preview.getBoundingClientRect();
        const x = ((event.clientX - rect.left) / Math.max(rect.width, 1) - 0.5) * 2;
        const y = ((event.clientY - rect.top) / Math.max(rect.height, 1) - 0.5) * 2;
        preview.style.setProperty("--cp-preview-tilt-x", `${(y * -1.8).toFixed(2)}deg`);
        preview.style.setProperty("--cp-preview-tilt-y", `${(x * 2.4).toFixed(2)}deg`);
      });
      preview.addEventListener("pointerleave", () => {
        preview.style.removeProperty("--cp-preview-tilt-x");
        preview.style.removeProperty("--cp-preview-tilt-y");
      });
    }

    previewNodes.forEach(bindPreviewMotion);

    return { render };
  }

  global.CustomPrintPreview = { boxForFormat, create, computeZoneBox, requirementsForPlacement, resolveGarmentRender, viewForPlacement };
})(globalThis);
