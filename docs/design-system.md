# PlantCore Operations Studio

## Design intent

The October 2026 redesign treats PlantCore as an operational decision workspace. Its hierarchy starts with the decision, then the numerical summary, then the analytical evidence. The interface uses a warm neutral canvas, a navy navigation rail, crisp white analytical surfaces, and restrained coral signals. It retains the supplied five-color brand palette.

The changes cover the control tower, factory intelligence, capacity and schedule, order portfolio and detail, disruption register and investigation, recovery studio, execution, continuous improvement, data governance, all 30 visual outputs, shared dialogs, and both HTML report formats. Existing model outputs and workflow operations are preserved.

## Foundations

| Foundation | Implementation |
| --- | --- |
| Primary ink and navigation | `#293241` |
| Primary action and analytical series | `#3D5A80` |
| Information and focus accent | `#98C1D9` |
| Intervention accent | `#EE6C4D` |
| Warm brand surface | `#F5F1E3` |
| Workspace canvas | `#F4F3EE` |
| Success and blocked semantics | Green/deep red with explicit labels; color is never the sole status cue |
| Type | Avenir Next, Segoe UI, platform sans-serif fallback; no remote font dependency |
| Numbers | Tabular numerals in tables; large measures separated from units and explanatory notes |
| Geometry | 12px analytical panels, 7px controls, subtle borders and shallow shadows |
| Motion | Short color, elevation, drawer, and dialog transitions; reduced-motion override |

## Composition and navigation

The sidebar groups work into Monitor & plan, Investigate & respond, and Improve & govern. A custom SVG monogram and consistent line icons replace miscellaneous text glyphs. The active workspace is marked by a coral edge, icon, dot, and `aria-current`.

The control tower uses a dedicated decision brief and a six-measure grid. Factory comparisons use consistent cards. Recovery pairs financial composition with delivery confidence before the detailed option cards. The visual library numbers each analytical question, labels its units and source, provides category filters, and preserves expandable source tables and CSV downloads.

Quick navigation opens with its sidebar button or Cmd/Ctrl+K. Search matches workspace titles and purpose descriptions. Native modal dialogs provide modal focus behavior; Escape closes them. The mobile navigation drawer explicitly manages focus, traps Tab, restores focus on close, and makes the background inert. Import remains available from every workspace and supports keyboard activation. A skip link moves focus to the workspace without triggering a route change.

## Responsive behavior

- Above 900px: persistent navigation and adaptive multi-column layouts.
- At 900px and below: navigation becomes a modal drawer with an explicit close control and backdrop.
- At 680px and below: panel grids, factory cards, recovery options, and forms stack. Filters use a compact grid and dialog actions remain accessible while scrolling.
- Long tables, capacity heatmaps, and Gantt schedules remain in bounded scroll regions with keyboard focus.
- SVG charts retain a readable 560px canvas on narrow screens inside horizontally scrollable frames, with an explicit scroll hint. Exact values remain available through source tables and exports.
- Reports have their own responsive and print treatment. The visual report embeds the application stylesheet and all chart evidence without external dependencies.

## Engineering boundaries

`web/app.css` owns shared presentation tokens and responsive composition. `web/experience.js` handles workspace search, icons, mobile navigation, and accessibility decoration; it does not calculate forecasts. `web/app.js` and `web/enterprise.js` retain the existing business workflows. `web/visualizations.js` retains all 30 data-derived views and adds consistent panel and export treatment.

Local static responses ask browsers to revalidate. The Pages build calculates one content hash across the copied assets and Python bundle. The HTML references versioned scripts and styles; the adapter passes that version to the worker, which passes it to Python manifest/source requests. This addresses stale assets after deployment while leaving the IndexedDB database intact. An already-open tab still needs a reload to run a new release.

## Verification record

Review performed across the October 18–21, 2026 implementation sessions:

- All ten workspaces rendered at 1440px desktop and 390px mobile widths; no document-level horizontal overflow was observed in those checks.
- Inspected the control tower, factory cards, visual library, recovery comparison, and mobile order filters visually.
- Verified category filtering, workspace search, recovery-plan selection, and the supplier cost-sharing dialog.
- Re-ran all 83 Python regression tests, the 20-scenario constraint sweep, JavaScript syntax checks, and the visual aggregate reconciliation suite successfully.

The final local review also verified:

- A 768px tablet layout with the navigation drawer and continuous-improvement workspace; no document-level horizontal overflow.
- Mobile file-chooser upload of `examples/sample-orders.csv`: 3 orders, 3,800 units, 33.3% forecast OTIF, $4,854 rounded delivery exposure, and N/A historical first-pass yield.
- All five report downloads: management HTML, evidence JSON, order CSV, working scenario JSON, and visual HTML. The HTML and JSON files contained the uploaded identities and excluded prior reference-order identities. Both HTML formats include responsive metadata and the redesigned styles.
- Reload retained Sample Orders. No JavaScript errors were captured in this workflow.
- Capacity-cell drill-through exposed the day's available/reserved minutes, output, external quantity, and linked order.
- Drawer keyboard wrap, Escape close, Ctrl+K search, and skip-link focus without a route change.

These checks apply to the exercised browser and flows, not every possible device, input, or browser-storage condition. The report HTML was inspected as downloaded content; a separate cross-browser print-layout audit was not performed.

## Production scope

This redesign improves the product experience and deployment consistency. It does not introduce authenticated identities, role enforcement, a shared managed database, ERP connectors, or calibrated factory forecasts. The calculation and hosting boundaries in the README and requirement coverage remain applicable.
