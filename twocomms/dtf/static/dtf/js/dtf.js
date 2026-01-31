(function () {
  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function revealOnScroll() {
    const items = document.querySelectorAll('[data-reveal]');
    if (!items.length) return;
    if (!('IntersectionObserver' in window) || prefersReduced) {
      items.forEach(el => el.classList.add('is-visible'));
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
    items.forEach(el => observer.observe(el));
  }

  function initFaq() {
    document.querySelectorAll('.faq-q').forEach(btn => {
      btn.addEventListener('click', () => {
        const item = btn.closest('.faq-item');
        if (item) item.classList.toggle('open');
      });
    });
  }

  function initTabs() {
    const tabs = document.querySelector('.order-tabs');
    if (!tabs) return;
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
  }

  function initCalc() {
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

  function initFileGuard() {
    const fileInput = document.querySelector('input[name="gang_file"]');
    if (!fileInput) return;
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

  function initSkeletons() {
    document.querySelectorAll('img.skeleton').forEach(img => {
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
    const btn = document.getElementById('dtf-fab');
    const modal = document.getElementById('dtf-fab-modal');
    if (!btn || !modal) return;
    const form = document.getElementById('dtf-fab-form');

    btn.addEventListener('click', () => {
      modal.classList.add('active');
      modal.setAttribute('aria-hidden', 'false');
    });

    modal.addEventListener('click', (e) => {
      if (e.target.dataset.close) {
        modal.classList.remove('active');
        modal.setAttribute('aria-hidden', 'true');
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

  document.addEventListener('DOMContentLoaded', () => {
    revealOnScroll();
    initFaq();
    initTabs();
    initCalc();
    initFileGuard();
    initSkeletons();
    initFab();
  });
})();
