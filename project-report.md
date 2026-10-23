# PlantCore — Multi-Factory Production Planning, Disruption Recovery & Improvement Platform

## Project report and implementation record

**Report date:** 23 October 2026 (Asia/Dhaka)
**Repository:** `mah-era/PlantCore`  
**Application:** FastAPI and SQLite decision workspace, available as a local server and an interactive browser build on GitHub Pages
**Implementation status:** Version 0.2 professional desktop decision workspace with browser deployment; production deployment gates remain explicit
**Data status:** packaged examples and 20 scenario files are synthetic; uploaded files may be user supplied and retain their own synthetic label

This report records the business concept, the software that exists, its data and calculations, the user workflow, the validation performed, and the remaining gaps. “Implemented” means there is corresponding executable code in this repository. It does not mean a live factory integration or production deployment. All dates, prices, capacity, probability, and performance values from packaged examples are simulated.

> **Current release:** Chapter 18 documents the version 0.2 transformation. Chapter 19 documents the interactive GitHub Pages deployment and supersedes earlier hosting claims. The current full requirement review is in [docs/requirement-coverage.md](docs/requirement-coverage.md).

## 1. Executive summary

The platform brings apparel order allocation, daily capacity scheduling, delivery risk, incident investigation, recovery comparison, factory commitments, RACI actions, and continuous improvement into one local decision workspace. It answers a manager’s immediate questions: what can ship, what is blocked or late, why it may be at risk, which modeled responses are feasible, what those responses may cost, and who owns follow-up.

The implemented system is an explainable **daily-capacity heuristic**, not a global optimization product. It works from a selected scenario document; every dashboard and report request reads the active scenario and recalculates the forecast. Users can select the baseline or one of 20 packaged scenarios, or upload a full scenario JSON or an order table in CSV, XLSX, or JSON. Uploaded order tables build a network from their own rows and disclose inferred assumptions. Missing history remains unavailable rather than appearing as fabricated historical KPI values.

The strongest implemented demonstration is the synthetic recurring flatlock needle-failure incident on Gazipur Works line L7. The application connects the line’s downtime history to the at-risk hoodie order, shows Pareto and structured cause evidence, compares recovery options and commercial exposure, records an approved option with its rejected alternatives, creates a factory commitment, and supports action and PDCA follow-up.

## 2. Business context and objective

Apparel production plans change when materials arrive late, required machines fail, staffing falls, inspections hold output, quality defects increase, factories close, demand changes, or transit stretches. Those events affect quality, cost, and delivery at once. A production manager needs a common operating picture and a traceable decision record, rather than disconnected spreadsheets and anecdotal explanations.

The intended end-to-end management loop is:

1. Model factories, orders, materials, capacity, and deadlines.
2. Allocate work to compatible resources and produce a feasible forecast.
3. Detect delivery risk and identify the specific blocking gate or capacity exposure.
4. Investigate recurring causes without treating correlation as confirmed causation.
5. Compare feasible response options on QCD, commercial impact, labor, lead time, and effects on other orders.
6. Record the decision, factory commitment, owners, dependencies, and escalation.
7. Reforecast after approved production changes.
8. Check whether the intervention improves performance and propose controlled planning-rule changes.

Primary intended users are production managers, factory planners, quality managers, merchandisers, material coordinators, finance representatives, logistics coordinators, factory management, and regional production offices. Phase 1 has workflow fields for these roles but does **not** authenticate users or enforce role permissions.

## 3. Scope at a glance

| Capability | Phase 1 implementation | Material limit |
| --- | --- | --- |
| Multi-factory model | Factories, lines, styles, orders, material gates, history, incidents, actions | No live ERP/MES feed or detailed machine work-center calendar |
| Allocation | Feasibility checks, ranked candidate lines, rejection reasons, displacement count | One-line recommendation per order; no order-quantity split optimizer |
| Scheduling | Daily cutting, sewing, finishing, inspection, packing, and transit | Coarse stages and greedy reservations, not operation-level finite capacity |
| Control tower | Scenario-aware KPIs, factories, trend, line load, readiness, risk timeline, exceptions | Forecasts illustrative; no push alerts |
| Disruption analysis | Source incidents plus derived forecast-risk exceptions, impact and evidence | No automatic causal inference or calibrated confidence intervals |
| Root cause | Downtime Pareto, six-category fishbone prompts, abbreviated 5 Whys, verified-cause label | No full guided investigation or evidence-file attachments |
| Recovery | Baseline, repair/overtime, line transfer, factory transfer, subcontract, freight, split shipment | Some options are simplified assumptions; no material expedite, temporary-shift, or lower-priority rescheduling solver |
| Finance/negotiation | Illustrative expected cost components, commitments, completion status | No accounting integration, detailed supplier chargebacks, or negotiated-price engine |
| War room | RACI-like fields, dependencies, due dates, decision history, commitment updates | No external notifications or authenticated approvals |
| PDCA/learning | Baseline, observations, comparability screen, rule proposal and review | No automated 30/60/90 reminders, sustained-effect proof, or deployment of approved rules |
| Validation | 62 automated tests and 20 packaged scenario files | Tests cannot prove every possible uploaded file or operational condition |

## 4. Architecture and repository map

The application has four main layers:

```text
CSV / XLSX / JSON input and 20 packaged scenario JSON files
                     │
                     ▼
  importers.py + scenarios.py: normalize and validate
                     │
                     ▼
  store.py: active scenario and scenario-scoped SQLite records
                     │
                     ▼
  engine.py: allocation, schedule, recovery, Pareto, baselines
                     │
                     ▼
  main.py FastAPI ── web/index.html + app.js + app.css
                     │
                     └── HTML / JSON / CSV report downloads
```

| Path | Responsibility |
| --- | --- |
| `app/seed.py` | Deterministic synthetic network and focal incident |
| `app/scenarios.py` | Full-scenario schema, relational checks, packaged-file discovery |
| `app/importers.py` | CSV, XLSX, and order-row JSON conversion, aliases, defaults, assumptions |
| `app/store.py` | SQLite schema, scenario catalog/selection, uploads, scenario-scoped workflow records |
| `app/engine.py` | Capacity model, scheduling, allocation candidates, recovery economics, Pareto, dispatch benchmarks |
| `app/main.py` | API, computed views, decisions, commitments, actions, PDCA, rules, reports |
| `web/index.html` | Desktop application shell, navigation, upload and report controls |
| `web/app.js` | Dashboard rendering, filters, drill-downs, upload, decisions, action and rule forms |
| `web/app.css` | Neutral professional dashboard styling |
| `scripts/generate_scenarios.py` | Reproducible generation of 20 synthetic scenario documents |
| `test-files/` | The 20 uploadable, self-contained JSON scenarios |
| `examples/sample-orders.csv` | Example order-table input and downloadable CSV template |
| `tests/` | Planning, workflow, import, scenario, and regression tests |
| `data/platform.db` | Local mutable SQLite database, created automatically |
| `requirements.txt` | FastAPI, Uvicorn, openpyxl dependency ranges |

The browser is served by the same FastAPI process at `/`. The JavaScript app requests JSON endpoints and rerenders the selected view. SQLite stores the current scenario ID and durable workflow records; it does not store an independent copy of every computed forecast. Forecasts are recomputed on reads.

## 5. Data model and synthetic network

### 5.1 Full scenario document

A complete scenario is JSON with `schema_version: 1`, a `meta` object, and a `data` object. Required `meta` values include `id`, `name`, `description`, and boolean `synthetic`. Optional `as_of` and `holidays` control the forecast calendar. The `data` object contains arrays named `factories`, `lines`, `styles`, `orders`, `materials`, `production`, `downtime`, `quality_holds`, `labor`, `incidents`, and `actions`. The current scenario can be downloaded from the web application to see the exact shape.

The validator requires at least one factory, line, style, and order; verifies IDs and cross-references; requires exactly one material record per order; checks dates and finite numeric values; validates capacity, staffing, quality, reliability, shortages, quality-hold states, and action states; and caps each collection at 3,000 rows. Order quantity is limited to 10,000,000 units to keep the prototype's numeric and schedule behavior bounded. The upload endpoint caps the payload at 3,000,000 bytes. Invalid inputs return an explanatory HTTP 400 or 413 response.

### 5.2 Packaged synthetic baseline

The deterministic seed, dated **14 October 2026**, contains:

- **Three partner factories:** Dhaka Precision (F1), Chattogram Apparel (F2), and Gazipur Works (F3). They differ in product capabilities, stage capacities, unit costs, quality, delivery reliability, logistics time, and compliance status.
- **Eight sewing lines:** L1–L3 at F1, L4–L6 at F2, and L7–L8 at F3. Lines differ in staffing, efficiency, skills, available machines, and maintenance dates.
- **Ten styles:** knit, woven, and denim garments with named operation sequences, standard minute values (SMV), required machine, and a designated bottleneck operation.
- **Thirty orders:** customer, style, assignment, quantity, due/material dates, target cost, priority, unit contribution margin, minimum lot, and quality release.
- **Material records:** fabric readiness, trim readiness, and shortage units for each order.
- **Historical events:** daily target/actual/first-pass/rework output, line attendance, downtime, and quality holds.
- **Management history:** three source incidents and four source actions in the baseline, before any derived forecast-risk exceptions.

The focal example is order **PO-2618**, a knit hoodie of **1,450 units** assigned to **Gazipur Works line L7** with a **23 October 2026** deadline. Source incident **INC-001** records repeated flatlock needle failures, **665 lost minutes**, and a verified maintenance-standard omission. Its evidence states seven FL-07 needle failures in 19 production days, no scheduled needle replacement in service logs, and supervised wear inspection. The application still treats the *effectiveness of the intervention* as unverified until later observations are recorded.

### 5.3 Uploaded order tables

CSV, XLSX, a JSON array of order rows, or `{ "orders": [...] }` can be uploaded. XLSX reads the `Orders` sheet when present, otherwise the active sheet. Required logical columns are `order_id`, `quantity`, `material_date`, and `due_date` as ISO dates. Aliases include `qty`, `deadline`, `factory`, `line`, `style`, `standard_minutes`, and `required_machine`. Useful optional values include `as_of`, `synthetic`, customer, factory/line/style names, category, machine, SMV, operators, efficiency, factory stage capacities, cost, quality, reliability, transit days, priority, quality release, fabric/trims readiness, shortage, margin, and target cost.

The importer constructs factory, line, style, order, and material objects from the supplied rows. Missing network values receive explicit illustrative defaults, including F1/L1/S1 identifiers, woven/lockstitch/20-minute style, 30 operators at 75% efficiency, 2,000 units per factory stage per day, factory cost 5, quality 95%, reliability 85%, and two logistics days where those fields are absent. The planning date is the supplied `as_of` or earliest material date. It infers supported skills/machines from assigned orders, so an order-only file cannot prove that a factory owns every real machine it claims. The assumptions appear in scenario metadata, the dashboard, and reports.

Order-table uploads contain no historical production, downtime, incident, or quality data unless a full scenario JSON is supplied. The app reports historical first-pass yield and schedule adherence as **N/A** in that case. If an imported order is late or blocked and has no source incident, the app creates a *derived forecast-risk exception* and proposed follow-up action in the computed view. That exception is labeled as derived, and its cause is not represented as verified.

### 5.4 Scenario selection and isolation

The catalog consists of the baseline, 20 built-in scenario files, and saved uploads. Selecting or uploading a scenario changes the active ID in SQLite. Decision, commitment, action-update, PDCA, and rule records carry a scenario ID so a decision made in one scenario does not silently alter another scenario. Reloading the browser reads the active scenario again. The active scenario JSON can be exported.

## 6. Planning and calculation methods

### 6.1 Allocation feasibility

For each candidate line, the engine checks factory compliance, nonzero capacity in every required pooled stage, product-category support, line skill, required machine, minimum lot, unresolved material shortage, order quality-release status, and open quality holds. A rejected candidate carries readable reasons. Feasible candidates receive a ranking score:

`factory unit cost + 20 × (1 − factory quality) + 12 × (1 − delivery reliability) + 3 × forecast late days`

The candidate list also shows forecast shipment, changeover estimate, and the number of other orders whose shipment forecast changes in the trial. This is an interpretable score, not a mathematical proof of an optimal allocation. The current engine assigns an entire order to one line for a trial; it does not optimize fractional allocation across factories.

### 6.2 Working calendar and daily capacity

The working calendar excludes Sundays and supplied holidays. Factory shutdown dates and line maintenance dates make the corresponding line capacity zero. A line’s daily output is calculated from eight shift hours, operator count, line efficiency, historical attendance ratio (or a 94% fallback when no labor history exists), optional overtime, style SMV, and a downtime factor. The downtime loss is average logged downtime minutes per observed production day divided by 480, capped at 35%. A modeled repair removes that historical downtime reduction for the recovery trial.

In simplified notation:

`sewing units/day = floor[480 × (1 + overtime fraction) × operators × efficiency × attendance × (1 − modeled downtime loss) / SMV]`

Daily line reservations are stored in **SMV minutes**, so orders with different garment SMVs cannot overbook a line by each claiming the same unit capacity. A 12% first-day changeover also consumes line minutes. Future-dated labor, output, and downtime records are excluded from historical calculations at the scenario `as_of` date.

This is a planning assumption, not an equipment-specific reliability model. Daily capacity depends on the selected file’s staffing, efficiency, attendance, downtime, and style SMV. The seed scenario includes changeover by deducting 12% of the line’s first sewing day capacity for a new order.

### 6.3 Finite-capacity schedule

Orders are sorted by priority descending, deadline ascending, then ID. Alternative benchmark runs use first-come-first-served or earliest due date ordering. For each order, the engine:

1. Waits until the scenario date, order/material release dates, and any recovery implementation date.
2. Reserves pooled factory cutting capacity by day.
3. Starts sewing on the next working day, reserves available line capacity each day, and applies first-day changeover.
4. Reserves pooled finishing capacity after sewing.
5. Starts inspection after a further working-day handoff.
6. Reserves packing capacity after inspection.
7. Adds normal factory logistics days, or one day for expedited finished-goods freight.

Reservations are tentative until the order clears every modeled stage. An order that cannot be completed within the **120-day planning horizon** returns a blocked reason and does not consume capacity needed by later orders. Quantity is represented per sewing day in the plan. Cutting, finishing, inspection, and packing are factory-wide unit pools; detailed operation stations, WIP transfer buffers, and rework loops are outside Phase 1.

An unresolved material shortage, pending quality release, or open quality hold blocks scheduling because no confirmed release date exists in the model. `expected_ship` is omitted for blocked orders. For feasible orders, `delay_days = max(0, expected_ship − customer due date)` in calendar days. The order’s forecast OTIF status is on-time only if the complete modeled quantity can ship by the due date. These are forecast measures, not actual shipment evidence.

### 6.4 Control-tower calculations

The overview recalculates from the selected scenario and optional factory filter. It shows active orders, at-risk orders (late **or** blocked), forecast OTIF, historical first-pass yield, historical schedule adherence, open exceptions, overdue actions, late units, blocked orders, downtime minutes and leading cause, absenteeism, rework units, material readiness, quality-pending count, open holds, factory QCD summaries, line load, daily target-versus-actual trend, shipment-risk timeline, and priority exception list.

Key definitions are exposed at `/api/definitions`:

- **Forecast OTIF:** orders whose full modeled quantity has a shipment date on/before the deadline divided by active orders. Blocked orders fail this measure.
- **Historical first-pass yield:** first-pass acceptable units / actual production units in supplied production records; N/A without those records.
- **Historical schedule adherence:** actual units / target units in supplied production records; N/A without target history.
- **Line-load utilization:** scheduled sewing workload in SMV minutes / available line minutes over distinct scheduled days. Subcontracted output is included in gross workload; this is not a whole-horizon plant utilization measure.
- **Absenteeism:** `1 − total present / total scheduled` from supplied line labor records; N/A without labor history.
- **Open exception:** source or derived incident whose status is not closed. This is not synonymous with an at-risk order; some source incidents remain open even when the current forecast improves.

The interface identifies missing history with coverage counts and neutral empty states. Packaged built-in scenarios additionally show the change in at-risk orders and exposed units versus the original synthetic network.

### 6.5 Incident impact and root-cause analysis

An incident is linked to an order, factory, and line. Its expected delay comes from the current schedule. When lost minutes are known, approximate lost units are `round(lost_minutes × operators × efficiency / style SMV)`. Unknown lost minutes remain N/A rather than zero. The displayed recovery deadline subtracts the factory transit allowance and three calendar days from the customer due date. Commercial exposure uses an illustrative `18% × ordered units × contribution margin per unit`. A feasible plan is labeled with an illustrative ±2-day range; blocked plans have no range until the gate is resolved.

For recurring downtime incidents, Pareto ranks downtime causes on the incident line by summed minutes and supplies each cause’s share and cumulative share. The incident detail also gives a six-category fishbone prompt (machine, method, material, people, measurement, environment), immediate-cause wording, source evidence, verified-root-cause status, a compact 5 Whys narrative, and recurrence count per observed production days. These tools organize evidence; they do not automatically prove causality. A source-provided verified cause is shown as verified only when the file explicitly supplies it.

### 6.6 Recovery alternatives and economics

The simulator produces or explains rejection of seven options: current plan, controlled overtime with modeled repair where downtime history exists, compatible line transfer in the same factory, partner-factory transfer, subcontracted bottleneck capacity, expedited finished-goods freight, and split shipment with a negotiated balance date. Option implementation dates are modeled for overtime/repair (one day), line transfer (two), partner transfer (three), and subcontracting (two). Subcontracting adds a 35% sewing allowance but only reserves the in-house share against in-house line capacity.

Each feasible option includes expected shipment date, late days, illustrative on-time probability, quality risk, incremental spend, expected late penalty, expected contribution-margin exposure, expected quality cost, estimated cost shifted to other orders, total modeled impact, lead time, labor note, commitment needed, compliance/customer-approval note, capacity requirement, and affected orders. Infeasible options remain visible with a reason.

The probability is a **normal-CDF approximation with a fixed 1.8-day forecast standard deviation**, derived from the gap between expected shipment and deadline. A shipment dated on the deadline is counted within that deadline day's interval; the discrete-day continuity threshold is `0.5 − (expected ship date − due date)`. It has not been fitted to historical outcomes. The illustrative financial components are:

`incremental spend + expected late penalty + expected margin exposure + expected quality loss + displaced-order cost`

The late penalty uses `1.15 × units × (1 − on-time probability)`. Margin exposure uses `0.18 × units × margin per unit × (1 − on-time probability)`. Quality loss uses `3.2 × units × modeled quality-risk fraction`, with the quality-risk fraction bounded to 0–100%. An order delayed by a trial contributes `0.35 × its units` as a proxy cost shifted to other orders; an order made unschedulable contributes a larger penalty-plus-margin proxy and appears in the affected-order list. Option-specific operational premiums are fixed assumptions in code; the resulting dollar amounts are **comparative estimates**, not validated invoices or negotiated prices. Split shipment reduces the late penalty and margin-exposure proxies to 45% and adds a handling premium; customer acceptance remains required. The model does not calculate exact partial shipment dates/quantities or reprice a customer contract.

### 6.7 Dispatch-rule comparison

The validation endpoint compares five transparent dispatch rules on the selected file: priority-aware, first-come-first-served, earliest due date, lowest-cost compatible factory, and highest-available-capacity compatible line. It reports late orders, forecast OTIF, estimated operating-plus-exposure cost, plan changes, capacity utilization, constraint violations, and a compute note. The cheapest factory can still produce a delivery failure; the fastest line can carry higher quality exposure. Results are directional because dispatch rules and financial exposures use simplified assumptions, and there is no manual-recovery baseline implementation.

## 7. User experience and end-to-end flow

The desktop dashboard uses a neutral professional theme. The six main views are **Control tower**, **Orders & allocation**, **Disruption lab**, **Recovery simulator**, **Production war room**, and **PDCA & learning**. The top bar provides a scenario selector, upload control, CSV template, report selector, data-source badge, and KPI definitions. Mobile behavior was explicitly outside the requested audit scope.

The expected navigation path is:

1. Choose a packaged scenario or upload a compatible file. The selected file becomes active and the dashboard reloads its calculations.
2. Use the control tower to filter the factory, inspect readiness and risk, and open a specific order or exception.
3. Inspect the order’s material gate, stage forecast, daily sewing schedule, and candidate allocations with rejection reasons.
4. Open an incident to review source evidence, cause status, Pareto, fishbone, and affected schedule.
5. Compare recovery alternatives and enter an approver, decision rationale, factory owner, written commitment, and due date.
6. Use the war room to update RACI actions and factory-commitment status, respecting action dependencies.
7. Record PDCA observations and propose a planning-rule adjustment for management review.
8. Download a management HTML, full JSON, order forecast CSV, or the active scenario JSON.

The JavaScript UI escapes supplied text for HTML and escapes IDs inserted into inline handler arguments. Query-based API aliases support order and incident identifiers containing slashes. Failed uploads surface validation feedback, including row-specific errors for order tables. Reloading the page should retain the active scenario and server-side records because selection and workflow data live in SQLite; transient navigation and filter state live only in browser memory.

## 8. Decision, action, commitment, and PDCA records

### 8.1 Decision record

Submitting a recovery decision requires a known, open incident, a currently feasible option, a rationale, an approver name, a factory owner, a written commitment, and a due date on/after the scenario date. The stored decision includes a snapshot of **all alternatives**, so rejected options and their modeled values remain reviewable. The application then creates a factory commitment. Approved production-changing options are translated into schedule overrides on subsequent reads. The baseline and split-shipment choices do not overwrite an already active production recovery override.

This is an audit-oriented record of a named approver, **not** identity-verified authorization. No role-based access control, e-signature, or multi-level approval exists.

### 8.2 War room

Actions include responsible owner, accountable person, consulted and informed parties, due date, status, dependency, and evidence. The API flags overdue and blocked actions. It prevents marking an action done while its recorded prerequisite remains incomplete. The board shows action counts, critical-path dependency, decision history, and factory commitments. Commitments can be open, fulfilled (with actual date), or missed. There are no outbound notifications or automatic escalation messages.

### 8.3 Improvement loop

PDCA records support stages `plan`, `do`, `check`, and `act`. A check must include observed event rate, daily volume, style complexity, and a written observation. The baseline derives line-specific downtime events per observed production day, average daily output, style SMV, and first-pass yield from supplied history. For a recurring-downtime case, the target rate is 55% of baseline. A check is preliminarily comparable only when volume differs by at most 20% and style SMV by at most 10%. The response says whether the target was preliminarily met, whether conditions are incomparable, or whether the intervention should be reopened. It explicitly does **not** certify a sustained 30/60/90-day causal effect.

A non-downtime incident does not receive an invented downtime recurrence target: the UI asks the investigator to define a measure appropriate to that incident type. A rule proposal stores key, old value, new value, reason, and incident. Management may record approval or rejection and approver name. Approved rules are **not auto-applied** to scheduling; promotion and versioned deployment are later-phase work.

## 9. Reports and API surface

The report selector offers:

- **Management HTML:** printable view of the selected scenario’s management summary and order outcomes. Browser printing may produce a PDF.
- **Management JSON:** scenario metadata, overview, orders, incidents, actions, benchmarks, decisions, commitments, PDCA, rules, definitions, and caveat.
- **Order forecast CSV:** scenario, order/customer/style, planned factory and line, quantity, material release/readiness/shortage, quality gate, due and expected shipment, late days, blocked/feasible status, priority, and target cost. User-originated text beginning with spreadsheet formula markers is prefixed for safer spreadsheet opening.
- **Current scenario JSON:** complete active document for audit or reuse.

The main read endpoints are `/api/scenarios`, `/api/scenarios/export`, `/api/network`, `/api/definitions`, `/api/validation`, `/api/overview`, `/api/orders`, `/api/order?order_id=...`, `/api/allocation?order_id=...`, `/api/incidents`, `/api/incident?incident_id=...`, `/api/incident/options?incident_id=...`, `/api/actions`, `/api/improvement`, `/api/rules`, and the report endpoints. Mutations are `/api/scenarios/select`, `/api/scenarios/upload`, `/api/decisions`, `/api/action?action_id=...`, `/api/commitments/{id}`, `/api/improvement`, `/api/rules`, and `/api/rules/{id}`. Path-based order/incident aliases also exist. FastAPI exposes its generated OpenAPI schema and documentation at its conventional endpoints.

All report values are produced from the selected active file and current scenario-scoped workflow data. HTML/JSON/CSV are **three views of the model**, not three independent forecast engines. A report’s numbers can change after a decision or scenario switch because the schedule is recalculated.

## 10. Twenty packaged test scenarios

Each file under `test-files/` is a complete valid scenario JSON generated from the deterministic seed and one distinct mutation. The files can be selected in the UI or uploaded directly. `scripts/generate_scenarios.py` recreates them and validates each document.

| File | Scenario | Perturbation and intended question |
| --- | --- | --- |
| `01_steady_network.json` | Steady network | Later due dates, released quality/material, closed exceptions/actions; can the low-risk network clear? |
| `02_late_fabric.json` | Late fabric arrival | PO-2607 material moves eight days; how does readiness change delivery? |
| `03_needles_fail.json` | Recurring needle failure | L7 efficiency falls; another breakdown and higher lost minutes stress the bottleneck. |
| `04_absenteeism.json` | Operator absenteeism | L7 loses operators and historical attendance worsens. |
| `05_quality_release.json` | Quality release hold | PO-2618 release becomes pending with an open seam-strength hold. |
| `06_rush_order.json` | Urgent deadline | PO-2618 deadline advances to 19 October 2026. |
| `07_demand_surge.json` | Demand surge | Focal hoodie quantity increases to 2,300 units. |
| `08_planned_maintenance.json` | Planned maintenance | L7 has three unavailable production dates. |
| `09_factory_shutdown.json` | Factory shutdown | Gazipur closes for four dates. |
| `10_logistics_delay.json` | Transport disruption | Gazipur transit increases from two to six days. |
| `11_compliance_hold.json` | Compliance hold | Chattogram Apparel becomes ineligible for production allocation. |
| `12_defect_spike.json` | Defect spike | Gazipur quality and L7 first-pass output fall to 84%. |
| `13_rework_growth.json` | Rework growth | L7 rework rises to 16%; focal order needs quality release. |
| `14_second_shift.json` | Temporary second shift | L7 gains staffing and higher effective output as a synthetic capacity test. |
| `15_low_cost_trap.json` | Low-cost supplier trap | Gazipur cost falls while reliability and quality worsen. |
| `16_complex_style.json` | Complex operation | Hoodie SMV and hood-attach minutes increase. |
| `17_capacity_crunch.json` | Factory capacity crunch | All Dhaka lines lose efficiency. |
| `18_combined_disruption.json` | Combined material and downtime | Material, L7 sewing efficiency, and Gazipur transit deteriorate together. |
| `19_fast_quality_tradeoff.json` | Fast line, high quality risk | A faster Dhaka line has lower factory quality than Gazipur. |
| `20_no_machine.json` | No feasible machine | Denim jacket requires a laser-bond machine unavailable in the network. |

The “second shift” case is represented by an increase in operator count and line efficiency; it is **not** a general shift calendar or labor-law solver. The “no machine” case provides a clear no-feasible-allocation example. The steady case is a low-risk reference, while the low-cost and fast-quality cases expose QCD tradeoffs.

## 11. Validation and audit history

The repository’s automated suite currently contains **62 passing tests**, run with:

```bash
.venv/bin/python -m unittest discover -s tests -q
```

The latest audit run completed `Ran 62 tests ... OK`. The tests check capacity and feasibility, blocker gates, recovery tradeoffs, benchmark shape, action dependencies, decision and alternative persistence, transaction rollback, split-shipment override preservation, 20 distinct valid scenario files, scenario switching/isolation, JSON upload, report generation, CSV-driven changes in the dashboard, XLSX import, invalid-row errors, unusual IDs, spreadsheet-formula escaping, fractional staffing rejection, invalid incident data, huge-number rejection, tentative reservation rollback, subcontract in-house capacity, mixed-SMV minute reservations across all packaged scenarios, future-history isolation, derived-exception resolution, transferred-factory counts, deadline-day probability, non-downtime PDCA labeling, root-cause evidence requirements, and the cost of an order blocked by another order's recovery. A fresh sweep used a temporary database to exercise the baseline and 20 packaged cases through overview, orders, incidents, recovery options, and JSON/CSV/HTML report endpoints. Desktop browser inspection exercised scenario selection, custom upload, invalid upload, navigation, and report download. The latest audit also checked all six main views, scenario persistence after reload, a live CSV report download, and no browser console errors on the final dashboard. An isolated browser workflow on a disposable database submitted a recovery decision and factory commitment, recorded a comparable PDCA check, proposed a rule, and verified all three persisted after reload.

Important corrections made during the user/developer audit included: making blocked orders release tentative capacity; preventing subcontracting from overbooking in-house lines; honoring scenario `as_of`; treating material shortages, pending releases, and open quality holds as forecast blockers; generating derived risk exceptions for uncovered at-risk orders; aligning dashboard/readiness/report values; preserving existing recovery when a split shipment is later approved; showing rejection reasons for infeasible recovery; using the selected file for dispatch comparison; validating numeric values and references; handling IDs with slashes; and escaping user text in the UI and CSV export.

This evidence is **bounded**. It supports the tested paths and inputs but cannot establish that every possible calculation, action, analysis, reload, or uploaded file behaves correctly. The previous universal yes/no question was therefore correctly answered **No**. Browser reload persistence is supported by the architecture and selected checks, but exhaustive browser interaction testing and property-based fuzzing have not been completed.

## 12. Known limitations, risks, and interpretation rules

1. **Forecast quality:** the greedy scheduler and fixed probability spread are explanatory approximations. They need calibration against actual factory performance before external commitments.
2. **Optimization scope:** the engine does not search a global optimum, split order quantities across lines/factories, model every garment operation as a separate resource, or reserve dedicated rework capacity.
3. **Capacity detail:** cutting/finishing/QC/packing are pooled daily factory quantities; sewing is line/day. Changeover is a fixed 12% first-day deduction. There is no line-level shift roster, legal overtime constraint, detailed machine maintenance duration, WIP transfer, or inspection sampling calendar.
4. **Materials and quality:** unresolved shortages/holds block the forecast. The UI does not provide a transactional material receipt or quality-release action; a corrected scenario file must be uploaded or source data changed. The model does not estimate an unknown replenishment date.
5. **Recovery realism:** subcontract capacity, repair effectiveness, premiums, and lead times are assumptions. A candidate-line prefilter checks the immediate candidate schedule before the transfer lead is applied, so an unusual time-dependent case may need a more complete search. Split shipment is a commercial proxy and does not generate independently dated tranche schedules.
6. **Financial completeness:** baseline manufacturing cost, penalties, margin exposure, and quality loss are modeled proxies. Material price, scrap/rework accounting, chargebacks, cost sharing, cancellation terms, and full contribution-margin accounting are not individually reconciled to ledgers.
7. **Causality:** Pareto and trend observations do not prove a root cause. The seeded verified root cause relies on supplied inspection/service-log evidence. Derived exceptions explicitly have unverified causes.
8. **Improvement claims:** PDCA comparability checks control only for daily volume and style SMV. The application does not automatically schedule 30/60/90-day reviews, enforce sample sizes, or establish counterfactual causality.
9. **Security and governance:** local single-user deployment has no authentication, permission matrix, tenant isolation, encrypted secrets policy, attachment storage, or external notification integration. Typed approver names are not identity verification.
10. **Data quality:** order-table defaults are transparent but may be materially wrong for a real factory. Full scenario validation checks structure and many numeric constraints, not every possible business inconsistency or malicious file pattern.
11. **Runtime and scale:** SQLite and synchronous recomputation suit a local prototype. Performance, concurrent editing, durable migrations, backup/restore, observability, and high-volume production workloads require further engineering.
12. **User interface:** designed and audited for desktop use. Mobile adaptation was explicitly not required. Some management actions use browser prompts rather than dedicated forms.
13. **Current scope:** the user’s initial vision included broader monitoring, dynamic negotiation, calibrated uncertainty, multi-stage optimization, and enterprise workflow. These should not be described as already delivered.

## 13. Future phases and acceptance criteria

### Phase 2: operational depth

- Integrate permission-cleared ERP, MES, quality, material, and logistics feeds; add source lineage and reconciliation checks.
- Add authentication, role enforcement, approval policy, immutable audit events, and evidence attachments.
- Represent operation-level routings, machine work centers, skills by shift, inspection/rework capacity, shutdown and maintenance windows, and regulated overtime limits.
- Add an optimizer capable of partial order allocation and explicit infeasibility certificates, while preserving readable constraint explanations.
- Model material expedition, extra shift, lower-priority rescheduling, customer-approved split shipment, and supplier cost-sharing as fully scheduled alternatives.
- Replace fixed commercial proxies with configurable contracts and accounting inputs; calibrate forecast intervals and on-time probabilities with outcome history.

### Phase 3: measured improvement and deployment

- Pilot with real partner factories, compare forecasts against actual stage completions, and back-test risk thresholds.
- Measure 30/60/90-day recurrence with comparable volume/style and documented confounder review.
- Promote approved planning rules through versioned deployment, rollback, and measured post-change outcomes.
- Add notifications, SLA escalations, management review history, operational monitoring, backups, concurrency tests, and deployment controls.

Before a production release, acceptance should include representative real-data imports; verified stage and financial reconciliations; no unreported capacity or compliance violations; clear behavior when no plan exists; calibrated probability and cost error; tested role approvals; audit integrity; and user acceptance across production, quality, material, logistics, and finance functions.

## 14. How to run and reproduce

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/`. The local SQLite file is created at `data/platform.db`. Deleting that file resets the local scenario selection and recorded workflow data, so export any needed scenario/report first. Regenerate packaged scenarios with `python scripts/generate_scenarios.py`. Run the tests with `.venv/bin/python -m unittest discover -s tests -q`. The browser’s **CSV template** and **Current scenario JSON** downloads provide starting formats for new files.

## 15. Final status

Phase 1 is a working, test-backed local decision-support prototype with scenario-aware uploads, dashboard views, explainable schedules, recovery comparisons, workflow records, and report downloads. The 20 packaged scenarios and arbitrary compatible order-table imports make the behavior demonstrable beyond one hard-coded demo. Its outputs remain modeled forecasts based on synthetic data or user-supplied inputs and disclosed defaults. The remaining roadmap is substantial; the platform should be treated as a transparent prototype until operational data, model calibration, security, and production acceptance work are completed.

## 16. Technical and development appendix

### 16.1 Runtime and dependency choices

The backend runs on Python with FastAPI and Pydantic request models. Uvicorn serves both the API and three static web assets. SQLite is accessed with the Python standard library `sqlite3`; no ORM or external database service is required. `openpyxl` reads XLSX uploads in read-only, values-only mode. The frontend is plain HTML, CSS, and JavaScript with no JavaScript package manager, transpiler, or bundler. The only declared third-party dependencies are `fastapi>=0.115,<1`, `uvicorn>=0.30,<1`, and `openpyxl>=3.1,<4`. The app object reports version `0.1.0`.

The server command is `uvicorn app.main:app --reload` during development. The `--reload` switch watches code changes and is a development convenience, not a production server configuration. The app is served from `http://127.0.0.1:8000/` under the default Uvicorn settings. There is no container definition, production process manager, CI configuration, migration package, or deployment manifest in this repository.

### 16.2 Request and data lifecycle

An upload reaches `POST /api/scenarios/upload?filename=...` as a raw request body. The filename extension selects CSV, XLSX, or JSON parsing. Importers normalize row headings and types, construct a full document when the source is an order table, and pass it to `validate_document`. Only a validated document is stored. `save_upload` assigns a generated `upload_<12 hex characters>` ID, saves both metadata and payload in SQLite, and makes it active. A packaged scenario is instead read from `test-files/` by its metadata ID. The baseline is reconstructed from seeded SQLite records.

Each computed endpoint calls `scenario()` in `app/main.py`. That function loads the active document, records source-data counts, calculates the initial schedule, creates in-memory derived incidents and actions for uncovered late/blocked orders, applies stored action updates, reads decisions in ID order, builds effective schedule overrides, and returns the assembled scenario. The endpoint then invokes `schedule_all` or another engine function. Derived incidents are generated on each read rather than inserted into the source scenario payload; their action updates can still persist using stable derived IDs. This distinction matters when comparing the exported source document with an API response.

`schedule_all` sorts orders, creates fresh line/day and factory/day reservation maps, checks each assigned line, and calls `_schedule_one`. The latter uses tentative maps and commits them only after every stage succeeds. To simulate an allocation or recovery option, the engine calls `schedule_all` with an override map while preserving the other active overrides. The whole order book is then recomputed, allowing the option to reveal displaced orders. This approach favors explainability over computation efficiency: a page that requests overview, validation, incidents, and reports may recalculate the same order book several times.

The browser initializes by fetching `/api/scenarios` and `/api/overview`. `web/app.js` keeps current page and filters in a global `state` object; `go(page)` sets the selected navigation button, shows a loading state, awaits the page renderer, and displays an error card on failure. Scenario selection and upload clear stale order/incident/option filters before returning to the control tower. This client state is ephemeral; server-side scenario selection and records survive a page reload.

### 16.3 SQLite schema and transaction behavior

`store.initialize()` creates tables on demand. The key tables are:

| Table | Key fields and purpose |
| --- | --- |
| `seed_records` | `(kind, record_id)` primary key and JSON payload for the baseline |
| `scenario_uploads` | Uploaded scenario ID, JSON metadata, JSON payload, creation timestamp |
| `app_state` | Key/value entry `active_scenario` |
| `decisions` | Scenario ID, incident, selected option, rationale, approver, timestamp, serialized alternatives |
| `commitments` | Scenario ID, incident, decision ID, owner, promise, due date, status, actual date |
| `scenario_action_updates` | `(scenario_id, action_id)` key, status, evidence, timestamp |
| `pdca` | Scenario/incident, stage, baseline and observation measures, narrative, timestamp |
| `rules` | Scenario/incident, rule key, old/new values, reason, pending/approved/rejected status, approver, timestamp |
| `action_updates` | Legacy baseline action-update table; copied into scenario-scoped updates during initialization |

The `connect()` context manager commits on success, rolls back on an exception, and closes the connection. Inserts and updates use SQL parameters for record values. Existing installations receive a lightweight `scenario_id` column addition for four workflow tables if missing. This is an inline compatibility migration, not a versioned migration system. `record_decision()` now writes the decision and its commitment in one SQLite transaction. SQLite has no configured backup schedule or concurrency policy in this prototype.

### 16.4 API contract and error handling

The API returns JSON for operational reads and writes, except file/download routes. FastAPI/Pydantic validates typed mutation bodies. Domain checks add HTTP 400 for invalid options or states, HTTP 404 for unknown referenced records, and HTTP 413 for an oversize upload. For example, a closed incident cannot receive a recovery decision; an action with an unfinished dependency cannot be completed; a fulfilled commitment needs an actual date; a `check` PDCA record needs outcome/volume/complexity; and a planning-rule proposal must differ from its old value.

Order and incident routes have both path-parameter and query-parameter forms. The UI uses the query forms and `encodeURIComponent`, because an external order ID may contain `/`. The report endpoints set `Content-Disposition: attachment` and names based on the active scenario. Uploaded filenames are not used directly in SQL. Validation messages are shown in the UI toast and on API failure responses. There is no explicit API authentication, authorization, rate limiting, background job queue, or request tracing.

### 16.5 Frontend implementation and interaction details

The interface is a single-page application assembled with template strings and `innerHTML`. Text derived from scenario files is passed through `esc()` for HTML output. Identifiers inserted into inline event-handler argument positions are encoded with `jsarg()`, and query strings use `encodeURIComponent`. The CSV exporter prefixes text whose trimmed beginning is `=`, `+`, `-`, or `@` to reduce spreadsheet-formula execution risk. These are targeted protections; a broader security review and a frontend architecture without inline handlers would be appropriate before production use.

The upload input accepts `.json`, `.csv`, and `.xlsx`, enforces the 3 MB limit in the client as well as the server, and clears its value afterward so the same file can be uploaded again. The report selector triggers a normal browser attachment download. Search and status filters operate on the fetched order array in browser memory; factory filtering on the control tower is server-side. The output trend is hand-built SVG, while line loads and risk timelines use HTML/CSS components. There is no Plotly, React, Streamlit, or client build pipeline in the implemented project.

The interface uses browser `prompt` and `confirm` for action status, commitment status, and rule approval. That is serviceable for a prototype but offers limited input guidance and no rich evidence-attachment workflow. Forms for recovery decisions and PDCA observations are rendered directly in the page. On a reload, the application returns to the control tower, even though the active scenario and saved workflow records persist.

### 16.6 Import and schema edge cases

The importer decodes CSV as UTF-8 with optional BOM, reads XLSX values through `openpyxl`, and accepts two lightweight JSON order-row shapes in addition to the full schema. It skips wholly empty rows, rejects a row lacking one of the four required fields, rejects nonfinite or fractional values where integers are required, and rejects conflicting declarations such as one line belonging to two factories or one style ID having different category/machine/SMV. A provided `as_of` or `synthetic` value must be consistent across rows. The full-schema validator checks collection membership and references, but it does not validate every business rule a live ERP might need, such as overlapping duplicate production records, cyclic action dependencies, or contractual currency conversions.

Factory and line attributes on repeated order rows are taken from the **first occurrence** of the respective factory or line. Later rows extend inferred category skills and machines but do not reconcile conflicting costs, capacities, staffing, or efficiency. This is a known ingestion limitation and should be resolved with explicit network sheets or consistency validation before using diverse operational extracts.

### 16.7 Test organization and reproducibility

`tests/test_platform.py` covers engine and workflow behaviors; `tests/test_external_imports.py` covers file-driven results, import validation, and selected scheduling regressions; `tests/test_scenario_files.py` validates all 20 files and distinct scenario mutations. Tests use `unittest` and temporarily patch `store.DB_PATH` to an isolated SQLite database for persistence checks. The synthetic seed uses `random.Random(57)`, making its generated orders and historical records deterministic. The scenario generator validates every output before writing it.

The command to rerun all repository tests is:

```bash
.venv/bin/python -m unittest discover -s tests -q
```

For a direct API smoke test with the server running, use `curl http://127.0.0.1:8000/api/overview` and `curl http://127.0.0.1:8000/api/scenarios`. A packaged file can be uploaded with `curl --data-binary @test-files/20_no_machine.json 'http://127.0.0.1:8000/api/scenarios/upload?filename=20_no_machine.json'`, which **changes the active local scenario**. A developer should use a disposable database or restore the desired scenario afterward. The suite tests representative outcomes and regression risks; it is not exhaustive property testing across arbitrary combinations.

### 16.8 Development sequence and decisions

The build evolved from a connected synthetic baseline to a file-driven platform. The initial implementation provided the network, scheduler, control tower, disruption analysis, recovery and workflow APIs, and desktop UI. A later phase added 20 self-contained scenarios, scenario selection, upload, and report downloads. User feedback identified that changing files initially left too much of the dashboard unchanged, so the import path was extended to construct a scenario from arbitrary order rows and to drive every major computed endpoint from the active file. Missing history was explicitly represented as unavailable. Subsequent user and developer audits corrected blocker handling, derived exceptions, scenario isolation, schedule reservations, recovery override behavior, validation, unusual IDs, and report consistency. The report reflects the current code, not a claim that every theoretical case has been solved.

### 16.9 Developer priorities for the next iteration

1. Add model-level invariants and property-based tests for reservations, monotonic capacity effects, date boundaries, report/API agreement, and scenario isolation under many generated inputs.
2. Introduce versioned database migrations and test transactional rollback when a commitment insert fails.
3. Refactor scheduling into explicit stage/operation objects and add a constrained optimization option with readable infeasibility explanations.
4. Separate source events, inferred signals, and approved decisions in typed schemas, with provenance and immutable audit events.
5. Add robust import reconciliation for repeated factory/line rows, multi-sheet network templates, currency and unit declarations, and externally supplied holidays.
6. Replace `prompt`/`confirm` flows with accessible forms and validate all state changes on the server under authenticated roles.
7. Cache per-request scenario calculations or persist versioned forecast runs so multi-panel views and reports share a consistent calculation snapshot.
8. Instrument forecast accuracy, computation time, upload failures, and data-quality errors before scaling beyond a local prototype.

## 17. Complete implementation inventory and traceability

### 17.1 Full data-field reference

The following is the working model’s field inventory. A full scenario must include every collection, even when a historical collection is empty. `id` values identify rows inside their own collection; cross-reference rules are described in Section 5. A value being present in a scenario does not mean every algorithm uses it.

| Collection | Fields used or preserved | Main consumers |
| --- | --- | --- |
| `factories` | `id`, `name`, `region`, `daily_cut`, `daily_finish`, `daily_qc`, `daily_pack`, `cost`, `quality`, `reliability`, `logistics_days`, `compliance`, `capabilities`, optional `shutdown_dates` | Allocation, pooled stages, transit, QCD, recovery costs |
| `lines` | `id`, `factory_id`, `name`, `operators`, `efficiency`, `skills`, `machines`, `maintenance` | Allocation, line capacity, downtime and labor join |
| `styles` | `id`, `name`, `category`, `smv`, `bottleneck`, `machine`, `operations` | Compatibility, capacity, stage display, cause context |
| `orders` | `id`, `customer`, `style_id`, `factory_id`, `line_id`, `quantity`, `due_date`, `material_date`, `target_cost`, `priority`, `margin_per_unit`, `min_lot`, `quality_release`, `status` | Scheduling, cost, order book, risk |
| `materials` | `order_id`, `fabric_ready`, `trims_ready`, `shortage_units` | Release date, readiness, blocking gates |
| `production` | `date`, `line_id`, `target`, `actual`, `first_pass`, `rework` | Historical output trend, first-pass yield, adherence, PDCA baseline |
| `downtime` | `id`, `date`, `line_id`, `machine`, `cause`, `minutes`, `shift` | Capacity-loss factor, Pareto, incident evidence |
| `quality_holds` | `id`, `order_id`, `date`, `hours`, `cause`, `status` | Quality gate, readiness count, order detail |
| `labor` | `date`, `line_id`, `scheduled`, `present` | Attendance-adjusted capacity and absenteeism |
| `incidents` | `id`, `order_id`, `factory_id`, `line_id`, `type`, `title`, `detected_at`, `severity`, `status`, `lost_minutes`, `immediate_cause`, `verified_root_cause`, `evidence`, `verification`, `owner` | Disruption view, recovery, PDCA, war room |
| `actions` | `id`, `incident_id`, `title`, `owner`, `accountable`, `consulted`, `informed`, `due_date`, `status`, `dependency`, `evidence` | RACI board and escalation flags |

`style.operations` retains a named sequence of `(operation, minutes)` pairs. Phase 1 does **not** independently reserve capacity for each listed operation; its total `smv` drives line output. `order.status` must be `active`; full-scenario validation rejects completed or cancelled orders so they cannot silently enter the active planning forecast. Status-aware historical-order processing is future work.

The `meta` object also carries optional `source_format` and `assumptions` for imported order tables. `synthetic` is the source label, not a validation guarantee. All scenario dates use `YYYY-MM-DD`; database timestamps from `now()` are local server-time ISO strings without an explicit timezone offset. This is sufficient for a local prototype but not a cross-region audit trail.

### 17.2 Endpoint-by-endpoint inventory

| Method and path | Inputs | Result or mutation |
| --- | --- | --- |
| `GET /` | None | Dashboard HTML shell |
| `GET /app.css`, `GET /app.js` | None | Styles and browser logic |
| `GET /sample-orders.csv` | None | Downloadable order-table example |
| `GET /api/scenarios` | None | Active scenario ID and catalog |
| `POST /api/scenarios/select` | JSON `id` | Activates a catalog scenario |
| `POST /api/scenarios/upload` | Raw file body; query `filename` | Parses, validates, stores, and activates upload |
| `GET /api/scenarios/export` | None | Complete active scenario JSON |
| `GET /api/definitions` | None | KPI and assumption definitions |
| `GET /api/network` | None | Active factories, lines, styles, materials |
| `GET /api/validation` | None | Five dispatch-rule benchmarks |
| `GET /api/overview` | Optional `factory_id` | Control-tower data and KPIs |
| `GET /api/orders` | None | Source order data plus plan/readiness/gate fields |
| `GET /api/orders/{order_id}` or `/api/order?order_id=` | Order ID | One order, style, plan, material, holds, incidents |
| `GET /api/allocate/{order_id}` or `/api/allocation?order_id=` | Order ID | Feasible and rejected candidate lines |
| `GET /api/incidents` | None | Source/derived incidents with impact estimates |
| `GET /api/incidents/{incident_id}` or `/api/incident?incident_id=` | Incident ID | Evidence, Pareto, fishbone, 5 Whys, actions, decisions, commitments |
| `GET /api/incidents/{incident_id}/options` or `/api/incident/options?incident_id=` | Incident ID | Recovery comparison, including rejected alternatives |
| `POST /api/decisions` | Incident, option, rationale, approver, owner, commitment, due date | Saves decision and factory promise |
| `GET /api/actions` | None | Actions with overdue and dependency-blocked flags |
| `PATCH /api/actions/{action_id}` or `/api/action?action_id=` | Status and evidence | Scenario-scoped action update |
| `PATCH /api/commitments/{commitment_id}` | Status and optional actual date | Promise fulfillment record |
| `GET /api/improvement` | Optional `incident_id` | Baseline, target, observations, comparability assessment |
| `POST /api/improvement` | Incident, PDCA stage, measurements, observation | Adds PDCA record |
| `GET /api/rules` | None | Scenario-scoped rule proposals |
| `POST /api/rules` | Incident, key, old/new value, reason | Pending rule proposal |
| `PATCH /api/rules/{rule_id}` | Approver and approve boolean | Records approval or rejection |
| `GET /api/reports/management.json` | None | Complete machine-readable management report |
| `GET /api/reports/orders.csv` | None | Current order forecast table |
| `GET /api/reports/management.html` | None | Printable management report |

The path aliases and query aliases call the same Python functions; they are not distinct business calculations. Generated FastAPI documentation may be inspected locally at `/docs` and `/openapi.json`. Because no authentication exists, any process able to reach the local server can use mutation endpoints; do not expose this prototype to an untrusted network.

### 17.3 Requirement-by-requirement disposition

This table maps the original project brief to the current repository. “Partial” means a meaningful path exists but does not satisfy every sub-requirement.

| Original requirement | Status | Exact Phase 1 disposition |
| --- | --- | --- |
| Multi-factory network | Partial | Three factories, eight lines, ten styles, orders, material and historical records; no detailed work centers or live sourcing feeds |
| Multi-factory order allocation | Partial | Compatibility and ranking over whole-order line assignments; no quantity split or global optimum |
| Capacity-constrained scheduler | Partial | Daily finite capacity across five stages and transit; no per-operation resource schedule or rework loop |
| Control tower | Implemented for prototype | Scenario-aware interactive desktop views and drill-downs; no enterprise push monitoring |
| Disruption detection/impact | Partial | Source incidents plus derived late/blocked exceptions and illustrative impact; no broad live event detector or calibrated ranges |
| Root-cause/prevention engine | Partial | Pareto, fishbone prompts, concise 5 Whys, evidence/status separation; no automated hypothesis ranking or historical incident similarity |
| Dynamic recovery engine | Partial | Seven modeled alternatives with feasibility, effects and decisions; several requested interventions are absent |
| Financial/negotiation simulator | Partial | Proxy total-impact components and recorded commitments; no complete contract, chargeback, or cost-sharing engine |
| War room/leadership | Partial | RACI fields, dependencies, due dates, decision and commitment history; no identity-backed approvals or notifications |
| PDCA loop | Partial | Plan/do/check/act observations, baseline and comparability, proposal review; no sustained 30/60/90 verification automation |
| Learning/adaptability | Partial | Outcomes can be recorded and rule changes proposed/reviewed; approved rules do not modify the engine automatically |
| QCD KPI framework | Partial | Forecast OTIF, historical yield/adherence, cost proxies, exception and action counts; many requested detailed KPIs are not calculated |
| Required synthetic dataset | Implemented for demonstration | Three factories, eight lines, ten styles, thirty orders and histories; all labeled simulated |
| Validation against simple baselines | Partial | Five dispatch rules and 62 automated tests; no manual recovery comparator or calibrated business validation |
| Upload arbitrary similar files | Partial | Compatible order-table CSV/XLSX/JSON and full schema JSON; heterogeneous ERP exports need mapping/validation extensions |
| Download report | Implemented for prototype | HTML, JSON, CSV, and source scenario JSON downloads |

### 17.4 Requested KPI catalog versus actual calculations

The original brief’s KPI list is wider than the current implementation. The following prevents a reader from mistaking a visible proxy for a fully implemented metric.

| KPI area | Currently calculated or shown | Not yet calculated as a first-class metric |
| --- | --- | --- |
| Quality | Historical first-pass yield; line rework units; quality-pending orders; open holds; factory quality input and modeled option quality risk | Defect rate by defect type, rejected-batch %, repeat-defect rate, quality-hold hours aggregated as a KPI, inspection yield by order |
| Cost | Factory cost per acceptable historical unit, option recovery/penalty/margin/quality/other-order proxy, target cost, benchmark estimated cost | Actual manufacturing cost per acceptable unit with ledger reconciliation, scrap, full cost variance, chargeback/cost sharing, cancellation exposure |
| Delivery | Forecast OTIF, late/blocked orders, late units, delay days, expected shipment, historical output/target adherence | Actual OTIF from shipment confirmations, milestone adherence from actual stage events, measured recovery time, plan-stability time series |
| Leadership/improvement | Open/overdue actions, blocked dependency, commitment statuses, PDCA event-rate comparison | Escalation response-time distribution, commitment reliability trend, action completion rate over period, verified recurrence after 30/60/90 days, decision-to-action lead time |

### 17.5 Development quality gates and unresolved engineering work

At present there is one automated `unittest` command and manual desktop browser inspection; there is no CI pipeline enforcing it on every change. No benchmark threshold is enforced for compute time. The SQLite database file is mutable local state and should not be treated as a reproducible fixture; the seed generator and scenario JSON files provide reproducibility. The current process lacks structured logging, centralized error reporting, request correlation IDs, and a health/readiness endpoint.

For future changes, a developer should run the 62-test suite, validate the 20 scenario documents, exercise one CSV and one XLSX import, compare dashboard/JSON/CSV values after scenario switching, and inspect the affected desktop flow in the browser. An API change should update both the endpoint reference here and the generated/OpenAPI contract. Any formula change should carry a worked example or invariant test and should version its assumptions so older recorded decisions remain interpretable. A production release additionally needs security, data provenance, calibration, and operational acceptance described above.

## 18. Version 0.2 — professional workspace transformation

### 18.1 Release purpose and status

Version 0.2 changes the product structure, analytics, operating workflows, and development controls. It is not solely a visual update. The work retains the original constraint-aware scheduler while adding a reconciled analytics layer, an operating-event ledger, controlled source-data updates, uncertainty experiments, measured persistence checkpoints, and nine desktop workspaces.

The detailed requirement reconciliation is maintained in [docs/requirement-coverage.md](docs/requirement-coverage.md). That document explicitly distinguishes working capabilities from partial coverage and outstanding production gates. The application remains a local single-user planning system; it must not be represented as an authenticated enterprise production service.

Sections 1–17 preserve the previous implementation record. Where they describe absent capabilities such as event auditing, Monte Carlo, measured persistence checkpoints, CI, or health checks, this version 0.2 chapter supersedes them. The original business requirements and limitations not addressed here remain relevant.

### 18.2 Information architecture

The interface now separates three management activities:

1. **Monitor and plan:** Control tower, Factory intelligence, Capacity & schedule, Order portfolio.
2. **Investigate and respond:** Disruption intelligence, Recovery studio, Execution workspace.
3. **Improve and govern:** Continuous improvement, Data & decision ledger.

Every workspace has a question it answers. The control tower identifies exceptions; factory intelligence compares performance; scheduling explains resource reservations; recovery compares operating and commercial trade-offs; execution assigns accountability; improvement evaluates evidence; governance exposes provenance, assumptions and changes. The global dataset selector, import control, export menu, planning date and source label remain consistent across pages.

### 18.3 Design system and visual behavior

The desktop design uses a navy navigation rail, slate typography, white analytical surfaces, restrained teal for favorable performance, amber for caution, and muted red for delivery/quality exposure. System fonts replace externally loaded fonts. Page headings, section titles, KPI labels, financial values, captions, tables and form fields follow a consistent hierarchy. Number formatting uses USD, explicit percentages and grouped units.

The Operations Studio supports desktop, tablet, and mobile layouts; validation included 1440 × 960 desktop, 768 × 1024 tablet, and 390 × 844 mobile viewports. Dense schedules, tables, and charts remain in bounded scroll regions. Keyboard focus outlines, accessible dialog titles, text status labels, chart titles, SVG labels, tooltips, drawer focus management, skip-link focus, and modal controls support usability. This is not a claim of completed WCAG conformance testing.

Browser prompt/confirm workflows for actions, commitments and rule review have been replaced by structured dialogs. A rejected management rule is an explicit choice, not the side effect of cancelling a confirmation. Forms retain input when server validation fails and show the error inside the dialog. Mutation controls disable during submission.

### 18.4 Purpose and provenance of each visualization

| Visual | Analytical purpose | Data and interpretation |
| --- | --- | --- |
| Output/target lines | Identify production shortfalls through time | Supplied historical production, through the planning date; zero-based units |
| Factory exposure bars | Prioritize partner-level delivery decisions | Modeled order exposure summed to the planned factory |
| Delivery status strip | Show portfolio composition | On-time, late and blocked order counts; no probability mixing |
| Material/quality gate bars | Identify prerequisites preventing production | Material and quality counts may overlap |
| Quality/adherence lines | Compare output quality and plan adherence | Observed ratios, not factory input ratings |
| Downtime contribution and cumulative table | Prioritize cause investigation | Cause-coded downtime minutes; association is not causal confirmation |
| Capacity heatmap | Locate competing line/day reservations | In-house SMV minutes plus changeover divided by available minutes |
| Production Gantt | Explain stage timing and customer deadlines | Forecast stage spans, including queues and non-working time |
| Planned WIP lines | Reveal stage inventory and shipment waiting | Cumulative scheduled cutting less packing; packed less shipped |
| Recovery cost composition | Explain what drives each alternative’s total | Extra spend, penalty, margin, quality and displacement components |
| Cost/delivery bubble chart | Compare competing objectives | Expected total impact, on-time probability and quality-risk bubble size |
| Monte Carlo quantiles | Test shipment variability and cost tails | 2,000 repeatable synthetic shipment-date shocks per feasible alternative |
| RACI matrix | Make responsibility and accountability visible | Action owners and accountable roles, alongside due dates/dependencies |
| PDCA recurrence lines | Compare measured checks with baseline/target | Recorded observations and context; no automatic causal attribution |
| Policy benchmark bars | Compare simple scheduling approaches | Same source scenario and explicit heuristic assumptions |

No chart substitutes synthetic history for an upload that contains only orders. Empty states explain the missing evidence. Factory charts and order drilldowns use the planned assignment, including recorded allocation changes.

### 18.5 Reservation-level schedule transparency

The scheduling engine now exposes two complementary reservation records for every feasible order:

- `daily`: sewing date, units, offered unit capacity, available minutes, reserved in-house minutes, and outsourced units.
- `stages`: stage name, production date, and reserved units for cutting, finishing, inspection and packing.

Factory-stage records are obtained by subtracting the pre-order reservation map from the tentative post-order map before committing it. Thus, each order’s stage record contains its own units instead of the factory’s accumulated workload. Infeasible orders continue to release all tentative reservations.

The analytics heatmap aggregates each line/date once. Its numerator includes first-day changeover and in-house sewing minutes. Its denominator is that day’s offered capacity, including a selected recovery uplift when applicable. Subcontracted units are exposed separately and are not counted as internal minute consumption. Zero-capacity dates appear unavailable instead of zero utilization.

The benchmark utilization calculation was also changed to unique line/day minutes. It no longer repeatedly adds an entire day’s capacity for every order sharing that day.

### 18.6 Planned work-in-progress accounting

For each date in a 42-day analytical horizon, PlantCore aggregates cumulative scheduled quantities:

- Cutting completed.
- Sewing completed.
- Finishing completed.
- Inspection completed.
- Packing completed.
- Full-order shipment completed according to the modeled shipment date.

Derived balances are:

```text
Cut queue            = cumulative cutting − cumulative sewing
Sew queue            = cumulative sewing − cumulative finishing
Finish queue         = cumulative finishing − cumulative inspection
Inspection queue     = cumulative inspection − cumulative packing
Ready to ship        = cumulative packing − cumulative shipped
Planned production WIP = cumulative cutting − cumulative packing
```

The schedule’s stage precedence keeps these balances nonnegative. The chart explicitly identifies them as planned balances. They do not establish actual factory WIP or actual stage completion.

### 18.7 Portfolio exposure and factory QCD

For a feasible order, delivery slack is its customer deadline minus its modeled shipment date, in calendar days. The illustrative full-order on-time probability is:

```text
P(on time) = normal_CDF((slack_days + 0.5) / 1.8)
Expected exposure = quantity × (1.15 + 0.18 × margin_per_unit) × (1 − P(on time))
```

Blocked orders have no supported shipment probability and use the full penalty/margin exposure assumption for prioritization. They are not labeled as having a measured 0% shipment likelihood. Network exposure is the sum of order exposure; factory exposure is the same sum grouped by planned factory. This also aligns incident commercial exposure with the portfolio calculation.

Modeled manufacturing cost and target variance are available per order:

```text
Manufacturing proxy = quantity × (factory cost + style SMV × 0.15)
Target variance = manufacturing proxy − supplied target cost
```

Blocked orders are excluded from planned manufacturing totals. These values are not accounting records. The factory analysis additionally calculates observed first-pass yield, rework/output, actual/target, aggregate present/scheduled attendance, recorded downtime minutes, active units, late/blocked counts, and forecast OTIF. All historical data is restricted to dates at or before the scenario planning date.

### 18.8 Operational release and allocation controls

An order’s detail page now supports a release-change form covering fabric date, trim date, outstanding shortage and quality-release status. The user records an owner and supporting evidence. Quality release explicitly closes the order’s open inspection holds. The order’s material-release prerequisite follows the updated fabric/trim dates.

After saving, the entire network is rescheduled. This matters because clearing one order can consume capacity previously available to another. The user sees the revised forecast, assignment, gates and connected incident records.

A separate allocation approval form lists feasible candidate lines, forecast shipment and the number of other orders delayed. Approval retains every candidate, selected line, approver name and rationale, then reruns the complete schedule. Incompatible or blocked allocations are rejected on the server as well as excluded from the selectable list.

Chronology is respected between allocation approvals and subsequent recovery decisions. Recovery alternatives retain their exact operating override so that replay uses the approved line, lead time, overtime, repair, subcontract or freight configuration. Source-level changes do not erase the original derived investigation history.

### 18.9 Operating-event ledger

A new SQLite table, `workflow_events`, stores:

| Field | Purpose |
| --- | --- |
| `id` | Monotonic event identifier |
| `scenario_id` | Isolates the event to the selected scenario |
| `kind` | Release, allocation, hypothesis, action, update, negotiation, pilot, checkpoint or review |
| `entity_id` | Related order, incident, action or rule |
| `actor` | Recorded responsible person or role |
| `evidence` | Supporting explanation |
| `payload` | Structured JSON with the change, alternatives or measured result |
| `created_at` | Timestamp with microsecond precision for new records |

Release and allocation changes replay into the working model. Custom actions join the response plan. Verified investigation records provide the retained verification statement. Event rows are append-only through the application API. This is an application history, not tamper-evident storage: someone with direct SQLite access can alter the database, and actor names are not authenticated.

Recovery decisions and factory commitments remain in their dedicated tables and are inserted atomically. The detailed JSON evidence pack includes those records alongside workflow events, rules, PDCA observations, analytics and definitions.

### 18.10 Structured investigations

The investigation form records a cause statement, one of six fishbone dimensions, an evidence classification, up to five Why steps, verification text, supporting evidence and an owner.

Supported classifications are unverified hypothesis, contributing factor, rejected hypothesis, and verified root cause. A verified cause requires a substantive verification method/result. The system does not elevate a Pareto association to a verified cause automatically. The fishbone map and chronological evidence cards expose the classification directly.

Evidence is currently text. Uploading a spreadsheet is data import, not an evidence-attachment system. Binary files, immutable evidence URLs, cause-taxonomy versioning and formal causal inference remain outstanding.

### 18.11 Recovery, negotiation and uncertainty

Recovery alternatives expose both operational feasibility and expected financial consequences. The interface now provides a component comparison and a cost/delivery/quality relationship chart before the detailed option cards.

Supplier negotiation is a separately recorded proposal:

```text
Supplier contribution = incremental operating spend × supplier share
Buyer expected impact = gross modeled impact − supplier contribution + buyer concession
```

The gross cost remains visible. A proposal does not silently apply an operating plan or claim supplier acceptance. The operating plan still requires the existing approval and written factory commitment workflow.

The former unsupported partial-tranche probability uplift was removed. Negotiated partial-delivery terms now explicitly disclose a commercial sensitivity assumption: a 55% reduction of modeled penalty and margin exposure, with the full-order schedule unchanged. A real partial shipment requires a tranche-level schedule and customer acceptance; neither is implied by this commercial case.

The simulation uses 2,000 common normal shipment-date shocks with seed 57. The default standard deviation is 1.8 days and can be varied from 0.1 to 10 days. Common draws make comparisons repeatable. Date shocks are rounded to calendar days; simulated arrival cannot precede the planning date. Each option returns the fraction of on-time trials, shipment P10/P50/P90, mean modeled cost and cost P10/P90. P10/P90 enclose the central 80% of the modeled outcomes. Quality and displacement costs remain fixed expectations. This is a sensitivity experiment rather than a validated prediction interval.

### 18.12 Response execution

Users can create an action with a responsible owner, exactly one accountable field, consulted and informed participants, due date, prerequisite, and evidence. Prerequisites must belong to the same incident. Completion requires the prerequisite to be complete. A completed prerequisite cannot be reopened while a completed dependent action still relies on it; the dependent action must be reopened first.

The workspace shows overdue and dependency-blocked actions, recorded decisions, factory commitments and a responsibility matrix. Commitment updates record open/fulfilled/missed status and require an actual fulfillment date for fulfilled commitments. These are recorded managerial controls; external escalations and notifications are not sent.

### 18.13 Measured PDCA persistence

Version 0.2 adds an evidence-based pilot record beyond the original freeform PDCA journal. Starting a recurrence pilot requires an incident with a verified cause and a nonzero historical recurring-downtime baseline. The pilot retains intervention start, baseline, owner, evidence and target reduction.

A checkpoint records a real or explicitly synthetic observation period, number of production days, matching line downtime events, daily volume, average style SMV, first-pass yield, owner and evidence. Production days cannot exceed calendar days in the observation interval. Non-synthetic observations cannot end in the future.

Assessment rules are explicit:

1. Event rate = events / observed production days.
2. Volume must be within 20% of baseline.
3. Style SMV must be within 10% of baseline.
4. First-pass yield may not deteriorate by more than one percentage point from baseline.
5. Event rate must meet the retained pilot target.

Incomparable production produces an inconclusive assessment. A recurrence or quality failure requests reopening the intervention. Successful evidence is assigned to windows 30–59, 60–89 and 90–119 days after intervention start. All three windows must have successful observations before the system displays sustained observation. The latest check in a window can invalidate an earlier success.

This process evaluates reported observations; it does not automatically prove the intervention caused the result. Alternative causes, valid cause matching, actual output evidence and factory acceptance still require review.

### 18.14 Imports, missing data and validation improvements

Repeated factory and line attributes are now checked for conflict. Two rows declaring different costs, quality/reliability, compliance, stage capacity, transit time, operator counts or line efficiency for the same entity produce an explicit validation error rather than accepting whichever row appeared first.

Every full-schema collection entry must be an object. Malformed history rows therefore yield a controlled import error rather than an internal server failure. Existing finite-number, reference, date, quantity, action-cycle and cause-evidence validation remains in force.

An order-table import still creates only the network needed by those rows. It does not borrow the packaged factory history. All nine workspaces use the selected file’s resulting model.

### 18.15 Reload, navigation and failure behavior

The UI stores the current workspace, selected incident/order and order filters in session storage, associated with the selected scenario. A reload restores this context when it belongs to the active dataset. Selecting or uploading a new scenario resets incompatible order/line/gate filters.

Each workspace navigation cancels outstanding view requests using `AbortController` and a navigation generation counter. A slow response from an abandoned page cannot replace the newer workspace. API failures become visible retry states. Form failures remain visible in the active dialog rather than silently closing it.

The application still has one server-global active scenario. The controls are appropriate to a single-user local workspace; they do not implement concurrent multi-user transaction isolation or merge resolution.

### 18.16 Exports and report scope

The printable management HTML now adds factory QCD/exposure, response actions and accountable owners, commitments, policy benchmarks, operating evidence, PDCA observations, rule reviews and calculation notes to the original order/incident/decision summary.

The full JSON includes the detailed analytics model and workflow events. The CSV contains order forecasts and uses formula-injection-safe text fields. The working scenario JSON includes source-level release changes and planned line assignments; it is not a database backup and does not reproduce every recovery override or approval history. Download the evidence pack and back up SQLite when complete state retention is required.

### 18.17 Engineering and release support

New components:

- `app/analytics.py`: reconciled portfolio, capacity, history, factory performance, cause contribution, WIP and Monte Carlo.
- `app/workflows.py`: operating-event storage and replay.
- `web/enterprise.js`: chart components, enhanced workspaces, structured dialogs and navigation control.
- `tests/test_enterprise.py`: reservation invariants, simulations, imports and controlled workflows.
- `scripts/validate_scenarios.py`: validates and reconciles all 20 packaged scenarios.
- `.github/workflows/quality.yml`: automated Python tests, syntax checks and scenario sweep.
- `Dockerfile`, `compose.yaml`, `.dockerignore`: non-root container configuration with persistent storage and a local-only published port.

`PLANTCORE_DB` configures the database path. `/api/health` checks SQLite connectivity and returns the version, storage type and local single-user mode. Application version is 0.2.0. The project uses no chart CDN dependency; the charts are SVG/HTML computed from API responses.

A Docker runtime was unavailable in the development environment, so the supplied container configuration has not been built or smoke-tested there. CI is a supplied workflow until the hosted run confirms its result.

### 18.18 Added API surface

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/analytics` | Reconciled portfolio, capacity, stage load, WIP, factory QCD and methodology |
| GET | `/api/audit` | Operating events, recovery decisions and rule history |
| POST | `/api/releases` | Record evidence-backed material and quality gate changes |
| POST | `/api/allocations` | Approve a feasible whole-order line assignment |
| POST | `/api/hypotheses` | Record cause classification, Whys, evidence and verification |
| POST | `/api/actions` | Create an accountable action with validated dependency |
| POST | `/api/negotiations` | Record supplier-sharing and buyer-concession proposal |
| GET | `/api/simulation` | Repeatable recovery uncertainty experiment |
| POST | `/api/pilots` | Start a verified-cause recurrence pilot |
| GET/POST | `/api/checkpoints` | Retrieve or record measured persistence evidence |
| GET | `/api/health` | Version and SQLite readiness check |

### 18.19 Validation evidence

The automated regression suite passed: **83 tests** after the new analytics and workflow implementation. The suite covers both prior functionality and added reservation, chronology, import, proposal and checkpoint behavior. The 20-scenario sweep verifies per-stage quantity conservation, line/day capacity limits, pooled factory-stage capacity limits and portfolio status reconciliation.

Desktop browser tests on an isolated database confirmed:

- All principal workspaces render, with no captured JavaScript errors in the checked flows.
- A capacity cell exposes its exact available/reserved minutes, output, outsourced units and order links.
- Clearing a synthetic material shortage makes `PO-2607` schedulable and revises its shipment forecast.
- Reload preserves the order detail and updated release evidence.
- Approving line L1 moves the plan to F1/L1 and recalculates the expected shipment.
- A recurrence pilot accepts a valid measured 30-day period, shows improvement observed for day 30, and leaves days 60/90 awaiting evidence.
- Creating a RACI action adds the action to the execution workspace and event ledger.

These tests do not demonstrate the correctness of every possible input or certify industrial deployment. Real-world acceptance additionally requires representative factory data, finance reconciliation, uncertainty calibration, security review and monitored operation.

## 19. Interactive GitHub Pages deployment — 16 October 2026

### 19.1 Deployment outcome

The application at `https://mah-era.github.io/PlantCore/` is an interactive desktop workspace. It supports the same nine views and working flows as the local FastAPI application: importing compatible CSV, XLSX, and full/order-row JSON; recalculating the selected file; navigating orders and incidents; recording decisions, commitments, actions, hypotheses, negotiations, pilots, and checkpoints; reloading; and exporting HTML, JSON, CSV, and working-scenario reports. The earlier static showcase has been replaced in the Pages publishing pipeline.

### 19.2 Architecture

GitHub Pages serves static files. `scripts/build_pages.py` assembles a release directory containing the existing `web/` application, the Python source modules, 20 full synthetic scenarios, an order-table template, and a file manifest. `.github/workflows/pages.yml` builds this directory and publishes it as the Pages artifact.

`site/browser-adapter.js` intercepts the dashboard's `/api/` calls and sends them to a dedicated browser Web Worker. `site/python-worker.js` loads pinned Pyodide 0.28.3 and the FastAPI, Pydantic, SQLite, and OpenPyXL dependencies. It mounts the packaged Python files into Pyodide's virtual filesystem, invokes the actual FastAPI application through its ASGI interface, and returns HTTP status, headers, and body to the existing JavaScript views. Requests are serialized because one Python interpreter and one active scenario share the worker. Python's thread-pool calls execute inline because browser WebAssembly cannot start the application's normal worker threads. The same Python scheduling, financial, validation, reporting, and workflow code is therefore used in both deployment modes.

The worker copies the SQLite database into IndexedDB after every successful mutating request. On startup, it restores that database before the API serves the first request. This retains uploads, the active scenario, action updates, approved decisions, commitments, and other event records across reloads in the same browser profile. The browser's location, privacy settings, and storage quota govern retention. Clearing site storage removes the data. There is no central database or synchronization between devices, browsers, tabs, or users. The first load needs internet access to retrieve the pinned Python runtime and package files; normal Pages hosting also needs network access.

Files are parsed in the browser worker. The application does not transmit uploaded factory data to a PlantCore server. Public CDN requests load program code and dependencies. The full JSON evidence pack is the portable record of analysis and actions; the working scenario export carries source-level changes but is not a complete database backup. For an organizational deployment, a managed backend and authenticated shared storage are still necessary.

### 19.3 Browser verification

The assembled Pages directory was served on a separate local static port and exercised through the browser UI. The baseline network loaded with its 30 orders. Uploading `examples/sample-orders.csv` changed the control tower to three orders, 3,800 units, one late order, one blocked order, 33.3% forecast OTIF, and no invented historical yield; the capacity view showed that uploaded network. A JSON evidence-pack download contained matching scenario and portfolio totals. A reload restored the same active uploaded scenario. A full scenario JSON for recurring needle failures changed the control tower to its 30-order disruption case, and the execution workspace loaded the incident's RACI actions. A new action was recorded and remained visible after reload. An XLSX version of the order table imported and recalculated correctly. The browser build uses the 20 packaged scenarios through the same manifest.

These checks cover representative input formats and critical state transitions. They do not prove all possible files, browser storage failure modes, or simultaneous-tab behavior. The local Python test suite and 20-scenario invariant sweep remain the automated calculation checks. The Pages build must pass its deployment workflow and be tested at the public URL before a live deployment is considered verified.

### 19.4 Operating and production limits

The desktop browser needs JavaScript, WebAssembly, IndexedDB, and sufficient memory for Pyodide and the planning model. Initialization is slower than the local server because the browser downloads and starts Python. A private-browsing session or cleared site data does not preserve decisions. Browser records are local and cannot serve an authenticated team war room; named actors are recorded text fields rather than verified identities. The underlying planning, financial, causal, and operational limitations in chapters 18 and the requirement matrix continue to apply unchanged.

## 20. Expanded visual outputs — 16 October 2026

The Visual analytics workspace supplements the existing operational charts with 30 analytical views. Its seven category filters cover Delivery (7 views), Network (2), Cost (4), Capacity (6), Quality (6), Execution (4), and Evidence (1). Views include order and unit delivery composition, customer exposure and workload, delivery buffer distribution, cumulative due demand versus planned full-order shipments, quantity versus lateness risk, factory manufacturing proxy, order target variance, sewing utilization and headroom, daily capacity versus reservations, downstream peak utilization, stage queues, packed inventory, observed first-pass yield, rework and adherence trends, absence, downtime causes, action status/ownership/overdue counts, event counts, and input record coverage.

The library reads the active analytics, actions, and audit endpoints. It uses the same API transport on the local Python server and GitHub Pages. The views distinguish forecasts, modeled cost exposure, and supplied historical observations. No history is synthesized for an order-only upload. Blocked orders are retained in due demand and exposure, but excluded from forecasts that need a feasible shipment date or manufacturing amount. Line utilization sums reserved and available minutes over the 42-day horizon. Unused minutes indicate a planning opportunity, not an automatically feasible allocation. Stage queue balances remain planned inventory rather than observed WIP.

Every panel includes its analytical question, units, method note, source name, planning date, provenance, and an expandable data table. Ranked bars show the top 12 categories by absolute value and disclose that limit. Tables and per-chart CSV exports include every contributing row. Negative manufacturing variance and delivery buffer use diverging bars with a visible zero reference. The rework time series uses a labeled zero-based scale suited to the observed rate. CSV exports escape formula-leading text while preserving numeric values. Unusual user labels are HTML-escaped and aggregation uses dictionaries without inherited properties.

The new Visual analysis report HTML export embeds all 30 panels, SVG charts, stylesheet, source notes, and data tables in one printable document. It requires no network resources once downloaded. The export re-reads the active scenario, ensuring that an earlier visual snapshot cannot be exported as though it were the newly selected file. Existing management HTML/JSON, order CSV, and working-scenario outputs remain available.

Validation includes JavaScript syntax checks, browser rendering and category filtering, downloaded visual HTML inspection, and aggregate reconciliation against a full synthetic network and a small CSV import. The reconciliation checks order/unit totals, customer exposure, cumulative demand, manufacturing totals, missing history, nonfinite chart coordinates, and unusual labels. The visual library does not add new calibrated forecasting or causal models; the existing model boundaries still apply.

## 21. Live upload-to-report verification — 17 October 2026

A deployed-browser audit exercised JSON, CSV, and XLSX uploads across all ten workspaces, downloaded reports, and reconciled the resulting analytical payloads against fresh Python calculations. The three datasets produced distinct order quantities, on-time outcomes, commercial exposure, capacity and evidence coverage. Invalid CSV validation preserved the last valid dataset, and reload retained the imported workbook. Detailed inputs, outcomes, limitations, and corrected defects are recorded in [Live upload verification](docs/live-upload-verification.md).

The audit corrected the cumulative shipment graph to include shipment dates outside the deadline range and show calendar-proportional steps, and added an explicit import-analysis status overlay to prevent apparent nonresponse and conflicting interactions while processing.

## 22. Operations Studio redesign — 21 October 2026

### 22.1 Product direction and scope

The interface was rebuilt under one design system across all ten workspaces, both detail views, shared dialogs, forms, analytical panels, and downloadable HTML reports. The visual hierarchy now begins with an actionable network brief, six headline measures, and supporting operational evidence. Factory performance, recovery comparisons, execution records, and governance use the same visual vocabulary. The supplied blue, sky, coral, cream, and navy palette is retained, with explicit semantic green and red status treatments.

The implementation includes a custom SVG monogram, coherent line icons, typography and spacing tokens, a grouped navigation rail, active-page indication, focus treatments, restrained hover transitions, reduced-motion support, and consistent empty/loading/error states. The 30-view visual library retains source notes, units, CSV exports, and expandable evidence tables, with numbered analytical questions and accessible filter state.

### 22.2 Responsive and keyboard interaction

The earlier desktop-only interface is superseded by desktop, tablet, and mobile compositions. At 900px the navigation becomes a drawer with an explicit close button, backdrop, focus trap, background isolation, and focus restoration. At 680px panels and forms stack, filters rearrange, and buttons retain touch-friendly dimensions. Long schedules, heatmaps, tables, and SVG charts use contained horizontal scrolling rather than forcing the full page wider or shrinking dense analytical labels indefinitely.

Cmd/Ctrl+K opens a searchable workspace navigator. The skip link transfers focus to the current workspace without changing routes. Imports support keyboard activation. Active navigation and category filters expose their state through ARIA attributes. Dialogs and exports inherit the same hierarchy and palette.

### 22.3 Implementation and deployment

`web/app.css` is the central presentation layer. The new `web/experience.js` manages navigation, search, static icons, and accessibility decoration. Existing scheduling, recovery, finance, causal, and improvement logic is preserved. The management report's HTML style and visual report's embedded stylesheet are updated to match the application.

The Pages packager now creates a content version from the distributed UI, worker, and Python files. The HTML's version query propagates through the worker to Python manifest and source requests. This reduces stale-cache mismatches after deployment and preserves existing IndexedDB data. Local static responses use revalidation headers. The CI JavaScript syntax gate now includes the experience layer.

### 22.4 Review and evidence

All 83 Python tests passed, the 20-scenario sweep passed, visual aggregates reconciled, JavaScript syntax checks passed, and the Pages build succeeded. Desktop and mobile checks covered all ten workspaces; a tablet review checked the improvement workspace and drawer. Further UI checks covered filtering, quick search, keyboard navigation, capacity drill-through, recovery selection, a commercial dialog, sample CSV upload, all five downloads, and reload persistence. The sample CSV produced 3 orders, 3,800 units, 33.3% forecast OTIF, rounded exposure of $4,854, and unavailable historical yield. Downloaded evidence matched those values.

The updated screenshots, component decisions, responsive rules, and review limitations are documented in [Design system and review notes](docs/design-system.md). This release improves the experience; it does not change the limitations around authentication, shared hosting, live factory integration, causal verification, or forecast calibration described elsewhere in this report.
