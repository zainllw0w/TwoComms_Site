import { getCookie } from './shared.js';

function showPromoMessage(msgBox, message, type) {
  if (!msgBox) return;
  const typeClass = type === 'success'
    ? 'cart-promo-message-success'
    : type === 'error'
      ? 'cart-promo-message-error'
      : 'cart-promo-message-info';
  msgBox.innerHTML = `<div class="cart-promo-message ${typeClass}">${message}</div>`;
  setTimeout(() => {
    try { msgBox.innerHTML = ''; } catch (_) {}
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
      'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || getCookie('csrftoken')
    },
    body: 'promo_code=' + encodeURIComponent(code)
  })
    .then(r => r.json())
    .then(d => {
      if (d && d.success) {
        showPromoMessage(msgBox, d.message || 'Застосовано', 'success');
        setTimeout(() => window.location.reload(), 900);
      } else {
        showPromoMessage(msgBox, (d && d.message) || 'Помилка', 'error');
      }
    })
    .catch(() => showPromoMessage(msgBox, 'Помилка при застосуванні', 'error'));
}

function removePromoCode(msgBox) {
  fetch('/cart/remove-promo/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
      'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || getCookie('csrftoken')
    }
  })
    .then(r => r.json())
    .then(() => window.location.reload())
    .catch(() => showPromoMessage(msgBox, 'Не вдалося видалити промокод', 'error'));
}

function setupCartValidation(form) {
  if (!form) return;
  const inputs = form.querySelectorAll('input, select');

  function markError(field, msg) {
    field.classList.add('cart-form-input-error');
    const wrap = field.closest('.cart-form-group') || field.parentElement;
    if (!wrap) return;
    let err = wrap.querySelector('.cart-form-error');
    if (!err) {
      err = document.createElement('div');
      err.className = 'cart-form-error';
      wrap.appendChild(err);
    }
    err.textContent = msg;
    err.style.display = 'block';
  }

  function clearError(field) {
    field.classList.remove('cart-form-input-error');
    const wrap = field.closest('.cart-form-group') || field.parentElement;
    if (!wrap) return;
    const err = wrap.querySelector('.cart-form-error');
    if (err) err.style.display = 'none';
  }

  function validate(field) {
    const v = (field.value || '').trim();
    clearError(field);
    if (field.hasAttribute('required') && !v) {
      markError(field, "Це поле обов'язкове");
      return false;
    }
    if (v && field.name === 'phone') {
      const p = v.replace(/[^\d+]/g, '');
      if (!p.startsWith('+380') || p.length !== 13) {
        markError(field, 'Телефон у форматі +380XXXXXXXXX');
        return false;
      }
    }
    return true;
  }

  inputs.forEach((input) => {
    input.addEventListener('input', () => clearError(input));
    input.addEventListener('blur', () => validate(input));
  });

  form.addEventListener('submit', (e) => {
    let ok = true;
    inputs.forEach((input) => {
      if (!validate(input)) ok = false;
    });
    if (!ok) {
      e.preventDefault();
      const first = form.querySelector('.cart-form-input-error');
      if (first) {
        first.scrollIntoView({ behavior: 'smooth', block: 'center' });
        first.focus();
      }
    }
  });
}

export function initCartInteractions() {
  document.addEventListener('DOMContentLoaded', () => {
    const promoInput = document.getElementById('promo-code-input');
    const applyBtn = document.querySelector('.cart-promo-apply-btn');
    const removeBtn = document.querySelector('.cart-promo-remove-btn');
    const msgBox = document.getElementById('promo-message');

    if (applyBtn) {
      applyBtn.addEventListener('click', (e) => {
        e.preventDefault();
        if (promoInput) {
          applyPromoCode(promoInput, msgBox);
        }
      });
    }

    if (removeBtn) {
      removeBtn.addEventListener('click', (e) => {
        e.preventDefault();
        removePromoCode(msgBox);
      });
    }

    if (promoInput) {
      promoInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          applyPromoCode(promoInput, msgBox);
        }
      });
    }

    document.addEventListener('click', (e) => {
      const btn = e.target.closest?.('.cart-item-remove-btn');
      if (!btn) return;
      e.preventDefault();
      e.stopPropagation();
      const key = btn.getAttribute('data-key');
      if (key && window.CartRemoveKey) {
        try {
          window.CartRemoveKey(key, btn);
        } catch (_) {}
      }
    });

    setupCartValidation(document.getElementById('guest-form'));
    setupCartValidation(document.getElementById('deliveryForm'));
  });
}
