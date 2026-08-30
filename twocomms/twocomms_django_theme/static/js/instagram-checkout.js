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
  const paymentFallbackErrors = {
    uk: {
      expired: "Термін дії пропозиції завершився.",
      unavailable: "Цю пропозицію більше не можна оплатити.",
      in_progress: "Платіж уже створюється. Зачекайте кілька секунд.",
      provider_ambiguous: "Банк ще перевіряє платіж. Не повторюйте оплату — ми звіримо статус і повідомимо вас у Direct.",
      full_name: "Вкажіть ім'я та прізвище.",
      phone: "Вкажіть коректний український номер телефону.",
      email: "Перевірте email для чека.",
      city: "Оберіть місто зі списку Нової пошти.",
      np_office: "Оберіть відділення або поштомат зі списку Нової пошти.",
      promo_unavailable: "Промокод для цієї пропозиції недоступний.",
      promo_invalid: "Промокод недійсний або вже використаний.",
      promo_requires_account: "Цей промокод доступний лише в особистому кабінеті.",
      catalog_changed: "Товар або його умови змінилися. Попросіть бота оновити пропозицію.",
      invalid_amount: "Сума замовлення має бути більшою за нуль.",
      item_unavailable: "Один із товарів більше недоступний.",
      empty_items: "У пропозиції немає товарів.",
      default: "Не вдалося створити платіж. Спробуйте ще раз.",
    },
    ru: {
      expired: "Срок действия предложения истек.",
      unavailable: "Это предложение больше нельзя оплатить.",
      in_progress: "Платеж уже создается. Подождите несколько секунд.",
      provider_ambiguous: "Банк еще проверяет платеж. Не повторяйте оплату — мы сверим статус и сообщим вам в Direct.",
      full_name: "Укажите имя и фамилию.",
      phone: "Укажите корректный украинский номер телефона.",
      email: "Проверьте email для чека.",
      city: "Выберите город из списка Новой почты.",
      np_office: "Выберите отделение или почтомат из списка Новой почты.",
      promo_unavailable: "Промокод для этого предложения недоступен.",
      promo_invalid: "Промокод недействителен или уже использован.",
      promo_requires_account: "Этот промокод доступен только в личном кабинете.",
      catalog_changed: "Товар или его условия изменились. Попросите бота обновить предложение.",
      invalid_amount: "Сумма заказа должна быть больше нуля.",
      item_unavailable: "Один из товаров больше недоступен.",
      empty_items: "В предложении нет товаров.",
      default: "Не удалось создать платеж. Попробуйте еще раз.",
    },
    en: {
      expired: "This offer has expired.",
      unavailable: "This offer can no longer be paid.",
      in_progress: "A payment is already being created. Please wait a few seconds.",
      provider_ambiguous: "The bank is still checking this payment. Do not pay again; we will verify it and message you in Direct.",
      full_name: "Enter your first and last name.",
      phone: "Enter a valid Ukrainian phone number.",
      email: "Check the receipt email.",
      city: "Choose a city from the Nova Poshta list.",
      np_office: "Choose a branch or locker from the Nova Poshta list.",
      promo_unavailable: "A promo code is not available for this offer.",
      promo_invalid: "The promo code is invalid or already used.",
      promo_requires_account: "This promo code is available only in an account.",
      catalog_changed: "An item or its terms changed. Ask the bot for an updated offer.",
      invalid_amount: "The order total must be greater than zero.",
      item_unavailable: "One of the items is no longer available.",
      empty_items: "This offer has no items.",
      default: "We could not create the payment. Please try again.",
    },
  };
  const prefersReducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;

  const readJsonResponse = async (response) => {
    const contentType = String(response.headers?.get("content-type") || "").toLowerCase();
    if (!contentType.includes("application/json")) return {};
    try {
      const payload = await response.json();
      return payload && typeof payload === "object" && !Array.isArray(payload) ? payload : {};
    } catch (_error) {
      return {};
    }
  };

  const paymentErrorMessage = (code) => {
    const copy = paymentFallbackErrors[locale] || paymentFallbackErrors.uk;
    const safeCode = typeof code === "string" ? code : "";
    return copy[safeCode] || copy.default;
  };

  const paymentErrorField = (code) => ({
    promo_invalid: 'promo_code',
    promo_unavailable: 'promo_code',
    promo_requires_account: 'promo_code',
  }[code] || code);

  const trackCheckoutEvent = (name, eventId, extra = {}) => {
    if (!eventId || window.__twcAnalyticsConsent !== true || typeof window.trackEvent !== "function") return;
    window.trackEvent(name, {
      event_id: eventId,
      value: Number(root.dataset.analyticsValue || 0),
      currency: root.dataset.analyticsCurrency || "UAH",
      ...extra,
      __meta: { event_id: eventId },
    });
  };

  // The bearer entry redirects to a clean URL before this runs. Crawlers do
  // not execute this browser-only bridge, and repeated loads reuse the event id.
  trackCheckoutEvent("ViewContent", document.documentElement.dataset.viewContentEventId);
  trackCheckoutEvent("Purchase", document.documentElement.dataset.purchaseEventId);

  const csrfToken = () =>
    document.querySelector('[name="csrfmiddlewaretoken"]')?.value || "";

  const setActionLabel = (button, value) => {
    const label = button?.querySelector("[data-action-label]");
    if (label) label.textContent = value;
  };

  const paymentRail = document.querySelector("[data-payment-rail]");
  const paymentButton = document.querySelector("[data-payment-submit]");
  const paymentContinue = document.querySelector("[data-payment-continue]");
  const checkoutForm = document.querySelector("[data-np-form]");
  let checkoutExpired = false;
  const shareDialog = document.querySelector("[data-share-dialog]");
  const priceDialog = document.querySelector("[data-price-dialog]");
  const priceDetails = document.querySelector("[data-price-details]");
  const checkoutStateBanner = document.querySelector("[data-checkout-state-banner]");
  let dialogTrigger = null;

  const showCheckoutDialog = (dialog, trigger) => {
    if (!dialog) return;
    dialogTrigger = trigger || document.activeElement;
    if (typeof dialog.showModal === "function") {
      dialog.showModal();
    } else {
      dialog.setAttribute("open", "");
    }
    window.setTimeout(() => {
      dialog.querySelector("button, a[href], input")?.focus({ preventScroll: true });
    }, 0);
  };

  const restoreDialogFocus = () => {
    dialogTrigger?.focus?.({ preventScroll: true });
    dialogTrigger = null;
  };

  const closeCheckoutDialog = (dialog) => {
    if (!dialog || (!dialog.open && !dialog.hasAttribute("open"))) return;
    if (typeof dialog.close === "function") {
      dialog.close();
    } else {
      dialog.removeAttribute("open");
    }
  };

  const bindCheckoutDialog = (dialog) => {
    dialog?.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close?.();
    });
    dialog?.addEventListener("close", restoreDialogFocus);
  };

  bindCheckoutDialog(priceDialog);
  bindCheckoutDialog(shareDialog);
  document.querySelectorAll("[data-price-details]").forEach((trigger) => {
    trigger.addEventListener("click", () => {
      if (!checkoutExpired) showCheckoutDialog(priceDialog, trigger);
    });
  });
  document.querySelectorAll("[data-share-open]").forEach((trigger) => {
    trigger.addEventListener("click", () => {
      if (checkoutExpired) return;
      if (shareDialog) shareDialog.dataset.preferNative = trigger.hasAttribute("data-share-native") ? "true" : "false";
      showCheckoutDialog(shareDialog, trigger);
    });
  });

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
      if (checkoutExpired || !button.dataset.shareUrl) return;
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
        const payload = await readJsonResponse(response);
        if (!response.ok || !payload.url) throw new Error("share_unavailable");
        if (checkoutExpired) return;
        const preferNativeShare = shareDialog?.dataset.preferNative === "true";
        if (preferNativeShare && navigator.share) {
          await navigator.share({ url: payload.url });
        } else {
          await writeClipboard(payload.url);
        }
        setActionLabel(button, button.dataset.shareDone || original);
      } catch (error) {
        setActionLabel(
          button,
          error?.name === "AbortError"
            ? original
            : (button.dataset.shareError || original),
        );
      } finally {
        window.setTimeout(() => {
          setActionLabel(button, original);
          button.disabled = checkoutExpired;
        }, 1800);
      }
    });
  });

  const countdown = document.querySelector("[data-countdown]");
  const expiryStatus = document.querySelector("[data-expiry-status]");
  const countdownWrap = document.querySelector("[data-countdown-wrap]");
  const countdownRing = document.querySelector("[data-countdown-ring]");
  const expiresAt = Date.parse(root.dataset.expiresAt || "");
  const createdAt = Date.parse(root.dataset.createdAt || "");
  const countdownDuration = Number.isFinite(expiresAt)
    ? Math.max(1000, expiresAt - (Number.isFinite(createdAt) ? createdAt : expiresAt - 25 * 60 * 1000))
    : 0;
  const ringCircumference = 2 * Math.PI * 17;
  if (countdownRing) {
    countdownRing.style.strokeDasharray = `${ringCircumference}`;
    countdownRing.style.strokeDashoffset = "0";
  }

  const expireCheckout = () => {
    if (checkoutExpired) return;
    checkoutExpired = true;
    root.classList.add("is-expired");
    root.dataset.checkoutState = "expired";
    countdownWrap?.classList.add("is-expired");
    dialogTrigger = null;
    closeCheckoutDialog(priceDialog);
    closeCheckoutDialog(shareDialog);
    if (priceDetails) {
      priceDetails.classList.remove("ig-state--ready");
      priceDetails.classList.add("ig-state--expired");
      priceDetails.querySelector(".ig-state__copy strong").textContent = priceDetails.dataset.expiredTitle || "";
      priceDetails.querySelector(".ig-state__copy small").textContent = priceDetails.dataset.expiredBody || "";
      priceDetails.disabled = true;
      priceDetails.removeAttribute("aria-haspopup");
      priceDetails.removeAttribute("aria-controls");
      const stateIcon = priceDetails.querySelector("[data-state-icon]");
      stateIcon?.setAttribute("data-state-icon", "attention");
      stateIcon?.querySelector("use")?.setAttribute("href", "#ig-icon-alert");
    }
    if (checkoutStateBanner) {
      checkoutStateBanner.classList.remove("ig-state--pending", "ig-state--locked");
      checkoutStateBanner.classList.add("ig-state--expired");
      checkoutStateBanner.querySelector(".ig-state__copy strong").textContent = checkoutStateBanner.dataset.expiredTitle || "";
      checkoutStateBanner.querySelector(".ig-state__copy small").textContent = checkoutStateBanner.dataset.expiredBody || "";
      const stateIcon = checkoutStateBanner.querySelector("[data-state-icon]");
      stateIcon?.setAttribute("data-state-icon", "attention");
      stateIcon?.querySelector("use")?.setAttribute("href", "#ig-icon-alert");
    }
    document.querySelectorAll("[data-share-open]").forEach((trigger) => {
      trigger.disabled = true;
      trigger.setAttribute("aria-disabled", "true");
    });
    document.querySelectorAll("[data-share-url]").forEach((button) => {
      button.disabled = true;
      button.removeAttribute("data-share-url");
    });
    if (paymentRail) paymentRail.classList.add("is-expired");
    if (paymentButton) {
      paymentButton.disabled = true;
      setActionLabel(paymentButton, countdown?.dataset.expiredLabel || "Час завершився");
    }
    if (paymentContinue) {
      paymentContinue.removeAttribute("href");
      paymentContinue.setAttribute("aria-disabled", "true");
      paymentContinue.setAttribute("tabindex", "-1");
      setActionLabel(paymentContinue, countdown?.dataset.expiredLabel || "Час завершився");
    }
    checkoutForm?.querySelectorAll("input, button, select, textarea").forEach((field) => {
      if (field !== paymentButton) field.disabled = true;
    });
    if (countdown) {
      countdown.textContent = "00:00";
      countdown.setAttribute("aria-label", countdown.dataset.expiredLabel || "00:00");
    }
    if (expiryStatus && !expiryStatus.textContent) {
      expiryStatus.textContent = countdown?.dataset.expiredLabel || "00:00";
    }
    const directHelp = root.querySelector("[data-direct-help]");
    directHelp?.classList.add("is-priority");
  };

  if (countdown && Number.isFinite(expiresAt)) {
    const renderCountdown = () => {
      const remaining = Math.max(0, expiresAt - Date.now());
      const remainingSeconds = Math.ceil(remaining / 1000);
      const minutes = Math.floor(remainingSeconds / 60);
      const seconds = remainingSeconds % 60;
      const progress = countdownDuration ? Math.min(1, remaining / countdownDuration) : 0;
      countdownRing?.style.setProperty("stroke-dashoffset", `${ringCircumference * (1 - progress)}`);
      root.style.setProperty("--countdown-progress", `${progress}`);
      countdownWrap?.classList.toggle("is-expiring", remaining > 0 && remaining <= 5 * 60 * 1000);
      if (!remaining) {
        expireCheckout();
        return false;
      }
      countdown.textContent = `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
      return true;
    };
    renderCountdown();
    const countdownTimer = window.setInterval(() => {
      if (!renderCountdown()) window.clearInterval(countdownTimer);
    }, 1000);
    window.addEventListener("beforeunload", () => window.clearInterval(countdownTimer), { once: true });
  }

  if (root.dataset.checkoutState === "pending" && root.dataset.statusUrl) {
    const generationExpiresAt = Date.parse(root.dataset.generationExpiresAt || "");
    let generationExpiryTimer;
    if (Number.isFinite(generationExpiresAt)) {
      const remaining = Math.max(0, generationExpiresAt - Date.now() + 500);
      generationExpiryTimer = window.setTimeout(() => window.location.reload(), remaining);
      window.addEventListener(
        "beforeunload",
        () => window.clearTimeout(generationExpiryTimer),
        { once: true },
      );
    }
    let polling = false;
    let pollCount = 0;
    const pollDelays = [3000, 5000, 8000, 12000, 18000, 25000, 30000, 30000];
    const pollStatus = async () => {
      if (polling || document.visibilityState !== "visible" || pollCount >= pollDelays.length) return;
      pollCount += 1;
      polling = true;
      try {
        const response = await fetch(root.dataset.statusUrl, {
          credentials: "same-origin",
          cache: "no-store",
          headers: { Accept: "application/json" },
        });
        if (!response.ok) return;
        const payload = await readJsonResponse(response);
        if (payload.state === "verified" && payload.redirect) {
          window.location.assign(payload.redirect);
          return;
        }
        if (payload.state && ["failed", "expired", "cancellation_ambiguous", "reissue"].includes(payload.state)) {
          window.location.reload();
        }
      } catch (_error) {
        // A later poll retries without exposing payment or recipient data.
      } finally {
        polling = false;
      }
    };
    let pendingTimer;
    const schedulePoll = () => {
      if (pollCount >= pollDelays.length) return;
      pendingTimer = window.setTimeout(async () => {
        await pollStatus();
        schedulePoll();
      }, pollDelays[pollCount]);
    };
    schedulePoll();
    window.addEventListener("beforeunload", () => window.clearTimeout(pendingTimer), { once: true });
  }

  document.querySelectorAll("[data-product-image]").forEach((image) => {
    const enableFallback = () => {
      image.closest("[data-product-media]")?.classList.add("is-fallback");
    };
    image.addEventListener("error", enableFallback);
    if (image.complete && image.naturalWidth === 0) enableFallback();
  });

  const form = checkoutForm;
  if (form) {
    const errorBox = form.querySelector("[data-form-error]");
    const paymentLabel = paymentButton?.querySelector("[data-action-label]");
    const defaultPaymentLabel = paymentLabel?.textContent || "";
    let submitted = false;
    const serverErrorFieldName = document.documentElement.dataset.formErrorField || "";
    const serverErrorField = serverErrorFieldName
      ? form.elements.namedItem(serverErrorFieldName)
      : null;
    let serverErrorPending = Boolean(
      serverErrorField instanceof HTMLElement
      && serverErrorField.getAttribute("aria-invalid") === "true",
    );
    const validationSummaryCopy = {
      uk: "Перевірте виділене поле, щоб продовжити.",
      ru: "Проверьте выделенное поле, чтобы продолжить.",
      en: "Check the highlighted field to continue.",
    };

    const invalidField = (fieldName = "") => {
      const namedField = fieldName ? form.elements.namedItem(fieldName) : null;
      return namedField instanceof HTMLElement
        ? namedField
        : form.querySelector("input[aria-invalid='true'], input:invalid, select:invalid, textarea:invalid");
    };

    const setFieldError = (field, message) => {
      if (!(field instanceof HTMLElement)) return;
      const wrapper = field.closest(".ig-field");
      if (!wrapper) return;
      let fieldError = wrapper.querySelector("[data-field-error], .cart-form-error");
      if (!fieldError) {
        fieldError = document.createElement("small");
        wrapper.appendChild(fieldError);
      }
      fieldError.classList.add("ig-field-error");
      fieldError.dataset.fieldError = "";
      if (!fieldError.id) {
        fieldError.id = `${field.id || field.getAttribute("name") || "ig-field"}-error`;
      }
      fieldError.textContent = message || validationSummaryCopy[locale] || validationSummaryCopy.uk;
      fieldError.hidden = false;
      field.setAttribute("aria-invalid", "true");
      const describedBy = new Set(
        String(field.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean),
      );
      describedBy.add(fieldError.id);
      field.setAttribute("aria-describedby", [...describedBy].join(" "));
    };

    const clearFieldError = (field) => {
      if (!(field instanceof HTMLElement)) return;
      const fieldError = field.closest(".ig-field")?.querySelector("[data-field-error], .cart-form-error");
      if (fieldError) fieldError.hidden = true;
      if (field.checkValidity?.()) field.removeAttribute("aria-invalid");
    };

    const showFormError = (message, fieldName = "") => {
      if (errorBox) {
        errorBox.textContent = message || validationSummaryCopy[locale] || validationSummaryCopy.uk;
        errorBox.hidden = false;
      }
      setFieldError(invalidField(fieldName), message);
      focusFirstInvalid(fieldName);
    };

    const focusFirstInvalid = (fieldName = "") => {
      const field = invalidField(fieldName);
      if (!(field instanceof HTMLElement)) {
        errorBox?.focus({ preventScroll: true });
        return;
      }
      field.closest("details")?.setAttribute("open", "");
      field.setAttribute("aria-invalid", "true");
      if (errorBox?.id) {
        const describedBy = new Set(
          String(field.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean),
        );
        describedBy.add(errorBox.id);
        field.setAttribute("aria-describedby", [...describedBy].join(" "));
      }
      field.style.scrollMarginBottom = `${(paymentRail?.offsetHeight || 0) + 24}px`;
      field.scrollIntoView({
        block: "center",
        behavior: prefersReducedMotion ? "auto" : "smooth",
      });
      window.setTimeout(() => field.focus({ preventScroll: true }), prefersReducedMotion ? 0 : 220);
    };

    const syncServerError = () => {
      if (!serverErrorPending) return;
      const fieldName = serverErrorFieldName;
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
    if (document.documentElement.dataset.formErrorField && errorBox && !errorBox.hidden) {
      window.setTimeout(() => focusFirstInvalid(document.documentElement.dataset.formErrorField), 0);
    }

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
      const syncCompletion = (event) => {
        if (serverErrorPending && serverErrorField === field) {
          if (!event?.isTrusted) {
            if (typeof window.queueMicrotask === "function") {
              window.queueMicrotask(syncServerError);
            } else {
              Promise.resolve().then(syncServerError);
            }
            return;
          }
          serverErrorPending = false;
        }
        const optionalEmpty = !field.required && !field.value.trim();
        if (field.value.trim()) clearFieldError(field);
        wrapper?.classList.toggle(
          "is-complete",
          !optionalEmpty && field.value.trim() !== "" && field.checkValidity(),
        );
        const requiredFields = [...form.querySelectorAll("input[required]")];
        const deliverySelectionsAreSigned = () => {
          const value = (selector) => form.querySelector(selector)?.value?.trim() || "";
          return Boolean(
            (value("[data-np-settlement-ref]") || value("[data-np-city-ref]"))
            && value("[data-np-city-token]")
            && value("[data-np-warehouse-ref]")
            && value("[data-np-warehouse-token]"),
          );
        };
        const isPaymentReady = requiredFields.length > 0
          && requiredFields.every((requiredField) => (
            requiredField.checkValidity()
            && requiredField.value.trim()
            && requiredField.getAttribute("aria-invalid") !== "true"
          ))
          && deliverySelectionsAreSigned();
        const wasPaymentReady = paymentRail?.classList.contains("is-payment-ready");
        paymentRail?.classList.toggle("is-payment-ready", isPaymentReady);
        if (isPaymentReady && !wasPaymentReady && !prefersReducedMotion) {
          paymentRail?.classList.remove("has-readiness-sheen");
          void paymentRail?.offsetWidth;
          paymentRail?.classList.add("has-readiness-sheen");
          window.setTimeout(() => paymentRail?.classList.remove("has-readiness-sheen"), 700);
        }
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

      if (checkoutExpired) {
        showFormError(paymentErrorMessage("expired"));
        return;
      }
      if (!form.checkValidity()) {
        const firstInvalid = invalidField();
        const invalidName = firstInvalid?.getAttribute("name") || "default";
        showFormError(paymentErrorMessage(invalidName), invalidName);
        return;
      }
      const bridge = window.TwoCommsNovaPoshta;
      if (!bridge?.validateForm) {
        showFormError(fallbackErrors[locale] || fallbackErrors.uk);
        return;
      }

      const result = await bridge.validateForm(form);
      if (!result.ok) {
        showFormError(result.message, result.field);
        return;
      }

      const initiateEventId = document.documentElement.dataset.initiateCheckoutEventId;
      trackCheckoutEvent("InitiateCheckout", initiateEventId, {
        num_items: document.querySelectorAll(".ig-item").length,
      });
      if (paymentButton) {
        paymentButton.disabled = true;
        setActionLabel(
          paymentButton,
          paymentButton.dataset.loadingLabel || defaultPaymentLabel,
        );
      }
      try {
        const response = await fetch(form.action, {
          method: "POST",
          body: new FormData(form),
          credentials: "same-origin",
          cache: "no-store",
          headers: { Accept: "application/json" },
        });
        const payload = await readJsonResponse(response);
        if (!response.ok || !payload.invoice_url) {
          throw new Error(typeof payload.error === "string" ? payload.error : "payment_unavailable");
        }
        trackCheckoutEvent("AddPaymentInfo", payload.add_payment_event_id, {
          value: Number(payload.value || root.dataset.analyticsValue || 0),
        });
        submitted = true;
        window.location.assign(payload.invoice_url);
      } catch (error) {
        submitted = false;
        if (paymentButton) {
          paymentButton.disabled = false;
          setActionLabel(paymentButton, defaultPaymentLabel);
        }
        if (errorBox) {
          const errorCode = error instanceof Error ? error.message : "";
          showFormError(paymentErrorMessage(errorCode), paymentErrorField(errorCode));
        }
      }
    });
  }

  const exitDialog = document.querySelector("[data-exit-dialog]");
  let exitTrigger = null;
  document.querySelectorAll("[data-checkout-exit]").forEach((trigger) => {
    trigger.addEventListener("click", (event) => {
      if (!exitDialog) return;
      event.preventDefault();
      exitTrigger = trigger;
      showCheckoutDialog(exitDialog, trigger);
      exitDialog.querySelector("[data-checkout-exit-cancel]")?.focus();
    });
  });
  exitDialog?.querySelector("[data-checkout-exit-confirm]")?.addEventListener("click", () => {
    const target = exitTrigger?.getAttribute("href") || "/";
    exitDialog.close?.();
    window.location.assign(target);
  });
  exitDialog?.addEventListener("close", () => {
    exitTrigger?.focus({ preventScroll: true });
    exitTrigger = null;
    dialogTrigger = null;
  });
  exitDialog?.addEventListener("click", (event) => {
    if (event.target === exitDialog) exitDialog.close();
  });

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
