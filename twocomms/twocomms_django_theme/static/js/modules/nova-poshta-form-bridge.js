import { initNovaPoshtaSelectors, validateNovaPoshtaSelection } from './nova-poshta-selector.js?v=20260422b';
import { normalizeUkraineCheckoutPhoneValue, syncUkraineCheckoutPhoneField } from './phone.js';

const LOCALIZED_ERRORS = {
  uk: {
    phone: 'Вкажіть коректний український номер. Можна без +380.',
    delivery: 'Оберіть місто та пункт доставки зі списку Нової пошти.',
    unavailable: 'Не вдалося перевірити Нову пошту. Оновіть сторінку.',
  },
  ru: {
    phone: 'Укажите корректный украинский номер. Можно без +380.',
    delivery: 'Выберите город и пункт доставки из списка Новой почты.',
    unavailable: 'Не удалось проверить Новую почту. Обновите страницу.',
  },
  en: {
    phone: 'Enter a valid Ukrainian phone number. +380 is optional.',
    delivery: 'Choose a city and pickup point from the Nova Poshta list.',
    unavailable: 'We could not verify Nova Poshta. Refresh the page.',
  },
};

function localizedError(form, key) {
  const locale = String(form?.dataset?.locale || 'uk').split('-')[0].toLowerCase();
  return LOCALIZED_ERRORS[locale]?.[key] || LOCALIZED_ERRORS.uk[key];
}

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
        message: localizedError(form, 'phone'),
      };
    }
  }

  const isDeliveryValid = await validateNovaPoshtaSelection(form, options);
  if (!isDeliveryValid) {
    return {
      ok: false,
      field: 'delivery',
      message: localizedError(form, 'delivery'),
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
