(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.productCatalogEditorCatalog = factory();
}(typeof self !== "undefined" ? self : this, function () {
  function id(value) { return String(value == null ? "" : value); }

  function sortPrints(items, selectedIds) {
    const selected = new Set(Array.from(selectedIds || []).map(id));
    return (items || []).slice().sort((a, b) => {
      const selectedDelta = Number(selected.has(id(b.id))) - Number(selected.has(id(a.id)));
      if (selectedDelta) return selectedDelta;
      const activeDelta = Number(b.is_active !== false) - Number(a.is_active !== false);
      if (activeDelta) return activeDelta;
      const categoryDelta = String(a.category || "").localeCompare(String(b.category || ""), "uk");
      if (categoryDelta) return categoryDelta;
      return String(a.name || "").localeCompare(String(b.name || ""), "uk");
    });
  }

  function printSourceLabel(item) {
    if (item && item.image_source === "print") return "Арт принта";
    if (item && item.image_source === "variant") return "Арт варіанту";
    return "Artwork відсутній";
  }

  function printStateLabel(item, selected) {
    if (selected) return "Вибрано";
    if (!item || item.is_active === false) return "Архів";
    return "Обрати";
  }

  function shouldShowPrintEmpty(visibleCount, query) {
    return Number(visibleCount || 0) === 0 && String(query || "").trim().length > 0;
  }

  function reorderIds(values, itemId, direction) {
    const rows = (values || []).map(id);
    const current = rows.indexOf(id(itemId));
    const target = direction === "up" ? current - 1 : current + 1;
    if (current < 0 || target < 0 || target >= rows.length) return rows;
    const result = rows.slice();
    [result[current], result[target]] = [result[target], result[current]];
    return result;
  }

  return {
    sortPrints,
    printSourceLabel,
    printStateLabel,
    shouldShowPrintEmpty,
    reorderIds,
  };
}));
