import { getCookie } from './shared.js';

const CART_EMPTY_TEMPLATE = `
  <div class="cart-empty">
    <div class="cart-empty-icon">
      <svg width="64" height="64" viewBox="0 0 24 24" fill="currentColor">
        <path d="M7 18c-1.1 0-1.99.9-1.99 2S5.9 22 7 22s2-.9 2-2-.9-2-2-2zM1 2v2h2l3.6 7.59-1.35 2.45c-.16.28-.25.61-.25.96 0 1.1.9 2 2 2h12v-2H7.42c-.14 0-.25-.11-.25-.25l.03-.12L8.1 13h7.45c.75 0 1.41-.41 1.75-1.03L21.7 4H5.21l-.94-2H1zm16 16c-1.1 0-1.99.9-1.99 2s.89 2 1.99 2 2-.9 2-2-.9-2-2-2z"/>
      </svg>
    </div>
    <h2 class="cart-empty-title">Кошик порожній</h2>
    <p class="cart-empty-text">Додайте товари до кошика, щоб зробити замовлення</p>
    <a href="/" class="cart-empty-btn">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88Л12 17.77л-6.18 3.25Л7 14.14 2 9.27л6.91-1.01Л12 2z"/>
      </svg>
      Перейти до покупок
    </a>
  </div>
`;

const NOOP = () => {};

const getCsrfToken = () =>
  document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
  document.querySelector('input[name="csrfmiddlewaretoken"]')?.value ||
  getCookie('csrftoken') ||
  '';

const parseNumber = (raw) => {
  if (raw === null || raw === undefined) {
    return 0;
  }

  const cleaned = String(raw)
    .replace(/\u00A0/g, '') // nbsp
    .replace(/\s/g, '')
    .replace(/,/g, '.')
    .replace(/[^\d.-]/g, '');

  const parsed = Number.parseFloat(cleaned);
  return Number.isFinite(parsed) ? parsed : 0;
};

const formatUAH = (amount) => {
  const value = Number.isFinite(amount) ? amount : 0;
  const isInt = Math.abs(value % 1) < 1e-9;
  const options = isInt
    ? { minimumFractionDigits: 0, maximumFractionDigits: 0 }
    : { minimumFractionDigits: 2, maximumFractionDigits: 2 };
  return `${value.toLocaleString('uk-UA', options)} грн`;
};

const toggleElement = (el, show) => {
  if (!el) {
    return;
  }
  el.classList[show ? 'remove' : 'add']('d-none');
};

class CartPageController {
  constructor(root) {
    this.root = root;
    this.cartList = root.querySelector('#cart-list');
    this.cartMainSection = root.querySelector('.cart-main-section');
    this.subtotalValueEl = root.querySelector('#cart-subtotal-value');
    this.itemsLabelEl = root.querySelector('#cart-items-label');
    this.discountRow = root.querySelector('#cart-discount-row');
    this.discountValueEl = root.querySelector('#cart-discount-value');
    this.siteDiscountRow = root.querySelector('#cart-site-discount-row');
    this.siteDiscountValueEl = root.querySelector('#cart-site-discount-value');
    this.payNowAmountEl = root.querySelector('#pay-now-amount');
    this.payNowLabelEl = root.querySelector('#pay-now-label');
    this.prepayRow = root.querySelector('#prepay-remaining-row');
    this.prepayAmountEl = root.querySelector('#prepay-remaining-amount');
    this.prepayNote = root.querySelector('#prepay-note');
    this.payTypeSelect = root.querySelector('#pay_type_auth') || root.querySelector('#pay_type_guest');
    this.placeOrderBtn = root.querySelector('#placeOrderBtn');
    this.guestOrderBtn = root.querySelector('#guestOrderBtn');
    this.pointsSummary = root.querySelector('#cart-points-summary');
    this.pointsEarnedBox = root.querySelector('#cart-points-earned');
    this.pointsAmountEl = root.querySelector('#cart-points-amount');
    this.pointsNoneBox = root.querySelector('#cart-points-none');
    this.savingsInfoEl = root.querySelector('#cart-savings-info');
    this.savingsSiteLine = root.querySelector('#cart-savings-site');
    this.savingsSiteAmountEl = root.querySelector('#cart-savings-site-amount');
    this.savingsPromoLine = root.querySelector('#cart-savings-promo');
    this.savingsPromoCodeEl = root.querySelector('#cart-savings-promo-code');
    this.savingsPromoAmountEl = root.querySelector('#cart-savings-promo-amount');
    this.savingsTotalEl = root.querySelector('#cart-savings-total');
    this.savingsTotalAmountEl = root.querySelector('#cart-savings-total-amount');
    this.checkoutPayloadEl = root.querySelector('#checkout-payload');
    this.promoAppliedDiscountEl = root.querySelector('.cart-promo-applied-discount');
    this.placeholderImage = this.cartList?.dataset.placeholder || '';
    this.prepayValue = parseNumber(this.payNowAmountEl?.dataset.prepay || 200) || 200;
    this.itemsEndpoint = root.dataset.cartItemsUrl || '/cart/items/';
    this.summaryEndpoint = root.dataset.cartSummaryUrl || '/cart/summary/';
    this.contactUrl = root.dataset.contactUrl || '/cart/contact-manager/';
    this.state = null;
    this.syncTimer = null;
    this.requestController = null;
    this.handleCartEvent = this.handleCartEvent.bind(this);
    this.handleRefreshSummary = this.handleRefreshSummary.bind(this);
  }

  init() {
    this.setupPayTypeControls();
    this.setupCartListeners();
    this.setupRefreshSummaryHook();
    this.setupContactModal();
    this.updateOrderButtonText(this.getCurrentPayType());
    this.updatePaymentSummary(this.getCurrentPayType());
    this.requestSync(0);
  }

  destroy() {
    document.removeEventListener('cartUpdated', this.handleCartEvent);
  }

  handleCartEvent() {
    this.requestSync(80);
  }

  handleRefreshSummary(originalPromise) {
    this.requestSync(0);
    return originalPromise;
  }

  setupCartListeners() {
    document.addEventListener('cartUpdated', this.handleCartEvent);
  }

  setupRefreshSummaryHook() {
    if (typeof window.refreshCartSummary !== 'function') {
      return;
    }
    const originalRefresh = window.refreshCartSummary;
    const controller = this;
    window.refreshCartSummary = function overriddenRefresh(...args) {
      const result = originalRefresh.apply(this, args);
      controller.requestSync(0);
      if (result && typeof result.then === 'function') {
        return result.then((value) => {
          controller.requestSync(0);
          return value;
        });
      }
      return result;
    };
  }

  getCurrentPayType() {
    return this.payTypeSelect?.value || 'online_full';
  }

  setupPayTypeControls() {
    if (!this.payTypeSelect) {
      return;
    }
    this.payTypeSelect.addEventListener('change', () => {
      const payType = this.getCurrentPayType();
      this.updateOrderButtonText(payType);
      this.updatePaymentSummary(payType);
    });
  }

  updateOrderButtonText(payType) {
    const activeBtn = this.placeOrderBtn || this.guestOrderBtn;
    if (!activeBtn) {
      return;
    }
    const textSpan = activeBtn.querySelector('span') || activeBtn;
    let text = '';
    switch (payType) {
      case 'online_full':
        text = 'Перейти до оплати';
        break;
      case 'prepay_200':
        text = 'Внести передплату 200 грн';
        break;
      default:
        text = this.placeOrderBtn ? 'Оформити замовлення' : 'Замовити як гість';
    }
    textSpan.textContent = text;
  }

  requestSync(delay) {
    clearTimeout(this.syncTimer);
    this.syncTimer = window.setTimeout(() => {
      this.syncTimer = null;
      this.sync();
    }, delay);
  }

  async sync() {
    if (this.requestController) {
      this.requestController.abort();
    }
    const controller = new AbortController();
    this.requestController = controller;

    try {
      const response = await fetch(this.itemsEndpoint, {
        method: 'GET',
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'Cache-Control': 'no-cache',
        },
        cache: 'no-store',
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`Cart sync failed with status ${response.status}`);
      }

      const data = await response.json();
      if (controller.signal.aborted) {
        return;
      }
      this.requestController = null;

      if (data && data.ok) {
        this.applyState(data);
      }
    } catch (error) {
      if (error.name === 'AbortError') {
        return;
      }
      console.error('Cart sync error:', error);
      this.requestController = null;
    }
  }

  applyState(data) {
    this.state = data;

    this.renderItems(Array.isArray(data.items) ? data.items : []);
    this.updateSummary(data);
    this.updatePaymentSummary(this.getCurrentPayType(), data);
    this.updatePoints(data);
    this.updateCheckoutPayload(data);
    this.updatePromoDiscount(data);

    if (typeof window.updateCartBadge === 'function') {
      const badgeCount = data.items_count ?? data.cart_count ?? 0;
      window.updateCartBadge(badgeCount);
    }
  }

  renderItems(items) {
    if (!this.cartMainSection) {
      return;
    }

    if (!items.length) {
      this.cartMainSection.innerHTML = CART_EMPTY_TEMPLATE;
      return;
    }

    if (!this.cartList) {
      const container = document.createElement('div');
      container.className = 'cart-items-container';
      container.id = 'cart-list';
      this.cartMainSection.appendChild(container);
      this.cartList = container;
    }

    const placeholder = this.placeholderImage || '';
    const rows = items.map((item) => this.renderItem(item, placeholder)).join('');
    this.cartList.innerHTML = rows;
  }

  renderItem(item, placeholder) {
    const imageUrl = item.image_url || placeholder || '';
    const size = item.size || '—';
    const qty = Number(item.qty || 0);
    const unitPrice = parseNumber(item.unit_price);
    const originalUnitPrice = parseNumber(
      item.original_unit_price !== undefined ? item.original_unit_price : item.unit_price
    );
    const lineTotal = parseNumber(item.line_total);
    const hasSiteDiscount = originalUnitPrice > unitPrice + 0.009;
    const points = Number(item.points_reward || 0) * qty;
    const colorLabel = item.color_label || '—';
    const hasColor = Boolean(item.color_variant_id);
    const priceHtml = hasSiteDiscount
      ? `<span class="cart-item-price-old">${formatUAH(originalUnitPrice)}</span><span class="cart-item-price-current">${formatUAH(unitPrice)}</span>`
      : `<span class="cart-item-price-current">${formatUAH(unitPrice)}</span>`;

    return `
      <div class="cart-item" data-cart-row data-key="${item.key}" data-offer-id="${item.offer_id || ''}">
        <div class="cart-item-sparks">
          <div class="cart-item-spark cart-item-spark-1"></div>
          <div class="cart-item-spark cart-item-spark-2"></div>
          <div class="cart-item-spark cart-item-spark-3"></div>
        </div>
        <div class="cart-item-image">
          <img src="${imageUrl}" alt="${item.product_title || 'Товар TwoComms'}" class="cart-item-img" width="80" height="80">
          <div class="cart-item-image-glow"></div>
        </div>
        <div class="cart-item-info">
          <h3 class="cart-item-title">${item.product_title || ''}</h3>
          <div class="cart-item-details">
            <div class="cart-item-detail">
              <span class="cart-item-label">Розмір:</span>
              <span class="cart-item-value">${size}</span>
            </div>
            <div class="cart-item-detail">
              <span class="cart-item-label">Кількість:</span>
              <span class="cart-item-value">${qty}</span>
            </div>
            ${hasColor ? `
            <div class="cart-item-detail">
              <span class="cart-item-label">Колір:</span>
              <div class="cart-item-color d-flex align-items-center gap-2">
                <span class="cart-item-swatch swatch" data-primary="#000"></span>
                <span class="cart-item-color-name">${colorLabel}</span>
              </div>
            </div>` : ''}
          </div>
          <div class="cart-item-price">
            <span class="cart-item-price-label">Ціна:</span>
            <span class="cart-item-price-value">${priceHtml}</span>
          </div>
          ${points > 0 ? `
          <div class="cart-item-points">
            <div class="cart-item-points-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77л-6.18 3.25Л7 14.14 2 9.27л6.91-1.01Л12 2z"/>
              </svg>
            </div>
            <span class="cart-item-points-text">Заробите ${points} балів</span>
          </div>` : ''}
        </div>
        <div class="cart-item-actions">
          <div class="cart-item-total">
            <span class="cart-item-total-label">Разом:</span>
            <span class="cart-item-total-value">${formatUAH(lineTotal)}</span>
          </div>
          <button type="button" class="cart-item-remove-btn" data-key="${item.key}">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5л-1-1h-5л-1 1H5v2h14V4z"/>
            </svg>
            Видалити
          </button>
        </div>
      </div>
    `;
  }

  updateSummary(data) {
    // Используем original_subtotal (сумма без скидок) для отображения суммы товаров
    const subtotal = parseNumber(data.original_subtotal || data.subtotal);
    if (this.subtotalValueEl) {
      this.subtotalValueEl.textContent = formatUAH(subtotal);
    }

    const itemsCount = Number.isFinite(data.items_count)
      ? Number(data.items_count)
      : Array.isArray(data.items)
        ? data.items.reduce((acc, item) => acc + Number(item.qty || 0), 0)
        : 0;

    if (this.itemsLabelEl) {
      this.itemsLabelEl.textContent = `Товари (${itemsCount}):`;
    }

    const promoDiscount = parseNumber(data.discount);
    const hasPromoDiscount = promoDiscount > 0;
    if (this.discountRow) {
      toggleElement(this.discountRow, hasPromoDiscount);
    }
    if (this.discountValueEl) {
      this.discountValueEl.textContent = hasPromoDiscount
        ? `-${formatUAH(promoDiscount)}`
        : '-0 грн';
    }

    const siteDiscount = parseNumber(data.site_discount_total);
    const hasSiteDiscount = siteDiscount > 0;
    if (this.siteDiscountRow) {
      toggleElement(this.siteDiscountRow, hasSiteDiscount);
    }
    if (this.siteDiscountValueEl) {
      this.siteDiscountValueEl.textContent = hasSiteDiscount
        ? `-${formatUAH(siteDiscount)}`
        : '-0 грн';
    }

    const totalSavingsRaw = parseNumber(data.total_savings);
    const savingsTotal = totalSavingsRaw > 0 ? totalSavingsRaw : siteDiscount + promoDiscount;
    const hasSavings = hasSiteDiscount || hasPromoDiscount;

    if (this.savingsInfoEl) {
      toggleElement(this.savingsInfoEl, hasSavings);
    }
    if (this.savingsSiteLine) {
      toggleElement(this.savingsSiteLine, hasSiteDiscount);
    }
    if (this.savingsSiteAmountEl) {
      this.savingsSiteAmountEl.textContent = formatUAH(siteDiscount);
    }
    if (this.savingsPromoLine) {
      toggleElement(this.savingsPromoLine, hasPromoDiscount);
    }
    if (this.savingsPromoAmountEl) {
      this.savingsPromoAmountEl.textContent = formatUAH(promoDiscount);
    }
    if (this.savingsPromoCodeEl) {
      this.savingsPromoCodeEl.textContent = data.applied_promo || '';
    }
    if (this.savingsTotalEl) {
      toggleElement(this.savingsTotalEl, hasSavings);
    }
    if (this.savingsTotalAmountEl) {
      this.savingsTotalAmountEl.textContent = formatUAH(Math.max(savingsTotal, 0));
    }
  }

  updatePaymentSummary(payType, state = this.state) {
    if (!this.payNowAmountEl || !state) {
      return;
    }

    const total = Math.max(parseNumber(state.total ?? state.grand_total), 0);
    const isPrepay = payType === 'prepay_200';
    const payNow = isPrepay ? Math.min(this.prepayValue, total) : total;
    const remaining = isPrepay ? Math.max(total - payNow, 0) : 0;

    this.payNowAmountEl.dataset.total = total.toFixed(2);
    this.payNowAmountEl.textContent = formatUAH(payNow);

    if (this.payNowLabelEl) {
      this.payNowLabelEl.textContent = isPrepay ? 'До сплати зараз:' : 'До сплати:';
    }

    toggleElement(this.prepayRow, isPrepay);
    toggleElement(this.prepayNote, isPrepay);
    if (this.prepayAmountEl) {
      this.prepayAmountEl.textContent = formatUAH(remaining);
    }

    window.paymentSummary = {
      total,
      prepay: this.prepayValue,
      pay_now: payNow,
      remaining,
    };
  }

  updatePoints(data) {
    if (!this.pointsSummary) {
      return;
    }
    const points = Number(data.total_points || 0);
    toggleElement(this.pointsEarnedBox, points > 0);
    toggleElement(this.pointsNoneBox, points <= 0);

    if (this.pointsAmountEl) {
      this.pointsAmountEl.textContent = `+${points} балів`;
    }
  }

  updateCheckoutPayload(data) {
    if (!this.checkoutPayloadEl) {
      return;
    }

    const items = Array.isArray(data.items) ? data.items : [];
    const ids = items.map((item) => item.offer_id).filter(Boolean);
    const contents = items.map((item) => ({
      id: item.offer_id,
      quantity: item.qty || 0,
      item_price: parseNumber(item.unit_price),
      item_name: item.product_title || '',
      item_category: item.product_category || '',
      brand: 'TwoComms',
    }));

    const encodedIds = encodeURIComponent(JSON.stringify(ids));
    const encodedContents = encodeURIComponent(JSON.stringify(contents));
    const total = parseNumber(data.total ?? data.grand_total);
    const itemsCount = Number.isFinite(data.items_count)
      ? Number(data.items_count)
      : contents.reduce((acc, item) => acc + Number(item.quantity || 0), 0);

    this.checkoutPayloadEl.setAttribute('data-ids', encodedIds);
    this.checkoutPayloadEl.setAttribute('data-contents', encodedContents);
    this.checkoutPayloadEl.setAttribute('data-value', total.toFixed(2));
    this.checkoutPayloadEl.setAttribute('data-num-items', String(itemsCount));
  }

  updatePromoDiscount(data) {
    if (!this.promoAppliedDiscountEl) {
      return;
    }
    const discount = parseNumber(data.discount);
    if (discount > 0) {
      this.promoAppliedDiscountEl.textContent = `Знижка: -${formatUAH(discount)}`;
    } else {
      this.promoAppliedDiscountEl.textContent = '';
    }
  }

  setupContactModal() {
    // Модальное окно находится в {% block modals %}, который рендерится ВНЕ .cart-page-container
    const modal = document.querySelector('#contactManagerModal');
    // Кнопки находятся внутри .cart-page-container
    const triggers = this.root.querySelectorAll('.btn-contact-manager');
    if (!modal || !triggers.length) {
      return;
    }

    const closeBtn = modal.querySelector('.contact-modal-close');
    const form = modal.querySelector('#contactManagerForm');
    const body = document.body;
    const closeModal = () => {
      modal.classList.remove('modal-active');
      body.classList.remove('contact-modal-open');
      modal.setAttribute('aria-hidden', 'true');
      setTimeout(() => {
        modal.style.display = 'none';
        body.style.overflow = '';
      }, 250);
    };

    const fillFromForms = () => {
      const deliveryForm = this.root.querySelector('#deliveryForm');
      const guestForm = this.root.querySelector('#guest-form');
      const sourceForm = deliveryForm || guestForm;
      if (!sourceForm) {
        return;
      }

      const fullName = sourceForm.querySelector('[name="full_name"]')?.value || '';
      const phone = sourceForm.querySelector('[name="phone"]')?.value || '';

      const fullNameInput = modal.querySelector('#contactModalFullName');
      const phoneInput = modal.querySelector('#contactModalPhone');

      if (fullNameInput) {
        fullNameInput.value = fullName;
      }
      if (phoneInput) {
        phoneInput.value = phone;
      }
    };

    const openModal = () => {
      fillFromForms();
      modal.style.display = 'flex';
      modal.setAttribute('aria-hidden', 'false');
      body.classList.add('contact-modal-open');
      body.style.overflow = 'hidden';
      window.requestAnimationFrame(() => modal.classList.add('modal-active'));
    };

    triggers.forEach((btn) => {
      btn.addEventListener('click', (event) => {
        event.preventDefault();
        openModal();
      });
    });

    if (closeBtn) {
      closeBtn.addEventListener('click', (event) => {
        event.preventDefault();
        closeModal();
      });
    }

    modal.addEventListener('click', (event) => {
      if (event.target === modal) {
        closeModal();
      }
    });

    if (form) {
      form.addEventListener('submit', async (event) => {
        event.preventDefault();

        const formData = new FormData(form);
        const submitBtn = form.querySelector('button[type="submit"]');
        const originalText = submitBtn ? submitBtn.textContent : '';

        if (submitBtn) {
          submitBtn.disabled = true;
          submitBtn.textContent = 'Відправляємо...';
        }

        try {
          const response = await fetch(this.contactUrl, {
            method: 'POST',
            headers: { 'X-CSRFToken': getCsrfToken() },
            body: formData,
          });
          const data = await response.json();
          if (data.success) {
            alert('✅ Дякуємо! Менеджер зв\'яжеться з вами найближчим часом.');
            form.reset();
            closeModal();
          } else {
            alert(`❌ Помилка: ${data.error || 'Спробуйте ще раз'}`);
          }
        } catch (error) {
          console.error('Contact manager error:', error);
          alert('❌ Помилка з\'єднання. Спробуйте ще раз.');
        } finally {
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
          }
        }
      });
    }
  }
}

function showPromoMessage(msgBox, message, type) {
  if (!msgBox) {
    return;
  }
  const typeClass = type === 'success'
    ? 'cart-promo-message-success'
    : type === 'error'
      ? 'cart-promo-message-error'
      : 'cart-promo-message-info';
  msgBox.innerHTML = `<div class="cart-promo-message ${typeClass}">${message}</div>`;
  window.setTimeout(() => {
    try {
      msgBox.innerHTML = '';
    } catch (error) {
      console.error(error);
    }
  }, 5000);
}

function applyPromoCode(promoInput, msgBox) {
  const code = (promoInput.value || '').trim().toUpperCase();
  if (!code) {
    showPromoMessage(msgBox, 'Введіть код промокоду', 'error');
    return;
  }

  showPromoMessage(msgBox, 'Застосовуємо промокод...', 'info');
  fetch('/cart/apply-promo/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
      'X-CSRFToken': getCsrfToken(),
    },
    body: `promo_code=${encodeURIComponent(code)}`,
  })
    .then((r) => r.json())
    .then((data) => {
      if (data && data.success) {
        showPromoMessage(msgBox, data.message || 'Застосовано', 'success');
        window.setTimeout(() => window.location.reload(), 800);
      } else if (data && data.auth_required) {
        // Особлива обробка для незареєстрованих користувачів
        const authMessage = data.message || 'Промокоди доступні тільки для зареєстрованих користувачів';
        showPromoMessage(msgBox, authMessage, 'error');
        // Показуємо модальне вікно з пропозицією авторизуватися
        setTimeout(() => {
          if (confirm(authMessage + '.\n\nПерейти до авторизації?')) {
            window.location.href = '/login/';
          }
        }, 800);
      } else {
        showPromoMessage(msgBox, (data && (data.error || data.message)) || 'Помилка', 'error');
      }
    })
    .catch(() => showPromoMessage(msgBox, 'Помилка при застосуванні', 'error'));
}

function removePromoCode(msgBox) {
  fetch('/cart/remove-promo/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
      'X-CSRFToken': getCsrfToken(),
    },
  })
    .then((r) => r.json())
    .then(() => window.location.reload())
    .catch(() => showPromoMessage(msgBox, 'Не вдалося видалити промокод', 'error'));
}

function setupCartValidation(form) {
  if (!form) {
    return;
  }
  const inputs = form.querySelectorAll('input, select');

  const markError = (field, msg) => {
    field.classList.add('cart-form-input-error');
    const wrap = field.closest('.cart-form-group') || field.parentElement;
    if (!wrap) {
      return;
    }
    let err = wrap.querySelector('.cart-form-error');
    if (!err) {
      err = document.createElement('div');
      err.className = 'cart-form-error';
      wrap.appendChild(err);
    }
    err.textContent = msg;
    err.style.display = 'block';
  };

  const clearError = (field) => {
    field.classList.remove('cart-form-input-error');
    const wrap = field.closest('.cart-form-group') || field.parentElement;
    if (!wrap) {
      return;
    }
    const err = wrap.querySelector('.cart-form-error');
    if (err) {
      err.style.display = 'none';
    }
  };

  const validate = (field) => {
    const value = (field.value || '').trim();
    clearError(field);

    if (field.hasAttribute('required') && !value) {
      markError(field, "Це поле обов'язкове");
      return false;
    }

    if (value && field.name === 'phone') {
      const cleaned = value.replace(/[^\d+]/g, '');
      if (!cleaned.startsWith('+380') || cleaned.length !== 13) {
        markError(field, 'Телефон у форматі +380XXXXXXXXX');
        return false;
      }
    }
    return true;
  };

  inputs.forEach((input) => {
    input.addEventListener('input', () => clearError(input));
    input.addEventListener('blur', () => validate(input));
  });

  form.addEventListener('submit', (event) => {
    let ok = true;
    inputs.forEach((input) => {
      if (!validate(input)) {
        ok = false;
      }
    });
    if (!ok) {
      event.preventDefault();
      const first = form.querySelector('.cart-form-input-error');
      if (first) {
        first.scrollIntoView({ behavior: 'smooth', block: 'center' });
        first.focus();
      }
    }
  });
}

export function initCartInteractions() {
  const promoInput = document.getElementById('promo-code-input');
  const applyBtn = document.querySelector('.cart-promo-apply-btn');
  const removeBtn = document.querySelector('.cart-promo-remove-btn');
  const msgBox = document.getElementById('promo-message');

  if (applyBtn && promoInput) {
    applyBtn.addEventListener('click', (event) => {
      event.preventDefault();
      applyPromoCode(promoInput, msgBox);
    });
  }

  if (removeBtn) {
    removeBtn.addEventListener('click', (event) => {
      event.preventDefault();
      removePromoCode(msgBox);
    });
  }

  if (promoInput) {
    promoInput.addEventListener('keypress', (event) => {
      if (event.key === 'Enter') {
        event.preventDefault();
        applyPromoCode(promoInput, msgBox);
      }
    });
  }

  document.addEventListener('click', (event) => {
    const btn = event.target.closest?.('.cart-item-remove-btn');
    if (!btn) {
      return;
    }
    const key = btn.getAttribute('data-key');
    if (key && typeof window.CartRemoveKey === 'function') {
      event.preventDefault();
      window.CartRemoveKey(key, btn);
    }
  });

  setupCartValidation(document.getElementById('guest-form'));
  setupCartValidation(document.getElementById('deliveryForm'));

  const root = document.querySelector('.cart-page-container');
  if (root) {
    if (root.__cartController) {
      root.__cartController.destroy();
    }
    const controller = new CartPageController(root);
    root.__cartController = controller;
    controller.init();
  }
}
