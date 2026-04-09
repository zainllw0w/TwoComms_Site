# ⚡ Быстрое решение: Настроить CRON без ошибок

## 🎯 Самый простой способ (через SSH - 1 команда)

**Скопируйте и выполните эту команду:**

```bash
sshpass -p 'trs5m4t1' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "bash -lc '(crontab -l 2>/dev/null | grep -v update_tracking_statuses | grep -v \"Nova Poshta\"; echo \"# Nova Poshta: проверка каждые 5 минут\"; echo \"*/5 * * * * cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/python manage.py update_tracking_statuses >> /tmp/nova_poshta.log 2>&1\") | crontab - && crontab -l | grep update_tracking_statuses'"
```

**Это:**
- ✅ Настроит cron каждые 5 минут
- ✅ Покажет результат
- ✅ Не требует cPanel

---

## 📝 Или через cPanel (если SSH не работает)

### Вариант 1: Короткая команда (для cPanel)

В cPanel → Cron Jobs добавьте:

**Время:**
```
*/5 * * * *
```

**Команда:**
```bash
/home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/python /home/qlknpodo/TWC/TwoComms_Site/twocomms/manage.py update_tracking_statuses >> /tmp/nova_poshta.log 2>&1
```

**Важно:** В cPanel не используйте `cd &&`, используйте полный путь к Python.

---

## ✅ Проверка

Через 5-10 минут проверьте:

```bash
tail -20 /tmp/nova_poshta.log
```

Должно быть:
```
[2025-10-30 XX:XX:XX] Начало обновления статусов...
Найдено X заказов с ТТН
Обновление завершено...
```

---

## 🔍 Если появилась ошибка "Internal Error"

1. **Где появилась?** (cPanel, браузер, SSH)
2. **Что вы делали?** (настраивали cron, открывали страницу)
3. **Проверьте логи:**

```bash
sshpass -p 'trs5m4t1' ssh -o StrictHostKeyChecking=no qlknpodo@195.191.24.169 "tail -30 /tmp/nova_poshta.log"
```

---

**Подробные инструкции:**
- `КАК_РАБОТАЕТ_CRON.md` - объяснение как работает cron
- `ИНСТРУКЦИЯ_CPANEL_CRON.md` - детальная инструкция для cPanel
- `РЕШЕНИЕ_ВНУТРЕННЯЯ_ОШИБКА.md` - решение ошибок

















