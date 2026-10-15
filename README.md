# PlantCore — Multi-Factory Production Planning

PlantCore is a production-management decision platform for multi-factory apparel networks. It connects order allocation, capacity planning, disruption recovery, accountable response, and continuous improvement in one desktop web application.

A runnable, synthetic-data production management platform. Phase 1 connects order allocation, capacity planning, disruption detection, root-cause evidence, recovery economics, accountable actions, and PDCA verification in one local application.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. The SQLite database is created automatically at `data/platform.db`. Delete that file to reset the synthetic scenario.

## Test scenarios and files

The [`test-files/`](test-files/) folder contains **20 self-contained JSON test files**: steady flow; late fabric; needle failures; absenteeism; quality release; urgent deadline; demand surge; planned maintenance; factory shutdown; logistics delay; compliance hold; defect spike; rework growth; second shift; low-cost supplier trap; complex style; factory capacity crunch; combined disruption; speed-versus-quality tradeoff; and no compatible machine. Regenerate them with `python scripts/generate_scenarios.py`.

Use the scenario selector at the top of the web app to switch among these files. The control tower recalculates forecast dates, risk, exposed units, factory QCD, incident impact, recovery choices, and reports from the selected file. The scenario outcome panel shows the change from the original network for built-in tests.

**Upload file** accepts:

- A full scenario `.json` with `schema_version: 1`, `meta`, and `data`. Download the current scenario JSON for the complete structure. Set `meta.as_of` and optional `meta.holidays` to use the file's planning calendar.
- An order table in `.csv` or `.xlsx` (an `Orders` sheet or the first sheet). A JSON array of order rows, or `{ "orders": [...] }`, works too. Use [the sample order file](examples/sample-orders.csv) or the **CSV template** button in the app.

The order table requires `order_id`, `quantity`, `material_date`, and `due_date` (ISO `YYYY-MM-DD`). Useful optional columns are `as_of`, `synthetic`, `customer`, `factory_id`, `factory_name`, `line_id`, `style_id`, `style_name`, `category`, `machine`, `smv`, `operators`, `efficiency`, `daily_cut`, `daily_finish`, `daily_qc`, `daily_pack`, `factory_cost`, `factory_quality`, `factory_reliability`, `logistics_days`, `priority`, `quality_release`, `fabric_ready`, `trims_ready`, `shortage_units`, `margin_per_unit`, and `target_cost`. Common headings such as `qty`, `deadline`, `factory`, `line`, and `style` are recognized. Files are limited to 3 MB.

Missing network and cost columns use explicit illustrative assumptions shown on the dashboard and in the report. An order-only file does not imply historical production, downtime, or first-pass yield; those results show `N/A`. The platform automatically raises forecast-risk exceptions and actions for late or blocked orders without their own source incident, even when other incidents are supplied. Confirmed material shortages, pending quality release, and open quality holds block shipment forecasting until release is recorded. To analyze actual event history, upload a full scenario JSON. Uploads, decisions, commitments, and improvement records are kept separately in local SQLite.

The **Download report** menu provides a printable management HTML report, a complete JSON report, and an order-forecast CSV. A browser can print the HTML report to PDF. Reports use the currently selected scenario, its planning date, input coverage, assumptions, and calculated outcomes.

## What Phase 1 does

- Seeds **3 partner factories, 8 sewing lines, 10 styles, 30 orders**, materials, daily production, downtime, quality holds, labor availability, incidents, and action history.
- Rejects incompatible, noncompliant, unskilled, under-MOQ, unavailable-machine, material-short, and open-quality-hold allocations with explicit reasons.
- Reserves cutting before sewing, then pooled finishing, inspection, and packing capacity by day, followed by logistics. It accounts for calendars, factory shutdowns, planned maintenance, material releases, quality holds, and sewing changeovers.
- Flags late orders and exposes affected capacity, forecast delay, commercial exposure, and forecast confidence assumptions.
- Compares overtime, line transfer, factory transfer, subcontracting, split shipment, and expedited freight; infeasible options remain visible with reasons. Costs include operational premiums, expected late penalties, and contribution-margin exposure. Impacts on other orders are estimated.
- Records decisions, factory commitments, RACI actions, escalation status, PDCA observations, and proposed planning-rule revisions in SQLite.
- Reforecasts the order book when an approved recovery option changes the line, overtime, subcontract capacity, repair assumption, or freight mode.
- Compares the priority-aware plan against first-come-first-served, earliest-due-date, lowest-cost-factory, and highest-capacity dispatch rules.
- Keeps root-cause hypotheses separate from verified causes. The seeded case contains an evidence-backed verified cause; the UI shows the evidence and 5 Whys.

## Scope and limits

The included test figures are **simulated examples** in USD, dated **2026-10-14**. Uploaded files use their own `as_of` date, or the earliest material date if none is provided. No real factory or customer data is included in the examples. The scheduler is a transparent greedy daily-capacity heuristic, not a global optimizer. Cutting/finishing/inspection/packing share factory/day capacity; sewing uses line/day capacity. Recovery implementation lead time is applied before production can restart. Probabilities use an explicit uncertainty approximation, not a calibrated forecast. This is a **single-user local app**: uploaded records and decisions persist in SQLite, without authentication, role enforcement, or external notifications. Validate live source data and constraints before treating outputs as production commitments.

## Phased roadmap

1. **Phase 1 (implemented):** connected synthetic scenario and manager workflow.
2. **Phase 2:** authenticated roles, imports/API integration, richer operation-level finite capacity, optimization and Monte Carlo calibration, audit trails, and attachment storage.
3. **Phase 3:** multi-site pilots, forecast back-testing, 30/60/90 day sustained-improvement monitoring, approved rule promotion, and deployment/observability.

## API

`/api/overview`, `/api/network`, `/api/orders`, `/api/orders/{id}`, `/api/allocate/{id}`, `/api/incidents`, `/api/incidents/{id}`, `/api/incidents/{id}/options`, `/api/decisions`, `/api/actions`, `/api/improvement`, `/api/rules`, and `/api/definitions`.

Run `python3 -m unittest discover -s tests -v` for the planning, scenario, and workflow checks.
