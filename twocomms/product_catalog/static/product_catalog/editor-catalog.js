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

  function orderedCollections(items) {
    return (items || []).slice().sort((a, b) => {
      const orderDelta = Number(a.order || 0) - Number(b.order || 0);
      if (orderDelta) return orderDelta;
      return String(a.slug || "").localeCompare(String(b.slug || ""), "uk");
    });
  }

  function groupCollections(items) {
    const rows = orderedCollections(items);
    const bySlug = new Map(rows.map((row) => [id(row.slug), row]));
    const children = new Map();
    rows.forEach((row) => {
      const parentSlug = id(row.parent_slug);
      const key = parentSlug && bySlug.has(parentSlug) ? parentSlug : "";
      if (!children.has(key)) children.set(key, []);
      children.get(key).push(row);
    });
    const visited = new Set();
    function build(row, ancestors) {
      const slug = id(row.slug);
      visited.add(slug);
      const branch = new Set(ancestors || []);
      branch.add(slug);
      return Object.assign({}, row, {
        children: (children.get(slug) || [])
          .filter((child) => !branch.has(id(child.slug)))
          .map((child) => build(child, branch)),
      });
    }
    const grouped = (children.get("") || []).map((row) => build(row, new Set()));
    rows.forEach((row) => {
      if (!visited.has(id(row.slug))) grouped.push(build(row, new Set()));
    });
    return grouped;
  }

  function derivedCollectionSlugs(items, selectedSlugs) {
    const rows = orderedCollections(items);
    const selected = new Set(Array.from(selectedSlugs || []).map(id));
    const bySlug = new Map(rows.map((row) => [id(row.slug), row]));
    const derived = new Set();
    selected.forEach((slug) => {
      let row = bySlug.get(slug);
      const seen = new Set();
      while (row && row.parent_slug && !seen.has(id(row.parent_slug))) {
        const parentSlug = id(row.parent_slug);
        seen.add(parentSlug);
        if (!selected.has(parentSlug)) derived.add(parentSlug);
        row = bySlug.get(parentSlug);
      }
    });
    return new Set(rows.map((row) => id(row.slug)).filter((slug) => derived.has(slug)));
  }

  function canonicalCollectionSlugs(items, selectedSlugs) {
    const rows = orderedCollections(items);
    const bySlug = new Map(rows.map((row) => [id(row.slug), row]));
    const selected = new Set(Array.from(selectedSlugs || []).map(id));
    const canonical = new Set(selected);
    selected.forEach((slug) => {
      let row = bySlug.get(slug);
      const seen = new Set([slug]);
      while (row && row.parent_slug && !seen.has(id(row.parent_slug))) {
        const parentSlug = id(row.parent_slug);
        seen.add(parentSlug);
        canonical.delete(parentSlug);
        row = bySlug.get(parentSlug);
      }
    });
    return new Set(rows.map((row) => id(row.slug)).filter((slug) => canonical.has(slug)));
  }

  return {
    sortPrints,
    printSourceLabel,
    printStateLabel,
    shouldShowPrintEmpty,
    reorderIds,
    groupCollections,
    derivedCollectionSlugs,
    canonicalCollectionSlugs,
  };
}));
