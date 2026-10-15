"""Validate each supplied scenario and reconcile all resource reservations."""

import json
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scenarios import validate_document
from app.analytics import analyze
from app.engine import schedule_all


def main():
    results = []
    for path in sorted(
        (Path(__file__).resolve().parents[1] / "test-files").glob("*.json")
    ):
        doc = validate_document(json.loads(path.read_text()))
        d = doc["data"]
        d["_meta"] = doc["meta"]
        a = analyze(d)
        plans = schedule_all(d)
        used = defaultdict(float)
        capacities = {}
        stages = defaultdict(int)
        for order_id, p in plans.items():
            if not p["feasible"]:
                continue
            assert sum(r["units"] for r in p["daily"]) == p["quantity"], order_id
            for r in p["daily"]:
                key = (p["line_id"], r["date"])
                used[key] += r["reserved_minutes"]
                capacities[key] = max(capacities.get(key, 0), r["available_minutes"])
            for stage in ["cut", "finish", "qc", "pack"]:
                assert (
                    sum(r["units"] for r in p["stages"] if r["stage"] == stage)
                    == p["quantity"]
                ), (order_id, stage)
            for r in p["stages"]:
                stages[(p["factory_id"], r["date"], r["stage"])] += r["units"]
        assert all(
            value <= capacities[key] + 0.001 for key, value in used.items()
        ), path
        factories = {f["id"]: f for f in d["factories"]}
        assert all(
            value <= factories[f]["daily_" + stage]
            for (f, day, stage), value in stages.items()
        ), path
        assert sum(a["totals"][k] for k in ["blocked", "late", "on_time"]) == len(
            d["orders"]
        )
        results.append(
            dict(
                scenario=path.stem,
                orders=a["totals"]["orders"],
                late=a["totals"]["late"],
                blocked=a["totals"]["blocked"],
                result="pass",
            )
        )
    print(json.dumps(dict(scenarios=len(results), results=results), indent=2))


if __name__ == "__main__":
    main()
