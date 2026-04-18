/**
 * Favorites + notifications — lazy-mounted (Phase 2.1 ext).
 *
 * Реальная логика:
 *   - toggleFavorite(productId, button)  — POST /favorites/toggle/<id>/ + AddToWishlist / RemoveFromWishlist
 *   - checkFavoriteStatus(productId, button) — GET /favorites/check/<id>/ + проставить is-favorite класс
 *   - showNotification(message, type)   — toast-уведомление в правом нижнем углу
 *
 * main.js экспонирует тонкие глобальные стабы `window.toggleFavorite`
 * и т.п., которые динамически импортируют этот модуль при первом вызове.
 * Таким образом `onclick="toggleFavorite(...)"` из шаблонов продолжает работать,
 * но код favorites не парсится/не выполняется до реального взаимодействия.
 */

import { escapeHtml, getCookie } from './shared.js';

export function toggleFavorite(productId, button) {
  if (!button) return;
  button.classList.add('loading');

  fetch(`/favorites/toggle/${productId}/`, {
    method: 'POST',
    headers: {
      'X-CSRFToken': getCookie('csrftoken'),
      'Content-Type': 'application/json',
    },
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        if (data.is_favorite) {
          button.classList.add('is-favorite');
          try {
            if (window.trackEvent) {
              const offerId = 'TC-' + productId + '-default-S';
              let productPrice = parseFloat(button.getAttribute('data-product-price') || '0');
              if (!productPrice || productPrice === 0) productPrice = 0.01;
              window.trackEvent('AddToWishlist', {
                content_ids: [offerId],
                content_type: 'product',
                value: productPrice,
                currency: 'UAH',
                num_items: 1,
                contents: [{ id: offerId, quantity: 1, item_price: productPrice }],
              });
            }
          } catch (_) { }
        } else {
          button.classList.remove('is-favorite');
          try {
            if (window.trackEvent) {
              const offerId = 'TC-' + productId + '-default-S';
              let productPrice = parseFloat(button.getAttribute('data-product-price') || '0');
              if (!productPrice || productPrice === 0) productPrice = 0.01;
              window.trackEvent('RemoveFromWishlist', {
                content_ids: [offerId],
                content_type: 'product',
                value: productPrice,
                currency: 'UAH',
                num_items: 1,
                contents: [{ id: offerId, quantity: 1, item_price: productPrice }],
              });
            }
          } catch (_) { }
        }

        if (data.favorites_count !== undefined) {
          if (typeof window.updateFavoritesBadge === 'function') {
            window.updateFavoritesBadge(data.favorites_count);
          }
        }
        showNotification(data.message, 'success');
      } else {
        showNotification(data.message || 'Помилка', 'error');
      }
    })
    .catch((error) => {
      console.error('Error:', error);
      showNotification('Помилка з\'єднання', 'error');
    })
    .finally(() => {
      button.classList.remove('loading');
    });
}

export function checkFavoriteStatus(productId, button) {
  if (!button) return;
  fetch(`/favorites/check/${productId}/`)
    .then((response) => response.json())
    .then((data) => {
      if (data.is_favorite) button.classList.add('is-favorite');
      else button.classList.remove('is-favorite');
    })
    .catch((error) => {
      console.error('Error checking favorite status:', error);
    });
}

export function showNotification(message, type = 'info') {
  const notification = document.createElement('div');
  notification.className = `notification notification-${type}`;
  notification.innerHTML = `
    <div class="notification-content">
      <span class="notification-message">${escapeHtml(message)}</span>
      <button class="notification-close" onclick="this.parentElement.parentElement.remove();">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
          <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
        </svg>
      </button>
    </div>
  `;
  document.body.appendChild(notification);
  setTimeout(() => { notification.classList.add('show'); }, 100);
  setTimeout(() => {
    notification.classList.remove('show');
    setTimeout(() => {
      if (notification.parentElement) notification.remove();
    }, 300);
  }, 3000);
}
