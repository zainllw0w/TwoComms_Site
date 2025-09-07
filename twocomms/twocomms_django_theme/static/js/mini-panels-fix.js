// Исправление для мини-корзины и мини-профиля
// Этот скрипт загружается после основного main.js и исправляет проблемы

document.addEventListener('DOMContentLoaded', function() {
    console.log('[Mini Panels Fix] Инициализация исправлений...');
    
    // Функция для принудительной переинициализации мини-корзины
    function reinitializeMiniCart() {
        console.log('[Mini Panels Fix] Переинициализация мини-корзины...');
        
        // Удаляем старые обработчики
        const cartToggle = document.getElementById('cart-toggle');
        const cartToggleMobile = document.getElementById('cart-toggle-mobile');
        
        if (cartToggle) {
            cartToggle.removeEventListener('click', toggleMiniCart);
            cartToggle.removeEventListener('pointerdown', function(e) {
                suppressNextDocPointerdownUntil = Date.now() + 250;
            });
            
            // Добавляем новые обработчики
            cartToggle.addEventListener('pointerdown', function(e) {
                suppressNextDocPointerdownUntil = Date.now() + 250;
                console.log('[Mini Panels Fix] Cart toggle pointerdown');
            });
            
            cartToggle.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                console.log('[Mini Panels Fix] Cart toggle click');
                toggleMiniCart();
            });
        }
        
        if (cartToggleMobile) {
            cartToggleMobile.removeEventListener('click', toggleMiniCart);
            cartToggleMobile.removeEventListener('pointerdown', function(e) {
                suppressNextDocPointerdownUntil = Date.now() + 250;
            });
            
            // Добавляем новые обработчики
            cartToggleMobile.addEventListener('pointerdown', function(e) {
                suppressNextDocPointerdownUntil = Date.now() + 250;
                console.log('[Mini Panels Fix] Cart toggle mobile pointerdown');
            });
            
            cartToggleMobile.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                console.log('[Mini Panels Fix] Cart toggle mobile click');
                toggleMiniCart();
            });
        }
    }
    
    // Функция для принудительной переинициализации мини-профиля
    function reinitializeUserPanel() {
        console.log('[Mini Panels Fix] Переинициализация мини-профиля...');
        
        const userToggle = document.getElementById('user-toggle');
        const userPanel = document.getElementById('user-panel');
        
        if (userToggle && userPanel) {
            // Удаляем старые обработчики
            userToggle.removeEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                // Логика переключения профиля
            });
            
            // Добавляем новые обработчики
            userToggle.addEventListener('pointerdown', function(e) {
                suppressNextDocPointerdownUntil = Date.now() + 250;
                console.log('[Mini Panels Fix] User toggle pointerdown');
            });
            
            userToggle.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                console.log('[Mini Panels Fix] User toggle click');
                
                if (userPanel.classList.contains('d-none') || !userPanel.classList.contains('show')) {
                    // Открываем профиль
                    userPanel.classList.remove('d-none', 'hiding');
                    void userPanel.offsetHeight;
                    userPanel.classList.add('show');
                    console.log('[Mini Panels Fix] User panel opened');
                } else {
                    // Закрываем профиль
                    userPanel.classList.remove('show');
                    userPanel.classList.add('hiding');
                    setTimeout(() => {
                        userPanel.classList.add('d-none');
                        userPanel.classList.remove('hiding');
                    }, 220);
                    console.log('[Mini Panels Fix] User panel closed');
                }
            });
        }
        
        // Мобильная версия
        const userToggleMobile = document.getElementById('user-toggle-mobile');
        const userPanelMobile = document.getElementById('user-panel-mobile');
        
        if (userToggleMobile && userPanelMobile) {
            // Удаляем старые обработчики
            userToggleMobile.removeEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                // Логика переключения профиля
            });
            
            // Добавляем новые обработчики
            userToggleMobile.addEventListener('pointerdown', function(e) {
                suppressNextDocPointerdownUntil = Date.now() + 250;
                console.log('[Mini Panels Fix] User toggle mobile pointerdown');
            });
            
            userToggleMobile.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                console.log('[Mini Panels Fix] User toggle mobile click');
                
                if (userPanelMobile.classList.contains('d-none') || !userPanelMobile.classList.contains('show')) {
                    // Открываем профиль
                    userPanelMobile.classList.remove('d-none', 'hiding');
                    void userPanelMobile.offsetHeight;
                    userPanelMobile.classList.add('show');
                    console.log('[Mini Panels Fix] User panel mobile opened');
                } else {
                    // Закрываем профиль
                    userPanelMobile.classList.remove('show');
                    userPanelMobile.classList.add('hiding');
                    setTimeout(() => {
                        userPanelMobile.classList.add('d-none');
                        userPanelMobile.classList.remove('hiding');
                    }, 220);
                    console.log('[Mini Panels Fix] User panel mobile closed');
                }
            });
        }
    }
    
    // Функция для исправления стрелочек
    function fixArrowIssues() {
        console.log('[Mini Panels Fix] Исправление стрелочек...');
        
        // Убираем лишние стрелочки из кнопок
        const buttons = document.querySelectorAll('button, .btn, .menu-item, .cart-menu-item');
        buttons.forEach(button => {
            // Убираем псевдоэлементы, которые могут создавать стрелочки
            button.style.setProperty('--arrow-content', 'none');
            
            // Проверяем, есть ли в кнопке текст со стрелочкой
            if (button.textContent && button.textContent.includes('→')) {
                button.textContent = button.textContent.replace(/→/g, '');
            }
            if (button.textContent && button.textContent.includes('>')) {
                button.textContent = button.textContent.replace(/>/g, '');
            }
        });
        
        // Убираем стрелочки из меню
        const menuItems = document.querySelectorAll('.menu-item, .cart-menu-item');
        menuItems.forEach(item => {
            const arrow = item.querySelector('.menu-arrow, .cart-menu-arrow');
            if (arrow) {
                arrow.style.display = 'none';
            }
        });
    }
    
    // Запускаем исправления с задержкой, чтобы основной скрипт успел загрузиться
    setTimeout(() => {
        reinitializeMiniCart();
        reinitializeUserPanel();
        fixArrowIssues();
        console.log('[Mini Panels Fix] Все исправления применены!');
    }, 500);
    
    // Дополнительная проверка через 2 секунды
    setTimeout(() => {
        console.log('[Mini Panels Fix] Дополнительная проверка...');
        reinitializeMiniCart();
        reinitializeUserPanel();
    }, 2000);
});

// Экспортируем функции для использования в других скриптах
window.MiniPanelsFix = {
    reinitializeMiniCart: function() {
        console.log('[Mini Panels Fix] Ручная переинициализация мини-корзины');
        // Логика переинициализации
    },
    reinitializeUserPanel: function() {
        console.log('[Mini Panels Fix] Ручная переинициализация мини-профиля');
        // Логика переинициализации
    },
    fixArrowIssues: function() {
        console.log('[Mini Panels Fix] Ручное исправление стрелочек');
        // Логика исправления стрелочек
    }
};
