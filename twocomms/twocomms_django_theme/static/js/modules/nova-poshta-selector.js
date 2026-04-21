const CITY_MIN_CHARS = 2;
const SEARCH_DEBOUNCE_MS = 250;

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

function createOptionButton(item, buildMeta) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'np-selector-option';

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

class NovaPoshtaSelectorController {
  constructor(form, options) {
    this.form = form;
    this.cityUrl = options.cityUrl;
    this.warehouseUrl = options.warehouseUrl;

    this.cityInput = form.querySelector('[data-np-city-input]');
    this.cityResults = form.querySelector('[data-np-city-results]');
    this.cityStatus = form.querySelector('[data-np-city-status]');
    this.settlementRefInput = form.querySelector('[data-np-settlement-ref]');
    this.cityRefInput = form.querySelector('[data-np-city-ref]');

    this.warehouseInput = form.querySelector('[data-np-warehouse-input]');
    this.warehouseResults = form.querySelector('[data-np-warehouse-results]');
    this.warehouseStatus = form.querySelector('[data-np-warehouse-status]');
    this.warehouseRefInput = form.querySelector('[data-np-warehouse-ref]');
    this.kindButtons = Array.from(form.querySelectorAll('[data-np-kind-toggle] [data-kind]'));

    this.lookupDisabled = false;
    this.selectedSettlementRef = '';
    this.selectedCityRef = '';
    this.selectedCityLabel = '';
    this.selectedWarehouseRef = '';
    this.selectedWarehouseLabel = '';
    this.activeKind = 'all';

    this.skipCityInputHandler = false;
    this.skipWarehouseInputHandler = false;
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
    this.selectedWarehouseRef = this.warehouseRefInput?.value?.trim() || '';

    this.cityInput.addEventListener('input', this.handleCityInput);
    this.cityInput.addEventListener('keydown', (event) => {
      this.handleInputKeydown(event, this.cityResults, (item) => this.selectCity(item));
    });
    this.cityInput.addEventListener('blur', () => {
      window.setTimeout(() => hideResults(this.cityResults, this.cityInput), 150);
    });

    this.warehouseInput.addEventListener('input', this.handleWarehouseInput);
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
        this.kindButtons.forEach((item) => item.classList.toggle('is-active', item === button));
        this.clearWarehouseSelection({ preserveInput: false });
        if (this.selectedSettlementRef || this.selectedCityRef) {
          this.fetchWarehouses();
        }
      });
    });

    document.addEventListener('click', this.handleDocumentClick);

    if (this.cityInput.value.trim()) {
      this.selectedCityLabel = this.cityInput.value.trim();
      setStatus(
        this.cityStatus,
        'Можна залишити поточне місто або вибрати інше зі списку Нової пошти.',
        'success',
      );
    }
    if (this.warehouseInput.value.trim()) {
      this.selectedWarehouseLabel = this.warehouseInput.value.trim();
      setStatus(
        this.warehouseStatus,
        'Можна залишити поточний пункт доставки або вибрати інший.',
        'success',
      );
    }
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
    if (event.key !== 'Enter') {
      return;
    }

    const firstOption = container?.querySelector?.('[data-item-json]');
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

  handleCityInput() {
    if (this.skipCityInputHandler) {
      this.skipCityInputHandler = false;
      return;
    }

    const currentValue = this.cityInput.value.trim();
    if (this.selectedCityLabel && normalizeValue(currentValue) !== normalizeValue(this.selectedCityLabel)) {
      this.clearCitySelection({ preserveInput: true });
      this.clearWarehouseSelection({ preserveInput: false });
    }

    if (!currentValue) {
      hideResults(this.cityResults, this.cityInput);
      setStatus(this.cityStatus, 'Почніть вводити назву міста.', '');
      return;
    }
    if (currentValue.length < CITY_MIN_CHARS) {
      hideResults(this.cityResults, this.cityInput);
      setStatus(this.cityStatus, 'Введіть щонайменше 2 символи для пошуку міста.', '');
      return;
    }
    if (this.lookupDisabled) {
      setStatus(this.cityStatus, 'Пошук НП недоступний. Місто можна ввести вручну.', 'error');
      return;
    }

    setStatus(this.cityStatus, 'Шукаємо місто в довіднику Нової пошти…', 'loading');
    this.debouncedCityLookup();
  }

  handleWarehouseInput() {
    if (this.skipWarehouseInputHandler) {
      this.skipWarehouseInputHandler = false;
      return;
    }

    const currentValue = this.warehouseInput.value.trim();
    if (this.selectedWarehouseLabel && normalizeValue(currentValue) !== normalizeValue(this.selectedWarehouseLabel)) {
      this.clearWarehouseSelection({ preserveInput: true });
    }

    if (this.lookupDisabled) {
      setStatus(this.warehouseStatus, 'Пошук НП недоступний. Пункт доставки можна ввести вручну.', 'error');
      return;
    }

    if (!currentValue && (this.selectedSettlementRef || this.selectedCityRef)) {
      setStatus(this.warehouseStatus, 'Почніть вводити номер або адресу відділення.', '');
      return;
    }

    if (!(this.selectedSettlementRef || this.selectedCityRef)) {
      this.ensureCitySelection()
        .then((resolved) => {
          if (!resolved) {
            hideResults(this.warehouseResults, this.warehouseInput);
            setStatus(
              this.warehouseStatus,
              'Оберіть місто зі списку Нової пошти, щоб отримати підказки для відділення.',
              '',
            );
            return;
          }
          setStatus(this.warehouseStatus, 'Шукаємо відділення або поштомат…', 'loading');
          this.debouncedWarehouseLookup();
        })
        .catch(() => {
          setStatus(this.warehouseStatus, 'Не вдалося підготувати пошук відділень. Можна ввести дані вручну.', 'error');
        });
      return;
    }

    setStatus(this.warehouseStatus, 'Шукаємо відділення або поштомат…', 'loading');
    this.debouncedWarehouseLookup();
  }

  handleWarehouseFocus() {
    if (this.lookupDisabled || this.warehouseInput.value.trim()) {
      return;
    }

    this.ensureCitySelection()
      .then((resolved) => {
        if (!resolved) {
          setStatus(
            this.warehouseStatus,
            'Оберіть місто зі списку Нової пошти, щоб отримати підказки для відділення.',
            '',
          );
          return;
        }
        this.fetchWarehouses();
      })
      .catch(() => {
        setStatus(this.warehouseStatus, 'Не вдалося підготувати пошук відділень. Можна ввести дані вручну.', 'error');
      });
  }

  async ensureCitySelection() {
    if (this.selectedSettlementRef || this.selectedCityRef) {
      return true;
    }

    const query = this.cityInput.value.trim();
    if (query.length < CITY_MIN_CHARS) {
      return false;
    }

    const items = await this.fetchCities({ silent: true });
    const normalizedQuery = normalizeValue(query);
    const exactMatch = items.find((item) => {
      const label = normalizeValue(item.label);
      const mainDescription = normalizeValue(item.main_description);
      return (
        label === normalizedQuery ||
        mainDescription === normalizedQuery ||
        label.startsWith(`${normalizedQuery},`) ||
        label.startsWith(`${normalizedQuery} `)
      );
    });

    if (!exactMatch) {
      return false;
    }

    this.selectCity(exactMatch, { focusWarehouse: false });
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
      const response = await fetch(`${this.cityUrl}?q=${encodeURIComponent(query)}&limit=10`, {
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
            payload.error || 'Пошук Нової пошти тимчасово недоступний. Можна ввести місто вручну.',
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
        setStatus(this.cityStatus, 'Не вдалося завантажити список міст. Можна ввести місто вручну.', 'error');
      }
      hideResults(this.cityResults, this.cityInput);
      return [];
    } finally {
      this.cityController = null;
    }
  }

  async fetchWarehouses() {
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
    params.set('limit', '20');

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
        setStatus(
          this.warehouseStatus,
          payload.error || 'Пошук відділень тимчасово недоступний. Можна ввести пункт вручну.',
          response.status === 400 ? '' : 'error',
        );
        hideResults(this.warehouseResults, this.warehouseInput);
        return [];
      }

      const items = Array.isArray(payload.items) ? payload.items : [];
      this.renderWarehouses(items);
      return items;
    } catch (error) {
      if (error.name === 'AbortError') {
        return [];
      }
      setStatus(this.warehouseStatus, 'Не вдалося завантажити список відділень. Можна ввести пункт вручну.', 'error');
      hideResults(this.warehouseResults, this.warehouseInput);
      return [];
    } finally {
      this.warehouseController = null;
    }
  }

  renderCities(items) {
    if (!items.length) {
      hideResults(this.cityResults, this.cityInput);
      setStatus(this.cityStatus, 'За цим запитом місто не знайдено. Можна продовжити вручну.', '');
      return;
    }

    this.cityResults.innerHTML = '';
    items.forEach((item) => {
      const button = createOptionButton(item, (current) => {
        const meta = [];
        if (current.settlement_type) {
          meta.push(current.settlement_type);
        }
        if (current.area || current.region) {
          meta.push([current.area, current.region].filter(Boolean).join(', '));
        }
        if (current.warehouses) {
          meta.push(`Доступно пунктів: ${current.warehouses}`);
        }
        return meta.join(' • ');
      });
      button.dataset.itemJson = JSON.stringify(item);
      button.addEventListener('click', () => this.selectCity(item));
      this.cityResults.appendChild(button);
    });

    showResults(this.cityResults, this.cityInput);
    setStatus(this.cityStatus, 'Оберіть місто зі списку Нової пошти.', '');
  }

  renderWarehouses(items) {
    if (!items.length) {
      hideResults(this.warehouseResults, this.warehouseInput);
      setStatus(this.warehouseStatus, 'За цим запитом нічого не знайдено. Можна продовжити вручну.', '');
      return;
    }

    this.warehouseResults.innerHTML = '';
    items.forEach((item) => {
      const button = createOptionButton(item, (current) => {
        const meta = [current.kind === 'postomat' ? 'Поштомат' : 'Відділення'];
        if (current.number) {
          meta.push(`№${current.number}`);
        }
        if (current.description && current.description !== current.label) {
          meta.push(current.description);
        }
        return meta.join(' • ');
      });
      button.dataset.itemJson = JSON.stringify(item);
      button.addEventListener('click', () => this.selectWarehouse(item));
      this.warehouseResults.appendChild(button);
    });

    showResults(this.warehouseResults, this.warehouseInput);
    setStatus(this.warehouseStatus, 'Оберіть відділення або поштомат зі списку Нової пошти.', '');
  }

  selectCity(item, options = {}) {
    const focusWarehouse = options.focusWarehouse !== false;
    const nextLabel = item.label || '';
    const nextSettlementRef = item.settlement_ref || item.legacy_ref || '';
    const nextCityRef = item.city_ref || item.legacy_ref || '';
    const cityChanged =
      this.selectedCityLabel &&
      normalizeValue(this.selectedCityLabel) !== normalizeValue(nextLabel);

    this.selectedSettlementRef = nextSettlementRef;
    this.selectedCityRef = nextCityRef;
    this.selectedCityLabel = nextLabel;
    if (this.settlementRefInput) {
      this.settlementRefInput.value = nextSettlementRef;
    }
    if (this.cityRefInput) {
      this.cityRefInput.value = nextCityRef;
    }

    this.skipCityInputHandler = true;
    this.cityInput.value = nextLabel;
    this.cityInput.dispatchEvent(new Event('input', { bubbles: true }));
    this.cityInput.dispatchEvent(new Event('change', { bubbles: true }));
    hideResults(this.cityResults, this.cityInput);
    setStatus(this.cityStatus, `Місто вибрано: ${nextLabel}`, 'success');

    if (cityChanged || !this.selectedWarehouseRef) {
      this.clearWarehouseSelection({ preserveInput: false });
    }
    if (focusWarehouse) {
      window.requestAnimationFrame(() => this.warehouseInput.focus());
    }
  }

  selectWarehouse(item) {
    const nextLabel = item.label || '';
    const nextRef = item.ref || '';
    this.selectedWarehouseRef = nextRef;
    this.selectedWarehouseLabel = nextLabel;
    if (this.warehouseRefInput) {
      this.warehouseRefInput.value = nextRef;
    }

    this.skipWarehouseInputHandler = true;
    this.warehouseInput.value = nextLabel;
    this.warehouseInput.dispatchEvent(new Event('input', { bubbles: true }));
    this.warehouseInput.dispatchEvent(new Event('change', { bubbles: true }));
    hideResults(this.warehouseResults, this.warehouseInput);
    setStatus(
      this.warehouseStatus,
      `Пункт доставки вибрано: ${item.kind === 'postomat' ? 'поштомат' : 'відділення'}.`,
      'success',
    );
  }

  clearCitySelection(options = {}) {
    this.selectedSettlementRef = '';
    this.selectedCityRef = '';
    this.selectedCityLabel = options.preserveInput ? this.cityInput.value.trim() : '';
    if (this.settlementRefInput) {
      this.settlementRefInput.value = '';
    }
    if (this.cityRefInput) {
      this.cityRefInput.value = '';
    }
    if (!options.preserveInput) {
      this.skipCityInputHandler = true;
      this.cityInput.value = '';
      this.cityInput.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }

  clearWarehouseSelection(options = {}) {
    this.selectedWarehouseRef = '';
    this.selectedWarehouseLabel = options.preserveInput ? this.warehouseInput.value.trim() : '';
    if (this.warehouseRefInput) {
      this.warehouseRefInput.value = '';
    }
    if (!options.preserveInput) {
      this.skipWarehouseInputHandler = true;
      this.warehouseInput.value = '';
      this.warehouseInput.dispatchEvent(new Event('input', { bubbles: true }));
      this.warehouseInput.dispatchEvent(new Event('change', { bubbles: true }));
      setStatus(this.warehouseStatus, 'Після вибору міста почніть вводити номер або адресу відділення.', '');
    }
  }
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
    controller.init();
  });
}
