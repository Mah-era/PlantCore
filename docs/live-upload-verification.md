# Live upload and report verification — 23 October 2026

Target: https://mah-era.github.io/PlantCore/

## Browser workflow exercised

Used the deployed GitHub Pages application and its Python Web Worker, with actual file chooser uploads and report downloads. The files were synthetic test inputs, not operational factory data. This review also covered the Operations Studio redesign, responsive layouts, keyboard navigation, cache-versioned assets, and reload persistence.

| Upload | Orders | Units | On time | Late | Blocked | Expected delivery exposure |
|---|---:|---:|---:|---:|---:|---:|
| `test-files/03_needles_fail.json` | 30 | 27,562 | 17 | 8 | 5 | $24,005.92 |
| `examples/sample-orders.csv` | 3 | 3,800 | 1 | 1 | 1 | $4,854.29 |
| Changed Excel order workbook | 3 | 600 | 3 | 0 | 0 | $0.00 |

The changed workbook used the sample CSV columns, new IDs `QA-NEW-1` through `QA-NEW-3`, customer `QA Changed Customer`, quantities 100/200/300, all quality releases enabled, and deadline 2026-12-20. Other sample fields were retained. This is a deliberately different, reproducible order-only input.

## Checks

- Opened all ten workspaces after each upload: control tower, factories, schedule, orders, disruptions, recovery, execution, improvement, governance, and visual analytics.
- Confirmed old order IDs, customers, and full-network factory names did not survive in new-file workspace content.
- Confirmed order-only files show unavailable historical quality/downtime evidence rather than synthetic history.
- Downloaded all five formats for the full scenario: management HTML, evidence JSON, forecast CSV, working-scenario JSON, and visual HTML.
- Downloaded changed-file evidence JSON, forecast CSV, management HTML, and visual HTML; checked new identities and absence of prior order IDs.
- Compared downloaded evidence against fresh local Python calculations for all three uploads: totals, complete portfolio, factories, heatmap, stage load, flow, history, Pareto, and coverage matched exactly.
- Reload retained the active uploaded workbook and its 30-view library.
- Invalid CSV missing quantity returned `Row 2 needs quantity` and preserved the prior valid dataset.
- No browser JavaScript errors were captured during these flows.

## Defects corrected

1. The cumulative demand/shipment chart sampled only order deadlines. Early shipment dates and shipments after the last deadline were absent. It now includes both deadline and shipment events, uses calendar-proportional horizontal positioning, and draws steps so it does not imply partial shipments between full-order events.
2. Upload processing left the prior dashboard visible without a processing indicator. A live status overlay now names the file being validated and analyzed, blocks conflicting interactions during import, and restores controls on success or failure.

Regression coverage includes early, late, and blocked orders sharing one deadline, plus proportional date spacing and step paths. The existing Python and visual reconciliation suites remain applicable.

## Scope of conclusion

These checks verify the exercised upload → analysis → workspace → download and reload paths on the deployed release. They do not prove every possible external file, workflow mutation, browser, print layout, or numerical edge case. Unsupported or invalid inputs still require schema validation; missing source history remains unavailable. The redesign review is recorded in [Design system and review notes](design-system.md).
