"""Deterministic, documented synthetic apparel-production scenario."""

from datetime import date, timedelta
import random
from copy import deepcopy

AS_OF = date(2026, 10, 14)

FACTORIES = [
    dict(
        id="F1",
        name="Dhaka Precision",
        region="Dhaka",
        daily_cut=2600,
        daily_finish=2250,
        daily_qc=2100,
        daily_pack=2300,
        cost=4.65,
        quality=0.965,
        reliability=0.91,
        logistics_days=2,
        compliance=True,
        capabilities=["knit", "woven", "denim"],
    ),
    dict(
        id="F2",
        name="Chattogram Apparel",
        region="Chattogram",
        daily_cut=2400,
        daily_finish=2000,
        daily_qc=1950,
        daily_pack=2100,
        cost=4.25,
        quality=0.948,
        reliability=0.84,
        logistics_days=3,
        compliance=True,
        capabilities=["knit", "woven"],
    ),
    dict(
        id="F3",
        name="Gazipur Works",
        region="Gazipur",
        daily_cut=1850,
        daily_finish=1750,
        daily_qc=1700,
        daily_pack=1800,
        cost=4.05,
        quality=0.928,
        reliability=0.78,
        logistics_days=2,
        compliance=True,
        capabilities=["knit", "denim"],
    ),
]

LINES = [
    dict(
        id="L1",
        factory_id="F1",
        name="DP-01",
        operators=38,
        efficiency=0.78,
        skills=["knit", "woven"],
        machines=["lockstitch", "overlock", "flatlock"],
        maintenance=[],
    ),
    dict(
        id="L2",
        factory_id="F1",
        name="DP-02",
        operators=34,
        efficiency=0.76,
        skills=["woven", "denim"],
        machines=["lockstitch", "overlock", "bartack"],
        maintenance=["2026-10-22"],
    ),
    dict(
        id="L3",
        factory_id="F1",
        name="DP-03",
        operators=32,
        efficiency=0.74,
        skills=["knit", "denim"],
        machines=["lockstitch", "overlock", "flatlock", "bartack"],
        maintenance=[],
    ),
    dict(
        id="L4",
        factory_id="F2",
        name="CA-01",
        operators=36,
        efficiency=0.76,
        skills=["knit", "woven"],
        machines=["lockstitch", "overlock", "flatlock"],
        maintenance=[],
    ),
    dict(
        id="L5",
        factory_id="F2",
        name="CA-02",
        operators=34,
        efficiency=0.73,
        skills=["woven"],
        machines=["lockstitch", "overlock", "bartack"],
        maintenance=["2026-10-26"],
    ),
    dict(
        id="L6",
        factory_id="F2",
        name="CA-03",
        operators=35,
        efficiency=0.72,
        skills=["knit"],
        machines=["lockstitch", "overlock", "flatlock"],
        maintenance=[],
    ),
    dict(
        id="L7",
        factory_id="F3",
        name="GW-01",
        operators=33,
        efficiency=0.71,
        skills=["knit", "denim"],
        machines=["lockstitch", "overlock", "flatlock", "bartack"],
        maintenance=[],
    ),
    dict(
        id="L8",
        factory_id="F3",
        name="GW-02",
        operators=31,
        efficiency=0.70,
        skills=["knit"],
        machines=["lockstitch", "overlock", "flatlock"],
        maintenance=[],
    ),
]

STYLES = [
    dict(
        id="S01",
        name="Essential Tee",
        category="knit",
        smv=12.4,
        bottleneck="Sleeve attach",
        machine="flatlock",
        operations=[
            ("Cutting", 2.1),
            ("Shoulder join", 2.2),
            ("Sleeve attach", 4.1),
            ("Side seam", 2.7),
            ("Finishing", 1.3),
        ],
    ),
    dict(
        id="S02",
        name="Polo Shirt",
        category="knit",
        smv=17.3,
        bottleneck="Collar attach",
        machine="flatlock",
        operations=[
            ("Cutting", 2.5),
            ("Placket", 3.6),
            ("Collar attach", 5.1),
            ("Side seam", 4.1),
            ("Finishing", 2.0),
        ],
    ),
    dict(
        id="S03",
        name="Oxford Shirt",
        category="woven",
        smv=22.5,
        bottleneck="Collar construction",
        machine="lockstitch",
        operations=[
            ("Cutting", 3.0),
            ("Front assembly", 4.5),
            ("Collar construction", 6.4),
            ("Sleeve set", 5.2),
            ("Finishing", 3.4),
        ],
    ),
    dict(
        id="S04",
        name="Chino Trouser",
        category="woven",
        smv=24.2,
        bottleneck="Waistband",
        machine="bartack",
        operations=[
            ("Cutting", 3.2),
            ("Pocket", 5.1),
            ("Inseam", 4.6),
            ("Waistband", 7.0),
            ("Finishing", 4.3),
        ],
    ),
    dict(
        id="S05",
        name="Denim Jean",
        category="denim",
        smv=29.1,
        bottleneck="Waistband",
        machine="bartack",
        operations=[
            ("Cutting", 3.8),
            ("Pocket", 6.1),
            ("Inseam", 5.4),
            ("Waistband", 8.2),
            ("Finishing", 5.6),
        ],
    ),
    dict(
        id="S06",
        name="Performance Tee",
        category="knit",
        smv=15.0,
        bottleneck="Flatlock seam",
        machine="flatlock",
        operations=[
            ("Cutting", 2.3),
            ("Shoulder join", 2.5),
            ("Flatlock seam", 5.2),
            ("Hem", 3.2),
            ("Finishing", 1.8),
        ],
    ),
    dict(
        id="S07",
        name="Woven Blouse",
        category="woven",
        smv=20.4,
        bottleneck="Sleeve set",
        machine="lockstitch",
        operations=[
            ("Cutting", 2.8),
            ("Front assembly", 4.4),
            ("Sleeve set", 6.1),
            ("Hem", 4.1),
            ("Finishing", 3.0),
        ],
    ),
    dict(
        id="S08",
        name="Knit Hoodie",
        category="knit",
        smv=26.0,
        bottleneck="Hood attach",
        machine="flatlock",
        operations=[
            ("Cutting", 3.3),
            ("Body assembly", 5.8),
            ("Hood attach", 8.0),
            ("Pocket", 5.1),
            ("Finishing", 3.8),
        ],
    ),
    dict(
        id="S09",
        name="Cargo Short",
        category="woven",
        smv=21.7,
        bottleneck="Pocket attach",
        machine="bartack",
        operations=[
            ("Cutting", 3.0),
            ("Pocket attach", 6.9),
            ("Inseam", 4.4),
            ("Waistband", 4.3),
            ("Finishing", 3.1),
        ],
    ),
    dict(
        id="S10",
        name="Denim Jacket",
        category="denim",
        smv=34.0,
        bottleneck="Sleeve set",
        machine="bartack",
        operations=[
            ("Cutting", 4.3),
            ("Front assembly", 7.4),
            ("Sleeve set", 9.3),
            ("Collar", 7.1),
            ("Finishing", 5.9),
        ],
    ),
]


def seed_data():
    rng = random.Random(57)
    orders = []
    materials = []
    for i in range(30):
        style = STYLES[i % len(STYLES)]
        factory = FACTORIES[(i * 2 + i // 4) % 3]
        compatible = [
            l
            for l in LINES
            if l["factory_id"] == factory["id"]
            and style["category"] in l["skills"]
            and style["machine"] in l["machines"]
        ]
        if not compatible:
            factory = next(
                f
                for f in FACTORIES
                if any(
                    l["factory_id"] == f["id"]
                    and style["category"] in l["skills"]
                    and style["machine"] in l["machines"]
                    for l in LINES
                )
            )
            compatible = [
                l
                for l in LINES
                if l["factory_id"] == factory["id"]
                and style["category"] in l["skills"]
                and style["machine"] in l["machines"]
            ]
        quantity = 520 + (i % 5) * 160 + rng.randint(0, 120)
        due = AS_OF + timedelta(days=10 + i % 16 + (i // 10) * 3)
        material_date = AS_OF + timedelta(days=(i * 3) % 8)
        if i in (6, 16, 23):
            material_date += timedelta(days=5)
        order = dict(
            id=f"PO-{2601+i:04d}",
            customer=["Northstar Retail", "Cedar & Co", "Harbor Outfitters"][i % 3],
            style_id=style["id"],
            factory_id=factory["id"],
            line_id=compatible[i % len(compatible)]["id"],
            quantity=quantity,
            due_date=due.isoformat(),
            material_date=material_date.isoformat(),
            target_cost=round(quantity * (factory["cost"] + style["smv"] * 0.15), 2),
            priority=3 if i in (4, 14, 24) else 2 if i % 4 == 0 else 1,
            margin_per_unit=round(2.4 + i % 6 * 0.45, 2),
            min_lot=200,
            quality_release=not (i in (9, 19)),
            status="active",
        )
        orders.append(order)
        materials.append(
            dict(
                order_id=order["id"],
                fabric_ready=material_date.isoformat(),
                trims_ready=(
                    material_date + timedelta(days=1 if i % 6 == 0 else 0)
                ).isoformat(),
                shortage_units=100 if i in (6, 16, 23) else 0,
            )
        )
    # The focal incident is intentionally late: a recurring flatlock failure on F3-L7.
    focal = orders[17]
    focal.update(
        factory_id="F3",
        line_id="L7",
        style_id="S08",
        quantity=1450,
        due_date="2026-10-23",
        material_date="2026-10-14",
        priority=3,
        target_cost=14200.0,
        margin_per_unit=4.9,
        quality_release=True,
    )
    materials[17].update(
        fabric_ready="2026-10-14", trims_ready="2026-10-14", shortage_units=0
    )

    production = []
    downtime = []
    quality_holds = []
    labor = []
    causes = [
        "Flatlock needle failure",
        "Sensor fault",
        "Thread jam",
        "Power interruption",
        "Changeover",
    ]
    for day_offset in range(-21, 1):
        day = AS_OF + timedelta(days=day_offset)
        if day.weekday() == 6:
            continue
        for line in LINES:
            absence = rng.choice([0, 1, 1, 2, 2, 3])
            if line["id"] == "L7" and day_offset % 5 == 0:
                absence = 5
            labor.append(
                dict(
                    date=day.isoformat(),
                    line_id=line["id"],
                    scheduled=line["operators"],
                    present=line["operators"] - absence,
                )
            )
            target = round(line["operators"] * 480 * line["efficiency"] / 20)
            loss = rng.randint(0, 16)
            if line["id"] == "L7":
                loss += 20
            actual = max(0, target - loss)
            production.append(
                dict(
                    date=day.isoformat(),
                    line_id=line["id"],
                    target=target,
                    actual=actual,
                    first_pass=round(actual * (0.95 if line["id"] == "L7" else 0.975)),
                    rework=round(actual * (0.05 if line["id"] == "L7" else 0.025)),
                )
            )
            if day_offset % 3 == 0:
                cause = (
                    "Flatlock needle failure"
                    if line["id"] == "L7"
                    else rng.choice(causes[1:])
                )
                downtime.append(
                    dict(
                        id=f"DT-{len(downtime)+1:03d}",
                        date=day.isoformat(),
                        line_id=line["id"],
                        machine="FL-07" if line["id"] == "L7" else "Generic station",
                        cause=cause,
                        minutes=95 if line["id"] == "L7" else rng.randint(12, 55),
                        shift="A",
                    )
                )
    for i in (9, 19):
        quality_holds.append(
            dict(
                id=f"QH-{i}",
                order_id=orders[i]["id"],
                date=AS_OF.isoformat(),
                hours=12,
                cause="Inspection release pending",
                status="open",
            )
        )
    quality_holds.append(
        dict(
            id="QH-17",
            order_id=focal["id"],
            date="2026-10-09",
            hours=5,
            cause="Seam strength retest",
            status="closed",
        )
    )
    incidents = [
        dict(
            id="INC-001",
            order_id=focal["id"],
            factory_id="F3",
            line_id="L7",
            type="recurring_downtime",
            title="Flatlock bottleneck repeatedly stops hoodie sewing",
            detected_at="2026-10-14",
            severity="critical",
            status="investigating",
            lost_minutes=665,
            immediate_cause="Needle breakage stops sleeve and hood seam operations",
            verified_root_cause="Preventive needle replacement interval was omitted from the maintenance standard",
            evidence="Seven FL-07 needle failures in 19 production days; service log has no scheduled needle replacement. A supervised inspection found wear beyond the supplier's run-hour threshold.",
            verification="Maintenance lead inspected service logs and reproduced wear at the specified run-hour threshold on 2026-10-12. Pilot outcome remains to be measured.",
            owner="Production manager",
        ),
        dict(
            id="INC-002",
            order_id=orders[6]["id"],
            factory_id=orders[6]["factory_id"],
            line_id=orders[6]["line_id"],
            type="material_delay",
            title="Fabric release moved five days",
            detected_at="2026-10-14",
            severity="high",
            status="open",
            lost_minutes=0,
            immediate_cause="Supplier missed confirmed fabric dispatch",
            verified_root_cause=None,
            evidence="Purchase order dispatch date missed; freight receipt unconfirmed.",
            verification=None,
            owner="Material coordinator",
        ),
        dict(
            id="INC-003",
            order_id=orders[9]["id"],
            factory_id=orders[9]["factory_id"],
            line_id=orders[9]["line_id"],
            type="quality_hold",
            title="Inspection release pending",
            detected_at="2026-10-14",
            severity="medium",
            status="open",
            lost_minutes=720,
            immediate_cause="Quality inspection hold",
            verified_root_cause=None,
            evidence="Batch sampling report pending.",
            verification=None,
            owner="Quality manager",
        ),
    ]
    actions = [
        dict(
            id="ACT-001",
            incident_id="INC-001",
            title="Replace worn needles and validate FL-07 output",
            owner="Maintenance lead",
            accountable="Factory general manager",
            consulted="Quality manager",
            informed="Production manager",
            due_date="2026-10-15",
            status="in_progress",
            dependency=None,
            evidence="",
        ),
        dict(
            id="ACT-002",
            incident_id="INC-001",
            title="Publish preventive replacement standard",
            owner="Maintenance lead",
            accountable="Factory general manager",
            consulted="Production manager",
            informed="Factory production planner",
            due_date="2026-10-17",
            status="open",
            dependency="ACT-001",
            evidence="",
        ),
        dict(
            id="ACT-003",
            incident_id="INC-001",
            title="Confirm recovery capacity and revised shipment",
            owner="Factory production planner",
            accountable="Production manager",
            consulted="Logistics coordinator",
            informed="Merchandising representative",
            due_date="2026-10-14",
            status="open",
            dependency="ACT-001",
            evidence="",
        ),
        dict(
            id="ACT-004",
            incident_id="INC-002",
            title="Obtain supplier dispatch evidence",
            owner="Material coordinator",
            accountable="Production manager",
            consulted="Merchandising representative",
            informed="Factory production planner",
            due_date="2026-10-15",
            status="open",
            dependency=None,
            evidence="",
        ),
    ]
    return dict(
        factories=deepcopy(FACTORIES),
        lines=deepcopy(LINES),
        styles=deepcopy(STYLES),
        orders=orders,
        materials=materials,
        production=production,
        downtime=downtime,
        quality_holds=quality_holds,
        labor=labor,
        incidents=incidents,
        actions=actions,
    )
