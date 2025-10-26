# ⚡ Быстрый Старт: Обновление Google Merchant Feed

## 🎯 Одна команда для обновления СЕЙЧАС

Скопируйте и вставьте в терминал:

```bash
ssh qlknpodo@195.191.24.169 'cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/python manage.py generate_google_merchant_feed --output twocomms/static/google_merchant_feed.xml && cp -f twocomms/static/google_merchant_feed.xml media/google-merchant-v3.xml && echo "✅ ГОТОВО!" && ls -lh media/google-merchant-v3.xml && grep -c "<item>" media/google-merchant-v3.xml | xargs -I {} echo "📦 Товаров в feed: {}"'
```

**Эта команда:**
- ✅ Обновит feed с актуальными ценами
- ✅ Обновит все товары
- ✅ Покажет результат

---

## 🔍 Проверить результат

### В браузере:
```
https://twocomms.shop/media/google-merchant-v3.xml
```

### Проверить CRON задачу:
```bash
ssh qlknpodo@195.191.24.169 "crontab -l | grep merchant"
```

### Посмотреть логи:
```bash
ssh qlknpodo@195.191.24.169 "tail -20 /home/qlknpodo/TWC/TwoComms_Site/twocomms/cron.log"
```

---

## 📚 Полная документация

Для детальных инструкций смотрите: **[GOOGLE_MERCHANT_FEED_UPDATE.md](./GOOGLE_MERCHANT_FEED_UPDATE.md)**

---

## 🛠️ Скрипты

| Скрипт | Описание | Использование |
|--------|----------|---------------|
| `update_feed_now.sh` | Быстрое обновление | `ssh qlknpodo@195.191.24.169 "bash -s" < update_feed_now.sh` |
| `update_google_merchant_feed.sh` | Полное обновление + CRON | `ssh qlknpodo@195.191.24.169 "bash -s" < update_google_merchant_feed.sh` |
| `verify_google_feed.sh` | Проверка feed | `ssh qlknpodo@195.191.24.169 "bash -s" < verify_google_feed.sh` |
| `check_merchant_cron.sh` | Проверка CRON | `ssh qlknpodo@195.191.24.169 "bash -s" < check_merchant_cron.sh` |

---

## ⚙️ Настройка автообновления

Если CRON не настроен, выполните:

```bash
ssh qlknpodo@195.191.24.169 << 'ENDSSH'
(crontab -l 2>/dev/null | grep -v "generate_google_merchant_feed" | grep -v "Django: обновление Google Merchant feed"; 
echo "# Django: обновление Google Merchant feed (создано $(date +%Y-%m-%d))"; 
echo "0 4 * * * cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.13/bin/python manage.py generate_google_merchant_feed --output twocomms/static/google_merchant_feed.xml && cp -f twocomms/static/google_merchant_feed.xml media/google-merchant-v3.xml >> /home/qlknpodo/TWC/TwoComms_Site/twocomms/cron.log 2>&1") | crontab -
echo "✅ CRON настроен: обновление каждый день в 4:00"
ENDSSH
```

---

## 🎉 Готово!

Feed будет обновляться автоматически каждый день в 4:00 утра.

