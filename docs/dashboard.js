"use strict";
// Native fragment links remain usable when JavaScript or saved data is unavailable.
(() => {
  const links = [...document.querySelectorAll('.sidebar a[href^="#"]')];
  function markLocation() {
    const current = links.find(link => link.hash === window.location.hash) || links[0];
    for (const link of links) {
      if (link === current) link.setAttribute("aria-current", "location");
      else link.removeAttribute("aria-current");
    }
  }
  for (const link of links) {
    link.addEventListener("click", () => {
      document.getElementById(link.hash.slice(1))?.focus({preventScroll: true});
    });
  }
  window.addEventListener("hashchange", markLocation);
  markLocation();

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
