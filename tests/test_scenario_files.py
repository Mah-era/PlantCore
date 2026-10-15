"""Each of the 20 uploadable test files exercises a distinct operational condition."""

import copy
import asyncio
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from app import store
from app.engine import (
    allocation_check,
    line_capacity,
    line_minutes,
    lookup,
    schedule_all,
)
from fastapi import Request, HTTPException
from app.main import (
    overview,
    orders,
    report_csv,
    report_html,
    scenarios,
    upload_scenario,
)
from app.scenarios import SCENARIO_DIR, ScenarioError, load_file, validate_document
from app.seed import AS_OF, seed_data


def record(data, kind, id):
    return lookup(data[kind], id)


class ScenarioFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = seed_data()
        cls.files = sorted(SCENARIO_DIR.glob("*.json"))

    def test_exactly_twenty_distinct_valid_files(self):
        self.assertEqual(len(self.files), 20)
        docs = [load_file(path) for path in self.files]
        self.assertEqual(len({d["meta"]["id"] for d in docs}), 20)
        self.assertTrue(all(d["meta"]["synthetic"] for d in docs))
        self.assertTrue(all(len(d["data"]["orders"]) == 30 for d in docs))

    def test_rejects_broken_order_reference(self):
        doc = load_file(self.files[0])
        doc = copy.deepcopy(doc)
        doc["data"]["orders"][0]["style_id"] = "MISSING"
        with self.assertRaises(ScenarioError):
            validate_document(doc)

    def test_rejects_inactive_orders_and_cyclic_actions(self):
        document = copy.deepcopy(load_file(self.files[0]))
        document["data"]["orders"][0]["status"] = "cancelled"
        with self.assertRaisesRegex(ScenarioError, "must be active"):
            validate_document(document)
        document = copy.deepcopy(load_file(self.files[0]))
        actions = document["data"]["actions"]
        actions[0]["dependency"] = actions[1]["id"]
        actions[1]["dependency"] = actions[0]["id"]
        with self.assertRaisesRegex(ScenarioError, "dependency cycle"):
            validate_document(document)

    def test_verified_cause_requires_verification_evidence(self):
        document = copy.deepcopy(load_file(self.files[0]))
        document["data"]["incidents"][0]["verification"] = None
        with self.assertRaisesRegex(ScenarioError, "needs evidence and verification"):
            validate_document(document)

    def test_switching_keeps_workflow_state_separate(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            store, "DB_PATH", Path(tmp) / "test.db"
        ):
            store.select_scenario("02_late_fabric")
            store.execute(
                "INSERT INTO scenario_action_updates VALUES (?,?,?,?,?)",
                (
                    "02_late_fabric",
                    "ACT-001",
                    "done",
                    "Repaired in trial",
                    "2026-10-14",
                ),
            )
            self.assertEqual(
                next(a for a in store.data()["actions"] if a["id"] == "ACT-001")[
                    "status"
                ],
                "done",
            )
            store.select_scenario("baseline")
            self.assertNotEqual(
                next(a for a in store.data()["actions"] if a["id"] == "ACT-001")[
                    "status"
                ],
                "done",
            )
            store.select_scenario("02_late_fabric")
            self.assertEqual(
                next(a for a in store.data()["actions"] if a["id"] == "ACT-001")[
                    "status"
                ],
                "done",
            )

    def test_json_upload_validates_and_activates(self):
        raw = self.files[1].read_bytes()

        async def receive():
            return {"type": "http.request", "body": raw, "more_body": False}

        with tempfile.TemporaryDirectory() as tmp, patch.object(
            store, "DB_PATH", Path(tmp) / "test.db"
        ):
            result = asyncio.run(
                upload_scenario(
                    Request({"type": "http", "method": "POST", "headers": []}, receive)
                )
            )
            self.assertTrue(result["active"]["id"].startswith("upload_"))
            self.assertEqual(store.active_id(), result["active"]["id"])
            self.assertEqual(len(store.data()["orders"]), 30)
            self.assertIn("attachment", report_csv().headers["content-disposition"])

    def test_json_upload_rejects_missing_collection(self):
        document = load_file(self.files[0])
        document = copy.deepcopy(document)
        document["data"].pop("materials")
        raw = json.dumps(document).encode()

        async def receive():
            return {"type": "http.request", "body": raw, "more_body": False}

        with tempfile.TemporaryDirectory() as tmp, patch.object(
            store, "DB_PATH", Path(tmp) / "test.db"
        ):
            with self.assertRaises(HTTPException):
                asyncio.run(
                    upload_scenario(
                        Request(
                            {"type": "http", "method": "POST", "headers": []}, receive
                        )
                    )
                )

    def test_every_file_runs_dashboard_and_reports(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            store, "DB_PATH", Path(tmp) / "test.db"
        ):
            self.assertEqual(len(scenarios()["items"]), 21)
            for path in self.files:
                with self.subTest(path=path.name):
                    store.select_scenario(path.stem)
                    result = overview()
                    self.assertEqual(result["kpis"]["active_orders"], 30)
                    self.assertEqual(len(orders()), 30)
                    self.assertIn(b"order_id", report_csv().body)
                    self.assertIn(b"Production Management Report", report_html().body)

    def test_every_file_respects_daily_sewing_minutes(self):
        for path in self.files:
            with self.subTest(path=path.name):
                document = load_file(path)
                data = document["data"]
                data["_meta"] = document["meta"]
                plans = schedule_all(data)
                used = {}
                for order in data["orders"]:
                    plan = plans[order["id"]]
                    if not plan.get("feasible"):
                        continue
                    style = lookup(data["styles"], order["style_id"])
                    for row in plan["daily"]:
                        key = (plan["line_id"], row["date"])
                        used[key] = used.get(key, 0) + row["units"] * style["smv"]
                for (line_id, day), minutes in used.items():
                    available = line_minutes(
                        lookup(data["lines"], line_id), date.fromisoformat(day), data
                    )
                    self.assertLessEqual(
                        minutes, available + 0.001, (path.name, line_id, day)
                    )


def make_case_test(slug, assertion):
    def test(self):
        data = load_file(SCENARIO_DIR / f"{slug}.json")["data"]
        assertion(self, data, self.baseline)

    test.__name__ = "test_" + slug
    return test


CASE_ASSERTIONS = {
    "01_steady_network": lambda t, d, b: t.assertEqual(
        sum(x.get("delay_days", 0) > 0 for x in schedule_all(d).values()), 0
    ),
    "02_late_fabric": lambda t, d, b: t.assertGreater(
        record(d, "orders", "PO-2607")["material_date"],
        record(b, "orders", "PO-2607")["material_date"],
    ),
    "03_needles_fail": lambda t, d, b: t.assertLess(
        record(d, "lines", "L7")["efficiency"], record(b, "lines", "L7")["efficiency"]
    ),
    "04_absenteeism": lambda t, d, b: t.assertLess(
        record(d, "lines", "L7")["operators"], record(b, "lines", "L7")["operators"]
    ),
    "05_quality_release": lambda t, d, b: t.assertFalse(
        record(d, "orders", "PO-2618")["quality_release"]
    ),
    "06_rush_order": lambda t, d, b: t.assertLess(
        record(d, "orders", "PO-2618")["due_date"],
        record(b, "orders", "PO-2618")["due_date"],
    ),
    "07_demand_surge": lambda t, d, b: t.assertGreater(
        record(d, "orders", "PO-2618")["quantity"],
        record(b, "orders", "PO-2618")["quantity"],
    ),
    "08_planned_maintenance": lambda t, d, b: t.assertEqual(
        line_capacity(
            record(d, "lines", "L7"),
            record(d, "styles", "S08"),
            AS_OF.replace(day=16),
            d,
        ),
        0,
    ),
    "09_factory_shutdown": lambda t, d, b: t.assertEqual(
        line_capacity(
            record(d, "lines", "L7"),
            record(d, "styles", "S08"),
            AS_OF.replace(day=15),
            d,
        ),
        0,
    ),
    "10_logistics_delay": lambda t, d, b: t.assertGreater(
        record(d, "factories", "F3")["logistics_days"],
        record(b, "factories", "F3")["logistics_days"],
    ),
    "11_compliance_hold": lambda t, d, b: t.assertGreater(
        sum(not x["feasible"] for x in schedule_all(d).values()), 0
    ),
    "12_defect_spike": lambda t, d, b: t.assertLess(
        record(d, "factories", "F3")["quality"], record(b, "factories", "F3")["quality"]
    ),
    "13_rework_growth": lambda t, d, b: t.assertGreater(
        sum(x["rework"] for x in d["production"] if x["line_id"] == "L7"),
        sum(x["rework"] for x in b["production"] if x["line_id"] == "L7"),
    ),
    "14_second_shift": lambda t, d, b: t.assertGreater(
        line_capacity(record(d, "lines", "L7"), record(d, "styles", "S08"), AS_OF, d),
        line_capacity(record(b, "lines", "L7"), record(b, "styles", "S08"), AS_OF, b),
    ),
    "15_low_cost_trap": lambda t, d, b: t.assertLess(
        record(d, "factories", "F3")["cost"], record(b, "factories", "F3")["cost"]
    ),
    "16_complex_style": lambda t, d, b: t.assertGreater(
        record(d, "styles", "S08")["smv"], record(b, "styles", "S08")["smv"]
    ),
    "17_capacity_crunch": lambda t, d, b: t.assertTrue(
        all(
            x["efficiency"] < record(b, "lines", x["id"])["efficiency"]
            for x in d["lines"]
            if x["factory_id"] == "F1"
        )
    ),
    "18_combined_disruption": lambda t, d, b: t.assertGreater(
        record(d, "factories", "F3")["logistics_days"],
        record(b, "factories", "F3")["logistics_days"],
    ),
    "19_fast_quality_tradeoff": lambda t, d, b: t.assertLess(
        record(d, "factories", "F1")["quality"], record(b, "factories", "F1")["quality"]
    ),
    "20_no_machine": lambda t, d, b: t.assertTrue(
        all(
            allocation_check(record(d, "orders", "PO-2610"), line, d)
            for line in d["lines"]
        )
    ),
}

for slug, assertion in CASE_ASSERTIONS.items():
    setattr(ScenarioFileTests, "test_" + slug, make_case_test(slug, assertion))
