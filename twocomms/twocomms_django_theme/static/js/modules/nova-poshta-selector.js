const CITY_MIN_CHARS = 2;
const SEARCH_DEBOUNCE_MS = 250;
const controllerRegistry = new WeakMap();

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
  const err = ensureErrorNode(field);
  if (err) {
    err.textContent = message;
    err.style.display = 'block';
  }
}

function clearFieldError(field) {
  if (!field) {
    return;
  }
  field.classList.remove('cart-form-input-error');
  field.classList.remove('is-invalid');
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

    this.lookupDisabled = false;
    this.selectedSettlementRef = '';
    this.selectedCityRef = '';
    this.selectedCityToken = '';
    this.selectedCityLabel = '';
    this.selectedWarehouseRef = '';
    this.selectedWarehouseToken = '';
    this.selectedWarehouseLabel = '';
    this.activeKind = 'all';

    this.skipCityInputHandler = false;
    this.skipWarehouseInputHandler = false;
    this.skipSubmitValidation = false;
    this.isSubmitting = false;
    this.cityController = null;
    this.warehouseController = null;

    this.handleDocumentClick = this.handleDocumentClick.bind(this);
    this.handleCityInput = this.handleCityInput.bind(this);
    this.handleWarehouseInput = this.handleWarehouseInput.bind(this);
    this.handleWarehouseFocus = this.handleWarehouseFocus.bind(this);
    this.handleSubmit = this.handleSubmit.bind(this);

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
        this.kindButtons.forEach((item) => item.classList.toggle('is-active', item === button));
        this.clearWarehouseSelection({ preserveInput: false });
        if (this.selectedSettlementRef || this.selectedCityRef) {
          this.fetchWarehouses();
        }
      });
    });

    this.form.addEventListener('submit', this.handleSubmit);
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

  async handleSubmit(event) {
    if (this.skipSubmitValidation) {
      this.skipSubmitValidation = false;
      return;
    }

    event.preventDefault();
    if (this.isSubmitting) {
      return;
    }

    this.isSubmitting = true;
    try {
      const isValid = await this.validateSelection({ showErrors: true });
      if (!isValid) {
        return;
      }

      this.skipSubmitValidation = true;
      if (typeof this.form.requestSubmit === 'function') {
        this.form.requestSubmit();
      } else {
        HTMLFormElement.prototype.submit.call(this.form);
      }
    } finally {
      this.isSubmitting = false;
    }
  }

  async restoreExistingSelection() {
    if (!this.cityInput.value.trim()) {
      setStatus(this.cityStatus, 'Почніть вводити назву міста.', '');
      setStatus(this.warehouseStatus, 'Після вибору міста почніть вводити номер або адресу відділення.', '');
      return;
    }

    if (this.selectedCityToken && this.selectedWarehouseToken) {
      setStatus(this.cityStatus, 'Місто підтверджено в довіднику Нової пошти.', 'success');
      setStatus(this.warehouseStatus, 'Пункт доставки підтверджено в довіднику Нової пошти.', 'success');
      return;
    }

    setStatus(this.cityStatus, 'Перевіряємо збережене місто в довіднику Нової пошти…', 'loading');
    const cityResolved = await this.ensureCitySelection({ silent: true });
    if (!cityResolved) {
      setStatus(this.cityStatus, 'Підтвердіть місто, обравши його зі списку Нової пошти.', '');
      setStatus(this.warehouseStatus, 'Після підтвердження міста оберіть відділення або поштомат зі списку.', '');
      return;
    }

    if (!this.warehouseInput.value.trim()) {
      setStatus(this.warehouseStatus, 'Після вибору міста почніть вводити номер або адресу відділення.', '');
      return;
    }

    setStatus(this.warehouseStatus, 'Перевіряємо збережений пункт доставки в довіднику Нової пошти…', 'loading');
    const warehouseResolved = await this.ensureWarehouseSelection({ silent: true });
    if (!warehouseResolved) {
      setStatus(
        this.warehouseStatus,
        'Підтвердіть відділення або поштомат, обравши його зі списку Нової пошти.',
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
      setStatus(this.cityStatus, 'Почніть вводити назву міста.', '');
      return;
    }
    if (currentValue.length < CITY_MIN_CHARS) {
      hideResults(this.cityResults, this.cityInput);
      setStatus(this.cityStatus, 'Введіть щонайменше 2 символи для пошуку міста.', '');
      return;
    }
    if (this.lookupDisabled) {
      setStatus(
        this.cityStatus,
        'Довідник Нової пошти тимчасово недоступний. Спробуйте ще раз трохи пізніше.',
        'error',
      );
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

    clearFieldError(this.warehouseInput);
    const currentValue = this.warehouseInput.value.trim();
    if (this.selectedWarehouseLabel && normalizeValue(currentValue) !== normalizeValue(this.selectedWarehouseLabel)) {
      this.clearWarehouseSelection({ preserveInput: true });
    }

    if (this.lookupDisabled) {
      setStatus(
        this.warehouseStatus,
        'Довідник Нової пошти тимчасово недоступний. Спробуйте ще раз трохи пізніше.',
        'error',
      );
      return;
    }

    if (!currentValue && (this.selectedSettlementRef || this.selectedCityRef)) {
      setStatus(this.warehouseStatus, 'Почніть вводити номер або адресу відділення.', '');
      return;
    }

    if (!(this.selectedSettlementRef || this.selectedCityRef)) {
      this.ensureCitySelection({ silent: true })
        .then((resolved) => {
          if (!resolved) {
            hideResults(this.warehouseResults, this.warehouseInput);
            setStatus(
              this.warehouseStatus,
              'Спочатку оберіть місто зі списку Нової пошти.',
              '',
            );
            return;
          }
          setStatus(this.warehouseStatus, 'Шукаємо відділення або поштомат…', 'loading');
          this.debouncedWarehouseLookup();
        })
        .catch(() => {
          setStatus(
            this.warehouseStatus,
            'Не вдалося підготувати пошук відділень Нової пошти. Спробуйте ще раз.',
            'error',
          );
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

    this.ensureCitySelection({ silent: true })
      .then((resolved) => {
        if (!resolved) {
          setStatus(
            this.warehouseStatus,
            'Спочатку оберіть місто зі списку Нової пошти.',
            '',
          );
          return;
        }
        this.fetchWarehouses();
      })
      .catch(() => {
        setStatus(
          this.warehouseStatus,
          'Не вдалося підготувати пошук відділень Нової пошти. Спробуйте ще раз.',
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
            payload.error || 'Довідник Нової пошти тимчасово недоступний. Спробуйте ще раз трохи пізніше.',
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
          'Не вдалося завантажити список міст Нової пошти. Спробуйте ще раз.',
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
            payload.error || 'Довідник Нової пошти тимчасово недоступний. Спробуйте ще раз трохи пізніше.',
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
          'Не вдалося завантажити список відділень Нової пошти. Спробуйте ще раз.',
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
      setStatus(this.cityStatus, 'За цим запитом місто не знайдено. Уточніть назву і виберіть варіант зі списку.', '');
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
      setStatus(
        this.warehouseStatus,
        'За цим запитом нічого не знайдено. Уточніть номер або адресу і виберіть пункт зі списку.',
        '',
      );
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
      'Місто підтверджено в довіднику Нової пошти.',
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
      `Пункт доставки підтверджено: ${item.kind === 'postomat' ? 'поштомат' : 'відділення'}.`,
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
      setStatus(this.warehouseStatus, 'Після вибору міста почніть вводити номер або адресу відділення.', '');
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
        setFieldError(this.cityInput, 'Оберіть місто зі списку Нової пошти.');
        setStatus(this.cityStatus, 'Потрібно обрати місто зі списку Нової пошти.', 'error');
      }
    }

    const hasWarehouseSelection = valid
      ? await this.ensureWarehouseSelection({ silent: !showErrors })
      : false;
    if (!hasWarehouseSelection || !this.selectedWarehouseToken) {
      valid = false;
      if (showErrors) {
        setFieldError(this.warehouseInput, 'Оберіть відділення або поштомат зі списку Нової пошти.');
        setStatus(
          this.warehouseStatus,
          'Потрібно обрати відділення або поштомат зі списку Нової пошти.',
          'error',
        );
      }
    }

    if (!valid) {
      const first = this.form.querySelector('.cart-form-input-error');
      if (first && showErrors) {
        first.scrollIntoView({ behavior: 'smooth', block: 'center' });
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
