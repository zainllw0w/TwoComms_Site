(function() {
  'use strict';

  // Инициализация при загрузке DOM
  document.addEventListener('DOMContentLoaded', function() {
    initProductDetail();
  });

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
    const colorPicker = document.getElementById('colorPicker');
    if (!colorPicker) return;

    const mainImage = document.getElementById('mainProductImage');
    const mainWrapper = document.getElementById('mainImageWrapper');
    const thumbnails = document.getElementById('productThumbnails');
    
    // Парсим данные вариантов
    const variantDataTag = document.getElementById('variant-data');
    let variants = [];
    try {
      variants = JSON.parse((variantDataTag && variantDataTag.textContent) || '[]');
    } catch(e) {
      variants = [];
    }

    // Превью изображения при hover на свотч
    const swatches = colorPicker.querySelectorAll('.product-color-swatch, .product-color-swatch-compact');
    swatches.forEach(swatch => {
      const variantId = parseInt(swatch.getAttribute('data-variant') || '-1', 10);
      const variant = variants.find(v => v.id === variantId);
      
      // Клик на свотч (без превью при hover)
      swatch.addEventListener('click', function() {
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
            const payload = document.getElementById('product-analytics-payload');
            const pid = payload && payload.dataset.id;
            window.trackEvent('CustomizeProduct', {
              content_ids: [String(pid)],
              content_type: 'product',
              variant_id: variantId
            });
          }
        } catch(e) {}
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
    tempImg.style.left = '100%';
    tempImg.style.width = '100%';
    tempImg.style.height = '100%';
    tempImg.style.objectFit = 'contain';
    tempImg.style.transition = 'left 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94)';
    tempImg.alt = mainImage.alt;
    
    wrapper.appendChild(tempImg);
    
    // Запускаем анимацию
    requestAnimationFrame(() => {
      mainImage.style.transition = 'left 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94)';
      mainImage.style.position = 'absolute';
      mainImage.style.left = '-100%';
      
      tempImg.style.left = '0';
    });
    
    // После анимации заменяем изображение
    setTimeout(() => {
      mainImage.src = newImage;
      mainImage.setAttribute('data-zoom', newImage);
      mainImage.style.position = 'static';
      mainImage.style.left = 'auto';
      mainImage.style.transition = '';
      tempImg.remove();
      
      // Обновляем zoom
      if (window.mediumZoom) {
        const zoom = window.mediumZoom(mainImage);
        if (zoom) zoom.refresh();
      }
    }, 400);
  }

  // Показ превью цвета
  let previewElement = null;
  function showColorPreview(imageUrl) {
    if (!imageUrl) return;
    
    const mainImage = document.getElementById('mainProductImage');
    if (!mainImage) return;
    
    previewElement = document.createElement('div');
    previewElement.className = 'color-preview-overlay';
    previewElement.style.cssText = `
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.8);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 5;
      opacity: 0;
      transition: opacity 0.3s ease;
    `;
    
    const previewImg = document.createElement('img');
    previewImg.src = imageUrl;
    previewImg.style.cssText = `
      max-width: 80%;
      max-height: 80%;
      object-fit: contain;
      border-radius: 12px;
    `;
    
    previewElement.appendChild(previewImg);
    mainImage.parentElement.appendChild(previewElement);
    
    requestAnimationFrame(() => {
      previewElement.style.opacity = '1';
    });
  }

  function hideColorPreview() {
    if (previewElement) {
      previewElement.style.opacity = '0';
      setTimeout(() => {
        if (previewElement && previewElement.parentElement) {
          previewElement.parentElement.removeChild(previewElement);
        }
        previewElement = null;
      }, 300);
    }
  }

  // Обновление галереи
  function initImageGallery() {
    const extraImagesTag = document.getElementById('product-extra-images');
    if (!extraImagesTag) return;
    
    let extraImages = [];
    try {
      extraImages = JSON.parse(extraImagesTag.textContent || '[]').filter(img => !!img);
    } catch(e) {
      extraImages = [];
    }
    
    const mainImage = document.getElementById('mainProductImage');
    if (!mainImage) return;
    
    const mainUrl = mainImage.src;
    const allImages = [mainUrl, ...extraImages];
    const thumbnails = document.getElementById('productThumbnails');
    
    if (!thumbnails) return;
    
    thumbnails.innerHTML = '';
    
    allImages.forEach((url, idx) => {
      const thumb = document.createElement('button');
      thumb.type = 'button';
      thumb.className = 'product-thumbnail' + (idx === 0 ? ' active' : '');
      thumb.addEventListener('click', () => {
        thumbnails.querySelectorAll('.product-thumbnail').forEach(t => t.classList.remove('active'));
        thumb.classList.add('active');
        mainImage.src = url;
        mainImage.setAttribute('data-zoom', url);
        if (window.mediumZoom) {
          const zoom = window.mediumZoom(mainImage);
          if (zoom) zoom.refresh();
        }
      });
      
      const img = document.createElement('img');
      img.src = url;
      img.alt = '';
      img.loading = 'lazy';
      
      thumb.appendChild(img);
      thumbnails.appendChild(thumb);
    });
  }

  function updateThumbnails(images, thumbnailsContainer) {
    if (!images || images.length === 0 || !thumbnailsContainer) return;
    
    thumbnailsContainer.innerHTML = '';
    
    images.forEach((url, idx) => {
      const thumb = document.createElement('button');
      thumb.type = 'button';
      thumb.className = 'product-thumbnail' + (idx === 0 ? ' active' : '');
      thumb.addEventListener('click', () => {
        thumbnailsContainer.querySelectorAll('.product-thumbnail').forEach(t => t.classList.remove('active'));
        thumb.classList.add('active');
        const mainImage = document.getElementById('mainProductImage');
        if (mainImage) {
          mainImage.src = url;
          mainImage.setAttribute('data-zoom', url);
          if (window.mediumZoom) {
            const zoom = window.mediumZoom(mainImage);
            if (zoom) zoom.refresh();
          }
        }
      });
      
      const img = document.createElement('img');
      img.src = url;
      img.alt = '';
      img.loading = 'lazy';
      
      thumb.appendChild(img);
      thumbnailsContainer.appendChild(thumb);
    });
  }

  // Medium Zoom для изображений
  function initMediumZoom() {
    const mainImage = document.getElementById('mainProductImage');
    if (mainImage && window.mediumZoom) {
      const zoom = window.mediumZoom(mainImage, {
        background: 'rgba(12, 12, 15, 0.95)',
        margin: 40
      });
      window.productImageZoom = zoom;
    }
  }

  // Карусель рекомендаций с автопрокруткой
  function initRecommendationsCarousel() {
    const swiperEl = document.getElementById('recommendationsSwiper');
    if (!swiperEl || !window.Swiper) return;
    
    const swiper = new window.Swiper(swiperEl, {
      slidesPerView: 1,
      spaceBetween: 20,
      autoplay: {
        delay: 3000, // 3 секунды между слайдами
        disableOnInteraction: false,
        pauseOnMouseEnter: true
      },
      loop: true,
      speed: 1200, // Плавная прокрутка
      effect: 'slide',
      freeMode: false,
      breakpoints: {
        576: {
          slidesPerView: 2,
          spaceBetween: 20
        },
        768: {
          slidesPerView: 3,
          spaceBetween: 24
        },
        992: {
          slidesPerView: 4,
          spaceBetween: 24
        },
        1200: {
          slidesPerView: 4,
          spaceBetween: 28
        }
      },
      navigation: {
        nextEl: '.recommendations-next',
        prevEl: '.recommendations-prev'
      },
      on: {
        init: function() {
          // Показываем навигацию только на desktop
          if (window.innerWidth >= 992) {
            const next = document.querySelector('.recommendations-next');
            const prev = document.querySelector('.recommendations-prev');
            if (next) next.style.display = 'flex';
            if (prev) prev.style.display = 'flex';
          }
        }
      }
    });
    
    // Скрываем навигацию на мобильных
    window.addEventListener('resize', function() {
      const next = document.querySelector('.recommendations-next');
      const prev = document.querySelector('.recommendations-prev');
      if (window.innerWidth >= 992) {
        if (next) next.style.display = 'flex';
        if (prev) prev.style.display = 'flex';
      } else {
        if (next) next.style.display = 'none';
        if (prev) prev.style.display = 'none';
      }
    });
  }

  // Вкладки
  function initTabs() {
    const tabButtons = document.querySelectorAll('.product-tab-btn-modern');
    const tabPanes = document.querySelectorAll('.product-tab-pane-modern');
    
    tabButtons.forEach(button => {
      button.addEventListener('click', function() {
        const tabName = this.getAttribute('data-tab');
        
        // Убираем active со всех
        tabButtons.forEach(btn => btn.classList.remove('active'));
        tabPanes.forEach(pane => pane.classList.remove('active'));
        
        // Добавляем active к выбранным
        this.classList.add('active');
        const pane = document.getElementById('tab-' + tabName);
        if (pane) pane.classList.add('active');
      });
    });
  }

  // Выбор размера
  function initSizeSelection() {
    const sizeInputs = document.querySelectorAll('input[name="size"]');
    const addToCartBtn = document.getElementById('addToCartBtn');
    const stickyBtn = document.getElementById('stickyAddToCartBtn');
    
    function checkSizeAvailability() {
      const checkedSize = document.querySelector('input[name="size"]:checked');
      const isUnavailable = checkedSize && checkedSize.disabled;
      
      [addToCartBtn, stickyBtn].forEach(btn => {
        if (!btn) return;
        if (isUnavailable) {
          btn.classList.add('unavailable');
          btn.disabled = true;
          btn.querySelector('.btn-text')?.setAttribute('data-original-text', btn.querySelector('.btn-text').textContent);
          btn.querySelector('.btn-text').textContent = 'Немає в наявності';
        } else {
          btn.classList.remove('unavailable');
          btn.disabled = false;
          const originalText = btn.querySelector('.btn-text')?.getAttribute('data-original-text');
          if (originalText) {
            btn.querySelector('.btn-text').textContent = originalText;
          }
        }
      });
    }
    
    sizeInputs.forEach(input => {
      input.addEventListener('change', checkSizeAvailability);
    });
    
    checkSizeAvailability();
  }

  // Sticky кнопка для мобильных
  function initStickyButton() {
    const stickyContainer = document.getElementById('productStickyMobile');
    if (!stickyContainer) return;
    
    // Показываем sticky на мобильных
    function updateStickyVisibility() {
      if (window.innerWidth < 992) {
        stickyContainer.classList.add('active');
      } else {
        stickyContainer.classList.remove('active');
      }
    }
    
    updateStickyVisibility();
    window.addEventListener('resize', updateStickyVisibility);
    
    // Синхронизируем клики sticky и обычной кнопки
    const stickyBtn = stickyContainer.querySelector('.sticky-add-btn');
    const mainBtn = document.getElementById('addToCartBtn');
    
    if (stickyBtn && mainBtn) {
      stickyBtn.addEventListener('click', function() {
        mainBtn.click();
      });
    }
  }

  // Добавление в корзину с fly to cart анимацией
  function initAddToCart() {
    const addButtons = document.querySelectorAll('[data-add-to-cart]');
    
    addButtons.forEach(button => {
      button.addEventListener('click', function(e) {
        // Если есть inline обработчик, не перехватываем
        if (this.hasAttribute('onclick')) return;
        
        e.preventDefault();
        
        const productId = this.getAttribute('data-add-to-cart');
        const sizeInput = document.querySelector('input[name="size"]:checked');
        const size = sizeInput ? sizeInput.value : 'S';
        
        // Получаем выбранный цвет
        let colorVariantId = null;
        const activeColorSwatch = document.querySelector('#colorPicker .product-color-swatch.active, #colorPicker .product-color-swatch-compact.active');
        if (activeColorSwatch) {
          colorVariantId = activeColorSwatch.getAttribute('data-variant');
        }
        
        // Получаем количество
        const qtyInput = document.getElementById('productQty');
        const qty = qtyInput ? parseInt(qtyInput.value) || 1 : 1;
        
        // Показываем loading состояние
        button.classList.add('loading');
        button.disabled = true;
        
        // Fly to cart анимация
        const mainImage = document.getElementById('mainProductImage');
        if (mainImage && window.innerWidth < 992) {
          // На мобильных летит вниз
          flyToCartMobile(mainImage, button);
        } else if (mainImage) {
          // На desktop летит вверх
          flyToCartDesktop(mainImage, button);
        }
        
        // Отправляем запрос
        const body = new URLSearchParams({
          product_id: productId,
          size: size,
          qty: qty
        });
        
        if (colorVariantId) {
          body.append('color_variant_id', colorVariantId);
        }
        
        fetch('/cart/add/', {
          method: 'POST',
          headers: {
            'X-CSRFToken': getCSRFToken(),
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
          },
          body: body
        })
        .then(r => r.json())
        .then(data => {
          button.classList.remove('loading');
          button.disabled = false;
          
          if (data.ok) {
            // Success состояние
            button.classList.add('success');
            const originalText = button.querySelector('.btn-text')?.textContent;
            if (originalText) {
              button.querySelector('.btn-text').setAttribute('data-original-text', originalText);
            }
            button.querySelector('.btn-text').textContent = 'Додано!';
            
            // Обновляем мини-корзину
            try {
              if (window.refreshMiniCart) window.refreshMiniCart();
            } catch(e) {}
            
            // Возвращаем текст через 2 секунды
            setTimeout(() => {
              button.classList.remove('success');
              const original = button.querySelector('.btn-text')?.getAttribute('data-original-text');
              if (original) {
                button.querySelector('.btn-text').textContent = original;
              } else {
                button.querySelector('.btn-text').textContent = 'Додати в кошик';
              }
            }, 2000);
          } else {
            // Error состояние
            button.classList.add('error');
            button.querySelector('.btn-text').textContent = 'Помилка';
            setTimeout(() => {
              button.classList.remove('error');
              const original = button.querySelector('.btn-text')?.getAttribute('data-original-text');
              if (original) {
                button.querySelector('.btn-text').textContent = original;
              } else {
                button.querySelector('.btn-text').textContent = 'Додати в кошик';
              }
            }, 2000);
          }
        })
        .catch(error => {
          button.classList.remove('loading');
          button.disabled = false;
          button.classList.add('error');
          button.querySelector('.btn-text').textContent = 'Помилка';
          setTimeout(() => {
            button.classList.remove('error');
            const original = button.querySelector('.btn-text')?.getAttribute('data-original-text');
            if (original) {
              button.querySelector('.btn-text').textContent = original;
            } else {
              button.querySelector('.btn-text').textContent = 'Додати в кошик';
            }
          }, 2000);
        });
      });
    });
  }

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
      
      flyElement.style.left = startRect.left + 'px';
      flyElement.style.top = startRect.top + 'px';
      
      requestAnimationFrame(() => {
        flyElement.style.left = cartRect.left + (cartRect.width / 2) - 30 + 'px';
        flyElement.style.top = cartRect.top + (cartRect.height / 2) - 30 + 'px';
        flyElement.style.transform = 'scale(0.3)';
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
      
      flyElement.style.left = startRect.left + 'px';
      flyElement.style.top = startRect.top + 'px';
      
      requestAnimationFrame(() => {
        flyElement.style.left = cartRect.left + (cartRect.width / 2) - 30 + 'px';
        flyElement.style.top = cartRect.top + (cartRect.height / 2) - 30 + 'px';
        flyElement.style.transform = 'scale(0.3)';
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

