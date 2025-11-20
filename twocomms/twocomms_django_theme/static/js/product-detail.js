(function () {
  'use strict';

  // Инициализация при загрузке DOM
  document.addEventListener('DOMContentLoaded', function () {
    initProductDetail();
  });

  // Local DOM Cache
  const DOM = {
    elements: {},
    get(id) {
      if (!this.elements[id]) {
        this.elements[id] = document.getElementById(id);
      }
      return this.elements[id];
    }
  };

  function initProductDetail() {
    initColorSwatches();
    initImageGallery();
    initRecommendationsCarousel();
    initMediumZoom();
    initTabs();
    initSizeSelection();
    initStickyButton();
    initAddToCart();
    initURLParams();
  }

  // Переключение цветов с slide анимацией
  function initColorSwatches() {
    const colorPicker = DOM.get('colorPicker');
    if (!colorPicker) return;

    const mainImage = DOM.get('mainProductImage');
    const mainWrapper = DOM.get('mainImageWrapper');
    const thumbnails = DOM.get('productThumbnails');

    // Парсим данные вариантов
    const variantDataTag = DOM.get('variant-data');
    let variants = [];
    try {
      variants = JSON.parse((variantDataTag && variantDataTag.textContent) || '[]');
    } catch (e) {
      variants = [];
    }

    // Превью изображения при hover на свотч
    const swatches = colorPicker.querySelectorAll('.product-color-swatch, .product-color-swatch-compact');
    swatches.forEach(swatch => {
      const variantId = parseInt(swatch.getAttribute('data-variant') || '-1', 10);
      const variant = variants.find(v => v.id === variantId);

      // Клик на свотч (без превью при hover)
      swatch.addEventListener('click', function () {
        if (!variant) return;

        // Убираем active со всех
        swatches.forEach(s => s.classList.remove('active'));
        swatch.classList.add('active');

        // Добавляем checkmark
        swatches.forEach(s => {
          const checkIcon = s.querySelector('.color-check-icon');
          if (checkIcon) checkIcon.remove();
        });

        if (!swatch.querySelector('.color-check-icon')) {
          const checkIcon = document.createElement('span');
          checkIcon.className = 'color-check-icon';
          checkIcon.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>';
          swatch.appendChild(checkIcon);
        }

        // Переключаем изображения с slide анимацией
        if (variant.images && variant.images.length > 0) {
          switchImagesWithSlide(variant.images, mainImage, mainWrapper);
          updateThumbnails(variant.images, thumbnails);
        }

        // Analytics tracking
        try {
          if (window.trackEvent) {
            const payload = DOM.get('product-analytics-payload');
            const pid = payload && payload.dataset.id;
            window.trackEvent('CustomizeProduct', {
              content_ids: [String(pid)],
              content_type: 'product',
              variant_id: variantId
            });
          }
        } catch (e) { }
      });
    });
  }

  // Slide анимация переключения изображений
  function switchImagesWithSlide(images, mainImage, wrapper) {
    if (!images || images.length === 0 || !mainImage || !wrapper) return;

    const newImage = images[0];

    // Создаем временное изображение для slide эффекта
    const tempImg = document.createElement('img');
    tempImg.src = newImage;
    tempImg.className = 'product-main-image';
    tempImg.style.position = 'absolute';
    tempImg.style.top = '0';
    tempImg.style.left = '0'; // Start at 0 but translated
    tempImg.style.width = '100%';
    tempImg.style.height = '100%';
    tempImg.style.objectFit = 'contain';
    tempImg.style.transform = 'translateX(100%)'; // Initial position
    tempImg.style.willChange = 'transform';
    tempImg.alt = mainImage.alt;

    wrapper.appendChild(tempImg);

    // Prepare main image for animation
    mainImage.style.position = 'absolute';
    mainImage.style.top = '0';
    mainImage.style.left = '0';
    mainImage.style.willChange = 'transform';

    // Запускаем анимацию
    requestAnimationFrame(() => {
      // Force reflow
      tempImg.getBoundingClientRect();

      mainImage.style.transition = 'transform 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94)';
      tempImg.style.transition = 'transform 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94)';

      mainImage.style.transform = 'translateX(-100%)';
      tempImg.style.transform = 'translateX(0)';
    });

    // После анимации заменяем изображение
    setTimeout(() => {
      mainImage.src = newImage;
      mainImage.setAttribute('data-zoom', newImage);
      mainImage.style.position = 'static';
      mainImage.style.transform = '';
      mainImage.style.transition = '';
      mainImage.style.willChange = '';
      tempImg.remove();

      // Обновляем zoom
      if (window.mediumZoom) {
        const zoom = window.mediumZoom(mainImage);
        if (zoom) zoom.refresh();
      }
    }, 400);
  }

  // ... (rest of the file until flyToCartMobile) ...

  // Fly to cart анимация для мобильных
  function flyToCartMobile(image, button) {
    const flyElement = document.createElement('div');
    flyElement.className = 'fly-to-cart';

    const img = document.createElement('img');
    img.src = image.src;
    flyElement.appendChild(img);

    document.body.appendChild(flyElement);

    const buttonRect = button.getBoundingClientRect();
    const cartBtn = document.querySelector('#cart-toggle-mobile') || document.querySelector('#cart-toggle');

    if (cartBtn) {
      const cartRect = cartBtn.getBoundingClientRect();
      const startRect = image.getBoundingClientRect();

      // Set initial position using transform
      flyElement.style.position = 'fixed';
      flyElement.style.left = '0';
      flyElement.style.top = '0';
      flyElement.style.transform = `translate(${startRect.left}px, ${startRect.top}px)`;
      flyElement.style.willChange = 'transform, opacity';

      // Calculate target position relative to viewport (since fixed)
      const targetX = cartRect.left + (cartRect.width / 2) - 30;
      const targetY = cartRect.top + (cartRect.height / 2) - 30;

      requestAnimationFrame(() => {
        // Force reflow
        flyElement.getBoundingClientRect();

        flyElement.style.transition = 'transform 0.6s cubic-bezier(0.19, 1, 0.22, 1), opacity 0.6s ease';
        flyElement.style.transform = `translate(${targetX}px, ${targetY}px) scale(0.3)`;
        flyElement.style.opacity = '0';
      });

      setTimeout(() => {
        if (flyElement.parentElement) {
          flyElement.parentElement.removeChild(flyElement);
        }
      }, 600);
    } else {
      // Fallback: просто исчезает
      setTimeout(() => {
        if (flyElement.parentElement) {
          flyElement.parentElement.removeChild(flyElement);
        }
      }, 300);
    }
  }

  // Fly to cart анимация для desktop
  function flyToCartDesktop(image, button) {
    const flyElement = document.createElement('div');
    flyElement.className = 'fly-to-cart';

    const img = document.createElement('img');
    img.src = image.src;
    flyElement.appendChild(img);

    document.body.appendChild(flyElement);

    const cartBtn = document.querySelector('#cart-toggle');

    if (cartBtn) {
      const cartRect = cartBtn.getBoundingClientRect();
      const startRect = image.getBoundingClientRect();

      // Set initial position using transform
      flyElement.style.position = 'fixed';
      flyElement.style.left = '0';
      flyElement.style.top = '0';
      flyElement.style.transform = `translate(${startRect.left}px, ${startRect.top}px)`;
      flyElement.style.willChange = 'transform, opacity';

      // Calculate target position
      const targetX = cartRect.left + (cartRect.width / 2) - 30;
      const targetY = cartRect.top + (cartRect.height / 2) - 30;

      requestAnimationFrame(() => {
        // Force reflow
        flyElement.getBoundingClientRect();

        flyElement.style.transition = 'transform 0.6s cubic-bezier(0.19, 1, 0.22, 1), opacity 0.6s ease';
        flyElement.style.transform = `translate(${targetX}px, ${targetY}px) scale(0.3)`;
        flyElement.style.opacity = '0';
      });

      setTimeout(() => {
        if (flyElement.parentElement) {
          flyElement.parentElement.removeChild(flyElement);
        }
      }, 600);
    } else {
      setTimeout(() => {
        if (flyElement.parentElement) {
          flyElement.parentElement.removeChild(flyElement);
        }
      }, 300);
    }
  }

  // URL параметры для размеров
  function initURLParams() {
    const urlParams = new URLSearchParams(window.location.search);
    const sizeParam = urlParams.get('size');

    if (sizeParam) {
      const sizeInput = document.querySelector(`input[name="size"][value="${sizeParam.toUpperCase()}"]`);
      if (sizeInput && !sizeInput.disabled) {
        sizeInput.checked = true;
        sizeInput.dispatchEvent(new Event('change'));
      }
    }
  }

  // Получение CSRF токена
  function getCSRFToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) return meta.getAttribute('content');

    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (input) return input.value;

    // Fallback: cookie
    const name = 'csrftoken';
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

})();

