# PlantCore requirement coverage — version 0.2

This matrix reviews the complete original brief. “Implemented” means executable and testable in the local application. “Partial” means the connected workflow exists but does not satisfy every production-grade detail. No item in the original vision is silently treated as complete.

| Requirement | Implemented now | Remaining boundary |
| --- | --- | --- |
| 1. Multi-factory network | Factories, capabilities, costs, compliance, quality/reliability, lines, skills/machines, operators, maintenance, shutdowns, calendars, styles, SMV, operation routes, orders, target costs, material/quality gates, logistics, commitments | Machine-instance availability, named operator certifications, factory-specific shift calendars, sourcing certification records, and contractual overtime rules |
| 2. Order allocation | Compatibility/MOQ/gate/compliance checks, candidate ranking, full-network rescheduling, displaced-order counts, approved line assignment with retained alternatives and rationale | Multi-factory quantity splitting and a global optimization objective; cost/reliability scoring uses disclosed heuristic weights |
| 3. Capacity schedule | Cutting → sewing → finishing → inspection → packing → transit; shared reservations, precedence, material releases, holidays, maintenance, shutdowns, changeover, daily quantities, capacity heatmap, Gantt, planned WIP, lateness | Detailed operation/machine sequencing, exact rework resource reservation, customer carrier cut-off times, actual milestone tracking |
| 4. Control tower | Scenario-driven KPIs, output/target history, material/quality readiness, factory exposure/QCD, capacity, risk orders, response owners, order/incident drilldowns | Live event ingestion, push alerts, measured production-stage progress by order |
| 5. Disruption detection | Late/blocked forecast exceptions, source incidents, machine/material/quality/compliance/workforce effects, lost-capacity proxies, exposure, deadlines, variability analysis | Dedicated detection models for every disruption category; trained confidence calibration; automated customer/market segmentation |
| 6. Root cause and prevention | Cause contribution/cumulative Pareto, line event log, six fishbone dimensions, structured 5 Whys, hypotheses/contributing factors/rejection/verification, evidence/verification fields, reviewer history | Binary attachments, statistical hypothesis ranking, cross-case similarity search, causal experiments and preventive-action recommendation models |
| 7. Dynamic recovery | Repair/overtime, same-factory transfer, partner transfer, subcontract capacity, freight expedite, commercial partial-delivery terms, lead times, quality premiums, labor/commitment notes, displaced orders, approval/rationale/alternatives | Scheduled partial lots, real temporary-shift contracts, operation-specific subcontracting, expedited material procurement, inspection/rework reservation alternatives, measured sustainability |
| 8. Financial and negotiation | Incremental spend, manufacturing proxy, penalty/margin/quality/displacement components, total impact, cost composition, cost-delivery scatter, supplier contribution/concession proposals and buyer net impact | Full financial ledger covering actual material, labor, scrap, tax, cancellation, chargeback settlement; proposal acceptance does not constitute a contract |
| 9. War room | Incident owners, new RACI actions, due dates/dependencies, status/evidence updates, prerequisite checks, overdue indicators, commitments, explicit management decisions, audit views | Authenticated roles, notifications/escalation dispatch, meeting calendar integration, evidence object storage, legally attributable approvals |
| 10. PDCA | Plan/do/check/act observations; verified-cause pilot, retained baseline/target, measured production-period checks, comparable volume ±20% and SMV ±10%, FPY guardrail, 30/60/90 windows, sustained status | Automatic observation ingestion, controlled causal evaluation, organization-wide standard deployment, multiple incident-specific outcome measures beyond downtime |
| 11. Learning | Assumption notes, observations, decision alternatives, rule proposals, reasons, old/proposed values, review history, approvals/rejections | Calibrated forecast error pipeline, automatic recommendation learning, managed rule promotion/version execution and rollback |
| Quality KPIs | Observed FPY, rework rate/units, quality gate/hold counts, modeled option quality risk | Repeat-defect rate, rejected batch percentage, defect-type rates, actual scrap, fully reconciled inspection quality ledger |
| Cost KPIs | Manufacturing proxy and target variance in analytics, modeled recovery and delivery exposure, supplier-sharing net impact | Actual cost per acceptable unit from accounting, actual overtime/rework/scrap, cancellation loss, actual contribution margin |
| Delivery KPIs | Forecast OTIF, schedule output adherence, expected shipment, delay/slack, exposed orders/units, simulated on-time likelihood | Actual shipment OTIF, actual milestone adherence, recovery-duration and plan-stability time series |
| Leadership KPIs | Open/done/overdue/blocked actions, recorded decisions, commitments/status/actual dates, comparable checks and persistence windows | Escalation response time, historical commitment-reliability trend, decision-to-action lead time, portfolio recurrence rates |
| Required data | Documented synthetic 3-factory/8-line/10-style/30-order network, 20 full scenario files, compatible CSV/XLSX/JSON imports | Live permission-cleared ERP/MES integrations and arbitrary heterogeneous file mapping |
| Validation | Five dispatch policies; regression/invariant tests; 20-scenario quantity/capacity sweep; desktop workflow tests | Manual recovery policy comparator, optimizer optimality gaps, industrial-scale load tests, customer acceptance and calibrated forecast backtesting |
| Technical implementation | Python/FastAPI/SQLite, modular analytics/event ledger, custom SVG/HTML charts, API schema, health endpoint, container configuration, CI | PostgreSQL multi-user service, authentication/authorization, job queue, database migrations, structured telemetry, security and disaster recovery validation |
| Upload, export, reload | Selected-file recalculation, explicit missing-data state, retained source provenance, working-source/HTML/JSON/CSV exports, session navigation/filter state, durable scenario records, cancelled stale view requests | Multi-user scenario isolation and cross-tab concurrent-edit conflict resolution |
| Desktop visual transformation | Nine focused workspaces, professional neutral system, consistent forms/dialogs, chart legends/axes/units/tooltips, semantic status labels, keyboard focus, printable reports | Full accessibility audit and mobile interface (mobile intentionally excluded) |

## Release acceptance achieved

- State changes are reviewable in forms and persist locally.
- Forecast dates and reservations recalculate after release/allocation changes.
- No historical KPIs are fabricated for order-only uploads.
- Infeasible options remain visible with explanations.
- Statistical association is not labeled verified causation.
- A single early improvement observation cannot certify 90-day persistence.
- Source-level export and complete decision-history export have distinct, documented semantics.

## Next production gates

Before organizational deployment, add authenticated identity and authorization, per-user/scenario isolation, immutable evidence storage, monitored backups, a hosted backend, factory/finance data contracts, and calibrated acceptance tests. These are substantive implementation tasks; a visual redesign does not make them complete.
