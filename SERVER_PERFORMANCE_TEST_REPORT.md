# Отчет о тестировании производительности сервера TwoComms

**Дата тестирования:** 2025-10-14T04:36:24.678537

## 📊 Сводка результатов

### Время загрузки страниц

### Производительность базы данных
- ✅ **query_1**: 0.65s
- ✅ **query_2**: 0.552s
- ✅ **query_3**: 0.586s
- ✅ **query_4**: 0.594s

### Использование памяти
- **Django процессы**: 1
- **Память Django**: 30.57 MB
- **Системная память**: 14.1%

### Статические файлы

## 🚨 Обнаруженные проблемы
- Ошибка загрузки /: HTTPConnectionPool(host='localhost', port=8000): Max retries exceeded with url: / (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x7f02c13c9550>: Failed to establish a new connection: [Errno 111] Connection refused'))
- Ошибка загрузки /catalog/: HTTPConnectionPool(host='localhost', port=8000): Max retries exceeded with url: /catalog/ (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x7f02c13d9f90>: Failed to establish a new connection: [Errno 111] Connection refused'))
- Ошибка загрузки /product/base-hoodie-black/: HTTPConnectionPool(host='localhost', port=8000): Max retries exceeded with url: /product/base-hoodie-black/ (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x7f02c13da850>: Failed to establish a new connection: [Errno 111] Connection refused'))
- Ошибка загрузки /cart/: HTTPConnectionPool(host='localhost', port=8000): Max retries exceeded with url: /cart/ (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x7f02c1382b10>: Failed to establish a new connection: [Errno 111] Connection refused'))
- Ошибка загрузки /admin-panel/: HTTPConnectionPool(host='localhost', port=8000): Max retries exceeded with url: /admin-panel/ (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x7f02c1383230>: Failed to establish a new connection: [Errno 111] Connection refused'))
- Ошибка загрузки /static/css/styles.css: HTTPConnectionPool(host='localhost', port=8000): Max retries exceeded with url: /static/css/styles.css (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x7f02c06b0170>: Failed to establish a new connection: [Errno 111] Connection refused'))
- Ошибка загрузки /static/js/main.js: HTTPConnectionPool(host='localhost', port=8000): Max retries exceeded with url: /static/js/main.js (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x7f02c14ff9b0>: Failed to establish a new connection: [Errno 111] Connection refused'))
- Ошибка загрузки /static/img/logo.png: HTTPConnectionPool(host='localhost', port=8000): Max retries exceeded with url: /static/img/logo.png (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x7f02c14ff350>: Failed to establish a new connection: [Errno 111] Connection refused'))

## 📋 Рекомендации

### Критические проблемы
1. Исправить ошибки загрузки страниц
2. Оптимизировать медленные запросы к БД
3. Уменьшить использование памяти

### Оптимизация
1. Включить кэширование статических файлов
2. Использовать CDN для статики
3. Оптимизировать изображения
4. Настроить gzip сжатие

---
*Отчет сгенерирован автоматически системой тестирования TwoComms*
