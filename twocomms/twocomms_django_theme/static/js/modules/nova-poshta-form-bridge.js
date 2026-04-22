import { initNovaPoshtaSelectors, validateNovaPoshtaSelection } from './nova-poshta-selector.js?v=20260422b';
import { normalizeUkraineCheckoutPhoneValue, syncUkraineCheckoutPhoneField } from './phone.js';

function initScope(scope = document) {
  const roots = [];
  if (
    scope instanceof HTMLElement &&
    scope.dataset?.npCitySearchUrl &&
    scope.dataset?.npWarehouseSearchUrl
  ) {
    roots.push(scope);
  }

  if (typeof scope.querySelectorAll === 'function') {
    roots.push(
      ...scope.querySelectorAll('[data-np-city-search-url][data-np-warehouse-search-url]'),
    );
  }

  roots.forEach((root) => initNovaPoshtaSelectors(root));

  if (typeof scope.querySelectorAll !== 'function') {
    return;
  }

  scope.querySelectorAll('[data-uk-phone-field]').forEach((field) => {
    if (field.dataset.ukPhoneBound === '1') {
      return;
    }

    field.dataset.ukPhoneBound = '1';
    field.addEventListener('blur', () => {
      syncUkraineCheckoutPhoneField(field);
    });
  });
}

async function validateForm(form, options = {}) {
  const phoneField = form?.querySelector?.('[data-uk-phone-field]');
  if (phoneField) {
    const normalizedPhone = syncUkraineCheckoutPhoneField(phoneField);
    if (!normalizedPhone) {
      return {
        ok: false,
        field: 'phone',
        message: 'Вкажіть коректний український номер. Можна без +380.',
      };
    }
  }

  const isDeliveryValid = await validateNovaPoshtaSelection(form, options);
  if (!isDeliveryValid) {
    return {
      ok: false,
      field: 'delivery',
      message: 'Оберіть місто та пункт доставки зі списку Нової пошти.',
    };
  }

  return { ok: true };
}

window.TwoCommsNovaPoshta = {
  initScope,
  normalizePhoneValue: normalizeUkraineCheckoutPhoneValue,
  syncPhoneField: syncUkraineCheckoutPhoneField,
  validateForm,
};

document.addEventListener('DOMContentLoaded', () => {
  initScope(document);
});

document.addEventListener('ds:tabloaded', () => {
  initScope(document);
});
