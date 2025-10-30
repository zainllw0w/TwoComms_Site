import { scheduleIdle, getCookie } from './modules/shared.js';
import { ImageOptimizer } from './modules/optimizers.js';

const qs = (selector, scope = document) => scope.querySelector(selector);
const qsa = (selector, scope = document) => Array.from(scope.querySelectorAll(selector));

const toInt = (value, fallback = 0) => {
  const parsed = parseInt(value, 10);
  return Number.isNaN(parsed) ? fallback : parsed;
};

class EventBus {
  constructor() {
    this.listeners = new Map();
  }

  on(event, handler) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event).add(handler);
  }

  off(event, handler) {
    if (!this.listeners.has(event)) return;
    this.listeners.get(event).delete(handler);
  }

  emit(event, payload) {
    if (!this.listeners.has(event)) return;
    for (const handler of this.listeners.get(event)) {
      try {
        handler(payload);
      } catch (error) {
        console.error(`[builder:event:${event}]`, error);
      }
    }
  }
}

class ProductBuilder {
  constructor(root) {
    this.root = root;
    this.form = qs('[data-builder-form]', root);
    this.sidebar = qs('[data-builder-sidebar]', root);
    this.progressBar = qs('[data-progress-bar]', root);
    this.progressValue = qs('[data-progress-value]', root);
    this.checklist = qs('[data-checklist]', root);
    this.sections = qsa('[data-step]', root);
    this.eventBus = new EventBus();

    this.initialProgress = this.readInitialProgress();
    this.initialPercent = Number(root.dataset.progressPercent || 0);
    this.endpoints = this.readEndpoints();

    // Инициализация width прогресс-бара из data-width атрибута
    if (this.progressBar && this.progressBar.dataset.width) {
      this.progressBar.style.width = `${this.progressBar.dataset.width}%`;
    }

    this.autosavePending = false;

    this.variantZone = null;
    this.variantTemplate = null;
    this.variantTotalInput = null;
    this.addVariantBtn = null;

    this.sizeGridList = qs('[data-size-grid-list]', root);
    this.toastContainer = null;
  }

  init() {
    if (!this.root || !this.form) {
      console.warn('[ProductBuilder] Не знайдено форму для конструктора');
      return;
    }

    this.initSteps();
    this.bindFormHandlers();
    this.registerDefaultListeners();
    this.setupVariantControls();
    this.setupCatalogListeners();
    this.setupMediaUploads();
    this.setupFeaturePlaceholders();
    this.updateCounters();
    this.evaluateSteps();
    this.calculateProgress();
  }

  readEndpoints() {
    return {
      base: this.root.dataset.endpointBase || '',
      detail: this.root.dataset.endpointDetail || '',
      newProduct: this.root.dataset.endpointNew || '',
      catalogDetail: this.root.dataset.endpointCatalog || '',
    };
  }

  readInitialProgress() {
    return {
      basic: this.root.dataset.progressBasic === 'true',
      catalog: this.root.dataset.progressCatalog === 'true',
      colors: this.root.dataset.progressColors === 'true',
      seo: this.root.dataset.progressSeo === 'true',
      preview: this.root.dataset.progressPreview === 'true',
    };
  }

  initSteps() {
    this.sections.forEach(section => {
      const name = section.dataset.step;
      if (!name) return;
      this.stateSteps().set(name, {
        element: section,
        completed: Boolean(this.initialProgress[name]),
        touched: false,
      });
    });

    this.syncChecklistUI();
    this.updateProgressUI(this.initialPercent);
  }

  stateSteps() {
    if (!this._stateSteps) {
      this._stateSteps = new Map();
    }
    return this._stateSteps;
  }

  bindFormHandlers() {
    this.form.addEventListener('input', evt => {
      const section = evt.target.closest('[data-step]');
      if (!section) return;
      const stepName = section.dataset.step;
      const step = this.stateSteps().get(stepName);
      if (!step) return;

      if (!step.touched) {
        step.touched = true;
        this.eventBus.emit('step:touched', stepName);
      }

      scheduleIdle(() => {
        this.updateVariantPreview(evt.target.closest('[data-variant-row]'));
        this.updateCounters();
      });
    });

    this.form.addEventListener('submit', evt => {
      // Форма має відправлятися стандартно, а JS використовується для UX
      this.eventBus.emit('form:submit', new FormData(this.form));
    });
  }

  registerDefaultListeners() {
    this.eventBus.on('autosave:trigger', () => {
      if (this.autosavePending) return;
      this.autosavePending = true;
      setTimeout(() => {
        this.autosavePending = false;
        this.eventBus.emit('autosave:done');
      }, 500);
    });

    const autosaveBtn = qs('[data-action="autosave"]', this.sidebar);
    if (autosaveBtn) {
      autosaveBtn.addEventListener('click', () => {
        this.eventBus.emit('autosave:trigger');
      });

      this.eventBus.on('autosave:done', () => {
        autosaveBtn.classList.add('btn-success');
        setTimeout(() => autosaveBtn.classList.remove('btn-success'), 800);
      });
    }
  }

  setupVariantControls() {
    this.variantZone = qs('[data-dnd-zone]', this.root);
    this.variantTemplate = qs('#builder-variant-template', this.root);
    this.variantTotalInput = this.form.querySelector('input[name="color_variants-TOTAL_FORMS"]');
    this.addVariantBtn = qs('[data-action="add-variant"]', this.root);

    if (this.addVariantBtn) {
      this.addVariantBtn.addEventListener('click', evt => {
        evt.preventDefault();
        this.addVariant();
      });
    }

    if (this.variantZone) {
      this.variantCards(true).forEach(card => this.prepareVariantCard(card));
      this.setupDragAndDrop();
    }
  }

  setupCatalogListeners() {
    const catalogSelect = this.form.querySelector('select[name="product-catalog"]');
    if (!catalogSelect) return;

    catalogSelect.addEventListener('change', () => {
      this.handleCatalogChange(catalogSelect.value);
    });

    if (catalogSelect.value) {
      scheduleIdle(() => this.handleCatalogChange(catalogSelect.value));
    }
  }

  setupMediaUploads() {
    const mainInput = this.form.querySelector('[data-main-image-input]');
    const mainPreview = this.form.querySelector('[data-main-image-preview]');
    if (mainInput && mainPreview) {
      mainInput.addEventListener('change', evt => {
        const [file] = Array.from(evt.target.files || []);
        if (!file) {
          mainPreview.innerHTML = '<span class="placeholder-icon"><i class="fas fa-image"></i></span>';
          return;
        }
        const img = document.createElement('img');
        const url = URL.createObjectURL(file);
        img.src = url;
        img.onload = () => URL.revokeObjectURL(url);
        mainPreview.innerHTML = '';
        mainPreview.appendChild(img);
      });
    }

    const extraInput = this.form.querySelector('[data-extra-images-input]');
    const extraList = this.form.querySelector('[data-extra-upload-list]');
    if (extraInput && extraList) {
      extraInput.addEventListener('change', evt => {
        const files = Array.from(evt.target.files || []);
        extraList.innerHTML = '';
        if (!files.length) {
          const empty = document.createElement('span');
          empty.className = 'text-muted small';
          empty.textContent = 'Файли не обрано';
          extraList.appendChild(empty);
          return;
        }
        const fragment = document.createDocumentFragment();
        files.forEach(file => {
          const chip = document.createElement('span');
          chip.textContent = `${file.name} (${Math.round(file.size / 1024)} КБ)`;
          fragment.appendChild(chip);
        });
        extraList.appendChild(fragment);
      });
    }
  }

  setupFeaturePlaceholders() {
    const targets = qsa('[data-feature-placeholder]', this.root);
    if (!targets.length) return;
    targets.forEach(element => {
      element.classList.add('is-placeholder');
      element.setAttribute('aria-disabled', 'true');
      element.addEventListener('click', evt => {
        evt.preventDefault();
        const message = element.dataset.placeholderMessage || 'Функція в розробці.';
        this.showToast(message, 'info');
      });
    });
  }

  ensureToastContainer() {
    if (this.toastContainer) return this.toastContainer;
    const container = document.createElement('div');
    container.className = 'builder-toast-container';
    this.root.appendChild(container);
    this.toastContainer = container;
    return container;
  }

  showToast(message, tone = 'info') {
    const container = this.ensureToastContainer();
    const toast = document.createElement('div');
    toast.className = `builder-toast builder-toast--${tone}`;
    toast.textContent = message;
    container.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('is-visible'));
    setTimeout(() => {
      toast.classList.remove('is-visible');
      toast.addEventListener('transitionend', () => toast.remove(), { once: true });
    }, 3200);
  }

  handleCatalogChange(catalogId) {
    if (!this.endpoints.catalogDetail) return;
    if (!catalogId) {
      this.clearSizeGridPreview('Оберіть каталог, щоб переглянути варіанти сіток.');
      return;
    }

    const url = `${this.endpoints.catalogDetail}${catalogId}/`;
    this.fetchJSON(url)
      .then(data => {
        this.updateSizeGridPreview(data?.catalog);
      })
      .catch(() => {
        this.clearSizeGridPreview('Не вдалося отримати інформацію про каталог.');
      });
  }

  fetchJSON(url, options) {
    return fetch(url, options).then(response => {
      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }
      return response.json();
    });
  }

  updateSizeGridPreview(catalog) {
    if (!this.sizeGridList) return;
    this.sizeGridList.innerHTML = '';

    if (!catalog || !catalog.size_grids || !catalog.size_grids.length) {
      this.sizeGridList.innerHTML = '<span class="text-muted small">Для цього каталогу немає попередньо збережених сіток.</span>';
      return;
    }

    const fragment = document.createDocumentFragment();
    catalog.size_grids.forEach(grid => {
      const item = document.createElement('div');
      item.className = 'size-grid-preview-item';
      const description = grid.description ? `<p>${grid.description}</p>` : '';
      item.innerHTML = `<h6>${grid.name}</h6>${description}`;
      fragment.appendChild(item);
    });
    this.sizeGridList.append(fragment);
  }

  clearSizeGridPreview(message) {
    if (!this.sizeGridList) return;
    this.sizeGridList.innerHTML = `<span class="text-muted small">${message}</span>`;
  }

  setupDragAndDrop() {
    if (!this.variantZone) return;

    this.variantZone.addEventListener('dragstart', evt => {
      const card = evt.target.closest('[data-variant-row]');
      if (!card || card.classList.contains('is-deleted')) return;
      evt.dataTransfer.effectAllowed = 'move';
      evt.dataTransfer.setData('text/plain', card.dataset.variantOrder || '0');
      card.classList.add('is-dragging');
      this.draggedCard = card;
    });

    this.variantZone.addEventListener('dragover', evt => {
      if (!this.draggedCard) return;
      evt.preventDefault();
      const target = evt.target.closest('[data-variant-row]');
      if (!target || target === this.draggedCard || target.classList.contains('is-deleted')) return;
      const bounds = target.getBoundingClientRect();
      const shouldInsertAfter = (evt.clientY - bounds.top) > bounds.height / 2;
      this.variantZone.insertBefore(this.draggedCard, shouldInsertAfter ? target.nextSibling : target);
    });

    const finalize = () => {
      if (!this.draggedCard) return;
      this.draggedCard.classList.remove('is-dragging');
      this.draggedCard = null;
      this.commitVariantOrder();
    };

    this.variantZone.addEventListener('drop', evt => {
      evt.preventDefault();
      finalize();
    });

    this.variantZone.addEventListener('dragend', finalize);
  }

  commitVariantOrder() {
    this.variantCards().forEach((card, index) => {
      card.dataset.variantOrder = String(index);
      const orderInput = card.querySelector('input[name$="-order"]');
      if (orderInput) {
        orderInput.value = index;
      }
    });
    this.updateCounters();
  }

  addVariant() {
    if (!this.variantTemplate || !this.variantZone || !this.variantTotalInput) return;
    const currentTotal = toInt(this.variantTotalInput.value, 0);
    const variantPrefix = `color_variants-${currentTotal}`;

    let html = this.variantTemplate.innerHTML;
    html = html.replace(/color_variants-__prefix__/g, variantPrefix);
    html = html.replace(/__prefix__/g, currentTotal);

    const wrapper = document.createElement('div');
    wrapper.innerHTML = html.trim();
    const card = wrapper.firstElementChild;
    if (!card) return;

    card.dataset.newVariant = 'true';
    card.dataset.formPrefix = variantPrefix;
    this.variantZone.appendChild(card);

    this.variantTotalInput.value = currentTotal + 1;
    this.prepareVariantCard(card);
    this.commitVariantOrder();
  }

  variantCards(includeDeleted = false) {
    if (!this.variantZone) return [];
    const cards = qsa('[data-variant-row]', this.variantZone);
    return includeDeleted ? cards : cards.filter(card => !card.classList.contains('is-deleted'));
  }

  prepareVariantCard(card) {
    if (!card) return;
    const prefix = card.dataset.formPrefix || this.deriveFormPrefix(card);
    card.dataset.formPrefix = prefix;

    const deleteBtn = qs('[data-action="delete-variant"]', card);
    if (deleteBtn) {
      deleteBtn.addEventListener('click', evt => {
        evt.preventDefault();
        this.deleteVariant(card);
      });
    }

    const defaultBtn = qs('[data-action="set-default"]', card);
    if (defaultBtn) {
      defaultBtn.addEventListener('click', evt => {
        evt.preventDefault();
        this.setDefaultVariant(card);
      });
    }

    const nameInput = card.querySelector(`input[name="${prefix}-name"]`);
    if (nameInput) {
      nameInput.addEventListener('input', () => {
        this.updateVariantPreview(card);
        this.updateCounters();
      });
    }

    const primaryInput = card.querySelector(`input[name="${prefix}-primary_hex"]`);
    if (primaryInput) {
      primaryInput.addEventListener('input', () => this.updateVariantPreview(card));
    }

    const secondaryInput = card.querySelector(`input[name="${prefix}-secondary_hex"]`);
    if (secondaryInput) {
      secondaryInput.addEventListener('input', () => this.updateVariantPreview(card));
    }

    this.prepareImageGallery(card);
    this.syncDefaultState(card);
    this.updateVariantPreview(card);
  }

  deriveFormPrefix(card) {
    const hidden = card.querySelector('input[name$="-id"]');
    if (!hidden) return '';
    return hidden.name.replace(/-id$/, '');
  }

  syncDefaultState(card) {
    const checkbox = card.querySelector('input[name$="-is_default"]');
    if (!checkbox) return;
    card.classList.toggle('is-default', checkbox.checked || checkbox.value === 'on');
  }

  deleteVariant(card) {
    const deleteInput = card.querySelector('input[name$="-DELETE"]');
    if (deleteInput) {
      deleteInput.value = 'on';
      if (deleteInput.type === 'checkbox') deleteInput.checked = true;
    }
    card.classList.add('is-deleted');
    card.style.display = 'none';
    this.updateCounters();
  }

  setDefaultVariant(card) {
    const checkbox = card.querySelector('input[name$="-is_default"]');
    if (!checkbox) return;
    this.variantCards(true).forEach(other => {
      const otherCheckbox = other.querySelector('input[name$="-is_default"]');
      if (!otherCheckbox) return;
      const isDefault = other === card && !other.classList.contains('is-deleted');
      otherCheckbox.checked = isDefault;
      otherCheckbox.value = isDefault ? 'on' : '';
      other.classList.toggle('is-default', isDefault);
    });
  }

  updateVariantPreview(card) {
    if (!card) return;
    const preview = qs('[data-color-preview]', card);
    const nameHeading = qs('.variant-header h6', card);
    const nameInput = card.querySelector('input[name$="-name"]');
    const primaryInput = card.querySelector('input[name$="-primary_hex"]');
    const secondaryInput = card.querySelector('input[name$="-secondary_hex"]');

    if (nameHeading && nameInput) {
      nameHeading.textContent = nameInput.value || 'Новий колір';
    }
    if (preview && primaryInput) {
      preview.style.setProperty('--primary', primaryInput.value || '#000000');
    }
    if (preview && secondaryInput) {
      preview.style.setProperty('--secondary', secondaryInput.value || '');
    }
  }

  prepareImageGallery(card) {
    const gallery = qs('[data-variant-gallery]', card);
    if (!gallery) return;

    const list = qs('[data-image-list]', gallery);
    const template = qs('template[data-image-template]', gallery);
    const addInput = qs('[data-action="add-image"] input[type="file"]', gallery);

    if (addInput) {
      addInput.addEventListener('change', evt => {
        const files = Array.from(evt.target.files || []);
        if (!files.length) return;
        files.forEach(file => this.addImageForm(card, file));
        evt.target.value = '';
      });
    }

    gallery.addEventListener('click', evt => {
      const btn = evt.target.closest('[data-action="delete-image"]');
      if (!btn) return;
      evt.preventDefault();
      const imageCard = btn.closest('.image-card');
      if (imageCard) {
        this.deleteImage(imageCard);
      }
    });

    qsa('.image-card', list).forEach(imageCard => this.syncImageState(imageCard));
  }

  addImageForm(card, file) {
    const gallery = qs('[data-variant-gallery]', card);
    if (!gallery) return;

    const list = qs('[data-image-list]', gallery);
    const template = qs('template[data-image-template]', gallery);
    const totalInput = gallery.querySelector('input[name$="-TOTAL_FORMS"]');
    if (!list || !template || !totalInput) return;

    const variantPrefix = card.dataset.formPrefix || this.deriveFormPrefix(card);
    const newIndex = toInt(totalInput.value, 0);

    let html = template.innerHTML;
    html = html.replace(/color_variants-__prefix__/g, variantPrefix);
    html = html.replace(/__prefix__/g, newIndex);

    const wrapper = document.createElement('div');
    wrapper.innerHTML = html.trim();
    const node = wrapper.firstElementChild;
    if (!node) return;

    list.appendChild(node);
    totalInput.value = newIndex + 1;

    if (file) {
      const fileInput = node.querySelector('input[type="file"]');
      if (fileInput) {
        const dt = new DataTransfer();
        dt.items.add(file);
        fileInput.files = dt.files;
      }
      const preview = node.querySelector('[data-image-preview]');
      if (preview) {
        const img = document.createElement('img');
        const url = URL.createObjectURL(file);
        img.src = url;
        img.onload = () => URL.revokeObjectURL(url);
        preview.innerHTML = '';
        preview.appendChild(img);
      }
    }

    this.updateCounters();
  }

  deleteImage(imageCard) {
    const deleteInput = imageCard.querySelector('input[name$="-DELETE"]');
    if (deleteInput) {
      deleteInput.value = 'on';
      if (deleteInput.type === 'checkbox') deleteInput.checked = true;
    }
    imageCard.classList.add('is-deleted');
    this.updateCounters();
  }

  syncImageState(imageCard) {
    const deleteInput = imageCard.querySelector('input[name$="-DELETE"]');
    if (deleteInput && (deleteInput.checked || deleteInput.value === 'on')) {
      imageCard.classList.add('is-deleted');
    }
  }

  updateCounters() {
    const colorBadge = qs('#colors-count', this.root);
    const imageBadge = qs('#images-count', this.root);

    const activeVariants = this.variantCards();
    if (colorBadge) {
      colorBadge.textContent = String(activeVariants.length);
    }

    let imageCount = 0;
    activeVariants.forEach(card => {
      const gallery = qs('[data-variant-gallery]', card);
      if (!gallery) return;
      const images = qsa('.image-card', gallery).filter(imageCard => !imageCard.classList.contains('is-deleted'));
      imageCount += images.length;
    });

    if (imageBadge) {
      imageBadge.textContent = String(imageCount);
    }

    this.evaluateSteps();
    this.calculateProgress();
  }

  updateProgressUI(percent) {
    const clamped = Math.min(Math.max(Number(percent) || 0, 0), 100);
    if (this.progressBar) {
      this.progressBar.style.width = `${clamped}%`;
      this.progressBar.setAttribute('aria-valuenow', String(clamped));
    }
    if (this.progressValue) {
      this.progressValue.textContent = `${clamped}%`;
    }
    this.syncChecklistUI();
  }

  syncChecklistUI() {
    if (!this.checklist) return;
    this.stateSteps().forEach((step, name) => {
      const item = qs(`[data-checklist-item="${name}"]`, this.checklist);
      if (!item) return;
      item.classList.toggle('is-complete', step.completed);
      const icon = qs('[data-checklist-icon]', item);
      if (!icon) return;
      if (step.completed) {
        icon.classList.remove('far', 'fa-circle', 'text-muted');
        icon.classList.add('fas', 'fa-check-circle', 'text-success');
      } else {
        icon.classList.remove('fas', 'fa-check-circle', 'text-success');
        icon.classList.add('far', 'fa-circle', 'text-muted');
      }
    });
  }

  evaluateSteps() {
    this.stateSteps().forEach((step, name) => {
      step.completed = this.evaluateStep(name);
    });
    this.syncChecklistUI();
  }

  evaluateStep(name) {
    switch (name) {
      case 'basic':
        return this.basicStepCompleted();
      case 'catalog':
        return this.catalogStepCompleted();
      case 'colors':
        return this.colorsStepCompleted();
      case 'seo':
        return this.seoStepCompleted();
      case 'preview':
        return this.previewStepCompleted();
      default:
        return this.stateSteps().get(name)?.completed || false;
    }
  }

  basicStepCompleted() {
    const title = this.fieldValue('product-title');
    const category = this.fieldValue('product-category');
    const price = this.fieldValue('product-price');
    return Boolean(title && category && price);
  }

  catalogStepCompleted() {
    const catalog = this.fieldValue('product-catalog');
    return Boolean(catalog);
  }

  colorsStepCompleted() {
    return this.variantCards().length > 0;
  }

  seoStepCompleted() {
    const title = this.fieldValue('seo-seo_title');
    const description = this.fieldValue('seo-seo_description');
    const keywords = this.fieldValue('seo-seo_keywords');
    return Boolean(title || description || keywords);
  }

  previewStepCompleted() {
    const status = this.fieldValue('product-status');
    return Boolean(status && status !== 'draft');
  }

  calculateProgress() {
    const steps = this.stateSteps();
    if (!steps.size) return;
    let completed = 0;
    steps.forEach(step => {
      if (step.completed) completed += 1;
    });
    const percent = Math.round((completed / steps.size) * 100);
    this.updateProgressUI(percent);
  }

  fieldValue(fieldName) {
    const input = this.form.querySelector(`[name="${fieldName}"]`);
    if (!input) return '';
    if (input.type === 'checkbox') {
      return input.checked ? 'on' : '';
    }
    return (input.value || '').trim();
  }
}

function initialiseProductBuilder() {
  const root = document.querySelector('[data-product-builder]');
  if (!root) return;

  const builder = new ProductBuilder(root);
  builder.init();

  // Оптимізація існуючих скриптів
  document.documentElement.classList.add('js-ready');
  scheduleIdle(() => ImageOptimizer.init());

  window.twcProductBuilder = builder;
}

document.addEventListener('DOMContentLoaded', initialiseProductBuilder);
