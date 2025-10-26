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
  loadCart();
  loadExistingOrders();
  
  // Глобальный обработчик для загрузки корзины при открытии модального окна заказа
  setupOrderModalWatcher();
  
  // ПРИНУДИТЕЛЬНАЯ ЗАГРУЗКА КОРЗИНЫ ПРИ ОТКРЫТИИ МОДАЛЬНОГО ОКНА
  // Добавляем обработчик клика на кнопку открытия модального окна заказа
  document.addEventListener('click', function(event) {
    if (event.target.classList.contains('js-open-order-modal')) {
      // Небольшая задержка, чтобы модальное окно успело открыться
      setTimeout(() => {
        loadCart();
      }, 100);
    }
  });
  
  // Также проверяем каждые 500ms, открыто ли модальное окно заказа
  setInterval(() => {
    if (orderModal && !orderModal.hidden) {
      loadCart();
    }
  }, 500);

  function bindOpeners() {
    document.querySelectorAll('.js-open-order-modal').forEach((btn) => {
      btn.addEventListener('click', (event) => {
        event.preventDefault();
        
        // Переключаем на вкладку "Товари" вместо открытия модального окна
        const productsTab = document.querySelector('[data-tab-link="products"]');
        if (productsTab) {
          productsTab.click();
          
          // Дополнительно переключаем панель
          const productsPanel = document.querySelector('[data-tab-panel="products"]');
          if (productsPanel) {
            // Убираем активный класс с других панелей
            document.querySelectorAll('[data-tab-panel]').forEach(panel => {
              panel.classList.remove('is-active');
            });
            // Добавляем активный класс к панели товаров
            productsPanel.classList.add('is-active');
          }
        } else {
        }
      });
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
      const client_city = formData.get('client_city') || '';
      const client_np_office = formData.get('client_np_office') || '';
      const client_np_address = `${client_city}, ${client_np_office}`.trim();
      
      const payload = {
        client_name: formData.get('client_name'),
        client_phone: formData.get('client_phone'),
        client_np_address: client_np_address,
        order_source: formData.get('order_source') || '',
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
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify(payload),
      })
        .then((response) => {
          return response.json();
        })
        .then((data) => {
          if (data.success) {
            showToast(data.message || 'Замовлення створено!');
            orderForm.reset();
            orderItems = [];
            renderOrderItems();
            closeModal(orderModal);
            
            // Перезагружаем панель заказов если она открыта
            const ordersPanel = document.querySelector('[data-tab-panel="orders"]');
            if (ordersPanel && ordersPanel.classList.contains('is-active')) {
              document.dispatchEvent(new CustomEvent('ds:reload-tab', {
                detail: { target: 'orders' }
              }));
            }
            
            // Обновляем бейдж заказов после создания заказа
            loadExistingOrders();
          } else {
            throw new Error(data.message || 'Не вдалося створити замовлення');
          }
        })
        .catch((error) => {
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


    quickButtons.forEach((btn) => {
      if (btn.dataset.quickAddBound === 'true') {
        return;
      }
      btn.dataset.quickAddBound = 'true';
      btn.addEventListener('click', (event) => {
        event.preventDefault();
        
        // Получаем ID товара из родительского элемента
        const productCard = btn.closest('[data-product-id]');
        const productId = productCard ? productCard.dataset.productId : null;
        
        if (productId) {
          // Вызываем НОВУЮ функцию из dropshipper-product-modal.js
          if (typeof window.openAddProductModal === 'function') {
            window.openAddProductModal(productId);
          } else {
          }
        } else {
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
        // Используем НОВОЕ модальное окно с lightbox
        if (typeof window.openAddProductModal === 'function') {
          window.openAddProductModal(productId);
        } else {
        }
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
          chooseButton.addEventListener('click', () => {
            // Используем НОВОЕ модальное окно
            if (typeof window.openAddProductModal === 'function') {
              window.openAddProductModal(productId);
            }
          });
        }

          productResults.appendChild(item);
        });
      })
      .catch((error) => {
        if (error.name === 'AbortError') {
          return;
        }
        showToast('Не вдалося завантажити товари. Спробуйте ще раз.', 'error');
      });
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
    // Временно исключаем XXL из доступных размеров
    const uniqueSizes = Array.from(new Set((sizes || []).map((size) => (size || '').trim()).filter((size) => size && size.toUpperCase() !== 'XXL')));
    
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
          const itemToRemove = orderItems[removeIndex];
          
          if (itemToRemove) {
            // Удаляем товар с сервера
            fetch('/orders/dropshipper/api/cart/remove/', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest',
              },
              body: JSON.stringify({
                product_id: itemToRemove.productId,
                color_variant_id: itemToRemove.colorVariantId,
                size: itemToRemove.size
              }),
            })
              .then(response => response.json())
              .then(data => {
                if (data.success) {
                  // Удаляем из локальной корзины
                  orderItems = orderItems.filter((_, idx) => idx !== removeIndex);
                  renderOrderItems();
                  showToast('Товар видалено з корзини');
                } else {
                  throw new Error(data.message || 'Не вдалося видалити товар');
                }
              })
              .catch(error => {
                showToast(error.message || 'Помилка при видаленні товару', 'error');
              });
          }
        });
      }

      orderItemsContainer.appendChild(row);
    });
  }
  
  function updateOrderBadge() {
    // Эта функция больше не управляет бейджем заказов - только корзиной
    // Бейдж заказов управляется функцией loadExistingOrders
  }
  
  function loadCart() {
    fetch('/orders/dropshipper/api/cart/get/', {
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
      },
    })
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          // Обновляем локальную корзину
          orderItems = data.cart.map(item => ({
            productId: item.product_id,
            title: item.product_title,
            dropPrice: item.drop_price,
            recommendedPrice: item.selling_price,
            sellingPrice: item.selling_price,
            quantity: item.quantity,
            size: item.size,
            colorVariantId: item.color_variant_id,
            colorName: item.color_name,
          }));
          
          renderOrderItems();
        } else {
          orderItems = [];
          renderOrderItems();
        }
      })
      .catch(error => {
        orderItems = [];
        renderOrderItems();
      });
  }

  function loadExistingOrders() {
    fetch('/orders/dropshipper/orders/?partial=1', {
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
      },
    })
      .then(response => {
        return response.text();
      })
      .then(html => {
        
        // КРИТИЧЕСКИ ВАЖНО: Вставляем HTML в DOM!
        const ordersPanel = document.querySelector('[data-tab-panel="orders"]');
        if (ordersPanel) {
          ordersPanel.innerHTML = html;
        } else {
        }
        
        // НЕ обновляем бейдж здесь! Он обновляется только через updateOrdersCounter()
        // при создании нового заказа, или инициализируется из backend при загрузке страницы
        
        // Глобальный обработчик оплаты уже привязан через делегирование событий,
        // поэтому не нужно ничего делать здесь
      })
      .catch(error => {
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
        showToast(error.message || 'Помилка при оновленні статусу', 'error');
        button.textContent = originalText;
        button.disabled = false;
      });
  }

  function openModal(modal) {
    modal.hidden = false;
    modal.focus();
    
    // Загружаем корзину при открытии модального окна заказа
    if (modal === orderModal) {
      loadCart();
    }
  }

  function closeModal(modal) {
    modal.hidden = true;
  }
  
  function setupOrderModalWatcher() {
    
    // Создаем наблюдатель за изменениями атрибута hidden
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.type === 'attributes' && mutation.attributeName === 'hidden') {
          const modal = mutation.target;
          if (modal === orderModal) {
            if (!modal.hidden) {
              loadCart();
            }
          }
        }
      });
    });
    
    // Начинаем наблюдение за изменениями атрибута hidden
    observer.observe(orderModal, {
      attributes: true,
      attributeFilter: ['hidden']
    });
    
    // Также проверяем каждые 100ms, открыто ли модальное окно
    let lastModalState = orderModal.hidden;
    setInterval(() => {
      const currentModalState = orderModal.hidden;
      if (currentModalState !== lastModalState) {
        lastModalState = currentModalState;
        if (!currentModalState) {
          loadCart();
        }
      }
    }, 100);
    
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
  
  // ============================================================================
  // ОБРАБОТКА КНОПОК ОПЛАТЫ ДРОПШИПЕРА (через делегирование событий)
  // ============================================================================
  
  function bindDropshipperPaymentButtons() {
    // Используем делегирование событий - привязываем обработчик к document
    // Это работает даже когда элементы динамически добавляются/удаляются
    
    // Проверяем, не привязан ли уже глобальный обработчик
    if (window.dropshipperPaymentHandlerBound) {
      return;
    }
    
    
    document.addEventListener('click', async function(e) {
      // Проверяем, является ли кликнутый элемент кнопкой оплаты
      const button = e.target.closest('[data-dropshipper-pay]');
      if (!button) return;
      
      e.preventDefault();
      e.stopPropagation();
      
      const orderId = button.dataset.orderId;
      const paymentMethod = button.dataset.paymentMethod;
      const paymentAmount = button.dataset.paymentAmount;
      
      
      // Блокируем кнопку
      const originalHTML = button.innerHTML;
      button.disabled = true;
      button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Створення платежу...';
      
      try {
        
        // Создаем платеж Monobank
        const response = await fetch('/orders/dropshipper/monobank/create/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
            'X-Requested-With': 'XMLHttpRequest',
          },
          body: JSON.stringify({
            order_id: orderId
          })
        });
        
        
        const data = await response.json();
        
        if (data.success && data.page_url) {
          // Track StartPayment event for dropshipper order
          try{
            if(window.trackEvent){
              window.trackEvent('StartPayment', {
                value: parseFloat(paymentAmount) || 0,
                currency: 'UAH',
                payment_method: 'monobank',
                order_id: String(orderId),
                order_type: 'dropshipper',
                content_type: 'order'
              });
            }
          }catch(_){}
          
          // Перенаправляем на страницу оплаты Monobank
          window.location.href = data.page_url;
        } else {
          throw new Error(data.error || 'Не вдалося створити платіж');
        }
      } catch (error) {
        alert('Помилка при створенні платежу: ' + error.message);
        
        // Восстанавливаем кнопку
        button.disabled = false;
        button.innerHTML = originalHTML;
      }
    });
    
    window.dropshipperPaymentHandlerBound = true;
  }
  
  function getCsrfToken() {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, 10) === ('csrftoken' + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(10));
          break;
        }
      }
    }
    return cookieValue;
  }
  
  // Привязываем глобальный обработчик оплаты при загрузке (только один раз!)
  document.addEventListener('DOMContentLoaded', function() {
    bindDropshipperPaymentButtons();
  });
  
  // Делаем функцию глобальной для вызова из других мест
  window.bindDropshipperPaymentButtons = bindDropshipperPaymentButtons;
})();
