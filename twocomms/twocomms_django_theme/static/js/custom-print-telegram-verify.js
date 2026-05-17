/**
 * custom-print-telegram-verify.js
 *
 * UI-керування верифікацією Telegram-контакту:
 *  - відкриває модалку коли користувач натискає «Підтвердити Telegram через бота»;
 *  - стартує сесію через POST /custom-print/telegram-verify/start/;
 *  - відкриває deep-link бота і поллить статус кожні 2с до 5 хв;
 *  - при success автозаповнює поле контакту і показує бейдж;
 *  - при cancel/expire — повертає до стану intro або показує помилку.
 *
 * Залежить від: куки `csrftoken`, наявності елементів за data-атрибутами в шаблоні
 * pages/custom_print.html.
 */

(function () {
  "use strict";

  const ENDPOINTS = {
    start: "/custom-print/telegram-verify/start/",
    status: "/custom-print/telegram-verify/status/",
    cancel: "/custom-print/telegram-verify/cancel/",
  };

  const POLL_INTERVAL_MS = 2200;
  const TTL_FALLBACK_SECONDS = 5 * 60;

  function getCsrfToken() {
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  async function postJSON(url, payload) {
    const response = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
        "X-Requested-With": "XMLHttpRequest",
      },
      body: JSON.stringify(payload || {}),
    });
    let data = null;
    try {
      data = await response.json();
    } catch (e) {
      data = null;
    }
    return { ok: response.ok, status: response.status, data };
  }

  async function getJSON(url) {
    const response = await fetch(url, {
      method: "GET",
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });
    let data = null;
    try {
      data = await response.json();
    } catch (e) {
      data = null;
    }
    return { ok: response.ok, status: response.status, data };
  }

  function safeNotify(message, type) {
    if (typeof window.showNotification === "function") {
      try {
        window.showNotification(message, type || "info");
      } catch (e) {
        /* noop */
      }
    }
  }

  // ── DOM init ──
  function init() {
    const verifyShell = document.querySelector("[data-tg-verify-shell]");
    const trigger = document.querySelector("[data-tg-verify-trigger]");
    const modal = document.querySelector("[data-tg-verify-modal]");
    if (!verifyShell || !trigger || !modal) return;

    // ─── Portal: переносим модалку в <body> чтобы position: fixed
    // работал относительно viewport (родительские transform/perspective
    // ломают fixed → элемент привязывается к ближайшему transformed-предку).
    if (modal.parentElement !== document.body) {
      document.body.appendChild(modal);
    }

    const screens = {
      intro: modal.querySelector('[data-tg-verify-screen="intro"]'),
      waiting: modal.querySelector('[data-tg-verify-screen="waiting"]'),
      success: modal.querySelector('[data-tg-verify-screen="success"]'),
      error: modal.querySelector('[data-tg-verify-screen="error"]'),
    };
    const successMeta = modal.querySelector("[data-tg-verify-success-meta]");
    const errorTitle = modal.querySelector("[data-tg-verify-error-title]");
    const errorMessage = modal.querySelector("[data-tg-verify-error-message]");
    const timerEl = modal.querySelector("[data-tg-verify-timer]");
    const verifyState = verifyShell.querySelector("[data-tg-verify-state]");
    const verifyStateMeta = verifyShell.querySelector("[data-tg-verify-state-meta]");
    const verifyStateTitle = verifyShell.querySelector("[data-tg-verify-state-title]");
    const verifyStateReset = verifyShell.querySelector("[data-tg-verify-reset]");
    const contactValueInput = document.querySelector("[data-contact-value-input]");
    const contactChannelList = document.querySelector("[data-contact-channel-list]");
    const nameInput = document.querySelector("[data-name-input]");

    // Hidden поля для додавання у форму при сабміті ліда
    const hiddenInputs = ensureHiddenInputs();

    let session = null; // {token, deep_link_url, deep_link_app, expires_at, ttl_seconds}
    let pollHandle = null;
    let timerHandle = null;
    let verified = null;

    function ensureHiddenInputs() {
      const form = document.getElementById("customPrintConfiguratorForm");
      if (!form) return null;
      function getOrCreate(name) {
        let input = form.querySelector(`input[name="${name}"]`);
        if (!input) {
          input = document.createElement("input");
          input.type = "hidden";
          input.name = name;
          form.appendChild(input);
        }
        return input;
      }
      return {
        token: getOrCreate("telegram_verification_token"),
        userId: getOrCreate("telegram_verified_user_id"),
        username: getOrCreate("telegram_verified_username"),
        phone: getOrCreate("telegram_verified_phone"),
        firstName: getOrCreate("telegram_verified_first_name"),
        lastName: getOrCreate("telegram_verified_last_name"),
      };
    }

    function showScreen(name) {
      Object.entries(screens).forEach(([key, el]) => {
        if (!el) return;
        el.hidden = key !== name;
      });
    }

    function openModal() {
      modal.hidden = false;
      // Force reflow so that transition plays
      // eslint-disable-next-line no-unused-expressions
      modal.offsetWidth;
      modal.classList.add("is-visible");
      document.body.style.overflow = "hidden";
    }

    function closeModal() {
      modal.classList.remove("is-visible");
      document.body.style.overflow = "";
      // Залишаємо короткий fade
      setTimeout(() => {
        if (!modal.classList.contains("is-visible")) modal.hidden = true;
      }, 220);
    }

    function isChannelTelegram() {
      // Конфігуратор використовує STATE.contact.channel, але читати його безпечно тільки
      // через клас .is-active в чіпсах.
      if (!contactChannelList) return false;
      const active = contactChannelList.querySelector("[data-choice-value].is-active");
      return active && active.dataset.choiceValue === "telegram";
    }

    function updateShellVisibility() {
      const shouldShow = isChannelTelegram();
      verifyShell.hidden = !shouldShow;
      if (!shouldShow) {
        // Якщо канал змінили — скидаємо verified-стан, бо контакт уже інший
        if (verified) resetVerified({ silent: true });
      }
    }

    function startTimer(ttlSeconds) {
      if (timerHandle) clearInterval(timerHandle);
      let remaining = Math.max(1, ttlSeconds || TTL_FALLBACK_SECONDS);
      function paint() {
        if (!timerEl) return;
        const m = Math.floor(remaining / 60).toString().padStart(2, "0");
        const s = (remaining % 60).toString().padStart(2, "0");
        timerEl.textContent = `${m}:${s}`;
      }
      paint();
      timerHandle = setInterval(() => {
        remaining -= 1;
        if (remaining <= 0) {
          clearInterval(timerHandle);
          timerHandle = null;
          paint();
          handleExpired();
          return;
        }
        paint();
      }, 1000);
    }

    function stopTimer() {
      if (timerHandle) clearInterval(timerHandle);
      timerHandle = null;
    }

    function startPolling() {
      stopPolling();
      pollHandle = setInterval(pollStatus, POLL_INTERVAL_MS);
    }

    function stopPolling() {
      if (pollHandle) clearInterval(pollHandle);
      pollHandle = null;
    }

    async function pollStatus() {
      if (!session || !session.token) return;
      try {
        const url = `${ENDPOINTS.status}?token=${encodeURIComponent(session.token)}`;
        const { ok, data } = await getJSON(url);
        if (!ok || !data) return;
        if (data.status === "verified" && data.verified) {
          handleVerified(data);
          return;
        }
        if (data.status === "expired") {
          handleExpired();
          return;
        }
        if (data.status === "cancelled") {
          handleCancelled();
          return;
        }
      } catch (e) {
        // Тихо ігноруємо мережеві помилки під час поллінгу
      }
    }

    async function handleStart() {
      try {
        trigger.disabled = true;
        const namePayload = nameInput && nameInput.value ? nameInput.value : "";
        const { ok, data } = await postJSON(ENDPOINTS.start, { name: namePayload });
        if (!ok || !data || !data.ok) {
          throw new Error((data && data.error) || "Не вдалося створити сесію верифікації.");
        }
        session = data;
        if (hiddenInputs && hiddenInputs.token) {
          hiddenInputs.token.value = data.token || "";
        }
        // Відкриваємо бота. Спершу спробуємо tg:// (мобільні), якщо ні — http
        try {
          window.open(data.deep_link_url, "_blank", "noopener,noreferrer");
        } catch (e) {
          location.href = data.deep_link_url;
        }
        showScreen("waiting");
        startTimer(data.ttl_seconds);
        startPolling();
      } catch (err) {
        showScreen("error");
        if (errorTitle) errorTitle.textContent = "Не вдалося створити сесію";
        if (errorMessage) errorMessage.textContent = err.message || "Спробуйте ще раз або введіть @username вручну.";
      } finally {
        trigger.disabled = false;
      }
    }

    function handleVerified(data) {
      stopPolling();
      stopTimer();
      verified = {
        username: data.telegram_username || "",
        phone: data.phone || "",
        firstName: data.telegram_first_name || "",
        lastName: data.telegram_last_name || "",
        userId: data.telegram_user_id || null,
      };

      // Заповнюємо форму
      if (contactValueInput && verified.username) {
        const handle = `@${verified.username.replace(/^@+/, "")}`;
        contactValueInput.value = handle;
        // dispatch input event — щоб конфігуратор зберіг у STATE
        contactValueInput.dispatchEvent(new Event("input", { bubbles: true }));
        contactValueInput.dispatchEvent(new Event("change", { bubbles: true }));
      }
      if (hiddenInputs) {
        if (hiddenInputs.userId) hiddenInputs.userId.value = verified.userId || "";
        if (hiddenInputs.username) hiddenInputs.username.value = verified.username || "";
        if (hiddenInputs.phone) hiddenInputs.phone.value = verified.phone || "";
        if (hiddenInputs.firstName) hiddenInputs.firstName.value = verified.firstName || "";
        if (hiddenInputs.lastName) hiddenInputs.lastName.value = verified.lastName || "";
      }

      // UI
      const meta = [];
      if (verified.username) meta.push(`@${verified.username.replace(/^@+/, "")}`);
      if (verified.phone) meta.push(verified.phone);
      const metaText = meta.join(" · ");
      if (successMeta) successMeta.textContent = metaText || "Контакт отримано.";
      if (verifyStateTitle) verifyStateTitle.textContent = "Telegram підтверджено";
      if (verifyStateMeta) verifyStateMeta.textContent = metaText || "Контакт отримано.";
      if (verifyState) verifyState.hidden = false;
      trigger.hidden = true;

      showScreen("success");
      safeNotify("Telegram підтверджено — продовжуйте оформлення.", "success");
    }

    function handleExpired() {
      stopPolling();
      stopTimer();
      showScreen("error");
      if (errorTitle) errorTitle.textContent = "Сесія завершилась";
      if (errorMessage)
        errorMessage.textContent =
          "Ми не отримали ваш контакт за 5 хвилин. Спробуйте знову або введіть @username вручну.";
    }

    function handleCancelled() {
      stopPolling();
      stopTimer();
      showScreen("error");
      if (errorTitle) errorTitle.textContent = "Сесію скасовано";
      if (errorMessage) errorMessage.textContent = "Ви можете запустити підтвердження ще раз.";
    }

    async function cancelSession() {
      if (!session || !session.token) return;
      try {
        await postJSON(ENDPOINTS.cancel, { token: session.token });
      } catch (e) {
        /* ignore */
      }
    }

    function resetVerified({ silent } = {}) {
      verified = null;
      if (verifyState) verifyState.hidden = true;
      trigger.hidden = false;
      if (hiddenInputs) {
        ["userId", "username", "phone", "firstName", "lastName", "token"].forEach((k) => {
          if (hiddenInputs[k]) hiddenInputs[k].value = "";
        });
      }
      if (!silent) safeNotify("Підтвердження Telegram скинуто.", "info");
    }

    // ── Events ──
    trigger.addEventListener("click", () => {
      showScreen("intro");
      openModal();
    });

    modal.addEventListener("click", (event) => {
      if (event.target === modal) {
        closeModal();
      }
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !modal.hidden) {
        closeModal();
      }
    });

    modal.querySelectorAll("[data-tg-verify-close]").forEach((btn) => {
      btn.addEventListener("click", closeModal);
    });

    modal.querySelectorAll("[data-tg-verify-open-bot]").forEach((btn) => {
      btn.addEventListener("click", handleStart);
    });

    modal.querySelectorAll("[data-tg-verify-reopen-bot]").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (session && session.deep_link_url) {
          try {
            window.open(session.deep_link_url, "_blank", "noopener,noreferrer");
          } catch (e) {
            location.href = session.deep_link_url;
          }
        }
      });
    });

    modal.querySelectorAll("[data-tg-verify-copy-link]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!session || !session.deep_link_url) return;
        try {
          await navigator.clipboard.writeText(session.deep_link_url);
          safeNotify("Посилання скопійовано.", "success");
        } catch (e) {
          safeNotify("Не вдалося скопіювати — використайте кнопку «Відкрити бота».", "error");
        }
      });
    });

    modal.querySelectorAll("[data-tg-verify-cancel]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await cancelSession();
        stopPolling();
        stopTimer();
        closeModal();
      });
    });

    modal.querySelectorAll("[data-tg-verify-manual]").forEach((btn) => {
      btn.addEventListener("click", () => {
        closeModal();
        if (contactValueInput) {
          contactValueInput.focus();
          contactValueInput.select?.();
        }
      });
    });

    modal.querySelectorAll("[data-tg-verify-retry]").forEach((btn) => {
      btn.addEventListener("click", handleStart);
    });

    if (verifyStateReset) {
      verifyStateReset.addEventListener("click", () => resetVerified());
    }

    // Слухач зміни каналу зв'язку: моніторимо клік по чипсам.
    if (contactChannelList) {
      contactChannelList.addEventListener("click", () => {
        // Чіпси оновлюють активний клас всередині свого хендлера.
        // Чекаємо мікрозадачу, щоб клас встиг переключитись.
        setTimeout(updateShellVisibility, 0);
      });
      // MutationObserver на випадок, якщо чіпси перемальовуються конфігуратором
      try {
        const observer = new MutationObserver(updateShellVisibility);
        observer.observe(contactChannelList, {
          subtree: true,
          attributes: true,
          attributeFilter: ["class"],
          childList: true,
        });
      } catch (e) {
        /* ignore */
      }
    }

    // Початковий показ
    updateShellVisibility();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
