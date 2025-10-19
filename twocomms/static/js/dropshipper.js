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
      const explicitActive = document.querySelector('[data-tab-panel].is-active')?.dataset.tabPanel;
      const initialTarget = initialParam || explicitActive || tabLinks[0]?.dataset.tabTarget || tabPanels[0].dataset.tabPanel;

      const activateTab = (target, { updateHistory = true } = {}) => {
        if (!target) {
          return;
        }

        const targetPanel = document.querySelector(`[data-tab-panel="${target}"]`);
        if (!targetPanel) {
          return;
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
      };

      tabLinks.forEach((link) => {
        link.addEventListener('click', (event) => {
          const target = event.currentTarget.dataset.tabTarget;
          if (!target) {
            return;
          }

          event.preventDefault();
          activateTab(target);
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

        event.preventDefault();
        activateTab(target);
      });

      document.addEventListener('ds:reload-tab', (event) => {
        const target = event.detail?.target;
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
        activateTab(initialTarget, { updateHistory: false });
      }
    }

    function loadPanel(panel, target) {
      panel.classList.add('is-loading');

      fetch(panel.dataset.tabAutoload, {
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
          console.error('Не вдалося завантажити дані вкладки:', error);
          panel.innerHTML = `
            <div class="ds-panel-error">
              <p>Не вдалося завантажити дані. Спробуйте ще раз.</p>
              <button type="button" class="ds-btn ds-btn--ghost" data-tab-retry>Повторити</button>
            </div>
          `;
          panel.classList.remove('is-loading');
          panel.querySelector('[data-tab-retry]')?.addEventListener('click', () => {
            delete panel.dataset.tabLoaded;
            loadPanel(panel, target);
          });
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

      const animatedBlocks = document.querySelectorAll('[data-animate]:not(.is-animated)');
      if (!animatedBlocks.length) {
        return;
      }

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
          threshold: 0.2,
          rootMargin: '0px 0px -15% 0px',
        },
      );

      animatedBlocks.forEach((block) => observer.observe(block));
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
                  successBadge?.classList.remove('is-visible');
                  successBadge?.setAttribute('hidden', 'hidden');
                }, 3200);
              }

              updateCompanyWidgets(data.profile || {});
              showToast(data.message || 'Дані компанії оновлено');
            })
            .catch((error) => {
              if (error.message !== 'validation') {
                console.error(error);
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
        if (event.detail?.target === 'company') {
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

      document.addEventListener('click', (event) => {
        const trigger = event.target.closest('[data-request-payout]');
        if (!trigger || trigger.disabled) {
          return;
        }

        event.preventDefault();
        payoutForm.reset();
        payoutForm.dataset.reloadTarget = trigger.closest('[data-tab-panel]')?.dataset.tabPanel || 'payouts';
        payoutModal.hidden = false;
        payoutModal.setAttribute('aria-hidden', 'false');
        payoutModal.classList.add('is-open');
        payoutModal.focus();
      });

      payoutForm.addEventListener('submit', (event) => {
        event.preventDefault();

        const submitButton = payoutForm.querySelector('button[type="submit"]');
        submitButton?.setAttribute('disabled', 'disabled');
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
              throw new Error(data.message || 'Не вдалося створити запит на виплату');
            }
            showToast(data.message || 'Запит на виплату створено');
            payoutModal.querySelector('[data-dismiss-modal]')?.click();
            document.dispatchEvent(new CustomEvent('ds:reload-tab', {
              detail: { target: payoutForm.dataset.reloadTarget || 'payouts' },
            }));
          })
          .catch((error) => {
            console.error(error);
            showToast(error.message || 'Не вдалося створити запит на виплату', 'error');
          })
          .finally(() => {
            submitButton?.removeAttribute('disabled');
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
