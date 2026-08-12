/* Pure render-planning helpers for the Custom Print configurator. */
(function (global) {
  "use strict";

  const DOMAIN_KEYS = ["navigation", "content", "pricing", "preview"];

  function stable(value) {
    if (value == null) return "";
    if (Array.isArray(value)) return `[${value.map(stable).join(",")}]`;
    if (typeof value === "object") {
      return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stable(value[key])}`).join(",")}}`;
    }
    return JSON.stringify(value);
  }

  function signature(snapshot) {
    return DOMAIN_KEYS.reduce((result, key) => {
      result[key] = stable(snapshot?.[key]);
      return result;
    }, {});
  }

  function dirtyDomains(previous, next) {
    if (!previous) return new Set(DOMAIN_KEYS);
    return new Set(DOMAIN_KEYS.filter((key) => previous[key] !== next[key]));
  }

  function memoize(compute) {
    let key = null;
    let value;
    return function memoized(nextKey) {
      if (nextKey !== key) {
        key = nextKey;
        value = compute(nextKey);
      }
      return value;
    };
  }

  function createRefreshGate(flush) {
    const pending = new Set();
    return {
      request(domains) {
        (domains || DOMAIN_KEYS).forEach((domain) => pending.add(domain));
      },
      flush() {
        if (!pending.size) return;
        const domains = new Set(pending);
        pending.clear();
        flush(domains);
      },
    };
  }

  global.CustomPrintRenderPlan = { createRefreshGate, dirtyDomains, memoize, signature, stable };
})(globalThis);
