// Глобальная функция для сброса Telegram (должна быть доступна для onclick)
window.resetDropshipperTelegram = function() {
  
  if (!confirm('Ви впевнені, що хочете відв\'язати Telegram? Вам потрібно буде прив\'язати його заново.')) {
    return;
  }
  
  const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
  
  
  fetch('/accounts/telegram/unlink/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken
    },
    credentials: 'same-origin'
  })
  .then(response => {
    return response.json();
  })
  .then(data => {
    
    if (data.success) {
      
      const buttonContainer = document.querySelector('.telegram-button-container');
      
      if (buttonContainer) {
        
        buttonContainer.innerHTML = `
          <button type="button" class="ds-btn telegram-confirm-btn" onclick="confirmDropshipperTelegram()" style="
            background: linear-gradient(135deg, #8b5cf6, #6366f1) !important;
            border: none !important;
            color: white !important;
            border-radius: 8px !important;
            padding: 10px 16px !important;
            font-weight: 700 !important;
            font-size: 0.85rem !important;
            cursor: pointer !important;
            transition: all 0.2s !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 8px !important;
            white-space: nowrap !important;
            height: 100% !important;
            min-height: 44px !important;
          " onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 8px 20px rgba(139,92,246,.4)'" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='none'">
            <i class="fab fa-telegram"></i>
            <span>Підтвердити</span>
          </button>
        `;
        
      }
      alert('✅ Telegram відв\'язано! Тепер ви можете прив\'язати новий акаунт.');
    } else {
      alert('❌ Помилка при відв\'язуванні Telegram: ' + (data.error || 'Невідома помилка'));
    }
  })
  .catch(error => {
    alert('❌ Помилка при відв\'язуванні Telegram');
  });
};


// Глобальная функция для подтверждения Telegram дропшипера
window.confirmDropshipperTelegram = function() {
  const telegramInput = document.querySelector('input[name="telegram"]');
  let telegramUsername = telegramInput.value.trim();
  
  if (!telegramUsername) {
    alert('Будь ласка, введіть ваш Telegram username');
    return;
  }
  
  // Автоматически добавляем @ если его нет
  if (!telegramUsername.startsWith('@')) {
    telegramUsername = '@' + telegramUsername;
    telegramInput.value = telegramUsername;
  }
  
  // Открываем Telegram бота
  const botUrl = 'https://t.me/twocommsbot?start=' + encodeURIComponent(telegramUsername);
  window.open(botUrl, '_blank');
  
  // Показываем инструкцию
  alert('Відкриється Telegram бот. Напишіть будь-яке повідомлення для підтвердження протягом 5 хвилин. Статус оновиться автоматично.');
  
  // Показываем индикатор загрузки
  showDropshipperTelegramLoadingIndicator();
  
  // Запускаем проверку статуса
  const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
  if (csrfToken) {
    startDropshipperTelegramStatusCheck();
  } else {
    hideDropshipperTelegramLoadingIndicator();
  }
};

// Функция для проверки статуса подтверждения Telegram
function checkDropshipperTelegramStatus() {
  fetch('/accounts/telegram/status/', {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'same-origin'
  })
  .then(response => response.json())
  .then(data => {
    if (data.is_confirmed) {
      // Telegram подтвержден
      hideDropshipperTelegramLoadingIndicator();
      updateDropshipperTelegramButton(true);
      stopDropshipperTelegramStatusCheck();
    }
  })
  .catch(error => {
  });
}

// Запускаем периодическую проверку статуса
let dropshipperTelegramCheckInterval;
function startDropshipperTelegramStatusCheck() {
  checkDropshipperTelegramStatus();
  dropshipperTelegramCheckInterval = setInterval(checkDropshipperTelegramStatus, 5000); // каждые 5 секунд
  
  // Автоматически останавливаем через 5 минут
  setTimeout(stopDropshipperTelegramStatusCheck, 5 * 60 * 1000);
}

function stopDropshipperTelegramStatusCheck() {
  if (dropshipperTelegramCheckInterval) {
    clearInterval(dropshipperTelegramCheckInterval);
    dropshipperTelegramCheckInterval = null;
    hideDropshipperTelegramLoadingIndicator();
  }
}

// Показываем индикатор загрузки
function showDropshipperTelegramLoadingIndicator() {
  const buttonContainer = document.querySelector('.telegram-button-container');
  if (buttonContainer) {
    const existingBtn = buttonContainer.querySelector('.telegram-confirm-btn');
    if (existingBtn) {
      existingBtn.innerHTML = `
        <svg class="spinner" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <circle cx="12" cy="12" r="10" stroke-width="4" stroke-opacity="0.25"/>
          <path d="M12 2a10 10 0 0 1 10 10" stroke-width="4" stroke-linecap="round"/>
        </svg>
        <span>Очікування підтвердження...</span>
      `;
      existingBtn.disabled = true;
      existingBtn.style.opacity = '0.7';
      existingBtn.style.cursor = 'not-allowed';
    }
  }
}

function hideDropshipperTelegramLoadingIndicator() {
  const buttonContainer = document.querySelector('.telegram-button-container');
  if (buttonContainer) {
    const existingBtn = buttonContainer.querySelector('.telegram-confirm-btn');
    if (existingBtn && !existingBtn.classList.contains('confirmed')) {
      existingBtn.innerHTML = `
        <i class="fab fa-telegram"></i>
        <span>Підтвердити Telegram</span>
      `;
      existingBtn.disabled = false;
      existingBtn.style.opacity = '1';
      existingBtn.style.cursor = 'pointer';
    }
  }
}

// Обновляем кнопку после подтверждения
function updateDropshipperTelegramButton(confirmed) {
  const buttonContainer = document.querySelector('.telegram-button-container');
  if (buttonContainer && confirmed) {
    buttonContainer.innerHTML = `
      <button type="button" class="ds-btn" disabled style="
        background: linear-gradient(135deg, #10b981, #059669) !important;
        border: none !important;
        color: white !important;
        border-radius: 8px !important;
        padding: 10px 16px !important;
        font-weight: 700 !important;
        font-size: 0.85rem !important;
        cursor: not-allowed !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 8px !important;
        opacity: 0.7 !important;
        white-space: nowrap !important;
        height: 100% !important;
        min-height: 44px !important;
      ">
        <i class="fas fa-check-circle"></i>
        <span>Telegram підтверджено</span>
      </button>
      <button type="button" class="ds-btn telegram-reset-btn" onclick="resetDropshipperTelegram()" title="Переприв'язати Telegram" style="
        background: linear-gradient(135deg, #ef4444, #dc2626) !important;
        border: none !important;
        color: white !important;
        border-radius: 8px !important;
        padding: 10px 12px !important;
        font-weight: 700 !important;
        font-size: 0.95rem !important;
        cursor: pointer !important;
        transition: all 0.2s !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        height: 100% !important;
        min-height: 44px !important;
      " onmouseover="this.style.transform='scale(1.1)'; this.style.boxShadow='0 4px 12px rgba(239,68,68,.4)'" onmouseout="this.style.transform='scale(1)'; this.style.boxShadow='none'">
        <i class="fas fa-times"></i>
      </button>
    `;
  }
}

// Добавляем стили для spinner
if (!document.getElementById('dropshipper-spinner-styles')) {
  const spinnerStyle = document.createElement('style');
  spinnerStyle.id = 'dropshipper-spinner-styles';
  spinnerStyle.textContent = `
    .spinner {
      animation: spin 1s linear infinite;
    }
    @keyframes spin {
      from { transform: rotate(0deg); }
      to { transform: rotate(360deg); }
    }
  `;
  document.head.appendChild(spinnerStyle);
}


(() => {
  document.addEventListener('DOMContentLoaded', () => {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const csrfTokenMeta = document.querySelector('meta[name="csrf-token"]');
    const csrfToken = csrfTokenMeta ? csrfTokenMeta.getAttribute('content') : '';

    setupTabNavigation();
    setupScrollLinks();
    setupAutoAnimateSections();
    setupCompanyTab();
    setupPayoutRequest();

    function setupTabNavigation() {
      const tabPanels = Array.from(document.querySelectorAll('[data-tab-panel]'));
      if (!tabPanels.length) {
        return;
      }

      const tabLinks = Array.from(document.querySelectorAll('[data-tab-target]'));
      const searchParams = new URLSearchParams(window.location.search);
      const initialParam = searchParams.get('tab');
      const activePanel = document.querySelector('[data-tab-panel].is-active');
      const explicitActive = activePanel ? activePanel.dataset.tabPanel : null;
      const firstTabLink = tabLinks[0];
      const initialTarget = initialParam || explicitActive || (firstTabLink ? firstTabLink.dataset.tabTarget : null) || tabPanels[0].dataset.tabPanel;

      const activateTab = (target, { updateHistory = true } = {}) => {
        if (!target) {
          return false;
        }

        const targetPanel = document.querySelector(`[data-tab-panel="${target}"]`);
        if (!targetPanel) {
          return false;
        }

        tabLinks.forEach((link) => {
          link.classList.toggle('is-active', link.dataset.tabTarget === target);
        });

        tabPanels.forEach((panel) => {
          panel.classList.toggle('is-active', panel === targetPanel);
        });

        if (updateHistory) {
          const params = new URLSearchParams(window.location.search);
          if (target === 'main') {
            params.delete('tab');
          } else {
            params.set('tab', target);
          }
          const query = params.toString();
          const newUrl = `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash}`;
          window.history.replaceState({}, '', newUrl);
        }

        if (targetPanel.dataset.tabAutoload && !targetPanel.dataset.tabLoaded) {
          loadPanel(targetPanel, target);
        } else {
          setupAutoAnimateSections();
        }

        return true;
      };

      tabLinks.forEach((link) => {
        link.addEventListener('click', (event) => {
          const target = event.currentTarget.dataset.tabTarget;
          if (!target) {
            return;
          }

          const handled = activateTab(target);
          if (handled) {
            event.preventDefault();
          }
        });
      });

      document.addEventListener('click', (event) => {
        const link = event.target.closest('[data-tab-link]');
        if (!link) {
          return;
        }

        const target = link.dataset.tabLink;
        if (!target) {
          return;
        }

        const handled = activateTab(target);
        if (handled) {
          event.preventDefault();
        }
      });

      document.addEventListener('ds:reload-tab', (event) => {
        const target = event.detail ? event.detail.target : null;
        if (!target) {
          return;
        }

        const panel = document.querySelector(`[data-tab-panel="${target}"]`);
        if (!panel) {
          return;
        }

        delete panel.dataset.tabLoaded;
        if (panel.classList.contains('is-active')) {
          activateTab(target, { updateHistory: false });
        }
      });

      if (initialTarget) {
        const handled = activateTab(initialTarget, { updateHistory: false });
        if (!handled) {
          const fallback = tabPanels[0];
          if (fallback) {
            activateTab(fallback.dataset.tabPanel, { updateHistory: false });
          }
        }
      }
    }

    function loadPanel(panel, target) {
      panel.classList.add('is-loading');

      fetch(panel.dataset.tabAutoload, {
        credentials: 'same-origin',
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
        },
      })
        .then((response) => {
          if (!response.ok) {
            throw new Error(response.statusText || 'Network error');
          }
          return response.text();
        })
        .then((html) => {
          panel.innerHTML = html;
          panel.dataset.tabLoaded = 'true';
          panel.classList.remove('is-loading');
          setupAutoAnimateSections();
          document.dispatchEvent(new CustomEvent('ds:tabloaded', { detail: { target } }));
        })
        .catch((error) => {
          panel.innerHTML = `
            <div class="ds-panel-error">
              <p>Не вдалося завантажити дані. Спробуйте ще раз.</p>
              <button type="button" class="ds-btn ds-btn--ghost" data-tab-retry>Повторити</button>
            </div>
          `;
          panel.classList.remove('is-loading');
          const retryButton = panel.querySelector('[data-tab-retry]');
          if (retryButton) {
            retryButton.addEventListener('click', () => {
              delete panel.dataset.tabLoaded;
              loadPanel(panel, target);
            });
          }
        });
    }

    function setupScrollLinks() {
      const scrollLinks = document.querySelectorAll('[data-scroll-target]');
      if (!scrollLinks.length) {
        return;
      }

      scrollLinks.forEach((link) => {
        link.addEventListener('click', (event) => {
          const targetId = link.getAttribute('data-scroll-target');
          const target = document.getElementById(targetId);
          if (!target) {
            return;
          }

          event.preventDefault();
          target.scrollIntoView({ behavior: prefersReducedMotion ? 'auto' : 'smooth', block: 'start' });
        });
      });
    }

    function setupAutoAnimateSections() {
      if (prefersReducedMotion) {
        return;
      }

      const animatedBlocks = document.querySelectorAll('[data-animate]:not(.is-animated), [data-animate-early]:not(.is-animated)');
      if (!animatedBlocks.length) {
        return;
      }

      // Для блоков с data-animate-early - большой rootMargin чтобы анимация началась раньше
      const observerEarly = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.classList.add('is-animated');
              entry.target.querySelectorAll('[data-fade]').forEach((child) => {
                const delay = Number(child.dataset.delay || 0);
                child.style.setProperty('--ds-fade-delay', `${delay}ms`);
                child.classList.add('is-revealed');
              });
              observerEarly.unobserve(entry.target);
            }
          });
        },
        {
          threshold: 0.05,
          rootMargin: '300px 0px 0px 0px', // Начинаем анимацию за 300px до появления блока
        },
      );

      // Для обычных блоков - стандартный threshold
      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.classList.add('is-animated');
              entry.target.querySelectorAll('[data-fade]').forEach((child) => {
                const delay = Number(child.dataset.delay || 0);
                child.style.setProperty('--ds-fade-delay', `${delay}ms`);
                child.classList.add('is-revealed');
              });
              observer.unobserve(entry.target);
            }
          });
        },
        {
          threshold: 0.05,
          rootMargin: '0px 0px 0px 0px',
        },
      );

      // Применяем соответствующий observer
      animatedBlocks.forEach((block) => {
        if (block.hasAttribute('data-animate-early')) {
          observerEarly.observe(block);
        } else {
          observer.observe(block);
        }
      });
    }

    function setupCompanyTab() {
      const bindPanel = (panel) => {
        if (!panel) {
          return;
        }

        const form = panel.querySelector('[data-company-form]');
        if (!form || form.dataset.bound === 'true') {
          return;
        }

        form.dataset.bound = 'true';

        const submitButton = form.querySelector('[data-company-submit]');
        const successBadge = panel.querySelector('[data-company-success]');

        const showErrors = (errors = {}) => {
          form.querySelectorAll('[data-field-error]').forEach((node) => {
            const fieldName = node.dataset.fieldError;
            const messages = errors[fieldName];
            node.textContent = messages ? messages.join(' ') : '';
            if (messages && messages.length) {
              node.removeAttribute('hidden');
            } else {
              node.setAttribute('hidden', 'hidden');
            }
          });
        };

        form.addEventListener('submit', (event) => {
          event.preventDefault();
          const formData = new FormData(form);

          if (submitButton) {
            submitButton.setAttribute('disabled', 'disabled');
          }
          showErrors();

          fetch(form.action, {
            method: 'POST',
            headers: {
              'X-CSRFToken': csrfToken,
              'X-Requested-With': 'XMLHttpRequest',
            },
            body: formData,
          })
            .then((response) => response.json())
            .then((data) => {
              if (!data.success) {
                showErrors(data.errors);
                throw new Error('validation');
              }

              if (successBadge) {
                successBadge.removeAttribute('hidden');
                successBadge.classList.add('is-visible');
                window.setTimeout(() => {
                  if (successBadge) {
                    successBadge.classList.remove('is-visible');
                    successBadge.setAttribute('hidden', 'hidden');
                  }
                }, 3200);
              }

              updateCompanyWidgets(data.profile || {});
              showToast(data.message || 'Дані компанії оновлено');
            })
            .catch((error) => {
              if (error.message !== 'validation') {
                showToast('Не вдалося зберегти дані компанії', 'error');
              }
            })
            .finally(() => {
              if (submitButton) {
                submitButton.removeAttribute('disabled');
              }
            });
        });
      };

      const companyPanel = document.querySelector('[data-tab-panel="company"]');
      if (companyPanel && companyPanel.dataset.tabLoaded === 'true') {
        bindPanel(companyPanel);
      }

      document.addEventListener('ds:tabloaded', (event) => {
        if (event.detail && event.detail.target === 'company') {
          bindPanel(document.querySelector('[data-tab-panel="company"]'));
        }
      });
    }

    function setupPayoutRequest() {
      const payoutModal = document.getElementById('ds-payout-modal');
      const payoutForm = document.getElementById('ds-payout-form');
      if (!payoutModal || !payoutForm) {
        return;
      }

      document.addEventListener('click', async (event) => {
        const trigger = event.target.closest('[data-request-payout]');
        if (!trigger || trigger.disabled) {
          return;
        }

        event.preventDefault();
        payoutForm.reset();
        
        // Загружаем данные профиля для автозаполнения
        try {
          const response = await fetch('/orders/dropshipper/company/?partial=1', {
            headers: {
              'X-Requested-With': 'XMLHttpRequest',
            },
          });
          
          if (response.ok) {
            const html = await response.text();
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            
            // Получаем payment_method из формы компании
            const paymentMethodField = doc.querySelector('#id_payment_method, select[name="payment_method"]');
            const paymentDetailsField = doc.querySelector('#id_payment_details, input[name="payment_details"], textarea[name="payment_details"]');
            
            if (paymentMethodField && paymentMethodSelect) {
              const savedMethod = paymentMethodField.value || 'card';
              paymentMethodSelect.value = savedMethod;
              
              // Обновляем форму под выбранный метод
              const changeEvent = new Event('change');
              paymentMethodSelect.dispatchEvent(changeEvent);
            }
            
            if (paymentDetailsField && detailsInput) {
              detailsInput.value = paymentDetailsField.value || '';
            }
          }
        } catch (error) {
        }
        
        const parentPanel = trigger.closest('[data-tab-panel]');
        payoutForm.dataset.reloadTarget = parentPanel && parentPanel.dataset.tabPanel ? parentPanel.dataset.tabPanel : 'payouts';
        payoutModal.hidden = false;
        payoutModal.setAttribute('aria-hidden', 'false');
        payoutModal.classList.add('is-open');
        payoutModal.focus();
      });

      // Обработчик смены способа выплаты
      const paymentMethodSelect = payoutForm.querySelector('#ds-payout-method');
      const detailsLabel = payoutForm.querySelector('#ds-payout-details-label');
      const detailsInput = payoutForm.querySelector('#ds-payout-details');
      const detailsHint = payoutForm.querySelector('#ds-payout-hint');
      
      if (paymentMethodSelect && detailsLabel && detailsInput && detailsHint) {
        paymentMethodSelect.addEventListener('change', () => {
          const method = paymentMethodSelect.value;
          
          if (method === 'card') {
            detailsLabel.textContent = 'Номер картки';
            detailsInput.placeholder = '1234 5678 9012 3456';
            detailsHint.textContent = '16 цифр картки без пробілів або з пробілами';
          } else if (method === 'iban') {
            detailsLabel.textContent = 'IBAN';
            detailsInput.placeholder = 'UA123456789012345678901234567';
            detailsHint.textContent = 'Міжнародний номер банківського рахунку (29 символів для України)';
          }
        });
      }

      payoutForm.addEventListener('submit', (event) => {
        event.preventDefault();

        const submitButton = payoutForm.querySelector('button[type="submit"]');
        if (submitButton) {
          submitButton.setAttribute('disabled', 'disabled');
        }
        payoutForm.classList.add('is-loading');

        const formData = new FormData(payoutForm);
        const payload = {
          payment_method: formData.get('payment_method'),
          payment_details: formData.get('payment_details'),
          notes: formData.get('notes'),
        };

        fetch('/orders/dropshipper/api/request-payout/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest',
          },
          body: JSON.stringify(payload),
        })
          .then((response) => response.json())
          .then((data) => {
            if (!data.success) {
              throw new Error(data.error || data.message || 'Не вдалося створити запит на виплату');
            }
            showToast(data.message || 'Запит на виплату створено');
            const dismissTrigger = payoutModal.querySelector('[data-dismiss-modal]');
            if (dismissTrigger) {
              dismissTrigger.click();
            }
            document.dispatchEvent(new CustomEvent('ds:reload-tab', {
              detail: { target: payoutForm.dataset.reloadTarget || 'payouts' },
            }));
          })
          .catch((error) => {
            showToast(error.message || 'Не вдалося створити запит на виплату', 'error');
          })
          .finally(() => {
            if (submitButton) {
              submitButton.removeAttribute('disabled');
            }
            payoutForm.classList.remove('is-loading');
          });
      });
    }

    function updateCompanyWidgets(profile) {
      const summaryHeader = document.querySelector('[data-company-summary]');
      if (summaryHeader) {
        const nameEl = summaryHeader.querySelector('[data-company-summary-name]');
        if (nameEl) {
          nameEl.textContent = profile.company_name || 'Компанія ще не заповнена';
        }

        const statusEl = summaryHeader.querySelector('[data-company-summary-status]');
        if (statusEl) {
          const isFilled = Boolean(profile.company_name);
          statusEl.classList.toggle('ds-badge--success', isFilled);
          statusEl.classList.toggle('ds-badge--warning', !isFilled);
          statusEl.innerHTML = isFilled
            ? '<i class="fas fa-circle-check" aria-hidden="true"></i> Актуально'
            : '<i class="fas fa-pen" aria-hidden="true"></i> Потрібно заповнити';
        }

        summaryHeader.querySelectorAll('[data-company-summary-field]').forEach((node) => {
          const key = node.dataset.companySummaryField;
          let value = profile[key] || '—';

          if (key === 'website' && profile.website) {
            value = `<a href="${profile.website}" target="_blank" rel="noopener" class="ds-link">${profile.website}</a>`;
          }

          if (key === 'instagram' && profile.instagram) {
            const href = profile.instagram.startsWith('http') ? profile.instagram : `https://instagram.com/${profile.instagram.replace('@', '')}`;
            value = `<a href="${href}" target="_blank" rel="noopener" class="ds-link">${profile.instagram}</a>`;
          }

          if (key === 'email' && profile.email) {
            value = `<a href="mailto:${profile.email}" class="ds-link">${profile.email}</a>`;
          }

          if (key === 'payment_details' && profile.payment_details) {
            value = profile.payment_details.replace(/\n/g, '<br>');
          }

          node.innerHTML = value || '—';
        });
      }

      const sidebar = document.querySelector('[data-company-sidebar]');
      if (sidebar) {
        const name = sidebar.querySelector('[data-company-sidebar-name]');
        if (name) {
          name.textContent = profile.company_name || 'Створіть компанію';
        }

        const status = sidebar.querySelector('[data-company-sidebar-status]');
        if (status) {
          const isFilled = Boolean(profile.company_name);
          status.classList.toggle('ds-sidebar__company-status--ok', isFilled);
          status.classList.toggle('ds-sidebar__company-status--warn', !isFilled);
          status.innerHTML = isFilled
            ? '<i class="fas fa-circle-check" aria-hidden="true"></i> Актуально'
            : '<i class="fas fa-pen" aria-hidden="true"></i> Заповніть дані';
        }

        const phonePill = sidebar.querySelector('[data-company-sidebar-phone]');
        if (phonePill) {
          phonePill.innerHTML = `<i class="fas fa-phone" aria-hidden="true"></i>${profile.phone || ''}`;
        }

        const tags = sidebar.querySelector('[data-company-sidebar-tags]');
        const linkPill = sidebar.querySelector('[data-company-sidebar-link]');
        if (tags && linkPill) {
          if (profile.website) {
            linkPill.innerHTML = `<i class="fas fa-globe" aria-hidden="true"></i>${profile.website}`;
            linkPill.removeAttribute('hidden');
          } else if (profile.instagram) {
            linkPill.innerHTML = `<i class="fab fa-instagram" aria-hidden="true"></i>${profile.instagram}`;
            linkPill.removeAttribute('hidden');
          } else {
            linkPill.setAttribute('hidden', 'hidden');
          }
        }
      }
    }

    function showToast(message, type = 'success') {
      if (typeof window.dsShowToast === 'function') {
        window.dsShowToast(message, type);
        return;
      }

      let toast = document.querySelector('.ds-toast');
      if (!toast) {
        toast = document.createElement('div');
        toast.className = 'ds-toast';
        document.body.appendChild(toast);
      }

      toast.textContent = message;
      toast.dataset.type = type;
      toast.classList.remove('is-visible');
      requestAnimationFrame(() => {
        toast.classList.add('is-visible');
      });
      setTimeout(() => {
        toast.classList.remove('is-visible');
      }, 4000);
    }
  });
})();

// Старый обработчик удален - теперь используется модальное окно (см. выше)

function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}
