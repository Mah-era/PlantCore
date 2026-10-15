"""Reconciliation and state-transition tests for PlantCore's connected workspaces."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import date, timedelta
from collections import defaultdict
from fastapi import HTTPException
from app import store, workflows
from app.analytics import analyze, simulate_recovery
from app.engine import schedule_all, recovery_options
from app.seed import seed_data
from app.importers import import_file
from app.scenarios import ScenarioError, validate_document
from app.main import (
    scenario,
    ReleaseIn,
    release_gate,
    AllocationIn,
    commit_allocation,
    HypothesisIn,
    hypothesis,
    NewAction,
    create_action,
    update_action,
    ActionUpdate,
    NegotiationIn,
    negotiation,
    PilotIn,
    create_pilot,
    CheckpointIn,
    create_checkpoint,
    checkpoints,
    DecisionIn,
    decide,
    analytics,
    export_scenario,
)


class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.data = seed_data()
        self.data["_meta"] = dict(store.DEFAULT_META)

    def test_portfolio_reconciles_factory_and_network(self):
        a = analyze(self.data)
        self.assertEqual(a["totals"]["orders"], 30)
        self.assertEqual(sum(f["units"] for f in a["factories"]), a["totals"]["units"])
        self.assertAlmostEqual(
            sum(f["expected_exposure"] for f in a["factories"]),
            a["totals"]["expected_exposure"],
            places=2,
        )
        self.assertEqual(
            sum(a["totals"][k] for k in ["blocked", "late", "on_time"]), 30
        )

    def test_stage_and_sewing_reservations_conserve_units(self):
        for p in schedule_all(self.data).values():
            if not p["feasible"]:
                continue
            for stage in ["cut", "finish", "qc", "pack"]:
                self.assertEqual(
                    sum(r["units"] for r in p["stages"] if r["stage"] == stage),
                    p["quantity"],
                )
            self.assertEqual(sum(r["units"] for r in p["daily"]), p["quantity"])
            self.assertTrue(
                all(
                    0 <= r["reserved_minutes"] <= r["available_minutes"] + 0.00001
                    for r in p["daily"]
                )
            )

    def test_shared_resources_not_double_booked(self):
        a = analyze(self.data)
        for line in a["heatmap"]:
            for cell in line["cells"]:
                self.assertLessEqual(
                    cell["reserved_minutes"], cell["capacity_minutes"] + 0.02
                )
        self.assertTrue(all((r["peak_utilization"] or 0) <= 1 for r in a["stage_load"]))

    def test_planned_wip_conserves_stage_balances(self):
        a = analyze(self.data)
        for day in a["flow"]:
            self.assertGreaterEqual(day["wip"], 0)
            self.assertGreaterEqual(day["ready_to_ship"], 0)
            self.assertEqual(
                day["wip"],
                sum(
                    day[k]
                    for k in [
                        "cut_queue",
                        "sew_queue",
                        "finish_queue",
                        "inspection_queue",
                    ]
                ),
            )
            self.assertLessEqual(
                day["wip"] + day["ready_to_ship"] + day["shipped"], a["totals"]["units"]
            )

    def test_order_table_history_remains_unavailable(self):
        doc = import_file(
            b"id,quantity,due_date,material_date\nA,500,2026-11-01,2026-10-14\n",
            "orders.csv",
        )
        d = doc["data"]
        d["_meta"] = doc["meta"]
        a = analyze(d)
        self.assertEqual(a["history"], [])
        self.assertIsNone(a["factories"][0]["first_pass_yield"])

    def test_future_history_does_not_pollute_analytics(self):
        before = analyze(self.data)
        self.data["downtime"].append(
            dict(self.data["downtime"][0], date="2099-01-01", minutes=999999)
        )
        self.assertEqual(analyze(self.data)["pareto"], before["pareto"])

    def test_simulation_reproducible_and_quantiles_ordered(self):
        i = self.data["incidents"][0]
        opts = recovery_options(i, self.data)
        first = simulate_recovery(self.data, i, opts)
        self.assertEqual(first, simulate_recovery(self.data, i, opts))
        for r in first["options"]:
            self.assertLessEqual(r["ship_p10"], r["ship_p50"])
            self.assertLessEqual(r["ship_p50"], r["ship_p90"])
            o = next(o for o in opts if o["id"] == r["id"])
            self.assertLess(
                abs(r["on_time_probability"] - o["on_time_probability"]), 0.04
            )

    def test_conflicting_shared_attributes_are_rejected(self):
        for column, values in [
            ("factory_cost", (4, 5)),
            ("operators", (30, 35)),
            ("efficiency", (0.6, 0.9)),
            ("compliance", ("yes", "no")),
        ]:
            payload = f"id,quantity,due_date,material_date,{column}\nA,100,2026-11-01,2026-10-14,{values[0]}\nB,100,2026-11-01,2026-10-14,{values[1]}\n".encode()
            with self.assertRaises(ScenarioError):
                import_file(payload, "orders.csv")

    def test_nonobject_history_rejected(self):
        self.data["labor"] = [None]
        with self.assertRaises(ScenarioError):
            validate_document(
                dict(schema_version=1, meta=store.DEFAULT_META, data=self.data)
            )


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patch = patch.object(store, "DB_PATH", Path(self.temp.name) / "test.db")
        self.patch.start()
        store.initialize()

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def release(self, order_id="PO-2607"):
        return release_gate(
            ReleaseIn(
                order_id=order_id,
                fabric_ready="2026-10-14",
                trims_ready="2026-10-14",
                shortage_units=0,
                quality_release=True,
                actor="Material lead",
                evidence="Supplier receipt and inspection evidence verified.",
            )
        )

    def test_release_changes_forecast_and_persists(self):
        self.assertFalse(schedule_all(scenario())["PO-2607"]["feasible"])
        result = self.release()
        self.assertTrue(result["plan"]["feasible"])
        self.assertTrue(schedule_all(scenario())["PO-2607"]["feasible"])
        self.assertEqual(workflows.events()[0]["kind"], "release")

    def test_release_preserves_derived_incident_and_action_history(self):
        incident = "AUTO-PO-2602"
        action = create_action(
            NewAction(
                incident_id=incident,
                title="Review the changed capacity commitment",
                accountable="Production manager",
                due_date="2026-10-16",
                actor="Factory planner",
                evidence="Retain this investigation after material dates improve.",
            )
        )
        self.release("PO-2602")
        d = scenario()
        self.assertIn(incident, {i["id"] for i in d["incidents"]})
        self.assertIn(action["id"], {a["id"] for a in d["actions"]})

    def test_quality_release_closes_holds(self):
        self.release("PO-2610")
        d = scenario()
        self.assertTrue(
            all(
                h["status"] == "closed"
                for h in d["quality_holds"]
                if h["order_id"] == "PO-2610"
            )
        )
        self.assertTrue(schedule_all(d)["PO-2610"]["feasible"])

    def test_release_export_and_scenario_isolation(self):
        self.release()
        doc = json.loads(export_scenario().body)
        validate_document(doc)
        self.assertEqual(
            next(m for m in doc["data"]["materials"] if m["order_id"] == "PO-2607")[
                "shortage_units"
            ],
            0,
        )
        store.select_scenario(store.catalog()[1]["id"])
        self.assertEqual(workflows.events(), [])
        store.select_scenario("baseline")
        self.assertEqual(len(workflows.events()), 1)

    def test_incompatible_allocation_rejected_without_event(self):
        with self.assertRaises(HTTPException):
            commit_allocation(
                AllocationIn(
                    order_id="PO-2618",
                    line_id="L5",
                    actor="Planner",
                    evidence="Review candidate feasibility and capacity.",
                )
            )
        self.assertEqual(workflows.events(), [])

    def test_allocation_changes_assignment(self):
        commit_allocation(
            AllocationIn(
                order_id="PO-2618",
                line_id="L4",
                actor="Planner",
                evidence="Receiving factory confirms transferred workload.",
            )
        )
        self.assertEqual(schedule_all(scenario())["PO-2618"]["line_id"], "L4")

    def test_later_recovery_decision_supersedes_allocation(self):
        self.test_allocation_changes_assignment()
        decide(
            DecisionIn(
                incident_id="INC-001",
                option_id="maintenance_overtime",
                rationale="Confirmed overtime roster and quality control.",
                approver="Manager",
                factory_owner="Factory lead",
                commitment="Factory commits approved overtime roster.",
                due_date="2026-10-16",
            )
        )
        self.assertTrue(scenario()["active_overrides"]["PO-2618"]["overtime"])

    def test_verified_hypothesis_requires_verification(self):
        with self.assertRaises(HTTPException):
            hypothesis(
                HypothesisIn(
                    incident_id="INC-001",
                    category="Method",
                    statement="Maintenance standard omitted a replacement interval.",
                    status="verified",
                    actor="Maintenance lead",
                    evidence="Service log observation and repeated faults.",
                )
            )
        self.assertEqual(workflows.events(), [])

    def test_custom_action_dependency(self):
        a = create_action(
            NewAction(
                incident_id="INC-001",
                title="Verify maintenance pilot output",
                accountable="Production manager",
                due_date="2026-10-16",
                dependency="ACT-001",
                actor="Quality lead",
                evidence="Follow approved inspection and maintenance checklist.",
            )
        )
        with self.assertRaises(HTTPException):
            update_action(
                a["id"], ActionUpdate(status="done", evidence="Completed inspection")
            )
        update_action(
            "ACT-001",
            ActionUpdate(status="done", evidence="Needle replacement verified"),
        )
        update_action(
            a["id"], ActionUpdate(status="done", evidence="Inspection outcome verified")
        )
        self.assertEqual(
            next(x for x in scenario()["actions"] if x["id"] == a["id"])["status"],
            "done",
        )

    def test_cost_sharing_reconciles(self):
        r = negotiation(
            NegotiationIn(
                incident_id="INC-001",
                option_id="maintenance_overtime",
                supplier_share=0.5,
                concession=100,
                actor="Commercial lead",
                evidence="Proposed split of approved incremental expenses.",
            )
        )
        self.assertEqual(
            r["buyer_expected_impact"],
            r["gross_expected_impact"] - r["supplier_contribution"] + 100,
        )

    def test_checkpoint_guards_and_persistence(self):
        pid = create_pilot(
            PilotIn(
                incident_id="INC-001",
                start_date="2026-10-14",
                target_reduction=0.45,
                actor="Maintenance lead",
                evidence="Pilot replacement interval after verified root cause.",
            )
        )["id"]
        baseline = checkpoints("INC-001")["pilot"]["payload"]["baseline"]
        for day in [30, 60, 90]:
            end = date(2026, 10, 14) + timedelta(days=day)
            create_checkpoint(
                CheckpointIn(
                    incident_id="INC-001",
                    pilot_id=pid,
                    start_date=end - timedelta(days=20),
                    end_date=end,
                    production_days=18,
                    events=0,
                    daily_volume=baseline["daily_volume"],
                    style_smv=baseline["style_smv"],
                    first_pass_yield=baseline["first_pass_yield"],
                    actor="Quality lead",
                    evidence="Synthetic comparable production period; output and inspection logs reviewed.",
                )
            )
        self.assertTrue(checkpoints("INC-001")["sustained"])
        end = date(2026, 10, 14) + timedelta(days=95)
        create_checkpoint(
            CheckpointIn(
                incident_id="INC-001",
                pilot_id=pid,
                start_date=end - timedelta(days=20),
                end_date=end,
                production_days=18,
                events=0,
                daily_volume=baseline["daily_volume"],
                style_smv=baseline["style_smv"],
                first_pass_yield=0.7,
                actor="Quality lead",
                evidence="Quality deterioration observed despite fewer downtime events.",
            )
        )
        self.assertFalse(checkpoints("INC-001")["sustained"])

    def test_whitespace_evidence_rejected(self):
        with self.assertRaises(HTTPException):
            release_gate(
                ReleaseIn(
                    order_id="PO-2607",
                    fabric_ready="2026-10-14",
                    trims_ready="2026-10-14",
                    shortage_units=0,
                    quality_release=True,
                    actor="  ",
                    evidence="          ",
                )
            )
