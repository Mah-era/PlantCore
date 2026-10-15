"""Scenario-scoped event ledger and controlled operating changes."""

import json
from datetime import datetime
from . import store


def initialize():
    store.initialize()
    with store.connect() as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS workflow_events (id INTEGER PRIMARY KEY AUTOINCREMENT, scenario_id TEXT NOT NULL, kind TEXT NOT NULL, entity_id TEXT NOT NULL, actor TEXT NOT NULL, evidence TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL)"
        )


def events(kind=None):
    initialize()
    query = "SELECT * FROM workflow_events WHERE scenario_id=?"
    params = [store.active_id()]
    if kind:
        query += " AND kind=?"
        params.append(kind)
    rows = store.rows(query + " ORDER BY id", params)
    return [{**r, "payload": json.loads(r["payload"])} for r in rows]


def record(kind, entity_id, actor, evidence, payload):
    initialize()
    return store.execute(
        "INSERT INTO workflow_events (scenario_id,kind,entity_id,actor,evidence,payload,created_at) VALUES (?,?,?,?,?,?,?)",
        (
            store.active_id(),
            kind,
            entity_id,
            actor,
            evidence,
            json.dumps(payload),
            datetime.now().isoformat(timespec="microseconds"),
        ),
    )


def apply(data):
    for event in events():
        p = event["payload"]
        entity = event["entity_id"]
        if event["kind"] == "release":
            order = next((o for o in data["orders"] if o["id"] == entity), None)
            if not order:
                continue
            material = next(m for m in data["materials"] if m["order_id"] == entity)
            material.update(
                {k: p[k] for k in ["fabric_ready", "trims_ready", "shortage_units"]}
            )
            order["quality_release"] = p["quality_release"]
            order["material_date"] = max(p["fabric_ready"], p["trims_ready"])
            if p["quality_release"]:
                for hold in data["quality_holds"]:
                    if hold["order_id"] == entity:
                        hold["status"] = "closed"
        elif event["kind"] == "action":
            data["actions"].append(p)
        elif event["kind"] == "hypothesis" and p["status"] == "verified":
            incident = next((i for i in data["incidents"] if i["id"] == entity), None)
            if incident:
                incident.update(
                    verified_root_cause=p["statement"],
                    verification=p["verification"],
                    evidence=event["evidence"],
                )
    return data
