import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from app import store
from app.engine import (
    allocation_check,
    benchmark,
    lookup,
    recovery_options,
    schedule_all,
)
from app.main import (
    ActionUpdate,
    DecisionIn,
    PDCAIn,
    RuleIn,
    decide,
    record_pdca,
    update_action,
    scenario,
    propose_rule,
    overview,
    orders,
    incidents,
    report_csv,
    improvement,
)
from app.seed import seed_data
from datetime import date


class PlanningTests(unittest.TestCase):
    def setUp(self):
        self.data = seed_data()

    def test_seed_counts_and_focal_risk(self):
        self.assertEqual(
            (
                len(self.data["factories"]),
                len(self.data["lines"]),
                len(self.data["styles"]),
                len(self.data["orders"]),
            ),
            (3, 8, 10, 30),
        )
        plan = schedule_all(self.data)
        self.assertGreater(plan["PO-2618"]["delay_days"], 0)
        self.assertEqual(sum(x["units"] for x in plan["PO-2618"]["daily"]), 1450)

    def test_incompatible_allocation_is_rejected(self):
        order = lookup(self.data["orders"], "PO-2618")
        line = lookup(self.data["lines"], "L5")
        reasons = allocation_check(order, line, self.data)
        self.assertTrue(any("skill" in r for r in reasons))
        self.assertTrue(any("flatlock" in r for r in reasons))

    def test_recovery_options_and_cost_tradeoff(self):
        incident = lookup(self.data["incidents"], "INC-001")
        options = {o["id"]: o for o in recovery_options(incident, self.data)}
        self.assertGreaterEqual(len(options), 6)
        self.assertGreater(options["baseline"]["delay_days"], 0)
        self.assertEqual(options["cross_factory"]["implementation_days"], 3)
        self.assertGreaterEqual(
            options["cross_factory"]["delay_days"], options["baseline"]["delay_days"]
        )
        self.assertGreater(
            options["cross_factory"]["additional_cost"],
            options["baseline"]["additional_cost"],
        )
        self.assertGreater(
            options["subcontract"]["quality_risk"], options["baseline"]["quality_risk"]
        )

    def test_baselines_report_unreleased_material_and_quality_holds(self):
        rows = benchmark(self.data)
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(r["constraint_violations"] == 5 for r in rows))
        self.assertGreater(
            len({(r["late_orders"], r["estimated_cost"]) for r in rows}), 1
        )

    def test_unresolved_material_and_quality_gates_block_shipping(self):
        plans = schedule_all(self.data)
        self.assertIn("Material shortage", plans["PO-2617"]["reason"])
        self.assertIn("Open quality hold", plans["PO-2620"]["reason"])

    def test_no_feasible_allocation_when_compliance_is_held(self):
        for factory in self.data["factories"]:
            factory["compliance"] = False
        order = lookup(self.data["orders"], "PO-2618")
        self.assertTrue(
            all(allocation_check(order, line, self.data) for line in self.data["lines"])
        )
        self.assertFalse(schedule_all(self.data)[order["id"]]["feasible"])

    def test_shipment_on_deadline_counts_as_more_likely_on_time(self):
        focal = lookup(self.data["orders"], "PO-2618")
        focal["due_date"] = schedule_all(self.data)[focal["id"]]["expected_ship"]
        baseline = next(
            x
            for x in recovery_options(
                lookup(self.data["incidents"], "INC-001"), self.data
            )
            if x["id"] == "baseline"
        )
        self.assertEqual(baseline["delay_days"], 0)
        self.assertGreater(baseline["on_time_probability"], 0.5)

    def test_quality_risk_stays_within_probability_bounds(self):
        lookup(self.data["factories"], "F3")["quality"] = 0
        options = recovery_options(lookup(self.data["incidents"], "INC-001"), self.data)
        self.assertTrue(
            all(0 <= x["quality_risk"] <= 1 for x in options if x["feasible"])
        )


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = patch.object(store, "DB_PATH", Path(self.tmp.name) / "test.db")
        self.patch.start()
        store.initialize()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_decision_retains_alternatives(self):
        body = DecisionIn(
            incident_id="INC-001",
            option_id="maintenance_overtime",
            rationale="Protect quality while accelerating output",
            approver="Production manager",
            factory_owner="Factory general manager",
            commitment="Release repaired station and approved overtime roster",
            due_date=date(2026, 10, 17),
        )
        response = decide(body)
        self.assertEqual(response["status"], "recorded")
        self.assertEqual(len(store.rows("SELECT * FROM decisions")), 1)
        self.assertEqual(len(store.rows("SELECT * FROM commitments")), 1)
        self.assertIn(
            "cross_factory",
            store.rows("SELECT alternatives FROM decisions")[0]["alternatives"],
        )
        selected_scenario = scenario()
        self.assertEqual(
            selected_scenario["active_overrides"]["PO-2618"]["overtime"], 0.2
        )
        self.assertTrue(selected_scenario["active_overrides"]["PO-2618"]["repaired"])
        self.assertTrue(schedule_all(selected_scenario)["PO-2618"]["feasible"])

    def test_split_shipment_keeps_existing_recovery_plan(self):
        decide(
            DecisionIn(
                incident_id="INC-001",
                option_id="maintenance_overtime",
                rationale="Repair the bottleneck before adding hours",
                approver="Production manager",
                factory_owner="Factory manager",
                commitment="Repair and roster overtime for the line",
                due_date=date(2026, 10, 17),
            )
        )
        first = scenario()["active_overrides"]["PO-2618"]
        decide(
            DecisionIn(
                incident_id="INC-001",
                option_id="split_shipment",
                rationale="Ship the first tranche under the revised plan",
                approver="Production manager",
                factory_owner="Factory manager",
                commitment="Confirm both shipment tranches with customer",
                due_date=date(2026, 10, 18),
            )
        )
        self.assertEqual(scenario()["active_overrides"]["PO-2618"], first)

    def test_factory_transfer_reassigns_factory_dashboard_counts(self):
        before = overview()
        decide(
            DecisionIn(
                incident_id="INC-001",
                option_id="cross_factory",
                rationale="Use the partner line with confirmed capacity",
                approver="Production manager",
                factory_owner="Partner factory manager",
                commitment="Accept material and produce the transferred order",
                due_date=date(2026, 10, 18),
            )
        )
        transferred = next(x for x in orders() if x["id"] == "PO-2618")
        self.assertEqual(transferred["plan"]["factory_id"], "F2")
        after = overview()
        before_counts = {x["id"]: x["orders"] for x in before["factories"]}
        after_counts = {x["id"]: x["orders"] for x in after["factories"]}
        self.assertEqual(after_counts["F2"], before_counts["F2"] + 1)
        self.assertEqual(after_counts["F3"], before_counts["F3"] - 1)
        self.assertEqual(
            overview(factory_id="F2")["kpis"]["active_orders"], after_counts["F2"]
        )

    def test_decision_and_commitment_roll_back_together(self):
        with store.connect() as db:
            db.execute(
                "CREATE TRIGGER fail_commitment BEFORE INSERT ON commitments BEGIN SELECT RAISE(ABORT, 'failure'); END"
            )
        with self.assertRaises(Exception):
            decide(
                DecisionIn(
                    incident_id="INC-001",
                    option_id="expedite_freight",
                    rationale="Test atomic decision rollback with a failure",
                    approver="Production manager",
                    factory_owner="Factory manager",
                    commitment="Book expedited freight after approval",
                    due_date=date(2026, 10, 18),
                )
            )
        self.assertEqual(store.rows("SELECT * FROM decisions"), [])
        self.assertEqual(store.rows("SELECT * FROM commitments"), [])

    def test_action_dependency_is_enforced(self):
        with self.assertRaises(HTTPException):
            update_action(
                "ACT-002", ActionUpdate(status="done", evidence="Standard issued")
            )
        update_action(
            "ACT-001",
            ActionUpdate(status="done", evidence="Needle replaced and output checked"),
        )
        self.assertEqual(
            update_action(
                "ACT-002", ActionUpdate(status="done", evidence="Standard issued")
            )["status"],
            "done",
        )

    def test_check_stage_requires_comparable_context(self):
        with self.assertRaises(HTTPException):
            record_pdca(
                PDCAIn(
                    incident_id="INC-001",
                    stage="check",
                    observed=0.2,
                    observation="Downtime was reduced",
                )
            )

    def test_non_downtime_incident_has_no_invented_recurrence_target(self):
        result = improvement("INC-002")
        self.assertIsNone(result["baseline"]["events_per_day"])
        self.assertIsNone(result["targets"]["events_per_day"])
        self.assertIn("unavailable", result["assessment"])

    def test_blocked_order_has_consistent_gate_and_report_status(self):
        row = next(o for o in orders() if o["id"] == "PO-2617")
        self.assertFalse(row["material_ready"])
        self.assertEqual(row["material_shortage_units"], 100)
        self.assertFalse(row["plan"]["feasible"])
        impact = next(i["impact"] for i in incidents() if i["order_id"] == "PO-2617")
        self.assertIsNone(impact["expected_delay_days"])
        self.assertEqual(overview()["signals"]["blocked_orders"], 5)
        self.assertFalse(
            next(o for o in overview()["priority_orders"] if o["id"] == "PO-2617")[
                "material_ready"
            ]
        )
        csv_body = report_csv().body.decode()
        self.assertIn("material_shortage_units", csv_body)
        self.assertIn("PO-2617", csv_body)

    def test_rule_proposal_rejects_unknown_incident(self):
        with self.assertRaises(HTTPException):
            propose_rule(
                RuleIn(
                    incident_id="missing",
                    rule_key="line_factor",
                    old_value="0.8",
                    proposed_value="0.9",
                    reason="Observed a sustained change",
                )
            )


if __name__ == "__main__":
    unittest.main()
