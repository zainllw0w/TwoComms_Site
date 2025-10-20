(() => {
  const orderModal = document.getElementById('ds-order-modal');
  const productModal = document.getElementById('ds-product-modal');
  const orderForm = document.getElementById('ds-order-form');
  const orderItemsContainer = document.getElementById('ds-order-items');
  const productResults = document.getElementById('ds-product-results');
  const productSearchForm = document.getElementById('ds-product-search');
  const csrfTokenMeta = document.querySelector('meta[name="csrf-token"]');
  const csrfToken = csrfTokenMeta ? csrfTokenMeta.getAttribute('content') : '';
  const placeholderImage = window.__dsPlaceholder || '/static/img/placeholder.jpg';

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
  bindProductPreviewButtons();
  loadExistingOrders();

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

      console.log('Отправляем заказ:', payload);
      
      fetch('/orders/dropshipper/api/create-order/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify(payload),
      })
        .then((response) => {
          console.log('Ответ сервера:', response.status);
          return response.json();
        })
        .then((data) => {
          console.log('Данные ответа:', data);
          if (data.success) {
            showToast(data.message || 'Замовлення створено!');
            orderForm.reset();
            orderItems = [];
            renderOrderItems();
            closeModal(orderModal);
            
            // Обновляем бейдж в боковой панели
            updateOrderBadge();
            
            // Перезагружаем панель заказов если она открыта
            const ordersPanel = document.querySelector('[data-tab-panel="orders"]');
            if (ordersPanel && ordersPanel.classList.contains('is-active')) {
              document.dispatchEvent(new CustomEvent('ds:reload-tab', {
                detail: { target: 'orders' }
              }));
            }
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

    const input = productSearchForm ? productSearchForm.querySelector('input[name="search"]') : null;

    quickButtons.forEach((btn) => {
      if (btn.dataset.quickAddBound === 'true') {
        return;
      }
      btn.dataset.quickAddBound = 'true';
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

  document.addEventListener('ds:tabloaded', (event) => {
    if (event.detail && event.detail.target === 'products') {
      bindQuickAddButtons();
      bindProductPreviewButtons();
    } else if (event.detail && event.detail.target === 'orders') {
      bindOrderStatusUpdates();
    }
  });

  function bindProductPreviewButtons() {
    const previews = document.querySelectorAll('[data-product-preview]');
    previews.forEach((btn) => {
      if (btn.dataset.previewBound === 'true') {
        return;
      }
      btn.dataset.previewBound = 'true';
      btn.addEventListener('click', () => {
        const productId = Number(btn.dataset.productPreview);
        if (!productId) {
          return;
        }
        openProductDetail(productId);
      });
    });
  }

  function openProductDetail(productId) {
    if (!productId) {
      return;
    }

    openModal(productModal);
    orderModal.setAttribute('aria-hidden', 'true');
    productResults.dataset.emptyText = 'Завантажуємо товар…';
    productResults.innerHTML = '';

    fetch(`/orders/dropshipper/api/product/${productId}/`)
      .then((response) => {
        if (!response.ok) {
          throw new Error('Не вдалося завантажити товар');
        }
        return response.json();
      })
      .then((data) => {
        if (data.error) {
          throw new Error(data.error);
        }
        renderProductDetail({
          productId: data.id,
          title: data.title,
          description: data.description || '',
          dropPrice: data.drop_price || 0,
          recommendedPrice: data.recommended_price || 0,
          recommendedMin: data.recommended_min || null,
          recommendedMax: data.recommended_max || null,
          image: data.main_image || (Array.isArray(data.gallery) && data.gallery.length ? data.gallery[0] : null),
          gallery: Array.isArray(data.gallery) ? data.gallery : [],
          colorVariants: Array.isArray(data.color_variants) ? data.color_variants : [],
          sizes: Array.isArray(data.sizes) ? data.sizes : [],
        });
      })
      .catch((error) => {
        console.error(error);
        productResults.dataset.emptyText = error.message || 'Не вдалося завантажити товар.';
        productResults.innerHTML = '';
        showToast(error.message || 'Не вдалося завантажити товар', 'error');
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
          const titleNode = card.querySelector('.product-title');
          const dropPriceNode = card.querySelector('.drop-price');
          const recommendedNode = card.querySelector('.recommended-price');
          const imageNode = card.querySelector('.product-image');

          const titleText = titleNode && titleNode.textContent ? titleNode.textContent.trim() : '';
          const title = titleText || 'Товар без назви';
          const dropPrice = parseCurrency(dropPriceNode ? dropPriceNode.textContent : null);
          const recommendedPrice = parseCurrency(recommendedNode ? recommendedNode.textContent : null);
          const image = imageNode ? imageNode.getAttribute('src') : null;

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

        const chooseButton = item.querySelector('button');
        if (chooseButton) {
          chooseButton.addEventListener('click', () => openProductDetail(productId));
        }

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

  function renderProductDetail({
    productId,
    title,
    description,
    dropPrice,
    recommendedPrice,
    recommendedMin,
    recommendedMax,
    image,
    gallery,
    colorVariants,
    sizes,
  }) {
    const productPlaceholder = placeholderImage || '/static/img/placeholder.jpg';
    productResults.dataset.emptyText = '';
    productResults.innerHTML = '';

    const fallbackImage = placeholderImage || '';
    const previewImages = Array.isArray(gallery) && gallery.length
      ? gallery.filter(Boolean)
      : (image ? [image] : [productPlaceholder]);
    if (!previewImages.length && fallbackImage) {
      previewImages.push(fallbackImage);
    }

    const wrapper = document.createElement('form');
    wrapper.className = 'ds-product-detail';
    wrapper.innerHTML = `
      <div class="ds-product-modal__layout">
        <div class="ds-product-modal__media">
          <div class="ds-product-modal__media-main">
            <img src="${previewImages[0] || fallbackImage}" alt="${escapeHtml(title)}" loading="lazy" data-product-main>
          </div>
          <div class="ds-product-modal__thumbs" data-product-thumbs></div>
        </div>
        <div class="ds-product-modal__info">
          <div>
            <h3 class="ds-product-modal__title">${escapeHtml(title)}</h3>
            ${description ? `<p class="ds-product-modal__description">${escapeHtml(description).replace(/\n+/g, '<br>')}</p>` : ''}
          </div>
          <div class="ds-product-modal__meta">
            <span>Ціна дропа: <strong>${formatCurrency(dropPrice || 0)}</strong></span>
            <span>
              Рекомендовано: <strong>${recommendedPrice ? formatCurrency(recommendedPrice) : '—'}</strong>
              ${recommendedMin && recommendedMax ? `<small> (${formatCurrency(recommendedMin)} – ${formatCurrency(recommendedMax)})</small>` : ''}
            </span>
          </div>
          <div class="ds-form__grid">
            <label class="ds-input">
              <span class="ds-input__label">Кількість</span>
              <input type="number" name="quantity" value="1" min="1" required>
            </label>
            <label class="ds-input">
              <span class="ds-input__label">Розмір</span>
              <select name="size" data-size-select></select>
            </label>
            <label class="ds-input">
              <span class="ds-input__label">Колір</span>
              <select name="color_variant_id" data-color-select></select>
            </label>
            <label class="ds-input">
              <span class="ds-input__label">Ціна продажу, грн</span>
              <input type="number" name="selling_price" value="${Number(recommendedPrice || dropPrice || 0)}" min="${Number(dropPrice || 0)}" step="1" required>
            </label>
          </div>
          <input type="hidden" name="color_name">
          <div class="ds-product-detail__actions">
            <button type="button" class="ds-btn ds-btn--ghost" data-product-close>
              <i class="fas fa-times" aria-hidden="true"></i>
              <span>Закрити</span>
            </button>
            <button type="submit" class="ds-btn ds-btn--primary">
              <i class="fas fa-plus" aria-hidden="true"></i>
              <span>Додати до замовлення</span>
            </button>
          </div>
        </div>
      </div>
    `;

    const formState = {
      productId,
      title,
      dropPrice: Number(dropPrice || 0),
      recommendedPrice: Number(recommendedPrice || 0),
      baseImages: previewImages.slice(),
    };

    setupProductDetailForm(wrapper, colorVariants, sizes, formState);

    wrapper.addEventListener('submit', (event) => {
      event.preventDefault();
      const formData = new FormData(wrapper);
      const quantity = Number(formData.get('quantity')) || 1;
      const sellingPrice = Number(formData.get('selling_price')) || formState.recommendedPrice || formState.dropPrice;
      const size = formData.get('size') || '';
      const colorVariantId = formData.get('color_variant_id') || '';
      const colorName = formData.get('color_name') || '';

      orderItems.push({
        productId,
        title,
        dropPrice: formState.dropPrice,
        recommendedPrice: formState.recommendedPrice,
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

    const closeBtn = wrapper.querySelector('[data-product-close]');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        closeModal(productModal);
        orderModal.removeAttribute('aria-hidden');
      });
    }

    productResults.appendChild(wrapper);
  }

  
  function setupProductDetailForm(wrapper, colorVariants, sizes, state) {
    const mainImage = wrapper.querySelector('[data-product-main]');
    const thumbsContainer = wrapper.querySelector('[data-product-thumbs]');
    const sizeSelect = wrapper.querySelector('[data-size-select]');
    const colorSelect = wrapper.querySelector('[data-color-select]');
    const hiddenColor = wrapper.querySelector('input[name="color_name"]');

    const baseImages = state.baseImages.length ? state.baseImages : [placeholderImage];

    // Стандартные размеры для одежды
    const standardSizes = ['S', 'M', 'L', 'XL'];
    const uniqueSizes = Array.from(new Set((sizes || []).map((size) => (size || '').trim()).filter(Boolean)));
    
    if (sizeSelect) {
      sizeSelect.innerHTML = '';
      
      // Если нет размеров от товара, используем стандартные
      const availableSizes = uniqueSizes.length > 0 ? uniqueSizes : standardSizes;
      
      if (availableSizes.length === 0) {
        const singleOption = document.createElement('option');
        singleOption.value = '';
        singleOption.textContent = 'Єдиний розмір';
        sizeSelect.appendChild(singleOption);
      } else {
        const defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.textContent = '— Обрати розмір —';
        sizeSelect.appendChild(defaultOption);
        
        availableSizes.forEach((size) => {
          const option = document.createElement('option');
          option.value = size;
          option.textContent = size;
          sizeSelect.appendChild(option);
        });
      }
    }

    const normalizedVariants = Array.isArray(colorVariants)
      ? colorVariants.filter((variant) => variant && (variant.id || variant.id === 0))
      : [];

    if (colorSelect) {
      colorSelect.innerHTML = '';
      const baseOption = document.createElement('option');
      baseOption.value = '';
      baseOption.textContent = normalizedVariants.length ? 'Базовий колір' : 'Єдиний колір';
      colorSelect.appendChild(baseOption);

      normalizedVariants.forEach((variant) => {
        const option = document.createElement('option');
        option.value = variant.id;
        option.textContent = variant.color_name || 'Колір без назви';
        option.dataset.colorName = variant.color_name || '';
        colorSelect.appendChild(option);
      });

      colorSelect.addEventListener('change', (event) => {
        const selectEl = event.target;
        const selectedOption = selectEl.selectedOptions ? selectEl.selectedOptions[0] : null;
        const variant = normalizedVariants.find((item) => String(item.id) === String(selectEl.value));
        if (hiddenColor) {
          hiddenColor.value = selectedOption ? (selectedOption.dataset.colorName || selectedOption.textContent || '') : '';
        }
        const variantImages = variant && Array.isArray(variant.images) && variant.images.length ? variant.images : baseImages;
        renderThumbs(variantImages);
      });

      if (normalizedVariants.length) {
        colorSelect.value = String(normalizedVariants[0].id);
        colorSelect.dispatchEvent(new Event('change'));
      } else {
        if (hiddenColor) {
          hiddenColor.value = 'Базовий колір';
        }
        renderThumbs(baseImages);
      }
    } else {
      if (hiddenColor) {
        hiddenColor.value = 'Базовий колір';
      }
      renderThumbs(baseImages);
    }

    function renderThumbs(images) {
      if (!thumbsContainer || !mainImage) {
        return;
      }

      const unique = [];
      (images || []).forEach((url) => {
        if (url && !unique.includes(url)) {
          unique.push(url);
        }
      });

      if (!unique.length) {
        unique.push(placeholderImage);
      }

      thumbsContainer.innerHTML = '';
      unique.forEach((url, index) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'ds-product-modal__thumb' + (index === 0 ? ' is-active' : '');
        button.innerHTML = `<img src="${url}" alt="">`;
        button.addEventListener('click', () => {
          setMainImage(url);
          thumbsContainer.querySelectorAll('.ds-product-modal__thumb').forEach((thumb) => thumb.classList.remove('is-active'));
          button.classList.add('is-active');
        });
        thumbsContainer.appendChild(button);
      });

      setMainImage(unique[0]);
    }

    function setMainImage(url) {
      if (mainImage) {
        mainImage.src = url || placeholderImage;
      }
    }
  }

  function escapeHtml(value) {
    if (typeof value !== 'string') {
      return '';
    }
    return value.replace(/[&<>"']/g, (char) => {
      const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
      };
      return map[char] || char;
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
        <div class="ds-order-item__content">
          <div class="ds-order-item__info">
            <h4 class="ds-order-item__title">${item.title}</h4>
            <div class="ds-order-item__details">
              <span class="ds-order-item__detail">
                <i class="fas fa-ruler" aria-hidden="true"></i>
                ${item.size ? `Розмір: ${item.size}` : 'Розмір не обрано'}
              </span>
              <span class="ds-order-item__detail">
                <i class="fas fa-palette" aria-hidden="true"></i>
                ${item.colorName ? `Колір: ${item.colorName}` : 'Колір: базовий'}
              </span>
            </div>
            <div class="ds-order-item__pricing">
              <span class="ds-order-item__quantity">${item.quantity} шт</span>
              <span class="ds-order-item__price">
                Дроп: <strong>${formatCurrency(item.dropPrice)}</strong>
              </span>
              <span class="ds-order-item__price">
                Продаж: <strong>${formatCurrency(item.sellingPrice)}</strong>
              </span>
            </div>
          </div>
          <button type="button" class="ds-order-item__remove" data-remove-index="${index}" aria-label="Видалити товар">
            <i class="fas fa-trash" aria-hidden="true"></i>
          </button>
        </div>
      `;

      const removeBtn = row.querySelector('[data-remove-index]');
      if (removeBtn) {
        removeBtn.addEventListener('click', (event) => {
          const targetBtn = event.currentTarget;
          const removeIndex = Number(targetBtn.dataset.removeIndex);
          orderItems = orderItems.filter((_, idx) => idx !== removeIndex);
          renderOrderItems();
          updateOrderBadge();
        });
      }

      orderItemsContainer.appendChild(row);
    });
    
    updateOrderBadge();
  }
  
  function updateOrderBadge() {
    console.log('Обновляем бейдж заказов, текущие товары в корзине:', orderItems.length);
    const ordersBadge = document.querySelector('[data-orders-badge]');
    if (ordersBadge) {
      if (orderItems.length > 0) {
        ordersBadge.textContent = orderItems.length;
        ordersBadge.removeAttribute('hidden');
        ordersBadge.closest('.ds-sidebar__link').classList.add('has-orders');
        console.log('Бейдж обновлен для корзины:', orderItems.length);
      } else {
        ordersBadge.setAttribute('hidden', 'hidden');
        ordersBadge.closest('.ds-sidebar__link').classList.remove('has-orders');
        console.log('Бейдж скрыт, корзина пуста');
      }
    } else {
      console.log('Бейдж не найден в DOM');
    }
  }
  
  function loadExistingOrders() {
    console.log('Загружаем существующие заказы...');
    // Загружаем количество активных заказов для отображения в бейдже
    fetch('/orders/dropshipper/orders/?partial=1', {
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
      },
    })
      .then(response => {
        console.log('Ответ от сервера заказов:', response.status);
        return response.text();
      })
      .then(html => {
        console.log('HTML заказов получен, длина:', html.length);
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        const orderEntries = doc.querySelectorAll('.ds-order-entry');
        console.log('Найдено заказов в HTML:', orderEntries.length);
        
        const ordersBadge = document.querySelector('[data-orders-badge]');
        if (ordersBadge) {
          if (orderEntries.length > 0) {
            ordersBadge.textContent = orderEntries.length;
            ordersBadge.removeAttribute('hidden');
            ordersBadge.closest('.ds-sidebar__link').classList.add('has-orders');
            console.log('Бейдж обновлен для существующих заказов:', orderEntries.length);
          } else {
            ordersBadge.setAttribute('hidden', 'hidden');
            ordersBadge.closest('.ds-sidebar__link').classList.remove('has-orders');
            console.log('Бейдж скрыт, заказов нет');
          }
        } else {
          console.log('Бейдж не найден в DOM при загрузке заказов');
        }
      })
      .catch(error => {
        console.log('Не удалось загрузить заказы:', error);
      });
  }
  
  function bindOrderStatusUpdates() {
    const statusButtons = document.querySelectorAll('[data-order-status-update]');
    statusButtons.forEach(button => {
      if (button.dataset.statusBound === 'true') {
        return;
      }
      button.dataset.statusBound = 'true';
      
      button.addEventListener('click', (event) => {
        event.preventDefault();
        const orderId = button.dataset.orderId;
        const newStatus = button.dataset.newStatus;
        
        if (!orderId || !newStatus) {
          return;
        }
        
        updateOrderStatus(orderId, newStatus, button);
      });
    });
  }
  
  function updateOrderStatus(orderId, newStatus, button) {
    const originalText = button.textContent;
    button.textContent = 'Оновлення...';
    button.disabled = true;
    
    fetch(`/orders/dropshipper/api/update-order-status/${orderId}/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken,
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: JSON.stringify({ status: newStatus }),
    })
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          showToast(data.message || 'Статус замовлення оновлено!');
          // Перезагружаем панель заказов
          document.dispatchEvent(new CustomEvent('ds:reload-tab', {
            detail: { target: 'orders' }
          }));
        } else {
          throw new Error(data.message || 'Не вдалося оновити статус');
        }
      })
      .catch(error => {
        console.error(error);
        showToast(error.message || 'Помилка при оновленні статусу', 'error');
        button.textContent = originalText;
        button.disabled = false;
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
