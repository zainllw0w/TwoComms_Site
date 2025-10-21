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
            <div style="flex-shrink: 0; width: 200px; position: relative;">
              <img id="dsProductImage" src="" alt="Товар" style="
                width: 100%;
                height: 200px;
                object-fit: cover;
                border-radius: 12px;
                border: 1px solid rgba(255,255,255,.1);
                cursor: pointer;
                transition: all 0.3s ease;
              " onclick="openImageLightbox(this.src, this.alt)" onmouseover="this.style.transform='scale(1.05)'; this.style.boxShadow='0 8px 20px rgba(139,92,246,.4)'" onmouseout="this.style.transform='scale(1)'; this.style.boxShadow='none'">
              <div style="
                position: absolute;
                top: 8px;
                right: 8px;
                background: rgba(0,0,0,.7);
                color: white;
                padding: 6px 10px;
                border-radius: 8px;
                font-size: 0.75rem;
                font-weight: 700;
                pointer-events: none;
                display: flex;
                align-items: center;
                gap: 5px;
              ">
                <i class="fas fa-search-plus"></i>
                <span>Збільшити</span>
              </div>
            </div>
            <div style="flex: 1; min-width: 250px;">
              <h4 id="dsProductTitle" style="margin: 0 0 10px; font-weight: 700; color: #e5e7eb; font-size: 1.2rem;"></h4>
              
              <!-- Сворачиваемое описание -->
              <div style="margin-bottom: 15px;">
                <button type="button" id="dsProductDescriptionToggle" style="
                  background: rgba(139,92,246,.15);
                  border: 1px solid rgba(139,92,246,.3);
                  color: #a78bfa;
                  padding: 6px 12px;
                  border-radius: 8px;
                  font-size: 0.85rem;
                  cursor: pointer;
                  display: flex;
                  align-items: center;
                  gap: 6px;
                  transition: all 0.2s;
                " onmouseover="this.style.background='rgba(139,92,246,.25)'" onmouseout="this.style.background='rgba(139,92,246,.15)'">
                  <i class="fas fa-chevron-down" id="dsDescToggleIcon"></i>
                  <span>Опис товару</span>
                </button>
                <div id="dsProductDescription" style="
                  max-height: 0;
                  overflow: hidden;
                  transition: max-height 0.3s ease;
                  margin-top: 10px;
                  color: rgba(229,231,235,.7);
                  font-size: 0.9rem;
                  line-height: 1.6;
                "></div>
              </div>
              
              <!-- Цены в стиле сайта -->
              <div style="display: flex; gap: 12px; flex-wrap: wrap; align-items: stretch;">
                <div style="
                  flex: 1;
                  min-width: 140px;
                  background: linear-gradient(135deg, rgba(16,185,129,.15), rgba(5,150,105,.15));
                  border: 1px solid rgba(16,185,129,.3);
                  border-radius: 12px;
                  padding: 12px 16px;
                ">
                  <span style="font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.08em; color: rgba(16,185,129,.8); font-weight: 600;">Ціна дропа</span>
                  <div id="dsProductDropPrice" style="font-size: 1.4rem; font-weight: 800; color: #10b981; margin-top: 6px;">0 грн</div>
                  <span style="font-size: 0.7rem; color: rgba(16,185,129,.6);">Закупівельна вартість</span>
                </div>
                <div style="
                  flex: 1;
                  min-width: 140px;
                  background: linear-gradient(135deg, rgba(139,92,246,.15), rgba(124,58,237,.15));
                  border: 1px solid rgba(139,92,246,.3);
                  border-radius: 12px;
                  padding: 12px 16px;
                ">
                  <span style="font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.08em; color: rgba(139,92,246,.8); font-weight: 600;">Рекомендована</span>
                  <div id="dsProductRecommendedPrice" style="font-size: 1.4rem; font-weight: 800; color: #8b5cf6; margin-top: 6px;">0 грн</div>
                  <div id="dsProductPriceRange" style="font-size: 0.7rem; color: rgba(139,92,246,.6); margin-top: 2px;"></div>
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
            
            <!-- Спосіб оплати -->
            <div style="margin-bottom: 20px;">
              <h5 style="margin: 0 0 15px; font-weight: 700; color: #e5e7eb; font-size: 1rem; border-bottom: 1px solid rgba(255,255,255,.08); padding-bottom: 10px;">
                💳 Спосіб оплати
              </h5>
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                <label style="
                  position: relative;
                  display: flex;
                  flex-direction: column;
                  padding: 20px;
                  border-radius: 12px;
                  border: 2px solid rgba(255,255,255,.16);
                  background: rgba(12,12,18,.65);
                  cursor: pointer;
                  transition: all 0.3s ease;
                " onmouseover="this.style.borderColor='rgba(139,92,246,.38)'; this.style.background='rgba(139,92,246,.08)'" onmouseout="if(!this.querySelector('input').checked) { this.style.borderColor='rgba(255,255,255,.16)'; this.style.background='rgba(12,12,18,.65)' }">
                  <input type="radio" name="paymentMethod" value="prepaid" id="dsPaymentPrepaid" required style="
                    position: absolute;
                    opacity: 0;
                  " onchange="handlePaymentMethodChange(this)">
                  <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 10px;">
                    <div id="dsPaymentPrepaidIcon" style="
                      width: 24px;
                      height: 24px;
                      border-radius: 50%;
                      border: 2px solid rgba(255,255,255,.3);
                      display: flex;
                      align-items: center;
                      justify-content: center;
                      transition: all 0.3s ease;
                    ">
                      <div style="width: 12px; height: 12px; border-radius: 50%; background: transparent; transition: all 0.3s ease;"></div>
                    </div>
                    <strong style="font-size: 1.05rem; color: #e5e7eb;">Оплачено передоплатою</strong>
                  </div>
                  <div style="font-size: 0.85rem; color: rgba(229,231,235,.7); margin-bottom: 12px;">
                    Клієнт вже оплатив товар. Ви сплачуєте повну вартість дропа.
                  </div>
                  <div id="dsPaymentPrepaidAmount" style="
                    background: linear-gradient(135deg, rgba(139,92,246,.15), rgba(99,102,241,.15));
                    border: 1px solid rgba(139,92,246,.3);
                    border-radius: 8px;
                    padding: 12px;
                    display: none;
                  ">
                    <div style="font-size: 0.75rem; text-transform: uppercase; color: rgba(229,231,235,.6); margin-bottom: 4px;">До сплати:</div>
                    <div style="font-size: 1.3rem; font-weight: 800; color: #a78bfa;"><span id="dsPaymentPrepaidValue">0</span> грн</div>
                  </div>
                </label>
                
                <label style="
                  position: relative;
                  display: flex;
                  flex-direction: column;
                  padding: 20px;
                  border-radius: 12px;
                  border: 2px solid rgba(255,255,255,.16);
                  background: rgba(12,12,18,.65);
                  cursor: pointer;
                  transition: all 0.3s ease;
                " onmouseover="this.style.borderColor='rgba(139,92,246,.38)'; this.style.background='rgba(139,92,246,.08)'" onmouseout="if(!this.querySelector('input').checked) { this.style.borderColor='rgba(255,255,255,.16)'; this.style.background='rgba(12,12,18,.65)' }">
                  <input type="radio" name="paymentMethod" value="cod" id="dsPaymentCOD" required style="
                    position: absolute;
                    opacity: 0;
                  " onchange="handlePaymentMethodChange(this)" checked>
                  <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 10px;">
                    <div id="dsPaymentCODIcon" style="
                      width: 24px;
                      height: 24px;
                      border-radius: 50%;
                      border: 2px solid #8b5cf6;
                      background: #8b5cf6;
                      display: flex;
                      align-items: center;
                      justify-content: center;
                      transition: all 0.3s ease;
                    ">
                      <div style="width: 12px; height: 12px; border-radius: 50%; background: white; transition: all 0.3s ease;"></div>
                    </div>
                    <strong style="font-size: 1.05rem; color: #e5e7eb;">Накладний платіж</strong>
                  </div>
                  <div style="font-size: 0.85rem; color: rgba(229,231,235,.7); margin-bottom: 12px;">
                    Клієнт оплатить при отриманні на Новій Пошті. 200 грн вираховується з суми.
                  </div>
                  <div id="dsPaymentCODAmount" style="
                    background: linear-gradient(135deg, rgba(139,92,246,.15), rgba(99,102,241,.15));
                    border: 1px solid rgba(139,92,246,.3);
                    border-radius: 8px;
                    padding: 12px;
                  ">
                    <div style="font-size: 0.75rem; text-transform: uppercase; color: rgba(229,231,235,.6); margin-bottom: 4px;">З накладки віднімається:</div>
                    <div style="font-size: 1.3rem; font-weight: 800; color: #a78bfa;">200 грн</div>
                    <div style="font-size: 0.75rem; color: rgba(229,231,235,.5); margin-top: 6px;">
                      📦 Вираховується при отриманні клієнтом
                    </div>
                  </div>
                </label>
              </div>
              
              <div id="dsPaymentInfo" style="
                margin-top: 16px;
                padding: 16px;
                background: linear-gradient(135deg, rgba(59,130,246,.1), rgba(37,99,235,.1));
                border: 1px solid rgba(59,130,246,.2);
                border-radius: 12px;
                font-size: 0.85rem;
                color: rgba(229,231,235,.8);
                line-height: 1.6;
              ">
                <div style="font-weight: 700; margin-bottom: 8px; color: #60a5fa;">
                  <i class="fas fa-info-circle"></i> Важлива інформація:
                </div>
                <div id="dsPaymentInfoText">
                  При накладному платежі клієнт оплачує товар на Новій Пошті. З цієї суми автоматично віднімається 200 грн, які йдуть на покриття вартості дропа. Ви отримуєте суму продажу мінус 200 грн.
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
    // ВАЖНО: backdrop должен быть position: absolute с полным покрытием документа
    // или position: fixed с height: 100% от document.documentElement
    const scrollY = window.scrollY || window.pageYOffset;
    const documentHeight = Math.max(
      document.documentElement.scrollHeight,
      document.body.scrollHeight
    );
    
    backdrop.style.cssText = `
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: ${documentHeight}px;
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
    
    // ===== ШАГ 7: АБСОЛЮТНОЕ ЦЕНТРИРОВАНИЕ ЧЕРЕЗ VIEWPORT + SCROLL =====
    // КРИТИЧЕСКИ ВАЖНО: position: fixed работает относительно viewport,
    // НО если страница прокручена - нужно учитывать scrollY!
    setTimeout(() => {
      const viewportHeight = window.innerHeight;
      const viewportWidth = window.innerWidth;
      const scrollY = window.scrollY || window.pageYOffset;
      
      // Вычисляем абсолютную позицию центра ВИДИМОЙ области viewport
      const centerY = scrollY + (viewportHeight / 2);
      const centerX = viewportWidth / 2;
      
      // ЯВНО устанавливаем координаты
      popup.style.setProperty('top', `${centerY}px`, 'important');
      popup.style.setProperty('left', `${centerX}px`, 'important');
      popup.style.transform = 'translate(-50%, -50%) scale(1)';
      popup.style.opacity = '1';
      
      console.log('✅ Модальное окно отцентровано:', {
        scrollY,
        top: `${centerY}px`,
        left: `${centerX}px`
      });
    }, 10);
    
    // ===== ШАГ 8: ЗАГРУЗКА ДАННЫХ ТОВАРА =====
    loadProductData(productId, popup);
    
    console.log('✅ Модальное окно создано и отображено');
  };
  
  /**
   * Обработка изменения способа оплаты
   */
  window.handlePaymentMethodChange = function(radio) {
    const popup = document.getElementById('dsProductPopup');
    if (!popup || !currentProduct) return;
    
    const isPrepaid = radio.value === 'prepaid';
    const dropPrice = currentProduct.drop_price || 0;
    
    // Обновляем иконки
    const prepaidIcon = popup.querySelector('#dsPaymentPrepaidIcon');
    const codIcon = popup.querySelector('#dsPaymentCODIcon');
    const prepaidInner = prepaidIcon ? prepaidIcon.querySelector('div') : null;
    const codInner = codIcon ? codIcon.querySelector('div') : null;
    
    if (isPrepaid) {
      // Prepaid выбран
      if (prepaidIcon) {
        prepaidIcon.style.borderColor = '#8b5cf6';
        prepaidIcon.style.background = '#8b5cf6';
      }
      if (prepaidInner) {
        prepaidInner.style.background = 'white';
      }
      if (codIcon) {
        codIcon.style.borderColor = 'rgba(255,255,255,.3)';
        codIcon.style.background = 'transparent';
      }
      if (codInner) {
        codInner.style.background = 'transparent';
      }
      
      // Показываем сумму для prepaid
      const prepaidAmount = popup.querySelector('#dsPaymentPrepaidAmount');
      const codAmount = popup.querySelector('#dsPaymentCODAmount');
      const prepaidValue = popup.querySelector('#dsPaymentPrepaidValue');
      
      if (prepaidAmount) prepaidAmount.style.display = 'block';
      if (codAmount) codAmount.style.display = 'none';
      if (prepaidValue) prepaidValue.textContent = dropPrice.toFixed(0);
      
      // Обновляем инфо-текст
      const infoText = popup.querySelector('#dsPaymentInfoText');
      if (infoText) {
        infoText.innerHTML = `Ви сплачуєте <strong>${dropPrice} грн</strong> - повну вартість дропа. Клієнт вже оплатив товар, тому ризиків немає.`;
      }
      
      // Обновляем стили родительских label
      const prepaidLabel = popup.querySelector('#dsPaymentPrepaid').closest('label');
      const codLabel = popup.querySelector('#dsPaymentCOD').closest('label');
      if (prepaidLabel) {
        prepaidLabel.style.borderColor = 'rgba(139,92,246,.5)';
        prepaidLabel.style.background = 'rgba(139,92,246,.12)';
      }
      if (codLabel) {
        codLabel.style.borderColor = 'rgba(255,255,255,.16)';
        codLabel.style.background = 'rgba(12,12,18,.65)';
      }
    } else {
      // COD выбран
      if (prepaidIcon) {
        prepaidIcon.style.borderColor = 'rgba(255,255,255,.3)';
        prepaidIcon.style.background = 'transparent';
      }
      if (prepaidInner) {
        prepaidInner.style.background = 'transparent';
      }
      if (codIcon) {
        codIcon.style.borderColor = '#8b5cf6';
        codIcon.style.background = '#8b5cf6';
      }
      if (codInner) {
        codInner.style.background = 'white';
      }
      
      // Показываем сумму для COD
      const prepaidAmount = popup.querySelector('#dsPaymentPrepaidAmount');
      const codAmount = popup.querySelector('#dsPaymentCODAmount');
      
      if (prepaidAmount) prepaidAmount.style.display = 'none';
      if (codAmount) codAmount.style.display = 'block';
      
      // Обновляем инфо-текст
      const infoText = popup.querySelector('#dsPaymentInfoText');
      if (infoText) {
        infoText.innerHTML = 'При накладному платежі клієнт оплачує товар на Новій Пошті. З цієї суми автоматично віднімається <strong>200 грн</strong>, які йдуть на покриття вартості дропа. Ви отримуєте суму продажу мінус 200 грн.';
      }
      
      // Обновляем стили родительских label
      const prepaidLabel = popup.querySelector('#dsPaymentPrepaid').closest('label');
      const codLabel = popup.querySelector('#dsPaymentCOD').closest('label');
      if (prepaidLabel) {
        prepaidLabel.style.borderColor = 'rgba(255,255,255,.16)';
        prepaidLabel.style.background = 'rgba(12,12,18,.65)';
      }
      if (codLabel) {
        codLabel.style.borderColor = 'rgba(139,92,246,.5)';
        codLabel.style.background = 'rgba(139,92,246,.12)';
      }
    }
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
    
    // Описание (сворачиваемое)
    const productDescription = popup.querySelector('#dsProductDescription');
    const descToggle = popup.querySelector('#dsProductDescriptionToggle');
    const descToggleIcon = popup.querySelector('#dsDescToggleIcon');
    
    if (productDescription && product.description) {
      productDescription.textContent = product.description;
      
      // Обработчик сворачивания/разворачивания
      if (descToggle) {
        descToggle.addEventListener('click', () => {
          const isExpanded = productDescription.style.maxHeight !== '0px' && productDescription.style.maxHeight !== '';
          
          if (isExpanded) {
            productDescription.style.maxHeight = '0';
            if (descToggleIcon) descToggleIcon.className = 'fas fa-chevron-down';
          } else {
            productDescription.style.maxHeight = productDescription.scrollHeight + 'px';
            if (descToggleIcon) descToggleIcon.className = 'fas fa-chevron-up';
          }
        });
      }
    }
    
    // Цены
    const productDropPrice = popup.querySelector('#dsProductDropPrice');
    if (productDropPrice) {
      productDropPrice.textContent = `${product.drop_price} грн`;
    }
    
    const productRecommendedPrice = popup.querySelector('#dsProductRecommendedPrice');
    if (productRecommendedPrice) {
      productRecommendedPrice.textContent = `${product.recommended_price || product.drop_price} грн`;
    }
    
    // Диапазон цены (как на сайте)
    const productPriceRange = popup.querySelector('#dsProductPriceRange');
    if (productPriceRange && product.price_range) {
      productPriceRange.textContent = `Діапазон ${product.price_range.min}–${product.price_range.max} грн`;
    } else if (productPriceRange && product.recommended_price) {
      // Fallback если нет price_range
      const minPrice = Math.round(product.recommended_price * 0.9);
      const maxPrice = Math.round(product.recommended_price * 1.1);
      productPriceRange.textContent = `Діапазон ${minPrice}–${maxPrice} грн`;
    }
    
    // Устанавливаем рекомендованную цену как цену продажи по умолчанию
    const productSellingPrice = popup.querySelector('#dsProductSellingPrice');
    if (productSellingPrice) {
      const defaultPrice = product.recommended_price || product.drop_price;
      productSellingPrice.value = defaultPrice;
      productSellingPrice.setAttribute('min', product.drop_price);
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
      const paymentMethod = popup.querySelector('input[name="paymentMethod"]:checked');
      
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
        
        // Способ оплаты
        payment_method: paymentMethod ? paymentMethod.value : 'cod',
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
        
        // АВТООБНОВЛЕНИЕ СЧЕТЧИКА ЗАКАЗОВ
        updateOrdersCounter();
        
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
   * Обновить счетчик заказов в сайдбаре
   */
  function updateOrdersCounter() {
    // Находим badge по data-атрибуту
    const badge = document.querySelector('[data-orders-badge]');
    
    if (!badge) {
      console.warn('⚠️ Badge заказов не найден в DOM');
      return;
    }
    
    // Показываем badge если он скрыт
    if (badge.hasAttribute('hidden')) {
      badge.removeAttribute('hidden');
    }
    
    // Увеличиваем счетчик
    const currentCount = parseInt(badge.textContent) || 0;
    const newCount = currentCount + 1;
    badge.textContent = newCount;
    
    // Анимация увеличения
    badge.style.transition = 'transform 0.2s ease';
    badge.style.transform = 'scale(1.4)';
    
    setTimeout(() => {
      badge.style.transform = 'scale(1)';
    }, 200);
    
    console.log('✅ Счетчик заказов обновлен:', newCount);
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
  
  /**
   * LIGHTBOX: Открыть увеличенное изображение
   * Красивый, плавный, без перезагрузки страницы
   */
  window.openImageLightbox = function(imageSrc, imageAlt) {
    console.log('🖼️ Открываем lightbox для изображения');
    
    // Удаляем старый lightbox если есть
    const oldLightbox = document.getElementById('dsImageLightbox');
    if (oldLightbox) oldLightbox.remove();
    
    // Создаем backdrop
    const lightbox = document.createElement('div');
    lightbox.id = 'dsImageLightbox';
    
    const documentHeight = Math.max(
      document.documentElement.scrollHeight,
      document.body.scrollHeight
    );
    
    lightbox.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      background: rgba(0,0,0,.95);
      backdrop-filter: blur(20px);
      z-index: 999999;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: zoom-out;
      opacity: 0;
      transition: opacity 0.4s ease;
      padding: 40px;
    `;
    
    // Создаем контейнер для изображения
    const imageContainer = document.createElement('div');
    imageContainer.style.cssText = `
      position: relative;
      max-width: 90vw;
      max-height: 90vh;
      transform: scale(0.7);
      transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
    `;
    
    // Создаем изображение
    const img = document.createElement('img');
    img.src = imageSrc;
    img.alt = imageAlt || 'Товар';
    img.style.cssText = `
      max-width: 100%;
      max-height: 90vh;
      width: auto;
      height: auto;
      display: block;
      border-radius: 16px;
      box-shadow: 0 30px 90px rgba(0,0,0,.8);
      cursor: default;
    `;
    
    // Кнопка закрытия
    const closeBtn = document.createElement('button');
    closeBtn.innerHTML = '<i class="fas fa-times"></i>';
    closeBtn.style.cssText = `
      position: fixed;
      top: 30px;
      right: 30px;
      width: 50px;
      height: 50px;
      border-radius: 50%;
      border: 2px solid rgba(255,255,255,.3);
      background: rgba(0,0,0,.7);
      color: white;
      font-size: 1.5rem;
      cursor: pointer;
      transition: all 0.3s ease;
      z-index: 1000000;
      display: flex;
      align-items: center;
      justify-content: center;
      backdrop-filter: blur(10px);
    `;
    closeBtn.onmouseover = function() {
      this.style.background = 'rgba(239,68,68,.9)';
      this.style.borderColor = 'rgba(239,68,68,1)';
      this.style.transform = 'rotate(90deg) scale(1.1)';
    };
    closeBtn.onmouseout = function() {
      this.style.background = 'rgba(0,0,0,.7)';
      this.style.borderColor = 'rgba(255,255,255,.3)';
      this.style.transform = 'rotate(0deg) scale(1)';
    };
    
    // Название изображения
    const imageTitle = document.createElement('div');
    imageTitle.textContent = imageAlt || 'Товар';
    imageTitle.style.cssText = `
      position: fixed;
      bottom: 40px;
      left: 50%;
      transform: translateX(-50%);
      background: rgba(0,0,0,.8);
      color: white;
      padding: 12px 28px;
      border-radius: 50px;
      font-weight: 700;
      font-size: 1.1rem;
      backdrop-filter: blur(10px);
      border: 1px solid rgba(255,255,255,.2);
      box-shadow: 0 10px 30px rgba(0,0,0,.5);
      z-index: 1000000;
    `;
    
    // Собираем все вместе
    imageContainer.appendChild(img);
    lightbox.appendChild(imageContainer);
    lightbox.appendChild(closeBtn);
    lightbox.appendChild(imageTitle);
    
    // Функция закрытия
    const closeLightbox = function() {
      lightbox.style.opacity = '0';
      imageContainer.style.transform = 'scale(0.7)';
      setTimeout(() => {
        lightbox.remove();
        // Восстанавливаем скролл если он был заблокирован
        if (!document.getElementById('dsProductPopup')) {
          document.body.style.overflow = '';
        }
      }, 400);
    };
    
    // Обработчики закрытия
    closeBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      closeLightbox();
    });
    
    lightbox.addEventListener('click', function(e) {
      // Закрываем только если кликнули на backdrop, не на изображение
      if (e.target === lightbox) {
        closeLightbox();
      }
    });
    
    // Закрытие по Escape
    const escapeHandler = function(e) {
      if (e.key === 'Escape') {
        closeLightbox();
        document.removeEventListener('keydown', escapeHandler);
      }
    };
    document.addEventListener('keydown', escapeHandler);
    
    // Предотвращаем клик на изображении от закрытия
    img.addEventListener('click', function(e) {
      e.stopPropagation();
    });
    
    // Добавляем в DOM
    document.body.appendChild(lightbox);
    
    // Анимация появления
    setTimeout(() => {
      lightbox.style.opacity = '1';
      imageContainer.style.transform = 'scale(1)';
    }, 10);
    
    console.log('✅ Lightbox открыт');
  };
  
  console.log('✅ Модуль модального окна дропшиппера инициализирован (динамическое создание)');
  
})();
