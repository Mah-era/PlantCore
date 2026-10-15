"""SQLite persistence for scenario selection and scenario-scoped decisions."""

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from .seed import seed_data
from .scenarios import builtins, builtin_document

DB_PATH = Path(
    os.environ.get(
        "PLANTCORE_DB",
        str(Path(__file__).resolve().parents[1] / "data" / "platform.db"),
    )
)
DEFAULT_META = dict(
    id="baseline",
    name="Original production network",
    description="The connected 30-order reference scenario.",
    synthetic=True,
    builtin=True,
    as_of="2026-10-14",
    holidays=["2026-10-20"],
)


@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def initialize():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS seed_records (kind TEXT NOT NULL, record_id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(kind,record_id));
        CREATE TABLE IF NOT EXISTS decisions (id INTEGER PRIMARY KEY AUTOINCREMENT, incident_id TEXT NOT NULL, option_id TEXT NOT NULL, rationale TEXT NOT NULL, approver TEXT NOT NULL, decided_at TEXT NOT NULL, alternatives TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS commitments (id INTEGER PRIMARY KEY AUTOINCREMENT, incident_id TEXT NOT NULL, decision_id INTEGER NOT NULL, factory_owner TEXT NOT NULL, commitment TEXT NOT NULL, due_date TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open', actual_date TEXT);
        CREATE TABLE IF NOT EXISTS action_updates (action_id TEXT PRIMARY KEY, status TEXT NOT NULL, evidence TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS pdca (id INTEGER PRIMARY KEY AUTOINCREMENT, incident_id TEXT NOT NULL, stage TEXT NOT NULL, baseline REAL, observed REAL, volume INTEGER, complexity REAL, observation TEXT NOT NULL, recorded_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS rules (id INTEGER PRIMARY KEY AUTOINCREMENT, incident_id TEXT NOT NULL, rule_key TEXT NOT NULL, old_value TEXT NOT NULL, proposed_value TEXT NOT NULL, reason TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', approver TEXT, approved_at TEXT);
        CREATE TABLE IF NOT EXISTS scenario_uploads (id TEXT PRIMARY KEY, meta TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS app_state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS scenario_action_updates (scenario_id TEXT NOT NULL, action_id TEXT NOT NULL, status TEXT NOT NULL, evidence TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(scenario_id,action_id));
        """)
        for table in ("decisions", "commitments", "pdca", "rules"):
            columns = {r["name"] for r in db.execute(f"PRAGMA table_info({table})")}
            if "scenario_id" not in columns:
                db.execute(
                    f"ALTER TABLE {table} ADD COLUMN scenario_id TEXT NOT NULL DEFAULT 'baseline'"
                )
        db.execute(
            "INSERT OR IGNORE INTO app_state VALUES ('active_scenario','baseline')"
        )
        db.execute(
            "INSERT OR IGNORE INTO scenario_action_updates SELECT 'baseline',action_id,status,evidence,updated_at FROM action_updates"
        )
        if db.execute("SELECT COUNT(*) FROM seed_records").fetchone()[0] == 0:
            for kind, records in seed_data().items():
                for i, row in enumerate(records):
                    db.execute(
                        "INSERT INTO seed_records VALUES (?,?,?)",
                        (kind, row.get("id", f"{kind}-{i}"), json.dumps(row)),
                    )


def active_id():
    initialize()
    with connect() as db:
        return db.execute(
            "SELECT value FROM app_state WHERE key='active_scenario'"
        ).fetchone()[0]


def catalog():
    initialize()
    with connect() as db:
        uploaded = [
            dict(json.loads(r["meta"]), builtin=False)
            for r in db.execute(
                "SELECT meta FROM scenario_uploads ORDER BY created_at DESC"
            )
        ]
    return [DEFAULT_META, *builtins(), *uploaded]


def active_meta():
    selected = active_id()
    return next((x for x in catalog() if x["id"] == selected), DEFAULT_META)


def select_scenario(scenario_id):
    if scenario_id not in {x["id"] for x in catalog()}:
        raise KeyError(scenario_id)
    with connect() as db:
        db.execute(
            "UPDATE app_state SET value=? WHERE key='active_scenario'", (scenario_id,)
        )
    return active_meta()


def save_upload(document, uploaded_id, created_at):
    meta = {**document["meta"], "id": uploaded_id}
    doc = {**document, "meta": meta}
    initialize()
    with connect() as db:
        db.execute(
            "INSERT INTO scenario_uploads VALUES (?,?,?,?)",
            (uploaded_id, json.dumps(meta), json.dumps(doc), created_at),
        )
        db.execute(
            "UPDATE app_state SET value=? WHERE key='active_scenario'", (uploaded_id,)
        )
    return meta


def document(scenario_id=None):
    scenario_id = scenario_id or active_id()
    if scenario_id == "baseline":
        with connect() as db:
            data = {}
            for r in db.execute("SELECT kind,payload FROM seed_records ORDER BY rowid"):
                data.setdefault(r["kind"], []).append(json.loads(r["payload"]))
        return dict(schema_version=1, meta=DEFAULT_META, data=data)
    builtin = builtin_document(scenario_id)
    if builtin:
        return builtin
    with connect() as db:
        row = db.execute(
            "SELECT payload FROM scenario_uploads WHERE id=?", (scenario_id,)
        ).fetchone()
    if not row:
        raise KeyError(scenario_id)
    return json.loads(row["payload"])


def data():
    scenario_id = active_id()
    source = document(scenario_id)
    result = source["data"]
    meta = source["meta"]
    inferred = max((r["date"] for r in result["production"]), default=None) or min(
        o["material_date"] for o in result["orders"]
    )
    result["_meta"] = {
        **meta,
        "as_of": meta.get("as_of", inferred),
        "holidays": meta.get("holidays", []),
    }
    with connect() as db:
        updates = {
            r["action_id"]: dict(r)
            for r in db.execute(
                "SELECT * FROM scenario_action_updates WHERE scenario_id=?",
                (scenario_id,),
            )
        }
    for action in result["actions"]:
        if action["id"] in updates:
            action.update(
                status=updates[action["id"]]["status"],
                evidence=updates[action["id"]]["evidence"],
            )
    return result


def rows(query, params=()):
    initialize()
    with connect() as db:
        return [dict(r) for r in db.execute(query, params)]


def execute(query, params=()):
    initialize()
    with connect() as db:
        cursor = db.execute(query, params)
        return cursor.lastrowid


def record_decision(
    scenario_id,
    incident_id,
    option_id,
    rationale,
    approver,
    decided_at,
    alternatives,
    factory_owner,
    commitment,
    due_date,
):
    """Persist an approved choice and its factory promise in one transaction."""
    initialize()
    with connect() as db:
        cursor = db.execute(
            "INSERT INTO decisions (scenario_id,incident_id,option_id,rationale,approver,decided_at,alternatives) VALUES (?,?,?,?,?,?,?)",
            (
                scenario_id,
                incident_id,
                option_id,
                rationale,
                approver,
                decided_at,
                alternatives,
            ),
        )
        db.execute(
            "INSERT INTO commitments (scenario_id,incident_id,decision_id,factory_owner,commitment,due_date,status) VALUES (?,?,?,?,?,?,?)",
            (
                scenario_id,
                incident_id,
                cursor.lastrowid,
                factory_owner,
                commitment,
                due_date,
                "open",
            ),
        )
        return cursor.lastrowid
