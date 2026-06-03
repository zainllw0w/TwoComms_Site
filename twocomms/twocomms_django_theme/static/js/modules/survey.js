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

function isPlainObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value);
}

function hasMeaningfulAnswer(question, answer) {
  if (!question) return false;
  if (question.type === 'info_card') return true;
  if (Array.isArray(answer)) return answer.length > 0;
  if (question.type === 'maxdiff_best_worst') {
    return isPlainObject(answer) && answer.best && answer.worst && answer.best !== answer.worst;
  }
  if (question.type === 'budget_allocation_100') {
    if (!isPlainObject(answer)) return false;
    return Object.values(answer).reduce((sum, value) => sum + (parseInt(value, 10) || 0), 0) === 100;
  }
  if (question.type === 'contact_capture') {
    return isPlainObject(answer) && answer.channel && `${answer.value || ''}`.trim().length > 0;
  }
  if (
    question.type === 'concept_reaction_cards' ||
    question.type === 'tap_reaction_cards' ||
    question.type === 'purchase_intent_matrix'
  ) {
    return isPlainObject(answer) && Object.keys(answer).length > 0;
  }
  return !!answer || answer === 0;
}

export function initSurvey() {
  const cta = document.querySelector('[data-survey-cta]');
  if (!cta) return;
  // Lazy-mount: если модалка лежит в <template id="survey-modal-template">,
  // переносим её в body. Экономит DOM-узлы (~65 шт.) на first paint.
  let modal = document.getElementById('survey-modal');
  if (!modal) {
    const tpl = document.getElementById('survey-modal-template');
    if (tpl && tpl.content) {
      document.body.appendChild(tpl.content.cloneNode(true));
      modal = document.getElementById('survey-modal');
    }
  }
  if (!modal) return;
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
    authTitle: modal.dataset.authTitle || 'Збережи промокод у акаунті',
    authText: modal.dataset.authText || 'Увійди, щоб промокод не загубився.',
    authGoogle: modal.dataset.authGoogle || 'Увійти через Google',
    authTelegram: modal.dataset.authTelegram || 'Увійти через Telegram',
  };

  // Survey block / persistence config (anonymous visitors).
  const section = document.getElementById('survey-section');
  const surveyKey = modal.dataset.surveyKey
    || (section && section.getAttribute('data-survey-key'))
    || 'print_feedback_v1';
  const storeKey = `tc_survey_state__${surveyKey}`;
  const loginUrl = modal.dataset.loginUrl || '/login/?next=/cart/';
  const googleUrl = modal.dataset.googleUrl || '';

  const readStoredState = () => {
    try {
      const raw = window.localStorage.getItem(storeKey);
      return raw ? JSON.parse(raw) : null;
    } catch (_) {
      return null;
    }
  };

  const writeStoredState = (patch) => {
    try {
      const current = readStoredState() || {};
      const next = { ...current, ...patch };
      window.localStorage.setItem(storeKey, JSON.stringify(next));
      return next;
    } catch (_) {
      return null;
    }
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

  const scrollToTop = () => {
    bodyContainer.scrollTop = 0;
    requestAnimationFrame(() => {
      bodyContainer.scrollTop = 0;
    });
    setTimeout(() => {
      bodyContainer.scrollTop = 0;
    }, 40);
    setTimeout(() => {
      bodyContainer.scrollTop = 0;
    }, 100);
  };

  const showLoading = () => {
    bodyContainer.innerHTML = '<div class="survey-loading"><div class="survey-spinner"></div><div class="survey-loading-text">Завантаження…</div></div>';
    scrollToTop();
  };

  const showError = (message) => {
    const text = message || 'Сталася помилка. Спробуйте ще раз.';
    bodyContainer.innerHTML = `<div class="survey-error">${text}</div>`;
    scrollToTop();
  };

  const resetButtons = () => {
    nextBtn.textContent = strings.next;
    backBtn.textContent = strings.back;
    skipBtn.textContent = strings.skip;
  };

  const updateActionButtons = () => {
    const required = state.question?.required;
    const hasAnswer = hasMeaningfulAnswer(state.question, state.answer);
    nextBtn.disabled = required ? !hasAnswer : false;
    const partialStructuredAnswer = isPlainObject(state.answer) && Object.keys(state.answer).length > 0;
    if (
      partialStructuredAnswer &&
      ['budget_allocation_100', 'maxdiff_best_worst', 'contact_capture'].includes(state.question?.type)
    ) {
      nextBtn.disabled = !hasAnswer;
    }
    skipBtn.style.display = required ? 'none' : '';
    backBtn.disabled = state.backUsed || state.answeredCount <= 0;
  };

  const renderThanks = (promo, authenticated) => {
    const expires = promo?.expires_at ? formatExpiry(promo.expires_at) : '';
    const thanksText = strings.thanksText.replace('{expiry_date}', expires || '');
    const code = promo?.code || '';

    // Persist completion for anonymous visitors so the homepage block knows
    // to stay hidden (while the code is valid) or reappear (once expired).
    if (!authenticated) {
      writeStoredState({
        status: 'completed',
        code,
        expiresAt: promo?.expires_at || null,
        awardedAt: new Date().toISOString(),
      });
    }

    const authBlock = !authenticated
      ? `
        <div class="survey-auth-cta">
          <div class="survey-auth-title">${strings.authTitle}</div>
          <div class="survey-auth-text">${strings.authText}</div>
          <div class="survey-auth-buttons">
            ${googleUrl ? `
            <a class="survey-auth-btn survey-auth-google" href="${googleUrl}?next=/cart/">
              <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><path fill="#EA4335" d="M12 10.2v3.9h5.5c-.24 1.4-1.7 4.1-5.5 4.1-3.3 0-6-2.7-6-6.1s2.7-6.1 6-6.1c1.9 0 3.1.8 3.9 1.5l2.6-2.5C17.1 6.4 14.8 5.4 12 5.4 6.9 5.4 2.8 9.5 2.8 14.6S6.9 23.8 12 23.8c5.8 0 9.6-4.1 9.6-9.8 0-.66-.07-1.16-.16-1.66H12z"/></svg>
              <span>${strings.authGoogle}</span>
            </a>` : ''}
            <button type="button" class="survey-auth-btn survey-auth-telegram" data-survey-tg-login>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M9.78 18.65l.28-4.23 7.68-6.92c.34-.31-.07-.46-.52-.19L7.74 13.3 3.64 12c-.88-.25-.89-.86.2-1.3l15.97-6.16c.73-.33 1.43.18 1.15 1.3l-2.72 12.81c-.19.91-.74 1.13-1.5.71L12.6 16.3l-1.99 1.93c-.23.23-.42.42-.83.42z"/></svg>
              <span>${strings.authTelegram}</span>
            </button>
          </div>
        </div>
      `
      : '';

    bodyContainer.innerHTML = `
      <div class="survey-thanks">
        <div class="survey-thanks-title">${strings.thanksTitle}</div>
        <div class="survey-thanks-text">${thanksText}</div>
        <div class="survey-code-box">
          <div class="survey-code-label">Промокод</div>
          <div class="survey-code">${code}</div>
          <button type="button" class="survey-btn survey-btn-primary survey-copy-btn">${strings.copyCode}</button>
        </div>
        ${authBlock}
      </div>
    `;
    scrollToTop();
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

    // Telegram login: reuse the global verifier exposed via base.html.
    const tgBtn = bodyContainer.querySelector('[data-survey-tg-login]');
    if (tgBtn) {
      tgBtn.addEventListener('click', () => {
        if (window.TelegramVerify && typeof window.TelegramVerify.start === 'function') {
          window.TelegramVerify.start({ purpose: 'login', next: '/cart/' });
        } else {
          window.location.href = loginUrl;
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

    if (question.instruction || question.ui_hint) {
      const hint = document.createElement('div');
      hint.className = 'survey-question-help survey-question-hint';
      hint.textContent = question.instruction || question.ui_hint;
      container.appendChild(hint);
    }

    const optionsWrap = document.createElement('div');
    optionsWrap.className = 'survey-options';

    const renderChoiceCards = (items, choices, descriptionKey = 'description') => {
      const current = isPlainObject(state.answer) ? { ...state.answer } : {};
      const refresh = () => {
        optionsWrap.querySelectorAll('[data-choice-card]').forEach((card) => {
          const key = card.dataset.value;
          card.querySelectorAll('[data-choice]').forEach((button) => {
            button.classList.toggle('selected', current[key] === button.dataset.choice);
          });
        });
      };

      (items || []).forEach((item) => {
        const card = document.createElement('div');
        card.className = 'survey-choice-card';
        card.dataset.choiceCard = '1';
        card.dataset.value = item.value;

        const label = document.createElement('div');
        label.className = 'survey-choice-card-label';
        label.textContent = item.label || item.value;
        card.appendChild(label);

        if (item[descriptionKey]) {
          const desc = document.createElement('div');
          desc.className = 'survey-choice-card-desc';
          desc.textContent = item[descriptionKey];
          card.appendChild(desc);
        }

        const group = document.createElement('div');
        group.className = 'survey-segment-row';
        (choices || []).forEach((choice) => {
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'survey-segment-btn';
          button.dataset.choice = choice;
          button.textContent = choice;
          button.addEventListener('click', () => {
            current[item.value] = choice;
            state.answer = { ...current };
            refresh();
            updateActionButtons();
          });
          group.appendChild(button);
        });
        card.appendChild(group);
        optionsWrap.appendChild(card);
      });
      refresh();
    };

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
    } else if (question.type === 'info_card') {
      state.answer = true;
      const card = document.createElement('div');
      card.className = 'survey-info-card';
      card.textContent = 'Далі покажемо тільки релевантні питання.';
      optionsWrap.appendChild(card);
    } else if (question.type === 'maxdiff_best_worst') {
      const current = isPlainObject(state.answer) ? { ...state.answer } : {};
      const refresh = () => {
        optionsWrap.querySelectorAll('.survey-maxdiff-card').forEach((card) => {
          card.classList.toggle('best-selected', current.best === card.dataset.value);
          card.classList.toggle('worst-selected', current.worst === card.dataset.value);
        });
      };
      (question.options || []).forEach((opt) => {
        const card = document.createElement('div');
        card.className = 'survey-maxdiff-card';
        card.dataset.value = opt.value;

        const label = document.createElement('div');
        label.className = 'survey-maxdiff-label';
        label.textContent = opt.label;
        card.appendChild(label);

        const actions = document.createElement('div');
        actions.className = 'survey-maxdiff-actions';
        [
          ['best', 'Найважливіше'],
          ['worst', 'Найменш важливо'],
        ].forEach(([key, labelText]) => {
          const button = document.createElement('button');
          button.type = 'button';
          button.className = `survey-segment-btn survey-maxdiff-${key}`;
          button.textContent = labelText;
          button.addEventListener('click', () => {
            current[key] = opt.value;
            if (current.best && current.worst && current.best === current.worst) {
              const other = key === 'best' ? 'worst' : 'best';
              delete current[other];
            }
            state.answer = { ...current };
            refresh();
            updateActionButtons();
          });
          actions.appendChild(button);
        });
        card.appendChild(actions);
        optionsWrap.appendChild(card);
      });
      refresh();
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
    } else if (question.type === 'price_ladder_by_product') {
      if (question.price_context) {
        const context = document.createElement('div');
        context.className = 'survey-context-pill';
        context.textContent = question.price_context === 'retail_product' ? 'Роздрібна ціна' : 'Ціна під твій сценарій';
        optionsWrap.appendChild(context);
      }
      (question.options || []).forEach((opt) => {
        const option = document.createElement('button');
        option.type = 'button';
        option.className = 'survey-option survey-price-option';
        option.dataset.value = opt.value;
        option.innerHTML = `<span>${opt.label}</span>`;
        if (state.answer === opt.value) {
          option.classList.add('selected');
        }
        option.addEventListener('click', () => {
          state.answer = opt.value;
          optionsWrap.querySelectorAll('.survey-price-option').forEach((el) => el.classList.remove('selected'));
          option.classList.add('selected');
          updateActionButtons();
        });
        optionsWrap.appendChild(option);
      });
    } else if (question.type === 'concept_reaction_cards' || question.type === 'tap_reaction_cards') {
      renderChoiceCards(question.concepts || [], question.scale_options || []);
    } else if (question.type === 'purchase_intent_matrix') {
      renderChoiceCards(question.rows || [], question.columns || []);
    } else if (question.type === 'budget_allocation_100') {
      const current = isPlainObject(state.answer) ? { ...state.answer } : {};
      const totalLine = document.createElement('div');
      totalLine.className = 'survey-budget-total';

      const refreshTotal = () => {
        const total = Object.values(current).reduce((sum, value) => sum + (parseInt(value, 10) || 0), 0);
        totalLine.textContent = `Розподілено ${total}/100`;
        totalLine.classList.toggle('complete', total === 100);
        state.answer = Object.entries(current).reduce((acc, [key, value]) => {
          const number = parseInt(value, 10) || 0;
          if (number > 0) acc[key] = number;
          return acc;
        }, {});
        updateActionButtons();
      };

      optionsWrap.appendChild(totalLine);
      (question.buckets || []).forEach((bucket) => {
        const row = document.createElement('div');
        row.className = 'survey-budget-row';

        const label = document.createElement('label');
        label.textContent = bucket.label || bucket.value;
        row.appendChild(label);

        const value = document.createElement('span');
        value.className = 'survey-budget-value';
        value.textContent = current[bucket.value] || 0;

        const input = document.createElement('input');
        input.type = 'range';
        input.min = 0;
        input.max = 100;
        input.step = 5;
        input.value = current[bucket.value] || 0;
        input.className = 'survey-slider survey-budget-slider';
        input.addEventListener('input', () => {
          current[bucket.value] = parseInt(input.value, 10) || 0;
          value.textContent = current[bucket.value];
          refreshTotal();
        });

        row.appendChild(value);
        row.appendChild(input);
        optionsWrap.appendChild(row);
      });
      refreshTotal();
    } else if (question.type === 'contact_capture') {
      const current = isPlainObject(state.answer) ? { ...state.answer } : {};
      const channelRow = document.createElement('div');
      channelRow.className = 'survey-segment-row survey-contact-channels';
      (question.channels || []).forEach((channel) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'survey-segment-btn';
        button.textContent = channel;
        button.dataset.channel = channel;
        if (current.channel === channel) button.classList.add('selected');
        button.addEventListener('click', () => {
          current.channel = channel;
          state.answer = { ...current };
          channelRow.querySelectorAll('.survey-segment-btn').forEach((el) => el.classList.remove('selected'));
          button.classList.add('selected');
          updateActionButtons();
        });
        channelRow.appendChild(button);
      });
      const input = document.createElement('input');
      input.className = 'survey-text';
      input.type = 'text';
      input.placeholder = question.placeholder || '';
      input.value = current.value || '';
      input.addEventListener('input', () => {
        current.value = input.value;
        state.answer = { ...current };
        updateActionButtons();
      });
      optionsWrap.appendChild(channelRow);
      optionsWrap.appendChild(input);
    } else {
      const input = document.createElement(question.type === 'text_long' ? 'textarea' : 'input');
      input.className = 'survey-text';
      if (question.type !== 'text_long') {
        input.type = 'text';
      }
      if (question.placeholder) {
        input.placeholder = question.placeholder;
      }
      if (question.max_chars) {
        input.maxLength = parseInt(question.max_chars, 10);
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
    scrollToTop();
    nextBtn.style.display = '';
    skipBtn.style.display = '';
    backBtn.style.display = '';
    updateActionButtons();

    if (!prefersReducedMotion) {
      container.classList.add('reveal-fast');
      requestAnimationFrame(() => {
        container.classList.add('visible');
      });
    } else {
      container.classList.add('visible');
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
      renderThanks(data.promo, !!data.authenticated);
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

  /**
   * Resolve CSRF token: cookie → meta tag → force-set via lightweight GET.
   * Returns a Promise that always resolves to the best available token
   * (empty string in the worst case, which lets Django return a clear 403).
   */
  const resolveCSRFToken = () => {
    const fromCookie = getCookie('csrftoken');
    if (fromCookie) return Promise.resolve(fromCookie);
    // Fallback: some base templates store the token in a <meta> tag.
    const meta = document.querySelector('meta[name="csrf-token"]');
    const fromMeta = meta ? (meta.getAttribute('content') || '') : '';
    if (fromMeta) return Promise.resolve(fromMeta);
    // Last resort: hit the home page (lightweight HEAD) so the server
    // sets the csrftoken cookie, then re-read it.
    return fetch('/', { method: 'HEAD', credentials: 'same-origin' })
      .then(() => getCookie('csrftoken') || '')
      .catch(() => '');
  };

  const startSurvey = () => {
    showLoading();
    openModal();
    resetButtons();
    // If the homepage block reappeared after the previous reward expired,
    // ask the backend for a fresh run so the visitor can earn a new code.
    const wantsRestart = !!(section && section.getAttribute('data-survey-restart') === '1');
    resolveCSRFToken().then((token) => {
      fetch(`${BASE_URL}/start/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': token,
        },
        body: JSON.stringify(wantsRestart ? { restart: true } : {}),
      })
        .then((response) => response.json())
        .then((data) => {
          if (!data) return;
          if (wantsRestart && section) {
            section.removeAttribute('data-survey-restart');
          }
          updateFromResponse(data);
        })
        .catch(() => showError());
    });
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
    startSurvey();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && modal.classList.contains('open')) {
      closeModal();
    }
  });
}
