import re

# 1. Update JS to remove repeated fabric text and add logic for fleece toggle group
js_path = "twocomms/twocomms_django_theme/static/js/custom-print-configurator.js"
with open(js_path, "r") as f:
    orig_js = f.read()

# Fix repeated text in fabric chips
def remove_small_tier(m):
    return """
        <span class="cp-fabric-chip-title">
          <strong>${displayLabel}</strong>
        </span>
"""
orig_js = re.sub(r'\s*<span class="cp-fabric-chip-title">\s*<strong>\$\{displayLabel\}</strong>\s*<small>\$\{escapeHtml\(tierLabel\)\}</small>\s*</span>', remove_small_tier, orig_js)


# Add Fleece toggles rendering logic
def inject_fleece_logic(m):
    return """
    visibleAddons.forEach((a) => {
      // Special rendering if it's the Fleece group
      if (a.group === "fleece") {
         let fleeceWrap = dom.addonsList.querySelector(".cp-fleece-toggle");
         if (!fleeceWrap) {
             fleeceWrap = document.createElement("div");
             fleeceWrap.className = "cp-fleece-toggle";
             fleeceWrap.innerHTML = `<span class="cp-fleece-title">Утеплення (Фліс)</span><div class="cp-fleece-options"></div>`;
             dom.addonsList.appendChild(fleeceWrap);
         }
         
         const isActive = STATE.print.add_ons.includes(a.value);
         const btn = document.createElement("button");
         btn.type = "button";
         btn.className = `cp-fleece-btn cp-fleece-btn--${a.value}`;
         if (isActive) btn.classList.add("is-active");
         btn.innerHTML = `<span class="cp-addon-card-icon">${addonSvg(a.icon || "fleece")}</span> <span class="cp-fleece-btn-label">${escapeHtml(a.label)}</span>`;
         btn.addEventListener("click", () => {
             // Exclusive toggle logic
             STATE.print.add_ons = STATE.print.add_ons.filter(item => {
                 const currentAddon = addons.find(x => x.value === item);
                 return !(currentAddon && currentAddon.group === "fleece");
             });
             STATE.print.add_ons.push(a.value);
             renderAddons();
             refreshAll();
             persistDraft();
         });
         fleeceWrap.querySelector(".cp-fleece-options").appendChild(btn);
         return; // skip standard rendering
      }
"""
orig_js = re.sub(r'\s*visibleAddons\.forEach\(\(a\) => \{', inject_fleece_logic, orig_js)

# Add SVG icons for Fleece
def add_fleece_svgs(m):
    return """  function addonSvg(name) {
    if (name === "lacing") return lacingSvg();
    if (name === "ribbed_neck") return ribbedNeckSvg();
    if (name === "twill_tape") return twillTapeSvg();
    if (name === "fleece") return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11.667 2c.084 1.161-.269 3.013-.865 3.99-1.393 2.278-4.47 2.016-5.83.69-.971-.947-1.39-2.28-1.554-3.593A17.437 17.437 0 0111.667 2zM15.111 6c.036 1.488-.135 2.871-.525 4.14-1.127 3.65-4.7 4.29-6.9 2-1.636-1.7-2.126-4.63-.5-8.22M20 15c-3 3-5 5-10 6-3-.6-5.74-3.13-6-6-1-11 5-16 11-10 0 0 7.8 7.2 5 10z"/></svg>`;
    if (name === "no_fleece") return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v20 M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" /></svg>`;
    return defaultDotSvg();
"""
orig_js = re.sub(r'  function addonSvg\(name\) \{.*?\return defaultDotSvg\(\);\n', add_fleece_svgs, orig_js, flags=re.DOTALL)


# Ensure default fleece choice if none is set
def init_fleece(m):
    return m.group(0) + """
    // Initialize default fleece for hoodies
    if (['hoodie', 'zip_hoodie'].includes(STATE.product.type)) {
       const hasFleeceGroup = STATE.print.add_ons.some(v => ['fleece', 'no_fleece'].includes(v));
       if (!hasFleeceGroup) STATE.print.add_ons.push('fleece');
    }
"""
orig_js = re.sub(r'STATE\.print\.add_ons = \(STATE\.print\.add_ons \|\| \[\]\).*?\.filter\(.*?;\n', init_fleece, orig_js)


with open(js_path, "w") as f:
    f.write(orig_js)

# 2. Add python add_ons
py_path = "twocomms/storefront/custom_print_config.py"
with open(py_path, "r") as f:
    orig_py = f.read()

fleece_addons = """            {
                "value": "fleece",
                "label": "З флісом",
                "price_delta": 0,
                "icon": "fleece",
                "group": "fleece"
            },
            {
                "value": "no_fleece",
                "label": "Без флісу",
                "price_delta": 0,
                "icon": "no_fleece",
                "group": "fleece"
            },\n"""

# Inject into hoodie
orig_py = re.sub(r'("label": "Худі",.*?)(        "add_ons": \[\n)', r'\1\2' + fleece_addons, orig_py, flags=re.DOTALL)
# Inject into zip_hoodie
orig_py = re.sub(r'("label": "Зіп-Худі",.*?)(        "add_ons": \[\n)', r'\1\2' + fleece_addons, orig_py, flags=re.DOTALL)

with open(py_path, "w") as f:
    f.write(orig_py)

print("done")
