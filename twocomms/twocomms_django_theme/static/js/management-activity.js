(() => {
  const pulseUrl = document.body?.dataset?.activityPulseUrl;
  if (!pulseUrl) return;

  const getCookie = (name) => {
    if (!document.cookie) return '';
    const cookies = document.cookie.split(';');
    for (const rawCookie of cookies) {
      const cookie = rawCookie.trim();
      if (cookie.substring(0, name.length + 1) === `${name}=`) {
        return decodeURIComponent(cookie.substring(name.length + 1));
      }
    }
    return '';
  };

  const isValidCsrfToken = (token) => /^[A-Za-z0-9]{32}$|^[A-Za-z0-9]{64}$/.test(token || '');
  const readDomCsrfToken = () => {
    const meta = document.querySelector?.('meta[name="csrf-token"]');
    if (meta?.getAttribute) {
      const token = meta.getAttribute('content') || '';
      if (isValidCsrfToken(token)) return token;
    }

    const input = document.querySelector?.('[name="csrfmiddlewaretoken"]');
    if (input && 'value' in input && isValidCsrfToken(input.value)) {
      return input.value;
    }

    return '';
  };

  const resolveCsrfToken = () => {
    const domToken = readDomCsrfToken();
    if (domToken) return domToken;

    const cookieToken = getCookie('csrftoken');
    if (isValidCsrfToken(cookieToken)) return cookieToken;

    return '';
  };

  const IDLE_MS = 90_000; // idle threshold: allows short "reading" periods without clicks
  const TICK_MS = 15_000;

  let lastInteraction = Date.now();
  let lastTick = Date.now();
  let isFocused = document.hasFocus?.() ?? true;
  let isVisible = document.visibilityState !== 'hidden';
  let inFlight = false;

  const markInteraction = () => {
    lastInteraction = Date.now();
  };

  const onVisibility = () => {
    isVisible = document.visibilityState !== 'hidden';
    if (isVisible) markInteraction();
  };

  const onFocus = () => {
    isFocused = true;
    markInteraction();
  };
  const onBlur = () => {
    isFocused = false;
  };

  document.addEventListener('visibilitychange', onVisibility, { passive: true });
  window.addEventListener('focus', onFocus, { passive: true });
  window.addEventListener('blur', onBlur, { passive: true });

  ['keydown', 'mousedown', 'mousemove', 'scroll', 'touchstart'].forEach((evt) => {
    window.addEventListener(evt, markInteraction, { passive: true });
  });

  const tick = async () => {
    const now = Date.now();
    const deltaSec = Math.max(0, Math.min(60, Math.round((now - lastTick) / 1000)));
    lastTick = now;

    const active = isVisible && isFocused && (now - lastInteraction) < IDLE_MS;
    if (!active || deltaSec <= 0) return;
    if (inFlight) return;
    const token = resolveCsrfToken();
    if (!token) return;
    inFlight = true;

    try {
      await fetch(pulseUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': token,
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify({ active_seconds: deltaSec }),
      });
    } catch (e) {
      // ignore
    } finally {
      inFlight = false;
    }
  };

  // Stagger to avoid "thundering herd" on full reloads
  const jitter = Math.floor(Math.random() * 1200);
  setTimeout(() => {
    tick();
    setInterval(tick, TICK_MS);
  }, jitter);
})();
