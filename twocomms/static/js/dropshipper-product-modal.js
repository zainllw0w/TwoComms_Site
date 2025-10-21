/**
 * Новое модальное окно добавления товара в дропшиппинг
 * Полностью переписанное с нуля для стабильной работы
 */

(function() {
  'use strict';
  
  // Элементы модального окна
  const modal = document.getElementById('addProductModal');
  if (!modal) {
    console.error('Модальное окно addProductModal не найдено');
    return;
  }
  
  const productLoading = document.getElementById('productLoading');
  const productContent = document.getElementById('productContent');
  const productForm = document.getElementById('addProductForm');
  
  // Элементы информации о товаре
  const productImage = document.getElementById('productImage');
  const productTitle = document.getElementById('productTitle');
  const productDescription = document.getElementById('productDescription');
  const productDropPrice = document.getElementById('productDropPrice');
  const productRecommendedPrice = document.getElementById('productRecommendedPrice');
  
  // Поля формы товара
  const productSize = document.getElementById('productSize');
  const productColor = document.getElementById('productColor');
  const productQuantity = document.getElementById('productQuantity');
  const productSellingPrice = document.getElementById('productSellingPrice');
  
  // Поля клиента
  const clientFullName = document.getElementById('clientFullName');
  const clientPhone = document.getElementById('clientPhone');
  const clientCity = document.getElementById('clientCity');
  const clientNPOffice = document.getElementById('clientNPOffice');
  const orderSource = document.getElementById('orderSource');
  const orderNotes = document.getElementById('orderNotes');
  
  // Текущий товар
  let currentProduct = null;
  
  // CSRF token
  const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
                    document.querySelector('meta[name="csrf-token"]')?.content || '';
  
  /**
   * Открыть модальное окно для товара
   */
window.openAddProductModal = function(productId) {
  console.log('🎯 Открываем модальное окно для товара:', productId);
  
  // Показываем модальное окно
  modal.removeAttribute('hidden');
    
  // Показываем загрузку
  productLoading.removeAttribute('hidden');
  productContent.setAttribute('hidden', 'hidden');
  
  // Блокируем скролл страницы
  document.body.style.overflow = 'hidden';
  
  // Загружаем данные товара
  loadProductData(productId);
};
  
  /**
   * Закрыть модальное окно
   */
  function closeModal() {
    console.log('❌ Закрываем модальное окно');
    modal.setAttribute('hidden', 'hidden');
    document.body.style.overflow = '';
    
    // Сбрасываем форму
    if (productForm) {
      productForm.reset();
    }
    
    currentProduct = null;
  }
  
  /**
   * Загрузить данные товара с сервера
   */
  async function loadProductData(productId) {
    try {
      console.log('📡 Загружаем данные товара:', productId);
      
      const response = await fetch(`/orders/dropshipper/api/product/${productId}/`, {
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
        },
      });
      
      if (!response.ok) {
        throw new Error('Не вдалося завантажити товар');
      }
      
      const data = await response.json();
      
      if (!data.success) {
        throw new Error(data.message || 'Помилка завантаження товару');
      }
      
      console.log('✅ Товар загружен:', data.product);
      
      // Сохраняем данные товара
      currentProduct = data.product;
      
      // Отображаем данные товара
      displayProductData(data.product);
      
      // Скрываем загрузку, показываем контент
      productLoading.setAttribute('hidden', 'hidden');
      productContent.removeAttribute('hidden');
      
    } catch (error) {
      console.error('❌ Ошибка загрузки товара:', error);
      showNotification('Не вдалося завантажити товар: ' + error.message, 'error');
      closeModal();
    }
  }
  
  /**
   * Отобразить данные товара в модальном окне
   */
  function displayProductData(product) {
    // Изображение
    if (productImage && product.primary_image_url) {
      productImage.src = product.primary_image_url;
      productImage.alt = product.title;
    }
    
    // Название и описание
    if (productTitle) {
      productTitle.textContent = product.title;
    }
    
    if (productDescription) {
      productDescription.textContent = product.description || 'Опис товару відсутній';
    }
    
    // Цены
    if (productDropPrice) {
      productDropPrice.textContent = `${product.drop_price} грн`;
    }
    
    if (productRecommendedPrice) {
      productRecommendedPrice.textContent = `${product.recommended_price} грн`;
      // Устанавливаем рекомендованную цену как цену продажи по умолчанию
      if (productSellingPrice) {
        productSellingPrice.value = product.recommended_price;
      }
    }
    
    // Цвета
    if (productColor && Array.isArray(product.color_variants)) {
      productColor.innerHTML = '<option value="">Базовий колір</option>';
      product.color_variants.forEach(variant => {
        const option = document.createElement('option');
        option.value = variant.id;
        option.textContent = variant.name;
        productColor.appendChild(option);
      });
    }
  }
  
  /**
   * Обработка отправки формы
   */
  if (productForm) {
    productForm.addEventListener('submit', async function(e) {
      e.preventDefault();
      
      if (!currentProduct) {
        showNotification('Товар не завантажено', 'error');
        return;
      }
      
      // Собираем данные формы
      const formData = {
        product_id: currentProduct.id,
        color_variant_id: productColor.value || null,
        size: productSize.value,
        quantity: parseInt(productQuantity.value) || 1,
        selling_price: parseFloat(productSellingPrice.value) || 0,
        
        // Данные клиента
        client_name: clientFullName.value.trim(),
        client_phone: clientPhone.value.trim(),
        client_city: clientCity.value.trim(),
        client_np_office: clientNPOffice.value.trim(),
        order_source: orderSource.value.trim(),
        notes: orderNotes.value.trim(),
      };
      
      console.log('📦 Отправляем данные:', formData);
      
      // Блокируем кнопку
      const submitBtn = productForm.querySelector('button[type="submit"]');
      const originalBtnText = submitBtn.innerHTML;
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Додаємо...';
      
      try {
        // Отправляем на сервер
        const response = await fetch('/orders/dropshipper/api/cart/add/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest',
          },
          body: JSON.stringify(formData),
        });
        
        const data = await response.json();
        
        if (!data.success) {
          throw new Error(data.message || 'Не вдалося додати товар');
        }
        
        console.log('✅ Заказ создан:', data);
        showNotification(`Замовлення №${data.order_number} створено!`, 'success');
        
        // Закрываем модальное окно
        closeModal();
        
        // Обновляем список заказов
        if (typeof loadExistingOrders === 'function') {
          loadExistingOrders();
        }
        
        // Перезагружаем панель заказов если она открыта
        const ordersPanel = document.querySelector('[data-tab-panel="orders"]');
        if (ordersPanel && ordersPanel.classList.contains('is-active')) {
          document.dispatchEvent(new CustomEvent('ds:reload-tab', {
            detail: { target: 'orders' }
          }));
        }
        
      } catch (error) {
        console.error('❌ Ошибка добавления товара:', error);
        showNotification(error.message, 'error');
        
        // Восстанавливаем кнопку
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtnText;
      }
    });
  }
  
  /**
   * Обработчики закрытия модального окна
   */
  document.querySelectorAll('[data-close-product-modal]').forEach(btn => {
    btn.addEventListener('click', closeModal);
  });
  
  // Закрытие по клику на backdrop
  const backdrop = modal.querySelector('.add-product-modal__backdrop');
  if (backdrop) {
    backdrop.addEventListener('click', closeModal);
  }
  
  // Закрытие по ESC
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && !modal.hasAttribute('hidden')) {
      closeModal();
    }
  });
  
  /**
   * Привязка к кнопкам "Додати до замовлення"
   */
  function bindAddProductButtons() {
    document.querySelectorAll('.js-product-quick-add').forEach(btn => {
      if (btn.dataset.boundNewModal) return;
      btn.dataset.boundNewModal = 'true';
      
      btn.addEventListener('click', function(e) {
        e.preventDefault();
        const productCard = btn.closest('[data-product-id]');
        const productId = productCard?.dataset.productId;
        
        if (productId) {
          window.openAddProductModal(productId);
        } else {
          console.error('ID товара не найден');
        }
      });
    });
  }
  
  // Привязываем при загрузке страницы
  bindAddProductButtons();
  
  // Привязываем при динамической загрузке контента
  document.addEventListener('ds:tabloaded', function(e) {
    if (e.detail && e.detail.target === 'products') {
      bindAddProductButtons();
    }
  });
  
  /**
   * Показать уведомление
   */
  function showNotification(message, type = 'success') {
    // Используем существующую функцию если есть
    if (typeof window.dsShowToast === 'function') {
      window.dsShowToast(message, type);
      return;
    }
    
    // Или создаем простое уведомление
    const notification = document.createElement('div');
    notification.className = `notification notification--${type}`;
    notification.textContent = message;
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      padding: 16px 24px;
      background: ${type === 'success' ? '#10b981' : '#ef4444'};
      color: white;
      border-radius: 10px;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
      z-index: 99999;
      animation: slideIn 0.3s ease;
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
      notification.style.animation = 'slideOut 0.3s ease';
      setTimeout(() => notification.remove(), 300);
    }, 4000);
  }
  
  console.log('✅ Новое модальное окно добавления товара инициализировано');
  
})();

