"use strict";
// Native fragment links remain usable when JavaScript or saved data is unavailable.
(() => {
  // Give horizontally scrolling data tables keyboard access and distinct names.
  document.querySelectorAll(".table-wrap").forEach((wrapper, index) => {
    const table = wrapper.querySelector("table");
    if (!table) return;
    const heading = wrapper.closest("section")?.querySelector("h2");
    const columns = [...table.querySelectorAll("thead th")].map(th => th.textContent.trim());
    wrapper.tabIndex = 0;
    wrapper.setAttribute("role", "region");
    wrapper.setAttribute("aria-label", `${heading?.textContent || "Dashboard"}: ${columns.join(", ")} (scrollable table ${index + 1})`);
    table.querySelectorAll("thead th").forEach(th => th.setAttribute("scope", "col"));
  });
})();
