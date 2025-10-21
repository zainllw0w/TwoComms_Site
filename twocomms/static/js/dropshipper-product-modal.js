/**
 * Модальное окно добавления товара в дропшиппинг
 * Полностью переписано по образцу РАБОЧЕГО модального окна wholesale
 * 
 * КЛЮЧЕВЫЕ ОСОБЕННОСТИ:
 * ✅ Создается ДИНАМИЧЕСКИ через JavaScript (не статический HTML)
 * ✅ Использует INLINE стили (не CSS классы)
 * ✅ Правильное центрирование (position: fixed + transform)
 * ✅ Z-index иерархия (backdrop: 9999, popup: 10000)
 * ✅ Очистка event listeners при закрытии
 */

(function() {
  'use strict';
  
  // Текущий товар
  let currentProduct = null;
  let popupEscapeHandler = null;
  
  // CSRF token
  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }
  
  /**
   * ГЛАВНАЯ ФУНКЦИЯ: Открыть модальное окно для товара
   * По образцу openSendModal() из wholesale
   */
  window.openAddProductModal = function(productId) {
    console.log('🎯 Открываем модальное окно для товара:', productId);
    
    // Удаляем старое модальное окно если есть
    const oldPopup = document.getElementById('dsProductPopup');
    const oldBackdrop = document.getElementById('dsProductPopupBackdrop');
    if (oldPopup) oldPopup.remove();
    if (oldBackdrop) oldBackdrop.remove();
    
    // ===== ШАГ 1: СОЗДАНИЕ POPUP ЭЛЕМЕНТА =====
    const popup = document.createElement('div');
    popup.id = 'dsProductPopup';
    // Точная копия стилей из рабочего wholesale модала
    popup.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%) scale(0.8);
        background: linear-gradient(135deg, rgba(20,22,27,.98), rgba(14,16,22,.98));
        border: 1px solid rgba(255,255,255,.1);
        border-radius: 20px;
        padding: 20px;
        max-width: 900px;
        width: 90vw;
        max-height: 90vh;
        overflow-y: auto;
        z-index: 10000;
        box-shadow: 0 25px 60px rgba(0,0,0,.6);
        color: #e5e7eb;
        opacity: 0;
        transition: all 0.3s ease;
        display: flex;
        flex-direction: column;
    `;
    
    // ===== ШАГ 2: ЗАПОЛНЕНИЕ КОНТЕНТОМ =====
    popup.innerHTML = `
      <!-- Заголовок -->
      <div style="
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 24px;
        border-bottom: 1px solid rgba(255,255,255,.08);
      ">
        <h3 style="margin: 0; font-weight: 800; color: #e5e7eb; font-size: 1.35rem;">
          Додати товар до замовлення
        </h3>
        <button onclick="closeDsProductPopup()" style="
          width: 38px;
          height: 38px;
          border-radius: 14px;
          border: 1px solid rgba(255,255,255,.16);
          background: rgba(255,255,255,.04);
          color: #e5e7eb;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.3s ease;
        " onmouseover="this.style.background='rgba(255,255,255,.08)'" onmouseout="this.style.background='rgba(255,255,255,.04)'">
          <i class="fas fa-times"></i>
        </button>
      </div>
      
      <!-- Тело модального окна -->
      <div id="dsProductPopupBody" style="
        flex: 1;
        overflow-y: auto;
        padding: 24px;
      ">
        <!-- Состояние загрузки -->
        <div id="dsProductLoading" style="
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 60px 20px;
          text-align: center;
        ">
          <i class="fas fa-spinner fa-spin" style="font-size: 48px; color: #8b5cf6; margin-bottom: 20px;"></i>
          <p style="color: rgba(229,231,235,.8); margin: 0;">Завантажуємо товар...</p>
        </div>
        
        <!-- Контент товара (скрыт по умолчанию) -->
        <div id="dsProductContent" style="display: none;">
          <!-- Информация о товаре -->
          <div style="display: flex; gap: 20px; margin-bottom: 30px; flex-wrap: wrap;">
            <div style="flex-shrink: 0; width: 200px;">
              <img id="dsProductImage" src="" alt="Товар" style="
                width: 100%;
                height: 200px;
                object-fit: cover;
                border-radius: 12px;
                border: 1px solid rgba(255,255,255,.1);
              ">
            </div>
            <div style="flex: 1; min-width: 250px;">
              <h4 id="dsProductTitle" style="margin: 0 0 10px; font-weight: 700; color: #e5e7eb; font-size: 1.2rem;"></h4>
              <p id="dsProductDescription" style="margin: 0 0 15px; color: rgba(229,231,235,.7); font-size: 0.9rem;"></p>
              <div style="display: flex; gap: 20px; flex-wrap: wrap;">
                <div>
                  <span style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: rgba(255,255,255,.5);">Ціна дропа:</span>
                  <div id="dsProductDropPrice" style="font-size: 1.3rem; font-weight: 800; color: #10b981; margin-top: 4px;">0 грн</div>
                </div>
                <div>
                  <span style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: rgba(255,255,255,.5);">Рекомендована:</span>
                  <div id="dsProductRecommendedPrice" style="font-size: 1.3rem; font-weight: 800; color: #8b5cf6; margin-top: 4px;">0 грн</div>
                </div>
              </div>
            </div>
          </div>
          
          <!-- Форма -->
          <form id="dsProductForm">
            <!-- Параметры товара -->
            <div style="margin-bottom: 30px;">
              <h5 style="margin: 0 0 15px; font-weight: 700; color: #e5e7eb; font-size: 1rem; border-bottom: 1px solid rgba(255,255,255,.08); padding-bottom: 10px;">
                Параметри товару
              </h5>
              <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 18px;">
                <div>
                  <label style="display: block; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.06em; color: rgba(255,255,255,.65); margin-bottom: 8px;">
                    Розмір *
                  </label>
                  <select id="dsProductSize" required style="
                    width: 100%;
                    padding: 12px 14px;
                    border-radius: 12px;
                    border: 1px solid rgba(255,255,255,.16);
                    background: rgba(12,12,18,.65);
                    color: #e5e7eb;
                    transition: border-color 0.3s ease;
                  " onfocus="this.style.borderColor='rgba(139,92,246,.38)'" onblur="this.style.borderColor='rgba(255,255,255,.16)'">
                    <option value="">Оберіть розмір</option>
                    <option value="S">S</option>
                    <option value="M">M</option>
                    <option value="L">L</option>
                    <option value="XL">XL</option>
                    <option value="XXL">XXL</option>
                  </select>
                </div>
                
                <div>
                  <label style="display: block; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.06em; color: rgba(255,255,255,.65); margin-bottom: 8px;">
                    Колір
                  </label>
                  <select id="dsProductColor" style="
                    width: 100%;
                    padding: 12px 14px;
                    border-radius: 12px;
                    border: 1px solid rgba(255,255,255,.16);
                    background: rgba(12,12,18,.65);
                    color: #e5e7eb;
                    transition: border-color 0.3s ease;
                  " onfocus="this.style.borderColor='rgba(139,92,246,.38)'" onblur="this.style.borderColor='rgba(255,255,255,.16)'">
                    <option value="">Базовий колір</option>
                  </select>
                </div>
                
                <div>
                  <label style="display: block; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.06em; color: rgba(255,255,255,.65); margin-bottom: 8px;">
                    Кількість *
                  </label>
                  <input type="number" id="dsProductQuantity" value="1" min="1" max="99" required style="
                    width: 100%;
                    padding: 12px 14px;
                    border-radius: 12px;
                    border: 1px solid rgba(255,255,255,.16);
                    background: rgba(12,12,18,.65);
                    color: #e5e7eb;
                    transition: border-color 0.3s ease;
                  " onfocus="this.style.borderColor='rgba(139,92,246,.38)'" onblur="this.style.borderColor='rgba(255,255,255,.16)'">
                </div>
                
                <div>
                  <label style="display: block; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.06em; color: rgba(255,255,255,.65); margin-bottom: 8px;">
                    Ціна продажу (грн) *
                  </label>
                  <input type="number" id="dsProductSellingPrice" step="0.01" min="0" required style="
                    width: 100%;
                    padding: 12px 14px;
                    border-radius: 12px;
                    border: 1px solid rgba(255,255,255,.16);
                    background: rgba(12,12,18,.65);
                    color: #e5e7eb;
                    transition: border-color 0.3s ease;
                  " onfocus="this.style.borderColor='rgba(139,92,246,.38)'" onblur="this.style.borderColor='rgba(255,255,255,.16)'">
                </div>
              </div>
            </div>
            
            <!-- Данные клиента -->
            <div style="margin-bottom: 20px;">
              <h5 style="margin: 0 0 15px; font-weight: 700; color: #e5e7eb; font-size: 1rem; border-bottom: 1px solid rgba(255,255,255,.08); padding-bottom: 10px;">
                Дані клієнта
              </h5>
              <div style="display: grid; grid-template-columns: 1fr; gap: 18px;">
                <div>
                  <label style="display: block; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.06em; color: rgba(255,255,255,.65); margin-bottom: 8px;">
                    ПІБ клієнта *
                  </label>
                  <input type="text" id="dsClientFullName" placeholder="Прізвище Ім'я По батькові" required style="
                    width: 100%;
                    padding: 12px 14px;
                    border-radius: 12px;
                    border: 1px solid rgba(255,255,255,.16);
                    background: rgba(12,12,18,.65);
                    color: #e5e7eb;
                    transition: border-color 0.3s ease;
                  " onfocus="this.style.borderColor='rgba(139,92,246,.38)'" onblur="this.style.borderColor='rgba(255,255,255,.16)'">
                </div>
                
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 18px;">
                  <div>
                    <label style="display: block; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.06em; color: rgba(255,255,255,.65); margin-bottom: 8px;">
                      Телефон *
                    </label>
                    <input type="tel" id="dsClientPhone" placeholder="+380 __ ___ __ __" required style="
                      width: 100%;
                      padding: 12px 14px;
                      border-radius: 12px;
                      border: 1px solid rgba(255,255,255,.16);
                      background: rgba(12,12,18,.65);
                      color: #e5e7eb;
                      transition: border-color 0.3s ease;
                    " onfocus="this.style.borderColor='rgba(139,92,246,.38)'" onblur="this.style.borderColor='rgba(255,255,255,.16)'">
                  </div>
                  
                  <div>
                    <label style="display: block; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.06em; color: rgba(255,255,255,.65); margin-bottom: 8px;">
                      Місто *
                    </label>
                    <input type="text" id="dsClientCity" placeholder="Місто доставки" required style="
                      width: 100%;
                      padding: 12px 14px;
                      border-radius: 12px;
                      border: 1px solid rgba(255,255,255,.16);
                      background: rgba(12,12,18,.65);
                      color: #e5e7eb;
                      transition: border-color 0.3s ease;
                    " onfocus="this.style.borderColor='rgba(139,92,246,.38)'" onblur="this.style.borderColor='rgba(255,255,255,.16)'">
                  </div>
                </div>
                
                <div>
                  <label style="display: block; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.06em; color: rgba(255,255,255,.65); margin-bottom: 8px;">
                    Відділення Нової Пошти *
                  </label>
                  <input type="text" id="dsClientNPOffice" placeholder="Номер або адреса відділення" required style="
                    width: 100%;
                    padding: 12px 14px;
                    border-radius: 12px;
                    border: 1px solid rgba(255,255,255,.16);
                    background: rgba(12,12,18,.65);
                    color: #e5e7eb;
                    transition: border-color 0.3s ease;
                  " onfocus="this.style.borderColor='rgba(139,92,246,.38)'" onblur="this.style.borderColor='rgba(255,255,255,.16)'">
                </div>
                
                <div>
                  <label style="display: block; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.06em; color: rgba(255,255,255,.65); margin-bottom: 8px;">
                    Джерело замовлення
                  </label>
                  <input type="text" id="dsOrderSource" placeholder="Посилання на сторінку (необов'язково)" style="
                    width: 100%;
                    padding: 12px 14px;
                    border-radius: 12px;
                    border: 1px solid rgba(255,255,255,.16);
                    background: rgba(12,12,18,.65);
                    color: #e5e7eb;
                    transition: border-color 0.3s ease;
                  " onfocus="this.style.borderColor='rgba(139,92,246,.38)'" onblur="this.style.borderColor='rgba(255,255,255,.16)'">
                </div>
                
                <div>
                  <label style="display: block; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.06em; color: rgba(255,255,255,.65); margin-bottom: 8px;">
                    Примітки
                  </label>
                  <textarea id="dsOrderNotes" rows="3" placeholder="Коментарі, побажання клієнта" style="
                    width: 100%;
                    padding: 12px 14px;
                    border-radius: 12px;
                    border: 1px solid rgba(255,255,255,.16);
                    background: rgba(12,12,18,.65);
                    color: #e5e7eb;
                    transition: border-color 0.3s ease;
                    resize: vertical;
                    min-height: 80px;
                  " onfocus="this.style.borderColor='rgba(139,92,246,.38)'" onblur="this.style.borderColor='rgba(255,255,255,.16)'"></textarea>
                </div>
              </div>
            </div>
            
            <!-- Кнопки -->
            <div style="display: flex; justify-content: flex-end; gap: 12px; padding-top: 20px; border-top: 1px solid rgba(255,255,255,.08);">
              <button type="button" onclick="closeDsProductPopup()" style="
                background: transparent;
                border: 1px solid rgba(255,255,255,.2);
                color: #e5e7eb;
                border-radius: 10px;
                padding: 12px 24px;
                font-weight: 700;
                cursor: pointer;
                transition: all 0.3s ease;
              " onmouseover="this.style.background='rgba(255,255,255,.05)'" onmouseout="this.style.background='transparent'">
                <i class="fas fa-times"></i> Скасувати
              </button>
              <button type="submit" id="dsProductSubmitBtn" style="
                background: linear-gradient(135deg, #8b5cf6, #6366f1);
                border: none;
                color: white;
                border-radius: 10px;
                padding: 12px 24px;
                font-weight: 700;
                cursor: pointer;
                transition: all 0.3s ease;
              " onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 10px 25px rgba(139,92,246,.3)'" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='none'">
                <i class="fas fa-cart-plus"></i> Додати до замовлення
              </button>
            </div>
          </form>
        </div>
      </div>
    `;
    
    // ===== ШАГ 3: СОЗДАНИЕ BACKDROP =====
    const backdrop = document.createElement('div');
    backdrop.id = 'dsProductPopupBackdrop';
    backdrop.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      background: rgba(0,0,0,.75);
      backdrop-filter: blur(8px);
      z-index: 9999;
      cursor: pointer;
    `;
    
    // ===== ШАГ 4: ОБРАБОТЧИК КЛИКА НА BACKDROP =====
    backdrop.addEventListener('click', function() {
      closeDsProductPopup();
    });
    
    // ===== ШАГ 5: ОБРАБОТЧИК КЛАВИШИ ESCAPE =====
    popupEscapeHandler = function(event) {
      if (event.key === 'Escape') {
        closeDsProductPopup();
      }
    };
    document.addEventListener('keydown', popupEscapeHandler);
    
    // ===== ШАГ 6: ДОБАВЛЕНИЕ В DOM =====
    document.body.appendChild(backdrop);
    document.body.appendChild(popup);
    
    // КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: убираем position: relative с body
    // Это ломает position: fixed - он начинает работать как absolute!
    const originalBodyPosition = document.body.style.position;
    document.body.style.position = 'static';
    
    // Сохраняем оригинальную позицию для восстановления при закрытии
    popup.dataset.originalBodyPosition = originalBodyPosition;
    
    // Блокируем скролл страницы
    document.body.style.overflow = 'hidden';
    
    // ===== ШАГ 7: АБСОЛЮТНОЕ ЦЕНТРИРОВАНИЕ ЧЕРЕЗ VIEWPORT =====
    // Проблема: браузер всё ещё вычисляет 50% неправильно
    // Решение: устанавливаем ЯВНО координаты центра viewport в пикселях
    setTimeout(() => {
      const viewportHeight = window.innerHeight;
      const viewportWidth = window.innerWidth;
      
      // ЯВНО устанавливаем координаты центра viewport
      popup.style.setProperty('top', `${viewportHeight / 2}px`, 'important');
      popup.style.setProperty('left', `${viewportWidth / 2}px`, 'important');
      popup.style.transform = 'translate(-50%, -50%) scale(1)';
      popup.style.opacity = '1';
      
      console.log('✅ Модальное окно отцентровано:', {
        top: `${viewportHeight / 2}px`,
        left: `${viewportWidth / 2}px`
      });
    }, 10);
    
    // ===== ШАГ 8: ЗАГРУЗКА ДАННЫХ ТОВАРА =====
    loadProductData(productId, popup);
    
    console.log('✅ Модальное окно создано и отображено');
  };
  
  /**
   * Закрыть модальное окно
   * По образцу closeSendPopup() из wholesale
   */
  window.closeDsProductPopup = function() {
    console.log('❌ Закрываем модальное окно');
    
    const popup = document.getElementById('dsProductPopup');
    const backdrop = document.getElementById('dsProductPopupBackdrop');
    
    if (popup) {
      // Анимация исчезновения
      popup.style.transform = 'translate(-50%, -50%) scale(0.8)';
      popup.style.opacity = '0';
      
      // Восстанавливаем оригинальную позицию body
      const originalPosition = popup.dataset.originalBodyPosition;
      if (originalPosition !== undefined) {
        document.body.style.position = originalPosition;
      }
      
      // Удаление после анимации
      setTimeout(() => {
        // Удаляем обработчик Escape
        if (popupEscapeHandler) {
          document.removeEventListener('keydown', popupEscapeHandler);
          popupEscapeHandler = null;
        }
        popup.remove();
      }, 300);
    }
    
    if (backdrop) {
      backdrop.remove();
    }
    
    // Восстанавливаем скролл страницы
    document.body.style.overflow = '';
    
    // Сбрасываем текущий товар
    currentProduct = null;
    
    console.log('✅ Модальное окно закрыто');
  };
  
  /**
   * Загрузить данные товара с сервера
   */
  async function loadProductData(productId, popup) {
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
      
      // Скрываем загрузку
      const loading = popup.querySelector('#dsProductLoading');
      if (loading) loading.style.display = 'none';
      
      // Показываем контент
      const content = popup.querySelector('#dsProductContent');
      if (content) content.style.display = 'block';
      
      // Заполняем данные товара
      displayProductData(data.product, popup);
      
      // Навешиваем обработчик формы
      setupFormHandler(popup);
      
    } catch (error) {
      console.error('❌ Ошибка загрузки товара:', error);
      showNotification('Не вдалося завантажити товар: ' + error.message, 'error');
      closeDsProductPopup();
    }
  }
  
  /**
   * Отобразить данные товара
   */
  function displayProductData(product, popup) {
    // Изображение
    const productImage = popup.querySelector('#dsProductImage');
    if (productImage && product.primary_image_url) {
      productImage.src = product.primary_image_url;
      productImage.alt = product.title;
    }
    
    // Название
    const productTitle = popup.querySelector('#dsProductTitle');
    if (productTitle) {
      productTitle.textContent = product.title;
    }
    
    // Описание
    const productDescription = popup.querySelector('#dsProductDescription');
    if (productDescription) {
      productDescription.textContent = product.description || 'Опис товару відсутній';
    }
    
    // Цены
    const productDropPrice = popup.querySelector('#dsProductDropPrice');
    if (productDropPrice) {
      productDropPrice.textContent = `${product.drop_price} грн`;
    }
    
    const productRecommendedPrice = popup.querySelector('#dsProductRecommendedPrice');
    if (productRecommendedPrice) {
      productRecommendedPrice.textContent = `${product.recommended_price} грн`;
    }
    
    // Устанавливаем рекомендованную цену как цену продажи по умолчанию
    const productSellingPrice = popup.querySelector('#dsProductSellingPrice');
    if (productSellingPrice && product.recommended_price) {
      productSellingPrice.value = product.recommended_price;
    }
    
    // Цвета
    const productColor = popup.querySelector('#dsProductColor');
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
   * Настроить обработчик формы
   */
  function setupFormHandler(popup) {
    const form = popup.querySelector('#dsProductForm');
    if (!form) return;
    
    form.addEventListener('submit', async function(e) {
      e.preventDefault();
      
      if (!currentProduct) {
        showNotification('Товар не завантажено', 'error');
        return;
      }
      
      // Собираем данные формы
      const formData = {
        product_id: currentProduct.id,
        color_variant_id: popup.querySelector('#dsProductColor').value || null,
        size: popup.querySelector('#dsProductSize').value,
        quantity: parseInt(popup.querySelector('#dsProductQuantity').value) || 1,
        selling_price: parseFloat(popup.querySelector('#dsProductSellingPrice').value) || 0,
        
        // Данные клиента
        client_name: popup.querySelector('#dsClientFullName').value.trim(),
        client_phone: popup.querySelector('#dsClientPhone').value.trim(),
        client_city: popup.querySelector('#dsClientCity').value.trim(),
        client_np_office: popup.querySelector('#dsClientNPOffice').value.trim(),
        order_source: popup.querySelector('#dsOrderSource').value.trim(),
        notes: popup.querySelector('#dsOrderNotes').value.trim(),
      };
      
      console.log('📦 Отправляем данные:', formData);
      
      // Блокируем кнопку
      const submitBtn = popup.querySelector('#dsProductSubmitBtn');
      const originalBtnHTML = submitBtn.innerHTML;
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Додаємо...';
      
      try {
        // Отправляем на сервер
        const response = await fetch('/orders/dropshipper/api/cart/add/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken'),
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
        closeDsProductPopup();
        
        // Обновляем список заказов
        if (typeof loadExistingOrders === 'function') {
          setTimeout(() => loadExistingOrders(), 500);
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
        submitBtn.innerHTML = originalBtnHTML;
      }
    });
  }
  
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
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      padding: 16px 24px;
      background: ${type === 'success' ? 'linear-gradient(135deg, #10b981, #059669)' : 'linear-gradient(135deg, #ef4444, #dc2626)'};
      color: white;
      border-radius: 12px;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
      z-index: 99999;
      font-weight: 600;
      max-width: 400px;
      animation: slideInRight 0.3s ease;
    `;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
      notification.style.animation = 'slideOutRight 0.3s ease';
      setTimeout(() => notification.remove(), 300);
    }, 4000);
  }
  
  console.log('✅ Модуль модального окна дропшиппера инициализирован (динамическое создание)');
  
})();
