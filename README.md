# PlantCore

### Production intelligence for connected apparel networks

PlantCore connects multi-factory planning, capacity-constrained scheduling, disruption investigation, recovery economics, supplier commitments, and continuous improvement in a desktop decision workspace.

[Live interactive application](https://mah-era.github.io/PlantCore/) · [Repository](https://github.com/Mah-era/PlantCore) · [Detailed project report](project-report.md) · [Requirement coverage](docs/requirement-coverage.md)

![PlantCore production control tower](docs/images/control-tower.jpg)

## What changed in version 0.2

A substantial product and engineering upgrade introduces nine focused workspaces, daily reservation analytics, operational change controls, an evidence ledger, uncertainty simulation, and measured improvement checkpoints.

| Workspace | Decisions supported |
| --- | --- |
| **Control tower** | Identify exposed orders, delivery risk, release gates, and response owners |
| **Factory intelligence** | Compare observed quality, attendance, rework, downtime, and forecast delivery |
| **Capacity & schedule** | Inspect daily line reservations, stage capacity, shipment deadlines, and planned WIP |
| **Order portfolio** | Filter orders, resolve material/quality gates, and commit validated allocations |
| **Disruption intelligence** | Investigate cause concentration, fishbone dimensions, 5 Whys, hypotheses, and verified evidence |
| **Recovery studio** | Compare recovery costs, quality risk, displaced orders, uncertainty, and supplier cost-sharing |
| **Execution workspace** | Assign RACI owners, enforce action dependencies, track commitments, and retain decisions |
| **Continuous improvement** | Define pilots, measure comparable outcomes, review 30/60/90-day persistence, and propose rules |
| **Data & decision ledger** | Inspect source coverage, assumptions, benchmark policies, and operating changes |

Charts serve specific questions: output versus target, factory exposure, quality/adherence trends, downtime contribution, daily capacity heatmap, stage Gantt, WIP trajectories, recovery cost composition, cost–delivery trade-offs, and benchmark comparison. Every chart uses the selected file’s records or explicitly disclosed model assumptions.

The **Visual analytics** workspace adds 30 analytical views with category filters, hover values, source tables, and per-chart CSV downloads. Delivery, network, cost, capacity, quality, execution, and evidence panels use the active dataset. **Export report → Visual analysis report · HTML** downloads all 30 views as a self-contained, printable report with embedded SVG charts and expandable data tables. Charts without the necessary observations show an explicit missing-evidence state. Ranked charts show the top 12 categories; the data table and CSV retain all rows.

## Run PlantCore

### Open the hosted application

Use [PlantCore on GitHub Pages](https://mah-era.github.io/PlantCore/) to import CSV, XLSX, or JSON, analyze all nine workspaces, record decisions and actions, reload, and export reports. The hosted build runs the same FastAPI application and Python calculation modules inside a browser Web Worker using Pyodide. Its SQLite database is saved in that browser's IndexedDB. Initial startup downloads the Python runtime and packages; allow a short first load and an internet connection. Files and decisions stay on the current browser/device and are not shared between users or devices. Export the full JSON evidence pack for a portable record. Clearing site data or using a private session removes local records. This is not a centrally hosted, authenticated enterprise service.

### Run the Python server

Requires Python 3.10 or newer; CI uses Python 3.12.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open [PlantCore](http://127.0.0.1:8000/). SQLite initializes automatically at `data/platform.db`. Set `PLANTCORE_DB` to use another database path. Keep a backup of this database before changing or resetting it: it contains uploaded scenarios, approvals, commitments, and evidence history.

The desktop interface targets a viewport of at least 1120 pixels. Mobile support is outside the requested scope.

### Container configuration

```bash
docker compose up --build
```

The Compose file binds the service to `127.0.0.1:8000` and stores SQLite in a named volume. The image runs as a non-root user and exposes `/api/health`. Container configuration is supplied; a Docker build was not verified in the development environment because Docker was unavailable.

**Hosting:** GitHub Pages serves the full browser application. Pyodide executes the same API and calculation code locally in each browser. The optional Python server provides the same interface with filesystem SQLite storage and API documentation. Authentication, shared organizational access, and a managed production service remain separate work.

## Bring your own data

Use **Import data** for:

- Full network JSON: `schema_version: 1`, `meta`, and `data` collections. Includes factories, lines, styles, orders, materials, production, downtime, quality holds, labor, incidents, and actions.
- CSV or XLSX order tables. Excel uses an `Orders` sheet when present, otherwise the first sheet.
- A JSON array of order rows or `{ "orders": [...] }`.

Required order columns: `order_id`, `quantity`, `material_date`, `due_date`. Dates use `YYYY-MM-DD`. Aliases such as `qty`, `deadline`, `factory`, `line`, and `style` are supported. [Download the example](examples/sample-orders.csv).

Optional fields include `as_of`, `synthetic`, `customer`, factory/line/style IDs and names, `category`, `machine`, `smv`, `operators`, `efficiency`, factory stage capacities, cost/quality/reliability, `logistics_days`, priority, quality release, fabric/trim dates, shortage, margin, and target cost. Files are limited to 3 MB and full-schema collections to 3,000 records each; these limits are validation limits, not a performance guarantee.

Missing planning inputs use disclosed assumptions. Missing historical observations remain **N/A**. Conflicting factory or line attributes are rejected rather than silently depending on row order. A network shortage, unreleased quality gate, incompatible capability, missing machine, or compliance hold prevents an infeasible allocation.

**Export report** downloads a printable management HTML report, a detailed JSON evidence pack, an order forecast CSV, or a working scenario JSON. The working scenario includes source-level release and line-allocation changes; recovery overrides and workflow history are retained in the full JSON evidence pack.

## End-to-end demonstration

1. Select **Original production network**: 3 factories, 8 lines, 10 styles, and 30 orders.
2. Open **Capacity & schedule**, then the L7 reservation or order `PO-2618`.
3. Open `INC-001` in **Disruption intelligence** to inspect recurring flatlock failures and the documented maintenance cause.
4. Compare responses in **Recovery studio**. Inspect cost components, displaced orders, quality implications, and 2,000-trial shipment sensitivity.
5. Record a cost-sharing proposal, then approve a feasible operating plan with a factory owner and written commitment.
6. Assign and update actions in **Execution workspace**. A dependent action cannot close before its prerequisite.
7. Define an intervention pilot and record comparable production periods. The 30/60/90-day result remains unverified until evidence exists in each window.
8. Propose a planning-rule revision for management review. Approval does not silently deploy a formula change.

All packaged figures are **synthetic**, dated 14 October 2026. Custom files retain their own provenance and planning date.

## Validation

```bash
python -m unittest discover -s tests -v
python scripts/validate_scenarios.py
node --check web/app.js
node --check web/enterprise.js
```

The 20 files in [`test-files/`](test-files/) cover steady operation, late material, recurring failure, absence, quality holds, urgent dates, demand growth, maintenance, shutdown, transit, compliance, defect/rework growth, staffing expansion, low-cost traps, complex styles, capacity pressure, combined disruption, quality–speed trade-offs, and unavailable machines.

Automated checks cover scheduling constraints, quantity conservation at every stage, shared capacity, scenario isolation, import validation, exports, decision persistence, gate release, allocation, dependencies, cost-sharing reconciliation, reproducible simulations, and improvement guardrails. A scenario sweep reconciles reservations for all 20 files. Desktop browser verification covers navigation, heatmap drilldown, release/reallocation/reload, pilot/checkpoint records, action assignment, and the ledger. GitHub Actions runs the test suite, syntax checks, and scenario sweep on pushes and pull requests.

## Calculation boundaries

- The scheduler is a transparent daily-capacity heuristic, not an optimizer. It uses pooled factory stages and line sewing minutes, including a 12% initial changeover reservation.
- Current allocations place a whole order on one line. Detailed machine sequencing and multi-factory quantity splitting are not implemented.
- Recovery models overtime, repair assumptions, compatible transfers, added subcontract capacity, and expedited freight. Negotiated partial-delivery terms are **commercial sensitivity only**, with unchanged full-order shipment dates; no unverified tranche-on-time probability is reported.
- Expected exposure uses explicit penalty, contribution-margin, and probability assumptions. It is not actual financial loss. Manufacturing cost is a model proxy; full material, scrap, cancellation, tax, and carbon accounting require additional inputs.
- Monte Carlo uses fixed-seed shipment-date shocks; it tests uncertainty assumptions, not a calibrated factory reliability model.
- Planned WIP is calculated from scheduled stage quantities. Actual milestone adherence and actual OTIF require shipment/stage confirmations that are not present in the current schema.
- This is a **single-user browser or local-server application**. Hosted browser records are private to that browser profile. Named owners and approvers are recorded, but authentication, role enforcement, tamper-evident auditing, external notifications, ERP integration, and production observability are not implemented.

See the [coverage matrix](docs/requirement-coverage.md) for the complete requirement review and [project report](project-report.md) for formulas, architecture, development history, and operating limits.

## Code map

- `app/engine.py` — constraints, scheduling, allocation, recovery, benchmarks.
- `app/analytics.py` — portfolio, capacity, WIP, QCD, cause contributions, Monte Carlo.
- `app/main.py` — typed API, workflows, reports, static delivery, health.
- `app/workflows.py` — scenario-scoped operating event ledger and replay.
- `app/store.py` — SQLite persistence and atomic decision/commitment insertion.
- `app/importers.py`, `app/scenarios.py` — file conversion and validation.
- `web/` — desktop interface, chart components, dialogs, navigation and state.
- `site/`, `scripts/build_pages.py` — browser Python runtime, API transport, IndexedDB persistence, and Pages packaging.
- `tests/`, `scripts/validate_scenarios.py` — regression tests and reservation reconciliation.

API documentation is available at `/docs` when the server is running.
