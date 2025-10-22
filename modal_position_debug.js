// Скрипт для детального анализа позиционирования модального окна
// Вставьте этот код в консоль браузера на странице https://twocomms.shop/orders/dropshipper/

console.log('🔍 НАЧАЛО АНАЛИЗА МОДАЛЬНОГО ОКНА');
console.log('='.repeat(80));

// Функция для анализа элемента
function analyzeElement(element, name) {
    if (!element) {
        console.log(`❌ ${name}: НЕ НАЙДЕН`);
        return;
    }
    
    const computed = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    
    console.log(`\n📦 ${name}:`);
    console.log('  Положение:', {
        position: computed.position,
        top: computed.top,
        left: computed.left,
        transform: computed.transform,
        zIndex: computed.zIndex,
    });
    console.log('  Размеры:', {
        width: computed.width,
        height: computed.height,
        maxWidth: computed.maxWidth,
        maxHeight: computed.maxHeight,
    });
    console.log('  BoundingRect:', {
        top: rect.top,
        left: rect.left,
        right: rect.right,
        bottom: rect.bottom,
        x: rect.x,
        y: rect.y,
        width: rect.width,
        height: rect.height,
    });
    console.log('  Display & Overflow:', {
        display: computed.display,
        overflow: computed.overflow,
        overflowX: computed.overflowX,
        overflowY: computed.overflowY,
    });
    console.log('  Visibility:', {
        opacity: computed.opacity,
        visibility: computed.visibility,
    });
}

// Функция для проверки родительских контейнеров
function checkParentPositions(element, name) {
    console.log(`\n🔗 Родительские контейнеры для ${name}:`);
    let parent = element.parentElement;
    let level = 1;
    
    while (parent && level <= 10) {
        const computed = window.getComputedStyle(parent);
        const hasProblematicStyle = 
            computed.position !== 'static' ||
            computed.transform !== 'none' ||
            computed.willChange !== 'auto' ||
            computed.perspective !== 'none';
        
        if (hasProblematicStyle || parent.classList.contains('ds-shell') || parent.classList.contains('ds-main') || parent.tagName === 'BODY') {
            console.log(`  ${'  '.repeat(level)}${level}. ${parent.tagName}${parent.className ? '.' + parent.className.split(' ').join('.') : ''}:`, {
                position: computed.position,
                transform: computed.transform,
                willChange: computed.willChange,
                perspective: computed.perspective,
                containingBlock: hasProblematicStyle ? '⚠️ СОЗДАЕТ CONTAINING BLOCK' : '✅ OK',
            });
        }
        
        parent = parent.parentElement;
        level++;
    }
}

// Анализируем viewport
console.log('\n📱 VIEWPORT:');
console.log('  Размеры окна:', {
    width: window.innerWidth,
    height: window.innerHeight,
});
console.log('  Прокрутка:', {
    scrollX: window.scrollX,
    scrollY: window.scrollY,
});

// Анализируем body
const body = document.body;
analyzeElement(body, 'BODY');

// Анализируем .ds-shell
const dsShell = document.querySelector('.ds-shell');
analyzeElement(dsShell, '.ds-shell');

// Анализируем .ds-main
const dsMain = document.querySelector('.ds-main');
analyzeElement(dsMain, '.ds-main');

// Анализируем backdrop
const backdrop = document.getElementById('dsProductPopupBackdrop');
if (backdrop) {
    analyzeElement(backdrop, 'BACKDROP');
    checkParentPositions(backdrop, 'BACKDROP');
}

// Анализируем модальное окно
const modal = document.getElementById('dsProductPopup');
if (modal) {
    analyzeElement(modal, 'MODAL');
    checkParentPositions(modal, 'MODAL');
    
    // Проверяем dataset
    console.log('\n💾 DATASET модального окна:', modal.dataset);
    
    // Проверяем inline стили
    console.log('\n🎨 INLINE STYLES модального окна:');
    console.log('  style.position:', modal.style.position);
    console.log('  style.top:', modal.style.top);
    console.log('  style.left:', modal.style.left);
    console.log('  style.transform:', modal.style.transform);
    console.log('  style.zIndex:', modal.style.zIndex);
} else {
    console.log('\n❌ MODAL: НЕ НАЙДЕН - откройте модальное окно и запустите скрипт снова');
}

// Расчет центрирования
console.log('\n🎯 ПРАВИЛЬНОЕ ЦЕНТРИРОВАНИЕ (для position: fixed):');
const centerTop = window.innerHeight / 2;
const centerLeft = window.innerWidth / 2;
console.log(`  top: 50% (или ${centerTop}px)`);
console.log(`  left: 50% (или ${centerLeft}px)`);
console.log('  transform: translate(-50%, -50%)');
console.log('  ⚠️ НЕ НУЖНО учитывать scrollY для position: fixed!');

// Проверка стилей модального окна
if (modal) {
    const computed = window.getComputedStyle(modal);
    const rect = modal.getBoundingClientRect();
    
    console.log('\n🧮 ВЫЧИСЛЕННОЕ ПОЛОЖЕНИЕ МОДАЛЬНОГО ОКНА:');
    console.log('  Центр viewport:', { x: window.innerWidth / 2, y: window.innerHeight / 2 });
    console.log('  Центр модального окна:', { 
        x: rect.left + rect.width / 2, 
        y: rect.top + rect.height / 2 
    });
    
    const deltaX = (rect.left + rect.width / 2) - (window.innerWidth / 2);
    const deltaY = (rect.top + rect.height / 2) - (window.innerHeight / 2);
    
    console.log('  Отклонение от центра:', { 
        deltaX: deltaX.toFixed(2) + 'px',
        deltaY: deltaY.toFixed(2) + 'px',
        centered: Math.abs(deltaX) < 5 && Math.abs(deltaY) < 5 ? '✅ ДА' : '❌ НЕТ'
    });
    
    // Проверяем видимость
    console.log('\n👁️ ВИДИМОСТЬ МОДАЛЬНОГО ОКНА:');
    const isVisible = 
        rect.top < window.innerHeight &&
        rect.bottom > 0 &&
        rect.left < window.innerWidth &&
        rect.right > 0;
    
    console.log('  В области видимости:', isVisible ? '✅ ДА' : '❌ НЕТ');
    
    if (!isVisible) {
        console.log('  ⚠️ МОДАЛЬНОЕ ОКНО ЗА ПРЕДЕЛАМИ VIEWPORT!');
        if (rect.top < 0) console.log('    - Сверху (top < 0)');
        if (rect.bottom > window.innerHeight) console.log('    - Снизу (bottom > innerHeight)');
        if (rect.left < 0) console.log('    - Слева (left < 0)');
        if (rect.right > window.innerWidth) console.log('    - Справа (right > innerWidth)');
    }
}

console.log('\n' + '='.repeat(80));
console.log('✅ АНАЛИЗ ЗАВЕРШЕН');
console.log('📋 Скопируйте весь вывод консоли и отправьте AI для анализа');

