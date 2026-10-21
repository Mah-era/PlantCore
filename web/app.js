const state = {
  page: "overview",
  order: null,
  incident: "INC-001",
  option: null,
  incidentTab: "analysis",
  factoryFilter: "all",
  orderFactory: "all",
  orderRisk: "all",
  orderGate: "all",
  orderSearch: "",
  orderLine: "all",
  dueFilter: null,
};
const $ = (s) => document.querySelector(s);
const esc = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const jsarg = (s) => esc(JSON.stringify(String(s ?? "")));
const money = (n) => "$" + Math.round(Number(n || 0)).toLocaleString();
const pct = (n) => (Number(n || 0) * 100).toFixed(1) + "%";
const pctOrNA = (n) => (n === null || n === undefined ? "N/A" : pct(n));
const moneyOrNA = (n) => (n === null || n === undefined ? "N/A" : money(n));
const tag = (text, tone) => `<span class="tag ${tone}">${esc(text)}</span>`;
const fmt = (d) =>
  d
    ? new Date(d + "T12:00:00").toLocaleDateString("en-GB", {
        day: "2-digit",
        month: "short",
      })
    : "—";
async function api(path, options = {}) {
  const r = await fetch("/api" + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  let body = await r.json();
  if (!r.ok) throw new Error(body.detail || "Request failed");
  return body;
}
function toast(message) {
  const t = $("#toast");
  t.textContent = message;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 3400);
}
async function loadScenarioCatalog() {
  const catalog = await api("/scenarios");
  state.scenarios = catalog.items;
  state.scenario = catalog.active;
  $("#scenarioSelector").innerHTML = catalog.items
    .map(
      (x) =>
        `<option value="${esc(x.id)}" ${x.id === catalog.active ? "selected" : ""}>${x.builtin ? "" : "Upload · "}${esc(x.name)}</option>`,
    )
    .join("");
  const active = catalog.items.find((x) => x.id === catalog.active);
  state.asOf = active?.as_of;
  $("#scenarioName").textContent = active?.name || "Scenario";
  $("#scenarioDescription").textContent = active?.description || "";
  $("#dataBadge").textContent = active?.synthetic
    ? "● SIMULATED DATA"
    : "● UPLOADED DATA";
  $("#sidebarSource").textContent = active?.synthetic
    ? "Synthetic scenario"
    : "Uploaded order file";
}
async function changeScenario(id) {
  if (state.datasetBusy) return;
  try {
    await api("/scenarios/select", {
      method: "POST",
      body: JSON.stringify({ id }),
    });
    state.option = null;
    state.order = null;
    state.incident = "INC-001";
    state.factoryFilter = "all";
    state.orderFactory = "all";
    state.orderRisk = "all";
    state.orderGate = "all";
    state.orderLine = "all";
    state.orderSearch = "";
    state.dueFilter = null;
    state.scheduleFactory = "all";
    await loadScenarioCatalog();
    await go("overview");
    toast("Scenario loaded: " + $("#scenarioName").textContent);
  } catch (e) {
    toast(e.message);
    await loadScenarioCatalog();
  }
}
async function uploadScenario(file) {
  if (!file || state.datasetBusy) return;
  state.datasetBusy = true;
  const surfaces = [...document.querySelectorAll("main, aside")].map((el) => [el, el.inert]);
  surfaces.forEach(([el]) => { el.inert = true; });
  const progress = document.createElement("div");
  progress.className = "import-progress";
  progress.setAttribute("role", "status");
  progress.setAttribute("aria-live", "polite");
  progress.textContent = "Validating and analyzing " + file.name + "…";
  document.body.appendChild(progress);
  try {
    if (file.size > 3000000) throw new Error("Scenario file exceeds 3 MB");
    const response = await fetch(
      "/api/scenarios/upload?filename=" + encodeURIComponent(file.name),
      { method: "POST", body: file },
    );
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Upload failed");
    state.option = null;
    state.order = null;
    state.incident = "INC-001";
    state.factoryFilter = "all";
    state.orderFactory = "all";
    state.orderGate = "all";
    state.orderRisk = "all";
    state.orderLine = "all";
    state.orderSearch = "";
    state.dueFilter = null;
    state.scheduleFactory = "all";
    await loadScenarioCatalog();
    await go("overview");
    toast("Analyzed " + result.orders + " orders from " + file.name);
  } catch (e) {
    toast(e.message);
  } finally {
    $("#scenarioUpload").value = "";
    progress.remove();
    surfaces.forEach(([el, wasInert]) => { el.inert = wasInert; });
    state.datasetBusy = false;
  }
}
async function downloadReport(type) {
  if (!type) return;
  if (type === "visual-report") return downloadVisualReport();
  const path =
    type === "scenario" ? "/api/scenarios/export" : "/api/reports/" + type;
  try {
    const response = await fetch(path);
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Report download failed");
    }
    const url = URL.createObjectURL(await response.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = type === "scenario" ? "plantcore-working-scenario.json" : `plantcore-${type}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
    toast("Report downloaded");
  } catch (error) {
    toast(error.message);
  }
}
async function showDefinitions() {
  const d = await api("/definitions");
  let existing = $("#definitions");
  if (existing) {
    existing.scrollIntoView({ behavior: "smooth" });
    return;
  }
  const el = document.createElement("section");
  el.id = "definitions";
  el.className = "card panel";
  el.style.marginTop = "18px";
  el.innerHTML = `<div class="section-title"><h2>KPI definitions and assumptions</h2><button class="quiet" onclick="document.querySelector('#definitions').remove()">Close</button></div>${table(
    ["Measure", "Definition"],
    Object.entries(d).map(
      ([key, value]) =>
        `<tr><td><strong>${esc(key.replaceAll("_", " "))}</strong></td><td style="white-space:normal;min-width:350px">${esc(value)}</td></tr>`,
    ),
  )}`;
  $("#content").appendChild(el);
  el.scrollIntoView({ behavior: "smooth" });
}
function header(kicker, title, subtitle, actions = "") {
  return `<div class="page-head"><div><div class="eyebrow">${kicker}</div><h1>${title}</h1><p>${subtitle}</p></div><div class="toolbar">${actions}</div></div>`;
}
function card(title, body, side = "") {
  return `<section class="card panel"><div class="section-title"><h2>${title}</h2>${side ? `<span>${side}</span>` : ""}</div>${frameCharts(body)}</section>`;
}
function frameCharts(html) {
  return html.replace(/<svg class="chart"[\s\S]*?<\/svg>/g, (svg) =>
    `<div class="chart-viewport" tabindex="0" role="region" aria-label="Analytical chart · scroll horizontally to inspect">${svg}</div>`);
}
function table(headers, rows) {
  return `<div class="table-wrap"><table class="table"><thead><tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table></div>`;
}
function kpi(label, value, foot, tone = "") {
  return `<div class="card kpi ${tone}"><div class="label">${label}</div><div class="value">${value}</div><div class="foot">${foot}</div></div>`;
}
function lineChart(rows) {
  if (!rows.length)
    return '<div class="empty">No production records supplied in this file.</div>';
  const max = Math.max(1, ...rows.map((r) => r.target)) * 1.12,
    w = 700,
    h = 205,
    p = 28;
  const xs = (i) => p + (i * (w - 2 * p)) / Math.max(1, rows.length - 1);
  const ys = (v) => h - p - (v / max) * (h - 2 * p);
  const path = (key) =>
    rows
      .map(
        (r, i) =>
          (i ? "L" : "M") + xs(i).toFixed(1) + "," + ys(r[key]).toFixed(1),
      )
      .join(" ");
  return `<svg class="chart" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-label="Daily target and actual production"><line x1="${p}" y1="${h - p}" x2="${w - p}" y2="${h - p}" stroke="#dfe6ee"/><path d="${path("target")}" fill="none" stroke="#b4c5d8" stroke-width="2" stroke-dasharray="5 5"/><path d="${path("actual")}" fill="none" stroke="#2b5797" stroke-width="3"/>${rows.map((r, i) => (i % 3 === 0 ? `<text class="chart-label" x="${xs(i)}" y="${h - 6}" text-anchor="middle">${fmt(r.date)}</text>` : "")).join("")}</svg><div class="small muted">● Actual output <span style="color:#b4c5d8;margin-left:15px">– – Target output</span> · units per production day</div>`;
}
function riskTag(days, feasible = true) {
  return !feasible
    ? tag("Blocked", "amber")
    : days > 0
      ? tag(days + "d late", "red")
      : tag("On time", "green");
}
function ordersTable(rows) {
  return rows.length
    ? table(
        [
          "Order",
          "Customer / style",
          "Factory / line",
          "Units",
          "Material",
          "Ship forecast",
          "Deadline",
          "Risk",
        ],
        rows.map(
          (o) =>
            `<tr><td><button class="link" onclick="openOrder(${jsarg(o.id)})">${esc(o.id)}</button></td><td><strong>${esc(o.customer)}</strong><br><span class="muted">${esc(o.style_id)}</span></td><td>${esc(o.plan.factory_id || o.factory_id)} / ${esc(o.plan.line_id || o.line_id)}</td><td>${o.quantity.toLocaleString()}</td><td>${o.material_ready === undefined ? fmt(o.material_date) : tag(o.material_ready ? "Ready" : "Pending", o.material_ready ? "green" : "amber")}<br><span class="muted">${fmt(o.material_release_date || o.material_date)}${o.material_shortage_units ? " · " + o.material_shortage_units + " short" : ""}</span></td><td>${fmt(o.plan.expected_ship)}</td><td>${fmt(o.due_date)}</td><td>${riskTag(o.plan.delay_days, o.plan.feasible)}</td></tr>`,
        ),
      )
    : '<div class="empty">No orders match these filters.</div>';
}
function factoryCards(rows) {
  return rows
    .map(
      (f) =>
        `<div class="factory-card"><div><strong>${esc(f.name)}</strong><small>${esc(f.region)} · ${f.orders} active ${f.orders === 1 ? "order" : "orders"} · ${f.open_incidents} open ${f.open_incidents === 1 ? "exception" : "exceptions"}</small></div><div class="metric" style="color:${f.late ? "#c23732" : "#217346"}">${f.late}<small>at-risk orders</small></div></div>`,
    )
    .join("");
}
function lineLoadChart(rows) {
  if (!rows.length) return '<div class="empty">No line capacity records</div>';
  return (
    rows
      .map(
        (x) =>
          `<div class="line-load"><button class="link" onclick="openLine(${jsarg(x.line_id)})">${esc(x.factory_id)} / ${esc(x.line_id)}</button><div class="bar-track"><div class="bar-fill ${x.at_risk ? "bad" : ""}" style="width:${Math.min(100, x.utilization * 100)}%"></div></div><span class="small">${pct(x.utilization)} · ${x.orders} ${x.orders === 1 ? "order" : "orders"}</span></div>`,
      )
      .join("") +
    '<p class="small muted">Scheduled sewing workload in SMV minutes / available line minutes on scheduled days; subcontracted output is included in workload. Select a line to inspect its orders.</p>'
  );
}
function riskTimeline(rows) {
  if (!rows.length)
    return '<div class="empty">No deadline exposure in this filter.</div>';
  return rows
    .map(
      (x) =>
        `<div class="factory-card clickable" onclick="openDue(${jsarg(x.date)})"><div><strong>${fmt(x.date)}</strong><small>${x.units.toLocaleString()} units exposed</small></div><div>${tag(x.orders + " " + (x.orders === 1 ? "order" : "orders"), "red")}</div></div>`,
    )
    .join("");
}
function openLine(line) {
  state.orderLine = line;
  state.orderRisk = "all";
  go("orders");
}
function openDue(date) {
  state.dueFilter = date;
  state.orderRisk = "risk";
  go("orders");
}
function openRiskOrders() {
  state.orderRisk = "risk";
  go("orders");
}
function openGate(gate) {
  state.orderGate = gate;
  state.orderRisk = "all";
  go("orders");
}
function openActionIncident(id) {
  state.incident = id;
  go("warroom");
}
async function selectFactory(value) {
  state.factoryFilter = value;
  await overview();
}
async function overview() {
  const query =
    state.factoryFilter === "all"
      ? ""
      : "?factory_id=" + encodeURIComponent(state.factoryFilter);
  const [d, v] = await Promise.all([
    api("/overview" + query),
    api("/validation"),
  ]);
  const k = d.kpis;
  state.asOf = d.as_of;
  $("#sidebarDate").textContent =
    "As of " +
    new Date(d.as_of + "T12:00:00").toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    }) +
    " · USD";
  const factorySelect = `<select class="selector" aria-label="Filter factory" onchange="selectFactory(this.value)"><option value="all">All factories</option>${d.factories.map((f) => `<option value="${esc(f.id)}" ${state.factoryFilter === f.id ? "selected" : ""}>${esc(f.name)}</option>`).join("")}</select>`;
  const factoryCards = d.factories
    .map(
      (f) =>
        `<div class="factory-card clickable" onclick="selectFactory(${jsarg(f.id)})"><div><strong>${esc(f.name)}</strong><small>${esc(f.region)} · ${f.orders} active ${f.orders === 1 ? "order" : "orders"} · ${f.open_incidents} open ${f.open_incidents === 1 ? "exception" : "exceptions"}</small></div><div class="metric" style="color:${f.late ? "#c23732" : "#217346"}">${f.late}<small>at-risk / blocked</small></div></div>`,
    )
    .join("");
  const qcd = table(
    [
      "Factory",
      "First-pass yield",
      "Cost / acceptable unit",
      "Forecast OTIF",
      "Orders at risk",
    ],
    d.factories.map(
      (f) =>
        `<tr><td><button class="link" onclick="selectFactory(${jsarg(f.id)})">${esc(f.name)}</button></td><td>${pctOrNA(f.historical_first_pass_yield)}</td><td>${moneyOrNA(f.cost_per_acceptable_unit)}</td><td>${pctOrNA(f.forecast_otif)}</td><td>${f.late} / ${f.orders}</td></tr>`,
    ),
  );
  const readiness = `<div class="factory-card clickable" onclick="openGate('material_pending')"><div><strong>Material pending</strong><small>Fabric or trim release pending, or quantity shortage</small></div><div class="metric">${d.readiness.material_pending}<small>orders</small></div></div><div class="factory-card clickable" onclick="openGate('quality_pending')"><div><strong>Quality release pending</strong><small>${d.readiness.open_holds} open inspection holds</small></div><div class="metric">${d.readiness.quality_pending}<small>orders</small></div></div><p class="small muted">${d.readiness.material_ready} of ${k.active_orders} orders have enough fabric and trims ready.</p>`;
  const actionCards =
    d.actions
      .filter((a) => a.status !== "done")
      .sort((a, b) => a.due_date.localeCompare(b.due_date))
      .slice(0, 5)
      .map(
        (a) =>
          `<div class="factory-card clickable" onclick="openActionIncident(${jsarg(a.incident_id)})"><div><strong>${esc(a.title)}</strong><small>${esc(a.owner)} · ${esc(a.incident_id)} · due ${fmt(a.due_date)}</small></div><div>${tag(a.status, a.due_date < d.as_of ? "red" : "amber")}</div></div>`,
      )
      .join("") || '<div class="empty">No open actions in this filter.</div>';
  const s = d.signals;
  const outcomes = `<div class="detail-grid"><div class="detail-tile"><small>Units on exposed orders</small><strong>${s.late_units.toLocaleString()}</strong></div><div class="detail-tile"><small>Blocked orders</small><strong>${s.blocked_orders}</strong></div><div class="detail-tile"><small>Recorded downtime</small><strong>${s.data_coverage.downtime ? s.downtime_minutes + " min" : "N/A"}</strong></div><div class="detail-tile"><small>Observed absenteeism</small><strong>${pctOrNA(s.absenteeism)}</strong></div></div>${d.comparison ? `<div class="note"><strong>Change from original network:</strong> ${d.comparison.at_risk_delta >= 0 ? "+" : ""}${d.comparison.at_risk_delta} at-risk orders; ${d.comparison.exposed_units_delta >= 0 ? "+" : ""}${d.comparison.exposed_units_delta.toLocaleString()} exposed units.</div>` : ""}<p class="small">${s.top_downtime_cause ? `Top coded downtime cause: <strong>${esc(s.top_downtime_cause)}</strong>. ` : ""}${s.historical_records ? `Recorded rework: <strong>${s.rework_units.toLocaleString()} units</strong>.` : "No historical output records supplied."}</p>`;
  const coverage = `<p class="small"><strong>Input:</strong> ${esc(d.scenario.description)} · ${d.factories.length} factories · ${d.line_load.length} lines · ${k.active_orders} orders</p><p class="small"><strong>Historical evidence:</strong> ${s.data_coverage.production} production records · ${s.data_coverage.downtime} downtime events · ${s.data_coverage.quality_holds} quality holds · ${s.data_coverage.labor} labor records</p>${d.scenario.assumptions?.length ? `<div class="note"><strong>Assumptions applied to this file</strong><ul>${d.scenario.assumptions.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>` : '<p class="small muted">Full scenario data supplied; inspect the downloaded JSON for source records.</p>'}`;
  $("#content").innerHTML =
    header(
      "Network health",
      "Production control tower",
      "Move from a network exception to its order, constraint, owner, and recovery decision.",
      factorySelect +
        `<button class="secondary" onclick="openRiskOrders()">At-risk orders →</button>`,
    ) +
    `<p class="scenario-note">${esc(d.scenario.name)} · ${d.synthetic ? "Synthetic figures" : "Uploaded source data"} · as of ${fmt(d.as_of)} · USD</p>` +
    `<div class="insight"><div class="icon">✦</div><div><strong>Management focus</strong><p>${esc(d.insight)}</p></div></div>` +
    `<div class="kpi-grid">${kpi("Active orders", k.active_orders, "Current filter")}${kpi("At risk / blocked", k.at_risk, "Open the order book", "alert")}${kpi("Forecast OTIF", pct(k.forecast_otif), "Orders on time and in full", "good")}${kpi("First-pass yield", pctOrNA(k.first_pass_yield), k.first_pass_yield === null ? "No production records" : "Acceptable / produced")}${kpi("Schedule adherence", pctOrNA(k.schedule_adherence), k.schedule_adherence === null ? "No production targets" : "Actual / daily target")}${kpi("Open exceptions", k.open_incidents, k.overdue_actions + " overdue actions", "alert")}</div>` +
    `<div class="grid-two">${card("Results from this file", outcomes, "Forecast and observed evidence")}${card("Data coverage and assumptions", coverage, "Source transparency")}</div>` +
    `<div class="grid-two">${card("Production output versus target", lineChart(d.trend), "Last 14 production days")}${card("Factory exposure — select to filter", factoryCards, "Forecast status")}</div>` +
    `<div class="grid-two">${card("Line load exposes the sewing bottlenecks", lineLoadChart(d.line_load), "Select a line")}${card("Shipment deadlines with exposed units", riskTimeline(d.risk_timeline), "Select a due date")}</div>` +
    card(
      "Factory quality, cost, and delivery",
      qcd,
      "Select a factory to filter the tower",
    ) +
    `<div class="grid-two">${card("Material and quality release gates", readiness, "Select a gate to inspect orders")}${card("Response owners and due dates", actionCards, "Select an action to open the war room")}</div>` +
    card(
      "Highest-priority orders needing intervention",
      ordersTable(d.priority_orders),
      `Top ${d.priority_orders.length} of ${k.at_risk}; open the order book for all`,
    ) +
    `<div style="height:18px"></div>` +
    card(
      "Planning rules produce different QCD outcomes",
      table(
        [
          "Dispatch rule",
          "Late orders",
          "Forecast OTIF",
          "Operating + delivery exposure",
          "Plan changes",
          "Constraint breaches",
        ],
        v.benchmarks.map(
          (b) =>
            `<tr><td><strong>${esc(b.method)}</strong></td><td>${b.late_orders}</td><td>${pct(b.forecast_otif)}</td><td>${money(b.estimated_cost)}</td><td>${b.plan_changes}</td><td>${b.constraint_violations}</td></tr>`,
        ),
      ) + `<p class="small muted">${esc(v.note)}</p>`,
      "Selected-file rule comparison",
    );
}
async function orders() {
  const rows = await api("/orders");
  state.orders = rows;
  const factories = [
    ...new Set(rows.map((x) => x.plan.factory_id || x.factory_id)),
  ].sort();
  const lines = [
    ...new Set(rows.map((x) => x.plan.line_id || x.line_id)),
  ].sort();
  $("#content").innerHTML =
    header(
      "Planning workspace",
      "Order portfolio",
      "Filter the order book, inspect release gates, and compare valid factory and line assignments.",
      `<button class="secondary" onclick="downloadReport('orders.csv')">↓ Download forecast CSV</button>`,
    ) +
    `<div class="filter-row"><input id="orderSearch" type="search" placeholder="Search order, customer, or style" value="${esc(state.orderSearch)}" oninput="filterOrders()"><select class="selector" id="orderFactory" onchange="filterOrders()"><option value="all">All factories</option>${factories.map((f) => `<option value="${esc(f)}">${esc(f)}</option>`).join("")}</select><select class="selector" id="orderLine" onchange="filterOrders()"><option value="all">All lines</option>${lines.map((l) => `<option value="${esc(l)}">${esc(l)}</option>`).join("")}</select><select class="selector" id="orderFilter" onchange="filterOrders()"><option value="all">All statuses</option><option value="risk">At risk / blocked</option><option value="late">Forecast late</option><option value="blocked">No feasible plan</option><option value="ontime">On time</option></select><select class="selector" id="orderGate" onchange="filterOrders()"><option value="all">All release gates</option><option value="material_pending">Material pending</option><option value="quality_pending">Quality pending</option></select>${state.dueFilter ? `<button class="secondary" onclick="state.dueFilter=null;filterOrders()">Due ${fmt(state.dueFilter)} ×</button>` : ""}</div>` +
    card(
      "Production order book",
      `<div id="ordersTable"></div>`,
      `<span id="orderCount">${rows.length}</span> shown of ${rows.length}`,
    );
  $("#orderFactory").value = state.orderFactory || "all";
  $("#orderLine").value = state.orderLine || "all";
  $("#orderFilter").value = state.orderRisk || "all";
  $("#orderGate").value = state.orderGate || "all";
  filterOrders();
}
function filterOrders() {
  const search = ($("#orderSearch")?.value || "").trim().toLowerCase();
  const factory = $("#orderFactory")?.value || "all";
  const line = $("#orderLine")?.value || "all";
  const risk = $("#orderFilter")?.value || "all";
  const gate = $("#orderGate")?.value || "all";
  state.orderSearch = search;
  state.orderFactory = factory;
  state.orderLine = line;
  state.orderRisk = risk;
  state.orderGate = gate;
  const matches = state.orders.filter((o) => {
    const p = o.plan;
    const blocked = !p.feasible;
    const late = p.feasible && p.delay_days > 0;
    return (
      (!search ||
        [o.id, o.customer, o.style_id].some((x) =>
          x.toLowerCase().includes(search),
        )) &&
      (factory === "all" || (p.factory_id || o.factory_id) === factory) &&
      (line === "all" || (p.line_id || o.line_id) === line) &&
      (gate === "all" ||
        (gate === "material_pending" && !o.material_ready) ||
        (gate === "quality_pending" && o.quality_pending)) &&
      (!state.dueFilter || o.due_date === state.dueFilter) &&
      (risk === "all" ||
        (risk === "risk" && (blocked || late)) ||
        (risk === "late" && late) ||
        (risk === "blocked" && blocked) ||
        (risk === "ontime" && !blocked && !late))
    );
  });
  $("#ordersTable").innerHTML = ordersTable(matches);
  $("#orderCount").textContent = matches.length;
}
async function openOrder(id) {
  state.order = id;
  go("orderDetail");
}
async function orderDetail() {
  const d = await api("/order?order_id=" + encodeURIComponent(state.order));
  const candidates = await api(
    "/allocation?order_id=" + encodeURIComponent(state.order),
  );
  const o = d.order,
    p = d.plan,
    s = d.style;
  const blocked = !p.feasible;
  const path = blocked
    ? `<div class="insight"><div class="icon">!</div><div><strong>No feasible schedule on the assigned line</strong><p>${esc(p.reason)}. Resolve the constraint, then review compatible alternatives below.</p></div></div>`
    : `<div class="timeline">${[
        ["Material", o.material_date],
        ["Cutting", p.cut_complete],
        ["Sewing", p.sewing_complete],
        ["Finishing", p.finishing],
        ["Inspection", p.inspection],
        ["Packing", p.packing],
        ["Shipment", p.expected_ship],
      ]
        .map(
          ([name, day]) =>
            `<div class="${name === "Shipment" && p.delay_days ? "bad" : ""}"><strong>${name}</strong><br>${fmt(day)}</div>`,
        )
        .join(
          "",
        )}</div><p class="note">Bottleneck: ${esc(s.bottleneck)} · SMV ${s.smv} minutes · sewing utilization ${pct(p.capacity_utilization)}. The schedule uses the selected file’s calendar and stage capacities.</p>${table(
        ["Production date", "Planned units", "Available capacity"],
        p.daily.map(
          (x) =>
            `<tr><td>${fmt(x.date)}</td><td>${x.units}</td><td>${x.capacity}</td></tr>`,
        ),
      )}`;
  $("#content").innerHTML =
    header(
      "Order detail",
      esc(o.id),
      `${esc(o.customer)} · ${esc(s.name)} · ${o.quantity.toLocaleString()} units`,
      `<button class="secondary" onclick="go('orders')">← Back to orders</button>`,
    ) +
    `<div class="detail-grid"><div class="detail-tile"><small>Planned line</small><strong>${esc(p.factory_id || o.factory_id)} / ${esc(p.line_id || o.line_id)}</strong></div><div class="detail-tile"><small>Material gate</small><strong>${d.material.shortage_units ? d.material.shortage_units + " units short" : fmt(d.material.fabric_ready > d.material.trims_ready ? d.material.fabric_ready : d.material.trims_ready)}</strong></div><div class="detail-tile"><small>Expected shipment</small><strong>${blocked ? "Blocked" : fmt(p.expected_ship)}</strong></div><div class="detail-tile"><small>Customer deadline</small><strong>${fmt(o.due_date)} ${riskTag(p.delay_days, p.feasible)}</strong></div></div>` +
    `<div class="grid-two">${card("Capacity-constrained production path", path, "Cut → sew → finish → inspect → pack")}${card("Style & release evidence", `<div class="small muted">${esc(s.category.toUpperCase())} · Required machine: ${esc(s.machine)} · Quality release: ${o.quality_release && !d.quality_holds.some((h) => h.status === "open") ? "cleared" : "hold pending"}</div>${s.operations.map(([name, smv]) => `<div class="bar-row"><span>${esc(name)}</span><div class="bar-track"><div class="bar-fill" style="width:${(smv / Math.max(...s.operations.map((x) => x[1]))) * 100}%"></div></div><strong>${smv}m</strong></div>`).join("")}${d.quality_holds.length ? `<div class="note">Quality holds: ${d.quality_holds.map((h) => esc(h.cause) + " (" + h.hours + " h, " + h.status + ")").join("; ")}</div>` : ""}`, "Operation sequence")}</div>` +
    card(
      "Allocation alternatives",
      table(
        [
          "Factory / line",
          "Feasibility",
          "Expected ship",
          "Delay",
          "Explanation",
        ],
        candidates.map(
          (c) =>
            `<tr><td><strong>${esc(c.factory_id)} / ${esc(c.line_id)}</strong></td><td>${c.feasible ? tag("Feasible", "green") : tag("Rejected", "red")}</td><td>${c.feasible ? fmt(c.expected_ship) : "—"}</td><td>${c.feasible ? c.delay_days + "d" : "—"}</td><td>${c.feasible ? "Score " + c.score + " · " + c.changeover_hours + " h changeover" : esc(c.reasons.join("; "))}</td></tr>`,
        ),
      ),
      "Compatibility, capacity, reliability, cost",
    );
}
async function investigate() {
  const list = await api("/incidents");
  const items = list.length
    ? list
        .map(
          (i) =>
            `<div class="factory-card"><div><button class="link" onclick="state.incident=${jsarg(i.id)};go('incidentDetail')">${esc(i.title)}</button><small>${esc(i.id)} · ${i.source === "derived" ? "Modeled forecast · " : ""}${esc(i.factory_id)} / ${esc(i.line_id)} · ${esc(i.order_id)} · owner ${esc(i.owner)}</small></div><div>${tag(i.severity, i.severity === "critical" ? "red" : "amber")} ${tag(i.status, i.status === "closed" ? "green" : "amber")}</div></div>`,
        )
        .join("")
    : '<div class="empty">No incidents are recorded in this scenario.</div>';
  const exposure = list.length
    ? table(
        [
          "Incident",
          "Lost capacity",
          "Recovery deadline",
          "Expected delay",
          "Exposure",
        ],
        list.map(
          (i) =>
            `<tr><td><button class="link" onclick="state.incident=${jsarg(i.id)};go('incidentDetail')">${esc(i.id)}</button></td><td>${i.impact.lost_capacity_units === null ? "N/A" : i.impact.lost_capacity_units + " units"}</td><td>${fmt(i.impact.recovery_deadline)}</td><td>${i.impact.expected_delay_days === null ? "N/A · blocked" : i.impact.expected_delay_days + "d"}</td><td>${money(i.impact.commercial_exposure)}</td></tr>`,
        ),
      )
    : '<div class="empty">Impact estimates appear when an incident is recorded.</div>';
  $("#content").innerHTML =
    header(
      "Exception management",
      "Disruption intelligence",
      "Inspect affected orders, lost capacity, recovery deadlines, cause evidence, and the response owner.",
      `<button class="secondary" onclick="go('recovery')">Compare recovery →</button>`,
    ) +
    `<div class="grid-two">${card("Incident and forecast-risk register", items, "Select to investigate")}${card("Exposure by exception", exposure, "Illustrative estimate")}</div><div class="note">Feasible shipment forecasts use an illustrative ±2-day range; blocked orders have no shipment range until the gate clears. Open the cause record before treating a recurring pattern as causal evidence.</div>`;
}
async function incidentDetail() {
  const d = await api(
    "/incident?incident_id=" + encodeURIComponent(state.incident),
  );
  const i = d.incident,
    o = d.order;
  const total = d.pareto.reduce((x, p) => x + p.minutes, 0);
  $("#content").innerHTML =
    header(
      "Root-cause investigation",
      esc(i.id),
      esc(i.title),
      `<button class="secondary" onclick="go('investigate')">← All incidents</button><button class="primary" onclick="go('recovery')">Build recovery plan →</button>`,
    ) +
    `<div class="detail-grid"><div class="detail-tile"><small>Affected order</small><strong>${esc(o.id)}</strong></div><div class="detail-tile"><small>Factory / line</small><strong>${esc(i.factory_id)} / ${esc(i.line_id)}</strong></div><div class="detail-tile"><small>Lost minutes</small><strong>${i.lost_minutes ?? "N/A"}</strong></div><div class="detail-tile"><small>Cause confidence</small><strong>${tag(d.cause_status, d.cause_status === "verified" ? "green" : "amber")}</strong></div></div><div class="grid-two">${card(d.pareto.length ? "Largest recorded downtime causes" : "Cause-frequency evidence pending", d.pareto.length ? d.pareto.map((x, n) => `<div class="bar-row"><span>${esc(x.cause)}</span><div class="bar-track"><div class="bar-fill ${n === 0 ? "bad" : ""}" style="width:${x.share * 100}%"></div></div><strong>${pct(x.share)}</strong></div>`).join("") + `<p class="small muted">${total} minutes across ${d.recurrence.observed_production_days} production days; causal status requires separate verification.</p>` : '<div class="empty">This incident has no cause-coded downtime series. Collect comparable events before constructing a Pareto chart.</div>', "Pareto by lost minutes")}${card(i.verified_root_cause ? "Verified cause and evidence" : "Cause investigation pending", `<p><strong>Symptom:</strong> ${esc(i.title)}</p><p><strong>Immediate cause:</strong> ${esc(i.immediate_cause)}</p><p><strong>Root cause:</strong> ${i.verified_root_cause ? esc(i.verified_root_cause) : tag("Unverified hypothesis", "amber")}</p><div class="note"><strong>Evidence:</strong> ${esc(i.evidence)}<br><strong>Verification:</strong> ${esc(i.verification || "Pending investigation")}</div>`, "Association is not proof")}</div><div class="grid-two">${card("Five Whys", d.whys.map((w, n) => `<div class="step"><div class="step-num">${n + 1}</div><p>${esc(w)}</p></div>`).join(""), "Structured cause chain")}${card(
      "Fishbone evidence map",
      Object.entries(d.fishbone)
        .map(
          ([group, items]) =>
            `<div class="factory-card"><div><strong>${esc(group)}</strong><small>${items.map(esc).join("; ")}</small></div></div>`,
        )
        .join(""),
      "Unverified branches remain hypotheses",
    )}</div>${
      d.downtime.length
        ? card(
            "Downtime event log",
            table(
              ["Date", "Machine", "Cause", "Minutes", "Shift"],
              d.downtime
                .slice(-12)
                .reverse()
                .map(
                  (x) =>
                    `<tr><td>${fmt(x.date)}</td><td>${esc(x.machine)}</td><td>${esc(x.cause)}</td><td>${x.minutes}</td><td>${esc(x.shift)}</td></tr>`,
                ),
            ),
            "Source records",
          )
        : ""
    }`;
}

async function recovery() {
  const incidents = await api("/incidents");
  if (!incidents.length) {
    $("#content").innerHTML =
      header(
        "Scenario planning",
        "Recovery studio",
        "No incident has been recorded for this scenario.",
      ) +
      '<div class="empty card panel">Add an incident to the uploaded scenario to compare response plans.</div>';
    return;
  }
  const selected =
    incidents.find((x) => x.id === state.incident) || incidents[0];
  state.incident = selected.id;
  const options = await api(
    "/incident/options?incident_id=" + encodeURIComponent(state.incident),
  );
  state.options = options;
  const current = options.find((x) => x.id === "baseline");
  const viable = options.filter((x) => x.feasible && x.id !== "baseline");
  const best = viable[0];
  const incidentSelect = `<select class="selector" id="incidentSelect" onchange="state.incident=this.value;state.option=null;go('recovery')">${incidents.map((x) => `<option value="${esc(x.id)}" ${x.id === state.incident ? "selected" : ""}>${esc(x.id)} · ${esc(x.order_id)}</option>`).join("")}</select>`;
  const focus = best
    ? `<strong>${esc(best.name)} has the lowest modeled total impact</strong><p>${current?.feasible ? `Current plan: ${fmt(current.expected_ship)}, ${pct(current.on_time_probability)} full-order on-time chance, ${money(current.expected_total_impact)} expected impact.` : `Current plan blocked: ${esc(current?.reasons?.join("; ") || "no feasible schedule")}.`} Confirm customer and factory commitments before approval.</p>`
    : `<strong>No feasible recovery can be committed</strong><p>${esc(current?.reasons?.join("; ") || "The current assignment is blocked")}. Resolve the blocking constraint and rerun the options.</p>`;
  const cards = options
    .map(
      (o) =>
        `<div class="option ${!o.feasible ? "disabled" : ""} ${state.option === o.id ? "selected" : ""}"><div class="option-head"><h3>${esc(o.name)}</h3>${o.feasible ? tag(o.delay_days ? o.delay_days + "d late" : "On time", o.delay_days ? "red" : "green") : tag("Infeasible", "red")}</div><p>${esc(o.feasible ? o.detail : o.reasons?.join("; ") || o.detail)}</p>${o.feasible ? `<div class="option-metrics"><div><small>Ship date</small><strong>${fmt(o.expected_ship)}</strong></div><div><small>Full-order on-time</small><strong>${pct(o.on_time_probability)}</strong></div><div><small>Total impact</small><strong>${money(o.expected_total_impact)}</strong></div><div><small>Extra spend</small><strong>${money(o.additional_cost)}</strong></div><div><small>Quality risk</small><strong>${pct(o.quality_risk)}</strong></div><div><small>Lead time</small><strong>${o.implementation_days}d</strong></div></div><div class="meta">${esc(o.capacity_requirement)} · ${esc(o.labor)}<br>Other orders affected: ${o.affected_other_orders.length} · ${esc(o.compliance)}${o.partial_on_time_probability ? `<br>First-tranche on-time chance: ${pct(o.partial_on_time_probability)}` : ""}</div><button class="${state.option === o.id ? "secondary" : "primary"}" onclick="selectOption(${jsarg(o.id)})">${state.option === o.id ? "Selected" : "Select this plan"}</button>` : ""}</div>`,
    )
    .join("");
  const breakdown = best
    ? table(
        [
          "Scenario",
          "Extra spend",
          "Late penalty",
          "Margin exposure",
          "Quality + displacement",
          "Total",
        ],
        options
          .filter((x) => x.feasible)
          .map(
            (x) =>
              `<tr><td><strong>${esc(x.name)}</strong></td><td>${money(x.additional_cost)}</td><td>${money(x.expected_late_penalty)}</td><td>${money(x.expected_margin_exposure)}</td><td>${money(x.expected_quality_cost + x.other_order_cost)}</td><td><strong>${money(x.expected_total_impact)}</strong></td></tr>`,
          ),
      )
    : '<div class="empty">No cost comparison is valid until the blocking constraint is resolved.</div>';
  const form =
    best && !["closed", "resolved"].includes(selected.status)
      ? card(
          "Approve and record a factory commitment",
          `<form id="decisionForm" onsubmit="submitDecision(event)"><div class="form-row"><div class="field"><label>Selected plan</label><input id="selectedPlan" value="${esc(state.option || "Select a plan above")}" disabled></div><div class="field"><label>Approver</label><input name="approver" required placeholder="Production manager"></div><div class="field"><label>Factory owner</label><input name="factory_owner" required placeholder="Factory general manager"></div><div class="field"><label>Commitment due</label><input name="due_date" type="date" min="${esc(state.asOf || selected.detected_at)}" value="${esc(state.asOf || selected.detected_at)}" required></div></div><div class="form-row"><div class="field"><label>Decision rationale</label><textarea name="rationale" required minlength="10" placeholder="Why this option best balances quality, cost, and delivery"></textarea></div><div class="field"><label>Written factory commitment</label><textarea name="commitment" required minlength="10" placeholder="Capacity, output, handoff, and delivery commitment"></textarea></div></div><button class="primary" type="submit">Record approved plan</button></form>`,
          "Decision audit trail",
        )
      : "";
  $("#content").innerHTML =
    header(
      "Scenario planning",
      "Recovery studio",
      "Compare feasibility, expected financial impact, quality exposure, and displaced work.",
      incidentSelect,
    ) +
    `<div class="insight"><div class="icon">↗</div><div>${focus}</div></div><div class="option-grid">${cards}</div>` +
    `<div class="grid-two">${card("Commercial breakdown", breakdown, "USD · expected values")}${card("Commitment and uncertainty", `<p class="small">Each plan requires: <strong>${esc((options.find((x) => x.id === state.option) || best)?.factory_commitment || "Resolve constraints first")}</strong></p><div class="note">Feasible plans use an illustrative ±2-day forecast range and 1.8-day standard deviation. Quality risk uses the factory quality input or documented default, plus any option premium.</div><p class="small muted">Rejected alternatives are stored with the decision rationale. Split shipment needs customer acceptance; subcontracting needs a compliant supplier.</p>`, "Assumptions visible")}</div>${form}`;
}
function selectOption(id) {
  state.option = id;
  recovery();
}
async function submitDecision(event) {
  event.preventDefault();
  if (!state.option) {
    toast("Select a feasible plan first");
    return;
  }
  const f = new FormData(event.target);
  try {
    const r = await api("/decisions", {
      method: "POST",
      body: JSON.stringify({
        incident_id: state.incident,
        option_id: state.option,
        rationale: f.get("rationale"),
        approver: f.get("approver"),
        factory_owner: f.get("factory_owner"),
        commitment: f.get("commitment"),
        due_date: f.get("due_date"),
      }),
    });
    toast("Decision #" + r.decision_id + " and factory commitment recorded");
    go("warroom");
  } catch (e) {
    toast(e.message);
  }
}
async function warroom() {
  const [incidents, allActions] = await Promise.all([
    api("/incidents"),
    api("/actions"),
  ]);
  if (!incidents.length) {
    $("#content").innerHTML =
      header(
        "Response execution",
        "Execution workspace",
        "No incident is recorded for this scenario.",
      ) +
      '<div class="empty card panel">Upload an incident history to use the action board.</div>';
    return;
  }
  const selected =
    incidents.find((x) => x.id === state.incident) || incidents[0];
  state.incident = selected.id;
  const detail = await api(
    "/incident?incident_id=" + encodeURIComponent(state.incident),
  );
  const actions = allActions.filter((x) => x.incident_id === state.incident);
  const blocked = actions.filter((x) => x.blocked);
  const selector = `<select class="selector" onchange="state.incident=this.value;go('warroom')">${incidents.map((x) => `<option value="${esc(x.id)}" ${x.id === state.incident ? "selected" : ""}>${esc(x.id)} · ${esc(x.order_id)}</option>`).join("")}</select>`;
  const actionRows = actions.map(
    (a) =>
      `<tr><td><strong>${esc(a.title)}</strong><br><span class="muted">${esc(a.id)} ${a.dependency ? "· after " + esc(a.dependency) : ""}</span></td><td>${esc(a.owner)}<br><span class="muted">C: ${esc(a.consulted)} · I: ${esc(a.informed)}</span></td><td>${esc(a.accountable)}</td><td>${fmt(a.due_date)}</td><td>${tag(a.status, a.status === "done" ? "green" : a.overdue ? "red" : "amber")}</td><td><button class="link" onclick="actionPrompt(${jsarg(a.id)})">Update</button></td></tr>`,
  );
  const commitmentCards = detail.commitments.length
    ? detail.commitments
        .map(
          (c) =>
            `<div class="factory-card"><div><strong>${esc(c.commitment)}</strong><small>${esc(c.factory_owner)} · due ${fmt(c.due_date)} · decision #${c.decision_id}</small></div><div>${tag(c.status, c.status === "fulfilled" ? "green" : c.status === "missed" ? "red" : "amber")}<br><button class="link small" onclick="commitmentPrompt(${c.id})">Update</button></div></div>`,
        )
        .join("")
    : '<div class="empty">No plan approved yet. Select a recovery option and record a commitment.</div>';
  $("#content").innerHTML =
    header(
      "Response execution",
      "Execution workspace",
      "Track the selected incident’s critical path, RACI owners, and factory commitments.",
      selector +
        `<button class="secondary" onclick="go('recovery')">Review recovery</button>`,
    ) +
    `<div class="kpi-grid">${kpi("Open actions", actions.filter((x) => x.status !== "done").length, "For " + state.incident)}${kpi("Blocked actions", blocked.length, "Waiting for prerequisite", "alert")}${kpi("Overdue actions", actions.filter((x) => x.overdue).length, "Escalate to accountable owner", "alert")}${kpi("Recorded decisions", detail.decisions.length, "Approval history")}${kpi("Factory commitments", detail.commitments.length, "Written and trackable")}${kpi("Incident owner", esc(detail.incident.owner), "Escalation point")}</div>` +
    (blocked.length
      ? `<div class="insight"><div class="icon">!</div><div><strong>Critical path: ${esc(blocked[0].dependency)} blocks ${esc(blocked[0].id)}</strong><p>${esc(blocked[0].owner)} needs the prerequisite closed before this action can finish.</p></div></div>`
      : "") +
    `<div class="grid-two">${card("RACI action board", actionRows.length ? table(["Action / dependency", "Responsible · C / I", "Accountable", "Due", "Status", "Update"], actionRows) : '<div class="empty">No actions for this incident.</div>', "Owner and dependency")}${card("Factory commitments", commitmentCards, "Promise versus fulfillment")}</div>` +
    card(
      "Decision history and rejected alternatives",
      detail.decisions.length
        ? table(
            [
              "Decision",
              "Plan",
              "Approver",
              "Rationale",
              "Alternatives retained",
            ],
            detail.decisions.map(
              (x) =>
                `<tr><td>#${x.id}</td><td>${esc(x.option_id)}</td><td>${esc(x.approver)}</td><td>${esc(x.rationale)}</td><td>${JSON.parse(x.alternatives).length}</td></tr>`,
            ),
          )
        : '<div class="empty">Decisions appear after approval.</div>',
      "Scenario-scoped record",
    );
}
async function actionPrompt(id) {
  const status = prompt(
    "New status: open, in_progress, done, or blocked",
    "done",
  );
  if (status === null) return;
  const evidence = prompt("Evidence or update note (required)");
  if (evidence === null) return;
  try {
    await api("/action?action_id=" + encodeURIComponent(id), {
      method: "PATCH",
      body: JSON.stringify({ status, evidence }),
    });
    toast("Action updated");
    warroom();
  } catch (e) {
    toast(e.message);
  }
}
async function commitmentPrompt(id) {
  const status = prompt(
    "Commitment status: open, fulfilled, or missed",
    "fulfilled",
  );
  if (status === null) return;
  let actual_date = null;
  if (status === "fulfilled") {
    actual_date = prompt(
      "Actual fulfillment date (YYYY-MM-DD)",
      state.asOf || new Date().toISOString().slice(0, 10),
    );
    if (actual_date === null) return;
  }
  try {
    await api("/commitments/" + id, {
      method: "PATCH",
      body: JSON.stringify({ status, actual_date }),
    });
    toast("Commitment updated");
    warroom();
  } catch (e) {
    toast(e.message);
  }
}
async function improvement() {
  const incidents = await api("/incidents");
  if (!incidents.length) {
    $("#content").innerHTML =
      header(
        "Continuous improvement",
        "Continuous improvement",
        "No incident is recorded for this scenario.",
      ) +
      '<div class="empty card panel">Upload incident and action histories to start a PDCA cycle.</div>';
    return;
  }
  const selected =
    incidents.find((x) => x.id === state.incident) || incidents[0];
  state.incident = selected.id;
  const [d, allRules] = await Promise.all([
    api("/improvement?incident_id=" + encodeURIComponent(state.incident)),
    api("/rules"),
  ]);
  const rules = allRules.filter((x) => x.incident_id === state.incident);
  state.improvementBaseline = d.baseline.events_per_day;
  const selector = `<select class="selector" onchange="state.incident=this.value;go('improvement')">${incidents.map((x) => `<option value="${esc(x.id)}" ${x.id === state.incident ? "selected" : ""}>${esc(x.id)} · ${esc(x.order_id)}</option>`).join("")}</select>`;
  const ruleCards = rules
    .map(
      (r) =>
        `<div class="factory-card"><div><strong>${esc(r.rule_key)} · ${esc(r.old_value)} → ${esc(r.proposed_value)}</strong><small>${esc(r.reason)}</small></div><div>${tag(r.status, r.status === "approved" ? "green" : "amber")}${r.status === "pending" ? `<br><button class="link small" onclick="rulePrompt(${r.id})">Review</button>` : ""}</div></div>`,
    )
    .join("");
  $("#content").innerHTML =
    header(
      "Continuous improvement",
      "Continuous improvement",
      "Compare outcomes against a line-specific baseline and keep planning-rule changes under management approval.",
      selector,
    ) +
    `<div class="insight"><div class="icon">◎</div><div><strong>${esc(d.assessment)}</strong><p>${d.baseline.events_per_day === null ? "No downtime recurrence baseline applies." : "Baseline " + d.baseline.events_per_day + " downtime events per day on " + esc(d.baseline.line) + "."} Comparable output is ${d.baseline.daily_volume ?? "N/A"} units/day at ${d.baseline.style_smv} SMV. ${d.comparable_checks || 0} comparable checks recorded.</p></div></div>` +
    `<div class="grid-two">${card("Plan → Do → Check → Act", `<div class="step"><div class="step-num">1</div><p><strong>Plan:</strong> ${d.targets.events_per_day === null ? "Define a measure and baseline appropriate to this incident." : "Establish the cause and baseline; target at most " + d.targets.events_per_day + " downtime events per production day."}</p></div><div class="step"><div class="step-num">2</div><p><strong>Do:</strong> Pilot the intervention and record resources, deviations, and output.</p></div><div class="step"><div class="step-num">3</div><p><strong>Check:</strong> Compare at 30, 60, and 90 days. Volume must be within 20% and style SMV within 10% of baseline for a preliminary comparison.</p></div><div class="step"><div class="step-num">4</div><p><strong>Act:</strong> Standardize only after sustained evidence and management approval.</p></div><div class="note">A pre/post difference is an observation. Alternative causes and persistence still need review.</div>`, "Evidence-based verification")}${card("Record a PDCA observation", `<form onsubmit="submitPDCA(event)"><div class="form-row"><div class="field"><label>Stage</label><select name="stage"><option>plan</option><option>do</option><option>check</option><option>act</option></select></div><div class="field"><label>Observed events / day</label><input name="observed" type="number" step="0.01" min="0" placeholder="${d.targets.events_per_day ?? "No baseline"}"></div><div class="field"><label>Daily volume · units</label><input name="volume" type="number" min="0" placeholder="${d.baseline.daily_volume ?? "No baseline"}"></div><div class="field"><label>Average style SMV</label><input name="complexity" type="number" step="0.1" min="0" placeholder="${d.baseline.style_smv}"></div></div><div class="field"><label>Observation and evidence</label><textarea name="observation" required minlength="8" placeholder="Describe pilot dates, output, evidence, and unintended QCD effects"></textarea></div><button class="primary">Record observation</button></form>`, "Check requires outcome + context")}</div>` +
    `<div class="grid-two">${card(
      "Observation history",
      d.records.length
        ? table(
            ["Stage", "Observed", "Volume", "SMV", "Observation"],
            d.records.map(
              (x) =>
                `<tr><td>${tag(x.stage, "blue")}</td><td>${x.observed ?? "—"}</td><td>${x.volume ?? "—"}</td><td>${x.complexity ?? "—"}</td><td>${esc(x.observation)}</td></tr>`,
            ),
          )
        : '<div class="empty">Pilot and follow-up observations will appear here.</div>',
      "30 / 60 / 90-day checkpoints",
    )}${card("Planning-rule proposals", `<form onsubmit="submitRule(event)"><div class="form-row"><div class="field"><label>Rule key</label><input name="rule_key" required value="${esc(d.baseline.line)}_${d.baseline.events_per_day === null ? "capacity_factor" : "downtime_factor"}"></div><div class="field"><label>Current value</label><input name="old_value" required placeholder="Enter current approved value"></div><div class="field"><label>Proposed value</label><input name="proposed_value" required placeholder="Enter proposed value"></div></div><div class="field"><label>Evidence and reason</label><textarea name="reason" required minlength="10" placeholder="Explain verified results and why the assumption should change"></textarea></div><button class="primary">Propose rule</button></form>${ruleCards ? `<hr style="border:0;border-top:1px solid #e4eaf0;margin:18px 0">${ruleCards}` : ""}`, "Management sign-off")}</div>`;
}
async function submitPDCA(event) {
  event.preventDefault();
  const f = new FormData(event.target);
  const n = (x) => (f.get(x) === "" ? null : Number(f.get(x)));
  try {
    await api("/improvement", {
      method: "POST",
      body: JSON.stringify({
        incident_id: state.incident,
        stage: f.get("stage"),
        baseline: state.improvementBaseline,
        observed: n("observed"),
        volume: n("volume"),
        complexity: n("complexity"),
        observation: f.get("observation"),
      }),
    });
    toast("PDCA observation recorded");
    improvement();
  } catch (e) {
    toast(e.message);
  }
}
async function submitRule(event) {
  event.preventDefault();
  const f = new FormData(event.target);
  try {
    await api("/rules", {
      method: "POST",
      body: JSON.stringify({
        incident_id: state.incident,
        rule_key: f.get("rule_key"),
        old_value: f.get("old_value"),
        proposed_value: f.get("proposed_value"),
        reason: f.get("reason"),
      }),
    });
    toast("Rule submitted for management approval");
    improvement();
  } catch (e) {
    toast(e.message);
  }
}
async function rulePrompt(id) {
  const approver = prompt("Management approver name");
  if (!approver) return;
  const approve = confirm(
    "Approve this proposed planning rule? Cancel rejects it.",
  );
  try {
    await api("/rules/" + id, {
      method: "PATCH",
      body: JSON.stringify({ approver, approve }),
    });
    toast("Rule review recorded");
    improvement();
  } catch (e) {
    toast(e.message);
  }
}
const pages = {
  overview,
  orders,
  orderDetail,
  investigate,
  incidentDetail,
  recovery,
  warroom,
  improvement,
};
async function go(page) {
  state.page = page;
  document
    .querySelectorAll("#nav button")
    .forEach((b) =>
      b.classList.toggle(
        "active",
        b.dataset.page === page ||
          (page === "orderDetail" && b.dataset.page === "orders") ||
          (page === "incidentDetail" && b.dataset.page === "investigate"),
      ),
    );
  $("#crumb-current").textContent = {
    overview: "CONTROL TOWER",
    orders: "ORDERS & ALLOCATION",
    orderDetail: "ORDER DETAIL",
    investigate: "DISRUPTION LAB",
    incidentDetail: "ROOT CAUSE",
    recovery: "RECOVERY SIMULATOR",
    warroom: "PRODUCTION WAR ROOM",
    improvement: "PDCA & LEARNING",
  }[page];
  $("#content").innerHTML =
    '<div class="loading">Loading operational model…</div>';
  try {
    await pages[page]();
  } catch (e) {
    $("#content").innerHTML =
      `<div class="card panel"><h2>Could not load this view</h2><p>${esc(e.message)}</p></div>`;
    console.error(e);
  }
  window.scrollTo(0, 0);
}
