/* PlantCore desktop workspace. All chart marks derive from the active API snapshot. */
const palette = {
  navy: "#3d5a80",
  teal: "#3d7d78",
  amber: "#ee6c4d",
  red: "#c65345",
  slate: "#98c1d9",
  pale: "#d7e1e8",
};
const num = (n) =>
  Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 0 });
const emptyChart = (text) => `<div class="empty">${esc(text)}</div>`;
const legend = (items) =>
  `<div class="legend">${items.map(([name, color]) => `<span><i style="background:${color}"></i>${esc(name)}</span>`).join("")}</div>`;
let navigation = 0,
  requestController = new AbortController();
api = async function (path, options = {}) {
  const epoch = navigation;
  const r = await fetch("/api" + path, {
    signal: requestController.signal,
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await r.json();
  if (epoch !== navigation)
    throw new DOMException("View changed", "AbortError");
  if (!r.ok)
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : body.detail?.map((x) => x.loc.at(-1) + ": " + x.msg).join("; ") ||
            "Request failed",
    );
  return body;
};
function saveWorkspace() {
  try {
    sessionStorage.setItem(
      "plantcore-workspace",
      JSON.stringify({
        page: state.page,
        incident: state.incident,
        order: state.order,
        scenario: state.scenario,
        orderFactory: state.orderFactory,
        orderLine: state.orderLine,
        orderRisk: state.orderRisk,
        orderSearch: state.orderSearch,
        orderGate: state.orderGate,
        dueFilter: state.dueFilter,
        scheduleFactory: state.scheduleFactory,
      }),
    );
  } catch {}
}
function sparkChart(
  rows,
  series,
  { percent = false, height = 240, ceiling = null, timeScale = false, step = false } = {},
) {
  if (!rows.length)
    return emptyChart(
      "No historical observations supplied. Import a full scenario to analyze trends.",
    );
  const w = 680,
    h = height,
    left = 45,
    right = 18,
    top = 20,
    bottom = 35;
  const values = rows
    .flatMap((r) => series.map((s) => r[s.key]))
    .filter((x) => x !== null && x !== undefined);
  if (!values.length)
    return emptyChart("No observations available for this measure.");
  const max =
    ceiling ??
    (percent ? Math.max(1, ...values) : Math.max(1, ...values) * 1.12);
  const timestamps = timeScale ? rows.map((r) => Date.parse(r.date + "T00:00:00Z")) : [];
  const x = (i) =>
      left + (w - left - right) * (timeScale
        ? (timestamps[i] - timestamps[0]) / Math.max(1, timestamps.at(-1) - timestamps[0])
        : i / Math.max(1, rows.length - 1)),
    y = (v) => h - bottom - (v / max) * (h - top - bottom);
  return `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(series.map((s) => s.label).join(" versus "))} over time">${Array.from(
    { length: 5 },
    (_, i) => {
      const v = (max * i) / 4;
      return `<line x1="${left}" y1="${y(v)}" x2="${w - right}" y2="${y(v)}" stroke="#e8edf1"/><text class="chart-label" x="${left - 8}" y="${y(v) + 3}" text-anchor="end">${percent ? Math.round(v * 100) + "%" : num(v)}</text>`;
    },
  ).join("")}${series
    .map((s) => {
      let started = false;
      const path = rows
        .map((r, i) => {
          if (r[s.key] === null || r[s.key] === undefined) {
            started = false;
            return "";
          }
          const p = started && step
            ? `H${x(i)} V${y(r[s.key])}`
            : `${started ? "L" : "M"}${x(i)},${y(r[s.key])}`;
          started = true;
          return p;
        })
        .join(" ");
      return `<path d="${path}" stroke="${s.color}" stroke-width="2.5" fill="none" ${s.dashed ? 'stroke-dasharray="6 5"' : ""}/>${rows.map((r, i) => (r[s.key] == null ? "" : `<circle cx="${x(i)}" cy="${y(r[s.key])}" r="3" fill="${s.color}"><title>${esc(s.label)} · ${r.date}: ${percent ? pct(r[s.key]) : num(r[s.key])}</title></circle>`)).join("")}`;
    })
    .join(
      "",
    )}${rows.map((r, i) => (i % Math.ceil(rows.length / 6) === 0 ? `<text x="${x(i)}" y="${h - 8}" text-anchor="middle" class="chart-label">${fmt(r.date)}</text>` : "")).join("")}</svg>${legend(series.map((s) => [s.label + (s.dashed ? " (dashed)" : ""), s.color]))}`;
}
lineChart = (rows) =>
  sparkChart(rows, [
    {
      key: "target",
      label: "Planned output",
      color: palette.slate,
      dashed: true,
    },
    { key: "actual", label: "Actual output", color: palette.navy },
  ]);
function hbars(
  rows,
  key,
  label,
  {
    currency = false,
    percent = false,
    onClick = null,
    color = palette.navy,
  } = {},
) {
  if (!rows.length) return emptyChart("No records for this analysis.");
  const max = percent ? 1 : Math.max(1, ...rows.map((r) => r[key] || 0));
  return rows
    .map(
      (r) =>
        `<div class="chart-row">${onClick ? `<button class="link" onclick="${onClick(r)}">${esc(r[label])}</button>` : `<span>${esc(r[label])}</span>`}<div class="bar-track"><div class="bar-fill" style="width:${Math.max(0, Math.min(100, ((r[key] || 0) / max) * 100))}%;background:${color}"></div></div><strong style="text-align:right">${r[key] == null ? "N/A" : currency ? money(r[key]) : percent ? pct(r[key]) : num(r[key])}</strong></div>`,
    )
    .join("");
}
function paretoChart(rows) {
  if (!rows.length)
    return emptyChart(
      "No cause-coded downtime supplied. Statistical association cannot verify a root cause.",
    );
  return (
    hbars(rows, "minutes", "cause", { color: palette.navy }) +
    `<div class="note">${esc(rows[0].cause)} accounts for <strong>${pct(rows[0].share)}</strong> of coded lost minutes. The top ${Math.min(3, rows.length)} causes account for ${pct(rows[Math.min(2, rows.length - 1)].cumulative)}.</div>` +
    table(
      ["Cause", "Lost minutes", "Share", "Cumulative"],
      rows.map(
        (r) =>
          `<tr><td>${esc(r.cause)}</td><td>${num(r.minutes)}</td><td>${pct(r.share)}</td><td>${pct(r.cumulative)}</td></tr>`,
      ),
    )
  );
}
function costChart(options) {
  const rows = options.filter((o) => o.feasible);
  if (!rows.length)
    return emptyChart("Resolve the blocking constraint to compare costs.");
  const parts = [
    ["additional_cost", "Extra spend", palette.navy],
    ["expected_late_penalty", "Late penalty", palette.amber],
    ["expected_margin_exposure", "Margin exposure", palette.red],
    ["expected_quality_cost", "Quality", palette.slate],
    ["other_order_cost", "Displacement", palette.teal],
  ];
  const max = Math.max(1, ...rows.map((o) => o.expected_total_impact));
  return (
    rows
      .map(
        (o) =>
          `<div class="chart-row"><button class="link" onclick="selectOption(${jsarg(o.id)})">${esc(o.name)}</button><div style="display:flex;height:19px;border-radius:3px;overflow:hidden;background:#f3f6f8">${parts.map(([key, name, c]) => `<span style="width:${(o[key] / max) * 100}%;background:${c}" title="${name}: ${money(o[key])}"></span>`).join("")}</div><strong>${money(o.expected_total_impact)}</strong></div>`,
      )
      .join("") +
    legend(parts.map(([, n, c]) => [n, c])) +
    '<p class="chart-foot">Each component contributes to the same total impact. Select a bar label to review the plan.</p>'
  );
}
function tradeoffChart(options) {
  const rows = options.filter((o) => o.feasible);
  if (!rows.length) return emptyChart("No feasible plans to compare.");
  const w = 660,
    h = 260,
    l = 58,
    b = 40,
    t = 20,
    max = Math.max(1, ...rows.map((o) => o.expected_total_impact)) * 1.15;
  const x = (v) => l + (v / max) * (w - l - 35),
    y = (v) => h - b - v * (h - b - t);
  return `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Recovery expected cost versus on-time probability">${[0, 0.25, 0.5, 0.75, 1].map((v) => `<line x1="${l}" y1="${y(v)}" x2="${w - 30}" y2="${y(v)}" stroke="#e6edf2"/><text class="chart-label" x="${l - 8}" y="${y(v) + 3}" text-anchor="end">${pct(v)}</text>`).join("")}${[0, 0.25, 0.5, 0.75, 1].map((v) => `<text class="chart-label" x="${x(v * max)}" y="${h - 20}" text-anchor="middle">${money(v * max)}</text>`).join("")}${rows.map((o, i) => `<g tabindex="0" role="button" aria-label="Select ${esc(o.name)}" onclick="selectOption(${jsarg(o.id)})" onkeydown="if(event.key==='Enter')selectOption(${jsarg(o.id)})" style="cursor:pointer"><circle cx="${x(o.expected_total_impact)}" cy="${y(o.on_time_probability)}" r="${7 + o.quality_risk * 100}" fill="${o.quality_risk > 0.06 ? palette.amber : palette.teal}" opacity=".75" stroke="white" stroke-width="2"/><text x="${x(o.expected_total_impact)}" y="${y(o.on_time_probability) + 3}" text-anchor="middle" fill="white" font-size="9">${i + 1}</text><title>${esc(o.name)}: ${money(o.expected_total_impact)} · ${pct(o.on_time_probability)} on time · ${pct(o.quality_risk)} quality risk</title></g>`).join("")}<text class="chart-label" x="${w / 2}" y="${h - 2}" text-anchor="middle">Expected total impact · USD →</text></svg><div class="legend">${rows.map((o, i) => `<span>${i + 1}. ${esc(o.name)}</span>`).join("")}</div><p class="chart-foot">Higher is more likely on time; further right costs more. Larger circles indicate greater modeled quality risk. Select a point.</p>`;
}
function showModal(title, body, submit) {
  const dialog = $("#workspaceDialog");
  if (dialog.open) dialog.close();
  $("#dialogContent").innerHTML =
    `<div class="dialog-head"><h2 id="dialogTitle">${esc(title)}</h2><button class="quiet" aria-label="Close dialog" onclick="document.querySelector('#workspaceDialog').close()">✕</button></div><form id="workspaceForm" class="dialog-body"><div class="form-error" role="alert"></div>${body}<div class="dialog-actions"><button class="secondary" type="button" onclick="document.querySelector('#workspaceDialog').close()">Cancel</button><button class="primary" type="submit">Save and recalculate</button></div></form>`;
  $("#workspaceForm").onsubmit = async (e) => {
    e.preventDefault();
    const button = e.target.querySelector("[type=submit]");
    button.disabled = true;
    try {
      await submit(new FormData(e.target));
      dialog.close();
      toast("Saved to this scenario’s decision ledger");
      await go(state.page);
    } catch (err) {
      const box = e.target.querySelector(".form-error");
      box.style.display = "block";
      box.textContent = err.message;
    } finally {
      button.disabled = false;
    }
  };
  dialog.showModal();
}
const inputField = (label, name, value = "", type = "text", attrs = "") =>
  `<div class="field"><label for="field-${name}">${esc(label)}</label><input id="field-${name}" name="${name}" type="${type}" value="${esc(value)}" ${attrs}></div>`;
const textField = (
  label,
  name,
  value = "",
  attrs = 'required minlength="10"',
) =>
  `<div class="field"><label for="field-${name}">${esc(label)}</label><textarea id="field-${name}" name="${name}" ${attrs}>${esc(value)}</textarea></div>`;
const selectField = (label, name, options, value) =>
  `<div class="field"><label for="field-${name}">${esc(label)}</label><select id="field-${name}" name="${name}">${options.map((o) => `<option value="${esc(Array.isArray(o) ? o[0] : o)}" ${value === (Array.isArray(o) ? o[0] : o) ? "selected" : ""}>${esc(Array.isArray(o) ? o[1] : o)}</option>`).join("")}</select></div>`;
const ownerEvidence = () =>
  inputField(
    "Recorded by / responsible owner",
    "actor",
    "",
    "text",
    'required minlength="2"',
  ) + textField("Evidence and decision rationale", "evidence");
showDefinitions = async () => {
  const d = await api("/definitions");
  showModal(
    "Metric dictionary",
    Object.entries(d)
      .map(
        ([k, v]) =>
          `<div class="evidence-record"><strong>${esc(k.replaceAll("_", " "))}</strong><p>${esc(v)}</p></div>`,
      )
      .join(""),
    async () => {},
  );
  $("#workspaceForm .dialog-actions").remove();
};

async function tower() {
  const [a, o] = await Promise.all([api("/analytics"), api("/overview")]);
  state.analytics = a;
  state.asOf = a.as_of;
  $("#sidebarDate").textContent = "As of " + fmt(a.as_of) + " · USD";
  const t = a.totals,
    k = o.kpis,
    risks = a.portfolio.filter((p) => p.status !== "on_time");
  const most = risks[0];
  const status = `<div class="status-strip">${[
    ["on_time", palette.teal],
    ["late", palette.amber],
    ["blocked", palette.red],
  ]
    .map(
      ([key, c]) =>
        `<span style="width:${(t[key] / Math.max(1, t.orders)) * 100}%;background:${c}"></span>`,
    )
    .join("")}</div>${legend([
    [t.on_time + " on time", palette.teal],
    [t.late + " late", palette.amber],
    [t.blocked + " blocked", palette.red],
  ])}`;
  $("#content").innerHTML =
    header(
      "Network command / " + fmt(a.as_of),
      "Production control tower",
      "A connected view of delivery confidence, operating performance, and decisions that need attention.",
      `<button class="secondary" onclick="go('schedule')">View production plan →</button>`,
    ) +
    `<div class="executive-band"><section class="network-outlook" aria-label="Network decision brief"><span class="eyebrow">Network outlook / ${fmt(a.as_of)}</span><div class="outlook-count">${t.late + t.blocked}<small>/ ${t.orders}</small></div><h2>Orders need a production decision</h2><p>${most ? `${esc(most.id)} carries the largest modeled delivery exposure at ${money(most.expected_exposure)}. ${most.status === "blocked" ? "Its schedule is blocked by a hard constraint." : "Its shipment is " + Math.abs(most.slack_days) + " days beyond the deadline."}` : "All orders have a feasible on-time plan. Continue monitoring release gates and execution."} ${k.overdue_actions} response actions are overdue.</p>${status}<button class="secondary" onclick="openRiskOrders()">Review exceptions <span aria-hidden="true">→</span></button></section><div class="kpi-grid">${kpi("Active orders", t.orders, num(t.units) + " units in the network")}${kpi("Forecast OTIF", pct(t.on_time / Math.max(1,t.orders)), "On-time orders / all orders", "good")}${kpi("Delivery exposure", money(t.expected_exposure), "Penalty + margin · modeled", "alert")}${kpi("First-pass yield", pctOrNA(k.first_pass_yield), "Observed acceptable / output")}${kpi("Orders needing intervention", t.late + t.blocked, t.blocked + " blocked · " + t.late + " late", "alert")}${kpi("Overdue actions", k.overdue_actions, k.open_incidents + " open exceptions")}</div></div>` +
    `<div class="grid-two">${card("Actual output against the operating plan", lineChart(a.history.slice(-14)), "Units / production day")}${card(
      "Delivery exposure is concentrated by factory",
      hbars(
        [...a.factories].sort(
          (x, y) => y.expected_exposure - x.expected_exposure,
        ),
        "expected_exposure",
        "name",
        {
          currency: true,
          onClick: (r) =>
            `state.orderFactory=${jsarg(r.id)};state.orderRisk='risk';go('orders')`,
        },
      ) +
        '<p class="chart-foot">Expected penalty and margin exposure, not a booked financial loss. Select a factory to inspect its at-risk orders.</p>',
      "USD · active portfolio",
    )}</div>` +
    `<div class="grid-equal">${card(
      "Release gates determine what can enter production",
      hbars(
        [
          { name: "Material pending", count: o.readiness.material_pending },
          { name: "Quality pending", count: o.readiness.quality_pending },
          { name: "Material ready", count: o.readiness.material_ready },
        ],
        "count",
        "name",
        { color: palette.slate },
      ) +
        `<div class="toolbar"><button class="secondary" onclick="openGate('material_pending')">Review material gates</button><button class="secondary" onclick="openGate('quality_pending')">Review quality gates</button></div>`,
      "Orders · gates may overlap",
    )}${card(
      "Execution priorities",
      o.actions
        .filter((x) => x.status !== "done")
        .sort((a, b) => a.due_date.localeCompare(b.due_date))
        .slice(0, 4)
        .map(
          (x) =>
            `<div class="factory-card"><div><button class="link" onclick="openActionIncident(${jsarg(x.incident_id)})">${esc(x.title)}</button><small>${esc(x.owner)} · ${esc(x.incident_id)}</small></div><div>${tag(x.due_date < a.as_of ? "Overdue" : "Due " + fmt(x.due_date), x.due_date < a.as_of ? "red" : "blue")}</div></div>`,
        )
        .join("") || emptyChart("No open actions."),
      "Select to open response plan",
    )}</div>` +
    card(
      "Orders with the greatest commercial exposure",
      table(
        [
          "Order / customer",
          "Assignment",
          "Units",
          "Ship / deadline",
          "Delivery status",
          "Expected exposure",
          "Next step",
        ],
        risks
          .slice(0, 8)
          .map(
            (r) =>
              `<tr><td><button class="link" onclick="openOrder(${jsarg(r.id)})">${esc(r.id)}</button><br><span class="muted">${esc(r.customer)}</span></td><td>${esc(r.factory_id)} / ${esc(r.line_id)}</td><td>${num(r.quantity)}</td><td>${fmt(r.plan.expected_ship)} / ${fmt(r.due_date)}</td><td>${riskTag(r.plan.delay_days, r.plan.feasible)}</td><td><strong>${money(r.expected_exposure)}</strong></td><td><button class="link" onclick="openOrder(${jsarg(r.id)})">Inspect constraints ↗</button></td></tr>`,
          ),
      ) || emptyChart("No at-risk orders."),
      `${risks.length} exposed orders`,
    );
}
async function factoryIntelligence() {
  const a = await api("/analytics");
  state.analytics = a;
  $("#content").innerHTML =
    header(
      "Partner performance",
      "Factory intelligence",
      "Separate observed factory performance from future delivery forecasts. Compare the trade-offs behind an allocation.",
    ) +
    `<div class="network-cards">${a.factories.map((f, i) => `<section class="card network-card"><div class="section-number">PARTNER ${String(i + 1).padStart(2, "0")} <span style="float:right">${tag(f.compliance ? "Compliant" : "Compliance hold", f.compliance ? "green" : "red")}</span></div><h2>${esc(f.name)}</h2><div class="region">${esc(f.region)} · ${esc(f.id)}</div><div class="network-metrics"><div><strong>${f.orders}</strong><small>active orders</small></div><div><strong>${num(f.units)}</strong><small>committed units</small></div><div><strong>${pctOrNA(f.forecast_otif)}</strong><small>forecast OTIF</small></div><div><strong>${money(f.expected_exposure)}</strong><small>delivery exposure</small></div></div><div class="small muted">${f.capabilities.map(esc).join(" · ")}<br>${f.logistics_days} transit days · ${money(f.cost)} base unit cost</div><button class="secondary" style="margin-top:18px;width:100%" onclick="state.orderFactory=${jsarg(f.id)};go('orders')">Open factory portfolio →</button></section>`).join("")}</div>` +
    `<div class="grid-equal">${card(
      "Quality performance by production day",
      sparkChart(
        a.history,
        [
          {
            key: "first_pass_yield",
            label: "First-pass yield",
            color: palette.teal,
          },
          {
            key: "adherence",
            label: "Plan adherence",
            color: palette.slate,
            dashed: true,
          },
        ],
        { percent: true },
      ),
      "Ratios · hover for exact values",
    )}${card("Downtime concentrates maintenance effort", paretoChart(a.pareto), "Cause contribution · minutes")}</div>` +
    card(
      "Quality, cost, delivery, and workforce scorecard",
      table(
        [
          "Factory",
          "Observed FPY",
          "Rework rate",
          "Plan adherence",
          "Attendance",
          "Downtime",
          "Forecast OTIF",
          "Late / blocked",
        ],
        a.factories.map(
          (f) =>
            `<tr><td><strong>${esc(f.name)}</strong></td><td>${pctOrNA(f.first_pass_yield)}</td><td>${pctOrNA(f.rework_rate)}</td><td>${pctOrNA(f.adherence)}</td><td>${pctOrNA(f.attendance)}</td><td>${a.coverage.downtime ? num(f.downtime_minutes) + " min" : "N/A"}</td><td>${pctOrNA(f.forecast_otif)}</td><td>${f.late} / ${f.blocked}</td></tr>`,
        ),
      ),
      "History through " + fmt(a.as_of),
    ) +
    card(
      "Stage capacity identifies downstream limits",
      table(
        [
          "Factory",
          "Stage",
          "Daily capacity",
          "Peak reserved",
          "Peak utilization",
          "Peak date",
        ],
        a.stage_load.map(
          (r) =>
            `<tr><td>${esc(r.factory_id)}</td><td>${esc({ cut: "Cutting", finish: "Finishing", qc: "Inspection", pack: "Packing" }[r.stage])}</td><td>${num(r.capacity)} units</td><td>${num(r.peak_units)}</td><td>${pctOrNA(r.peak_utilization)}</td><td>${fmt(r.peak_date)}</td></tr>`,
        ),
      ),
      "Next 42 calendar days",
    );
}
function heatmapHTML(a) {
  const rows = a.heatmap.filter(
      (l) =>
        !state.scheduleFactory ||
        state.scheduleFactory === "all" ||
        l.factory_id === state.scheduleFactory,
    ),
    days = a.days.slice(0, 28);
  return `<div class="table-wrap"><table class="heatmap"><thead><tr><th>Factory / line</th>${days.map((d, i) => `<th title="${d}">${i % 3 === 0 ? fmt(d) : ""}</th>`).join("")}</tr></thead><tbody>${rows
    .map(
      (l) =>
        `<tr><th>${esc(l.factory_id)} / ${esc(l.id)}</th>${l.cells
          .slice(0, 28)
          .map((c) => {
            const u = c.utilization;
            const color =
              u === null
                ? ""
                : u === 0
                  ? "#f0f2f4"
                  : u < 0.5
                    ? "#98c1d9"
                    : u < 0.85
                      ? "#557798"
                      : u <= 1.00001
                        ? "#3d5a80"
                        : "#b24136";
            return `<td><button class="heat-cell ${u === null ? "unavailable" : ""}" style="${color ? "background:" + color + ";color:" + (u >= 0.5 ? "white" : "#293241") : ""}" title="${esc(l.id)} · ${c.date} · ${u === null ? "Unavailable" : pct(u) + " reserved"} · ${c.units} units" aria-label="${esc(l.id)} ${c.date} capacity details" onclick="capacityCell(${jsarg(l.id)},${jsarg(c.date)})">${u === null ? "—" : u > 0.05 ? Math.round(u * 100) : ""}</button></td>`;
          })
          .join("")}</tr>`,
    )
    .join("")}</tbody></table></div>${legend([
    ["No reservation", "#f0f2f4"],
    ["Under 50%", "#98c1d9"],
    ["50–85%", "#557798"],
    ["85–100%", "#3d5a80"],
    ["Over capacity", "#b24136"],
    ["Unavailable", "#e2e8ec"],
  ])}<p class="chart-foot">In-house minutes, including changeover. Click a day for capacity, external output, and the orders using it. Sunday, holidays, maintenance and shutdowns are excluded.</p>`;
}
function ganttHTML(a) {
  const rows = a.portfolio
    .filter(
      (r) =>
        (!state.scheduleFactory ||
          state.scheduleFactory === "all" ||
          r.factory_id === state.scheduleFactory) &&
        r.plan.feasible,
    )
    .sort((x, y) => x.due_date.localeCompare(y.due_date));
  if (!rows.length)
    return emptyChart(
      "No feasible schedules in this filter. Review blocked orders in the order portfolio.",
    );
  const dayMs = 86400000,
    origin = Date.parse(a.as_of),
    last = Math.max(
      ...rows.map((r) => Date.parse(r.plan.expected_ship)),
      origin + dayMs * 14,
    ),
    span = (last - origin) / dayMs + 2;
  const pos = (d) =>
    Math.max(0, ((Date.parse(d) - origin) / dayMs / span) * 100);
  const stages = [
    ["start", "cut_complete", "Cutting", "#b7cbd8"],
    ["cut_complete", "sewing_complete", "Sewing", palette.navy],
    ["sewing_complete", "finishing", "Finishing", palette.teal],
    ["finishing", "inspection", "Inspection", "#81aaa6"],
    ["inspection", "packing", "Packing", "#afc7bd"],
    ["packing", "expected_ship", "Transit", palette.amber],
  ];
  return `<div class="table-wrap"><div class="gantt"><div class="gantt-row"><span class="small muted">Order / assigned line</span><div style="display:flex;justify-content:space-between" class="small muted">${[0, 0.25, 0.5, 0.75, 1].map((v) => fmt(new Date(origin + span * v * dayMs).toISOString().slice(0, 10))).join("</span><span>")}</div><span class="small muted">Variance</span></div>${rows.map((r) => `<div class="gantt-row"><button class="link small" onclick="openOrder(${jsarg(r.id)})">${esc(r.id)} <span class="muted">${esc(r.line_id)}</span></button><div class="gantt-track">${stages.map(([start, end, label, c]) => `<button class="gantt-bar" style="left:${pos(r.plan[start])}%;width:${Math.max(0.4, pos(r.plan[end]) - pos(r.plan[start]))}%;background:${c}" title="${label}: ${r.plan[start]} → ${r.plan[end]}" aria-label="${esc(r.id)} ${label}" onclick="openOrder(${jsarg(r.id)})"></button>`).join("")}<span class="deadline-marker" style="left:${Math.min(100, pos(r.due_date))}%" title="Deadline ${r.due_date}"></span></div><span>${riskTag(r.plan.delay_days, true)}</span></div>`).join("")}</div></div>${legend([...stages.map((s) => [s[2], s[3]]), ["Deadline", palette.red]])}<p class="chart-foot">Stage spans include queue and non-working time. Bars represent planned dates; execution progress is only available in supplied historical records.</p>`;
}
async function capacitySchedule() {
  const a = await api("/analytics");
  state.analytics = a;
  $("#content").innerHTML =
    header(
      "Finite capacity planning",
      "Capacity & production schedule",
      "Inspect where capacity is reserved, which orders compete for it, and how stage timing reaches the customer deadline.",
      `<select class="selector" aria-label="Schedule factory" onchange="state.scheduleFactory=this.value;go('schedule')"><option value="all">All factories</option>${a.factories.map((f) => `<option value="${esc(f.id)}" ${state.scheduleFactory === f.id ? "selected" : ""}>${esc(f.name)}</option>`).join("")}</select>`,
    ) +
    card(
      "Sewing capacity by line and day",
      heatmapHTML(a),
      "Next 28 days · % reserved",
    ) +
    card(
      "Order-to-shipment planning timeline",
      ganttHTML(a),
      "Click an order or stage to inspect",
    ) +
    `<div class="note">${a.totals.blocked} orders have no feasible schedule and are excluded from these reservations. ${esc(a.methodology.capacity)}</div>`;
  $("#content").insertAdjacentHTML(
    "beforeend",
    card(
      "Planned work in progress across the network",
      sparkChart(a.flow, [
        { key: "wip", label: "Cut but not packed", color: palette.navy },
        {
          key: "ready_to_ship",
          label: "Packed, awaiting shipment",
          color: palette.teal,
        },
      ]),
      "End-of-day units · all factories",
    ) +
      `<p class="chart-foot">These balances are derived from scheduled stage quantities. They represent future planned inventory, not measured shop-floor WIP.</p>`,
  );
}
function capacityCell(line, date) {
  const r = state.analytics.heatmap
    .find((l) => l.id === line)
    .cells.find((c) => c.date === date);
  showModal(
    line + " · " + fmt(date),
    `<div class="detail-grid">${[
      ["Available minutes", num(r.capacity_minutes)],
      ["Reserved minutes", num(r.reserved_minutes)],
      ["Planned units", num(r.units)],
      ["External units", num(r.outsourced_units)],
    ]
      .map(
        ([label, v]) =>
          `<div class="detail-tile"><small>${label}</small><strong>${v}</strong></div>`,
      )
      .join(
        "",
      )}</div><p>${r.orders.length ? "Orders reserving this day:" : "No orders reserve this day."}</p>${r.orders.map((id) => `<p><button type="button" class="link" onclick="document.querySelector('#workspaceDialog').close();openOrder(${jsarg(id)})">${esc(id)} →</button></p>`).join("")}`,
    async () => {},
  );
  $("#workspaceForm .dialog-actions").remove();
}
const originalOrderDetail = orderDetail,
  originalInvestigation = incidentDetail,
  originalRecovery = recovery,
  originalWarroom = warroom,
  originalImprovement = improvement;
async function enhancedOrder() {
  await originalOrderDetail();
  const d = await api("/order?order_id=" + encodeURIComponent(state.order));
  $("#content .page-head .toolbar").insertAdjacentHTML(
    "afterbegin",
    `<button class="primary" onclick="releaseForm(${jsarg(state.order)})">Update release gates</button>`,
  );
  $("#content").insertAdjacentHTML(
    "beforeend",
    card(
      "Commit a validated allocation",
      `<p class="small muted">Review the candidate table above before committing. This reruns the complete network schedule and retains every candidate with your rationale.</p><button class="primary" onclick="allocationForm(${jsarg(state.order)})">Review allocation decision</button>`,
      "Controlled planning change",
    ),
  );
  if (d.incidents.length)
    $("#content").insertAdjacentHTML(
      "beforeend",
      card(
        "Connected response records",
        d.incidents
          .map(
            (i) =>
              `<div class="factory-card"><div><strong>${esc(i.title)}</strong><small>${esc(i.id)} · ${esc(i.owner)}</small></div><button class="secondary" onclick="state.incident=${jsarg(i.id)};go('incidentDetail')">Open investigation →</button></div>`,
          )
          .join(""),
        "Order → incident → response",
      ),
    );
}
async function releaseForm(id) {
  const d = await api("/order?order_id=" + encodeURIComponent(id));
  showModal(
    "Update release gates · " + id,
    `<p class="note">Clearing quality release closes all current holds for this order. Record inspection evidence and the responsible owner. Every change is retained in the ledger.</p><div class="form-row">${inputField("Fabric available", "fabric_ready", d.material.fabric_ready, "date", "required")}${inputField("Trims available", "trims_ready", d.material.trims_ready, "date", "required")}</div><div class="form-row">${inputField("Outstanding shortage · units", "shortage_units", d.material.shortage_units, "number", 'required min="0" step="1"')}${selectField(
      "Quality gate",
      "quality_release",
      [
        ["true", "Released — inspection accepted"],
        ["false", "Hold — not released"],
      ],
      String(
        d.order.quality_release &&
          !d.quality_holds.some((h) => h.status === "open"),
      ),
    )}</div>${ownerEvidence()}`,
    async (f) => {
      await api("/releases", {
        method: "POST",
        body: JSON.stringify({
          order_id: id,
          actor: f.get("actor"),
          evidence: f.get("evidence"),
          fabric_ready: f.get("fabric_ready"),
          trims_ready: f.get("trims_ready"),
          shortage_units: Number(f.get("shortage_units")),
          quality_release: f.get("quality_release") === "true",
        }),
      });
    },
  );
}
async function allocationForm(id) {
  const candidates = await api(
    "/allocation?order_id=" + encodeURIComponent(id),
  );
  const valid = candidates.filter((c) => c.feasible);
  if (!valid.length) {
    toast(
      "No feasible allocation. Resolve release or capability constraints first.",
    );
    return;
  }
  showModal(
    "Approve allocation · " + id,
    selectField(
      "Receiving line · delivery forecast",
      "line_id",
      valid.map((c) => [
        c.line_id,
        `${c.factory_id} / ${c.line_id} · ${c.expected_ship} · ${c.displaced_orders} other orders delayed`,
      ]),
      valid[0].line_id,
    ) + ownerEvidence(),
    async (f) => {
      await api("/allocations", {
        method: "POST",
        body: JSON.stringify({
          order_id: id,
          line_id: f.get("line_id"),
          actor: f.get("actor"),
          evidence: f.get("evidence"),
        }),
      });
    },
  );
}
async function enhancedInvestigation() {
  await originalInvestigation();
  const [d, audit] = await Promise.all([
    api("/incident?incident_id=" + encodeURIComponent(state.incident)),
    api("/audit"),
  ]);
  const records = audit.events.filter(
    (e) => e.kind === "hypothesis" && e.entity_id === state.incident,
  );
  $("#content .page-head .toolbar").insertAdjacentHTML(
    "afterbegin",
    '<button class="primary" onclick="hypothesisForm()">Record hypothesis</button>',
  );
  $("#content").insertAdjacentHTML(
    "beforeend",
    card(
      "Structured investigation and evidence",
      records.length
        ? records
            .map(
              (e) =>
                `<div class="evidence-record"><div>${tag(e.payload.status, e.payload.status === "verified" ? "green" : e.payload.status === "rejected" ? "red" : "amber")} <strong>${esc(e.payload.category)} · ${esc(e.payload.statement)}</strong></div><p>${esc(e.evidence)}</p>${e.payload.verification ? `<p><strong>Verification:</strong> ${esc(e.payload.verification)}</p>` : ""}${e.payload.whys?.length ? `<ol>${e.payload.whys.map((w) => `<li>${esc(w)}</li>`).join("")}</ol>` : ""}<small>${esc(e.actor)} · ${esc(e.created_at)}</small></div>`,
            )
            .join("")
        : emptyChart(
            "No additional hypotheses recorded. Classify observations before claiming a verified root cause.",
          ),
      "Evidence classification · append-only history",
    ),
  );
  if (d.pareto.length)
    $("#content").insertAdjacentHTML(
      "beforeend",
      card(
        "Cause concentration and cumulative contribution",
        paretoChart(d.pareto),
        "Recorded lost minutes · this line",
      ),
    );
  const fishbone = $("#content")
    .querySelectorAll(".grid-two")[1]
    ?.querySelectorAll(".card")[1];
  if (fishbone)
    fishbone.innerHTML = `<div class="section-title"><h2>Fishbone investigation map</h2><span>Six contributing dimensions</span></div><div class="fishbone-grid">${Object.entries(
      d.fishbone,
    )
      .map(
        ([category, items]) =>
          `<div class="fishbone-branch"><strong>${esc(category)}</strong>${items.map(esc).join("<br>")}${records
            .filter((e) => e.payload.category === category)
            .map(
              (e) =>
                `<p>${tag(e.payload.status, "blue")} ${esc(e.payload.statement)}</p>`,
            )
            .join("")}</div>`,
      )
      .join("")}</div>`;
}
function hypothesisForm() {
  showModal(
    "Record cause investigation",
    `<div class="form-row">${selectField("Fishbone dimension", "category", ["Machine", "Method", "Material", "People", "Measurement", "Environment"], "Method")}${selectField(
      "Evidence classification",
      "status",
      [
        ["hypothesis", "Unverified hypothesis"],
        ["contributing", "Contributing factor"],
        ["rejected", "Rejected hypothesis"],
        ["verified", "Verified root cause"],
      ],
      "hypothesis",
    )}</div>${textField("Cause statement", "statement")}${textField("5 Whys chain · one step per line", "whys", "", "")}${textField("Verification method and result · required for verified cause", "verification", "", "")}${ownerEvidence()}`,
    async (f) => {
      await api("/hypotheses", {
        method: "POST",
        body: JSON.stringify({
          incident_id: state.incident,
          category: f.get("category"),
          status: f.get("status"),
          statement: f.get("statement"),
          verification: f.get("verification"),
          whys: f
            .get("whys")
            .split("\n")
            .map((x) => x.trim())
            .filter(Boolean),
          actor: f.get("actor"),
          evidence: f.get("evidence"),
        }),
      });
    },
  );
}
async function enhancedRecovery() {
  state.options = null;
  await originalRecovery();
  if (!state.options) return;
  const anchor = $("#content .option-grid");
  if (!anchor) return;
  anchor.insertAdjacentHTML(
    "beforebegin",
    `<div class="grid-equal">${card("Compare the cost of each response", costChart(state.options), "USD · expected total impact")}${card("Delivery confidence against commercial impact", tradeoffChart(state.options), "Bubble size = quality risk")}</div>`,
  );
  $("#content").insertAdjacentHTML(
    "beforeend",
    card(
      "Supplier negotiation workbench",
      `<p class="small muted">Model supplier contributions and buyer concessions against a feasible recovery plan. Proposals preserve the original operating cost and do not silently change the production plan.</p><button class="primary" onclick="negotiationForm()">Model cost-sharing agreement</button><div id="negotiations"></div>`,
      "Commercial terms · separately recorded",
    ),
  );
  $("#content").insertAdjacentHTML(
    "beforeend",
    card(
      "Uncertainty and sensitivity",
      `<div class="filter-row"><label for="sigma">Shipment variability · days</label><input id="sigma" type="number" min="0.1" max="10" step="0.1" value="1.8"><button class="secondary" onclick="runSimulation()">Run 2,000 simulations</button></div><div id="simulationResults"></div>`,
      "Monte Carlo · fixed seed for comparison",
    ),
  );
  await runSimulation();
  const audit = await api("/audit");
  const records = audit.events.filter(
    (e) => e.kind === "negotiation" && e.entity_id === state.incident,
  );
  $("#negotiations").innerHTML = records.length
    ? table(
        [
          "Plan",
          "Gross impact",
          "Supplier contribution",
          "Buyer concession",
          "Buyer net impact",
          "Status",
        ],
        records.map(
          (e) =>
            `<tr><td>${esc(e.payload.option_id)}</td><td>${money(e.payload.gross_expected_impact)}</td><td>${money(e.payload.supplier_contribution)}</td><td>${money(e.payload.buyer_concession)}</td><td><strong>${money(e.payload.buyer_expected_impact)}</strong></td><td>${tag("Proposal", "amber")}</td></tr>`,
        ),
      )
    : "";
}
selectOption = (id) => {
  state.option = id;
  go("recovery");
};
function negotiationForm() {
  const opts = state.options.filter((o) => o.feasible);
  if (!opts.length) {
    toast("No feasible plan to negotiate.");
    return;
  }
  showModal(
    "Supplier cost-sharing scenario",
    selectField(
      "Recovery plan",
      "option_id",
      opts.map((o) => [o.id, o.name]),
      state.option || opts[0].id,
    ) +
      `<div class="form-row">${inputField("Supplier share of extra spend · %", "share", 50, "number", 'required min="0" max="100" step="1"')}${inputField("Buyer concession · USD", "concession", 0, "number", 'required min="0" step="0.01"')}</div><div class="note">Net buyer impact = gross expected impact − supplier share of incremental spend + buyer concession. Supplier acceptance remains to be confirmed.</div>${ownerEvidence()}`,
    async (f) => {
      await api("/negotiations", {
        method: "POST",
        body: JSON.stringify({
          incident_id: state.incident,
          option_id: f.get("option_id"),
          supplier_share: Number(f.get("share")) / 100,
          concession: Number(f.get("concession")),
          actor: f.get("actor"),
          evidence: f.get("evidence"),
        }),
      });
    },
  );
}
async function enhancedWarroom() {
  await originalWarroom();
  if (!$("#content .kpi-grid")) return;
  $("#content .page-head .toolbar").insertAdjacentHTML(
    "afterbegin",
    '<button class="primary" onclick="actionForm()">+ Assign action</button>',
  );
  const actions = (await api("/actions")).filter(
    (a) => a.incident_id === state.incident,
  );
  const roles = [...new Set(actions.flatMap((a) => [a.owner, a.accountable]))];
  $("#content").insertAdjacentHTML(
    "beforeend",
    card(
      "Responsibility and escalation matrix",
      actions.length
        ? table(
            ["Action", ...roles],
            actions.map(
              (a) =>
                `<tr><td>${esc(a.title)}<br><span class="muted">${a.blocked ? "Waiting on " + esc(a.dependency) : a.overdue ? "Escalate to " + esc(a.accountable) : "Due " + fmt(a.due_date)}</span></td>${roles.map((role) => `<td>${role === a.owner ? tag("R", "blue") : ""} ${role === a.accountable ? tag("A", "green") : ""}</td>`).join("")}</tr>`,
            ),
          )
        : emptyChart("Assign actions to establish ownership."),
      "R = responsible · A = accountable",
    ),
  );
}
actionPrompt = async (id) => {
  const a = (await api("/actions")).find((x) => x.id === id);
  showModal(
    "Update action · " + id,
    `<p><strong>${esc(a.title)}</strong></p>${a.blocked ? `<div class="note">Dependency ${esc(a.dependency)} must be completed before this action can close.</div>` : ""}${selectField("Action status", "status", ["open", "in_progress", "blocked", "done"], a.status)}${textField("Completion evidence or progress update", "evidence", a.evidence, 'required minlength="3"')}`,
    async (f) => {
      await api("/action?action_id=" + encodeURIComponent(id), {
        method: "PATCH",
        body: JSON.stringify({
          status: f.get("status"),
          evidence: f.get("evidence"),
        }),
      });
    },
  );
};
commitmentPrompt = (id) =>
  showModal(
    "Update factory commitment",
    selectField(
      "Fulfillment status",
      "status",
      ["open", "fulfilled", "missed"],
      "fulfilled",
    ) +
      inputField(
        "Actual fulfillment date · required when fulfilled",
        "actual_date",
        state.asOf || "",
        "date",
      ),
    async (f) => {
      await api("/commitments/" + id, {
        method: "PATCH",
        body: JSON.stringify({
          status: f.get("status"),
          actual_date: f.get("actual_date") || null,
        }),
      });
    },
  );
rulePrompt = (id) =>
  showModal(
    "Management review · rule #" + id,
    inputField(
      "Management approver",
      "approver",
      "",
      "text",
      'required minlength="2"',
    ) +
      selectField(
        "Explicit review decision",
        "approve",
        [
          ["true", "Approve proposal"],
          ["false", "Reject proposal"],
        ],
        "true",
      ) +
      '<div class="note">Approval records management intent. Changes to planning formulas require a reviewed implementation and validation before deployment.</div>',
    async (f) => {
      await api("/rules/" + id, {
        method: "PATCH",
        body: JSON.stringify({
          approver: f.get("approver"),
          approve: f.get("approve") === "true",
        }),
      });
    },
  );
async function actionForm() {
  const actions = (await api("/actions")).filter(
    (a) => a.incident_id === state.incident,
  );
  showModal(
    "Assign recovery action",
    inputField(
      "Action / deliverable",
      "title",
      "",
      "text",
      'required minlength="5"',
    ) +
      `<div class="form-row">${inputField("Accountable owner · one person or role", "accountable", "Production manager", "text", 'required minlength="2"')}${inputField("Due date", "due_date", state.asOf, "date", `required min="${state.asOf}"`)}</div><div class="form-row">${inputField("Consulted", "consulted")}${inputField("Informed", "informed")}</div>${selectField("Prerequisite action", "dependency", [["", "No dependency"], ...actions.map((a) => [a.id, a.id + " · " + a.title])], "")}${ownerEvidence()}`,
    async (f) => {
      await api("/actions", {
        method: "POST",
        body: JSON.stringify({
          incident_id: state.incident,
          title: f.get("title"),
          accountable: f.get("accountable"),
          due_date: f.get("due_date"),
          consulted: f.get("consulted"),
          informed: f.get("informed"),
          dependency: f.get("dependency") || null,
          actor: f.get("actor"),
          evidence: f.get("evidence"),
        }),
      });
    },
  );
}
async function enhancedImprovement() {
  await originalImprovement();
  if (!$("#content form")) return;
  const d = await api(
    "/improvement?incident_id=" + encodeURIComponent(state.incident),
  );
  const checks = [...d.records].reverse().filter((r) => r.stage === "check");
  const rows = checks.map((r) => ({
    date: r.recorded_at.slice(0, 10),
    observed: r.observed,
    baseline: d.baseline.events_per_day,
    target: d.targets.events_per_day,
  }));
  $("#content .insight").insertAdjacentHTML(
    "afterend",
    card(
      "Is the intervention reducing recurrence?",
      rows.length
        ? sparkChart(rows, [
            {
              key: "baseline",
              label: "Baseline",
              color: palette.slate,
              dashed: true,
            },
            {
              key: "target",
              label: "Target",
              color: palette.teal,
              dashed: true,
            },
            {
              key: "observed",
              label: "Observed events / day",
              color: palette.navy,
            },
          ])
        : emptyChart(
            "Record a post-intervention check to compare observed recurrence with the baseline and target.",
          ),
      "Checks by recorded date",
    ) + `<div id="checkpointPanel"></div>`,
  );
  await renderCheckpoints();
}
async function governance() {
  const [a, ledger, v] = await Promise.all([
    api("/analytics"),
    api("/audit"),
    api("/validation"),
  ]);
  const b = v.benchmarks;
  const best = [...b].sort(
    (x, y) =>
      y.forecast_otif - x.forecast_otif || x.estimated_cost - y.estimated_cost,
  )[0];
  $("#content").innerHTML =
    header(
      "Evidence, validation & governance",
      "Data & decision ledger",
      "Trace input coverage, model assumptions, planning alternatives, and recorded management decisions.",
      `<a class="secondary" href="./sample-orders.csv" download>↓ Order template</a><button class="primary" onclick="downloadReport('management.json')">Export full evidence pack</button>`,
    ) +
    `<div class="grid-equal">${card(
      "Source coverage",
      `<div class="coverage-grid">${Object.entries(a.coverage)
        .map(
          ([key, value]) =>
            `<div class="coverage-item"><strong>${num(value)}</strong><small>${esc(key.replaceAll("_", " "))} records</small></div>`,
        )
        .join("")}</div>`,
      "Active file only",
    )}${card("Assumptions and provenance", `<p><strong>${esc(a.scenario.name)}</strong></p><p class="small muted">${esc(a.scenario.description)}</p>${tag(a.scenario.synthetic ? "Synthetic data" : "Uploaded source", "blue")}<p class="small">Planning date: ${a.as_of}. No historical observations are generated for an order-table upload.</p>${a.scenario.assumptions?.length ? `<ul class="small">${a.scenario.assumptions.map((s) => `<li>${esc(s)}</li>`).join("")}</ul>` : '<p class="small muted">Full network schema supplied. Review source records in the scenario export.</p>'}`, "Source transparency")}</div>` +
    `<div class="insight"><div class="icon">↗</div><div><strong>${esc(best.method)} produces the highest forecast OTIF in this comparison</strong><p>${pct(best.forecast_otif)} OTIF at ${money(best.estimated_cost)} modeled operating and delivery exposure. All methods use the same input constraints. This comparison does not establish an optimum.</p></div></div>` +
    `<div class="grid-equal">${card("Dispatch policy changes delivery outcomes", hbars(b, "forecast_otif", "method", { percent: true, color: palette.teal }), "Forecast OTIF · zero to 100%")}${card("Operating cost and delivery exposure", hbars(b, "estimated_cost", "method", { currency: true }), "USD · same scenario")}</div>` +
    card(
      "Planning benchmark scorecard",
      table(
        [
          "Method",
          "Late",
          "Blocked",
          "Forecast OTIF",
          "Cost + exposure",
          "Assignment changes",
          "Capacity utilization",
        ],
        b.map(
          (r) =>
            `<tr><td>${esc(r.method)}</td><td>${r.late_orders}</td><td>${r.constraint_violations}</td><td>${pct(r.forecast_otif)}</td><td>${money(r.estimated_cost)}</td><td>${r.plan_changes}</td><td>${pct(r.capacity_utilization)}</td></tr>`,
        ),
      ) +
        `<p class="chart-foot">${esc(v.note)} “Blocked” counts rejected orders; these are prevented allocations, not schedules that violate a constraint.</p>`,
      "Transparent heuristic comparison",
    ) +
    card(
      "Operating event ledger",
      ledger.events.length
        ? table(
            ["Recorded", "Event / entity", "Owner", "Evidence", "Outcome"],
            ledger.events.map(
              (e) =>
                `<tr><td>${esc(e.created_at.replace("T", " "))}</td><td>${tag(e.kind, "blue")}<br>${esc(e.entity_id)}</td><td>${esc(e.actor)}</td><td>${esc(e.evidence)}</td><td>${esc(e.payload.status || e.payload.line_id || "Saved")}</td></tr>`,
            ),
          )
        : emptyChart(
            "Release, allocation, investigation, action and negotiation events appear here when recorded.",
          ),
      "Scenario scoped · immutable event rows",
    ) +
    card(
      "Calculation notes and operating boundaries",
      Object.entries(a.methodology)
        .map(
          ([key, value]) =>
            `<div class="evidence-record"><strong>${esc(key.replaceAll("_", " "))}</strong><p>${esc(value)}</p></div>`,
        )
        .join("") +
        '<div class="note">Local planning workspace: named approvers are recorded, but identity authentication and role enforcement are not configured. The scheduler is a finite-capacity heuristic. Partial-shipment promises, individual machine sequencing, carbon accounting, and ERP integrations require additional operating data and implementation.</div>',
      "Model transparency",
    );
}
improvement = enhancedImprovement;
Object.assign(pages, {
  overview: tower,
  network: factoryIntelligence,
  schedule: capacitySchedule,
  orderDetail: enhancedOrder,
  incidentDetail: enhancedInvestigation,
  recovery: enhancedRecovery,
  warroom: enhancedWarroom,
  improvement: enhancedImprovement,
  governance,
});
const pageNames = {
  overview: "Control tower",
  network: "Factory intelligence",
  schedule: "Capacity & schedule",
  orders: "Order portfolio",
  orderDetail: "Order detail",
  investigate: "Disruption intelligence",
  incidentDetail: "Cause investigation",
  recovery: "Recovery studio",
  warroom: "Execution workspace",
  improvement: "Continuous improvement",
  governance: "Data & decision ledger",
};
go = async function (page) {
  if (typeof toggleNavigation === 'function') toggleNavigation(false);
  if (!pages[page]) page = "overview";
  requestController.abort();
  requestController = new AbortController();
  const epoch = ++navigation;
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
  $("#crumb-current").textContent = pageNames[page];
  document.title = pageNames[page] + " · PlantCore";
  history.replaceState(null, "", "#" + page);
  saveWorkspace();
  $("#content").innerHTML =
    '<div class="loading">Reconciling the operational model…</div>';
  try {
    await pages[page]();
    if (epoch !== navigation) return;
    if (typeof finishWorkspacePresentation === 'function') finishWorkspacePresentation();
    saveWorkspace();
  } catch (e) {
    if (e.name === "AbortError") return;
    $("#content").innerHTML =
      `<section class="card panel"><h2>This workspace could not be loaded</h2><p>${esc(e.message)}</p><button class="secondary" onclick="go(state.page)">Try again</button></section>`;
    console.error(e);
  }
  window.scrollTo(0, 0);
};
selectFactory = async (value) => {
  state.orderFactory = value;
  go("orders");
};
const originalFilterOrders = filterOrders;
filterOrders = () => {
  originalFilterOrders();
  saveWorkspace();
};
document
  .querySelectorAll("#nav button")
  .forEach((b) => b.addEventListener("click", () => go(b.dataset.page)));
window.addEventListener("hashchange", () => {
  const page = location.hash.slice(1);
  if (page !== state.page) go(page);
});
window.addEventListener("DOMContentLoaded", async () => {
  try {
    await loadScenarioCatalog();
    const meta = state.scenarios.find((s) => s.id === state.scenario);
    state.asOf = meta.as_of;
    $("#sidebarDate").textContent = "As of " + fmt(meta.as_of) + " · USD";
    let saved;
    try {
      saved = JSON.parse(sessionStorage.getItem("plantcore-workspace"));
    } catch {}
    if (saved?.scenario === state.scenario) Object.assign(state, saved);
    const page = location.hash.slice(1) || state.page;
    await go(page);
  } catch (e) {
    $("#content").innerHTML =
      `<div class="card panel"><h2>Could not load PlantCore</h2><p>${esc(e.message)}</p></div>`;
  }
});
async function runSimulation() {
  const target = $("#simulationResults");
  if (!target) return;
  target.innerHTML =
    '<div class="small muted">Simulating shipment variability…</div>';
  try {
    const d = await api(
      "/simulation?incident_id=" +
        encodeURIComponent(state.incident) +
        "&sigma=" +
        encodeURIComponent($("#sigma").value),
    );
    target.innerHTML =
      table(
        [
          "Plan",
          "On-time trials",
          "Ship P10",
          "Ship P50",
          "Ship P90",
          "Mean impact",
          "Cost P10–P90",
        ],
        d.options.map(
          (o) =>
            `<tr><td>${esc(o.name)}</td><td>${pct(o.on_time_probability)}</td><td>${fmt(o.ship_p10)}</td><td>${fmt(o.ship_p50)}</td><td>${fmt(o.ship_p90)}</td><td>${money(o.mean_cost)}</td><td>${money(o.cost_p10)} – ${money(o.cost_p90)}</td></tr>`,
        ),
      ) +
      `<p class="chart-foot">${d.draws.toLocaleString()} trials · σ ${d.sigma_days} days · seed ${d.seed}. ${esc(d.method)}</p>`;
  } catch (e) {
    if (e.name !== "AbortError")
      target.innerHTML = `<div class="note">${esc(e.message)}</div>`;
  }
}
async function renderCheckpoints() {
  const d = await api(
    "/checkpoints?incident_id=" + encodeURIComponent(state.incident),
  );
  state.pilot = d.pilot;
  $("#checkpointPanel").innerHTML = card(
    "Intervention pilot and persistence verification",
    `<div class="toolbar" style="justify-content:flex-start;margin-bottom:18px"><button class="secondary" onclick="pilotForm()">Start an evidence-based pilot</button>${d.pilot ? '<button class="primary" onclick="checkpointForm()">Record measured checkpoint</button>' : ""}</div>${d.pilot ? `<p class="small">Pilot #${d.pilot.id} · starts ${fmt(d.pilot.payload.start_date)} · target ≤ ${d.pilot.payload.target} events / production day · owner ${esc(d.pilot.actor)}</p>` : ""}<div class="detail-grid">${d.milestones.map((m) => `<div class="detail-tile"><small>${m.day}-day checkpoint</small><strong>${tag(m.status, m.status === "Improvement observed" ? "green" : "amber")}</strong></div>`).join("")}<div class="detail-tile"><small>Persistence assessment</small><strong>${d.sustained ? "Sustained observation" : "Not yet demonstrated"}</strong></div></div>${
      d.checks.length
        ? table(
            ["Period", "Events / day", "Volume / SMV", "FPY", "Assessment"],
            d.checks.map(
              (e) =>
                `<tr><td>${fmt(e.payload.start_date)} – ${fmt(e.payload.end_date)}</td><td>${e.payload.rate}</td><td>${num(e.payload.daily_volume)} / ${e.payload.style_smv}</td><td>${pct(e.payload.first_pass_yield)}</td><td>${esc(e.payload.assessment)}</td></tr>`,
            ),
          )
        : ""
    }<p class="chart-foot">${esc(d.note)}</p>`,
    "Documented baseline + QCD guardrail",
  );
}
function pilotForm() {
  showModal(
    "Define intervention pilot",
    `<div class="form-row">${inputField("Intervention start", "start_date", state.asOf, "date", "required")}${inputField("Target recurrence reduction · %", "reduction", 45, "number", 'required min="1" max="99"')}</div>${ownerEvidence()}`,
    async (f) => {
      await api("/pilots", {
        method: "POST",
        body: JSON.stringify({
          incident_id: state.incident,
          start_date: f.get("start_date"),
          target_reduction: Number(f.get("reduction")) / 100,
          actor: f.get("actor"),
          evidence: f.get("evidence"),
        }),
      });
    },
  );
}
function checkpointForm() {
  const pilot = state.pilot;
  showModal(
    "Measure intervention outcome",
    `<div class="form-row">${inputField("Observation period start", "start_date", pilot.payload.start_date, "date", "required")}${inputField("Observation period end", "end_date", "", "date", "required")}</div><div class="form-row">${inputField("Observed production days", "production_days", "", "number", 'required min="1"')}${inputField("Matching downtime events", "events", "", "number", 'required min="0"')}</div><div class="form-row">${inputField("Average daily output · units", "daily_volume", pilot.payload.baseline.daily_volume, "number", 'required min="1"')}${inputField("Average style SMV", "style_smv", pilot.payload.baseline.style_smv, "number", 'required min="0.1" step="0.1"')}${inputField("First-pass yield · %", "fpy", Math.round(pilot.payload.baseline.first_pass_yield * 10000) / 100, "number", 'required min="0" max="100" step="0.01"')}</div>${ownerEvidence()}`,
    async (f) => {
      await api("/checkpoints", {
        method: "POST",
        body: JSON.stringify({
          incident_id: state.incident,
          pilot_id: pilot.id,
          start_date: f.get("start_date"),
          end_date: f.get("end_date"),
          production_days: Number(f.get("production_days")),
          events: Number(f.get("events")),
          daily_volume: Number(f.get("daily_volume")),
          style_smv: Number(f.get("style_smv")),
          first_pass_yield: Number(f.get("fpy")) / 100,
          actor: f.get("actor"),
          evidence: f.get("evidence"),
        }),
      });
    },
  );
}
