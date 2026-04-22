const DEFAULT_UA_CHECKOUT_PHONE_HINT =
  'Можна вводити 093..., 809..., 380... або +380... — номер приведемо до потрібного формату.';

export function normalizeUkraineCheckoutPhoneValue(value) {
  const raw = String(value || '').trim();
  const digits = raw.replace(/\D/g, '');

  if (!digits) {
    return '';
  }

  if (raw.startsWith('+')) {
    if (digits.startsWith('3800') && digits.length === 13) {
      return `+380${digits.slice(4)}`;
    }
    return digits.startsWith('380') && digits.length === 12 ? `+${digits}` : '';
  }

  if (digits.startsWith('00')) {
    const trimmed = digits.slice(2);
    if (trimmed.startsWith('3800') && trimmed.length === 13) {
      return `+380${trimmed.slice(4)}`;
    }
    return trimmed.startsWith('380') && trimmed.length === 12 ? `+${trimmed}` : '';
  }

  if (digits.startsWith('3800') && digits.length === 13) {
    return `+380${digits.slice(4)}`;
  }

  if (digits.startsWith('380') && digits.length === 12) {
    return `+${digits}`;
  }

  if (digits.startsWith('80') && digits.length === 11) {
    return `+38${digits.slice(1)}`;
  }

  if (digits.startsWith('8') && digits.length === 10) {
    return `+380${digits.slice(1)}`;
  }

  if (digits.startsWith('0') && digits.length === 10) {
    return `+38${digits}`;
  }

  if (digits.length === 9) {
    return `+380${digits}`;
  }

  return '';
}

export function getUkraineCheckoutPhoneHint(value) {
  const raw = String(value || '').trim();
  const digits = raw.replace(/\D/g, '');

  if (!digits) {
    return DEFAULT_UA_CHECKOUT_PHONE_HINT;
  }

  if (raw.startsWith('+')) {
    if (digits.startsWith('3800')) {
      return "Приберемо зайвий 0 після 380 і залишимо формат +380XXXXXXXXX.";
    }
    if (digits.startsWith('380')) {
      return 'Перевіримо номер і залишимо формат +380XXXXXXXXX.';
    }
    return 'Для оформлення через Нову пошту потрібен український номер.';
  }

  if (digits.startsWith('00')) {
    const trimmed = digits.slice(2);
    if (trimmed.startsWith('3800')) {
      return "Приберемо зайвий 0 після 380 і замінимо 00 на '+'.";
    }
    if (trimmed.startsWith('380')) {
      return "Замінемо 00 на '+' перед кодом країни.";
    }
    return 'Для оформлення через Нову пошту потрібен український номер.';
  }

  if (digits.startsWith('3800')) {
    return "Приберемо зайвий 0 після 380 і додамо символ '+'.";
  }
  if (digits.startsWith('380')) {
    return "Додамо лише символ '+' перед кодом країни.";
  }
  if (digits.startsWith('80')) {
    return 'Додамо лише +3 перед номером.';
  }
  if (digits.startsWith('0')) {
    return 'Додамо префікс +38 автоматично.';
  }
  if (digits.startsWith('8')) {
    return 'Додамо код України +380 автоматично.';
  }
  if (digits.length <= 9) {
    return 'Додамо код України +380 автоматично.';
  }

  return DEFAULT_UA_CHECKOUT_PHONE_HINT;
}

export function syncUkraineCheckoutPhoneHint(field) {
  if (!field) {
    return DEFAULT_UA_CHECKOUT_PHONE_HINT;
  }

  const wrap = field.closest('.cart-form-group') || field.parentElement;
  const hint = wrap ? wrap.querySelector('[data-phone-hint]') || wrap.querySelector('.cart-form-hint') : null;
  const message = getUkraineCheckoutPhoneHint(field.value);

  if (hint) {
    hint.textContent = message;
  }

  return message;
}

export function syncUkraineCheckoutPhoneField(field) {
  if (!field) {
    return '';
  }

  const normalized = normalizeUkraineCheckoutPhoneValue(field.value);
  if (normalized && field.value !== normalized) {
    field.value = normalized;
    field.dispatchEvent(new Event('change', { bubbles: true }));
  }
  syncUkraineCheckoutPhoneHint(field);
  return normalized;
}
