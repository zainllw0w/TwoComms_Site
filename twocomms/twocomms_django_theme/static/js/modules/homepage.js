import { prefersReducedMotion } from './shared.js';
import { forceShowAllImages } from './product-media.js';

function parseNumber(value, fallback = 1) {
  const parsed = parseInt(value, 10);
  return Number.isNaN(parsed) ? fallback : parsed;
}

function buildPageHref(basePath, page) {
  const safeBasePath = basePath || window.location.pathname || '/';
  if (page <= 1) {
    return safeBasePath;
  }
  return `${safeBasePath}?page=${page}`;
}

function syncPaginationViewport(navElement, currentPage) {
  if (!navElement) return;
  const scrollContainer = navElement.closest('.pagination-rail');
  const activeItem = navElement.querySelector(`.page-item-number[data-page="${currentPage}"]`);
  if (!scrollContainer || !activeItem) return;

  const scrollToActive = () => {
    const itemRect = activeItem.getBoundingClientRect();
    const containerRect = scrollContainer.getBoundingClientRect();
    const maxScroll = scrollContainer.scrollWidth - scrollContainer.clientWidth;

    if (maxScroll <= 0) {
      return;
    }

    let targetLeft = scrollContainer.scrollLeft + (itemRect.left - containerRect.left) - ((containerRect.width - itemRect.width) / 2);
    targetLeft = Math.max(0, Math.min(targetLeft, maxScroll));

    if (currentPage <= 2) {
      targetLeft = 0;
    }

    const totalPages = parseNumber(navElement.dataset.totalPages || currentPage, currentPage);
    if (currentPage >= totalPages - 1) {
      targetLeft = maxScroll;
    }

    scrollContainer.scrollTo({
      left: targetLeft,
      behavior: prefersReducedMotion ? 'auto' : 'smooth',
    });
  };

  requestAnimationFrame(scrollToActive);
}

function updatePaginationNav(navElement, currentPage) {
  if (!navElement) return;
  const totalPages = parseNumber(navElement.dataset.totalPages || currentPage, currentPage);
  const basePath = navElement.dataset.basePath || window.location.pathname || '/';

  navElement.dataset.currentPage = String(currentPage);

  navElement.querySelectorAll('.page-item-number').forEach((item) => {
    const targetPage = parseNumber(item.dataset.page, null);
    if (!targetPage) return;
    const link = item.querySelector('.page-link');
    item.classList.toggle('active', targetPage === currentPage);
    if (link) {
      if (targetPage === currentPage) {
        link.setAttribute('aria-current', 'page');
      } else {
        link.removeAttribute('aria-current');
      }
    }
  });

  const prevLink = navElement.querySelector('[data-page-nav="prev"]');
  const nextLink = navElement.querySelector('[data-page-nav="next"]');
  const prevItem = prevLink?.closest('.page-item');
  const nextItem = nextLink?.closest('.page-item');

  if (prevItem && prevLink) {
    const disabled = currentPage <= 1;
    prevItem.classList.toggle('disabled', disabled);
    prevLink.setAttribute('href', disabled ? '#' : buildPageHref(basePath, currentPage - 1));
  }

  if (nextItem && nextLink) {
    const disabled = currentPage >= totalPages;
    nextItem.classList.toggle('disabled', disabled);
    nextLink.setAttribute('href', disabled ? '#' : buildPageHref(basePath, currentPage + 1));
  }

  syncPaginationViewport(navElement, currentPage);
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
    const paginationNav = document.querySelector('nav[aria-label="Навігація по новинках"]');

    if (!productsContainer) {
      return;
    }

    const getTotalPages = () => {
      const dataValue = loadMoreContainer?.dataset.totalPages || paginationNav?.dataset.totalPages || '1';
      return parseNumber(dataValue, 1);
    };

    const getCurrentPage = () => parseNumber(loadMoreContainer?.dataset.currentPage || paginationNav?.dataset.currentPage || '1', 1);

    const setTotalPages = (value) => {
      if (loadMoreContainer) {
        loadMoreContainer.dataset.totalPages = String(value);
      }
      if (paginationNav) {
        paginationNav.dataset.totalPages = String(value);
      }
    };

    const setCurrentPage = (value) => {
      if (loadMoreContainer) {
        loadMoreContainer.dataset.currentPage = String(value);
      }
      if (paginationNav) {
        paginationNav.dataset.currentPage = String(value);
      }
      updatePaginationNav(paginationNav, value);
    };

    const updateLoadMoreState = (currentPage, totalPages) => {
      const hasMore = currentPage < totalPages;
      if (!loadMoreBtn || !loadMoreContainer) {
        return hasMore;
      }
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

    const syncUI = () => {
      const totalPages = getTotalPages();
      const currentPage = getCurrentPage();
      if (paginationNav) {
        paginationNav.dataset.totalPages = String(totalPages);
        paginationNav.dataset.currentPage = String(currentPage);
      }
      updatePaginationNav(paginationNav, currentPage);
      updateLoadMoreState(currentPage, totalPages);
    };

    const loadPage = (pageNumber) => {
      const targetPage = parseNumber(pageNumber, getCurrentPage());
      if (!loadMoreBtn || !loadMoreContainer) return;
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

    if (loadMoreBtn) {
      loadMoreBtn.addEventListener('click', () => {
        const nextPage = parseNumber(loadMoreBtn.dataset.page, getCurrentPage() + 1);
        loadPage(nextPage);
      });
    }

    syncUI();
    revealColorDots(productsContainer);
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot, { once: true });
  } else {
    boot();
  }
}
