(function () {
  const DTF = (window.DTF = window.DTF || {});

  function isReducedMotion() {
    return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }

  function isMobile() {
    const viewport = window.innerWidth || document.documentElement.clientWidth || 0;
    return viewport <= 900 || (window.matchMedia && window.matchMedia('(hover: none)').matches);
  }

  const motion = {
    isReducedMotion,
    isMobile,
  };

  DTF.motion = motion;
  window.DTFMotion = motion;
})();
