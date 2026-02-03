# Gemini Art Dept Prompt — DTF Redesign (Control Deck × Lab Proof)

You are the Art/Asset generator for **dtf.twocomms.shop**. The code and UI are already implemented; your job is to **produce the final visual assets** (photos, textures, icons, mockups) and deliver them **exactly** to the specified filenames and formats.

## 0) Core Visual Language (Non‑negotiable)
- **Style:** industrial, precise, lab‑grade, “Control Deck × Lab Proof.”
- **Mood:** dark carbon blacks, subtle metallics, molten orange accents. Clinical, engineered, high‑confidence.
- **Lighting:** neutral lab lighting, no warm “cozy” tones. Clean, high‑contrast, no stock photo vibe.
- **Composition:** minimal, technical, no clutter. Prefer single subject and controlled reflections.
- **Avoid:** cartoonish 3D, AI‑art artifacts, over‑glow, cheesy cyberpunk, busy backgrounds.

## 1) Global Requirements
- **Output quality:** High resolution, clean edges, no artifacts, no distortions.
- **Color space:** sRGB.
- **Compression:** optimized for web; keep file sizes reasonable.
- **Consistency:** before/after pairs must match framing, perspective, and lighting.
- **No embedded text** in images unless explicitly stated.
- **Do not change** filenames or formats. The code expects these exact assets.

---

## 2) Required Assets (IDs, usage, specs, filenames)

### A) Hero / Signature
1) **hero-printhead-photo**
- **Type:** photo (transparent PNG)
- **Usage:** HOME hero Printhead Scan
- **Spec:** ~2200px wide, transparent background, 2x
- **Notes:** top‑left view of DTF printer head, clean lab lighting, minimal reflections
- **Filename:** `twocomms/dtf/static/dtf/assets/hero-printhead.png`

2) **og-dtf**
- **Type:** photo (JPG)
- **Usage:** Open Graph share image
- **Spec:** 1200×630
- **Notes:** DTF Lab Proof cover. Industrial, crisp, minimal. No busy text.
- **Filename:** `twocomms/dtf/static/dtf/assets/og-dtf.jpg`

---

### B) Background / Texture
3) **noise-tiling-1**
- **Type:** texture (PNG)
- **Usage:** global background noise layer
- **Spec:** seamless 512×512, subtle grain, 8‑bit OK
- **Notes:** must tile perfectly, very subtle
- **Filename:** `twocomms/dtf/static/dtf/assets/noise-tiling-1.png`

---

### C) Home Proof Blocks
4) **compare-case-1-before / compare-case-1-after**
- **Type:** photo pair (JPG)
- **Usage:** Home Compare #1 (before/after)
- **Spec:** ~1400px wide each, 2x
- **Notes:** same framing; “before” = raw print, “after” = finished print
- **Filenames:**
  - `twocomms/dtf/static/dtf/assets/compare-case-1-before.jpg`
  - `twocomms/dtf/static/dtf/assets/compare-case-1-after.jpg`

5) **compare-case-2-before / compare-case-2-after**
- **Type:** photo pair (JPG)
- **Usage:** Home Compare #2 (before/after)
- **Spec:** ~1400px wide each, 2x
- **Notes:** same framing; focus on underbase/white layer
- **Filenames:**
  - `twocomms/dtf/static/dtf/assets/compare-case-2-before.jpg`
  - `twocomms/dtf/static/dtf/assets/compare-case-2-after.jpg`

6) **lens-macro-1**
- **Type:** photo (JPG)
- **Usage:** Home lens macro
- **Spec:** ~1400px wide, 2x
- **Notes:** 4K‑style macro texture of DTF print surface
- **Filename:** `twocomms/dtf/static/dtf/assets/lens-macro-1.jpg`

7) **gallery-macro-photos** (set)
- **Type:** photo set (JPG)
- **Usage:** Home “Наші роботи” grid
- **Spec:** 6–12 photos, consistent lighting, 2x
- **Notes:** mix of macro/process/final shots
- **Filenames:**
  - `twocomms/dtf/static/dtf/assets/gallery-macro-01.jpg`
  - `twocomms/dtf/static/dtf/assets/gallery-macro-02.jpg`
  - … up to `gallery-macro-12.jpg`

---

### D) Gallery (Proof‑first)
8) **gallery-compare-1-before / gallery-compare-1-after**
- **Type:** photo pair (JPG)
- **Spec:** ~1600px wide each, 2x
- **Notes:** same framing; raw vs finished
- **Filenames:**
  - `twocomms/dtf/static/dtf/assets/gallery-compare-1-before.jpg`
  - `twocomms/dtf/static/dtf/assets/gallery-compare-1-after.jpg`

9) **gallery-compare-2-before / gallery-compare-2-after**
- **Type:** photo pair (JPG)
- **Spec:** ~1600px wide each, 2x
- **Notes:** same framing; small text detail clarity
- **Filenames:**
  - `twocomms/dtf/static/dtf/assets/gallery-compare-2-before.jpg`
  - `twocomms/dtf/static/dtf/assets/gallery-compare-2-after.jpg`

10) **gallery-compare-3-before / gallery-compare-3-after**
- **Type:** photo pair (JPG)
- **Spec:** ~1600px wide each, 2x
- **Notes:** same framing; gradients/halftones accuracy
- **Filenames:**
  - `twocomms/dtf/static/dtf/assets/gallery-compare-3-before.jpg`
  - `twocomms/dtf/static/dtf/assets/gallery-compare-3-after.jpg`

11) **gallery-lens-macro-1**
- **Type:** photo (JPG)
- **Spec:** ~1600px wide, 2x
- **Notes:** 4K macro texture, used for zoom lens
- **Filename:** `twocomms/dtf/static/dtf/assets/gallery-lens-macro-1.jpg`

---

### E) Quality / Lab Proof
12) **lab-proof-photos** (set)
- **Type:** photo set (JPG)
- **Spec:** 4–6 photos, 2x
- **Notes:** QC, registration, wash test, tactile feel. Clean lab style.
- **Filenames:**
  - `twocomms/dtf/static/dtf/assets/lab-proof-01.jpg`
  - `twocomms/dtf/static/dtf/assets/lab-proof-02.jpg`
  - … up to `lab-proof-06.jpg`

---

### F) Requirements
13) **requirements-ok-risk**
- **Type:** photo (JPG)
- **Spec:** ~1400px wide, 2x
- **Notes:** side‑by‑side “OK vs RISK” comparison. Same framing. Clear difference.
- **Filename:** `twocomms/dtf/static/dtf/assets/requirements-ok-risk.jpg`

---

### G) Templates
14) **template-preview-60cm**
- **Type:** photo/mockup (JPG)
- **Spec:** ~1200px wide, 2x
- **Notes:** clean preview of 60cm layout grid
- **Filename:** `twocomms/dtf/static/dtf/assets/template-preview-60cm.jpg`

15) **template-60cm-file**
- **Type:** file set (PDF/AI/Figma)
- **Spec:** 60cm width layout template
- **Notes:** include guides, safe margins, bleed notes; no fancy visuals
- **Filenames:**
  - `twocomms/dtf/static/dtf/assets/template-60cm.pdf`
  - `twocomms/dtf/static/dtf/assets/template-60cm.ai`
  - `twocomms/dtf/static/dtf/assets/template-60cm.fig`

---

### H) Icons (SVG)
16) **status-pipeline-icons**
- **Type:** SVG set
- **Usage:** Status timeline icons
- **Stages:** Intake, Preflight, Print, Powder, Cure, Pack, Ship
- **Style:** thin line icons, 1.5–2px stroke, rounded caps
- **Color:** monochrome (use #EDEDED or #FFFFFF). No gradients.
- **Deliver:** one sprite or separate files
- **Filenames:**
  - `twocomms/dtf/static/dtf/assets/status-intake.svg`
  - `twocomms/dtf/static/dtf/assets/status-preflight.svg`
  - `twocomms/dtf/static/dtf/assets/status-print.svg`
  - `twocomms/dtf/static/dtf/assets/status-powder.svg`
  - `twocomms/dtf/static/dtf/assets/status-cure.svg`
  - `twocomms/dtf/static/dtf/assets/status-pack.svg`
  - `twocomms/dtf/static/dtf/assets/status-ship.svg`

17) **process-icons**
- **Type:** SVG set
- **Usage:** Home “Як це працює” steps
- **Steps:** Upload, Preflight, Payment, Print+Ship
- **Style:** same as above, clean technical line icons
- **Filenames:**
  - `twocomms/dtf/static/dtf/assets/step-upload.svg`
  - `twocomms/dtf/static/dtf/assets/step-preflight.svg`
  - `twocomms/dtf/static/dtf/assets/step-payment.svg`
  - `twocomms/dtf/static/dtf/assets/step-print-ship.svg`

---

## 3) Quality Checklist (self‑QA before delivery)
- All JPEGs sharp, no banding, no AI artifacts.
- Before/After pairs aligned exactly.
- No accidental text/branding inside images.
- Icons readable at 20–24px.
- Noise texture tiles seamlessly without seams.
- OG image looks premium even at small preview size.

## 4) Delivery
Provide assets exactly at the paths above. Do not change filenames.
If a file format is impossible (e.g., `.fig`), provide the closest equivalent and clearly note what’s missing.
