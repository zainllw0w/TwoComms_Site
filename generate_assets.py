import os

SVG_DIR = "twocomms/dtf/static/dtf/svg"
CSS_DIR = "twocomms/dtf/static/dtf/css/components"
os.makedirs(SVG_DIR, exist_ok=True)
os.makedirs(CSS_DIR, exist_ok=True)

# Common attributes for all SVGs
# viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="1.8", stroke-linecap="round", stroke-linejoin="round"
base_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">\n  {content}\n</svg>'

icons = {
    "icon-file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>\n  <polyline points="14 2 14 8 20 8"></polyline>\n  <line x1="16" y1="13" x2="8" y2="13"></line>\n  <line x1="16" y1="17" x2="8" y2="17"></line>\n  <polyline points="10 9 9 9 8 9"></polyline>',
    "icon-scan": '<path d="M3 7V5a2 2 0 0 1 2-2h2"></path>\n  <path d="M17 3h2a2 2 0 0 1 2 2v2"></path>\n  <path d="M21 17v2a2 2 0 0 1-2 2h-2"></path>\n  <path d="M7 21H5a2 2 0 0 1-2-2v-2"></path>\n  <line x1="4" y1="12" x2="20" y2="12" class="scan-line" stroke="currentColor"></line>',
    "icon-check": '<polyline points="20 6 9 17 4 12" class="icon-path"></polyline>',
    "icon-info": '<circle cx="12" cy="12" r="10"></circle>\n  <line x1="12" y1="16" x2="12" y2="12"></line>\n  <line x1="12" y1="8" x2="12.01" y2="8"></line>',
    "icon-warning": '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>\n  <line x1="12" y1="9" x2="12" y2="13"></line>\n  <line x1="12" y1="17" x2="12.01" y2="17"></line>',
    "icon-fix": '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path>',
    "icon-bulb": '<path d="M9 18h6"></path>\n  <path d="M10 22h4"></path>\n  <path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8c0 1.45.62 2.84 1.5 3.5.76.76 1.23 1.52 1.41 2.5"></path>\n  <line x1="12" y1="2" x2="12" y2="4"></line>',
    "icon-truck": '<rect x="1" y="3" width="15" height="13"></rect>\n  <polygon points="16 8 20 8 23 11 23 16 16 16 16 8"></polygon>\n  <circle cx="5.5" cy="18.5" r="2.5"></circle>\n  <circle cx="18.5" cy="18.5" r="2.5"></circle>',
    "icon-sheet60": '<path d="M6 3h12a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"></path>\n  <path d="M4 7h16"></path>\n  <path d="M4 17h16"></path>\n  <text x="12" y="13" text-anchor="middle" font-size="6" font-family="sans-serif" font-weight="600" stroke="none" fill="currentColor">60</text>',
    "icon-palette": '<circle cx="13.5" cy="6.5" r=".5" fill="currentColor"></circle>\n  <circle cx="17.5" cy="10.5" r=".5" fill="currentColor"></circle>\n  <circle cx="8.5" cy="7.5" r=".5" fill="currentColor"></circle>\n  <circle cx="6.5" cy="12.5" r=".5" fill="currentColor"></circle>\n  <path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z"></path>',
    "icon-telegram": '<line x1="22" y1="2" x2="11" y2="13"></line>\n  <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>',
    "icon-upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>\n  <polyline points="17 8 12 3 7 8"></polyline>\n  <line x1="12" y1="3" x2="12" y2="15"></line>',
    "icon-clock": '<circle cx="12" cy="12" r="10"></circle>\n  <polyline points="12 6 12 12 16 14"></polyline>',
    "icon-shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>\n  <polyline points="9 12 11 14 15 10"></polyline>',
    "icon-calculator": '<rect x="4" y="2" width="16" height="20" rx="2" ry="2"></rect>\n  <line x1="8" y1="6" x2="16" y2="6"></line>\n  <line x1="16" y1="14" x2="16" y2="14.01"></line>\n  <line x1="12" y1="14" x2="12" y2="14.01"></line>\n  <line x1="8" y1="14" x2="8" y2="14.01"></line>\n  <line x1="16" y1="18" x2="16" y2="18.01"></line>\n  <line x1="12" y1="18" x2="12" y2="18.01"></line>\n  <line x1="8" y1="18" x2="8" y2="18.01"></line>\n  <line x1="16" y1="10" x2="16" y2="10.01"></line>\n  <line x1="12" y1="10" x2="12" y2="10.01"></line>\n  <line x1="8" y1="10" x2="8" y2="10.01"></line>'
}

for name, content in icons.items():
    svg_path = os.path.join(SVG_DIR, f"{name}.svg")
    with open(svg_path, "w") as f:
        f.write(base_svg.format(content=content))

print("Created 15 SVGs in", SVG_DIR)

# Generate icons.css
icons_css = """/* Base icon styles & animations (dtf/static/dtf/css/components/icons.css) */
.dtf-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  color: inherit;
  flex-shrink: 0;
}
.dtf-icon svg {
  width: 100%;
  height: 100%;
}

@media (pointer: coarse) {
  .dtf-icon[role="button"],
  button .dtf-icon {
    padding: 2px;
  }
}

/* 1. check-draw */
.dtf-icon-check .icon-path {
  stroke-dasharray: 30;
  stroke-dashoffset: 30;
}
.dtf-icon-check.dtf-icon-animate .icon-path {
  animation: check-draw 0.35s ease-out forwards;
}
@keyframes check-draw {
  to { stroke-dashoffset: 0; }
}

/* 2. scan-line */
.dtf-icon-scan .scan-line {
  animation: scan-line 1.35s linear infinite;
}
@keyframes scan-line {
  0%   { transform: translateY(2px); opacity: 0.6; }
  100% { transform: translateY(20px); opacity: 0.2; }
}

/* 3. soft-glow */
.dtf-icon-bulb.dtf-icon-animate,
.dtf-icon-telegram.dtf-icon-animate {
  animation: soft-glow 0.4s ease-out;
}
@keyframes soft-glow {
  0%   { filter: drop-shadow(0 0 0 transparent); }
  50%  { filter: drop-shadow(0 0 6px var(--dtf-accent, #3b82f6)); }
  100% { filter: drop-shadow(0 0 0 transparent); }
}

/* 4. upload-bounce */
.dtf-icon-upload.dtf-icon-animate {
  animation: upload-bounce 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
}
@keyframes upload-bounce {
  0%   { transform: translateY(0); }
  40%  { transform: translateY(-6px); }
  100% { transform: translateY(0); }
}

/* 5. truck-slide */
.dtf-icon-truck.dtf-icon-animate {
  animation: truck-slide 0.6s ease-out;
}
@keyframes truck-slide {
  0%   { transform: translateX(-12px); opacity: 0; }
  100% { transform: translateX(0); opacity: 1; }
}

/* 6. pulse-ring */
.dtf-icon-shield.dtf-icon-animate {
  position: relative;
}
.dtf-icon-shield.dtf-icon-animate::after {
  content: '';
  position: absolute;
  inset: -4px;
  border: 2px solid var(--dtf-success, #22c55e);
  border-radius: 50%;
  animation: pulse-ring 0.6s ease-out forwards;
  opacity: 0;
}
@keyframes pulse-ring {
  0%   { transform: scale(0.8); opacity: 0.6; }
  100% { transform: scale(1.3); opacity: 0; }
}

/* 7. shimmer */
.dtf-icon-calculator.dtf-icon-animate {
  position: relative;
  overflow: hidden;
}
.dtf-icon-calculator.dtf-icon-animate::after {
  content: '';
  position: absolute;
  top: 0; left: -100%;
  width: 60%; height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.15), transparent);
  animation: icon-shimmer 1.5s ease-out;
}
@keyframes icon-shimmer {
  to { left: 150%; }
}

/* Reduced Motion Fallbacks */
@media (prefers-reduced-motion: reduce) {
  .dtf-icon-check.dtf-icon-animate .icon-path {
    animation: none;
    stroke-dashoffset: 0;
  }
  .dtf-icon-scan .scan-line { animation: none; opacity: 0.3; }
  .dtf-icon-bulb.dtf-icon-animate,
  .dtf-icon-telegram.dtf-icon-animate { animation: none; }
  .dtf-icon-upload.dtf-icon-animate { animation: none; }
  .dtf-icon-truck.dtf-icon-animate { animation: none; opacity: 1; }
  .dtf-icon-shield.dtf-icon-animate::after { display: none; }
  .dtf-icon-calculator.dtf-icon-animate::after { display: none; }
}
"""

with open(os.path.join(CSS_DIR, "icons.css"), "w") as f:
    f.write(icons_css)
print("Created icons.css in", CSS_DIR)

# Generate animations.css
animations_css = """/* Component CSS micro-animations (dtf/static/dtf/css/components/animations.css) */

/* 1. Button hover */
.btn-primary {
  transition: transform 0.2s cubic-bezier(0.2, 0, 0, 1), box-shadow 0.2s ease;
}
.btn-primary:hover {
  transform: scale(1.02) translateY(-1px);
  box-shadow: 0 4px 16px rgba(249, 115, 22, 0.25);
}
.btn-primary:active { transform: scale(0.98); }

.btn-secondary {
  transition: border-color 0.2s ease, transform 0.2s cubic-bezier(0.2, 0, 0, 1), box-shadow 0.2s ease;
}
.btn-secondary:hover {
  border-color: var(--dtf-accent, #f97316);
  transform: scale(1.01) translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

@media (pointer: coarse) {
  .btn-primary, .btn-secondary { min-height: 48px; }
}

/* 2. Card entrance */
.work-card, .proof-card, .price-row {
  opacity: 0;
  transform: translateY(20px);
  transition: opacity 0.5s ease-out, transform 0.5s cubic-bezier(0.16, 1, 0.3, 1);
}
.work-card.is-visible, .proof-card.is-visible, .price-row.is-visible {
  opacity: 1;
  transform: translateY(0);
}
.work-card:nth-child(2), .price-row:nth-child(2) { transition-delay: 0.1s; }
.work-card:nth-child(3), .price-row:nth-child(3) { transition-delay: 0.2s; }
.work-card:nth-child(4), .price-row:nth-child(4) { transition-delay: 0.3s; }

/* 3. Form input focus underline */
.form-group { position: relative; }
.form-group::after {
  content: '';
  position: absolute;
  bottom: 0; left: 50%; right: 50%;
  height: 2px;
  background: var(--dtf-accent, #f97316);
  transition: left 0.3s cubic-bezier(0.16, 1, 0.3, 1), right 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  border-radius: 2px 2px 0 0;
}
.form-group:focus-within::after { left: 0; right: 0; }

/* 4. FAQ accordion */
.faq-answer {
  max-height: 0;
  overflow: hidden;
  transition: max-height 0.4s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.3s ease-out;
  opacity: 0;
}
.faq-item.is-open .faq-answer {
  max-height: 300px;
  opacity: 1;
}
.faq-item {
  transition: border-left-color 0.3s ease;
  border-left: 3px solid transparent;
}
.faq-item.is-open {
  border-left-color: var(--dtf-accent, #f97316);
}

/* 5. Price badge shimmer */
.price-badge {
  position: relative;
  overflow: hidden;
}
.price-badge::after {
  content: '';
  position: absolute;
  top: 0; left: -100%; width: 60%; height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
  animation: shimmer 4s ease-in-out infinite;
}
@keyframes shimmer {
  0%, 80%, 100% { left: -100%; }
  40% { left: 150%; }
}

/* 6. Mobile dock entrance */
.mobile-dock {
  transform: translateY(120%);
  transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.mobile-dock.is-visible { transform: translateY(0); }

/* 7. Dropzone drag-over */
.dropzone {
  transition: border-color 0.3s ease, background-color 0.3s ease;
}
.dropzone.is-drag-over {
  animation: dropzone-pulse 1s ease-in-out infinite alternate;
  border-color: var(--dtf-accent, #f97316);
  background-color: rgba(249, 115, 22, 0.02);
}
@keyframes dropzone-pulse {
  0% { box-shadow: 0 0 0 0 rgba(249, 115, 22, 0.2); }
  100% { box-shadow: 0 0 0 8px rgba(249, 115, 22, 0); }
}

/* Reduced Motion Fallbacks */
@media (prefers-reduced-motion: reduce) {
  .btn-primary, .btn-secondary { transition: none; }
  .btn-primary:hover, .btn-secondary:hover { transform: none; box-shadow: none; }
  .work-card, .proof-card, .price-row { opacity: 1; transform: none; transition: none; }
  .form-group::after { transition: none; }
  .faq-answer { transition: none; }
  .price-badge::after { display: none; }
  .mobile-dock { transform: none; transition: none; }
  .dropzone { transition: none; }
  .dropzone.is-drag-over { animation: none; }
}
"""

with open(os.path.join(CSS_DIR, "animations.css"), "w") as f:
    f.write(animations_css)
print("Created animations.css in", CSS_DIR)
