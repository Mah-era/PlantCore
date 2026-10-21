/* Shared presentation and accessible workspace navigation. No planning calculations. */
const studioIcons = {
  overview:
    '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  network:
    '<path d="M3 21V9l6 3V7l6 3V3h6v18H3Z"/><path d="M7 16h1m4 0h1m4 0h1"/>',
  schedule:
    '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 11h18m-14 4h4m2 3h4"/>',
  orders:
    '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6m-6 4h6m-6 4h4"/>',
  visuals: '<path d="M4 3v17h17M8 15l4-5 4 2 5-7"/>',
  investigate: '<path d="m12 3 10 17H2L12 3Z"/><path d="M12 9v4m0 3v1"/>',
  recovery: '<path d="M4 8a8 8 0 1 1-1 7M4 3v5h5"/><path d="m9 12 2 2 4-4"/>',
  warroom:
    '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16m6-16v16M5 9h2m4 3h2m4-4h2"/>',
  improvement:
    '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><path d="m12 12 7-7"/>',
  governance:
    '<path d="M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6l-8-3Z"/><path d="m8 12 3 3 5-6"/>',
  search: '<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  refresh: '<path d="M20 7a8 8 0 1 0 1 8M20 3v5h-5"/>',
  upload: '<path d="M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6"/>',
  book: '<path d="M12 5v16M12 5C8 2 3 3 3 3v16s5-1 9 2c4-3 9-2 9-2V3s-5-1-9 2Z"/>',
  arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
};
function studioIcon(name) {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${studioIcons[name] || studioIcons.overview}</svg>`;
}
const workspaceHints = {
  overview: "Network health, exceptions, and priorities",
  network: "Partner factories, quality, cost, and delivery",
  schedule: "Capacity, production stages, and shipment dates",
  orders: "Orders, release gates, and line allocation",
  visuals: "30 analytical views and downloadable evidence",
  investigate: "Incidents, root causes, and supporting evidence",
  recovery: "Response alternatives and commercial trade-offs",
  warroom: "RACI actions, owners, and factory commitments",
  improvement: "Interventions, PDCA, and sustained outcomes",
  governance: "Source records, benchmarks, and decision history",
};
function renderWorkspaceSearch(query = "") {
  const matches = Object.entries(workspaceHints).filter(([page, hint]) =>
    `${pageNames[page]} ${hint}`
      .toLowerCase()
      .includes(query.trim().toLowerCase()),
  );
  $("#workspaceResults").innerHTML = matches.length
    ? matches
        .map(
          ([page, hint]) =>
            `<button class="workspace-result" onclick="document.getElementById('searchDialog').close();go(${jsarg(page)})"><span class="result-icon">${studioIcon(page)}</span><span><strong>${esc(pageNames[page])}</strong><small>${esc(hint)}</small></span><span class="result-arrow">${studioIcon("arrow")}</span></button>`,
        )
        .join("")
    : '<div class="empty">No workspace matches that search.</div>';
}
function openWorkspaceSearch() {
  toggleNavigation(false);
  $("#workspaceSearch").value = "";
  renderWorkspaceSearch();
  $("#searchDialog").showModal();
  $("#workspaceSearch").focus();
}
let navReturnFocus = null;
const narrowViewport = window.matchMedia("(max-width: 900px)");
function toggleNavigation(
  open = !document.body.classList.contains("nav-open"),
) {
  const active = open && narrowViewport.matches;
  if (active) navReturnFocus = document.activeElement;
  document.body.classList.toggle("nav-open", active);
  $(".menu-toggle").setAttribute("aria-expanded", String(active));
  $(".menu-toggle").setAttribute(
    "aria-label",
    active ? "Close workspace navigation" : "Open workspace navigation",
  );
  $(".nav-backdrop").hidden = !active;
  $(".sidebar").inert = narrowViewport.matches && !active;
  $(".main").inert = active;
  if (active) {
    $(".sidebar").setAttribute("role", "dialog");
    $(".sidebar").setAttribute("aria-modal", "true");
    $(".workspace-search").focus();
  } else {
    $(".sidebar").removeAttribute("role");
    $(".sidebar").removeAttribute("aria-modal");
    if (navReturnFocus?.isConnected) navReturnFocus.focus();
    navReturnFocus = null;
  }
}
function finishWorkspacePresentation() {
  document.body.dataset.workspace = state.page;
  document.querySelectorAll("#nav button").forEach((button) => {
    if (button.classList.contains("active"))
      button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  document.querySelectorAll("#content .table-wrap").forEach((wrap) => {
    wrap.tabIndex = 0;
    wrap.setAttribute("role", "region");
    wrap.setAttribute(
      "aria-label",
      (wrap.closest(".card")?.querySelector("h2")?.textContent ||
        "Detailed data") + " · scroll to inspect",
    );
  });
  document
    .querySelectorAll(
      "#content input:not([aria-label]), #content select:not([aria-label]), #content textarea:not([aria-label])",
    )
    .forEach((field, index) => {
      if (field.labels?.length) return;
      const label = field.closest(".field")?.querySelector("label");
      if (label) {
        field.id ||= `workspace-field-${state.page}-${index}`;
        label.htmlFor = field.id;
        return;
      }
      field.setAttribute(
        "aria-label",
        field.placeholder ||
          field.options?.[0]?.textContent ||
          field.name ||
          "Filter",
      );
    });
}
document.querySelectorAll("[data-icon]").forEach((el) => {
  el.innerHTML = studioIcon(el.dataset.icon);
});
document.querySelectorAll("#nav button").forEach((button) => {
  const label = pageNames[button.dataset.page];
  button.innerHTML = `<span class="nav-icon">${studioIcon(button.dataset.page)}</span><span class="nav-text">${esc(label)}</span><span class="nav-indicator" aria-hidden="true"></span>`;
});
narrowViewport.addEventListener("change", () => toggleNavigation(false));
toggleNavigation(false);
document.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    if (state.datasetBusy || $("#workspaceDialog").open) return;
    event.preventDefault();
    openWorkspaceSearch();
  }
  if (!document.body.classList.contains("nav-open")) return;
  if (event.key === "Escape") {
    event.preventDefault();
    toggleNavigation(false);
  }
  if (event.key === "Tab") {
    const focusable = [...$(".sidebar").querySelectorAll("a,button")];
    const first = focusable[0],
      last = focusable.at(-1);
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
});
