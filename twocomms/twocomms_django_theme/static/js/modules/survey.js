import { getCookie, prefersReducedMotion } from './shared.js';

const BASE_URL = '/survey/print-feedback';

function formatExpiry(dateStr) {
  if (!dateStr) return '';
  try {
    const dt = new Date(dateStr);
    return new Intl.DateTimeFormat('uk-UA', { day: '2-digit', month: '2-digit', year: 'numeric' }).format(dt);
  } catch (_) {
    return dateStr;
  }
}

function toggleBodyLock(enabled) {
  document.body.classList.toggle('survey-modal-open', enabled);
}

function buildOptionTooltip(helpText) {
  const infoBtn = document.createElement('button');
  infoBtn.type = 'button';
  infoBtn.className = 'survey-option-info';
  infoBtn.setAttribute('aria-label', 'Довідка');
  infoBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M11 9h2V7h-2v2zm1-7C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6z"/></svg>';

  const tooltip = document.createElement('div');
  tooltip.className = 'survey-option-tooltip';
  tooltip.textContent = helpText;

  infoBtn.addEventListener('click', (event) => {
    event.stopPropagation();
    tooltip.classList.toggle('open');
  });

  return { infoBtn, tooltip };
}

export function initSurvey() {
  const cta = document.querySelector('[data-survey-cta]');
  const modal = document.getElementById('survey-modal');
  if (!cta || !modal) return;
  if (modal.dataset.surveyInit === '1') return;
  modal.dataset.surveyInit = '1';

  const body = document.body;
  const overlay = modal.querySelector('[data-survey-close]');
  const closeBtn = modal.querySelector('.survey-close');
  const nextBtn = modal.querySelector('[data-survey-next]');
  const backBtn = modal.querySelector('[data-survey-back]');
  const skipBtn = modal.querySelector('[data-survey-skip]');
  const bodyContainer = modal.querySelector('#survey-body');
  const softHint = modal.querySelector('#survey-soft-hint');

  const strings = {
    next: modal.dataset.buttonNext || 'Далі',
    back: modal.dataset.buttonBack || 'Повернутись',
    skip: modal.dataset.buttonSkip || 'Пропустити',
    close: modal.dataset.buttonClose || 'Закрити',
    thanksTitle: modal.dataset.thanksTitle || 'Дякуємо!',
    thanksText: modal.dataset.thanksText || '',
    copyCode: modal.dataset.copyCode || 'Скопіювати код',
  };

  const state = {
    question: null,
    answer: null,
    version: null,
    answeredCount: 0,
    backUsed: false,
    isSubmitting: false,
  };

  const updateCTAState = (status) => {
    if (status === 'completed') {
      cta.classList.add('survey-complete');
      return;
    }
    cta.classList.remove('survey-complete');
    cta.querySelector('span').textContent = cta.dataset.surveyContinueText || cta.textContent;
  };

  const openModal = () => {
    modal.classList.add('open');
    modal.setAttribute('aria-hidden', 'false');
    toggleBodyLock(true);
  };

  const closeModal = () => {
    modal.classList.remove('open');
    modal.setAttribute('aria-hidden', 'true');
    toggleBodyLock(false);
    fetch(`${BASE_URL}/close/`, {
      method: 'POST',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': getCookie('csrftoken'),
      },
    }).catch(() => {});
  };

  const openAuthPanel = () => {
    const mobile = window.innerWidth < 576;
    const toggle = document.getElementById(mobile ? 'user-toggle-mobile' : 'user-toggle');
    if (toggle) {
      toggle.click();
      return;
    }
    const loginUrl = cta.dataset.loginUrl || '/login/';
    window.location.href = loginUrl;
  };

  const showLoading = () => {
    bodyContainer.innerHTML = '<div class="survey-loading"><div class="survey-spinner"></div><div class="survey-loading-text">Завантаження…</div></div>';
  };

  const showError = (message) => {
    const text = message || 'Сталася помилка. Спробуйте ще раз.';
    bodyContainer.innerHTML = `<div class="survey-error">${text}</div>`;
  };

  const resetButtons = () => {
    nextBtn.textContent = strings.next;
    backBtn.textContent = strings.back;
    skipBtn.textContent = strings.skip;
  };

  const updateActionButtons = () => {
    const required = state.question?.required;
    const hasAnswer = Array.isArray(state.answer) ? state.answer.length > 0 : !!state.answer || state.answer === 0;
    nextBtn.disabled = required ? !hasAnswer : false;
    skipBtn.style.display = required ? 'none' : '';
    backBtn.disabled = state.backUsed || state.answeredCount <= 0;
  };

  const renderThanks = (promo) => {
    const expires = promo?.expires_at ? formatExpiry(promo.expires_at) : '';
    const thanksText = strings.thanksText.replace('{expiry_date}', expires || '');
    const code = promo?.code || '';
    bodyContainer.innerHTML = `
      <div class="survey-thanks">
        <div class="survey-thanks-title">${strings.thanksTitle}</div>
        <div class="survey-thanks-text">${thanksText}</div>
        <div class="survey-code-box">
          <div class="survey-code-label">Промокод</div>
          <div class="survey-code">${code}</div>
          <button type="button" class="survey-btn survey-btn-primary survey-copy-btn">${strings.copyCode}</button>
        </div>
      </div>
    `;
    const copyBtn = bodyContainer.querySelector('.survey-copy-btn');
    if (copyBtn && code) {
      copyBtn.addEventListener('click', () => {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(code).then(() => {
            copyBtn.textContent = 'Скопійовано';
            setTimeout(() => { copyBtn.textContent = strings.copyCode; }, 1500);
          });
        } else {
          copyBtn.textContent = 'Скопійовано';
        }
      });
    }
    nextBtn.style.display = 'none';
    skipBtn.style.display = 'none';
    backBtn.style.display = 'none';
  };

  const renderQuestion = (question) => {
    state.question = question;
    state.answer = question.answer ?? null;

    const container = document.createElement('div');
    container.className = 'survey-question';

    const title = document.createElement('div');
    title.className = 'survey-question-title';
    title.textContent = question.prompt || '';
    container.appendChild(title);

    if (question.help) {
      const help = document.createElement('div');
      help.className = 'survey-question-help';
      help.textContent = question.help;
      container.appendChild(help);
    }

    const optionsWrap = document.createElement('div');
    optionsWrap.className = 'survey-options';

    if (question.type === 'slider_1_10' || question.type === 'slider_0_10') {
      const scale = question.scale || { min: 1, max: 10 };
      const value = state.answer ?? scale.min;
      const slider = document.createElement('input');
      slider.type = 'range';
      slider.min = scale.min;
      slider.max = scale.max;
      slider.step = 1;
      slider.value = value;
      slider.className = 'survey-slider';

      const sliderValue = document.createElement('div');
      sliderValue.className = 'survey-slider-value';
      sliderValue.textContent = value;

      const scaleLabels = document.createElement('div');
      scaleLabels.className = 'survey-slider-labels';
      scaleLabels.innerHTML = `<span>${scale.left_label_uk || ''}</span><span>${scale.right_label_uk || ''}</span>`;

      slider.addEventListener('input', () => {
        state.answer = parseInt(slider.value, 10);
        sliderValue.textContent = slider.value;
        updateActionButtons();
      });

      optionsWrap.appendChild(sliderValue);
      optionsWrap.appendChild(slider);
      optionsWrap.appendChild(scaleLabels);
    } else if (question.type === 'single_choice') {
      (question.options || []).forEach((opt) => {
        const option = document.createElement('button');
        option.type = 'button';
        option.className = 'survey-option';
        option.dataset.value = opt.value;
        option.innerHTML = `<span>${opt.label}</span>`;
        if (state.answer === opt.value) {
          option.classList.add('selected');
        }
        if (opt.help) {
          const { infoBtn, tooltip } = buildOptionTooltip(opt.help);
          option.appendChild(infoBtn);
          option.appendChild(tooltip);
        }
        option.addEventListener('click', () => {
          state.answer = opt.value;
          optionsWrap.querySelectorAll('.survey-option').forEach((el) => el.classList.remove('selected'));
          option.classList.add('selected');
          updateActionButtons();
        });
        optionsWrap.appendChild(option);
      });
    } else if (question.type === 'multi_choice' || question.type === 'multi_select') {
      const selected = new Set(Array.isArray(state.answer) ? state.answer : []);
      const maxSelect = question.max_select ? parseInt(question.max_select, 10) : null;
      (question.options || []).forEach((opt) => {
        const option = document.createElement('button');
        option.type = 'button';
        option.className = 'survey-option';
        option.dataset.value = opt.value;
        option.innerHTML = `<span>${opt.label}</span>`;
        if (selected.has(opt.value)) {
          option.classList.add('selected');
        }
        if (opt.help) {
          const { infoBtn, tooltip } = buildOptionTooltip(opt.help);
          option.appendChild(infoBtn);
          option.appendChild(tooltip);
        }
        option.addEventListener('click', () => {
          const value = opt.value;
          if (selected.has(value)) {
            selected.delete(value);
            option.classList.remove('selected');
          } else {
            if (maxSelect && selected.size >= maxSelect) {
              option.classList.add('shake');
              setTimeout(() => option.classList.remove('shake'), 300);
              return;
            }
            selected.add(value);
            option.classList.add('selected');
          }
          state.answer = Array.from(selected);
          updateActionButtons();
        });
        optionsWrap.appendChild(option);
      });
    } else {
      const input = document.createElement(question.type === 'text_long' ? 'textarea' : 'input');
      input.className = 'survey-text';
      if (question.type !== 'text_long') {
        input.type = 'text';
      }
      if (question.placeholder) {
        input.placeholder = question.placeholder;
      }
      input.value = state.answer || '';
      input.addEventListener('input', () => {
        state.answer = input.value;
        updateActionButtons();
      });
      optionsWrap.appendChild(input);
    }

    container.appendChild(optionsWrap);
    bodyContainer.innerHTML = '';
    bodyContainer.appendChild(container);
    nextBtn.style.display = '';
    skipBtn.style.display = '';
    backBtn.style.display = '';
    updateActionButtons();

    if (!prefersReducedMotion) {
      container.classList.add('reveal-fast');
    }
  };

  const updateFromResponse = (data) => {
    if (!data || !data.success) {
      showError();
      return;
    }
    state.version = data.version;
    state.backUsed = data.back_used;
    state.answeredCount = data.answered_count || 0;
    if (softHint) {
      softHint.textContent = data.soft_hint || '';
    }
    if (data.status === 'completed') {
      renderThanks(data.promo);
      updateCTAState('completed');
      return;
    }
    updateCTAState(data.status);
    if (!data.question) {
      showError();
      return;
    }
    state.question = data.question;
    renderQuestion(data.question);
  };

  const startSurvey = () => {
    showLoading();
    openModal();
    resetButtons();
    fetch(`${BASE_URL}/start/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': getCookie('csrftoken'),
      },
      body: JSON.stringify({}),
    })
      .then((response) => {
        if (response.status === 401) {
          closeModal();
          openAuthPanel();
          return null;
        }
        return response.json();
      })
      .then((data) => {
        if (!data) return;
        updateFromResponse(data);
      })
      .catch(() => showError());
  };

  const submitAnswer = (payload) => {
    if (state.isSubmitting) return;
    state.isSubmitting = true;
    nextBtn.classList.add('loading');

    fetch(`${BASE_URL}/answer/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': getCookie('csrftoken'),
      },
      body: JSON.stringify(payload),
    })
      .then((response) => response.json().then((data) => ({ status: response.status, data })))
      .then(({ status, data }) => {
        if (status === 409 && data.current) {
          updateFromResponse(data.current);
          return;
        }
        updateFromResponse(data);
      })
      .catch(() => showError())
      .finally(() => {
        state.isSubmitting = false;
        nextBtn.classList.remove('loading');
      });
  };

  nextBtn.addEventListener('click', () => {
    if (!state.question) return;
    submitAnswer({
      question_id: state.question.id,
      answer: state.answer,
      version: state.version,
    });
  });

  skipBtn.addEventListener('click', () => {
    if (!state.question || state.question.required) return;
    submitAnswer({
      question_id: state.question.id,
      answer: null,
      version: state.version,
    });
  });

  backBtn.addEventListener('click', () => {
    if (state.isSubmitting || state.backUsed) return;
    state.isSubmitting = true;
    fetch(`${BASE_URL}/back/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': getCookie('csrftoken'),
      },
      body: JSON.stringify({ version: state.version }),
    })
      .then((response) => response.json().then((data) => ({ status: response.status, data })))
      .then(({ status, data }) => {
        if (status === 409 && data.current) {
          updateFromResponse(data.current);
          return;
        }
        updateFromResponse(data);
      })
      .catch(() => showError())
      .finally(() => {
        state.isSubmitting = false;
      });
  });

  overlay?.addEventListener('click', closeModal);
  closeBtn?.addEventListener('click', closeModal);

  cta.addEventListener('click', (event) => {
    event.preventDefault();
    event.stopPropagation();
    const isAuthed = cta.dataset.surveyAuthenticated === '1';
    if (!isAuthed) {
      openAuthPanel();
      return;
    }
    startSurvey();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && modal.classList.contains('open')) {
      closeModal();
    }
  });
}
