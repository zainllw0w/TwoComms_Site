(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
    return;
  }
  root.CustomPrintSubmissionPolicy = factory();
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  function firstIssue(issues, fallback) {
    return Array.isArray(issues) && issues.length ? issues[0] : fallback;
  }

  function buildFinalActionPolicy(options) {
    const settings = options || {};
    const baseIssues = Array.isArray(settings.baseIssues) ? settings.baseIssues : [];
    const artworkIssues = Array.isArray(settings.artworkIssues) ? settings.artworkIssues : [];
    const estimateRequired = !!settings.estimateRequired;
    const isCustomerGarment = !!settings.isCustomerGarment;
    const serviceKind = (settings.serviceKind || "").trim();
    // Для режимів "готовий файл" та "потрібно допрацювати" файли є частиною
    // самої задачі: без них менеджер не зможе нічого зробити, тому блокуємо
    // навіть кнопку "Надіслати менеджеру", щоб клієнт не надіслав пусту заявку.
    const artworkRequiredForLead = serviceKind === "ready" || serviceKind === "adjust";

    const leadReady = baseIssues.length === 0
      && (!artworkRequiredForLead || artworkIssues.length === 0);
    const cartReady = baseIssues.length === 0
      && artworkIssues.length === 0
      && !estimateRequired
      && !isCustomerGarment;

    let leadHint;
    if (baseIssues.length) {
      leadHint = baseIssues[0];
    } else if (artworkRequiredForLead && artworkIssues.length) {
      leadHint = artworkIssues[0];
    } else if (artworkIssues.length) {
      leadHint = "Макети можна додати пізніше — менеджер побачить, яких файлів не вистачає.";
    } else {
      leadHint = "Бот відправить заявку в Telegram";
    }

    let cartHint = "Передзамовлення зі снимком конфігурації";
    if (baseIssues.length) {
      cartHint = baseIssues[0];
    } else if (artworkIssues.length) {
      cartHint = artworkIssues[0];
    } else if (estimateRequired) {
      cartHint = "Цей виріб потребує менеджерського прорахунку";
    } else if (isCustomerGarment) {
      cartHint = "Свій виріб оформлюємо тільки через менеджера";
    }

    return {
      leadReady,
      cartReady,
      leadHint,
      cartHint,
    };
  }

  return {
    buildFinalActionPolicy,
  };
});
