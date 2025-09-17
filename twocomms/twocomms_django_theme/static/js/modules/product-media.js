import { MobileOptimizer } from './optimizers.js';
import { prefersReducedMotion } from './shared.js';

function preloadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}

function getColorImageUrl(colorDot) {
  const imageUrl = colorDot.getAttribute('data-image-url');
  if (imageUrl) {
    return imageUrl;
  }
  const title = colorDot.getAttribute('title');
  if (title) {
    return null;
  }
  return null;
}

function animateImageChange(img, newSrc) {
  return new Promise((resolve) => {
    img.classList.add('switching');
    preloadImage(newSrc).then(() => {
      const picture = img.closest('picture');
      if (picture) {
        const sources = picture.querySelectorAll('source');
        sources.forEach(source => {
          const srcset = source.getAttribute('srcset');
          if (srcset) {
            const baseUrl = newSrc.replace(/\/[^\/]+\.(jpg|jpeg|png)$/, '');
            const fileName = newSrc.match(/\/([^\/]+)\.(jpg|jpeg|png)$/);
            if (fileName) {
              const baseName = fileName[1];
              const type = source.getAttribute('type');
              let newSrcset;
              if (type === 'image/avif') {
                newSrcset = `${baseUrl}/optimized/${baseName}.avif`;
              } else if (type === 'image/webp') {
                newSrcset = `${baseUrl}/optimized/${baseName}.webp`;
              } else {
                newSrcset = newSrc;
              }
              source.setAttribute('srcset', newSrcset);
            }
          }
        });
        img.src = newSrc;
      } else {
        img.src = newSrc;
      }
      requestAnimationFrame(() => {
        img.classList.remove('switching');
        resolve();
      });
    }).catch(() => {
      img.classList.remove('switching');
      resolve();
    });
  });
}

function handleColorDotClick(e) {
  if (!e.target.classList || !e.target.classList.contains('color-dot')) {
    return;
  }
  e.stopPropagation();
  const colorDot = e.target;
  const productCardWrap = colorDot.closest('.product-card-wrap');
  const productCard = productCardWrap ? productCardWrap.querySelector('.card.product') : null;
  if (!productCard) {
    return;
  }
  const mainImage = productCard.querySelector('.ratio picture img') || productCard.querySelector('.ratio .product-main-image') || productCard.querySelector('.ratio img');
  if (!mainImage) {
    return;
  }
  const newImageUrl = getColorImageUrl(colorDot, productCard);
  const allDots = productCardWrap.querySelectorAll('.color-dot');
  allDots.forEach(dot => {
    dot.classList.remove('active');
    dot.classList.add('switching');
  });
  requestAnimationFrame(() => {
    colorDot.classList.remove('switching');
    colorDot.classList.add('active');
  });
  if (!newImageUrl) {
    return;
  }
  if (mainImage.src !== newImageUrl) {
    animateImageChange(mainImage, newImageUrl);
  }
}

export function forceShowAllImages() {}

function revealColorDots() {
  const colorDots = document.querySelectorAll('.color-dot');
  colorDots.forEach((dot, index) => {
    requestAnimationFrame(() => {
      setTimeout(() => {
        dot.classList.add('visible');
      }, index * 60);
    });
  });
}

export function initProductMedia() {
  document.addEventListener('click', handleColorDotClick, { passive: false });

  const onReady = () => {
    MobileOptimizer.initMobileOptimizations();
    revealColorDots();
  };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', onReady);
  } else {
    onReady();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', forceShowAllImages);
  } else {
    forceShowAllImages();
  }
  window.addEventListener('load', forceShowAllImages);
}
