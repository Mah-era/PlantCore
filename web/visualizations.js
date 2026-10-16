/* Visual evidence library. Every series is derived from the selected API snapshot. */
let visualSnapshot = null;
let visualCategory = "All";
const visualColors = [
  palette.navy,
  palette.teal,
  palette.amber,
  palette.red,
  palette.slate,
];
const vnum = (v) =>
  Number(v).toLocaleString("en-US", { maximumFractionDigits: 2 });
function visualRows(rows, key, label) {
  return rows
    .filter((r) => r[key] != null && Number.isFinite(Number(r[key])))
    .map((r) => ({ label: String(r[label]), value: Number(r[key]) }));
}
function visualBar(rows, unit = "", signed = false) {
  if (!rows.length)
    return emptyChart("This file has no evidence for this measure.");
  const limit = 12,
    shown = [...rows]
      .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
      .slice(0, limit);
  const w = 680,
    left = 210,
    right = 125,
    h = shown.length * 31 + 35;
  const max = Math.max(1, ...shown.map((r) => Math.abs(r.value))),
    width = w - left - right;
  const zero = signed ? left + width / 2 : left,
    scale = (signed ? width / 2 : width) / max;
  return `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(unit)} by category"><line x1="${zero}" x2="${zero}" y1="5" y2="${h - 25}" stroke="#a9bac8"/>${shown
    .map((r, i) => {
      const y = 8 + i * 31,
        length = Math.abs(r.value) * scale;
      return `<text class="chart-label" x="${left - 10}" y="${y + 15}" text-anchor="end">${esc(r.label.length > 25 ? r.label.slice(0, 23) + "…" : r.label)}</text><rect x="${r.value < 0 ? zero - length : zero}" y="${y}" width="${length}" height="21" fill="${r.value < 0 ? palette.teal : palette.navy}"><title>${esc(r.label)}: ${vnum(r.value)} ${esc(unit)}</title></rect><text class="chart-label" x="${w - right + 10}" y="${y + 15}">${vnum(r.value)}</text>`;
    })
    .join(
      "",
    )}<text class="chart-label" x="${left}" y="${h - 3}">${esc(unit)} · ranked by magnitude${rows.length > limit ? " · top 12 of " + rows.length : ""}</text></svg>`;
}
function visualDonut(rows, unit) {
  const total = rows.reduce((s, r) => s + r.value, 0);
  if (!total) return emptyChart("No counted records for this measure.");
  let offset = 0;
  return `<svg class="chart" viewBox="0 0 680 220" role="img" aria-label="${esc(unit)} composition">${rows
    .map((r, i) => {
      const length = (r.value / total) * 502.65;
      const mark = `<circle cx="150" cy="108" r="80" fill="none" stroke="${r.color || visualColors[i % 5]}" stroke-width="27" stroke-dasharray="${length} ${502.65 - length}" stroke-dashoffset="${-offset}" transform="rotate(-90 150 108)"><title>${esc(r.label)}: ${vnum(r.value)} (${pct(r.value / total)})</title></circle>`;
      offset += length;
      return mark;
    })
    .join(
      "",
    )}<text x="150" y="105" text-anchor="middle" font-size="26" fill="#142b40">${num(total)}</text><text x="150" y="127" text-anchor="middle" class="chart-label">${esc(unit)}</text>${rows.map((r, i) => `<rect x="295" y="${30 + i * 32}" width="12" height="12" fill="${r.color || visualColors[i % 5]}"/><text x="320" y="${41 + i * 32}" class="chart-label">${esc(r.label)} · ${num(r.value)} · ${pct(r.value / total)}</text>`).join("")}</svg>`;
}
function visualScatter(rows, xLabel, yLabel) {
  if (!rows.length)
    return emptyChart("No comparable observations for both axes.");
  const w = 680,
    h = 285,
    l = 65,
    b = 55,
    t = 25,
    r = 20;
  const xmax = Math.max(1, ...rows.map((p) => p.x)) * 1.1,
    ymax = Math.max(1, ...rows.map((p) => p.y)) * 1.1;
  const x = (v) => l + (v / xmax) * (w - l - r),
    y = (v) => h - b - (v / ymax) * (h - b - t);
  return `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(yLabel)} versus ${esc(xLabel)}">${[0, 0.25, 0.5, 0.75, 1].map((q) => `<line x1="${l}" x2="${w - r}" y1="${y(q * ymax)}" y2="${y(q * ymax)}" stroke="#e6edf2"/><text x="${l - 6}" y="${y(q * ymax) + 4}" text-anchor="end" class="chart-label">${num(q * ymax)}</text><text x="${x(q * xmax)}" y="${h - b + 18}" text-anchor="middle" class="chart-label">${num(q * xmax)}</text>`).join("")}${rows.map((p) => `<circle cx="${x(p.x)}" cy="${y(p.y)}" r="6" fill="${palette.teal}" opacity=".72" tabindex="0"><title>${esc(p.label)} · ${esc(xLabel)}: ${vnum(p.x)} · ${esc(yLabel)}: ${vnum(p.y)}</title></circle>`).join("")}<text x="${w / 2}" y="${h - 5}" text-anchor="middle" class="chart-label">${esc(xLabel)}</text><text x="12" y="15" class="chart-label">${esc(yLabel)}</text></svg>`;
}
function visualTable(rows) {
  if (!rows.length) return "";
  const keys = Object.keys(rows[0]).filter((k) => k !== "color");
  return `<details class="visual-evidence"><summary>Inspect chart data · ${rows.length} rows</summary><div class="table-wrap"><table><thead><tr>${keys.map((k) => `<th>${esc(k.replaceAll("_", " "))}</th>`).join("")}</tr></thead><tbody>${rows.map((r) => `<tr>${keys.map((k) => `<td>${esc(r[k] ?? "N/A")}</td>`).join("")}</tr>`).join("")}</tbody></table></div></details>`;
}
function buildVisuals(a, actions, audit) {
  const charts = [],
    add = (category, title, unit, note, rows, html) =>
      charts.push({ category, title, unit, note, rows, html:
        !rows.length && category === "Execution"
          ? emptyChart("No matching actions or events recorded in this scenario.")
          : html });
  const bar = (category, title, unit, note, rows, signed = false) =>
    add(category, title, unit, note, rows, visualBar(rows, unit, signed));
  const series = (category, title, unit, note, rows, lines, percent = false) =>
    add(
      category,
      title,
      unit,
      note,
      rows,
      sparkChart(rows, lines, {
        percent,
        ceiling:
          lines[0]?.key === "rework_rate"
            ? Math.max(0.01, ...rows.map((r) => (r.rework_rate || 0) * 1.15))
            : null,
      }),
    );
  const p = a.portfolio,
    feasible = p.filter((x) => x.status !== "blocked");
  const groups = (key, value) =>
    Object.entries(
      p.reduce((out, r) => {
        out[r[key]] = (out[r[key]] || 0) + (value ? r[value] : 1);
        return out;
      }, Object.create(null)),
    ).map(([label, value]) => ({ label, value }));
  const status = ["on_time", "late", "blocked"].map((label) => ({
    label: label.replaceAll("_", " "),
    color: { on_time: palette.teal, late: palette.amber, blocked: palette.red }[
      label
    ],
    value: p.filter((r) => r.status === label).length,
  }));
  add(
    "Delivery",
    "How much of the order book needs intervention?",
    "orders",
    "Forecast status; blocked orders have no feasible shipment date.",
    status,
    visualDonut(status, "orders"),
  );
  const unitStatus = ["on_time", "late", "blocked"].map((label) => ({
    label: label.replaceAll("_", " "),
    color: { on_time: palette.teal, late: palette.amber, blocked: palette.red }[
      label
    ],
    value: p
      .filter((r) => r.status === label)
      .reduce((s, r) => s + r.quantity, 0),
  }));
  add(
    "Delivery",
    "How many units sit behind each delivery status?",
    "units",
    "Quantity-weighted exposure complements order-count OTIF.",
    unitStatus,
    visualDonut(unitStatus, "units"),
  );
  bar(
    "Delivery",
    "Which customers carry delivery exposure?",
    "USD",
    "Modeled penalty and contribution-margin exposure, summed by customer.",
    groups("customer", "expected_exposure"),
  );
  bar(
    "Delivery",
    "Which orders have the least delivery buffer?",
    "days",
    "Positive = days after the deadline; negative = available buffer. Blocked orders excluded.",
    feasible.map((r) => ({ label: r.id, value: -r.slack_days })),
    true,
  );
  const buckets = [
    ["Over 7 days late", (r) => r.slack_days < -7],
    ["1–7 days late", (r) => r.slack_days < 0 && r.slack_days >= -7],
    ["0–3 days buffer", (r) => r.slack_days >= 0 && r.slack_days <= 3],
    ["Over 3 days buffer", (r) => r.slack_days > 3],
  ];
  bar(
    "Delivery",
    "Where is delivery slack concentrated?",
    "orders",
    "Feasible orders grouped by forecast buffer.",
    buckets.map(([label, fn]) => ({
      label,
      value: feasible.filter(fn).length,
    })),
  );
  const dueDays = [...new Set(p.map((r) => r.due_date))].sort();
  const due = dueDays.map((date) => ({
    date,
    required: p
      .filter((r) => r.due_date <= date)
      .reduce((s, r) => s + r.quantity, 0),
    planned: feasible
      .filter((r) => r.plan.expected_ship <= date)
      .reduce((s, r) => s + r.quantity, 0),
  }));
  series(
    "Delivery",
    "Does planned shipment keep up with due demand?",
    "cumulative units",
    "Required includes blocked orders; planned includes feasible full-order shipments.",
    due,
    [
      {
        key: "required",
        label: "Due demand",
        color: palette.amber,
        dashed: true,
      },
      { key: "planned", label: "Planned shipments", color: palette.teal },
    ],
  );
  const risk = p
    .filter((r) => r.on_time_probability != null)
    .map((r) => ({
      label: r.id,
      x: r.quantity,
      y: (1 - r.on_time_probability) * 100,
    }));
  add(
    "Delivery",
    "Which large orders have high modeled lateness risk?",
    "units / %",
    "Probability is a scenario assumption, not calibrated historical reliability.",
    risk,
    visualScatter(
      risk,
      "Order quantity · units",
      "Modeled late probability · %",
    ),
  );
  bar(
    "Network",
    "How is volume distributed across factories?",
    "units",
    "Planned factory assignment; blocked orders retain their source factory.",
    visualRows(a.factories, "units", "name"),
  );
  bar(
    "Network",
    "Where is the customer workload concentrated?",
    "units",
    "Total quantity by customer.",
    groups("customer", "quantity"),
  );
  bar(
    "Cost",
    "Which factories carry the greatest commercial exposure?",
    "USD",
    "Expected delivery exposure, not booked loss.",
    visualRows(a.factories, "expected_exposure", "name"),
  );
  bar(
    "Cost",
    "Which orders exceed their manufacturing target?",
    "USD",
    "Modeled manufacturing minus target; negative is below target. Blocked orders excluded.",
    feasible.map((r) => ({ label: r.id, value: r.cost_variance })),
    true,
  );
  bar(
    "Cost",
    "How much manufacturing spend is assigned by factory?",
    "USD",
    "Manufacturing proxy summed over feasible orders.",
    a.factories.map((f) => ({
      label: f.name,
      value: feasible
        .filter((r) => r.factory_id === f.id)
        .reduce((s, r) => s + r.manufacturing_cost, 0),
    })),
  );
  const cost = p
    .filter((r) => r.manufacturing_cost != null)
    .map((r) => ({
      label: r.id,
      x: r.manufacturing_cost,
      y: r.expected_exposure,
    }));
  add(
    "Cost",
    "Which planned investments carry delivery exposure?",
    "USD",
    "Compares manufacturing proxy with expected delivery exposure.",
    cost,
    visualScatter(
      cost,
      "Manufacturing proxy · USD",
      "Expected delivery exposure · USD",
    ),
  );
  const utilization = a.heatmap.map((l) => {
    const capacity = l.cells.reduce((s, c) => s + c.capacity_minutes, 0),
      reserved = l.cells.reduce((s, c) => s + c.reserved_minutes, 0);
    return {
      label: l.factory_id + " / " + l.name,
      value: capacity ? (100 * reserved) / capacity : 0,
    };
  });
  bar(
    "Capacity",
    "Which lines carry the most reserved capacity?",
    "%",
    "42-day reserved minutes / available minutes; closed days contribute zero minutes.",
    utilization,
  );
  bar(
    "Capacity",
    "Where can planners inspect unused sewing capacity?",
    "minutes",
    "42-day available minus reserved minutes; compatibility and gates still determine usability.",
    a.heatmap.map((l) => ({
      label: l.factory_id + " / " + l.name,
      value: l.cells.reduce(
        (s, c) => s + Math.max(0, c.capacity_minutes - c.reserved_minutes),
        0,
      ),
    })),
  );
  const daily = a.days.map((date) => ({
    date,
    available: a.heatmap.reduce(
      (s, l) => s + l.cells.find((c) => c.date === date).capacity_minutes,
      0,
    ),
    reserved: a.heatmap.reduce(
      (s, l) => s + l.cells.find((c) => c.date === date).reserved_minutes,
      0,
    ),
  }));
  series(
    "Capacity",
    "When does sewing demand approach available capacity?",
    "minutes / day",
    "Daily pooled sewing minutes; individual line constraints remain binding.",
    daily,
    [
      {
        key: "available",
        label: "Available",
        color: palette.slate,
        dashed: true,
      },
      { key: "reserved", label: "Reserved", color: palette.navy },
    ],
  );
  bar(
    "Capacity",
    "Which downstream stage reaches its daily limit?",
    "peak %",
    "Peak reserved units / factory daily stage capacity within the 42-day horizon.",
    a.stage_load
      .filter((r) => r.peak_utilization != null)
      .map((r) => ({
        label: r.factory_id + " / " + r.stage,
        value: r.peak_utilization * 100,
      })),
  );
  series(
    "Capacity",
    "Where does planned work queue between stages?",
    "units",
    "End-of-day balances from scheduled stage reservations; not observed shop-floor inventory.",
    a.flow,
    [
      { key: "cut_queue", label: "After cutting", color: palette.navy },
      { key: "sew_queue", label: "After sewing", color: palette.teal },
      { key: "finish_queue", label: "After finishing", color: palette.amber },
      {
        key: "inspection_queue",
        label: "After inspection",
        color: palette.red,
      },
    ],
  );
  series(
    "Capacity",
    "When are packed goods waiting for shipment?",
    "units",
    "Ready-to-ship stock is packed quantity less cumulative shipments.",
    a.flow,
    [
      { key: "ready_to_ship", label: "Packed waiting", color: palette.amber },
      { key: "shipped", label: "Cumulative shipped", color: palette.teal },
    ],
  );
  series(
    "Quality",
    "Is first-pass yield holding as volume changes?",
    "ratio",
    "Observed first-pass units / actual output, aggregated by production day.",
    a.history,
    [
      {
        key: "first_pass_yield",
        label: "First-pass yield",
        color: palette.teal,
      },
    ],
    true,
  );
  series(
    "Quality",
    "Is the rework burden rising?",
    "ratio",
    "Observed rework units / actual output; missing history remains unavailable.",
    a.history,
    [{ key: "rework_rate", label: "Rework rate", color: palette.red }],
    true,
  );
  series(
    "Quality",
    "Is production meeting the recorded target?",
    "ratio",
    "Actual output / target on supplied production days; can exceed 100%.",
    a.history,
    [{ key: "adherence", label: "Output adherence", color: palette.navy }],
    true,
  );
  bar(
    "Quality",
    "Which factories have the highest rework rate?",
    "%",
    "Observed rework / output. Factories without output evidence are excluded.",
    a.factories
      .filter((f) => f.rework_rate != null)
      .map((f) => ({ label: f.name, value: f.rework_rate * 100 })),
  );
  bar(
    "Quality",
    "Where is attendance reducing staffing readiness?",
    "% absent",
    "1 − present / scheduled from supplied historical labor records.",
    a.factories
      .filter((f) => f.attendance != null)
      .map((f) => ({ label: f.name, value: (1 - f.attendance) * 100 })),
  );
  bar(
    "Quality",
    "Which downtime causes consume the most time?",
    "minutes",
    "Cause-coded observations; association alone does not verify a root cause.",
    a.pareto.map((r) => ({ label: r.cause, value: r.minutes })),
  );
  const actionStatus = ["open", "in_progress", "blocked", "done"].map(
    (label) => ({
      label: label.replaceAll("_", " "),
      value: actions.filter((r) => r.status === label).length,
    }),
  );
  add(
    "Execution",
    "How much response work remains open?",
    "actions",
    "Current action status for the active scenario.",
    actionStatus,
    visualDonut(actionStatus, "actions"),
  );
  const owners = Object.entries(
    actions
      .filter((r) => r.status !== "done")
      .reduce((o, r) => {
        o[r.owner] = (o[r.owner] || 0) + 1;
        return o;
      }, Object.create(null)),
  ).map(([label, value]) => ({ label, value }));
  bar(
    "Execution",
    "Who owns the largest open action workload?",
    "actions",
    "Includes open, in-progress, and blocked actions.",
    owners,
  );
  bar(
    "Execution",
    "Which owners have overdue actions?",
    "actions",
    "Due date earlier than the scenario planning date; completed actions excluded.",
    Object.entries(
      actions
        .filter((r) => r.overdue)
        .reduce((o, r) => {
          o[r.owner] = (o[r.owner] || 0) + 1;
          return o;
        }, Object.create(null)),
    ).map(([label, value]) => ({ label, value })),
  );
  bar(
    "Execution",
    "Which management interventions have been recorded?",
    "events",
    "Recorded operating ledger events, grouped by type; zero does not imply an operational failure.",
    Object.entries(
      audit.events.reduce((o, r) => {
        o[r.kind] = (o[r.kind] || 0) + 1;
        return o;
      }, Object.create(null)),
    ).map(([label, value]) => ({ label, value })),
  );
  bar(
    "Evidence",
    "Which source collections support this analysis?",
    "records",
    "Record counts measure coverage, not correctness or completeness.",
    Object.entries(a.coverage).map(([label, value]) => ({ label, value })),
  );
  return charts;
}
function visualPanel(c, index, a, exporting = false) {
  return `<section class="card panel visual-panel" data-category="${esc(c.category)}"><div class="card-head"><div><span class="source-label">${esc(c.category)} · ${esc(c.unit)}</span><h2>${esc(c.title)}</h2></div>${exporting ? "" : `<button class="quiet small" onclick="exportVisualCSV(${index})">↓ Data</button>`}</div>${c.html}<p class="chart-foot">${esc(c.note)}</p><p class="chart-foot">Source: ${esc(a.scenario.name)} · as of ${esc(a.as_of)} · ${a.scenario.synthetic ? "simulated data" : "uploaded data"}</p>${visualTable(c.rows)}</section>`;
}
async function visualAnalytics() {
  const [a, actions, audit] = await Promise.all([
    api("/analytics"),
    api("/actions"),
    api("/audit"),
  ]);
  visualSnapshot = { a, charts: buildVisuals(a, actions, audit) };
  renderVisualGallery();
}
function renderVisualGallery() {
  const { a, charts } = visualSnapshot;
  const categories = ["All", ...new Set(charts.map((c) => c.category))];
  const visible = charts
    .map((c, i) => ({ c, i }))
    .filter(
      ({ c }) => visualCategory === "All" || c.category === visualCategory,
    );
  $("#content").innerHTML =
    header(
      "Visual evidence / " + fmt(a.as_of),
      "Visual analytics library",
      `${charts.length} analytical views connect the active file to delivery, capacity, cost, quality and execution decisions. Missing evidence remains explicit.`,
      `<button class="primary" onclick="downloadVisualReport()">↓ Download visual report</button>`,
    ) +
    `<div class="toolbar visual-filters">${categories.map((c) => `<button class="${c === visualCategory ? "primary" : "secondary"}" onclick="visualCategory=${jsarg(c)};renderVisualGallery()">${esc(c)}</button>`).join("")}<span class="muted">${visible.length} views · hover chart marks or expand source tables</span></div><div class="visual-grid">${visible.map(({ c, i }) => visualPanel(c, i, a)).join("")}</div>`;
}
function saveVisualBlob(content, type, name) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}
function exportVisualCSV(index) {
  const c = visualSnapshot.charts[index];
  if (!c.rows.length) {
    toast("No source rows for this chart.");
    return;
  }
  const keys = Object.keys(c.rows[0]).filter((k) => k !== "color");
  const cell = (v) =>
    '"' +
    (typeof v === "string"
      ? v.replace(/^[=+@-]/, "'$&")
      : String(v ?? "")
    ).replaceAll('"', '""') +
    '"';
  saveVisualBlob(
    [keys, ...c.rows.map((r) => keys.map((k) => r[k]))]
      .map((r) => r.map(cell).join(","))
      .join("\r\n"),
    "text/csv;charset=utf-8",
    `plantcore-chart-${index + 1}.csv`,
  );
}
async function downloadVisualReport() {
  try {
    const [a, actions, audit] = await Promise.all([
      api("/analytics"),
      api("/actions"),
      api("/audit"),
    ]);
    const charts = buildVisuals(a, actions, audit);
    const styles = await (await fetch("./app.css")).text();
    saveVisualBlob(
      `<!doctype html><html><head><meta charset="utf-8"><title>PlantCore visual report</title><style>${styles}body{min-width:0;background:#f4f7fa;padding:32px}.visual-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}.visual-panel{break-inside:avoid;overflow:hidden}.chart{width:100%}h1{font-size:30px}.table-wrap{overflow:auto;max-height:400px}@media print{body{padding:0}.visual-grid{display:block}.visual-panel{margin-bottom:20px}details{display:none}}</style></head><body><h1>PlantCore · Visual analysis report</h1><p>${esc(a.scenario.name)} · as of ${esc(a.as_of)} · ${a.scenario.synthetic ? "Simulated data" : "Uploaded data"} · ${charts.length} analytical views</p><p>Forecasts and cost exposure are scenario estimates. Historical charts use supplied observations only. Expand chart data to inspect the underlying values. This report is self-contained and printable.</p><div class="visual-grid">${charts.map((c, i) => visualPanel(c, i, a, true)).join("")}</div></body></html>`,
      "text/html;charset=utf-8",
      "plantcore-visual-report.html",
    );
    toast("Visual report downloaded");
  } catch (e) {
    toast(e.message);
  }
}
pages.visuals = visualAnalytics;
pageNames.visuals = "Visual analytics";
