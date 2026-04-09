# PageSpeed Performance Optimization Progress

**Дата начала:** 2025-01-XX
**Приоритет:** Mobile First
**Статус:** ✅ Основные оптимизации выполнены

---

## 📊 Исходные проблемы (из PERFORMANCE_FIX_MAP.md)

### КРИТИЧЕСКИЕ (влияют на LCP/TBT/CLS):
1. ✅ **Блокирующий CSS** - `{% compress css %}` теперь async через `media="print"` hack
2. ✅ **Тяжелые CSS анимации** - отключены в aggressive perf-lite mode
3. ✅ **Длинные JS задачи** - cart/favorites отложены на 2s или user interaction
4. ✅ **LCP fetchpriority** - проверено, hero уже имеет fetchpriority="high"

### ВАЖНЫЕ:
5. ✅ **Third-party скрипты** - GTM/FB/TikTok отложены на user interaction или 3-4s timeout
6. ⏸️ **Шрифты Inter** - preload уже настроен, subsetting требует внешних инструментов
7. ✅ **Цепочки критических запросов** - cart/favorites теперь отложены

### НИЗКИЙ ПРИОРИТЕТ:
8. ✅ **Кэш TTL** - все CSS/JS файлы теперь кэшируются на 1 год (не только min)
9. ⏸️ **Неподдерживаемые CSS свойства** - не критично для PageSpeed

---

## ✅ ВЫПОЛНЕННЫЕ ИЗМЕНЕНИЯ

### 1. CSS Loading Optimization (`base.html`)
- ✅ Добавлен `media="print" onload="this.media='all'"` hack для async CSS loading
- ✅ Critical CSS расширен: product cards, bottom nav, reveal animations
- ✅ perf-lite режим автоматически включается на mobile

### 2. Aggressive perf-lite Mode для Mobile (`base.html`)
- ✅ Отключены ВСЕ backdrop-filter (очень дорого на mobile GPU)
- ✅ Отключены все filter эффекты
- ✅ Отключены все box-shadow
- ✅ Отключены все @keyframes анимации (`animation-duration: 0.001ms`)
- ✅ Отключены все transition
- ✅ Скрыты все декоративные элементы (glow, sparks, particles, floating-logos)
- ✅ Reveal элементы показываются мгновенно без анимации

### 3. JavaScript Optimization (`main.js`)
- ✅ Cart/favorites запросы отложены на 2s или до user interaction
- ✅ Используется scheduleIdle() для некритичных операций
- ✅ Guard против множественных вызовов

### 4. Third-party Scripts (`base.html`, `analytics-loader.js`)
- ✅ GTM: загружается на user interaction (scroll/click/touch/mousemove/keydown) или после 4s
- ✅ Meta Pixel: загружается на user interaction или после 3s
- ✅ TikTok Pixel: загружается на user interaction или после 3s
- ✅ Clarity: загружается через schedule() с 3s задержкой
- ✅ GA4: загружается через schedule() с 2s задержкой

### 5. Caching (`cache_headers.py`)
- ✅ Все CSS/JS файлы кэшируются на 1 год (immutable)
- ✅ Изображения кэшируются на 1 год
- ✅ Шрифты кэшируются на 1 год

---

## 📁 ИЗМЕНЕННЫЕ ФАЙЛЫ

| Файл | Изменение |
|------|-----------|
| `twocomms/twocomms_django_theme/templates/base.html` | Async CSS, extended critical CSS, aggressive perf-lite, deferred GTM |
| `twocomms/twocomms_django_theme/static/js/main.js` | Deferred cart/favorites requests |
| `twocomms/twocomms_django_theme/static/js/analytics-loader.js` | Deferred pixel loading |
| `twocomms/twocomms/cache_headers.py` | Extended cache TTL for all CSS/JS |

---

## 🔧 ИНСТРУКЦИИ ДЛЯ DEPLOY НА СЕРВЕР

После деплоя на сервер выполнить:

```bash
# 1. Перейти в директорию проекта и обновить код
cd /home/qlknpodo/TWC/TwoComms_Site/twocomms
git pull origin perf-pagespeed-mobile-priority-performance-fix-map

# 2. Активировать виртуальное окружение
source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/activate

# 3. Очистка статики и перекомпиляция (ВАЖНО!)
python manage.py collectstatic --noinput --clear

# 4. Пересжатие CSS (django-compressor)
python manage.py compress --force

# 5. Перезапуск приложения (Passenger)
touch tmp/restart.txt

# 6. Очистить browser cache и проверить в PageSpeed Insights
```

### Проверка результатов:
1. Открыть https://pagespeed.web.dev/
2. Ввести URL сайта
3. Выбрать "Mobile" для приоритетной проверки
4. Сравнить показатели до и после

---

## 📈 ОЖИДАЕМЫЕ УЛУЧШЕНИЯ

### Mobile:
| Метрика | До | После (ожидается) |
|---------|-----|-------------------|
| LCP | Высокий | < 2.5s |
| TBT | Высокий (third-party) | < 200ms |
| CLS | Оптимизировано | < 0.1 |
| FCP | - | < 1.8s |
| Render-blocking CSS | 930ms | ~0ms |

### Desktop:
| Метрика | До | После (ожидается) |
|---------|-----|-------------------|
| LCP | - | < 1.5s |
| TBT | - | < 100ms |
| CLS | Оптимизировано | < 0.05 |
| FCP | - | < 1.0s |

---

## ⚠️ ВАЖНЫЕ ЗАМЕЧАНИЯ

### Что НЕ было изменено (сохранено):
- ✅ Visual appearance на desktop (внешний вид полностью сохранён)
- ✅ Функциональность корзины/избранного
- ✅ Аналитика (GTM/Pixel/TikTok) - только отложена, не удалена
- ✅ SEO структура
- ✅ Работа на слабых устройствах (perf-lite режим)

### Mobile vs Desktop:
- На mobile (и слабых устройствах) автоматически включается `perf-lite` режим
- Визуально: убираются декоративные анимации, glow эффекты, particles
- Функционально: всё работает идентично
- Desktop с хорошим железом: сохраняется полный визуал

### Потенциальные проблемы:
1. **FOUC (Flash of Unstyled Content)** - возможен кратковременный FOUC при async CSS
   - Решение: Critical CSS inline покрывает основные элементы
2. **Analytics delay** - пиксели могут не успеть загрузиться при быстром уходе
   - Решение: буферизация событий, fallback таймауты

---

## 🔜 ДАЛЬНЕЙШИЕ ОПТИМИЗАЦИИ (если потребуется)

### Для SSH агента с доступом к серверу:

1. **Font subsetting** - уменьшить размер Inter шрифтов
   ```bash
   # Требует pyftsubset из fonttools
   pip install fonttools[ufo,lxml,woff,unicode]
   pyftsubset Inter-Regular.woff2 --unicodes="U+0000-00FF,U+0400-04FF" --flavor=woff2
   ```

2. **Image optimization** - проверить что AVIF/WebP отдаётся
   ```bash
   # Проверка заголовков
   curl -I "https://twocomms.ua/media/products/..." | grep -i content-type
   ```

3. **Brotli compression** - если nginx поддерживает
   ```nginx
   brotli on;
   brotli_types text/css application/javascript;
   ```

4. **HTTP/2 Push** - если поддерживается
   ```nginx
   http2_push /static/CACHE/css/output.xxx.css;
   ```

---

## 📝 ТЕХНИЧЕСКИЕ ДЕТАЛИ

### perf-lite Detection (в base.html):
```javascript
var needsLite = saveData || lowRam || lowCPU || isMobile;
// saveData: navigator.connection.saveData
// lowRam: navigator.deviceMemory <= 2
// lowCPU: navigator.hardwareConcurrency <= 2  
// isMobile: window.innerWidth < 768
```

### CSS Loading Flow:
1. Critical CSS inline → мгновенный FCP
2. Main CSS через `media="print"` → не блокирует рендер
3. `onload="this.media='all'"` → применяется после загрузки

### Third-party Loading:
1. GTM → user interaction OR 4s timeout
2. Meta Pixel → user interaction OR 3s timeout
3. TikTok Pixel → user interaction OR 3s timeout
4. Clarity → 3s delay via requestIdleCallback
5. GA4 → 2s delay via requestIdleCallback

---

*Обновлено: $(date)*
