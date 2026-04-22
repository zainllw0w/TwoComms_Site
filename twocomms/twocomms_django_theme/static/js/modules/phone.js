export function normalizeUkraineCheckoutPhoneValue(value) {
  const raw = String(value || '').trim();
  const digits = raw.replace(/\D/g, '');

  if (!digits) {
    return '';
  }

  if (raw.startsWith('+')) {
    return digits.startsWith('380') && digits.length === 12 ? `+${digits}` : '';
  }

  if (digits.startsWith('00')) {
    const trimmed = digits.slice(2);
    return trimmed.startsWith('380') && trimmed.length === 12 ? `+${trimmed}` : '';
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

export function syncUkraineCheckoutPhoneField(field) {
  if (!field) {
    return '';
  }

  const normalized = normalizeUkraineCheckoutPhoneValue(field.value);
  if (normalized && field.value !== normalized) {
    field.value = normalized;
    field.dispatchEvent(new Event('change', { bubbles: true }));
  }
  return normalized;
}
