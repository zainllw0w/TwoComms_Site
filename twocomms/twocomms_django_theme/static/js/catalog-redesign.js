(() => {
  const panels = document.querySelectorAll("[data-catalog-print-panel]");

  panels.forEach((panel) => {
    const preview = panel.querySelector("[data-print-preview]");
    const tools = Array.from(panel.querySelectorAll(".catalog-print-tool[data-print-mode]"));

    if (!preview || tools.length === 0) {
      return;
    }

    const activateMode = (mode) => {
      preview.dataset.printMode = mode;
      tools.forEach((tool) => {
        const isActive = tool.dataset.printMode === mode;
        tool.classList.toggle("is-active", isActive);
        tool.setAttribute("aria-pressed", isActive ? "true" : "false");
      });
    };

    tools.forEach((tool) => {
      tool.addEventListener("click", () => {
        activateMode(tool.dataset.printMode || "print");
      });
    });
  });
})();
