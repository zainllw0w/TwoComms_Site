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

    const leadReady = baseIssues.length === 0;
    const cartReady = leadReady && artworkIssues.length === 0 && !estimateRequired && !isCustomerGarment;

    let leadHint = firstIssue(baseIssues, "Бот відправить заявку в Telegram");
    if (leadReady && artworkIssues.length) {
      leadHint = "Макети можна додати пізніше — менеджер побачить, яких файлів не вистачає.";
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
