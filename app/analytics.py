"""Reconciled planning analytics. Forecasts and observations remain separate."""

from collections import defaultdict
from datetime import timedelta, date
from .engine import as_of, schedule_all, lookup, line_minutes, normal_cdf


def analyze(data):
    today = as_of(data)
    plans = schedule_all(data)
    portfolio = []
    reservations = defaultdict(
        lambda: dict(reserved=0, capacity=0, units=0, outsourced=0, orders=[])
    )
    stage_load = defaultdict(int)
    for o in data["orders"]:
        p = plans[o["id"]]
        f = lookup(data["factories"], p.get("factory_id", o["factory_id"]))
        style = lookup(data["styles"], o["style_id"])
        feasible = p["feasible"]
        slack = (
            (
                date.fromisoformat(o["due_date"])
                - date.fromisoformat(p["expected_ship"])
            ).days
            if feasible
            else None
        )
        probability = normal_cdf((slack + 0.5) / 1.8) if feasible else None
        manufacturing = (
            o["quantity"] * (f["cost"] + style["smv"] * 0.15) if feasible else None
        )
        exposure = (
            o["quantity"]
            * (1.15 + o["margin_per_unit"] * 0.18)
            * (1 - probability if feasible else 1)
        )
        portfolio.append(
            dict(
                id=o["id"],
                customer=o["customer"],
                quantity=o["quantity"],
                priority=o["priority"],
                factory_id=f["id"],
                line_id=p.get("line_id", o["line_id"]),
                due_date=o["due_date"],
                status=(
                    "blocked" if not feasible else "late" if slack < 0 else "on_time"
                ),
                slack_days=slack,
                on_time_probability=round(probability, 4) if feasible else None,
                expected_exposure=round(exposure, 2),
                manufacturing_cost=round(manufacturing, 2) if feasible else None,
                target_cost=o["target_cost"],
                cost_variance=(
                    round(manufacturing - o["target_cost"], 2) if feasible else None
                ),
                plan=p,
            )
        )
        if not feasible:
            continue
        for r in p["daily"]:
            cell = reservations[(p["line_id"], r["date"])]
            cell["reserved"] += r["reserved_minutes"]
            cell["capacity"] = max(cell["capacity"], r["available_minutes"])
            cell["units"] += r["units"]
            cell["outsourced"] += r["outsourced_units"]
            cell["orders"].append(o["id"])
        for r in p["stages"]:
            stage_load[(f["id"], r["date"], r["stage"])] += r["units"]
    days = [(today + timedelta(days=i)).isoformat() for i in range(42)]
    heatmap = []
    for line in data["lines"]:
        cells = []
        for day in days:
            cell = reservations.get(
                (line["id"], day),
                dict(reserved=0, capacity=0, units=0, outsourced=0, orders=[]),
            )
            capacity = max(
                cell["capacity"], line_minutes(line, date.fromisoformat(day), data)
            )
            cells.append(
                dict(
                    date=day,
                    capacity_minutes=round(capacity, 2),
                    reserved_minutes=round(cell["reserved"], 2),
                    utilization=(
                        round(cell["reserved"] / capacity, 4) if capacity else None
                    ),
                    units=cell["units"],
                    outsourced_units=cell["outsourced"],
                    orders=cell["orders"],
                )
            )
        heatmap.append(
            dict(
                id=line["id"],
                name=line["name"],
                factory_id=line["factory_id"],
                cells=cells,
            )
        )
    history = [r for r in data["production"] if r["date"] <= today.isoformat()]
    trends = []
    for day in sorted({r["date"] for r in history}):
        rows = [r for r in history if r["date"] == day]
        actual = sum(r["actual"] for r in rows)
        target = sum(r["target"] for r in rows)
        trends.append(
            dict(
                date=day,
                actual=actual,
                target=target,
                first_pass_yield=(
                    sum(r["first_pass"] for r in rows) / actual if actual else None
                ),
                rework_rate=sum(r["rework"] for r in rows) / actual if actual else None,
                adherence=actual / target if target else None,
            )
        )
    factories = []
    for f in data["factories"]:
        ids = {l["id"] for l in data["lines"] if l["factory_id"] == f["id"]}
        rows = [r for r in history if r["line_id"] in ids]
        output = sum(r["actual"] for r in rows)
        target = sum(r["target"] for r in rows)
        fp = sum(r["first_pass"] for r in rows)
        orders = [o for o in portfolio if o["factory_id"] == f["id"]]
        labor = [
            r
            for r in data["labor"]
            if r["line_id"] in ids and r["date"] <= today.isoformat()
        ]
        scheduled = sum(r["scheduled"] for r in labor)
        factories.append(
            dict(
                **f,
                orders=len(orders),
                units=sum(o["quantity"] for o in orders),
                blocked=sum(o["status"] == "blocked" for o in orders),
                late=sum(o["status"] == "late" for o in orders),
                forecast_otif=(
                    sum(o["status"] == "on_time" for o in orders) / len(orders)
                    if orders
                    else None
                ),
                first_pass_yield=fp / output if output else None,
                adherence=output / target if target else None,
                rework_rate=sum(r["rework"] for r in rows) / output if output else None,
                attendance=(
                    sum(r["present"] for r in labor) / scheduled if scheduled else None
                ),
                downtime_minutes=sum(
                    r["minutes"]
                    for r in data["downtime"]
                    if r["line_id"] in ids and r["date"] <= today.isoformat()
                ),
                expected_exposure=round(sum(o["expected_exposure"] for o in orders), 2)
            )
        )
    causes = defaultdict(float)
    for r in data["downtime"]:
        if r["date"] <= today.isoformat():
            causes[r["cause"]] += r["minutes"]
    total = sum(causes.values())
    cumulative = 0
    pareto = []
    for cause, minutes in sorted(causes.items(), key=lambda r: -r[1]):
        cumulative += minutes
        pareto.append(
            dict(
                cause=cause,
                minutes=minutes,
                share=minutes / total,
                cumulative=cumulative / total,
            )
        )
    bottlenecks = []
    for f in data["factories"]:
        for stage in ["cut", "finish", "qc", "pack"]:
            loads = [(day, stage_load[(f["id"], day, stage)]) for day in days]
            peak = max(loads, key=lambda r: r[1])
            cap = f["daily_" + stage]
            bottlenecks.append(
                dict(
                    factory_id=f["id"],
                    stage=stage,
                    capacity=cap,
                    peak_units=peak[1],
                    peak_date=peak[0],
                    peak_utilization=peak[1] / cap if cap else None,
                )
            )
    # Planned end-of-day stage balances; no claim of observed order-level WIP.
    flow = []
    for day in days:
        totals = dict(cut=0, sew=0, finish=0, qc=0, pack=0, shipped=0)
        for p in plans.values():
            if not p["feasible"]:
                continue
            totals["sew"] += sum(r["units"] for r in p["daily"] if r["date"] <= day)
            for r in p["stages"]:
                if r["date"] <= day:
                    totals[r["stage"]] += r["units"]
            if p["expected_ship"] <= day:
                totals["shipped"] += p["quantity"]
        flow.append(
            dict(
                date=day,
                cut_queue=totals["cut"] - totals["sew"],
                sew_queue=totals["sew"] - totals["finish"],
                finish_queue=totals["finish"] - totals["qc"],
                inspection_queue=totals["qc"] - totals["pack"],
                ready_to_ship=totals["pack"] - totals["shipped"],
                wip=totals["cut"] - totals["pack"],
                shipped=totals["shipped"],
            )
        )
    return dict(
        as_of=today.isoformat(),
        scenario=data["_meta"],
        flow=flow,
        portfolio=sorted(portfolio, key=lambda o: -o["expected_exposure"]),
        heatmap=heatmap,
        days=days,
        history=trends,
        factories=factories,
        pareto=pareto,
        stage_load=bottlenecks,
        totals=dict(
            orders=len(portfolio),
            units=sum(o["quantity"] for o in portfolio),
            blocked=sum(o["status"] == "blocked" for o in portfolio),
            late=sum(o["status"] == "late" for o in portfolio),
            on_time=sum(o["status"] == "on_time" for o in portfolio),
            expected_exposure=round(sum(o["expected_exposure"] for o in portfolio), 2),
            planned_manufacturing=round(
                sum(o["manufacturing_cost"] or 0 for o in portfolio), 2
            ),
        ),
        coverage={
            key: len(data[key])
            for key in [
                "factories",
                "lines",
                "styles",
                "orders",
                "materials",
                "production",
                "labor",
                "downtime",
                "quality_holds",
            ]
        },
        methodology=dict(
            exposure="Quantity × (USD 1.15 penalty + 18% of unit contribution margin) × modeled late probability. Blocked orders use 100% exposure. This is a scenario estimate, not booked loss.",
            capacity="Reserved in-house sewing SMV minutes plus changeover / available minutes, per line and date. External subcontract units are shown separately. Non-working days are unavailable.",
            uncertainty="Normal shipment-date uncertainty with an illustrative 1.8-day standard deviation and a deadline-day continuity correction; uncalibrated.",
            manufacturing="Quantity × (factory unit cost + style SMV × USD 0.15). Blocked orders are excluded from planned manufacturing totals.",
        ),
    )


def simulate_recovery(data, incident, options, sigma=1.8, draws=2000):
    """Common random draws support stable option comparisons, not calibrated confidence."""
    from random import Random
    from math import floor

    rng = Random(57)
    shocks = [rng.gauss(0, sigma) for _ in range(draws)]
    order = lookup(data["orders"], incident["order_id"])
    due = date.fromisoformat(order["due_date"])
    results = []

    def quantile(values, q):
        return sorted(values)[round((len(values) - 1) * q)]

    for option in options:
        if not option["feasible"]:
            continue
        expected = date.fromisoformat(option["expected_ship"])
        dates = []
        costs = []
        on_time = 0
        negotiated = 0.45 if option["id"] == "split_shipment" else 1
        for shock in shocks:
            arrival = max(as_of(data), expected + timedelta(days=floor(shock + 0.5)))
            late = arrival > due
            on_time += not late
            dates.append(arrival.toordinal())
            costs.append(
                option["additional_cost"]
                + option["expected_quality_cost"]
                + option["other_order_cost"]
                + (
                    order["quantity"]
                    * (1.15 + order["margin_per_unit"] * 0.18)
                    * negotiated
                    if late
                    else 0
                )
            )
        results.append(
            dict(
                id=option["id"],
                name=option["name"],
                on_time_probability=on_time / draws,
                ship_p10=date.fromordinal(quantile(dates, 0.1)).isoformat(),
                ship_p50=date.fromordinal(quantile(dates, 0.5)).isoformat(),
                ship_p90=date.fromordinal(quantile(dates, 0.9)).isoformat(),
                mean_cost=round(sum(costs) / draws, 2),
                cost_p10=round(quantile(costs, 0.1), 2),
                cost_p90=round(quantile(costs, 0.9), 2),
            )
        )
    return dict(
        draws=draws,
        seed=57,
        sigma_days=sigma,
        options=results,
        method="Common normal shipment-date shocks, rounded to calendar days. P10/P90 enclose 80% of modeled outcomes. Quality and displacement costs are held at expected values. Not calibrated to factory outcomes; sensitivity, not a service guarantee.",
    )
