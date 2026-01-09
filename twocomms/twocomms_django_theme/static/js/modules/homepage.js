import { prefersReducedMotion } from './shared.js';
import { forceShowAllImages } from './product-media.js';

function parseNumber(value, fallback = 1) {
  const parsed = parseInt(value, 10);
  return Number.isNaN(parsed) ? fallback : parsed;
}

function populateSelector(pageSelector, totalPages, currentPage) {
  if (!pageSelector) return;
  pageSelector.innerHTML = '';
  for (let i = 1; i <= totalPages; i += 1) {
    const option = document.createElement('option');
    option.value = String(i);
    option.textContent = String(i);
    if (i === currentPage) {
      option.selected = true;
    }
    pageSelector.appendChild(option);
  }
}

function updatePaginationNav(navElement, currentPage) {
  if (!navElement) return;
  const items = navElement.querySelectorAll('.page-item');
  items.forEach((item) => {
    const link = item.querySelector('.page-link');
    if (!link) return;
    const target = parseNumber(link.getAttribute('href')?.split('page=')[1], null);
    if (target) {
      item.classList.toggle('active', target === currentPage);
    }
  });
  const prev = navElement.querySelector('.page-item:first-child');
  const next = navElement.querySelector('.page-item:last-child');
  if (prev) {
    prev.classList.toggle('disabled', currentPage <= 1);
  }
  if (next) {
    const total = parseNumber(navElement.dataset.totalPages || currentPage, currentPage);
    next.classList.toggle('disabled', currentPage >= total);
  }
}

function animateNewCards(container) {
  const allCards = container.querySelectorAll('.product-card-wrap');
  const newCards = Array.from(allCards).slice(-8);
  newCards.forEach((card, index) => {
    if (prefersReducedMotion) {
      card.style.opacity = '';
      card.style.transform = '';
      card.style.filter = '';
      card.style.transition = '';
      return;
    }
    card.classList.remove('reveal-stagger', 'stagger-item', 'reveal-fast', 'reveal');
    const childCards = card.querySelectorAll('.card');
    childCards.forEach(childCard => childCard.classList.remove('reveal-stagger', 'stagger-item', 'reveal-fast', 'reveal'));
    card.style.opacity = '0';
    card.style.transform = 'translateY(24px) scale(0.94)';
    card.style.filter = 'blur(10px)';
    card.style.transition = 'none';
    setTimeout(() => {
      card.style.transition = 'all 560ms cubic-bezier(0.2, 0.8, 0.2, 1)';
      setTimeout(() => {
        card.style.opacity = '1';
        card.style.transform = 'translateY(0) scale(1)';
        card.style.filter = 'blur(0)';
      }, 50);
    }, index * 120);
  });
}

function revealColorDots(container) {
  if (!container) return;
  const cards = container.querySelectorAll('.product-card-wrap');
  cards.forEach((card) => {
    if (card.dataset.colorDotsReady === '1') return;
    const dotsWrap = card.querySelector('.product-card-dots');
    if (!dotsWrap) return;
    dotsWrap.classList.add('visible');
    const dots = dotsWrap.querySelectorAll('.color-dot');
    dots.forEach((dot, idx) => {
      if (dot.classList.contains('visible')) return;
      if (prefersReducedMotion) {
        dot.classList.add('visible');
      } else {
        setTimeout(() => dot.classList.add('visible'), idx * 60);
      }
    });
    card.dataset.colorDotsReady = '1';
  });
}

export function initHomepagePagination() {
  const boot = () => {
    const productsContainer = document.getElementById('products-container');
    const loadMoreBtn = document.getElementById('load-more-btn');
    const loadMoreContainer = document.getElementById('load-more-container');
    const pageSelector = document.getElementById('page-selector');
    const totalPagesSpan = document.getElementById('total-pages');
    const paginationNav = document.querySelector('nav[aria-label="Навігація по новинках"]');

    if (!productsContainer || !loadMoreBtn || !loadMoreContainer) {
      return;
    }

    const getTotalPages = () => {
      const dataValue = loadMoreContainer.dataset.totalPages || (totalPagesSpan ? totalPagesSpan.textContent : '1');
      return parseNumber(dataValue, 1);
    };

    const getCurrentPage = () => parseNumber(loadMoreContainer.dataset.currentPage || '1', 1);

    const setTotalPages = (value) => {
      loadMoreContainer.dataset.totalPages = String(value);
      if (totalPagesSpan) {
        totalPagesSpan.textContent = String(value);
      }
      if (paginationNav) {
        paginationNav.dataset.totalPages = String(value);
      }
    };

    const setCurrentPage = (value) => {
      loadMoreContainer.dataset.currentPage = String(value);
      if (pageSelector) {
        pageSelector.value = String(value);
      }
      updatePaginationNav(paginationNav, value);
    };

    const updateLoadMoreState = (currentPage, totalPages) => {
      const hasMore = currentPage < totalPages;
      if (hasMore) {
        loadMoreBtn.dataset.page = String(currentPage + 1);
        loadMoreBtn.disabled = false;
        loadMoreContainer.style.display = '';
      } else {
        loadMoreBtn.dataset.page = '';
        loadMoreContainer.style.display = 'none';
      }
      return hasMore;
    };

    const syncSelector = () => {
      const totalPages = getTotalPages();
      const currentPage = getCurrentPage();
      populateSelector(pageSelector, totalPages, currentPage);
      updateLoadMoreState(currentPage, totalPages);
    };

    const loadPage = (pageNumber) => {
      const targetPage = parseNumber(pageNumber, getCurrentPage());
      if (loadMoreBtn.disabled) return;
      const btnText = loadMoreBtn.querySelector('.btn-text');
      const btnSpinner = loadMoreBtn.querySelector('.btn-spinner');
      if (btnText && btnSpinner) {
        btnText.classList.add('d-none');
        btnSpinner.classList.remove('d-none');
      }
      loadMoreBtn.disabled = true;

      fetch(`/load-more-products/?page=${targetPage}`)
        .then(response => response.json())
        .then(data => {
          if (data && data.html && data.html.trim() !== '') {
            productsContainer.insertAdjacentHTML('beforeend', data.html);
            const totalPages = parseNumber(data.total_pages, getTotalPages());
            const currentPage = parseNumber(data.current_page, targetPage);
            setTotalPages(totalPages);
            setCurrentPage(currentPage);
            populateSelector(pageSelector, totalPages, currentPage);
            const hasMore = updateLoadMoreState(currentPage, totalPages);
            if (!hasMore && paginationNav) {
              updatePaginationNav(paginationNav, currentPage);
            }
            animateNewCards(productsContainer);
            revealColorDots(productsContainer);
            setTimeout(() => {
              try {
                if (window.equalizeCardHeights) {
                  window.equalizeCardHeights();
                }
                if (window.equalizeProductTitles) {
                  setTimeout(() => window.equalizeProductTitles(), 50);
                }
              } catch (_) {}
            }, 200);
            setTimeout(() => {
              forceShowAllImages();
            }, 100);
          }
        })
        .catch(() => {})
        .finally(() => {
          if (btnText && btnSpinner) {
            btnText.classList.remove('d-none');
            btnSpinner.classList.add('d-none');
          }
          loadMoreBtn.disabled = false;
        });
    };

    loadMoreBtn.addEventListener('click', () => {
      const nextPage = parseNumber(loadMoreBtn.dataset.page, getCurrentPage() + 1);
      loadPage(nextPage);
    });

    if (pageSelector) {
      pageSelector.addEventListener('change', () => {
        const selectedPage = parseNumber(pageSelector.value, getCurrentPage());
        loadPage(selectedPage);
      });
    }

    syncSelector();
    revealColorDots(productsContainer);
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot, { once: true });
  } else {
    boot();
  }
}
