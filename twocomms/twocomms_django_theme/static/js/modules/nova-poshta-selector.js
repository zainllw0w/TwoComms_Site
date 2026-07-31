const CITY_MIN_CHARS = 2;
const SEARCH_DEBOUNCE_MS = 250;
const controllerRegistry = new WeakMap();
const submitControllerRegistry = new WeakMap();

const COPY = {
  uk: {
    cityStart: 'Почніть вводити назву міста.',
    warehouseStart: 'Після вибору міста почніть вводити номер або адресу відділення.',
    cityConfirmed: 'Місто підтверджено в довіднику Нової пошти.',
    warehouseConfirmed: 'Пункт доставки підтверджено в довіднику Нової пошти.',
    cityChecking: 'Перевіряємо збережене місто в довіднику Нової пошти…',
    warehouseChecking: 'Перевіряємо збережений пункт доставки в довіднику Нової пошти…',
    cityChoose: 'Підтвердіть місто, обравши його зі списку Нової пошти.',
    warehouseChoose: 'Підтвердіть відділення або поштомат, обравши його зі списку.',
    cityMin: 'Введіть щонайменше 2 символи для пошуку міста.',
    searchDisabled: 'Довідник Нової пошти тимчасово недоступний. Спробуйте ще раз трохи пізніше.',
    warehouseSearch: 'Шукаємо відділення або поштомат…',
    citySearch: 'Шукаємо місто в довіднику Нової пошти…',
    cityEmpty: 'За цим запитом місто не знайдено. Уточніть назву і виберіть варіант зі списку.',
    warehouseEmpty: 'За цим запитом нічого не знайдено. Уточніть номер або адресу і виберіть пункт зі списку.',
    citySelect: 'Оберіть місто зі списку Нової пошти.',
    warehouseSelect: 'Оберіть відділення або поштомат зі списку Нової пошти.',
    cityRequired: 'Потрібно обрати місто зі списку Нової пошти.',
    warehouseRequired: 'Потрібно обрати відділення або поштомат зі списку Нової пошти.',
    cityError: 'Не вдалося завантажити список міст Нової пошти. Спробуйте ще раз.',
    warehouseError: 'Не вдалося завантажити список відділень Нової пошти. Спробуйте ще раз.',
    cityFirst: 'Спочатку оберіть місто зі списку Нової пошти.',
    warehousesAvailable: 'Доступно пунктів: {count}',
    branchLabel: 'Відділення',
    postomatLabel: 'Поштомат',
  },
  ru: {
    cityStart: 'Начните вводить название города.',
    warehouseStart: 'После выбора города начните вводить номер или адрес отделения.',
    cityConfirmed: 'Город подтвержден в справочнике Новой почты.',
    warehouseConfirmed: 'Пункт доставки подтвержден в справочнике Новой почты.',
    cityChecking: 'Проверяем сохраненный город в справочнике Новой почты…',
    warehouseChecking: 'Проверяем сохраненный пункт доставки в справочнике Новой почты…',
    cityChoose: 'Подтвердите город, выбрав его из списка Новой почты.',
    warehouseChoose: 'Подтвердите отделение или почтомат, выбрав его из списка.',
    cityMin: 'Введите минимум 2 символа для поиска города.',
    searchDisabled: 'Справочник Новой почты временно недоступен. Попробуйте позже.',
    warehouseSearch: 'Ищем отделение или почтомат…',
    citySearch: 'Ищем город в справочнике Новой почты…',
    cityEmpty: 'Город не найден. Уточните название и выберите вариант из списка.',
    warehouseEmpty: 'Ничего не найдено. Уточните номер или адрес и выберите пункт из списка.',
    citySelect: 'Выберите город из списка Новой почты.',
    warehouseSelect: 'Выберите отделение или почтомат из списка Новой почты.',
    cityRequired: 'Нужно выбрать город из списка Новой почты.',
    warehouseRequired: 'Нужно выбрать отделение или почтомат из списка Новой почты.',
    cityError: 'Не удалось загрузить список городов Новой почты. Попробуйте еще раз.',
    warehouseError: 'Не удалось загрузить список отделений Новой почты. Попробуйте еще раз.',
    cityFirst: 'Сначала выберите город из списка Новой почты.',
    warehousesAvailable: 'Доступно пунктов: {count}',
    branchLabel: 'Отделение',
    postomatLabel: 'Почтомат',
  },
  en: {
    cityStart: 'Start typing a city name.',
    warehouseStart: 'Choose a city, then type a branch number or address.',
    cityConfirmed: 'City verified in the Nova Poshta directory.',
    warehouseConfirmed: 'Pickup point verified in the Nova Poshta directory.',
    cityChecking: 'Checking the saved city in the Nova Poshta directory…',
    warehouseChecking: 'Checking the saved pickup point in the Nova Poshta directory…',
    cityChoose: 'Confirm the city by choosing it from the Nova Poshta list.',
    warehouseChoose: 'Confirm the branch or locker by choosing it from the list.',
    cityMin: 'Enter at least 2 characters to search for a city.',
    searchDisabled: 'The Nova Poshta directory is temporarily unavailable. Try again later.',
    warehouseSearch: 'Searching branches and lockers…',
    citySearch: 'Searching the Nova Poshta directory…',
    cityEmpty: 'No city found. Refine the name and choose an option from the list.',
    warehouseEmpty: 'No pickup point found. Refine the number or address and choose an option.',
    citySelect: 'Choose a city from the Nova Poshta list.',
    warehouseSelect: 'Choose a branch or locker from the Nova Poshta list.',
    cityRequired: 'Choose a city from the Nova Poshta list.',
    warehouseRequired: 'Choose a branch or locker from the Nova Poshta list.',
    cityError: 'We could not load the Nova Poshta city list. Try again.',
    warehouseError: 'We could not load the Nova Poshta pickup point list. Try again.',
    cityFirst: 'Choose a city from the Nova Poshta list first.',
    warehousesAvailable: '{count} pickup points available',
    branchLabel: 'Branch',
    postomatLabel: 'Locker',
  },
};

const SETTLEMENT_TYPE_COPY = {
  uk: {
    city: 'Місто',
    town: 'Містечко',
    village: 'Село',
    settlement: 'Селище',
  },
  ru: {
    city: 'Город',
    town: 'Городок',
    village: 'Село',
    settlement: 'Посёлок',
  },
  en: {
    city: 'City',
    town: 'Town',
    village: 'Village',
    settlement: 'Settlement',
  },
};

const SETTLEMENT_TYPE_KEYS = {
  'місто': 'city',
  'город': 'city',
  city: 'city',
  'містечко': 'town',
  'городок': 'town',
  town: 'town',
  'село': 'village',
  village: 'village',
  'селище': 'settlement',
  'посёлок': 'settlement',
  'поселок': 'settlement',
  settlement: 'settlement',
};

function localizeSettlementType(value, locale) {
  const normalized = String(value || '').trim().toLowerCase();
  const key = SETTLEMENT_TYPE_KEYS[normalized];
  return key ? (SETTLEMENT_TYPE_COPY[locale] || SETTLEMENT_TYPE_COPY.uk)[key] : String(value || '').trim();
}

function debounce(fn, wait) {
  let timer = null;
  return (...args) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => fn(...args), wait);
  };
}

function normalizeValue(value) {
  return String(value || '')
    .trim()
    .replace(/\s+/g, ' ')
    .toLowerCase();
}

function setStatus(node, text, type = '') {
  if (!node) {
    return;
  }
  node.textContent = text || '';
  node.classList.remove('is-loading', 'is-success', 'is-error');
  if (type) {
    node.classList.add(`is-${type}`);
  }
}

function hideResults(container, input) {
  if (container) {
    container.hidden = true;
    container.innerHTML = '';
  }
  if (input) {
    input.setAttribute('aria-expanded', 'false');
    input.removeAttribute('aria-activedescendant');
  }
}

function showResults(container, input) {
  if (container) {
    container.hidden = false;
  }
  if (input) {
    input.setAttribute('aria-expanded', 'true');
  }
}

function createOptionButton(item, buildMeta, { id = '', index = 0 } = {}) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'np-selector-option';
  button.id = id;
  button.dataset.optionIndex = String(index);
  button.setAttribute('role', 'option');
  button.setAttribute('aria-selected', 'false');

  const main = document.createElement('div');
  main.className = 'np-selector-option-main';
  main.textContent = item.label || '';
  button.appendChild(main);

  const metaText = typeof buildMeta === 'function' ? buildMeta(item) : '';
  if (metaText) {
    const meta = document.createElement('div');
    meta.className = 'np-selector-option-meta';
    meta.textContent = metaText;
    button.appendChild(meta);
  }

  return button;
}

function getFieldContainer(field) {
  return field?.closest?.('.cart-form-group, .form-group, .ds-input, .ds-np-field') || field?.parentElement || null;
}

function ensureErrorNode(field) {
  const wrap = getFieldContainer(field);
  if (!wrap) {
    return null;
  }
  let err = wrap.querySelector('.cart-form-error');
  if (!err) {
    err = document.createElement('div');
    err.className = 'cart-form-error';
    wrap.appendChild(err);
  }
  return err;
}

function setFieldError(field, message) {
  if (!field) {
    return;
  }
  field.classList.add('cart-form-input-error');
  field.classList.add('is-invalid');
  field.setAttribute('aria-invalid', 'true');
  const err = ensureErrorNode(field);
  if (err) {
    if (!err.id) {
      err.id = `${field.id || field.name || 'np-field'}-error`;
    }
    err.textContent = message;
    err.style.display = 'block';
    const describedBy = new Set(String(field.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean));
    describedBy.add(err.id);
    field.setAttribute('aria-describedby', [...describedBy].join(' '));
  }
}

function clearFieldError(field) {
  if (!field) {
    return;
  }
  field.classList.remove('cart-form-input-error');
  field.classList.remove('is-invalid');
  field.removeAttribute('aria-invalid');
  const wrap = getFieldContainer(field);
  const err = wrap?.querySelector('.cart-form-error');
  if (err) {
    err.style.display = 'none';
  }
}

function matchesCity(item, query) {
  const normalizedQuery = normalizeValue(query);
  if (!normalizedQuery) {
    return false;
  }
  const normalizedLabel = normalizeValue(item.label);
  const normalizedDescription = normalizeValue(item.main_description);
  return (
    normalizedLabel === normalizedQuery ||
    normalizedDescription === normalizedQuery ||
    normalizedLabel.startsWith(`${normalizedQuery},`) ||
    normalizedLabel.startsWith(`${normalizedQuery} `)
  );
}

function matchesWarehouse(item, query) {
  const normalizedQuery = normalizeValue(query);
  if (!normalizedQuery) {
    return false;
  }

  return [
    item.label,
    item.short_address,
    item.description,
  ].some((value) => normalizeValue(value) === normalizedQuery);
}

class NovaPoshtaSelectorController {
  constructor(form, options) {
    this.form = form;
    this.submitForm = form?.matches?.('form') ? form : form?.closest?.('form');
    this.cityUrl = options.cityUrl;
    this.warehouseUrl = options.warehouseUrl;

    this.cityInput = form.querySelector('[data-np-city-input]');
    this.cityResults = form.querySelector('[data-np-city-results]');
    this.cityStatus = form.querySelector('[data-np-city-status]');
    this.settlementRefInput = form.querySelector('[data-np-settlement-ref]');
    this.cityRefInput = form.querySelector('[data-np-city-ref]');
    this.cityTokenInput = form.querySelector('[data-np-city-token]');

    this.warehouseInput = form.querySelector('[data-np-warehouse-input]');
    this.warehouseResults = form.querySelector('[data-np-warehouse-results]');
    this.warehouseStatus = form.querySelector('[data-np-warehouse-status]');
    this.warehouseRefInput = form.querySelector('[data-np-warehouse-ref]');
    this.warehouseTokenInput = form.querySelector('[data-np-warehouse-token]');
    this.kindButtons = Array.from(form.querySelectorAll('[data-np-kind-toggle] [data-kind]'));
    this.optionalSelection = form.dataset.npOptional === '1';
    const locale = String(form.dataset.locale || document.documentElement.lang || 'uk')
      .split('-')[0]
      .toLowerCase();
    this.locale = COPY[locale] ? locale : 'uk';
    this.copy = COPY[this.locale];

    this.lookupDisabled = false;
    this.selectedSettlementRef = '';
    this.selectedCityRef = '';
    this.selectedCityToken = '';
    this.selectedCityLabel = '';
    this.selectedWarehouseRef = '';
    this.selectedWarehouseToken = '';
    this.selectedWarehouseLabel = '';
    this.activeKind = 'all';
    this.activeResultIndex = { city: -1, warehouse: -1 };

    this.skipCityInputHandler = false;
    this.skipWarehouseInputHandler = false;
    this.isSubmitting = false;
    this.cityController = null;
    this.warehouseController = null;

    this.handleDocumentClick = this.handleDocumentClick.bind(this);
    this.handleCityInput = this.handleCityInput.bind(this);
    this.handleWarehouseInput = this.handleWarehouseInput.bind(this);
    this.handleWarehouseFocus = this.handleWarehouseFocus.bind(this);

    this.debouncedCityLookup = debounce(() => this.fetchCities(), SEARCH_DEBOUNCE_MS);
    this.debouncedWarehouseLookup = debounce(() => this.fetchWarehouses(), SEARCH_DEBOUNCE_MS);
  }

  init() {
    if (!this.cityInput || !this.warehouseInput || !this.cityUrl || !this.warehouseUrl) {
      return;
    }

    this.selectedSettlementRef = this.settlementRefInput?.value?.trim() || '';
    this.selectedCityRef = this.cityRefInput?.value?.trim() || '';
    this.selectedCityToken = this.cityTokenInput?.value?.trim() || '';
    this.selectedWarehouseRef = this.warehouseRefInput?.value?.trim() || '';
    this.selectedWarehouseToken = this.warehouseTokenInput?.value?.trim() || '';
    this.selectedCityLabel = this.cityInput.value.trim();
    this.selectedWarehouseLabel = this.warehouseInput.value.trim();

    this.cityInput.addEventListener('input', this.handleCityInput);
    this.cityInput.addEventListener('change', () => clearFieldError(this.cityInput));
    this.cityInput.addEventListener('keydown', (event) => {
      this.handleInputKeydown(event, this.cityResults, (item) => this.selectCity(item));
    });
    this.cityInput.addEventListener('blur', () => {
      window.setTimeout(() => hideResults(this.cityResults, this.cityInput), 150);
    });

    this.warehouseInput.addEventListener('input', this.handleWarehouseInput);
    this.warehouseInput.addEventListener('change', () => clearFieldError(this.warehouseInput));
    this.warehouseInput.addEventListener('focus', this.handleWarehouseFocus);
    this.warehouseInput.addEventListener('keydown', (event) => {
      this.handleInputKeydown(event, this.warehouseResults, (item) => this.selectWarehouse(item));
    });
    this.warehouseInput.addEventListener('blur', () => {
      window.setTimeout(() => hideResults(this.warehouseResults, this.warehouseInput), 150);
    });

    this.kindButtons.forEach((button) => {
      button.addEventListener('click', () => {
        const nextKind = button.dataset.kind || 'all';
        if (nextKind === this.activeKind) {
          return;
        }
        this.activeKind = nextKind;
        this.kindButtons.forEach((item) => {
          const isActive = item === button;
          item.classList.toggle('is-active', isActive);
          item.setAttribute('aria-pressed', isActive ? 'true' : 'false');
        });
        this.clearWarehouseSelection({ preserveInput: false });
        if (this.selectedSettlementRef || this.selectedCityRef) {
          this.fetchWarehouses();
        }
      });
    });

    registerSubmitController(this);
    document.addEventListener('click', this.handleDocumentClick);
    this.restoreExistingSelection();
  }

  handleDocumentClick(event) {
    if (this.form.contains(event.target)) {
      return;
    }
    hideResults(this.cityResults, this.cityInput);
    hideResults(this.warehouseResults, this.warehouseInput);
  }

  handleInputKeydown(event, container, selectFn) {
    if (event.key === 'Escape') {
      hideResults(container, event.currentTarget);
      return;
    }
    const options = Array.from(container?.querySelectorAll?.('[role="option"]') || []);
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp' || event.key === 'Home' || event.key === 'End') {
      if (!options.length) return;
      event.preventDefault();
      const type = container === this.cityResults ? 'city' : 'warehouse';
      const direction = event.key === 'ArrowUp' ? -1 : 1;
      let index = this.activeResultIndex[type];
      if (event.key === 'Home') index = 0;
      else if (event.key === 'End') index = options.length - 1;
      else index = (index + direction + options.length) % options.length;
      this.activeResultIndex[type] = index;
      options.forEach((option, optionIndex) => {
        const active = optionIndex === index;
        option.setAttribute('aria-selected', active ? 'true' : 'false');
      });
      event.currentTarget.setAttribute('aria-activedescendant', options[index].id);
      options[index].scrollIntoView({ block: 'nearest' });
      return;
    }
    if (event.key !== 'Enter') return;

    const type = container === this.cityResults ? 'city' : 'warehouse';
    const activeIndex = this.activeResultIndex[type] >= 0 ? this.activeResultIndex[type] : 0;
    const firstOption = options[activeIndex] || container?.querySelector?.('[data-item-json]');
    if (!firstOption) {
      return;
    }

    event.preventDefault();
    try {
      selectFn(JSON.parse(firstOption.dataset.itemJson || '{}'));
    } catch (_) {
      // no-op
    }
  }

  async restoreExistingSelection() {
    if (!this.cityInput.value.trim()) {
      setStatus(this.cityStatus, this.copy.cityStart, '');
      setStatus(this.warehouseStatus, this.copy.warehouseStart, '');
      return;
    }

    if (this.selectedCityToken && this.selectedWarehouseToken) {
      setStatus(this.cityStatus, this.copy.cityConfirmed, 'success');
      setStatus(this.warehouseStatus, this.copy.warehouseConfirmed, 'success');
      return;
    }

    setStatus(this.cityStatus, this.copy.cityChecking, 'loading');
    const cityResolved = await this.ensureCitySelection({ silent: true });
    if (!cityResolved) {
      setStatus(this.cityStatus, this.copy.cityChoose, '');
      setStatus(this.warehouseStatus, this.copy.warehouseChoose, '');
      return;
    }

    if (!this.warehouseInput.value.trim()) {
      setStatus(this.warehouseStatus, this.copy.warehouseStart, '');
      return;
    }

    setStatus(this.warehouseStatus, this.copy.warehouseChecking, 'loading');
    const warehouseResolved = await this.ensureWarehouseSelection({ silent: true });
    if (!warehouseResolved) {
      setStatus(
        this.warehouseStatus,
        this.copy.warehouseChoose,
        '',
      );
    }
  }

  handleCityInput() {
    if (this.skipCityInputHandler) {
      this.skipCityInputHandler = false;
      return;
    }

    clearFieldError(this.cityInput);
    const currentValue = this.cityInput.value.trim();
    if (this.selectedCityLabel && normalizeValue(currentValue) !== normalizeValue(this.selectedCityLabel)) {
      this.clearCitySelection({ preserveInput: true });
      this.clearWarehouseSelection({ preserveInput: false });
    }

    if (!currentValue) {
      hideResults(this.cityResults, this.cityInput);
      setStatus(this.cityStatus, this.copy.cityStart, '');
      return;
    }
    if (currentValue.length < CITY_MIN_CHARS) {
      hideResults(this.cityResults, this.cityInput);
      setStatus(this.cityStatus, this.copy.cityMin, '');
      return;
    }
    if (this.lookupDisabled) {
      setStatus(
        this.cityStatus,
        this.copy.searchDisabled,
        'error',
      );
      return;
    }

    setStatus(this.cityStatus, this.copy.citySearch, 'loading');
    this.debouncedCityLookup();
  }

  handleWarehouseInput() {
    if (this.skipWarehouseInputHandler) {
      this.skipWarehouseInputHandler = false;
      return;
    }

    clearFieldError(this.warehouseInput);
    const currentValue = this.warehouseInput.value.trim();
    if (this.selectedWarehouseLabel && normalizeValue(currentValue) !== normalizeValue(this.selectedWarehouseLabel)) {
      this.clearWarehouseSelection({ preserveInput: true });
    }

    if (this.lookupDisabled) {
      setStatus(
        this.warehouseStatus,
        this.copy.searchDisabled,
        'error',
      );
      return;
    }

    if (!currentValue && (this.selectedSettlementRef || this.selectedCityRef)) {
      setStatus(this.warehouseStatus, this.copy.warehouseStart, '');
      return;
    }

    if (!(this.selectedSettlementRef || this.selectedCityRef)) {
      this.ensureCitySelection({ silent: true })
        .then((resolved) => {
          if (!resolved) {
            hideResults(this.warehouseResults, this.warehouseInput);
            setStatus(
              this.warehouseStatus,
              this.copy.cityFirst,
              '',
            );
            return;
          }
          setStatus(this.warehouseStatus, this.copy.warehouseSearch, 'loading');
          this.debouncedWarehouseLookup();
        })
        .catch(() => {
          setStatus(
            this.warehouseStatus,
            this.copy.warehouseError,
            'error',
          );
        });
      return;
    }

    setStatus(this.warehouseStatus, this.copy.warehouseSearch, 'loading');
    this.debouncedWarehouseLookup();
  }

  handleWarehouseFocus() {
    if (this.lookupDisabled || this.warehouseInput.value.trim()) {
      return;
    }

    this.ensureCitySelection({ silent: true })
      .then((resolved) => {
        if (!resolved) {
          setStatus(
            this.warehouseStatus,
            this.copy.cityFirst,
            '',
          );
          return;
        }
        this.fetchWarehouses();
      })
      .catch(() => {
        setStatus(
          this.warehouseStatus,
          this.copy.warehouseError,
          'error',
        );
      });
  }

  async ensureCitySelection(options = {}) {
    if (this.selectedCityToken && (this.selectedSettlementRef || this.selectedCityRef)) {
      return true;
    }

    const query = this.cityInput.value.trim();
    if (query.length < CITY_MIN_CHARS) {
      return false;
    }

    const items = await this.fetchCities({ silent: true });
    const exactMatch = items.find((item) => matchesCity(item, query));
    if (!exactMatch) {
      return false;
    }

    this.selectCity(exactMatch, { focusWarehouse: false, announce: !options.silent });
    return true;
  }

  async ensureWarehouseSelection(options = {}) {
    if (this.selectedWarehouseToken && this.selectedWarehouseRef) {
      return true;
    }
    if (!(this.selectedSettlementRef || this.selectedCityRef)) {
      const cityResolved = await this.ensureCitySelection({ silent: true });
      if (!cityResolved) {
        return false;
      }
    }

    const query = this.warehouseInput.value.trim();
    if (!query) {
      return false;
    }

    const items = await this.fetchWarehouses({ silent: true, limit: 50 });
    const exactMatch = items.find((item) => matchesWarehouse(item, query));
    if (!exactMatch) {
      return false;
    }

    this.selectWarehouse(exactMatch, { announce: !options.silent });
    return true;
  }

  async fetchCities(options = {}) {
    const silent = Boolean(options.silent);
    const query = this.cityInput.value.trim();
    if (!query || query.length < CITY_MIN_CHARS || this.lookupDisabled) {
      return [];
    }

    if (this.cityController) {
      this.cityController.abort();
    }
    this.cityController = new AbortController();

    try {
      const params = new URLSearchParams({ q: query, limit: '10', locale: this.locale });
      const response = await fetch(`${this.cityUrl}?${params.toString()}`, {
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'Cache-Control': 'no-cache',
        },
        signal: this.cityController.signal,
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !payload.ok) {
        if (response.status === 503) {
          this.lookupDisabled = true;
        }
        if (!silent) {
          setStatus(
            this.cityStatus,
            this.copy.searchDisabled,
            'error',
          );
          hideResults(this.cityResults, this.cityInput);
        }
        return [];
      }

      const items = Array.isArray(payload.items) ? payload.items : [];
      if (!silent) {
        this.renderCities(items);
      }
      return items;
    } catch (error) {
      if (error.name === 'AbortError') {
        return [];
      }
      if (!silent) {
        setStatus(
          this.cityStatus,
          this.copy.cityError,
          'error',
        );
      }
      hideResults(this.cityResults, this.cityInput);
      return [];
    } finally {
      this.cityController = null;
    }
  }

  async fetchWarehouses(options = {}) {
    const silent = Boolean(options.silent);
    const limit = options.limit || 20;
    if (this.lookupDisabled || !(this.selectedSettlementRef || this.selectedCityRef)) {
      return [];
    }

    if (this.warehouseController) {
      this.warehouseController.abort();
    }
    this.warehouseController = new AbortController();

    const params = new URLSearchParams();
    if (this.selectedSettlementRef) {
      params.set('settlement_ref', this.selectedSettlementRef);
    }
    if (this.selectedCityRef) {
      params.set('city_ref', this.selectedCityRef);
    }
    if (this.warehouseInput.value.trim()) {
      params.set('q', this.warehouseInput.value.trim());
    }
    params.set('kind', this.activeKind);
    params.set('limit', String(limit));
    params.set('locale', this.locale);

    try {
      const response = await fetch(`${this.warehouseUrl}?${params.toString()}`, {
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'Cache-Control': 'no-cache',
        },
        signal: this.warehouseController.signal,
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !payload.ok) {
        if (response.status === 503) {
          this.lookupDisabled = true;
        }
        if (!silent) {
          setStatus(
            this.warehouseStatus,
            response.status === 400 ? this.copy.cityFirst : this.copy.searchDisabled,
            response.status === 400 ? '' : 'error',
          );
          hideResults(this.warehouseResults, this.warehouseInput);
        }
        return [];
      }

      const items = Array.isArray(payload.items) ? payload.items : [];
      if (!silent) {
        this.renderWarehouses(items);
      }
      return items;
    } catch (error) {
      if (error.name === 'AbortError') {
        return [];
      }
      if (!silent) {
        setStatus(
          this.warehouseStatus,
          this.copy.warehouseError,
          'error',
        );
      }
      hideResults(this.warehouseResults, this.warehouseInput);
      return [];
    } finally {
      this.warehouseController = null;
    }
  }

  renderCities(items) {
    if (!items.length) {
      hideResults(this.cityResults, this.cityInput);
      setStatus(this.cityStatus, this.copy.cityEmpty, '');
      return;
    }

    this.cityResults.innerHTML = '';
    items.forEach((item, index) => {
      const button = createOptionButton(item, (current) => {
        const meta = [];
        if (current.settlement_type) {
          meta.push(localizeSettlementType(current.settlement_type, this.locale));
        }
        if (current.area || current.region) {
          meta.push([current.area, current.region].filter(Boolean).join(', '));
        }
        if (current.warehouses) {
          meta.push(this.copy.warehousesAvailable.replace('{count}', current.warehouses));
        }
        return meta.join(' • ');
      }, { id: `${this.cityInput.id}-option-${index}`, index });
      button.dataset.itemJson = JSON.stringify(item);
      button.addEventListener('click', () => this.selectCity(item));
      this.cityResults.appendChild(button);
    });

    showResults(this.cityResults, this.cityInput);
    this.activeResultIndex.city = -1;
    this.cityInput.removeAttribute('aria-activedescendant');
    setStatus(this.cityStatus, this.copy.citySelect, '');
  }

  renderWarehouses(items) {
    if (!items.length) {
      hideResults(this.warehouseResults, this.warehouseInput);
      setStatus(
        this.warehouseStatus,
        this.copy.warehouseEmpty,
        '',
      );
      return;
    }

    this.warehouseResults.innerHTML = '';
    items.forEach((item, index) => {
      const button = createOptionButton(item, (current) => {
        const meta = [current.kind === 'postomat' ? this.copy.postomatLabel : this.copy.branchLabel];
        if (current.number) {
          meta.push(`№${current.number}`);
        }
        if (current.description && current.description !== current.label) {
          meta.push(current.description);
        }
        return meta.join(' • ');
      }, { id: `${this.warehouseInput.id}-option-${index}`, index });
      button.dataset.itemJson = JSON.stringify(item);
      button.addEventListener('click', () => this.selectWarehouse(item));
      this.warehouseResults.appendChild(button);
    });

    showResults(this.warehouseResults, this.warehouseInput);
    this.activeResultIndex.warehouse = -1;
    this.warehouseInput.removeAttribute('aria-activedescendant');
    setStatus(this.warehouseStatus, this.copy.warehouseSelect, '');
  }

  selectCity(item, options = {}) {
    const nextLabel = item.label || '';
    const nextSettlementRef = item.settlement_ref || item.legacy_ref || '';
    const nextCityRef = item.city_ref || item.legacy_ref || '';
    const nextToken = item.token || '';
    const cityChanged =
      this.selectedCityLabel &&
      normalizeValue(this.selectedCityLabel) !== normalizeValue(nextLabel);

    this.selectedSettlementRef = nextSettlementRef;
    this.selectedCityRef = nextCityRef;
    this.selectedCityToken = nextToken;
    this.selectedCityLabel = nextLabel;
    if (this.settlementRefInput) {
      this.settlementRefInput.value = nextSettlementRef;
    }
    if (this.cityRefInput) {
      this.cityRefInput.value = nextCityRef;
    }
    if (this.cityTokenInput) {
      this.cityTokenInput.value = nextToken;
    }

    this.skipCityInputHandler = true;
    this.cityInput.value = nextLabel;
    this.cityInput.dispatchEvent(new Event('input', { bubbles: true }));
    this.cityInput.dispatchEvent(new Event('change', { bubbles: true }));
    hideResults(this.cityResults, this.cityInput);
    clearFieldError(this.cityInput);
    setStatus(
      this.cityStatus,
      this.copy.cityConfirmed,
      'success',
    );

    if (cityChanged || !this.selectedWarehouseRef) {
      this.clearWarehouseSelection({ preserveInput: false });
    }
    if (options.focusWarehouse !== false) {
      window.requestAnimationFrame(() => this.warehouseInput.focus());
    }
  }

  selectWarehouse(item, options = {}) {
    const nextLabel = item.label || '';
    const nextRef = item.ref || '';
    const nextToken = item.token || '';
    this.selectedWarehouseRef = nextRef;
    this.selectedWarehouseToken = nextToken;
    this.selectedWarehouseLabel = nextLabel;
    if (this.warehouseRefInput) {
      this.warehouseRefInput.value = nextRef;
    }
    if (this.warehouseTokenInput) {
      this.warehouseTokenInput.value = nextToken;
    }

    this.skipWarehouseInputHandler = true;
    this.warehouseInput.value = nextLabel;
    this.warehouseInput.dispatchEvent(new Event('input', { bubbles: true }));
    this.warehouseInput.dispatchEvent(new Event('change', { bubbles: true }));
    hideResults(this.warehouseResults, this.warehouseInput);
    clearFieldError(this.warehouseInput);
    setStatus(
      this.warehouseStatus,
      this.copy.warehouseConfirmed,
      'success',
    );
  }

  clearCitySelection(options = {}) {
    this.selectedSettlementRef = '';
    this.selectedCityRef = '';
    this.selectedCityToken = '';
    this.selectedCityLabel = options.preserveInput ? this.cityInput.value.trim() : '';
    if (this.settlementRefInput) {
      this.settlementRefInput.value = '';
    }
    if (this.cityRefInput) {
      this.cityRefInput.value = '';
    }
    if (this.cityTokenInput) {
      this.cityTokenInput.value = '';
    }
    if (!options.preserveInput) {
      this.skipCityInputHandler = true;
      this.cityInput.value = '';
      this.cityInput.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }

  clearWarehouseSelection(options = {}) {
    this.selectedWarehouseRef = '';
    this.selectedWarehouseToken = '';
    this.selectedWarehouseLabel = options.preserveInput ? this.warehouseInput.value.trim() : '';
    if (this.warehouseRefInput) {
      this.warehouseRefInput.value = '';
    }
    if (this.warehouseTokenInput) {
      this.warehouseTokenInput.value = '';
    }
    if (!options.preserveInput) {
      this.skipWarehouseInputHandler = true;
      this.warehouseInput.value = '';
      this.warehouseInput.dispatchEvent(new Event('input', { bubbles: true }));
      this.warehouseInput.dispatchEvent(new Event('change', { bubbles: true }));
      setStatus(this.warehouseStatus, this.copy.warehouseStart, '');
    }
  }

  async validateSelection(options = {}) {
    const showErrors = options.showErrors !== false;
    let valid = true;

    if (this.optionalSelection && !this.hasAnySelectionInput()) {
      clearFieldError(this.cityInput);
      clearFieldError(this.warehouseInput);
      return true;
    }

    const hasCitySelection = await this.ensureCitySelection({ silent: !showErrors });
    if (!hasCitySelection || !this.selectedCityToken) {
      valid = false;
      if (showErrors) {
        setFieldError(this.cityInput, this.copy.citySelect);
        setStatus(this.cityStatus, this.copy.cityRequired, 'error');
      }
    }

    const hasWarehouseSelection = valid
      ? await this.ensureWarehouseSelection({ silent: !showErrors })
      : false;
    if (!hasWarehouseSelection || !this.selectedWarehouseToken) {
      valid = false;
      if (showErrors) {
        setFieldError(this.warehouseInput, this.copy.warehouseSelect);
        setStatus(
          this.warehouseStatus,
          this.copy.warehouseRequired,
          'error',
        );
      }
    }

    if (!valid) {
      const first = this.form.querySelector('.cart-form-input-error');
      if (first && showErrors) {
        first.scrollIntoView({
          behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
          block: 'center',
        });
        first.focus();
      }
    }
    return valid;
  }

  hasAnySelectionInput() {
    return [
      this.cityInput?.value,
      this.warehouseInput?.value,
      this.selectedSettlementRef,
      this.selectedCityRef,
      this.selectedCityToken,
      this.selectedWarehouseRef,
      this.selectedWarehouseToken,
    ].some((value) => normalizeValue(value));
  }
}

function getOrCreateController(form) {
  if (!form || !form.dataset?.npForm) {
    return null;
  }
  const existing = controllerRegistry.get(form);
  if (existing) {
    return existing;
  }

  const root = form.closest('[data-np-city-search-url][data-np-warehouse-search-url]') || document.querySelector('[data-np-city-search-url][data-np-warehouse-search-url]');
  const cityUrl = root?.dataset?.npCitySearchUrl || '';
  const warehouseUrl = root?.dataset?.npWarehouseSearchUrl || '';
  if (!cityUrl || !warehouseUrl) {
    return null;
  }

  const controller = new NovaPoshtaSelectorController(form, { cityUrl, warehouseUrl });
  controllerRegistry.set(form, controller);
  return controller;
}

function registerSubmitController(controller) {
  const submitForm = controller.submitForm;
  if (!submitForm) {
    return;
  }

  let entry = submitControllerRegistry.get(submitForm);
  if (!entry) {
    entry = {
      controllers: [],
      isSubmitting: false,
      skipNextSubmit: false,
    };
    submitControllerRegistry.set(submitForm, entry);

    submitForm.addEventListener('submit', async (event) => {
      if (entry.skipNextSubmit) {
        entry.skipNextSubmit = false;
        return;
      }

      event.preventDefault();
      if (entry.isSubmitting) {
        return;
      }

      entry.isSubmitting = true;
      try {
        let valid = true;
        for (const item of entry.controllers) {
          const controllerValid = await item.validateSelection({ showErrors: true });
          valid = controllerValid && valid;
        }
        if (!valid) {
          return;
        }

        entry.skipNextSubmit = true;
        if (typeof submitForm.requestSubmit === 'function') {
          submitForm.requestSubmit();
        } else {
          HTMLFormElement.prototype.submit.call(submitForm);
        }
      } finally {
        entry.isSubmitting = false;
      }
    });
  }

  if (!entry.controllers.includes(controller)) {
    entry.controllers.push(controller);
  }
}

export async function validateNovaPoshtaSelection(form, options = {}) {
  const controller = getOrCreateController(form);
  if (!controller) {
    return true;
  }

  if (form.dataset.npInitialized !== '1') {
    form.dataset.npInitialized = '1';
    controller.init();
  }
  return controller.validateSelection(options);
}

export function initNovaPoshtaSelectors(root) {
  const scope = root || document;
  const cityUrl = scope.dataset?.npCitySearchUrl || '';
  const warehouseUrl = scope.dataset?.npWarehouseSearchUrl || '';
  if (!cityUrl || !warehouseUrl) {
    return;
  }

  scope.querySelectorAll('[data-np-form]').forEach((form) => {
    if (form.dataset.npInitialized === '1') {
      return;
    }
    form.dataset.npInitialized = '1';
    const controller = new NovaPoshtaSelectorController(form, { cityUrl, warehouseUrl });
    controllerRegistry.set(form, controller);
    controller.init();
  });
}
