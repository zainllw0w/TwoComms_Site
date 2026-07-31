(() => {
  "use strict";

  const root = document.querySelector("[data-ig-checkout]");
  if (!root) return;

  const locale = String(document.documentElement.lang || "uk").split("-")[0].toLowerCase();
  const fallbackErrors = {
    uk: "Не вдалося перевірити Нову пошту. Оновіть сторінку.",
    ru: "Не удалось проверить Новую почту. Обновите страницу.",
    en: "We could not verify Nova Poshta. Refresh the page.",
  };
  const prefersReducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;

  const csrfToken = () =>
    document.querySelector('[name="csrfmiddlewaretoken"]')?.value || "";

  const setActionLabel = (button, value) => {
    const label = button?.querySelector("[data-action-label]");
    if (label) label.textContent = value;
  };

  const writeClipboard = async (value) => {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value);
      return;
    }
    const field = document.createElement("textarea");
    field.value = value;
    field.setAttribute("readonly", "");
    field.style.position = "fixed";
    field.style.opacity = "0";
    document.body.appendChild(field);
    field.select();
    document.execCommand("copy");
    field.remove();
  };

  document.querySelectorAll("[data-share-url]").forEach((button) => {
    button.addEventListener("click", async () => {
      const original = button.dataset.shareLabel || button.textContent.trim();
      button.disabled = true;
      try {
        const response = await fetch(button.dataset.shareUrl, {
          method: "POST",
          credentials: "same-origin",
          cache: "no-store",
          headers: {
            "X-CSRFToken": csrfToken(),
            Accept: "application/json",
          },
        });
        const payload = await response.json();
        if (!response.ok || !payload.url) throw new Error("share_unavailable");
        await writeClipboard(payload.url);
        setActionLabel(button, button.dataset.shareDone || original);
      } catch (_error) {
        setActionLabel(button, button.dataset.shareError || original);
      } finally {
        window.setTimeout(() => {
          setActionLabel(button, original);
          button.disabled = false;
        }, 1800);
      }
    });
  });

  const countdown = document.querySelector("[data-countdown]");
  if (countdown && root.dataset.expiresAt) {
    const expiresAt = Date.parse(root.dataset.expiresAt);
    const renderCountdown = () => {
      const remaining = Math.max(0, expiresAt - Date.now());
      if (!remaining) {
        countdown.textContent = countdown.dataset.expiredLabel || "00:00";
        return false;
      }
      const totalMinutes = Math.floor(remaining / 60000);
      const hours = Math.floor(totalMinutes / 60);
      const minutes = totalMinutes % 60;
      countdown.textContent = `${hours}:${String(minutes).padStart(2, "0")}`;
      return true;
    };
    renderCountdown();
    const countdownTimer = window.setInterval(() => {
      if (!renderCountdown()) window.clearInterval(countdownTimer);
    }, 30000);
  }

  document.querySelectorAll("[data-product-image]").forEach((image) => {
    const enableFallback = () => {
      image.closest("[data-product-media]")?.classList.add("is-fallback");
    };
    image.addEventListener("error", enableFallback);
    if (image.complete && image.naturalWidth === 0) enableFallback();
  });

  const form = document.querySelector("[data-np-form]");
  if (form) {
    const errorBox = form.querySelector("[data-form-error]");
    const paymentButton = document.querySelector("[data-payment-submit]");
    const paymentLabel = paymentButton?.querySelector("[data-action-label]");
    const defaultPaymentLabel = paymentLabel?.textContent || "";
    let submitted = false;

    const syncServerError = () => {
      const fieldName = document.documentElement.dataset.formErrorField;
      if (!fieldName) return;
      const field = form.elements.namedItem(fieldName);
      if (!field || typeof field.setAttribute !== "function") return;
      field.setAttribute("aria-invalid", "true");
      if (errorBox?.id) {
        const describedBy = new Set(
          String(field.getAttribute("aria-describedby") || "")
            .split(/\s+/)
            .filter(Boolean),
        );
        describedBy.add(errorBox.id);
        field.setAttribute("aria-describedby", [...describedBy].join(" "));
      }
    };
    syncServerError();

    const setFocusedState = () => {
      root.classList.toggle(
        "is-field-focused",
        Boolean(form.querySelector("input:focus")),
      );
    };
    form.addEventListener("focusin", setFocusedState);
    form.addEventListener("focusout", () => window.setTimeout(setFocusedState, 0));

    form.querySelectorAll("input:not([type='hidden'])").forEach((field) => {
      const wrapper = field.closest(".ig-field");
      const syncCompletion = () => {
        const optionalEmpty = !field.required && !field.value.trim();
        if (field.value.trim() && field.getAttribute("aria-invalid") === "true") {
          field.removeAttribute("aria-invalid");
        }
        wrapper?.classList.toggle(
          "is-complete",
          !optionalEmpty && field.value.trim() !== "" && field.checkValidity(),
        );
      };
      field.addEventListener("input", syncCompletion);
      field.addEventListener("change", syncCompletion);
      syncCompletion();
    });

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
      if (submitted) return;
      if (errorBox) {
        errorBox.hidden = true;
        errorBox.textContent = "";
      }

      if (!form.reportValidity()) return;
      const bridge = window.TwoCommsNovaPoshta;
      if (!bridge?.validateForm) {
        if (errorBox) {
          errorBox.textContent = fallbackErrors[locale] || fallbackErrors.uk;
          errorBox.hidden = false;
        }
        return;
      }

      const result = await bridge.validateForm(form);
      if (!result.ok) {
        if (errorBox) {
          errorBox.textContent = result.message;
          errorBox.hidden = false;
          errorBox.scrollIntoView({ block: "center", behavior: prefersReducedMotion ? "auto" : "smooth" });
        }
        return;
      }

      submitted = true;
      if (paymentButton) {
        paymentButton.disabled = true;
        setActionLabel(
          paymentButton,
          paymentButton.dataset.loadingLabel || defaultPaymentLabel,
        );
      }
      HTMLFormElement.prototype.submit.call(form);
    });
  }

  const initializeNovaPoshta = () => {
    window.TwoCommsNovaPoshta?.initScope?.(root);
  };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeNovaPoshta, { once: true });
  } else {
    initializeNovaPoshta();
  }

  let revisionCheckRunning = false;
  document.addEventListener("visibilitychange", async () => {
    if (document.visibilityState !== "visible" || revisionCheckRunning) return;
    revisionCheckRunning = true;
    try {
      const response = await fetch(root.dataset.proposalUrl || window.location.href, {
        credentials: "same-origin",
        cache: "no-store",
        headers: { Accept: "text/html" },
      });
      if (!response.ok) return;
      const html = await response.text();
      const page = new DOMParser().parseFromString(html, "text/html").documentElement;
      const current = document.documentElement.dataset.proposalRevision;
      const next = page.dataset.proposalRevision;
      const currentState = document.documentElement.dataset.checkoutState;
      const nextState = page.dataset.checkoutState;
      if ((next && next !== current) || (nextState && nextState !== currentState)) {
        window.location.reload();
      }
    } catch (_error) {
      // The next visibility change safely retries without exposing proposal data.
    } finally {
      revisionCheckRunning = false;
    }
  });
})();
