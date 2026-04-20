(function () {
  const docEl = document.documentElement;
  const root = document.querySelector("[data-brand-scroll]");
  if (!root) return;

  const shell = root.querySelector(".pro-brand-scroll__shell");
  const stage = root.querySelector(".pro-brand-stage");
  const steps = Array.from(root.querySelectorAll(".pro-brand-scroll__step"));
  const screens = Array.from(root.querySelectorAll(".pro-brand-stage__screen-state"));
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const mobileQuery = window.matchMedia("(max-width: 991px)");

  if (!shell || !stage || !steps.length || !screens.length) return;

  let ticking = false;
  let activeIndex = -1;

  function setActive(index) {
    if (index === activeIndex) return;
    activeIndex = index;

    steps.forEach((step, stepIndex) => {
      step.classList.toggle("is-active", stepIndex === index);
    });

    screens.forEach((screen, screenIndex) => {
      screen.classList.toggle("is-active", screenIndex === index);
    });
  }

  function getDesktopProgress() {
    const rect = shell.getBoundingClientRect();
    const viewportHeight = window.innerHeight || document.documentElement.clientHeight;
    const distance = Math.max(rect.height - viewportHeight, 1);
    const raw = (0 - rect.top) / distance;
    return Math.min(1, Math.max(0, raw));
  }

  function resolveIndex(progress) {
    if (progress < 0.34) return 0;
    if (progress < 0.67) return 1;
    return 2;
  }

  function isDesktopInteractiveMode() {
    return !prefersReducedMotion.matches && !mobileQuery.matches;
  }

  function update() {
    ticking = false;

    if (!isDesktopInteractiveMode()) {
      docEl.classList.remove("brand-scroll-ready");
      stage.style.setProperty("--pb-progress", "1");
      setActive(1);
      return;
    }

    docEl.classList.add("brand-scroll-ready");
    const progress = getDesktopProgress();
    stage.style.setProperty("--pb-progress", progress.toFixed(4));
    setActive(resolveIndex(progress));
  }

  function requestUpdate() {
    if (ticking) return;
    ticking = true;
    window.requestAnimationFrame(update);
  }

  setActive(0);
  update();

  window.addEventListener("scroll", requestUpdate, { passive: true });
  window.addEventListener("resize", requestUpdate);

  if (typeof prefersReducedMotion.addEventListener === "function") {
    prefersReducedMotion.addEventListener("change", requestUpdate);
    mobileQuery.addEventListener("change", requestUpdate);
  } else if (typeof prefersReducedMotion.addListener === "function") {
    prefersReducedMotion.addListener(requestUpdate);
    mobileQuery.addListener(requestUpdate);
  }
})();
