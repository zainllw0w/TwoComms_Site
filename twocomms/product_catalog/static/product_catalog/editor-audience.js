(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.productCatalogAudience = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const DERIVED_FROM_UNISEX = ['men', 'women'];

  function uniqueCodes(codes) {
    return Array.from(new Set(
      Array.from(codes || [], (code) => String(code || '').trim()).filter(Boolean)
    ));
  }

  function canonicalAudienceCodes(codes) {
    const normalized = uniqueCodes(codes);
    if (!normalized.includes('unisex')) return normalized;
    return normalized.filter((code) => !DERIVED_FROM_UNISEX.includes(code));
  }

  function effectiveAudienceCodes(codes) {
    const canonical = canonicalAudienceCodes(codes);
    if (!canonical.includes('unisex')) return canonical;
    const effective = [];
    canonical.forEach((code) => {
      effective.push(code);
      if (code === 'unisex') effective.push(...DERIVED_FROM_UNISEX);
    });
    return uniqueCodes(effective);
  }

  function toggleAudienceCode(codes, code, checked) {
    const selected = new Set(canonicalAudienceCodes(codes));
    const normalizedCode = String(code || '').trim();
    if (!normalizedCode) return Array.from(selected);
    if (checked) selected.add(normalizedCode);
    else selected.delete(normalizedCode);
    return canonicalAudienceCodes(Array.from(selected));
  }

  return {
    canonicalAudienceCodes,
    effectiveAudienceCodes,
    toggleAudienceCode,
  };
}));
