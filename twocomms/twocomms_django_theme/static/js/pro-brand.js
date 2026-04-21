(function () {
  const revealTargets = document.querySelectorAll(
    ".pro-brand-breadcrumbs.reveal, .pro-brand-page .reveal, .pro-brand-page .stagger-item",
  );

  revealTargets.forEach((element) => {
    element.classList.add("visible");
  });

  const root = document.querySelector(".pro-brand-page");
  if (!root) return;

  const videoStage = root.querySelector("[data-pro-brand-video]");
  if (!videoStage) return;

  let prefersReducedMotion = false;
  try {
    prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch (_) {
    prefersReducedMotion = false;
  }

  if (prefersReducedMotion) {
    videoStage.dataset.motion = "reduced";
    return;
  }

  videoStage.dataset.motion = "ready";
})();
