(() => {
  const orderModal = document.getElementById('ds-order-modal');
  const productModal = document.getElementById('ds-product-modal');
  const orderForm = document.getElementById('ds-order-form');
  const orderItemsContainer = document.getElementById('ds-order-items');
  const productResults = document.getElementById('ds-product-results');
  const productSearchForm = document.getElementById('ds-product-search');
  const csrfTokenMeta = document.querySelector('meta[name="csrf-token"]');
  const csrfToken = csrfTokenMeta ? csrfTokenMeta.getAttribute('content') : '';

  const toast = createToast();
  let orderItems = [];
  let searchAbortController = null;
  let searchDebounceTimer = null;

  if (!orderModal || !productModal || !orderForm) {
    return;
  }

  bindOpeners();
  bindModalDismiss();
  bindOrderForm();
  bindProductSearch();
  bindQuickAddButtons();

  function bindOpeners() {
    document.querySelectorAll('.js-open-order-modal').forEach((btn) => {
      btn.addEventListener('click', () => openModal(orderModal));
    });

    document.querySelectorAll('.js-open-product-modal').forEach((btn) => {
      btn.addEventListener('click', () => {
        openModal(productModal);
        productResults.dataset.emptyText = 'Введіть пошуковий запит, щоб побачити товари.';
        productResults.innerHTML = '';
        orderModal.setAttribute('aria-hidden', 'true');
      });
    });
  }

  function bindModalDismiss() {
    document.querySelectorAll('[data-dismiss-modal]').forEach((el) => {
      el.addEventListener('click', () => {
        const modal = el.closest('.ds-modal');
        if (modal) {
          closeModal(modal);
          if (modal === productModal) {
            orderModal.removeAttribute('aria-hidden');
          }
        }
      });
    });

    [orderModal, productModal].forEach((modal) => {
      modal.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
          closeModal(modal);
        }
      });
    });
  }

  function bindOrderForm() {
    orderForm.addEventListener('submit', (event) => {
      event.preventDefault();
      if (!orderItems.length) {
        showToast('Додайте хоча б один товар до замовлення', 'warning');
        return;
      }

      const formData = new FormData(orderForm);
      const payload = {
        client_name: formData.get('client_name'),
        client_phone: formData.get('client_phone'),
        client_np_address: formData.get('client_np_address'),
        notes: formData.get('notes'),
        items: orderItems.map((item) => ({
          product_id: item.productId,
          color_variant_id: item.colorVariantId || null,
          size: item.size || '',
          quantity: item.quantity,
          drop_price: item.dropPrice,
          selling_price: item.sellingPrice,
        })),
      };

      fetch('/orders/dropshipper/api/create-order/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify(payload),
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.success) {
            showToast(data.message || 'Замовлення створено!');
            orderForm.reset();
            orderItems = [];
            renderOrderItems();
            closeModal(orderModal);
          } else {
            throw new Error(data.message || 'Не вдалося створити замовлення');
          }
        })
        .catch((error) => {
          console.error(error);
          showToast(error.message, 'error');
        });
    });
  }

  function bindProductSearch() {
    if (!productSearchForm || !productResults) {
      return;
    }

    const input = productSearchForm.querySelector('input[name="search"]');
    if (!input) {
      return;
    }

    productSearchForm.addEventListener('submit', (event) => {
      event.preventDefault();
      performSearch(input.value.trim());
    });

    input.addEventListener('input', () => {
      clearTimeout(searchDebounceTimer);
      searchDebounceTimer = setTimeout(() => {
        performSearch(input.value.trim());
      }, 320);
    });
  }

  function bindQuickAddButtons() {
    const quickButtons = document.querySelectorAll('.js-product-quick-add');
    if (!quickButtons.length) {
      return;
    }

    const input = productSearchForm?.querySelector('input[name="search"]');

    quickButtons.forEach((btn) => {
      btn.addEventListener('click', () => {
        openModal(productModal);
        orderModal.setAttribute('aria-hidden', 'true');

        const productName = btn.dataset.productName || '';
        if (input) {
          input.value = productName;
          performSearch(productName);
          input.focus();
        }
      });
    });
  }

  function performSearch(query) {
    if (!query) {
      productResults.innerHTML = '';
      productResults.dataset.emptyText = 'Введіть пошуковий запит, щоб побачити товари.';
      return;
    }

    if (searchAbortController) {
      searchAbortController.abort();
    }

    searchAbortController = new AbortController();
    productResults.dataset.emptyText = 'Завантажуємо товари…';
    productResults.innerHTML = '';

    const searchParams = new URLSearchParams({
      search: query,
      partial: '1',
    });

    fetch(`/orders/dropshipper/products/?${searchParams.toString()}`, {
      signal: searchAbortController.signal,
    })
      .then((response) => response.text())
      .then((html) => {
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        const productCards = Array.from(doc.querySelectorAll('.product-card'));

        if (!productCards.length) {
          productResults.innerHTML = '';
          productResults.dataset.emptyText = 'За цим запитом товари не знайдені.';
          return;
        }

        productResults.innerHTML = '';
        productResults.dataset.emptyText = '';

        productCards.slice(0, 8).forEach((card) => {
          const productId = Number(card.dataset.productId);
          const title = card.querySelector('.product-title')?.textContent?.trim() || 'Товар без назви';
          const dropPrice = parseCurrency(card.querySelector('.drop-price')?.textContent);
          const recommendedPrice = parseCurrency(card.querySelector('.recommended-price')?.textContent);
          const image = card.querySelector('.product-image')?.getAttribute('src');

          const item = document.createElement('article');
          item.className = 'ds-product-card';

          item.innerHTML = `
            <header class="ds-product-card__header">
              <div>
                <div class="ds-product-card__title">${title}</div>
                <div class="ds-product-card__prices">
                  <span>Ціна дропа: <strong>${dropPrice ? `${dropPrice} грн` : '—'}</strong></span>
                  <span>Рекомендована: <strong>${recommendedPrice ? `${recommendedPrice} грн` : '—'}</strong></span>
                </div>
              </div>
              ${image ? `<img src="${image}" alt="" loading="lazy" style="width:56px;height:56px;border-radius:14px;object-fit:cover;">` : ''}
            </header>
            <div class="ds-product-card__action">
              <button type="button" class="ds-btn ds-btn--primary" data-product-id="${productId}">
                <i class="fas fa-arrow-right" aria-hidden="true"></i>
                <span>Обрати</span>
              </button>
            </div>
          `;

          item.querySelector('button')?.addEventListener('click', () => {
            renderProductDetail({ productId, title, dropPrice, recommendedPrice, image });
          });

          productResults.appendChild(item);
        });
      })
      .catch((error) => {
        if (error.name === 'AbortError') {
          return;
        }
        console.error(error);
        showToast('Не вдалося завантажити товари. Спробуйте ще раз.', 'error');
      });
  }

  function renderProductDetail({ productId, title, dropPrice, recommendedPrice, image }) {
    productResults.dataset.emptyText = '';
    productResults.innerHTML = '';

    const wrapper = document.createElement('form');
    wrapper.className = 'ds-form';
    wrapper.addEventListener('submit', (event) => {
      event.preventDefault();
      const formData = new FormData(wrapper);
      const quantity = Number(formData.get('quantity')) || 1;
      const sellingPrice = Number(formData.get('selling_price')) || recommendedPrice || dropPrice || 0;
      const size = formData.get('size') || '';
      const colorVariantId = formData.get('color_variant_id') || '';
      const colorName = formData.get('color_name') || '';

      orderItems.push({
        productId,
        title,
        dropPrice: dropPrice || 0,
        recommendedPrice: recommendedPrice || 0,
        sellingPrice,
        quantity,
        size,
        colorVariantId: colorVariantId ? Number(colorVariantId) : null,
        colorName,
      });

      renderOrderItems();
      showToast('Товар додано до замовлення');
      closeModal(productModal);
      orderModal.removeAttribute('aria-hidden');
    });

    wrapper.innerHTML = `
      <div style="display:grid;gap:18px;">
        <div style="display:flex;gap:16px;align-items:center;">
          ${image ? `<img src="${image}" alt="" loading="lazy" style="width:80px;height:80px;border-radius:14px;object-fit:cover;">` : ''}
          <div>
            <h3 style="margin:0;font-size:1.1rem;">${title}</h3>
            <div style="display:flex;gap:12px;color:var(--ds-text-soft);font-size:0.9rem;">
              <span>Дроп: <strong>${dropPrice ? `${dropPrice} грн` : '—'}</strong></span>
              <span>Рекомендована: <strong>${recommendedPrice ? `${recommendedPrice} грн` : '—'}</strong></span>
            </div>
          </div>
        </div>
        <div class="ds-form__grid">
          <label class="ds-input">
            <span class="ds-input__label">Кількість</span>
            <input type="number" name="quantity" value="1" min="1" required>
          </label>
          <label class="ds-input">
            <span class="ds-input__label">Розмір</span>
            <select name="size">
              <option value="">— Обрати —</option>
            </select>
          </label>
          <label class="ds-input">
            <span class="ds-input__label">Варіант кольору</span>
            <select name="color_variant_id">
              <option value="">— Без кольору —</option>
            </select>
          </label>
          <label class="ds-input">
            <span class="ds-input__label">Ціна продажу, грн</span>
            <input type="number" name="selling_price" value="${recommendedPrice || dropPrice || 0}" min="${dropPrice || 0}" step="0.01" required>
          </label>
        </div>
        <div class="ds-actions" style="justify-content:flex-end;">
          <button type="button" class="ds-btn ds-btn--ghost" data-product-back>
            <i class="fas fa-arrow-left" aria-hidden="true"></i>
            <span>Назад до пошуку</span>
          </button>
          <button type="submit" class="ds-btn ds-btn--primary">
            <i class="fas fa-plus" aria-hidden="true"></i>
            <span>Додати до замовлення</span>
          </button>
        </div>
      </div>
    `;

    wrapper.querySelector('[data-product-back]')?.addEventListener('click', () => {
      productResults.innerHTML = '';
      productResults.dataset.emptyText = 'Введіть пошуковий запит, щоб побачити товари.';
    });

    productResults.appendChild(wrapper);
    populateProductDetails(productId, wrapper);
  }

  function populateProductDetails(productId, form) {
    fetch(`/orders/dropshipper/api/product/${productId}/`)
      .then((response) => response.json())
      .then((data) => {
        const sizeSelect = form.querySelector('select[name="size"]');
        const colorSelect = form.querySelector('select[name="color_variant_id"]');

        if (Array.isArray(data.sizes)) {
          data.sizes
            .filter((size) => size)
            .sort()
            .forEach((size) => {
              const option = document.createElement('option');
              option.value = size.trim();
              option.textContent = size.trim();
              sizeSelect?.appendChild(option);
            });
        }

        if (Array.isArray(data.color_variants)) {
          data.color_variants.forEach((variant) => {
            const option = document.createElement('option');
            option.value = variant.id;
            option.textContent = variant.color_name;
            option.dataset.colorName = variant.color_name;
            colorSelect?.appendChild(option);
          });

          colorSelect?.addEventListener('change', (event) => {
            const selectedOption = event.target.selectedOptions[0];
            const hiddenField = form.querySelector('input[name="color_name"]');
            if (hiddenField) {
              hiddenField.value = selectedOption?.dataset.colorName || '';
            }
          });
        }

        if (!form.querySelector('input[name="color_name"]')) {
          const hidden = document.createElement('input');
          hidden.type = 'hidden';
          hidden.name = 'color_name';
          form.appendChild(hidden);
        }
      })
      .catch((error) => {
        console.error(error);
        showToast('Не вдалося завантажити деталі товару', 'error');
      });
  }

  function renderOrderItems() {
    orderItemsContainer.innerHTML = '';
    if (!orderItems.length) {
      return;
    }

    orderItems.forEach((item, index) => {
      const row = document.createElement('div');
      row.className = 'ds-order-item';
      row.innerHTML = `
        <div style="display:flex;justify-content:space-between;gap:16px;align-items:center;">
          <div style="display:grid;gap:6px;">
            <strong>${item.title}</strong>
            <span style="color:var(--ds-text-soft);font-size:0.9rem;">
              ${item.size ? `Розмір: ${item.size}` : 'Розмір не обрано'} ·
              ${item.colorName ? `Колір: ${item.colorName}` : 'Колір: базовий'}
            </span>
            <span style="color:var(--ds-text-soft);font-size:0.9rem;">
              ${item.quantity} шт · Дроп: ${formatCurrency(item.dropPrice)} · Продаж: ${formatCurrency(item.sellingPrice)}
            </span>
          </div>
          <button type="button" class="ds-modal__close" data-remove-index="${index}" aria-label="Видалити товар">
            <i class="fas fa-trash" aria-hidden="true"></i>
          </button>
        </div>
      `;

      row.querySelector('[data-remove-index]')?.addEventListener('click', (event) => {
        const removeIndex = Number(event.currentTarget.dataset.removeIndex);
        orderItems = orderItems.filter((_, idx) => idx !== removeIndex);
        renderOrderItems();
      });

      orderItemsContainer.appendChild(row);
    });
  }

  function openModal(modal) {
    modal.hidden = false;
    modal.focus();
  }

  function closeModal(modal) {
    modal.hidden = true;
  }

  function parseCurrency(value) {
    if (!value) {
      return null;
    }
    const digits = value.replace(/[^\d.,-]/g, '').replace(',', '.');
    const parsed = parseFloat(digits);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function formatCurrency(value) {
    return `${Number(value || 0).toLocaleString('uk-UA')} грн`;
  }

  function createToast() {
    let toastEl = document.querySelector('.ds-toast');
    if (!toastEl) {
      toastEl = document.createElement('div');
      toastEl.className = 'ds-toast';
      document.body.appendChild(toastEl);
    }
    return toastEl;
  }

  function showToast(message, type = 'success') {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.remove('is-visible');
    toast.dataset.type = type;
    requestAnimationFrame(() => {
      toast.classList.add('is-visible');
    });
    setTimeout(() => {
      toast.classList.remove('is-visible');
    }, 4000);
  }

  window.dsShowToast = showToast;
})();
