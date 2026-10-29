# User workflow audit — 30 October 2026

## Reproduced issue and correction

Selecting another dataset immediately changed the selector while the previous
portfolio remained actionable during analysis. Scenario selection did not acquire
the busy lock already used by uploads. Another selection, upload, or export could
therefore overlap the transition.

Scenario selection and file import now share one loading lifecycle. A visible,
announced progress message accompanies an inert workspace until analysis finishes.
Exports and overlapping dataset operations are guarded. Success and failure both
release the lock. Navigation updates respect the lock, and completion recalculates
navigation accessibility rather than restoring an obsolete viewport state.

## Verification

- Browser: uploaded `examples/sample-orders.csv`; observed 3 orders, 3,800 units,
  33.3% forecast OTIF, and $4,854 rounded modeled exposure.
- Browser: switched to Original production network; observed 30 orders, 27,562
  units, 56.7% OTIF, and $23,223 rounded exposure.
- Browser: loading status replaces actionable controls during a transition.
- Browser: navigated to Order portfolio and reloaded the workspace.
- Automated: 83 Python tests passed; visual reconciliation passed.
- Added `node tests/dataset-transitions.cjs` to continuous integration, covering
  overlapping selection/upload/export, successful completion, failed selection,
  oversized upload, lock release, and accessibility state restoration.

This is a scoped workflow audit, not a claim that every possible input or business
decision has been exhaustively verified.
