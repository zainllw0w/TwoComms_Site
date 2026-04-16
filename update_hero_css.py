import re

file_path = "/Users/zainllw0w/TwoComms/site/twocomms/twocomms_django_theme/static/css/custom-print-configurator.css"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

new_hero_css = """/* ── 2. Hero ───────────────────────────────────────────────── */
.cp-hero {
  --cp-hero-scroll: 0;
  z-index: 1;
  position: relative;
  isolation: isolate;
  display: flex;
  align-items: flex-end;
  padding: clamp(1.45rem, 3vw, 2.7rem);
  min-height: clamp(460px, calc(100svh - 112px), 680px);
  background:
    radial-gradient(circle at 72% 24%, rgba(242, 211, 155, 0.15), transparent 30%),
    radial-gradient(circle at 86% 18%, rgba(215, 164, 80, 0.18), transparent 28%),
    linear-gradient(135deg, rgba(9, 8, 10, 0.96), rgba(18, 16, 20, 0.94) 52%, rgba(11, 10, 13, 0.96));
  border-color: rgba(236, 197, 127, 0.2);
  overflow: hidden;
}

.cp-hero::before,
.cp-hero::after {
  content: "";
  position: absolute;
  pointer-events: none;
}

.cp-hero::before {
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
  background-size: 44px 44px;
  opacity: 0.1;
  mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.65), transparent 86%);
}

.cp-hero::after {
  inset: auto 8% 0 8%;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(242, 211, 155, 0.4), transparent);
  opacity: 0.7;
}

.cp-hero-copy {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1.15rem;
  width: min(100%, 42rem);
  min-width: 0;
  padding: clamp(1.25rem, 4vw, 3.4rem) 0 1rem;
}

.cp-hero-brand {
  display: inline-flex;
  align-items: center;
  gap: 0.85rem;
  max-width: min(100%, 28rem);
}

.cp-hero-brandmark {
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  width: 56px;
  height: 56px;
  border-radius: 17px;
  background:
    radial-gradient(circle at 28% 28%, rgba(255, 255, 255, 0.26), transparent 34%),
    linear-gradient(145deg, rgba(242, 211, 155, 0.24), rgba(156, 97, 33, 0.14));
  border: 1px solid rgba(242, 211, 155, 0.3);
  box-shadow: 0 14px 28px rgba(0, 0, 0, 0.22);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.cp-hero-brandmark img {
  width: 34px;
  height: 34px;
  object-fit: contain;
  filter: drop-shadow(0 10px 16px rgba(0, 0, 0, 0.4));
}

.cp-hero-brandcopy {
  display: grid;
  gap: 0.12rem;
  min-width: 0;
}

.cp-hero-brandcopy strong {
  font-size: 1.05rem;
  font-weight: 800;
  line-height: 1.2;
  letter-spacing: 0.01em;
  color: #fff8ed;
  overflow-wrap: anywhere;
}

.cp-hero-brandcopy span {
  color: var(--cp-soft);
  font-size: 0.88rem;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.cp-hero-badge {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  padding: 0.55rem 1.1rem;
  border-radius: 999px;
  background: rgba(242, 211, 155, 0.06);
  border: 1px solid rgba(242, 211, 155, 0.28);
  color: var(--cp-accent-soft);
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}

.cp-hero-title {
  margin: 0;
  max-width: 8.8ch;
  font-size: clamp(2.95rem, 6.2vw, 6rem);
  line-height: 0.9;
  letter-spacing: -0.065em;
  color: #ffffff;
  text-wrap: balance;
  text-shadow: 0 20px 40px rgba(0,0,0,0.4);
}

.cp-hero-desc {
  margin: 0;
  max-width: 34rem;
  color: var(--cp-muted);
  font-size: clamp(1.05rem, 1.4vw, 1.18rem);
  line-height: 1.6;
  text-wrap: pretty;
}

.cp-hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  margin-top: 0.4rem;
}

.cp-hero-scrollcue {
  display: inline-flex;
  align-items: center;
  gap: 0.85rem;
  margin-top: auto;
  padding-top: 1rem;
  color: var(--cp-soft);
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.cp-hero-scrollcue-line {
  width: 74px;
  height: 1px;
  background: linear-gradient(90deg, rgba(242, 211, 155, 0.18), rgba(242, 211, 155, 0.8));
  transform-origin: left center;
  animation: cp-hero-scrollcue 2.8s ease-in-out infinite;
}

/* ── 2a. Hero Animations (Entrance & Wow) ──────────────────── */

.cp-animate-in {
  opacity: 0;
  transform: translateY(20px);
  animation: cp-hero-fade-up 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

.cp-delay-1 { animation-delay: 0.1s; }
.cp-delay-2 { animation-delay: 0.2s; }
.cp-delay-3 { animation-delay: 0.3s; }
.cp-delay-4 { animation-delay: 0.4s; }
.cp-delay-5 { animation-delay: 0.5s; }
.cp-delay-6 { animation-delay: 0.6s; }

@keyframes cp-hero-fade-up {
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.cp-hero-art {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  animation: cp-hero-art-fade 1.2s ease-out forwards;
}

@keyframes cp-hero-art-fade {
  from { opacity: 0; transform: scale(0.98); }
  to { opacity: 1; transform: scale(1); }
}

.cp-hero-beam,
.cp-hero-orb,
.cp-hero-mark,
.cp-hero-silhouette-shell {
  position: absolute;
}

.cp-hero-beam {
  top: -12%;
  right: -6%;
  width: min(48vw, 560px);
  height: 140%;
  background:
    radial-gradient(circle at 36% 28%, rgba(242, 211, 155, 0.22), transparent 26%),
    linear-gradient(180deg, rgba(242, 211, 155, 0.09), transparent 68%);
  opacity: calc(0.85 - var(--cp-hero-scroll) * 0.24);
  transform: translate3d(calc(var(--cp-hero-scroll) * 18px), calc(var(--cp-hero-scroll) * -22px), 0);
  filter: blur(2px);
  animation: cp-hero-pulse-beam 8s ease-in-out infinite alternate;
}

@keyframes cp-hero-pulse-beam {
  0% { transform: translate3d(0,0,0) scale(1); opacity: 0.8; }
  100% { transform: translate3d(2%, -4%, 0) scale(1.05); opacity: 0.95; }
}

.cp-hero-orb {
  top: clamp(16%, 20vh, 24%);
  right: clamp(12%, 16vw, 20%);
  width: clamp(120px, 12vw, 180px);
  aspect-ratio: 1;
  border-radius: 999px;
  background: radial-gradient(circle at 35% 35%, rgba(255, 255, 255, 0.3), rgba(242, 211, 155, 0.22) 34%, rgba(242, 211, 155, 0.06) 58%, transparent 72%);
  opacity: calc(0.95 - var(--cp-hero-scroll) * 0.24);
  transform: translate3d(0, calc(var(--cp-hero-scroll) * -28px), 0);
  filter: blur(1px);
  animation: cp-hero-float-orb 12s ease-in-out infinite alternate;
}

@keyframes cp-hero-float-orb {
  0% { transform: translate3d(0,0,0) rotate(0deg); }
  100% { transform: translate3d(-15px, 20px, 0) rotate(15deg); }
}

.cp-hero-mark {
  top: clamp(20%, 22vh, 27%);
  right: clamp(12%, 15vw, 19%);
  z-index: 1;
  display: grid;
  place-items: center;
  width: clamp(86px, 10vw, 136px);
  aspect-ratio: 1;
  border-radius: 28px;
  background:
    radial-gradient(circle at 30% 28%, rgba(255, 255, 255, 0.38), transparent 34%),
    linear-gradient(145deg, rgba(242, 211, 155, 0.35), rgba(156, 97, 33, 0.18));
  border: 1px solid rgba(242, 211, 155, 0.25);
  box-shadow:
    0 22px 42px rgba(0, 0, 0, 0.3),
    0 0 0 10px rgba(242, 211, 155, 0.04);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  opacity: calc(0.95 - var(--cp-hero-scroll) * 0.26);
  transform: translate3d(0, calc(var(--cp-hero-scroll) * -22px), 0);
  animation: cp-hero-float-mark 9s ease-in-out infinite alternate;
}

@keyframes cp-hero-float-mark {
  0% { transform: translate3d(0,0,0) rotate(0deg); }
  100% { transform: translate3d(8px, -12px, 0) rotate(-4deg); }
}

.cp-hero-mark img {
  width: 56%;
  height: 56%;
  object-fit: contain;
  filter: drop-shadow(0 8px 14px rgba(0, 0, 0, 0.3));
}

.cp-hero-silhouette-shell {
  right: clamp(-1rem, -2vw, 1rem);
  bottom: clamp(-4.5rem, -7vh, -1rem);
  width: min(42vw, 430px);
  opacity: calc(0.25 - var(--cp-hero-scroll) * 0.08);
  animation: cp-hero-float-sil 14s ease-in-out infinite alternate;
}

@keyframes cp-hero-float-sil {
  0% { transform: translate3d(0,0,0); }
  100% { transform: translate3d(-10px, 10px, 0); }
}

.cp-hero-silhouette {
  --cp-garment-fill: linear-gradient(180deg, rgba(94, 90, 100, 0.75), rgba(18, 17, 20, 0.28) 92%);
  width: 82%;
  height: 80%;
  transform: translate3d(0, calc(var(--cp-hero-scroll) * -34px), 0) scale(1.06);
  filter: saturate(0.8) drop-shadow(0 32px 42px rgba(0, 0, 0, 0.3));
}

.cp-hero-silhouette .cp-garment-body,
.cp-hero-silhouette .cp-garment-sleeve,
.cp-hero-silhouette .cp-garment-hood {
  border-color: rgba(255, 236, 204, 0.12);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.12);
}

/* Base modern button */
.cp-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
  min-height: 52px;
  padding: 0.95rem 1.45rem;
  border-radius: 999px;
  font-size: 0.95rem;
  font-weight: 700;
  line-height: 1;
  border: 1px solid transparent;
  transition: transform 180ms cubic-bezier(0.16, 1, 0.3, 1), background 180ms cubic-bezier(0.16, 1, 0.3, 1), color 180ms cubic-bezier(0.16, 1, 0.3, 1), border-color 180ms cubic-bezier(0.16, 1, 0.3, 1), box-shadow 180ms cubic-bezier(0.16, 1, 0.3, 1);
  cursor: pointer;
  text-decoration: none;
  font-family: inherit;
  box-sizing: border-box;
  position: relative;
  overflow: hidden;
}

.cp-btn svg {
  width: 18px;
  height: 18px;
  z-index: 1;
}

.cp-btn span:not(.cp-btn-shimmer) {
  z-index: 1;
}

.cp-btn--primary {
  background: linear-gradient(135deg, var(--cp-accent-soft), var(--cp-accent));
  color: #171317;
  border-color: rgba(242, 211, 155, 0.35);
  box-shadow: 0 18px 42px rgba(215, 164, 80, 0.32);
}

.cp-btn--primary:hover {
  transform: translateY(-3px);
  box-shadow: 0 22px 48px rgba(215, 164, 80, 0.45);
}

/* Shimmer animation for primary button */
.cp-btn-shimmer {
  position: absolute;
  top: 0;
  left: -100%;
  width: 50%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.4), transparent);
  transform: skewX(-20deg);
  animation: cp-btn-shimmer 3.5s infinite;
  z-index: 0;
}

@keyframes cp-btn-shimmer {
  0% { left: -100%; }
  25% { left: 200%; }
  100% { left: 200%; }
}

.cp-btn--telegram {
  background: rgba(42, 171, 238, 0.08);
  color: var(--cp-text);
  border-color: rgba(42, 171, 238, 0.25);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.cp-btn--telegram:hover {
  background: rgba(42, 171, 238, 0.18);
  border-color: rgba(42, 171, 238, 0.45);
  color: #ffffff;
  transform: translateY(-3px);
  box-shadow: 0 12px 24px rgba(42, 171, 238, 0.15);
}

.cp-btn:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px rgba(242, 211, 155, 0.25);
}

@keyframes cp-hero-scrollcue {
  0%,
  100% {
    transform: scaleX(0.55);
    opacity: 0.45;
  }
  50% {
    transform: scaleX(1);
    opacity: 0.95;
  }
}

@media (max-width: 1080px) {
  .cp-hero {
    min-height: clamp(440px, 68svh, 620px);
  }

  .cp-hero-title {
    font-size: clamp(2.6rem, 7.5vw, 4.8rem);
  }

  .cp-hero-silhouette-shell {
    width: min(44vw, 360px);
    opacity: 0.22;
  }
}

@media (max-width: 900px) {
  .cp-hero {
    align-items: flex-start;
    min-height: auto;
    padding-bottom: 2rem;
  }

  .cp-hero-copy {
    width: min(100%, 31rem);
    padding: 1rem 0 2rem;
  }

  .cp-hero-actions {
    width: 100%;
    display: grid;
    grid-template-columns: minmax(0, 1fr);
  }

  .cp-hero-title {
    max-width: 8.2ch;
    font-size: clamp(2.35rem, 11vw, 3.65rem);
  }

  .cp-hero-beam {
    top: -4%;
    right: -30%;
    width: 90%;
    opacity: 0.62;
  }

  .cp-hero-orb {
    top: 10%;
    right: 8%;
    width: 100px;
  }

  .cp-hero-mark {
    top: 5.75rem;
    right: 1rem;
    width: 78px;
  }

  .cp-hero-silhouette-shell {
    right: -5rem;
    bottom: -2rem;
    width: 250px;
    opacity: 0.15;
  }
}

@media (max-width: 560px) {
  .cp-hero-brand {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    align-items: flex-start;
    gap: 0.7rem;
    width: 100%;
    max-width: min(100%, 21rem);
  }

  .cp-hero-brandmark {
    width: 48px;
    height: 48px;
    border-radius: 15px;
  }

  .cp-hero-brandmark img {
    width: 28px;
    height: 28px;
  }

  .cp-hero-brandcopy span {
    font-size: 0.82rem;
  }

  .cp-hero-title {
    max-width: 7.3ch;
    font-size: clamp(2.1rem, 10.5vw, 3.2rem);
  }

  .cp-hero-desc {
    max-width: 21rem;
  }

  .cp-hero-scrollcue {
    font-size: 0.74rem;
  }

  .cp-hero-scrollcue-line {
    width: 52px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .cp-hero {
    --cp-hero-scroll: 0 !important;
  }
  
  .cp-animate-in {
    animation: none;
    opacity: 1;
    transform: none;
  }

  .cp-hero-art {
    animation: none;
    opacity: 1;
  }

  .cp-hero-beam,
  .cp-hero-orb,
  .cp-hero-mark,
  .cp-hero-silhouette,
  .cp-hero-silhouette-shell,
  .cp-btn-shimmer,
  .cp-hero-scrollcue-line {
    transform: none !important;
    animation: none !important;
  }
}

"""

pattern = r"/\* ── 2\. Hero ───────────────────────────────────────────────── \*/.*?/\* ── 3\. Buttons & Links ────────────────────────────────────── \*/"
new_content = re.sub(pattern, new_hero_css + "/* ── 3. Buttons & Links ────────────────────────────────────── */", content, flags=re.DOTALL)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(new_content)

print(f"Updated CSS file successfully. Replaced {len(content) - len(new_content)} bytes.")
