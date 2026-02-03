(function () {
  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const flags = getFeatureFlags();
  const initState = {
    keyboard: false,
    webVitals: false,
    printhead: false,
    fab: false,
    dropzonePaste: false,
    dynamicFavicon: false,
    reorderPrefill: false,
    orderDrafts: false,
    lensModal: false,
    htmxA11y: false,
    drawer: false,
    inkFlow: false,
    spotlight: false,
    inkDroplets: false,
    speculation: false,
  };
  let lensModalInstance = null;
  const focusTrap = {
    container: null,
    trigger: null,
    onEscape: null,
  };

  const FOCUSABLE = 'a[href], button:not([disabled]), textarea, input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex=\"-1\"])';

  function allowAmbientEffects() {
    if (prefersReduced) return false;
    if (window.matchMedia && window.matchMedia('(hover: none)').matches) return false;
    const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    if (connection && connection.saveData) return false;
    const memory = navigator.deviceMemory || 4;
    if (memory <= 2) return false;
    return true;
  }

  function getFocusable(container) {
    if (!container) return [];
    return Array.from(container.querySelectorAll(FOCUSABLE)).filter(el => !el.hasAttribute('aria-hidden'));
  }

  function setFocusTrap(container, trigger, onEscape) {
    focusTrap.container = container;
    focusTrap.trigger = trigger || document.activeElement;
    focusTrap.onEscape = onEscape || null;
    const focusables = getFocusable(container);
    if (focusables.length) {
      focusables[0].focus();
    } else if (container && container.focus) {
      container.setAttribute('tabindex', '-1');
      container.focus();
    }
  }

  function releaseFocusTrap() {
    if (focusTrap.trigger && focusTrap.trigger.focus) {
      focusTrap.trigger.focus();
    }
    focusTrap.container = null;
    focusTrap.trigger = null;
    focusTrap.onEscape = null;
  }

  document.addEventListener('keydown', (event) => {
    if (!focusTrap.container) return;
    if (event.key === 'Escape' && focusTrap.onEscape) {
      event.preventDefault();
      focusTrap.onEscape();
      return;
    }
    if (event.key !== 'Tab') return;
    const focusables = getFocusable(focusTrap.container);
    if (!focusables.length) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    const active = document.activeElement;
    if (event.shiftKey && active === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  });

  function initOnce(el, key) {
    if (!el || !key) return false;
    const attr = `init${key}`;
    if (el.dataset && el.dataset[attr]) return false;
    if (el.dataset) el.dataset[attr] = '1';
    return true;
  }

  function collectTargets(root, selector) {
    if (!root || !selector) return [];
    const nodes = [];
    if (root.matches && root.matches(selector)) nodes.push(root);
    if (root.querySelectorAll) nodes.push(...root.querySelectorAll(selector));
    return nodes;
  }

  function getFeatureFlags() {
    const defaults = {
      enable_printhead_scan: true,
      tier_mode: 'auto'
    };
    const el = document.getElementById('dtf-feature-flags');
    if (!el) return defaults;
    try {
      const parsed = JSON.parse(el.textContent || '{}');
      return { ...defaults, ...parsed };
    } catch (err) {
      return defaults;
    }
  }

  function revealOnScroll(root = document) {
    const items = collectTargets(root, '[data-reveal]');
    if (!items.length) return;
    if (!('IntersectionObserver' in window) || prefersReduced) {
      items.forEach(el => {
        if (!initOnce(el, 'Reveal')) return;
        el.classList.add('is-visible');
      });
      return;
    }
    const observer = new IntersectionObserver(
      entries => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.2 }
    );
    items.forEach(el => {
      if (!initOnce(el, 'Reveal')) return;
      observer.observe(el);
    });
  }

  function initFaq(root = document) {
    collectTargets(root, '.faq-q').forEach(btn => {
      if (!initOnce(btn, 'Faq')) return;
      btn.addEventListener('click', () => {
        const item = btn.closest('.faq-item');
        if (item) item.classList.toggle('open');
      });
    });
  }

  function initTabs(root = document) {
    const tabsList = collectTargets(root, '.order-tabs');
    if (!tabsList.length) return;
    tabsList.forEach(tabs => {
      if (!initOnce(tabs, 'Tabs')) return;
      const indicator = tabs.querySelector('.tab-indicator');
      const buttons = Array.from(tabs.querySelectorAll('.tab-btn'));

      function moveIndicator(btn) {
        if (!indicator || !btn) return;
        const rect = btn.getBoundingClientRect();
        const parentRect = tabs.getBoundingClientRect();
        indicator.style.width = rect.width + 'px';
        indicator.style.transform = `translateX(${rect.left - parentRect.left}px)`;
      }

      buttons.forEach(btn => {
        btn.addEventListener('click', () => {
          buttons.forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          const target = btn.dataset.target;
          document.querySelectorAll('.order-panels .panel').forEach(panel => {
            panel.classList.toggle('active', panel.id === `panel-${target}`);
          });
          moveIndicator(btn);
          const url = new URL(window.location.href);
          url.searchParams.set('tab', target);
          window.history.replaceState({}, '', url.toString());
        });
      });

      const activeBtn = tabs.querySelector('.tab-btn.active') || buttons[0];
      moveIndicator(activeBtn);
      window.addEventListener('resize', () => moveIndicator(activeBtn));
    });
  }

  function initCalc(root = document) {
    if (root !== document) return;
    const serverForm = document.querySelector('.estimate-bar[data-calc="server"]');
    const serverOrderForm = document.querySelector('.order-form[data-calc="server"]');
    if ((serverForm || serverOrderForm) && window.htmx) return;
    const pricing = document.getElementById('pricing-data');
    if (!pricing) return;
    const baseRate = parseFloat(pricing.dataset.baseRate || '0');
    const maxMetersReview = parseFloat(pricing.dataset.maxMetersReview || '0');
    const maxCopies = parseInt(pricing.dataset.maxCopies || '0', 10);
    const tiersRaw = pricing.dataset.tiers || '';
    const tiers = tiersRaw.split(',').map(pair => {
      const [min, rate] = pair.split(':');
      return { min: parseFloat(min), rate: parseFloat(rate) };
    }).filter(t => !Number.isNaN(t.min) && !Number.isNaN(t.rate));

    const lengthInput = document.querySelector('input[name="length_m"]');
    const copiesInput = document.querySelector('input[name="copies"]');
    const metersEl = document.getElementById('calc-meters');
    const priceEl = document.getElementById('calc-price');
    const warningEl = document.getElementById('calc-warning');
    if (!lengthInput || !copiesInput || !metersEl || !priceEl) return;

    function recalc() {
      const length = parseFloat(String(lengthInput.value || '').replace(',', '.'));
      const copies = parseInt(copiesInput.value || '0', 10);
      if (!length || !copies) {
        metersEl.textContent = '—';
        priceEl.textContent = '—';
        if (warningEl) warningEl.hidden = true;
        return;
      }
      const meters = length * copies;
      let rate = baseRate;
      tiers.forEach(tier => {
        if (meters >= tier.min) rate = tier.rate;
      });
      const total = meters * rate;
      metersEl.textContent = meters.toFixed(2) + ' м';
      priceEl.textContent = total.toFixed(2) + ' грн';
      if (warningEl) {
        const largeMeters = maxMetersReview && meters >= maxMetersReview;
        const largeCopies = maxCopies && copies > maxCopies;
        warningEl.hidden = !(largeMeters || largeCopies);
      }
    }

    lengthInput.addEventListener('input', recalc);
    copiesInput.addEventListener('input', recalc);
    recalc();
  }

  function initFileGuard(root = document) {
    const inputs = collectTargets(root, 'input[name="gang_file"]');
    if (!inputs.length) return;
    const fileInput = inputs[0];
    if (!initOnce(fileInput, 'GangFile')) return;
    const allowed = ['pdf', 'png'];
    fileInput.addEventListener('change', () => {
      const file = fileInput.files && fileInput.files[0];
      if (!file) return;
      const ext = file.name.split('.').pop().toLowerCase();
      if (!allowed.includes(ext)) {
        const helpTab = document.querySelector('.tab-btn[data-target="help"]');
        if (helpTab) helpTab.click();
        alert('Формат файлу не підтримується для готового ганг-листа. Перейшли у допомогу.');
      }
    });
  }

  function initSkeletons(root = document) {
    collectTargets(root, 'img.skeleton').forEach(img => {
      if (!initOnce(img, 'Skeleton')) return;
      if (img.complete) {
        img.classList.remove('skeleton');
      } else {
        img.addEventListener('load', () => img.classList.remove('skeleton'));
      }
    });
  }

  function getCookie(name) {
    const value = document.cookie.split('; ').find(row => row.startsWith(name + '='));
    return value ? decodeURIComponent(value.split('=')[1]) : '';
  }

  function initFab() {
    if (initState.fab) return;
    const btn = document.getElementById('dtf-fab');
    const modal = document.getElementById('dtf-fab-modal');
    if (!btn || !modal) return;
    initState.fab = true;
    const form = document.getElementById('dtf-fab-form');
    const dialog = modal.querySelector('.modal-content');

    const openModal = () => {
      modal.classList.add('active');
      modal.setAttribute('aria-hidden', 'false');
      if (dialog) setFocusTrap(dialog, btn, closeModal);
    };

    const closeModal = () => {
      modal.classList.remove('active');
      modal.setAttribute('aria-hidden', 'true');
      releaseFocusTrap();
    };

    btn.addEventListener('click', () => {
      openModal();
    });

    modal.addEventListener('click', (e) => {
      if (e.target.dataset.close) {
        closeModal();
      }
    });

    if (form) {
      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(form);
        try {
          const resp = await fetch(form.action, {
            method: 'POST',
            body: formData,
            headers: {
              'X-CSRFToken': getCookie('csrftoken'),
            }
          });
          const data = await resp.json();
          if (resp.ok) {
            form.reset();
            modal.classList.remove('active');
            alert('Дякуємо! Менеджер звʼяжеться найближчим часом.');
          } else {
            alert('Помилка. Перевірте форму.');
            console.error(data);
          }
        } catch (err) {
          alert('Не вдалося надіслати. Спробуйте пізніше.');
        }
      });
    }
  }

  function resolveScanTier() {
    const mode = String(flags.tier_mode || 'auto').toLowerCase();
    if (mode.startsWith('force')) {
      const forced = parseInt(mode.replace('force', ''), 10);
      return Number.isNaN(forced) ? 0 : Math.max(0, Math.min(forced, 4));
    }
    if (!flags.enable_printhead_scan || prefersReduced) return 0;
    const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    const saveData = connection && connection.saveData;
    const effectiveType = (connection && connection.effectiveType) || '';
    if (saveData || /2g/.test(effectiveType)) return 0;

    const width = window.innerWidth || 0;
    const isMobile = width < 640;
    const memory = navigator.deviceMemory || 4;
    const cores = navigator.hardwareConcurrency || 4;

    let tier = 2;
    if (memory <= 2 || cores <= 2) tier = 1;
    if (isMobile) tier = Math.min(tier, 1);
    if (memory >= 8 && cores >= 8 && width >= 1280) tier = 3;
    if (memory >= 16 && cores >= 12 && width >= 1440) tier = 4;
    return tier;
  }

  function initPrintheadScan() {
    if (initState.printhead) return;
    const hero = document.querySelector('.scan-hero');
    if (!hero) return;
    initState.printhead = true;
    const tier = resolveScanTier();
    hero.dataset.scanTier = String(tier);
    hero.classList.add(`scan-tier-${tier}`);
    hero.style.setProperty('--scan-duration', tier >= 2 ? '900ms' : '700ms');

    if (tier === 0) {
      hero.classList.add('scan-static');
      return;
    }

    requestAnimationFrame(() => {
      hero.classList.add('scan-animate');
    });
    trackEvent('used_printhead_scan', { tier });
  }

  function initInkFlow() {
    if (initState.inkFlow) return;
    const hero = document.querySelector('.hero');
    if (!hero) return;
    if (!allowAmbientEffects()) return;
    initState.inkFlow = true;
    let frame = null;
    let targetX = 55;
    let targetY = 30;

    const update = () => {
      hero.style.setProperty('--ink-x', `${targetX}%`);
      hero.style.setProperty('--ink-y', `${targetY}%`);
      frame = null;
    };

    const handleMove = (event) => {
      const rect = hero.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const x = ((event.clientX - rect.left) / rect.width) * 100;
      const y = ((event.clientY - rect.top) / rect.height) * 100;
      targetX = Math.max(0, Math.min(100, x));
      targetY = Math.max(0, Math.min(100, y));
      if (!frame) frame = window.requestAnimationFrame(update);
    };

    hero.addEventListener('mousemove', handleMove);
    hero.addEventListener('mouseenter', () => hero.style.setProperty('--ink-opacity', '0.65'));
    hero.addEventListener('mouseleave', () => hero.style.setProperty('--ink-opacity', '0'));
  }

  function initSpotlight(root = document) {
    if (!allowAmbientEffects()) return;
    const cards = collectTargets(root, '.work-card, .proof-card');
    if (!cards.length) return;
    cards.forEach(card => {
      if (!initOnce(card, 'Spotlight')) return;
      let frame = null;
      let targetX = 50;
      let targetY = 30;

      const update = () => {
        card.style.setProperty('--spot-x', `${targetX}%`);
        card.style.setProperty('--spot-y', `${targetY}%`);
        frame = null;
      };

      const handleMove = (event) => {
        const rect = card.getBoundingClientRect();
        if (!rect.width || !rect.height) return;
        const x = ((event.clientX - rect.left) / rect.width) * 100;
        const y = ((event.clientY - rect.top) / rect.height) * 100;
        targetX = Math.max(0, Math.min(100, x));
        targetY = Math.max(0, Math.min(100, y));
        if (!frame) frame = window.requestAnimationFrame(update);
      };

      card.addEventListener('mousemove', handleMove);
      card.addEventListener('mouseenter', () => card.style.setProperty('--spot-opacity', '0.7'));
      card.addEventListener('mouseleave', () => card.style.setProperty('--spot-opacity', '0'));
    });
  }

  function initInkDroplets() {
    if (initState.inkDroplets) return;
    const layer = document.querySelector('.ink-droplets');
    if (!layer) return;
    if (document.body && document.body.dataset.page === 'order') return;
    if (!allowAmbientEffects()) {
      layer.style.opacity = '0';
      return;
    }
    initState.inkDroplets = true;
    let frame = null;
    let targetX = 0;
    let targetY = 0;

    const apply = () => {
      layer.style.setProperty('--drop-dx', `${targetX}px`);
      layer.style.setProperty('--drop-dy', `${targetY}px`);
      frame = null;
    };

    const handleMove = (xRatio, yRatio) => {
      const maxShift = 22;
      targetX = (xRatio - 0.5) * maxShift * 2;
      targetY = (yRatio - 0.5) * maxShift * 2;
      if (!frame) frame = window.requestAnimationFrame(apply);
    };

    const onMouse = (event) => {
      const xRatio = event.clientX / window.innerWidth;
      const yRatio = event.clientY / window.innerHeight;
      handleMove(xRatio, yRatio);
      layer.style.setProperty('--drop-opacity', '0.55');
    };

    window.addEventListener('mousemove', onMouse);
    window.addEventListener('mouseenter', () => layer.style.setProperty('--drop-opacity', '0.55'));
    window.addEventListener('mouseleave', () => layer.style.setProperty('--drop-opacity', '0.2'));
    layer.style.setProperty('--drop-opacity', '0.2');

    let tiltEnabled = false;
    let tiltRequested = false;

    const onTilt = (event) => {
      if (event.beta == null || event.gamma == null) return;
      const gamma = Math.max(-30, Math.min(30, event.gamma));
      const beta = Math.max(-30, Math.min(30, event.beta));
      const xRatio = (gamma + 30) / 60;
      const yRatio = (beta + 30) / 60;
      handleMove(xRatio, yRatio);
      layer.style.setProperty('--drop-opacity', '0.4');
    };

    const enableTilt = async () => {
      if (tiltRequested) return;
      tiltRequested = true;
      try {
        if (typeof DeviceOrientationEvent !== 'undefined' && typeof DeviceOrientationEvent.requestPermission === 'function') {
          const result = await DeviceOrientationEvent.requestPermission();
          if (result !== 'granted') return;
        }
        window.addEventListener('deviceorientation', onTilt, true);
        tiltEnabled = true;
      } catch (err) {
        // ignore
      }
    };

    document.addEventListener('touchstart', () => {
      if (!tiltEnabled) enableTilt();
    }, { once: true, passive: true });
  }

  function initSpeculationRules() {
    if (initState.speculation) return;
    if (!('HTMLScriptElement' in window) || typeof HTMLScriptElement.supports !== 'function') return;
    if (!HTMLScriptElement.supports('speculationrules')) return;
    const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    if (connection && connection.saveData) return;
    const triggers = document.querySelectorAll('a.btn-primary[href*=\"/order\"], a.btn-primary[href*=\"/order/\"]');
    if (!triggers.length) return;
    initState.speculation = true;
    const inject = () => {
      if (document.getElementById('speculation-order')) return;
      const script = document.createElement('script');
      script.type = 'speculationrules';
      script.id = 'speculation-order';
      const url = new URL('/order/', window.location.origin).href;
      script.textContent = JSON.stringify({ prerender: [{ source: 'list', urls: [url] }] });
      document.head.appendChild(script);
    };
    triggers.forEach(btn => {
      btn.addEventListener('mouseenter', inject, { once: true });
      btn.addEventListener('focus', inject, { once: true });
      btn.addEventListener('touchstart', inject, { once: true });
    });
  }

  function showToast(message, tone = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast ${tone}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3200);
  }

  function initDropzones(root = document) {
    const zones = collectTargets(root, '[data-dropzone]');
    zones.forEach(zone => {
      if (!initOnce(zone, 'Dropzone')) return;
      const input = zone.querySelector('input[type=\"file\"]');
      const fileName = zone.querySelector('[data-file-name]');
      const addBtn = zone.querySelector('[data-add-file]');
      const pasteBtn = zone.querySelector('[data-paste]');
      if (!input) return;

      const updateName = () => {
        if (!fileName) return;
        const files = input.files || [];
        if (files.length) {
          fileName.textContent = files.length > 1 ? `${files.length} файлів` : files[0].name;
        } else {
          fileName.textContent = '—';
        }
      };

      const setFiles = (files) => {
        if (!files || !files.length) return;
        const data = new DataTransfer();
        Array.from(files).forEach(file => data.items.add(file));
        input.files = data.files;
        input.dispatchEvent(new Event('change', { bubbles: true }));
        updateName();
      };

      zone.addEventListener('dragenter', (e) => {
        e.preventDefault();
        zone.classList.add('is-dragover');
      });
      zone.addEventListener('dragover', (e) => e.preventDefault());
      zone.addEventListener('dragleave', () => zone.classList.remove('is-dragover'));
      zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('is-dragover');
        setFiles(e.dataTransfer.files);
        showToast('Файл додано', 'success');
      });

      input.addEventListener('change', updateName);

      if (addBtn) {
        addBtn.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          input.click();
        });
      }

      if (pasteBtn) {
        pasteBtn.addEventListener('click', async (e) => {
          e.preventDefault();
          e.stopPropagation();
          if (!navigator.clipboard || !navigator.clipboard.read) {
            showToast('Буфер недоступний у цьому браузері', 'warn');
            return;
          }
          try {
            const items = await navigator.clipboard.read();
            for (const item of items) {
              const type = item.types.find(t => t.includes('image') || t.includes('pdf'));
              if (!type) continue;
              const blob = await item.getType(type);
              const file = new File([blob], `clipboard.${type.includes('pdf') ? 'pdf' : 'png'}`, { type });
              setFiles([file]);
              showToast('Файл додано з буфера', 'success');
              return;
            }
            showToast('У буфері немає файлу', 'warn');
          } catch (err) {
            showToast('Не вдалося прочитати буфер', 'error');
          }
        });
      }
    });

    if (!initState.dropzonePaste) {
      document.addEventListener('paste', (event) => {
        const items = event.clipboardData && event.clipboardData.items;
        if (!items) return;
        const hasFile = Array.from(items).some(item => item.kind === 'file');
        if (hasFile) {
          showToast('Файл у буфері. Натисніть \"Вставити з буфера\"', 'warn');
        }
      });
      initState.dropzonePaste = true;
    }
  }

  function initOrderHtmxCalc(root = document) {
    if (!window.htmx) return;
    collectTargets(root, '.order-form[data-calc=\"server\"]').forEach(form => {
      if (!initOnce(form, 'OrderCalc')) return;
      const length = form.querySelector('input[name=\"length_m\"]');
      const copies = form.querySelector('input[name=\"copies\"]');
      const target = form.querySelector('#order-calc');
      const url = form.dataset.calcUrl;
      if (!length || !copies || !target || !url) return;
      [length, copies].forEach(input => {
        input.setAttribute('hx-get', url);
        input.setAttribute('hx-trigger', 'input changed delay:300ms');
        input.setAttribute('hx-target', '#order-calc');
        input.setAttribute('hx-include', "input[name='length_m'], input[name='copies']");
        input.setAttribute('hx-sync', 'this:replace');
      });
      window.htmx.process(form);
    });
  }

  function initSubmitGuard(root = document) {
    collectTargets(root, 'form[data-submit-guard]').forEach(form => {
      if (!initOnce(form, 'SubmitGuard')) return;
      form.addEventListener('submit', () => {
        const btn = form.querySelector('[data-submit]');
        if (btn) {
          btn.disabled = true;
          btn.classList.add('is-loading');
        }
      });
    });
  }

  function initKeyboardMode() {
    if (initState.keyboard) return;
    const vv = window.visualViewport;
    if (!vv) return;
    initState.keyboard = true;
    const update = () => {
      const keyboardOpen = vv.height < window.innerHeight;
      document.body.classList.toggle('keyboard-open', keyboardOpen);
    };
    vv.addEventListener('resize', update);
    vv.addEventListener('scroll', update);
    update();
  }

  function initOrderDrafts() {
    if (initState.orderDrafts) return;
    const forms = [
      { form: document.getElementById('order-ready-form'), key: 'dtf_order_ready_draft' },
      { form: document.getElementById('order-help-form'), key: 'dtf_order_help_draft' }
    ];
    initState.orderDrafts = true;
    forms.forEach(({ form, key }) => {
      if (!form) return;
      try {
        const raw = localStorage.getItem(key);
        if (raw) {
          const data = JSON.parse(raw);
          Object.entries(data).forEach(([name, value]) => {
            const field = form.querySelector(`[name=\"${name}\"]`);
            if (!field || field.type === 'file') return;
            if (field.type === 'checkbox') {
              field.checked = Boolean(value);
            } else {
              field.value = value;
            }
          });
        }
      } catch (err) {
        localStorage.removeItem(key);
      }

      const save = () => {
        const payload = {};
        form.querySelectorAll('input, select, textarea').forEach(field => {
          if (!field.name || field.type === 'file' || field.name === 'csrfmiddlewaretoken') return;
          payload[field.name] = field.type === 'checkbox' ? field.checked : field.value;
        });
        localStorage.setItem(key, JSON.stringify(payload));
      };

      form.addEventListener('input', save);
      form.addEventListener('change', save);
      form.addEventListener('submit', () => localStorage.removeItem(key));
    });
  }

  function initUnderbaseToggle(root = document) {
    collectTargets(root, '[data-underbase-toggle]').forEach(toggle => {
      if (!initOnce(toggle, 'Underbase')) return;
      const block = toggle.closest('.preview-block');
      const card = block ? block.querySelector('.preview-card') : null;
      if (!card) return;
      toggle.addEventListener('change', () => {
        card.classList.toggle('is-underbase', toggle.checked);
      });
    });
  }

  function initCopyButtons(root = document) {
    collectTargets(root, '[data-copy]').forEach(btn => {
      if (!initOnce(btn, 'Copy')) return;
      btn.addEventListener('click', async () => {
        const value = btn.getAttribute('data-copy');
        if (!value) return;
        try {
          await navigator.clipboard.writeText(value);
          showToast('Лінк скопійовано', 'success');
        } catch (err) {
          showToast('Не вдалося скопіювати', 'error');
        }
      });
    });
  }

  function initDynamicFavicon() {
    if (initState.dynamicFavicon) return;
    if (!flags.enable_dynamic_favicon) return;
    const el = document.querySelector('[data-status-index]');
    if (!el) return;
    initState.dynamicFavicon = true;
    const index = parseInt(el.dataset.statusIndex || '0', 10);
    const total = parseInt(el.dataset.statusTotal || '1', 10);
    if (!total) return;
    const ratio = Math.max(0, Math.min(1, index / total));
    const canvas = document.createElement('canvas');
    canvas.width = 32;
    canvas.height = 32;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.fillStyle = '#0a0a0a';
    ctx.fillRect(0, 0, 32, 32);
    ctx.strokeStyle = '#ff6a00';
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.arc(16, 16, 10, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * ratio);
    ctx.stroke();
    const link = document.querySelector('link[rel=\"icon\"]') || document.createElement('link');
    link.rel = 'icon';
    link.href = canvas.toDataURL('image/png');
    document.head.appendChild(link);
  }

  function initReorderPrefill() {
    if (initState.reorderPrefill) return;
    if (document.body.dataset.page !== 'order') return;
    const params = new URLSearchParams(window.location.search);
    const ref = params.get('reorder') || params.get('ref');
    if (!ref) return;
    initState.reorderPrefill = true;
    const comment = document.querySelector('textarea[name=\"comment\"]');
    if (comment && !comment.value) {
      comment.value = `Reorder: ${ref}`;
    }
    showToast('Додали референс до коментаря', 'success');
  }

  function initCompare(root = document) {
    const cards = collectTargets(root, '[data-compare]');
    if (!cards.length) return;
    if (!flags.enable_compare) {
      cards.forEach(card => card.classList.add('is-disabled'));
      return;
    }
    cards.forEach(card => {
      if (!initOnce(card, 'Compare')) return;
      const range = card.querySelector('.compare-range');
      if (!range) return;
      const update = () => {
        const value = `${range.value}%`;
        card.style.setProperty('--compare', value);
      };
      range.addEventListener('input', update);
      range.addEventListener('change', () => trackEvent('compare_interaction', { value: range.value }));
      update();
    });
  }

  function getLensModal() {
    if (lensModalInstance) return lensModalInstance;
    const modal = document.getElementById('lens-modal');
    if (!modal) return null;
    const img = modal.querySelector('[data-lens-modal-img]');
    const placeholder = modal.querySelector('[data-lens-modal-placeholder]');
    const dialog = modal.querySelector('.lens-modal-dialog');

    const close = () => {
      modal.classList.remove('is-open');
      modal.setAttribute('aria-hidden', 'true');
      releaseFocusTrap();
    };

    if (!initState.lensModal) {
      modal.addEventListener('click', (e) => {
        if (e.target && e.target.dataset && 'close' in e.target.dataset) {
          close();
        }
      });
      initState.lensModal = true;
    }

    lensModalInstance = {
      open: (src, alt, trigger) => {
        if (img) {
          if (src) {
            img.src = src;
            img.alt = alt || '';
            img.hidden = false;
            if (placeholder) placeholder.hidden = true;
          } else {
            img.hidden = true;
            if (placeholder) placeholder.hidden = false;
          }
        }
        modal.classList.add('is-open');
        modal.setAttribute('aria-hidden', 'false');
        if (dialog) setFocusTrap(dialog, trigger || document.activeElement, close);
      },
    };
    return lensModalInstance;
  }

  function initLens(root = document) {
    const cards = collectTargets(root, '[data-lens]');
    if (!cards.length) return;
    if (!flags.enable_lens) {
      cards.forEach(card => card.classList.add('is-disabled'));
      return;
    }
    const isTouch = window.matchMedia('(hover: none)').matches;
    const modal = isTouch ? getLensModal() : null;

    cards.forEach(card => {
      if (!initOnce(card, 'Lens')) return;
      const media = card.querySelector('.lens-media');
      const glass = card.querySelector('.lens-glass');
      if (!media || !glass) return;
      const img = media.querySelector('img');
      const src = (img && img.getAttribute('src')) || media.dataset.lensSrc;
      const alt = (img && img.getAttribute('alt')) || (card.querySelector('.proof-title') || {}).textContent || '';
      if (!src) {
        card.classList.add('is-disabled');
        return;
      }

      if (isTouch && modal) {
        glass.style.display = 'none';
        media.addEventListener('click', () => {
          modal.open(src, alt, media);
          trackEvent('lens_interaction', { mode: 'modal' });
        });
        return;
      }

      const zoom = 2;
      glass.style.backgroundImage = `url(${src})`;

      const updateSize = () => {
        glass.style.backgroundSize = `${media.offsetWidth * zoom}px ${media.offsetHeight * zoom}px`;
      };

      const move = (event) => {
        const e = event.touches ? event.touches[0] : event;
        const rect = media.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        glass.style.left = `${x}px`;
        glass.style.top = `${y}px`;
        const bgX = -(x * zoom - glass.offsetWidth / 2);
        const bgY = -(y * zoom - glass.offsetHeight / 2);
        glass.style.backgroundPosition = `${bgX}px ${bgY}px`;
      };

      const activate = () => media.classList.add('is-active');
      const deactivate = () => media.classList.remove('is-active');

      updateSize();
      media.addEventListener('mousemove', move);
      media.addEventListener('mouseenter', () => {
        activate();
        trackEvent('lens_interaction', {});
      });
      media.addEventListener('mouseleave', deactivate);
      window.addEventListener('resize', updateSize);
    });
  }

  function initStatusFlash(root = document) {
    const boards = collectTargets(root, '.status-board');
    if (!boards.length) return;
    boards.forEach(board => {
      if (!initOnce(board, 'StatusFlash')) return;
      const order = board.dataset.statusOrder || 'generic';
      const index = parseInt(board.dataset.statusIndex || '0', 10);
      const key = `dtf_status_${order}`;
      let prev = -1;
      try {
        prev = parseInt(localStorage.getItem(key) || '-1', 10);
      } catch (err) {
        prev = -1;
      }
      if (!prefersReduced && prev >= 0 && index > prev) {
        board.classList.add('is-flash');
        setTimeout(() => board.classList.remove('is-flash'), 240);
      }
      try {
        localStorage.setItem(key, String(index));
      } catch (err) {
        // ignore
      }
    });
  }

  function initHtmxA11y() {
    if (!window.htmx || initState.htmxA11y) return;
    initState.htmxA11y = true;
    document.body.addEventListener('htmx:beforeRequest', (evt) => {
      const target = evt.detail && evt.detail.target;
      if (target) target.setAttribute('aria-busy', 'true');
    });
    document.body.addEventListener('htmx:afterSwap', (evt) => {
      const target = evt.detail && evt.detail.target;
      if (target) target.setAttribute('aria-busy', 'false');
      if (target && target.hasAttribute && target.hasAttribute('data-swap-focus')) {
        const active = document.activeElement;
        const isFormField = active && (
          active.tagName === 'INPUT' ||
          active.tagName === 'TEXTAREA' ||
          active.tagName === 'SELECT' ||
          active.isContentEditable
        );
        if (!isFormField) {
          target.setAttribute('tabindex', '-1');
          target.focus({ preventScroll: true });
        }
      }
    });
  }

  function initDrawer() {
    const drawer = document.getElementById('nav-drawer');
    const openBtn = document.querySelector('[data-drawer-open]');
    if (!drawer || !openBtn || initState.drawer) return;
    initState.drawer = true;
    const panel = drawer.querySelector('.nav-panel');
    const closeButtons = drawer.querySelectorAll('[data-drawer-close]');

    const open = () => {
      drawer.classList.add('is-open');
      drawer.setAttribute('aria-hidden', 'false');
      openBtn.setAttribute('aria-expanded', 'true');
      if (panel) setFocusTrap(panel, openBtn, close);
    };

    const close = () => {
      drawer.classList.remove('is-open');
      drawer.setAttribute('aria-hidden', 'true');
      openBtn.setAttribute('aria-expanded', 'false');
      releaseFocusTrap();
    };

    openBtn.addEventListener('click', open);
    closeButtons.forEach(btn => btn.addEventListener('click', close));
  }

  function trackEvent(name, payload) {
    if (!name) return;
    const data = Object.assign({ event: name }, payload || {});
    if (window.dataLayer && Array.isArray(window.dataLayer)) {
      window.dataLayer.push(data);
    } else {
      window.__dtfEvents = window.__dtfEvents || [];
      window.__dtfEvents.push(data);
    }
  }

  function initWebVitals() {
    if (initState.webVitals) return;
    if (!('PerformanceObserver' in window)) return;
    initState.webVitals = true;
    const vitals = {};
    const report = (name, value) => {
      vitals[name] = value;
      trackEvent('web_vital', { metric: name, value });
    };

    try {
      const lcpObserver = new PerformanceObserver((list) => {
        const entries = list.getEntries();
        const last = entries[entries.length - 1];
        if (last) report('LCP', Math.round(last.startTime));
      });
      lcpObserver.observe({ type: 'largest-contentful-paint', buffered: true });

      let clsValue = 0;
      const clsObserver = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (!entry.hadRecentInput) clsValue += entry.value;
        }
        report('CLS', Number(clsValue.toFixed(4)));
      });
      clsObserver.observe({ type: 'layout-shift', buffered: true });

      const inpObserver = new PerformanceObserver((list) => {
        const entries = list.getEntries();
        const last = entries[entries.length - 1];
        if (last) report('INP', Math.round(last.duration || last.processingEnd - last.startTime));
      });
      inpObserver.observe({ type: 'event', buffered: true, durationThreshold: 40 });
    } catch (err) {
      // ignore
    }
  }

  function initAll(root = document) {
    revealOnScroll(root);
    initFaq(root);
    initTabs(root);
    initCalc(root);
    initFileGuard(root);
    initSkeletons(root);
    initFab();
    initPrintheadScan();
    initInkFlow();
    initSpotlight(root);
    initInkDroplets();
    initCompare(root);
    initLens(root);
    initDropzones(root);
    initOrderHtmxCalc(root);
    initSubmitGuard(root);
    initKeyboardMode();
    initOrderDrafts();
    initUnderbaseToggle(root);
    initCopyButtons(root);
    initDynamicFavicon();
    initReorderPrefill();
    initStatusFlash(root);
    initWebVitals();
    initHtmxA11y();
    initDrawer();
    initSpeculationRules();
  }

  document.addEventListener('DOMContentLoaded', () => {
    initAll(document);
    if (window.htmx) {
      if (typeof window.htmx.onLoad === 'function') {
        window.htmx.onLoad((content) => initAll(content));
      } else if (document.body) {
        document.body.addEventListener('htmx:afterSwap', (evt) => initAll(evt.detail.target));
      }
    }
  });
})();
