/* TwoComms Finance — PWA та налаштування
   Service Worker реєстрація, installability, push-повідомлення, settings panel */
(function () {
    'use strict';

    let deferredPrompt = null;
    let swRegistration = null;
    let settingsCloseTimer = null;

    window.FinanceSettings = {
        open: openSettings,
        close: closeSettings,
        isOpen: function () {
            const panel = document.getElementById('fin-settings-panel');
            return !!panel && !panel.hidden;
        }
    };

    document.addEventListener('DOMContentLoaded', function () {
        // ===== Service Worker реєстрація =====
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/static/js/finance-sw.js', { scope: '/' })
                .then(function (registration) {
                    console.log('[Finance PWA] Service Worker registered:', registration.scope);
                    swRegistration = registration;

                    // Перевіряємо оновлення кожні 60 секунд
                    setInterval(function () {
                        registration.update();
                    }, 60000);

                    // Слухаємо оновлення SW
                    registration.addEventListener('updatefound', function () {
                        const newWorker = registration.installing;
                        newWorker.addEventListener('statechange', function () {
                            if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                                // Є нова версія - показуємо повідомлення
                                showUpdateNotification();
                            }
                        });
                    });
                })
                .catch(function (error) {
                    console.error('[Finance PWA] Service Worker registration failed:', error);
                });

            // Слухаємо повідомлення від SW
            navigator.serviceWorker.addEventListener('message', function (event) {
                console.log('[Finance PWA] Message from SW:', event.data);
            });
        }

        // ===== Install prompt =====
        const installBtn = document.getElementById('install-app-btn');
        const installHint = document.getElementById('install-hint');

        window.addEventListener('beforeinstallprompt', function (e) {
            e.preventDefault();
            deferredPrompt = e;

            // Показуємо кнопку встановлення
            if (installBtn) {
                installBtn.hidden = false;
                installBtn.addEventListener('click', installApp);
            }
            if (installHint) installHint.hidden = false;
        });

        window.addEventListener('appinstalled', function () {
            console.log('[Finance PWA] App installed');
            deferredPrompt = null;
            if (installBtn) installBtn.hidden = true;
            if (installHint) installHint.hidden = true;
        });

        // ===== Панель налаштувань =====
        const settingsBtn = document.getElementById('fin-settings-btn');
        const settingsPanel = document.getElementById('fin-settings-panel');
        const settingsClose = document.getElementById('fin-settings-close');
        const settingsBackdrop = document.getElementById('fin-settings-backdrop');
        const pushDisclosure = document.getElementById('fin-push-disclosure');
        const pushDisclosureContent = document.getElementById('fin-push-settings-content');

        if (settingsBtn && settingsPanel) {
            settingsBtn.addEventListener('click', function () {
                openSettings();
            });

            settingsClose?.addEventListener('click', closeSettings);
            settingsBackdrop?.addEventListener('click', closeSettings);

            document.addEventListener('keydown', function (e) {
                if (e.key === 'Escape' && !settingsPanel.hidden) {
                    closeSettings();
                }
            });
        }

        if (pushDisclosure && pushDisclosureContent) {
            pushDisclosure.addEventListener('click', function () {
                const open = pushDisclosure.getAttribute('aria-expanded') !== 'true';
                pushDisclosure.setAttribute('aria-expanded', open ? 'true' : 'false');
                pushDisclosureContent.hidden = !open;
            });
        }

        // ===== Push-повідомлення =====
        const pushEnabled = document.getElementById('push-enabled');
        const pushSettingsContent = document.getElementById('push-settings-content');
        const pushDailyEnabled = document.getElementById('push-daily-enabled');
        const pushWeeklyEnabled = document.getElementById('push-weekly-enabled');
        const dailyTimeField = document.getElementById('daily-time-field');
        const weeklyDayField = document.getElementById('weekly-day-field');
        const saveSettingsBtn = document.getElementById('save-settings-btn');

        if (pushEnabled) {
            pushEnabled.addEventListener('change', function () {
                if (this.checked) {
                    requestNotificationPermission();
                }
                if (pushSettingsContent) pushSettingsContent.hidden = !this.checked;
            });
        }

        if (pushDailyEnabled) {
            pushDailyEnabled.addEventListener('change', function () {
                dailyTimeField.hidden = !this.checked;
            });
        }

        if (pushWeeklyEnabled) {
            pushWeeklyEnabled.addEventListener('change', function () {
                weeklyDayField.hidden = !this.checked;
            });
        }

        if (saveSettingsBtn) {
            saveSettingsBtn.addEventListener('click', saveSettings);
        }

        const testPushBtn = document.getElementById('test-push-btn');
        if (testPushBtn) {
            testPushBtn.addEventListener('click', function () {
                testPushBtn.disabled = true;
                fetch('/api/push/test/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    }
                })
                    .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
                    .then(function (res) {
                        if (res.ok && res.d.success) {
                            showNotification('Тестове повідомлення надіслано', 'success');
                        } else {
                            showNotification(res.d.error || 'Не вдалося надіслати', 'error');
                        }
                    })
                    .catch(function () { showNotification('Помилка мережі', 'error'); })
                    .finally(function () { testPushBtn.disabled = false; });
            });
        }

        // Завантажуємо збережені налаштування
        loadSettings();

        // ===== Швидкі дії з PWA shortcuts =====
        const urlParams = new URLSearchParams(window.location.search);
        const action = urlParams.get('action');
        if (action && window.FinanceModals) {
            setTimeout(function () {
                if (action === 'income' || action === 'expense' || action === 'transfer') {
                    window.FinanceModals.open(action);
                }
            }, 500);
        }
    });

    // ===== Функції =====
    function openSettings() {
        const panel = document.getElementById('fin-settings-panel');
        const settingsBtn = document.getElementById('fin-settings-btn');
        const burger = document.getElementById('fin-burger');
        if (panel) {
            if (settingsCloseTimer) {
                clearTimeout(settingsCloseTimer);
                settingsCloseTimer = null;
            }
            document.body.classList.remove('fin-sidebar-open', 'fin-menu-open');
            document.body.classList.add('fin-settings-open', 'fin-any-drawer-open');
            if (burger) burger.setAttribute('aria-expanded', 'false');
            if (settingsBtn) settingsBtn.setAttribute('aria-expanded', 'true');
            panel.hidden = false;
            // Анімація
            requestAnimationFrame(function () {
                panel.classList.add('is-open');
            });
        }
    }

    function closeSettings() {
        const panel = document.getElementById('fin-settings-panel');
        const settingsBtn = document.getElementById('fin-settings-btn');
        if (panel) {
            if (settingsCloseTimer) {
                clearTimeout(settingsCloseTimer);
                settingsCloseTimer = null;
            }
            panel.classList.remove('is-open');
            if (settingsBtn) settingsBtn.setAttribute('aria-expanded', 'false');
            settingsCloseTimer = setTimeout(function () {
                panel.hidden = true;
                document.body.classList.remove('fin-settings-open');
                document.body.classList.toggle('fin-any-drawer-open', document.body.classList.contains('fin-sidebar-open'));
                settingsCloseTimer = null;
            }, 300);
        }
    }

    function installApp() {
        if (!deferredPrompt) return;

        deferredPrompt.prompt();
        deferredPrompt.userChoice.then(function (choiceResult) {
            if (choiceResult.outcome === 'accepted') {
                console.log('[Finance PWA] User accepted install');
            }
            deferredPrompt = null;
        });
    }

    function requestNotificationPermission() {
        if (!('Notification' in window)) {
            alert('Ваш браузер не підтримує push-повідомлення');
            document.getElementById('push-enabled').checked = false;
            return;
        }

        if (Notification.permission === 'granted') {
            subscribeToPush();
            return;
        }

        if (Notification.permission !== 'denied') {
            Notification.requestPermission().then(function (permission) {
                if (permission === 'granted') {
                    subscribeToPush();
                } else {
                    document.getElementById('push-enabled').checked = false;
                    alert('Дозвіл на повідомлення відхилено');
                }
            });
        } else {
            document.getElementById('push-enabled').checked = false;
            alert('Повідомлення заблоковані в налаштуваннях браузера');
        }
    }

    function subscribeToPush() {
        if (!swRegistration) {
            console.error('[Finance PWA] No SW registration');
            return;
        }
        var vapidKey = getVapidPublicKey();
        if (!vapidKey) {
            console.warn('[Finance PWA] VAPID key not configured — push disabled');
            var toggle = document.getElementById('push-enabled');
            if (toggle) toggle.checked = false;
            return;
        }

        swRegistration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(vapidKey)
        })
            .then(function (subscription) {
                console.log('[Finance PWA] Push subscription:', subscription);
                sendSubscriptionToServer(subscription);
            })
            .catch(function (error) {
                console.error('[Finance PWA] Push subscription failed:', error);
            });
    }

    function sendSubscriptionToServer(subscription) {
        fetch('/api/push/subscribe/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                subscription: subscription.toJSON()
            })
        })
            .then(function (response) {
                if (!response.ok) throw new Error('Subscription failed');
                console.log('[Finance PWA] Subscription sent to server');
            })
            .catch(function (error) {
                console.error('[Finance PWA] Failed to send subscription:', error);
            });
    }

    function saveSettings() {
        const settings = {
            push_enabled: document.getElementById('push-enabled')?.checked || false,
            push_daily_enabled: document.getElementById('push-daily-enabled')?.checked || false,
            push_daily_time: document.getElementById('push-daily-time')?.value || '20:00',
            push_weekly_enabled: document.getElementById('push-weekly-enabled')?.checked || false,
            push_weekly_day: parseInt(document.getElementById('push-weekly-day')?.value || '1'),
            push_weekly_time: document.getElementById('push-weekly-time')?.value || '10:00',
            push_health_alerts: document.getElementById('push-health-alerts')?.checked || false,
            telegram_notifications: document.getElementById('telegram-notifications')?.checked || false
        };

        // Зберігаємо локально
        try {
            localStorage.setItem('fin_settings', JSON.stringify(settings));
        } catch (e) {
            console.error('[Finance PWA] Failed to save to localStorage:', e);
        }

        // Відправляємо на сервер
        fetch('/api/settings/save/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify(settings)
        })
            .then(function (response) {
                if (!response.ok) throw new Error('Save failed');
                return response.json();
            })
            .then(function (data) {
                console.log('[Finance PWA] Settings saved:', data);
                showNotification('Налаштування збережено', 'success');
                closeSettings();
            })
            .catch(function (error) {
                console.error('[Finance PWA] Failed to save settings:', error);
                showNotification('Помилка збереження налаштувань', 'error');
            });
    }

    function loadSettings() {
        // Спочатку з localStorage
        try {
            const saved = localStorage.getItem('fin_settings');
            if (saved) {
                applySettings(JSON.parse(saved));
            }
        } catch (e) {
            console.error('[Finance PWA] Failed to load from localStorage:', e);
        }

        // Потім з сервера
        fetch('/api/settings/get/')
            .then(function (response) {
                if (!response.ok) throw new Error('Load failed');
                return response.json();
            })
            .then(function (settings) {
                applySettings(settings);
                // Оновлюємо localStorage
                try {
                    localStorage.setItem('fin_settings', JSON.stringify(settings));
                } catch (e) {
                    console.error('[Finance PWA] Failed to update localStorage:', e);
                }
            })
            .catch(function (error) {
                console.log('[Finance PWA] Using local settings only');
            });
    }

    function applySettings(settings) {
        const pushEnabled = document.getElementById('push-enabled');
        const pushSettingsContent = document.getElementById('push-settings-content');
        const pushDailyEnabled = document.getElementById('push-daily-enabled');
        const pushDailyTime = document.getElementById('push-daily-time');
        const pushWeeklyEnabled = document.getElementById('push-weekly-enabled');
        const pushWeeklyDay = document.getElementById('push-weekly-day');
        const dailyTimeField = document.getElementById('daily-time-field');
        const weeklyDayField = document.getElementById('weekly-day-field');

        if (pushEnabled) pushEnabled.checked = settings.push_enabled || false;
        if (pushSettingsContent) pushSettingsContent.hidden = !settings.push_enabled;
        if (pushDailyEnabled) pushDailyEnabled.checked = settings.push_daily_enabled || false;
        if (pushDailyTime) pushDailyTime.value = settings.push_daily_time || '20:00';
        if (pushWeeklyEnabled) pushWeeklyEnabled.checked = settings.push_weekly_enabled || false;
        if (pushWeeklyDay) pushWeeklyDay.value = String(settings.push_weekly_day || 1);
        var weeklyTime = document.getElementById('push-weekly-time');
        if (weeklyTime) weeklyTime.value = settings.push_weekly_time || '10:00';
        var healthAlerts = document.getElementById('push-health-alerts');
        if (healthAlerts) healthAlerts.checked = settings.push_health_alerts !== false;
        if (dailyTimeField) dailyTimeField.hidden = !settings.push_daily_enabled;
        if (weeklyDayField) weeklyDayField.hidden = !settings.push_weekly_enabled;
    }

    function showUpdateNotification() {
        if (confirm('Доступна нова версія додатку. Оновити зараз?')) {
            if (swRegistration && swRegistration.waiting) {
                swRegistration.waiting.postMessage({ type: 'SKIP_WAITING' });
                window.location.reload();
            }
        }
    }

    function showNotification(message, type) {
        // Проста toast notification
        const toast = document.createElement('div');
        toast.className = 'fin-toast fin-toast--' + (type || 'info');
        toast.textContent = message;
        document.body.appendChild(toast);

        requestAnimationFrame(function () {
            toast.classList.add('is-visible');
        });

        setTimeout(function () {
            toast.classList.remove('is-visible');
            setTimeout(function () {
                document.body.removeChild(toast);
            }, 300);
        }, 3000);
    }

    // ===== Утиліти =====
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    function urlBase64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding).replace(/\-/g, '+').replace(/_/g, '/');
        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);
        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    }

    function getVapidPublicKey() {
        // Реальний публічний VAPID-ключ передається з сервера (context processor
        // → base.html → window.FIN_VAPID_PUBLIC_KEY). Фолбек лишаємо порожнім,
        // щоб не намагатись підписатись із недійсним ключем.
        return (window.FIN_VAPID_PUBLIC_KEY || '').trim();
    }
})();
