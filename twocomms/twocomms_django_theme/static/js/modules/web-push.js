import { getCookie } from './shared.js';

const INSTALLATION_ID_KEY = 'twc-web-push-installation-id-v1';
const DISMISS_UNTIL_KEY = 'twc-web-push-dismissed-until';
const DEVICE_DISABLED_KEY = 'twc-web-push-device-disabled';
const PROMPT_IMPRESSIONS_KEY = 'twc-web-push-prompt-impressions';
const VISIT_COUNT_KEY = 'twc-web-push-visit-count';
const PAGE_VIEW_COUNT_KEY = 'twc-web-push-page-view-count';
const LAST_SEEN_AT_KEY = 'twc-web-push-last-seen-at';
const LAST_SYNC_AT_KEY = 'twc-web-push-last-sync-at';
const LAST_SYNC_AUTH_KEY = 'twc-web-push-last-sync-auth';
const SESSION_STARTED_AT_KEY = 'twc-web-push-session-started-at';
const SESSION_PROMPT_SHOWN_KEY = 'twc-web-push-session-prompt-shown';

const MAX_PROMPT_IMPRESSIONS = 4;
const MAX_OVERLAY_RETRIES = 4;
const PROMPT_PRIORITIES = {
  manual: 100,
  order_success: 80,
  cart: 70,
  engaged: 40,
};

let registerPromise = null;
let promptTimerId = null;
let scheduledPromptPriority = -1;
let profileControlsBound = false;

function getStorage(kind) {
  try {
    return kind === 'session' ? window.sessionStorage : window.localStorage;
  } catch (_) {
    return null;
  }
}

function storageGet(key, fallback = '', kind = 'local') {
  const storage = getStorage(kind);
  if (!storage) {
    return fallback;
  }
  try {
    const value = storage.getItem(key);
    return value === null ? fallback : value;
  } catch (_) {
    return fallback;
  }
}

function storageSet(key, value, kind = 'local') {
  const storage = getStorage(kind);
  if (!storage) {
    return;
  }
  try {
    storage.setItem(key, String(value));
  } catch (_) { }
}

function storageRemove(key, kind = 'local') {
  const storage = getStorage(kind);
  if (!storage) {
    return;
  }
  try {
    storage.removeItem(key);
  } catch (_) { }
}

function readNumber(key, kind = 'local', fallback = 0) {
  const value = parseInt(storageGet(key, '', kind), 10);
  return Number.isFinite(value) ? value : fallback;
}

function incrementNumber(key, kind = 'local') {
  const nextValue = readNumber(key, kind, 0) + 1;
  storageSet(key, nextValue, kind);
  return nextValue;
}

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

function readStrategy(config) {
  const strategy = config?.strategy || {};
  return {
    repeatVisitMin: Math.max(1, Number(strategy.repeatVisitMin || 2)),
    pageViewMin: Math.max(1, Number(strategy.pageViewMin || 3)),
    warmupMs: Math.max(5000, Number(strategy.warmupMs || 45000)),
    visitGapMs: Math.max(1800000, Number(strategy.visitGapMs || 21600000)),
    cartPromptDelayMs: Math.max(0, Number(strategy.cartPromptDelayMs || 4000)),
    orderSuccessPromptDelayMs: Math.max(0, Number(strategy.orderSuccessPromptDelayMs || 5000)),
    subscriptionSyncIntervalMs: Math.max(
      300000,
      Number(strategy.subscriptionSyncIntervalMs || 86400000)
    ),
  };
}

function createInstallationId() {
  const existing = storageGet(INSTALLATION_ID_KEY, '');
  if (existing) {
    return existing;
  }

  const generated = window.crypto && window.crypto.randomUUID
    ? window.crypto.randomUUID()
    : 'twc-' + Date.now() + '-' + Math.random().toString(36).slice(2, 12);
  storageSet(INSTALLATION_ID_KEY, generated);
  return generated;
}

function getPermissionState() {
  if (!('Notification' in window)) {
    return 'unsupported';
  }
  return Notification.permission;
}

function isDismissed() {
  return readNumber(DISMISS_UNTIL_KEY, 'local', 0) > Date.now();
}

function dismissPrompt(days = 21) {
  storageSet(DISMISS_UNTIL_KEY, Date.now() + days * 24 * 60 * 60 * 1000);
}

function clearDismissal() {
  storageRemove(DISMISS_UNTIL_KEY);
}

function isDeviceDisabled() {
  return storageGet(DEVICE_DISABLED_KEY, '0') === '1';
}

function setDeviceDisabled(disabled) {
  storageSet(DEVICE_DISABLED_KEY, disabled ? '1' : '0');
}

function hasPromptShownThisSession() {
  return storageGet(SESSION_PROMPT_SHOWN_KEY, '', 'session') !== '';
}

function markPromptShownThisSession(reason) {
  storageSet(SESSION_PROMPT_SHOWN_KEY, reason || '1', 'session');
}

function markPromptImpression() {
  incrementNumber(PROMPT_IMPRESSIONS_KEY);
}

function clearScheduledPrompt() {
  if (promptTimerId) {
    window.clearTimeout(promptTimerId);
    promptTimerId = null;
  }
  scheduledPromptPriority = -1;
}

function hasAnotherPromptOpen() {
  return Boolean(document.querySelector('[data-pwa-install-prompt]'));
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
    const serviceWorkerUrl = readConfig()?.serviceWorkerUrl || '/sw.js';
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

function userPreferenceSnapshot(config) {
  return config?.viewer?.preferences || {
    marketingEnabled: true,
    orderUpdatesEnabled: true,
  };
}

function markSuccessfulSync(config) {
  storageSet(LAST_SYNC_AT_KEY, Date.now());
  storageSet(
    LAST_SYNC_AUTH_KEY,
    config?.viewer?.isAuthenticated ? '1' : '0'
  );
}

function authStateChangedSinceLastSync(config) {
  const currentAuthState = config?.viewer?.isAuthenticated ? '1' : '0';
  return storageGet(LAST_SYNC_AUTH_KEY, '') !== currentAuthState;
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
      permission: getPermissionState(),
      preferences: userPreferenceSnapshot(config),
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
  setDeviceDisabled(false);
  markSuccessfulSync(config);
  dispatchPushStateChange(config);
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

async function syncGrantedSubscription(config, options = {}) {
  const { force = false, detailed = false } = options;
  const strategy = readStrategy(config);
  const permission = getPermissionState();

  if (permission !== 'granted') {
    dispatchPushStateChange(config);
    return detailed ? { synced: false, reason: 'permission' } : false;
  }

  if (!canUsePush()) {
    dispatchPushStateChange(config);
    return detailed ? { synced: false, reason: 'unsupported' } : false;
  }

  if (isDeviceDisabled()) {
    dispatchPushStateChange(config);
    return detailed ? { synced: false, reason: 'device_disabled' } : false;
  }

  const lastSyncAt = readNumber(LAST_SYNC_AT_KEY, 'local', 0);
  const syncIsFresh = lastSyncAt && (Date.now() - lastSyncAt) < strategy.subscriptionSyncIntervalMs;
  if (!force && syncIsFresh && !authStateChangedSinceLastSync(config)) {
    dispatchPushStateChange(config);
    return detailed ? { synced: false, reason: 'fresh' } : false;
  }

  try {
    await subscribeUser(config);
    return detailed ? { synced: true, reason: 'synced' } : true;
  } catch (_) {
    dispatchPushStateChange(config);
    return detailed ? { synced: false, reason: 'error' } : false;
  }
}

async function unsubscribeDevice(config) {
  const payload = {
    installation_id: createInstallationId(),
  };

  if (canUsePush()) {
    try {
      const registration = await ensureServiceWorker();
      const subscription = await registration.pushManager.getSubscription();
      if (subscription) {
        payload.endpoint = subscription.endpoint || '';
        try {
          await subscription.unsubscribe();
        } catch (_) { }
      }
    } catch (_) { }
  }

  if (config?.unsubscribeUrl) {
    try {
      await fetch(config.unsubscribeUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
          'X-Requested-With': 'XMLHttpRequest',
        },
        credentials: 'same-origin',
        body: JSON.stringify(payload),
      });
    } catch (_) { }
  }

  setDeviceDisabled(true);
  storageRemove(LAST_SYNC_AT_KEY);
  storageSet(
    LAST_SYNC_AUTH_KEY,
    config?.viewer?.isAuthenticated ? '1' : '0'
  );
  clearScheduledPrompt();
  removePromptCard();
  dispatchPushStateChange(config);
}

function removePromptCard() {
  const existing = document.querySelector('[data-web-push-prompt]');
  if (existing) {
    existing.remove();
  }
}

function updatePromptState({ title, message, eyebrow, tone = 'default' }) {
  const card = document.querySelector('[data-web-push-prompt]');
  if (!card) {
    return;
  }

  const titleNode = card.querySelector('[data-web-push-title]');
  const textNode = card.querySelector('[data-web-push-copy]');
  const eyebrowNode = card.querySelector('[data-web-push-eyebrow]');
  if (titleNode && title) {
    titleNode.textContent = title;
  }
  if (textNode) {
    textNode.textContent = message;
  }
  if (eyebrowNode && eyebrow) {
    eyebrowNode.textContent = eyebrow;
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

function trackWebPushMetric(eventName, extra = {}) {
  try {
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({
      event: eventName,
      web_push_event_name: eventName,
      browser_family: detectBrowserFamily(),
      operating_system: detectOperatingSystem(),
      device_type: detectDeviceType(),
      standalone: isStandalone(),
      permission: getPermissionState(),
      route_name: document.documentElement.getAttribute('data-route-name') || '',
      device_class: document.documentElement.getAttribute('data-device-class') || '',
      path: window.location.pathname,
      ...extra,
    });
  } catch (_) { }
}

function promptCopy(reason) {
  if (reason === 'order_success') {
    return {
      eyebrow: 'Після замовлення',
      title: 'Отримувати статус цього замовлення?',
      body: 'Увімкніть push, щоб бачити доставку, оновлення замовлення та важливі повідомлення без зайвих листів.',
      action: 'Увімкнути',
      benefits: ['Статус замовлення', 'Доставка', 'Без зайвих листів'],
    };
  }

  if (reason === 'cart') {
    return {
      eyebrow: 'Лише корисні сповіщення',
      title: 'Залишатися в курсі без зайвого шуму?',
      body: 'Покажемо статус замовлення, доставку та справді доречні оновлення тоді, коли вони вам потрібні.',
      action: 'Увімкнути',
      benefits: ['Статус замовлення', 'Доставка', 'Без спаму'],
    };
  }

  if (reason === 'manual') {
    return {
      eyebrow: 'Налаштування браузера',
      title: 'Налаштувати push-сповіщення',
      body: 'Увімкніть push у цьому браузері, щоб TwoComms міг надсилати статуси замовлень та важливі оновлення.',
      action: 'Продовжити',
      benefits: ['Цей браузер', 'Швидке увімкнення', 'Керується у профілі'],
    };
  }

  return {
    eyebrow: 'Для постійних гостей',
    title: 'Увімкнути push-сповіщення?',
    body: 'Отримуйте статуси замовлень, важливі оновлення та новини про дропи прямо в браузері.',
    action: 'Увімкнути',
    benefits: ['Статуси', 'Нові дропи', 'Без зайвого шуму'],
  };
}

function renderPromptBenefits(copy) {
  const benefits = Array.isArray(copy?.benefits) ? copy.benefits.filter(Boolean) : [];
  if (!benefits.length) {
    return '';
  }
  return `
    <div class="web-push-prompt__benefits" aria-hidden="true">
      ${benefits.map((item) => `<span class="web-push-prompt__benefit">${item}</span>`).join('')}
    </div>
  `;
}

function buildPromptCard(mode, reason) {
  const copy = promptCopy(reason);
  const wrapper = document.createElement('aside');
  wrapper.className = 'web-push-prompt';
  wrapper.setAttribute('data-web-push-prompt', '1');
  wrapper.setAttribute(
    'data-tone',
    mode === 'ios_install' ? 'install' : (mode === 'retry' ? 'warning' : 'default')
  );
  wrapper.setAttribute('role', 'dialog');
  wrapper.setAttribute('aria-live', 'polite');
  wrapper.setAttribute('aria-label', 'Налаштування push-сповіщень');

  if (mode === 'ios_install') {
    wrapper.innerHTML = `
      <div class="web-push-prompt__glow"></div>
      <div class="web-push-prompt__content">
        <div class="web-push-prompt__icon" aria-hidden="true">App</div>
        <div class="web-push-prompt__text">
          <span class="web-push-prompt__eyebrow" data-web-push-eyebrow>iPhone та iPad</span>
          <div class="web-push-prompt__title" data-web-push-title>Установіть TwoComms на екран Додому</div>
          <p class="web-push-prompt__copy" data-web-push-copy>
            На iPhone та iPad push працюють після встановлення TwoComms як вебзастосунку. Це займає кілька секунд і не потребує App Store.
          </p>
          <div class="web-push-prompt__steps" aria-hidden="true">
            <div class="web-push-prompt__step">
              <span class="web-push-prompt__step-index">1</span>
              <div class="web-push-prompt__step-copy">
                <strong>Відкрийте меню “Поділитися”</strong>
                <small>У Safari або в іншому браузері на iPhone/iPad.</small>
              </div>
            </div>
            <div class="web-push-prompt__step">
              <span class="web-push-prompt__step-index">2</span>
              <div class="web-push-prompt__step-copy">
                <strong>Натисніть “На екран Додому”</strong>
                <small>Потім відкрийте TwoComms з іконки та дозвольте системні push-сповіщення.</small>
              </div>
            </div>
          </div>
          <p class="web-push-prompt__meta">Після встановлення TwoComms відкриватиметься як окремий швидкий вебзастосунок.</p>
        </div>
        <div class="web-push-prompt__actions">
          <button type="button" class="web-push-prompt__btn web-push-prompt__btn--ghost" data-web-push-dismiss>
            Добре
          </button>
        </div>
      </div>
    `;
    return wrapper;
  }

  if (mode === 'retry') {
    wrapper.innerHTML = `
      <div class="web-push-prompt__glow"></div>
      <div class="web-push-prompt__content">
        <div class="web-push-prompt__icon" aria-hidden="true">Push</div>
        <div class="web-push-prompt__text">
          <span class="web-push-prompt__eyebrow" data-web-push-eyebrow>Повторне підключення</span>
          <div class="web-push-prompt__title" data-web-push-title>Push потребує повторної синхронізації</div>
          <p class="web-push-prompt__copy" data-web-push-copy>
            Системний дозвіл уже надано, але TwoComms не зміг оновити push-підписку для цього браузера. Повторіть підключення, щоб сповіщення працювали стабільно.
          </p>
          <div class="web-push-prompt__benefits" aria-hidden="true">
            <span class="web-push-prompt__benefit">Дозвіл уже є</span>
            <span class="web-push-prompt__benefit">Оновимо підписку</span>
            <span class="web-push-prompt__benefit">Без повторної установки</span>
          </div>
        </div>
        <div class="web-push-prompt__actions">
          <button type="button" class="web-push-prompt__btn web-push-prompt__btn--ghost" data-web-push-dismiss>
            Пізніше
          </button>
          <button type="button" class="web-push-prompt__btn web-push-prompt__btn--primary" data-web-push-enable>
            Повторити
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
        <span class="web-push-prompt__eyebrow" data-web-push-eyebrow>${copy.eyebrow}</span>
        <div class="web-push-prompt__title" data-web-push-title>${copy.title}</div>
        <p class="web-push-prompt__copy" data-web-push-copy>${copy.body}</p>
        ${renderPromptBenefits(copy)}
      </div>
      <div class="web-push-prompt__actions">
        <button type="button" class="web-push-prompt__btn web-push-prompt__btn--ghost" data-web-push-dismiss>
          Пізніше
        </button>
        <button type="button" class="web-push-prompt__btn web-push-prompt__btn--primary" data-web-push-enable>
          ${copy.action}
        </button>
      </div>
    </div>
  `;
  return wrapper;
}

function hasBlockingOverlay() {
  if (document.body?.classList.contains('modal-open')) {
    return true;
  }

  return Boolean(document.querySelector('.modal.show, .offcanvas.show, [aria-modal="true"]'));
}

function shouldShowPrompt(config, options = {}) {
  const { force = false, allowGranted = false } = options;
  if (!config || !config.enabled || !config.vapidPublicKey) {
    return false;
  }
  if (document.documentElement.hasAttribute('data-no-web-push')) {
    return false;
  }
  if (document.visibilityState === 'hidden') {
    return false;
  }
  if (hasAnotherPromptOpen()) {
    return false;
  }
  const permission = getPermissionState();
  if (!allowGranted && permission !== 'default') {
    return false;
  }
  if (allowGranted && permission !== 'default' && permission !== 'granted') {
    return false;
  }
  if (!force && isDismissed()) {
    return false;
  }
  if (!force && isDeviceDisabled()) {
    return false;
  }
  if (!force && hasPromptShownThisSession()) {
    return false;
  }
  if (!force && readNumber(PROMPT_IMPRESSIONS_KEY, 'local', 0) >= MAX_PROMPT_IMPRESSIONS) {
    return false;
  }
  return true;
}

function showPromptCard(config, options = {}) {
  const { mode = 'default', reason = 'engaged', force = false, retryCount = 0 } = options;
  const allowGranted = mode === 'retry';
  if (!force && hasBlockingOverlay()) {
    if (retryCount < MAX_OVERLAY_RETRIES) {
      schedulePrompt(config, reason, 1800, {
        mode,
        force,
        retryCount: retryCount + 1,
      });
    }
    return false;
  }

  if (!shouldShowPrompt(config, { force, allowGranted })) {
    dispatchPushStateChange(config);
    return false;
  }

  clearScheduledPrompt();
  removePromptCard();
  markPromptShownThisSession(reason);
  markPromptImpression();

  const card = buildPromptCard(mode, reason);
  document.body.appendChild(card);
  trackWebPushMetric('web_push_prompt_shown', { mode, reason });
  dispatchPushStateChange(config);

  const dismissButton = card.querySelector('[data-web-push-dismiss]');
  dismissButton?.addEventListener('click', () => {
    dismissPrompt(mode === 'ios_install' ? 7 : 21);
    trackWebPushMetric('web_push_prompt_dismissed', { mode, reason });
    removePromptCard();
    dispatchPushStateChange(config);
  });

  const enableButton = card.querySelector('[data-web-push-enable]');
  enableButton?.addEventListener('click', async () => {
    enableButton.disabled = true;
    const hasGrantedPermission = getPermissionState() === 'granted';

    updatePromptState({
      title: hasGrantedPermission ? 'Відновлюємо push…' : 'Підключаємо push…',
      message: hasGrantedPermission
        ? 'Системний дозвіл уже є. Оновлюємо підписку TwoComms для цього браузера.'
        : 'Запитуємо дозвіл браузера. Системне вікно зʼявиться лише один раз.',
      eyebrow: hasGrantedPermission ? 'Повторна синхронізація' : 'Системний доступ',
      tone: 'loading',
    });

    try {
      let permission = getPermissionState();
      if (permission !== 'granted') {
        permission = await Notification.requestPermission();
      }

      trackWebPushMetric('web_push_permission_result', { mode, reason, permission });

      if (permission !== 'granted') {
        dismissPrompt(45);
        updatePromptState({
          title: 'Доступ не надано',
          message: 'Ви завжди можете змінити це в налаштуваннях браузера, коли будете готові.',
          eyebrow: 'Безпека браузера',
          tone: 'warning',
        });
        maybeNotify('Push-сповіщення не увімкнено.', 'info');
        dispatchPushStateChange(config);
        window.setTimeout(removePromptCard, 4200);
        return;
      }

      const syncResult = await syncGrantedSubscription(config, { force: true, detailed: true });
      if (!syncResult.synced) {
        throw new Error('Не вдалося зберегти push-підписку.');
      }

      trackWebPushMetric('web_push_subscribe_success', { mode, reason });
      updatePromptState({
        title: 'Push увімкнено',
        message: 'Нові повідомлення про замовлення та важливі оновлення тепер приходитимуть у браузер автоматично.',
        eyebrow: 'Готово',
        tone: 'success',
      });
      maybeNotify('Push-сповіщення успішно увімкнено.', 'success');
      dispatchPushStateChange(config);
      window.setTimeout(removePromptCard, 2400);
    } catch (error) {
      trackWebPushMetric('web_push_subscribe_error', {
        mode,
        reason,
        error_message: error?.message || 'unknown_error',
      });
      updatePromptState({
        title: 'Не вдалося завершити налаштування',
        message: error?.message || 'Спробуйте ще раз або перевірте налаштування браузера.',
        eyebrow: 'Потрібна перевірка',
        tone: 'warning',
      });
      maybeNotify(error?.message || 'Не вдалося налаштувати push-сповіщення.', 'error');
      enableButton.disabled = false;
      dispatchPushStateChange(config);
    }
  });

  return true;
}

function schedulePrompt(config, reason, delayMs, options = {}) {
  const priority = PROMPT_PRIORITIES[reason] || 0;
  if (promptTimerId && priority < scheduledPromptPriority) {
    return false;
  }

  clearScheduledPrompt();
  scheduledPromptPriority = priority;
  promptTimerId = window.setTimeout(() => {
    promptTimerId = null;
    scheduledPromptPriority = -1;
    showPromptCard(config, {
      mode: options.mode || (isIOS() && !isStandalone() ? 'ios_install' : 'default'),
      reason,
      force: options.force === true,
      retryCount: Number(options.retryCount || 0),
    });
  }, Math.max(0, delayMs));

  return true;
}

function readEngagement(config) {
  const strategy = readStrategy(config);
  const now = Date.now();
  const lastSeenAt = readNumber(LAST_SEEN_AT_KEY, 'local', 0);
  if (!storageGet(SESSION_STARTED_AT_KEY, '', 'session')) {
    storageSet(SESSION_STARTED_AT_KEY, now, 'session');
  }

  if (!lastSeenAt || (now - lastSeenAt) > strategy.visitGapMs) {
    incrementNumber(VISIT_COUNT_KEY);
  }

  storageSet(LAST_SEEN_AT_KEY, now);
  incrementNumber(PAGE_VIEW_COUNT_KEY);
}

function engagementSnapshot(config) {
  const sessionStartedAt = readNumber(SESSION_STARTED_AT_KEY, 'session', Date.now());
  return {
    visits: readNumber(VISIT_COUNT_KEY, 'local', 0),
    pageViews: readNumber(PAGE_VIEW_COUNT_KEY, 'local', 0),
    sessionMs: Math.max(0, Date.now() - sessionStartedAt),
    strategy: readStrategy(config),
  };
}

function isOrderSuccessPage() {
  return Boolean(document.getElementById('purchase-payload'));
}

function maybeScheduleEngagedPrompt(config) {
  if (!shouldShowPrompt(config)) {
    return;
  }

  const snapshot = engagementSnapshot(config);
  if (snapshot.visits < snapshot.strategy.repeatVisitMin) {
    return;
  }
  if (snapshot.pageViews < snapshot.strategy.pageViewMin) {
    return;
  }

  const promptDelay = Math.max(1000, Number(config.promptDelayMs || 12000));
  const remainingWarmupMs = Math.max(0, snapshot.strategy.warmupMs - snapshot.sessionMs);
  schedulePrompt(config, 'engaged', Math.max(promptDelay, remainingWarmupMs));
}

function pushProfileNodes() {
  const root = document.querySelector('[data-web-push-profile]');
  if (!root) {
    return null;
  }
  return {
    root,
    status: root.querySelector('[data-web-push-profile-status]'),
    detail: root.querySelector('[data-web-push-profile-detail]'),
    enable: root.querySelector('[data-web-push-profile-enable]'),
    disable: root.querySelector('[data-web-push-profile-disable]'),
  };
}

function profileStateText(config) {
  const permission = getPermissionState();
  if (permission === 'denied') {
    return {
      state: 'denied',
      status: 'Push заблоковані у браузері',
      detail: 'Щоб увімкнути їх знову, дозвольте сповіщення для цього сайту в налаштуваннях браузера.',
      canEnable: false,
      canDisable: false,
      enableLabel: 'Недоступно',
    };
  }

  if (permission === 'granted' && !isDeviceDisabled()) {
    return {
      state: 'enabled',
      status: 'Push увімкнено на цьому пристрої',
      detail: 'Цей браузер отримуватиме масові кампанії та персональні оновлення, коли вони будуть підключені.',
      canEnable: false,
      canDisable: true,
      enableLabel: 'Увімкнено',
    };
  }

  if (permission === 'granted' && isDeviceDisabled()) {
    return {
      state: 'device_disabled',
      status: 'Push вимкнено для цього браузера',
      detail: 'Системний дозвіл у браузері залишився, але сайт більше не використовує цю підписку, доки ви не ввімкнете її знову.',
      canEnable: true,
      canDisable: false,
      enableLabel: 'Увімкнути знову',
    };
  }

  if (isIOS() && !isStandalone()) {
    return {
      state: 'ios_install',
      status: 'На iPhone/iPad спочатку встановіть TwoComms на екран Додому',
      detail: 'Після цього сайт відкриватиметься як вебзастосунок TwoComms, і вже з нього можна буде дозволити системні push-сповіщення для цього пристрою.',
      canEnable: true,
      canDisable: false,
      enableLabel: 'Як встановити на iPhone/iPad',
    };
  }

  if (!canUsePush()) {
    return {
      state: 'unsupported',
      status: 'У цьому режимі браузера Web Push недоступний',
      detail: 'Спробуйте сучасний браузер з HTTPS та підтримкою service worker, щоб увімкнути сповіщення.',
      canEnable: false,
      canDisable: false,
      enableLabel: 'Недоступно',
    };
  }

  return {
    state: 'default',
    status: 'Push ще не увімкнено в цьому браузері',
    detail: 'Увімкніть сповіщення тут, щоб отримувати статуси замовлень, важливі оновлення та релевантні пропозиції.',
    canEnable: true,
    canDisable: false,
    enableLabel: 'Увімкнути в цьому браузері',
  };
}

function renderProfileControls(config) {
  const nodes = pushProfileNodes();
  if (!nodes) {
    return;
  }

  const view = profileStateText(config);
  nodes.root.setAttribute('data-state', view.state);

  if (nodes.status) {
    nodes.status.textContent = view.status;
  }
  if (nodes.detail) {
    nodes.detail.textContent = view.detail;
  }
  if (nodes.enable) {
    nodes.enable.textContent = view.enableLabel;
    nodes.enable.hidden = !view.canEnable;
    nodes.enable.disabled = !view.canEnable;
  }
  if (nodes.disable) {
    nodes.disable.hidden = !view.canDisable;
    nodes.disable.disabled = !view.canDisable;
  }
}

function dispatchPushStateChange(config) {
  renderProfileControls(config);
  try {
    document.dispatchEvent(new CustomEvent('twc:web-push-state', {
      detail: {
        permission: getPermissionState(),
        deviceDisabled: isDeviceDisabled(),
        isStandalone: isStandalone(),
      },
    }));
  } catch (_) { }
}

async function handleManualEnable(config) {
  const permission = getPermissionState();

  if (permission === 'granted') {
    const syncResult = await syncGrantedSubscription(config, { force: true, detailed: true });
    if (syncResult.synced) {
      maybeNotify('Push-сповіщення увімкнено для цього браузера.', 'success');
    } else if (syncResult.reason === 'error' && canUsePush() && !isDeviceDisabled()) {
      trackWebPushMetric('web_push_manual_sync_error', { reason: 'manual' });
      showPromptCard(config, {
        mode: 'retry',
        reason: 'manual',
        force: true,
      });
    }
    dispatchPushStateChange(config);
    return;
  }

  if (permission === 'denied') {
    maybeNotify('Push вже заблоковані в налаштуваннях браузера.', 'info');
    dispatchPushStateChange(config);
    return;
  }

  showPromptCard(config, {
    mode: isIOS() && !isStandalone() ? 'ios_install' : 'default',
    reason: 'manual',
    force: true,
  });
}

function bindProfileControls(config) {
  if (profileControlsBound) {
    renderProfileControls(config);
    return;
  }

  const nodes = pushProfileNodes();
  if (!nodes) {
    return;
  }

  profileControlsBound = true;
  nodes.enable?.addEventListener('click', (event) => {
    event.preventDefault();
    handleManualEnable(config).catch(() => undefined);
  });
  nodes.disable?.addEventListener('click', (event) => {
    event.preventDefault();
    unsubscribeDevice(config)
      .then(() => maybeNotify('Push-сповіщення для цього браузера вимкнено.', 'success'))
      .catch(() => maybeNotify('Не вдалося вимкнути push-сповіщення.', 'error'));
  });
  renderProfileControls(config);
}

function bindIntentSignals(config) {
  document.addEventListener('cartUpdated', (event) => {
    const detail = event?.detail || {};
    if (detail.action !== 'add' || !shouldShowPrompt(config)) {
      return;
    }
    schedulePrompt(
      config,
      'cart',
      readStrategy(config).cartPromptDelayMs
    );
  });

  document.addEventListener('click', (event) => {
    const toggle = event.target.closest('[data-web-push-open]');
    if (!toggle) {
      return;
    }
    event.preventDefault();
    handleManualEnable(config).catch(() => undefined);
  });
}

async function bootWebPush(config) {
  if (!config || !config.enabled || !config.vapidPublicKey) {
    return;
  }

  readEngagement(config);
  bindProfileControls(config);
  bindIntentSignals(config);
  dispatchPushStateChange(config);

  if (getPermissionState() === 'granted') {
    const profilePanelPresent = Boolean(document.querySelector('[data-web-push-profile]'));
    const syncResult = await syncGrantedSubscription(config, {
      force: profilePanelPresent,
      detailed: true,
    });

    if (syncResult.reason === 'error' && canUsePush() && !isDeviceDisabled()) {
      trackWebPushMetric('web_push_boot_sync_error', {
        reason: 'manual',
        profile_panel_present: profilePanelPresent,
      });
      showPromptCard(config, {
        mode: 'retry',
        reason: 'manual',
        force: true,
      });
    }

    return;
  }

  if (getPermissionState() !== 'default') {
    return;
  }

  if (isOrderSuccessPage()) {
    schedulePrompt(
      config,
      'order_success',
      readStrategy(config).orderSuccessPromptDelayMs
    );
    return;
  }

  maybeScheduleEngagedPrompt(config);
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
