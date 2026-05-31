/**
 * UI Enhancements для Finance — БЛОК 6
 * CountUp анімація для чисел, skeleton loaders, smooth interactions
 */

// CountUp для анімації чисел
function animateValue(element, start, end, duration) {
    if (!element) return;

    const range = end - start;
    const increment = range / (duration / 16); // 60 FPS
    let current = start;

    const timer = setInterval(() => {
        current += increment;
        if ((increment > 0 && current >= end) || (increment < 0 && current <= end)) {
            current = end;
            clearInterval(timer);
        }

        // Форматування числа з пробілами
        const formatted = Math.round(current).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
        element.textContent = formatted;
    }, 16);
}

// Ініціалізація CountUp для всіх KPI карток
function initCountUp() {
    document.querySelectorAll('.fin-kpi__value, .fin-balance-card__value').forEach(el => {
        const text = el.textContent.trim();
        const match = text.match(/^([-+]?)(\d[\d\s]*)/);

        if (match) {
            const sign = match[1];
            const number = parseInt(match[2].replace(/\s/g, ''), 10);

            if (!isNaN(number) && number > 0) {
                el.setAttribute('data-target', number);
                el.textContent = '0';

                // Запускаємо анімацію після невеликої затримки
                setTimeout(() => {
                    animateValue(el, 0, number, 1500);

                    // Додаємо знак назад після анімації
                    if (sign) {
                        setTimeout(() => {
                            el.textContent = sign + el.textContent;
                        }, 1500);
                    }
                }, 100);
            }
        }
    });
}

// Skeleton loader для таблиць
function showSkeletonLoader(tableBody) {
    if (!tableBody) return;

    const skeletonHTML = `
        <tr class="fin-skeleton-row">
            <td colspan="100%">
                <div class="fin-skeleton">
                    <div class="fin-skeleton__line"></div>
                    <div class="fin-skeleton__line"></div>
                    <div class="fin-skeleton__line"></div>
                </div>
            </td>
        </tr>
    `.repeat(5);

    tableBody.innerHTML = skeletonHTML;
}

// Smooth scroll до елемента
function smoothScrollTo(element, offset = 0) {
    if (!element) return;

    const targetPosition = element.getBoundingClientRect().top + window.pageYOffset - offset;
    window.scrollTo({
        top: targetPosition,
        behavior: 'smooth'
    });
}

// Intersection Observer для lazy-loading графіків
function initLazyCharts() {
    const chartBlocks = document.querySelectorAll('.fin-chart-block');

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('fin-chart-visible');
                observer.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: '50px'
    });

    chartBlocks.forEach(block => observer.observe(block));
}

// Sticky filters на scroll
function initStickyFilters() {
    const filters = document.querySelector('.fin-filters');
    if (!filters) return;

    const filtersTop = filters.offsetTop;

    window.addEventListener('scroll', () => {
        if (window.pageYOffset > filtersTop) {
            filters.classList.add('fin-filters--sticky');
        } else {
            filters.classList.remove('fin-filters--sticky');
        }
    });
}

// Збереження стану фільтрів у localStorage
function saveFiltersState() {
    const form = document.getElementById('fin-filters');
    if (!form) return;

    const formData = new FormData(form);
    const filters = {};

    for (let [key, value] of formData.entries()) {
        if (value) filters[key] = value;
    }

    localStorage.setItem('fin-filters-state', JSON.stringify(filters));
}

// Відновлення стану фільтрів
function restoreFiltersState() {
    const saved = localStorage.getItem('fin-filters-state');
    if (!saved) return;

    try {
        const filters = JSON.parse(saved);
        const form = document.getElementById('fin-filters');
        if (!form) return;

        Object.entries(filters).forEach(([key, value]) => {
            const input = form.querySelector(`[name="${key}"]`);
            if (input) input.value = value;
        });
    } catch (e) {
        console.error('Failed to restore filters:', e);
    }
}

// Показати кількість активних фільтрів
function updateActiveFiltersCount() {
    const form = document.getElementById('fin-filters');
    if (!form) return;

    const formData = new FormData(form);
    let count = 0;

    for (let [key, value] of formData.entries()) {
        if (value && key !== 'period') count++;
    }

    // Оновлюємо badge
    let badge = document.querySelector('.fin-filters__badge');
    if (count > 0) {
        if (!badge) {
            badge = document.createElement('span');
            badge.className = 'fin-filters__badge';
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) submitBtn.appendChild(badge);
        }
        badge.textContent = count;
    } else if (badge) {
        badge.remove();
    }
}

// Toast нотифікації
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `fin-toast fin-toast--${type}`;
    toast.textContent = message;

    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Ініціалізація при завантаженні сторінки
document.addEventListener('DOMContentLoaded', () => {
    // Запускаємо CountUp анімацію
    initCountUp();

    // Ініціалізуємо lazy-loading для графіків
    initLazyCharts();

    // Ініціалізуємо sticky filters
    initStickyFilters();

    // Відновлюємо стан фільтрів
    // restoreFiltersState(); // Закоментовано, щоб не заважати

    // Оновлюємо кількість активних фільтрів
    updateActiveFiltersCount();

    // Зберігаємо стан фільтрів при зміні
    const filterForm = document.getElementById('fin-filters');
    if (filterForm) {
        filterForm.addEventListener('change', () => {
            updateActiveFiltersCount();
            saveFiltersState();
        });
    }

    // Додаємо ripple ефект для кнопок
    document.querySelectorAll('.fin-btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
            const ripple = document.createElement('span');
            ripple.className = 'fin-ripple';
            this.appendChild(ripple);

            setTimeout(() => ripple.remove(), 600);
        });
    });
});

// Експортуємо функції для використання в інших скриптах
window.financeUI = {
    animateValue,
    showSkeletonLoader,
    smoothScrollTo,
    showToast,
    updateActiveFiltersCount
};
