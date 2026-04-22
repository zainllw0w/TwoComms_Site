import { getCookie } from './shared.js';

const INSTALLATION_ID_KEY = 'twc-web-push-installation-id-v1';
const DISMISS_UNTIL_KEY = 'twc-web-push-dismissed-until';

let registerPromise = null;

function readConfig() {
  const node = document.getElementById('web-push-config');
  if (!node) {
    return null;
  }

  try {
    return JSON.parse(node.textContent || '{}');
  } catch (_) {
    return null;
  }
}

function createInstallationId() {
  try {
    const existing = window.localStorage.getItem(INSTALLATION_ID_KEY);
    if (existing) {
      return existing;
    }

    const generated = window.crypto && window.crypto.randomUUID
      ? window.crypto.randomUUID()
      : 'twc-' + Date.now() + '-' + Math.random().toString(36).slice(2, 12);

    window.localStorage.setItem(INSTALLATION_ID_KEY, generated);
    return generated;
  } catch (_) {
    return 'twc-' + Date.now();
  }
}

function isDismissed() {
  try {
    const until = parseInt(window.localStorage.getItem(DISMISS_UNTIL_KEY) || '0', 10);
    return Number.isFinite(until) && until > Date.now();
  } catch (_) {
    return false;
  }
}

function dismissPrompt(days = 21) {
  try {
    window.localStorage.setItem(
      DISMISS_UNTIL_KEY,
      String(Date.now() + days * 24 * 60 * 60 * 1000)
    );
  } catch (_) { }
}

function clearDismissal() {
  try {
    window.localStorage.removeItem(DISMISS_UNTIL_KEY);
  } catch (_) { }
}

function detectDeviceType() {
  const width = Math.min(window.innerWidth || 0, window.screen?.width || 0) || window.innerWidth || 0;
  const ua = navigator.userAgent || '';
  if (/ipad|tablet/i.test(ua) || (width >= 768 && width <= 1180 && /mobile/i.test(ua))) {
    return 'tablet';
  }
  if (/mobi|iphone|android/i.test(ua) || width < 768) {
    return 'mobile';
  }
  return 'desktop';
}

function detectBrowserFamily() {
  const ua = navigator.userAgent || '';
  if (/edg/i.test(ua)) return 'Edge';
  if (/firefox/i.test(ua)) return 'Firefox';
  if (/chrome|crios/i.test(ua) && !/edg/i.test(ua)) return 'Chrome';
  if (/safari/i.test(ua) && !/chrome|crios|android/i.test(ua)) return 'Safari';
  return 'Unknown';
}

function detectOperatingSystem() {
  const ua = navigator.userAgent || '';
  if (/iphone|ipad|ipod/i.test(ua)) return 'iOS';
  if (/android/i.test(ua)) return 'Android';
  if (/mac os x/i.test(ua)) return 'macOS';
  if (/windows/i.test(ua)) return 'Windows';
  if (/linux/i.test(ua)) return 'Linux';
  return 'Unknown';
}

function isIOS() {
  return /iphone|ipad|ipod/i.test(navigator.userAgent || '');
}

function isStandalone() {
  try {
    return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
  } catch (_) {
    return window.navigator.standalone === true;
  }
}

function canUsePush() {
  return (
    window.isSecureContext &&
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window
  );
}

function getCsrfToken() {
  return (
    getCookie('csrftoken') ||
    document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
    document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
    ''
  );
}

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);

  for (let index = 0; index < rawData.length; index += 1) {
    outputArray[index] = rawData.charCodeAt(index);
  }

  return outputArray;
}

async function ensureServiceWorker() {
  if (!registerPromise) {
    const serviceWorkerUrl = readConfig()?.serviceWorkerUrl || '/static/sw.js';
    registerPromise = navigator.serviceWorker.register(serviceWorkerUrl, {
      scope: '/',
      updateViaCache: 'none',
    }).catch((error) => {
      registerPromise = null;
      throw error;
    });
  }

  return registerPromise;
}

async function syncSubscription(config, subscription) {
  const payload = {
    subscription: subscription.toJSON(),
    installation_id: createInstallationId(),
    language: navigator.language || '',
    timezone: Intl.DateTimeFormat?.().resolvedOptions?.().timeZone || '',
    browser_family: detectBrowserFamily(),
    operating_system: detectOperatingSystem(),
    device_type: detectDeviceType(),
    user_agent: navigator.userAgent || '',
    last_seen_path: window.location.pathname + window.location.search,
    metadata: {
      standalone: isStandalone(),
      permission: Notification.permission,
    },
  };

  const response = await fetch(config.subscribeUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken(),
      'X-Requested-With': 'XMLHttpRequest',
    },
    credentials: 'same-origin',
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error('Не вдалося зберегти push-підписку.');
  }

  clearDismissal();
  return response.json().catch(() => ({}));
}

async function subscribeUser(config) {
  const registration = await ensureServiceWorker();
  let subscription = await registration.pushManager.getSubscription();

  if (!subscription) {
    subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(config.vapidPublicKey),
    });
  }

  await syncSubscription(config, subscription);
  return subscription;
}

function removePromptCard() {
  const existing = document.querySelector('[data-web-push-prompt]');
  if (existing) {
    existing.remove();
  }
}

function updatePromptState(message, tone = 'default') {
  const card = document.querySelector('[data-web-push-prompt]');
  if (!card) {
    return;
  }

  const textNode = card.querySelector('[data-web-push-copy]');
  if (textNode) {
    textNode.textContent = message;
  }
  card.setAttribute('data-tone', tone);
}

function maybeNotify(message, type = 'info') {
  if (typeof window.showNotification === 'function') {
    try {
      window.showNotification(message, type);
    } catch (_) { }
  }
}

function buildPromptCard(mode) {
  const wrapper = document.createElement('aside');
  wrapper.className = 'web-push-prompt';
  wrapper.setAttribute('data-web-push-prompt', '1');
  wrapper.setAttribute('data-tone', mode === 'ios_install' ? 'install' : 'default');

  if (mode === 'ios_install') {
    wrapper.innerHTML = `
      <div class="web-push-prompt__glow"></div>
      <div class="web-push-prompt__content">
        <div class="web-push-prompt__icon" aria-hidden="true">Push</div>
        <div class="web-push-prompt__text">
          <div class="web-push-prompt__title">Push-сповіщення на iPhone/iPad</div>
          <p class="web-push-prompt__copy" data-web-push-copy>
            Додайте TwoComms на домашній екран, а потім відкрийте сайт як вебзастосунок, щоб увімкнути системні push-сповіщення.
          </p>
        </div>
        <div class="web-push-prompt__actions">
          <button type="button" class="web-push-prompt__btn web-push-prompt__btn--ghost" data-web-push-dismiss>
            Зрозуміло
          </button>
        </div>
      </div>
    `;
    return wrapper;
  }

  wrapper.innerHTML = `
    <div class="web-push-prompt__glow"></div>
    <div class="web-push-prompt__content">
      <div class="web-push-prompt__icon" aria-hidden="true">Push</div>
      <div class="web-push-prompt__text">
        <div class="web-push-prompt__title">Увімкнути push-сповіщення?</div>
        <p class="web-push-prompt__copy" data-web-push-copy>
          Отримуйте нові дропи, важливі оновлення та спецпропозиції TwoComms прямо в браузері.
        </p>
      </div>
      <div class="web-push-prompt__actions">
        <button type="button" class="web-push-prompt__btn web-push-prompt__btn--ghost" data-web-push-dismiss>
          Пізніше
        </button>
        <button type="button" class="web-push-prompt__btn web-push-prompt__btn--primary" data-web-push-enable>
          Увімкнути
        </button>
      </div>
    </div>
  `;
  return wrapper;
}

function showPromptCard(config, mode) {
  removePromptCard();
  const card = buildPromptCard(mode);
  document.body.appendChild(card);

  const dismissButton = card.querySelector('[data-web-push-dismiss]');
  dismissButton?.addEventListener('click', () => {
    dismissPrompt(mode === 'ios_install' ? 30 : 21);
    removePromptCard();
  });

  const enableButton = card.querySelector('[data-web-push-enable]');
  enableButton?.addEventListener('click', async () => {
    enableButton.disabled = true;
    updatePromptState('Запитуємо дозвіл браузера…', 'loading');

    try {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        dismissPrompt(45);
        updatePromptState('Дозвіл не надано. Ви завжди можете змінити це в налаштуваннях браузера.', 'warning');
        maybeNotify('Push-сповіщення не увімкнено.', 'info');
        setTimeout(removePromptCard, 4200);
        return;
      }

      await subscribeUser(config);
      updatePromptState('Push-сповіщення увімкнено. Нові повідомлення прийдуть у браузер автоматично.', 'success');
      maybeNotify('Push-сповіщення успішно увімкнено.', 'success');
      setTimeout(removePromptCard, 2400);
    } catch (error) {
      updatePromptState(error?.message || 'Не вдалося налаштувати push-сповіщення.', 'warning');
      maybeNotify(error?.message || 'Не вдалося налаштувати push-сповіщення.', 'error');
      enableButton.disabled = false;
    }
  });
}

function shouldShowPrompt() {
  if (document.documentElement.hasAttribute('data-no-web-push')) {
    return false;
  }
  if (document.visibilityState === 'hidden') {
    return false;
  }
  if (isDismissed()) {
    return false;
  }
  return true;
}

async function bootWebPush(config) {
  if (!config || !config.enabled || !config.vapidPublicKey) {
    return;
  }

  if (!window.isSecureContext || !('serviceWorker' in navigator)) {
    return;
  }

  if (Notification.permission === 'granted' && canUsePush()) {
    try {
      await subscribeUser(config);
    } catch (_) { }
    return;
  }

  if (Notification.permission !== 'default' || !shouldShowPrompt()) {
    return;
  }

  const promptDelay = Math.max(1500, Number(config.promptDelayMs || 12000));
  window.setTimeout(() => {
    if (!shouldShowPrompt()) {
      return;
    }

    if (isIOS() && !isStandalone()) {
      showPromptCard(config, 'ios_install');
      return;
    }

    if (!canUsePush()) {
      return;
    }

    showPromptCard(config, 'default');
  }, promptDelay);
}

export function initWebPush() {
  const config = readConfig();
  if (!config) {
    return;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      bootWebPush(config).catch(() => undefined);
    }, { once: true });
    return;
  }

  bootWebPush(config).catch(() => undefined);
}
