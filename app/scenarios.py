"""Scenario-file contract and validation for local imports."""

from datetime import date
from pathlib import Path
import json
from math import isfinite

SCENARIO_DIR = Path(__file__).resolve().parents[1] / "test-files"
COLLECTIONS = (
    "factories",
    "lines",
    "styles",
    "orders",
    "materials",
    "production",
    "downtime",
    "quality_holds",
    "labor",
    "incidents",
    "actions",
)
MAX_BYTES = 3_000_000


class ScenarioError(ValueError):
    pass


def _date(value, field):
    try:
        date.fromisoformat(value)
    except (ValueError, TypeError):
        raise ScenarioError(f"Invalid ISO date in {field}") from None


def _fields(row, names, label):
    missing = [name for name in names if name not in row]
    if missing:
        raise ScenarioError(f"{label} is missing {', '.join(missing)}")


def _finite_number(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return isfinite(value)
    except (OverflowError, ValueError):
        return False


def validate_document(document):
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise ScenarioError("Upload a schema_version 1 scenario JSON file")
    meta = document.get("meta")
    data = document.get("data")
    if not isinstance(meta, dict) or not isinstance(data, dict):
        raise ScenarioError("Scenario needs meta and data objects")
    for key in ("id", "name", "description"):
        if not isinstance(meta.get(key), str) or not meta[key].strip():
            raise ScenarioError(f"Scenario meta.{key} is required")
    if not isinstance(meta.get("synthetic"), bool):
        raise ScenarioError("Scenario meta.synthetic must be true or false")
    if "as_of" in meta:
        _date(meta["as_of"], "meta.as_of")
    if "holidays" in meta:
        if not isinstance(meta["holidays"], list):
            raise ScenarioError("Scenario meta.holidays must be an array")
        for day in meta["holidays"]:
            _date(day, "meta.holidays")
    for key in COLLECTIONS:
        if not isinstance(data.get(key), list):
            raise ScenarioError(f"Scenario data.{key} must be an array")
        if any(not isinstance(row, dict) for row in data[key]):
            raise ScenarioError(f"Every data.{key} record must be an object")
        if len(data[key]) > 3000:
            raise ScenarioError(f"Scenario data.{key} exceeds 3000 records")
    if (
        len(data["factories"]) < 1
        or len(data["lines"]) < 1
        or len(data["styles"]) < 1
        or len(data["orders"]) < 1
    ):
        raise ScenarioError("At least one factory, line, style, and order is required")
    ids = {}
    for key in ("factories", "lines", "styles", "orders", "incidents", "actions"):
        values = []
        for row in data[key]:
            if (
                not isinstance(row, dict)
                or not isinstance(row.get("id"), str)
                or not row["id"]
            ):
                raise ScenarioError(f"Every {key} record needs an id")
            values.append(row["id"])
        if len(values) != len(set(values)):
            raise ScenarioError(f"Duplicate id in {key}")
        ids[key] = set(values)
    for factory in data["factories"]:
        _fields(
            factory,
            ("name", "region", "quality", "reliability"),
            f"Factory {factory['id']}",
        )
        for key in (
            "daily_cut",
            "daily_finish",
            "daily_qc",
            "daily_pack",
            "cost",
            "logistics_days",
        ):
            if not _finite_number(factory.get(key)) or factory[key] < 0:
                raise ScenarioError(f"Factory {factory['id']} has invalid {key}")
        if any(
            not isinstance(factory[key], int) or isinstance(factory[key], bool)
            for key in (
                "daily_cut",
                "daily_finish",
                "daily_qc",
                "daily_pack",
                "logistics_days",
            )
        ):
            raise ScenarioError(
                f"Factory {factory['id']} stage capacities and logistics_days must be whole numbers"
            )
        if not isinstance(factory.get("compliance"), bool) or not isinstance(
            factory.get("capabilities"), list
        ):
            raise ScenarioError(
                f"Factory {factory['id']} needs compliance and capabilities"
            )
        if any(
            not _finite_number(factory[k]) or not 0 <= factory[k] <= 1
            for k in ("quality", "reliability")
        ):
            raise ScenarioError(
                f"Factory {factory['id']} quality and reliability must be 0–1"
            )
        for day in factory.get("shutdown_dates", []):
            _date(day, "factory shutdown_dates")
    for line in data["lines"]:
        _fields(line, ("name",), f"Line {line['id']}")
        if line.get("factory_id") not in ids["factories"]:
            raise ScenarioError(f"Line {line['id']} references an unknown factory")
        if (
            not isinstance(line.get("operators"), int)
            or isinstance(line.get("operators"), bool)
            or line["operators"] < 1
            or not _finite_number(line.get("efficiency"))
            or not 0 < line["efficiency"] <= 1
        ):
            raise ScenarioError(
                f"Line {line['id']} has invalid operators or efficiency"
            )
        if (
            not isinstance(line.get("skills"), list)
            or not isinstance(line.get("machines"), list)
            or not isinstance(line.get("maintenance"), list)
        ):
            raise ScenarioError(
                f"Line {line['id']} needs skills, machines, and maintenance arrays"
            )
        for day in line["maintenance"]:
            _date(day, "line maintenance")
    for style in data["styles"]:
        _fields(
            style, ("name", "category", "bottleneck", "machine"), f"Style {style['id']}"
        )
        if any(
            not isinstance(style[key], str) or not style[key].strip()
            for key in ("name", "category", "bottleneck", "machine")
        ):
            raise ScenarioError(
                f"Style {style['id']} needs nonempty name, category, bottleneck, and machine"
            )
        if (
            not _finite_number(style.get("smv"))
            or style["smv"] <= 0
            or not isinstance(style.get("operations"), list)
        ):
            raise ScenarioError(
                f"Style {style['id']} needs positive SMV and operations"
            )
        if not all(
            isinstance(op, (list, tuple))
            and len(op) == 2
            and isinstance(op[0], str)
            and _finite_number(op[1])
            and op[1] >= 0
            for op in style["operations"]
        ):
            raise ScenarioError(
                f"Style {style['id']} has an invalid operation sequence"
            )
    for order in data["orders"]:
        _fields(
            order,
            (
                "customer",
                "target_cost",
                "priority",
                "margin_per_unit",
                "min_lot",
                "quality_release",
                "status",
            ),
            f"Order {order['id']}",
        )
        if (
            order.get("factory_id") not in ids["factories"]
            or order.get("line_id") not in ids["lines"]
            or order.get("style_id") not in ids["styles"]
        ):
            raise ScenarioError(
                f"Order {order['id']} has an unknown factory, line, or style"
            )
        line = next(x for x in data["lines"] if x["id"] == order["line_id"])
        if line["factory_id"] != order["factory_id"]:
            raise ScenarioError(f"Order {order['id']} line belongs to another factory")
        if (
            not isinstance(order.get("quantity"), int)
            or isinstance(order["quantity"], bool)
            or not 1 <= order["quantity"] <= 10_000_000
        ):
            raise ScenarioError(f"Order {order['id']} has invalid quantity")
        if (
            not isinstance(order["quality_release"], bool)
            or not isinstance(order["priority"], int)
            or isinstance(order["priority"], bool)
            or not 1 <= order["priority"] <= 5
            or not isinstance(order["min_lot"], int)
            or isinstance(order["min_lot"], bool)
            or order["min_lot"] < 1
        ):
            raise ScenarioError(
                f"Order {order['id']} has invalid release, priority, or minimum lot"
            )
        if order["status"] != "active":
            raise ScenarioError(
                f"Order {order['id']} must be active; remove completed or cancelled orders from the planning file"
            )
        if (
            not _finite_number(order["target_cost"])
            or order["target_cost"] < 0
            or not _finite_number(order["margin_per_unit"])
            or order["margin_per_unit"] < 0
        ):
            raise ScenarioError(f"Order {order['id']} has invalid cost or margin")
        _date(order.get("due_date"), "order due_date")
        _date(order.get("material_date"), "order material_date")
    for material in data["materials"]:
        _fields(material, ("shortage_units",), "Material record")
        if material.get("order_id") not in ids["orders"]:
            raise ScenarioError("Material references an unknown order")
        if (
            not isinstance(material["shortage_units"], int)
            or isinstance(material["shortage_units"], bool)
            or material["shortage_units"] < 0
        ):
            raise ScenarioError(
                "Material shortage_units must be a nonnegative whole number"
            )
        _date(material.get("fabric_ready"), "material fabric_ready")
        _date(material.get("trims_ready"), "material trims_ready")
    material_orders = [material["order_id"] for material in data["materials"]]
    if (
        len(material_orders) != len(ids["orders"])
        or set(material_orders) != ids["orders"]
    ):
        raise ScenarioError("Each order needs exactly one material record")
    for row in data["production"]:
        _fields(
            row,
            ("line_id", "target", "actual", "first_pass", "rework", "date"),
            "Production record",
        )
        if row["line_id"] not in ids["lines"]:
            raise ScenarioError("Production references an unknown line")
        _date(row["date"], "production date")
        if (
            any(
                not _finite_number(row[k]) or row[k] < 0
                for k in ("target", "actual", "first_pass", "rework")
            )
            or row["first_pass"] + row["rework"] > row["actual"]
        ):
            raise ScenarioError("Production has invalid quantity values")
    for row in data["downtime"]:
        _fields(
            row,
            ("line_id", "date", "machine", "cause", "minutes", "shift"),
            "Downtime record",
        )
        if row["line_id"] not in ids["lines"]:
            raise ScenarioError("Downtime references an unknown line")
        _date(row["date"], "downtime date")
        if not _finite_number(row["minutes"]) or row["minutes"] < 0:
            raise ScenarioError("Downtime minutes must be nonnegative")
    for row in data["quality_holds"]:
        _fields(row, ("order_id", "date", "hours", "cause", "status"), "Quality hold")
        if row["order_id"] not in ids["orders"]:
            raise ScenarioError("Quality hold references an unknown order")
        _date(row["date"], "quality hold date")
        if not _finite_number(row["hours"]) or row["hours"] < 0:
            raise ScenarioError("Quality hold hours must be nonnegative")
        if row["status"] not in ("open", "closed"):
            raise ScenarioError("Quality hold status must be open or closed")
    for row in data["labor"]:
        _fields(row, ("line_id", "date", "scheduled", "present"), "Labor record")
        if row["line_id"] not in ids["lines"]:
            raise ScenarioError("Labor references an unknown line")
        _date(row["date"], "labor date")
        if (
            not isinstance(row["scheduled"], int)
            or isinstance(row["scheduled"], bool)
            or row["scheduled"] < 1
            or not isinstance(row["present"], int)
            or isinstance(row["present"], bool)
            or not 0 <= row["present"] <= row["scheduled"]
        ):
            raise ScenarioError("Labor has invalid scheduled or present count")
    for incident in data["incidents"]:
        _fields(
            incident,
            (
                "factory_id",
                "type",
                "title",
                "detected_at",
                "severity",
                "status",
                "lost_minutes",
                "immediate_cause",
                "verified_root_cause",
                "evidence",
                "verification",
                "owner",
            ),
            f"Incident {incident['id']}",
        )
        if (
            incident.get("order_id") not in ids["orders"]
            or incident.get("line_id") not in ids["lines"]
        ):
            raise ScenarioError(
                f"Incident {incident['id']} has an unknown order or line"
            )
        if incident["factory_id"] not in ids["factories"]:
            raise ScenarioError(f"Incident {incident['id']} has an unknown factory")
        if incident["line_id"] not in {
            line["id"]
            for line in data["lines"]
            if line["factory_id"] == incident["factory_id"]
        }:
            raise ScenarioError(
                f"Incident {incident['id']} line belongs to another factory"
            )
        if incident["lost_minutes"] is not None and (
            not isinstance(incident["lost_minutes"], (int, float))
            or isinstance(incident["lost_minutes"], bool)
            or not isfinite(incident["lost_minutes"])
            or incident["lost_minutes"] < 0
        ):
            raise ScenarioError(f"Incident {incident['id']} has invalid lost_minutes")
        if incident["status"] not in ("open", "investigating", "closed", "resolved"):
            raise ScenarioError(f"Incident {incident['id']} has invalid status")
        if incident["verified_root_cause"] is not None and not isinstance(
            incident["verified_root_cause"], str
        ):
            raise ScenarioError(
                f"Incident {incident['id']} has invalid verified_root_cause"
            )
        if incident["verified_root_cause"] and (
            not isinstance(incident["evidence"], str)
            or not incident["evidence"].strip()
            or not isinstance(incident["verification"], str)
            or not incident["verification"].strip()
        ):
            raise ScenarioError(
                f"Incident {incident['id']} needs evidence and verification to label a root cause verified"
            )
        _date(incident["detected_at"], "incident detected_at")
    for action in data["actions"]:
        _fields(
            action,
            (
                "title",
                "owner",
                "accountable",
                "consulted",
                "informed",
                "status",
                "dependency",
                "evidence",
            ),
            f"Action {action['id']}",
        )
        if action.get("incident_id") not in ids["incidents"]:
            raise ScenarioError(f"Action {action['id']} references an unknown incident")
        _date(action.get("due_date"), "action due_date")
        if action["dependency"] and action["dependency"] not in ids["actions"]:
            raise ScenarioError(f"Action {action['id']} has an unknown dependency")
        if action["status"] not in ("open", "in_progress", "done", "blocked"):
            raise ScenarioError(f"Action {action['id']} has invalid status")
    dependencies = {action["id"]: action["dependency"] for action in data["actions"]}
    for action_id in dependencies:
        seen = set()
        current = action_id
        while current:
            if current in seen:
                raise ScenarioError(f"Action dependency cycle includes {current}")
            seen.add(current)
            current = dependencies.get(current)
    return document


def load_file(path):
    if path.stat().st_size > MAX_BYTES:
        raise ScenarioError("Scenario file exceeds 3 MB")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ScenarioError("Scenario file is not valid UTF-8 JSON") from None
    return validate_document(doc)


def builtins():
    result = []
    for path in sorted(SCENARIO_DIR.glob("*.json")):
        doc = load_file(path)
        result.append(dict(**doc["meta"], filename=path.name, builtin=True))
    return result


def builtin_document(scenario_id):
    for path in SCENARIO_DIR.glob("*.json"):
        doc = load_file(path)
        if doc["meta"]["id"] == scenario_id:
            return doc
    return None
