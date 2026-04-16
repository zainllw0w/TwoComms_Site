import re

path = "twocomms/twocomms_django_theme/static/js/custom-print-configurator.js"
with open(path, "r") as f:
    orig = f.read()

# 1. Inject fire icon for thermo label
def replace_fabric_chip(m):
    return """
      const tierLabel = fab.value === "premium" ? "Преміум" : fab.value === "thermo" ? "Термо" : "База";
      const fireSvg = `<svg class="cp-fire-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8.5 14.5A2.5 2.5 0 0011 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 11-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 002.5 2.5z"></path></svg>`;
      const displayLabel = fab.value === "thermo" ? `${escapeHtml(fab.label)} ${fireSvg}` : escapeHtml(fab.label);
      
      let btnContent = `
        <span class="cp-fabric-chip-title">
          <strong>${displayLabel}</strong>
          <small>${escapeHtml(tierLabel)}</small>
        </span>
"""
orig = re.sub(r'      const tierLabel = fab\.value === "premium" \? "Преміум" : fab\.value === "thermo" \? "Термо" : "База";\n      let btnContent = `\n        <span class="cp-fabric-chip-title">\n          <strong>\$\{escapeHtml\(fab\.label\)\}</strong>\n          <small>\$\{escapeHtml\(tierLabel\)\}</small>\n        </span>', replace_fabric_chip, orig)

# 2. Modify renderAddons to handle 'auto_include_condition'
def replace_addons(m):
    return """  function renderAddons() {
    if (!dom.addonsList) return;
    dom.addonsList.innerHTML = "";
    const cfg = getProductConfig();
    const addons = cfg && cfg.add_ons ? cfg.add_ons : [];
    
    // Filter addons: if auto-include condition exists, only show them if condition is met
    const visibleAddons = addons.filter(a => {
      if (a.auto_include_condition === "premium_or_oversize") {
        return (STATE.product.fabric === "premium" || STATE.product.fabric === "thermo" || STATE.product.fit === "oversize");
      }
      return true;
    });

    if (!visibleAddons.length) {
      if (dom.addonsWrap) dom.addonsWrap.hidden = true;
      return;
    }
    if (dom.addonsWrap) dom.addonsWrap.hidden = false;
    
    visibleAddons.forEach((a) => {
      const isAutoIncluded = a.auto_include_condition === "premium_or_oversize";
      const isActive = isAutoIncluded ? true : STATE.print.add_ons.includes(a.value);
      
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = `cp-addon-card cp-addon-card--${a.value}`;
      if (isActive) btn.classList.add("is-active");
      if (isAutoIncluded) btn.classList.add("is-auto-included"); // new class to lock
      btn.dataset.choiceValue = a.value;
      btn.dataset.priceModifier = String(a.price_delta || 0);
      btn.innerHTML = `
        <span class="cp-addon-card-icon" aria-hidden="true">${addonSvg(a.icon)}</span>
        <span class="cp-addon-card-body">
          <strong>${escapeHtml(a.label)}</strong>
          <span class="cp-addon-card-badge">${escapeHtml(a.badge || "")}</span>
          <span class="cp-addon-card-hint">${escapeHtml(a.hint || "")}</span>
        </span>
      `;
      btn.addEventListener("click", () => {
        if (isAutoIncluded) return; // Prevent toggling included items
        const i = STATE.print.add_ons.indexOf(a.value);
        if (i >= 0) STATE.print.add_ons.splice(i, 1);
        else STATE.print.add_ons.push(a.value);
        renderAddons();
        refreshAll();
        persistDraft();
      });
      dom.addonsList.appendChild(btn);
    });
  }"""
orig = re.sub(r'  function renderAddons\(\) \{.*?(?=  function addonSvg)', replace_addons, orig, flags=re.DOTALL)

# 3. Add ribbed_neck and twill_tape SVGs to addonSvg
def replace_addons_svg(m):
    return """  function addonSvg(name) {
    if (name === "lacing") return lacingSvg();
    if (name === "ribbed_neck") return ribbedNeckSvg();
    if (name === "twill_tape") return twillTapeSvg();
    return defaultDotSvg();
  }

  function ribbedNeckSvg() {
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 6C5 6 9 10 12 10C15 10 19 6 19 6C19 6 22 17 22 17H2C2 17 5 6 5 6Z"/><path d="M9 10V17M15 10V17M12 10V17"/></svg>`;
  }

  function twillTapeSvg() {
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12L20 12M4 8L20 8M4 16L20 16" stroke-dasharray="2 4"/></svg>`;
  }"""
orig = re.sub(r'  function addonSvg\(name\) \{.*?return defaultDotSvg\(\);\n  \}', replace_addons_svg, orig, flags=re.DOTALL)

with open(path, "w") as f:
    f.write(orig)

print("done")
