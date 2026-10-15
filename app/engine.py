"""Explainable daily-capacity planning and recovery calculations."""
from collections import defaultdict
from datetime import date, timedelta
from math import erf, sqrt
from .seed import AS_OF


def as_of(data):
    return date.fromisoformat(data.get("_meta",{}).get("as_of",AS_OF.isoformat()))


def workday(d, data=None):
    holidays=set((data or {}).get("_meta",{}).get("holidays",[]))
    return d.weekday() != 6 and d.isoformat() not in holidays


def next_workday(d, data=None):
    while not workday(d,data):
        d += timedelta(days=1)
    return d


def add_workdays(d, days, data=None):
    for _ in range(days):
        d = next_workday(d + timedelta(days=1),data)
    return d


def lookup(rows, key):
    return {row["id"]: row for row in rows}[key]


def allocation_check(order, line, data, quantity=None):
    style = lookup(data["styles"], order["style_id"])
    factory = lookup(data["factories"], line["factory_id"])
    reasons = []
    qty = quantity or order["quantity"]
    if not factory["compliance"]:
        reasons.append("Factory compliance hold")
    if any(factory[key]<=0 for key in ("daily_cut","daily_finish","daily_qc","daily_pack")):
        reasons.append("Factory has no capacity in a required production stage")
    if style["category"] not in factory["capabilities"]:
        reasons.append("Factory does not support this product category")
    if style["category"] not in line["skills"]:
        reasons.append("Line lacks the required operator skill")
    if style["machine"] not in line["machines"]:
        reasons.append(f"Required {style['machine']} machine unavailable")
    if qty < order["min_lot"]:
        reasons.append(f"Below {order['min_lot']}-unit minimum lot")
    material=next((m for m in data["materials"] if m["order_id"]==order["id"]),None)
    if material and material["shortage_units"]>0:
        reasons.append(f"Material shortage: {material['shortage_units']} units have no confirmed replenishment date")
    if not order["quality_release"]:
        reasons.append("Quality release pending with no confirmed release date")
    if any(h["order_id"]==order["id"] and h["status"]=="open" for h in data["quality_holds"]):
        reasons.append("Open quality hold has no confirmed release date")
    return reasons


def line_minutes(line, day, data, overtime=0, repaired=False):
    factory=lookup(data["factories"],line["factory_id"])
    if not workday(day,data):
        return 0
    if day.isoformat() in factory.get("shutdown_dates",[]):
        return 0
    if day.isoformat() in line["maintenance"]:
        return 0
    historical = [r for r in data["labor"] if r["line_id"] == line["id"] and r["date"] <= as_of(data).isoformat()]
    attendance = sum(r["present"] / r["scheduled"] for r in historical) / len(historical) if historical else .94
    minutes = 480 * (1 + overtime) * line["operators"] * line["efficiency"] * attendance
    # Use this file's downtime history; a repaired option removes the observed loss.
    if not repaired:
        events=[r for r in data["downtime"] if r["line_id"]==line["id"] and r["date"] <= as_of(data).isoformat()]
        production_days=len({r["date"] for r in data["production"] if r["line_id"]==line["id"] and r["date"] <= as_of(data).isoformat()})
        loss=min(.35,sum(r["minutes"] for r in events)/max(1,production_days*480))
        minutes *= 1-loss
    return max(0, minutes)


def line_capacity(line, style, day, data, overtime=0, repaired=False):
    return int(line_minutes(line, day, data, overtime, repaired) / style["smv"])


def reserve_factory_stage(factory, stage, quantity, first_day, used, data):
    """Reserve pooled factory units by workday; return start and completion."""
    capacity=factory[f"daily_{stage}"]
    remaining=quantity
    day=next_workday(first_day,data)
    first=None
    last=None
    limit=as_of(data)+timedelta(days=120)
    while remaining>0 and day<=limit:
        if workday(day,data) and day.isoformat() not in factory.get("shutdown_dates",[]):
            available=max(0,capacity-used[(factory["id"],day,stage)])
            made=min(remaining,available)
            if made:
                first=first or day
                last=day
                used[(factory["id"],day,stage)]+=made
                remaining-=made
        day+=timedelta(days=1)
    return (first,last) if remaining==0 else (None,None)


def _schedule_one(order, line, data, line_used, factory_used, quantity=None, overtime=0, repaired=False, expedite_freight=False, subcontract=False, not_before=None):
    # Keep reservations tentative until every production stage can be scheduled.
    # A blocked order must not consume capacity needed by subsequent orders.
    line_pending=defaultdict(int,line_used)
    factory_pending=defaultdict(int,factory_used)
    quantity = quantity or order["quantity"]
    style = lookup(data["styles"], order["style_id"])
    factory = lookup(data["factories"], line["factory_id"])
    material = next((m for m in data["materials"] if m["order_id"] == order["id"]), None)
    if any(h["order_id"]==order["id"] and h["status"]=="open" for h in data["quality_holds"]):
        return dict(feasible=False,reason="Open quality hold has no confirmed release date")
    today=as_of(data)
    material_day = max(date.fromisoformat(order["material_date"]), date.fromisoformat(material["fabric_ready"]) if material else today, date.fromisoformat(material["trims_ready"]) if material else today)
    material_release = next_workday(max(today, material_day, date.fromisoformat(not_before) if not_before else today),data)
    start,cut_complete=reserve_factory_stage(factory,"cut",quantity,material_release,factory_pending,data)
    if not cut_complete:
        return dict(feasible=False,reason="Insufficient cutting capacity within 120-day planning horizon")
    daily = []
    remaining = quantity
    day = next_workday(cut_complete+timedelta(days=1),data)
    while remaining > 0 and day <= today + timedelta(days=120):
        if workday(day,data):
            minutes = line_minutes(line, day, data, overtime, repaired)
            cap = int(minutes / style["smv"])
            available_minutes = max(0, minutes - line_pending[(line["id"], day)] - (minutes * .12 if not daily else 0))
            in_house = int(available_minutes / style["smv"])
            available = in_house
            if subcontract:
                available += int(cap * .35)
            made = min(remaining, available)
            if made:
                first_sewing_day = not daily
                daily.append(dict(date=day.isoformat(), units=made, capacity=cap+(int(cap*.35) if subcontract else 0)))
                in_house_made = min(made, in_house)
                line_pending[(line["id"], day)] += in_house_made * style["smv"] + (minutes * .12 if first_sewing_day and in_house_made else 0)
                remaining -= made
        day += timedelta(days=1)
    if remaining:
        return dict(feasible=False, reason="No capacity within 120-day planning horizon")
    last_sewing = date.fromisoformat(daily[-1]["date"])
    _,finishing=reserve_factory_stage(factory,"finish",quantity,next_workday(last_sewing+timedelta(days=1),data),factory_pending,data)
    if not finishing:
        return dict(feasible=False,reason="Insufficient finishing capacity within 120-day planning horizon")
    quality_start=add_workdays(finishing,1,data)
    _,inspection=reserve_factory_stage(factory,"qc",quantity,quality_start,factory_pending,data)
    if not inspection:
        return dict(feasible=False,reason="Insufficient inspection capacity within 120-day planning horizon")
    _,packing=reserve_factory_stage(factory,"pack",quantity,next_workday(inspection+timedelta(days=1),data),factory_pending,data)
    if not packing:
        return dict(feasible=False,reason="Insufficient packing capacity within 120-day planning horizon")
    ship = packing + timedelta(days=1 if expedite_freight else factory["logistics_days"])
    due = date.fromisoformat(order["due_date"])
    line_used.update(line_pending)
    factory_used.update(factory_pending)
    return dict(feasible=True, factory_id=factory["id"], line_id=line["id"], start=start.isoformat(),cut_complete=cut_complete.isoformat(), sewing_complete=last_sewing.isoformat(), finishing=finishing.isoformat(), inspection=inspection.isoformat(), packing=packing.isoformat(), expected_ship=ship.isoformat(), due_date=due.isoformat(), delay_days=max(0, (ship-due).days), daily=daily, quantity=quantity, capacity_utilization=round(sum(x["units"] for x in daily)/max(1,sum(x["capacity"] for x in daily)),2), bottleneck=style["bottleneck"])


def schedule_all(data, overrides=None, sequence="priority"):
    overrides = data.get("active_overrides",{}) if overrides is None else overrides
    line_used = defaultdict(int)
    factory_used = defaultdict(int)
    results = {}
    ordering={
        "priority":lambda o:(-o["priority"],o["due_date"],o["id"]),
        "fcfs":lambda o:o["id"],
        "edd":lambda o:(o["due_date"],o["id"]),
    }
    orders = sorted(data["orders"], key=ordering.get(sequence,ordering["priority"]))
    for order in orders:
        config = overrides.get(order["id"], {})
        line_id = config.get("line_id", order["line_id"])
        line = lookup(data["lines"], line_id)
        if allocation_check(order, line, data):
            results[order["id"]] = dict(feasible=False, reason="; ".join(allocation_check(order,line,data)))
            continue
        results[order["id"]] = _schedule_one(order, line, data, line_used, factory_used, overtime=config.get("overtime",0), repaired=config.get("repaired",False), expedite_freight=config.get("expedite_freight",False), subcontract=config.get("subcontract",False), not_before=config.get("not_before"))
    return results


def allocation_candidates(order, data):
    baseline = schedule_all(data)
    out = []
    for line in data["lines"]:
        reasons = allocation_check(order, line, data)
        factory = lookup(data["factories"], line["factory_id"])
        if reasons:
            out.append(dict(line_id=line["id"], factory_id=factory["id"], feasible=False, reasons=reasons))
            continue
        trial_all=schedule_all(data,{**data.get("active_overrides",{}),order["id"]:dict(line_id=line["id"])})
        trial=trial_all[order["id"]]
        if not trial.get("feasible"):
            out.append(dict(line_id=line["id"],factory_id=factory["id"],feasible=False,reasons=[trial.get("reason","No capacity within the planning horizon")]))
            continue
        score = factory["cost"] + (1-factory["quality"])*20 + (1-factory["reliability"])*12 + trial["delay_days"]*3
        out.append(dict(line_id=line["id"], factory_id=factory["id"], feasible=True, reasons=[], expected_ship=trial["expected_ship"], delay_days=trial["delay_days"], score=round(score,2), changeover_hours=round(480*.12/60,1), displaced_orders=sum(1 for oid, row in baseline.items() if oid != order["id"] and row.get("feasible") and (not trial_all[oid].get("feasible") or trial_all[oid]["expected_ship"]>row["expected_ship"]))))
    return sorted(out, key=lambda x: (not x["feasible"], x.get("score",999), x["line_id"]))


def normal_cdf(x):
    return .5 * (1 + erf(x/sqrt(2)))


def _financial(order, plan, factory, extra, quality_delta=0, shifted=0):
    due = date.fromisoformat(order["due_date"])
    ship = date.fromisoformat(plan["expected_ship"])
    mean_late = (ship-due).days
    # Explicit illustrative uncertainty: 1.8-day standard deviation.
    # A shipment dated on the deadline is within the deadline-day interval.
    on_time = normal_cdf((.5 - mean_late)/1.8)
    penalty = order["quantity"] * 1.15 * (1-on_time)
    margin = order["quantity"] * order["margin_per_unit"] * .18 * (1-on_time)
    quality_risk = min(1,max(0,1-factory["quality"]+quality_delta))
    quality_loss = order["quantity"] * quality_risk * 3.2
    components=[round(x,0) for x in (extra,penalty,margin,quality_loss,shifted)]
    return dict(additional_cost=components[0], expected_late_penalty=components[1], expected_margin_exposure=components[2], expected_quality_cost=components[3], other_order_cost=components[4], expected_total_impact=sum(components), on_time_probability=round(on_time,2), quality_risk=round(quality_risk,3))


def recovery_options(incident, data):
    today=as_of(data)
    order = lookup(data["orders"], incident["order_id"])
    baseline = schedule_all(data)
    current = baseline[order["id"]]
    current_line=current.get("line_id",data.get("active_overrides",{}).get(order["id"],{}).get("line_id",order["line_id"]))
    current_factory=lookup(data["factories"],lookup(data["lines"],current_line)["factory_id"])
    def option(key, name, detail, override, extra, lead, labor, commitment, quality_delta=0, compliance="within policy"):
        trial_all = schedule_all(data, {**data.get("active_overrides",{}),order["id"]:override})
        plan = trial_all[order["id"]]
        if not plan.get("feasible"):
            return dict(id=key,name=name,detail=detail,feasible=False,reasons=[plan.get("reason","No feasible schedule")])
        shifted_orders = [oid for oid, p in trial_all.items() if oid != order["id"] and baseline[oid].get("feasible") and (not p.get("feasible") or p["expected_ship"]>baseline[oid]["expected_ship"])]
        shifted = sum(lookup(data["orders"],oid)["quantity"]*(1.15+lookup(data["orders"],oid)["margin_per_unit"]*.18 if not trial_all[oid].get("feasible") else .35) for oid in shifted_orders)
        factory = lookup(data["factories"], plan["factory_id"])
        return dict(id=key, name=name, detail=detail, feasible=True, line_id=plan["line_id"], not_before=override.get("not_before"), expected_ship=plan["expected_ship"], delay_days=plan["delay_days"], implementation_days=lead, labor=labor, factory_commitment=commitment, compliance=compliance, affected_other_orders=shifted_orders, capacity_requirement=f"{order['quantity']} units on {plan['line_id']}", forecast_range=f"{(date.fromisoformat(plan['expected_ship'])-timedelta(days=2)).isoformat()} to {(date.fromisoformat(plan['expected_ship'])+timedelta(days=2)).isoformat()}", **_financial(order,plan,factory,extra,quality_delta,shifted))
    options = [dict(id="baseline", name="Current plan", detail="Continue on the current assignment", feasible=True, line_id=current["line_id"], expected_ship=current["expected_ship"], delay_days=current["delay_days"], implementation_days=0, labor="existing shift", factory_commitment="Existing plan", compliance="within policy", affected_other_orders=[], capacity_requirement=f"{order['quantity']} units on {current['line_id']}", forecast_range=f"±2 days around {current['expected_ship']}", **_financial(order,current,current_factory,0))] if current.get("feasible") else [dict(id="baseline",name="Current plan",detail="Current assignment cannot be scheduled",feasible=False,reasons=[current.get("reason","No feasible schedule")])]
    observed_downtime=any(event["line_id"]==current_line for event in data["downtime"])
    options.append(option("maintenance_overtime","Repair + controlled overtime" if observed_downtime else "Controlled overtime","Verify preventive maintenance, then add up to 20% daily hours" if observed_downtime else "Add up to 20% daily hours on the assigned line",dict(line_id=current_line,repaired=observed_downtime,overtime=.20,not_before=(today+timedelta(days=1)).isoformat()),order["quantity"]*.62+350,1,"20% extra hours; supervisor approval", "Maintenance release and overtime roster" if observed_downtime else "Approved overtime roster",.008))
    compatible = [line for line in data["lines"] if line["id"] != current_line and not allocation_check(order,line,data)]
    same = [line for line in compatible if line["factory_id"] == current_factory["id"]]
    other = [line for line in compatible if line["factory_id"] != current_factory["id"]]
    def best_transfer(lines, key, name, detail, days, extra, labor, commitment, quality_delta=0):
        trials=[option(key,name,detail,dict(line_id=line["id"],not_before=(today+timedelta(days=days)).isoformat()),extra,days,labor,commitment,quality_delta) for line in lines]
        feasible=[trial for trial in trials if trial["feasible"]]
        if feasible:
            return min(feasible,key=lambda trial:(trial["expected_total_impact"],trial["expected_ship"],trial["line_id"]))
        return dict(id=key,name=name,feasible=False,reasons=sorted({reason for trial in trials for reason in trial["reasons"]}) if trials else ["No compatible compliant spare line"])
    options.append(best_transfer(same,"same_factory_line","Move to another line","Transfer work to compatible line after changeover",2,order["quantity"]*.35+270,"Existing shift; retrain one cell","Line transfer and tooling sign-off"))
    options.append(best_transfer(other,"cross_factory","Reallocate to partner factory","Move production and materials to a compatible partner",3,order["quantity"]*1.05+850,"Receiving factory shift","Partner accepts capacity and material transfer",.012))
    options.append(option("subcontract","Subcontract bottleneck operation","Approved local subcontractor adds 35% sewing capacity",dict(line_id=current_line,subcontract=True,not_before=(today+timedelta(days=2)).isoformat()),order["quantity"]*1.4+500,2,"External approved operators", "Quality and compliance approval",.025,"Requires subcontractor compliance approval"))
    options.append(option("expedite_freight","Expedite finished goods","Protect transit time after production; does not repair bottleneck",dict(line_id=current_line,expedite_freight=True),order["quantity"]*.75+450,1,"No production change", "Logistics slot confirmation"))
    # Split shipment: half can depart after first production tranche, with a later balance.
    if current.get("feasible"):
        split = dict(options[0])
        split.update(id="split_shipment",name="Split shipment + negotiated date",detail="Ship first acceptable tranche; negotiate date for balance",additional_cost=round(order["quantity"]*.42+300,0),implementation_days=2,labor="Existing shift",factory_commitment="Written partial quantity and balance dates",compliance="Customer approval required",partial_on_time_probability=round(min(.95,split["on_time_probability"]+.23),2))
        split["expected_late_penalty"] = round(split["expected_late_penalty"]*.45,0)
        split["expected_margin_exposure"] = round(split["expected_margin_exposure"]*.45,0)
        split["expected_total_impact"] = round(split["additional_cost"] + split["expected_late_penalty"] + split["expected_margin_exposure"] + split["expected_quality_cost"],0)
        options.append(split)
    else:
        options.append(dict(id="split_shipment",name="Split shipment + negotiated date",feasible=False,reasons=["Production remains blocked on the current assignment"]))
    return sorted(options,key=lambda x:(not x["feasible"],x.get("expected_total_impact",10**9)))


def pareto(incident, data):
    if incident["type"] != "recurring_downtime":
        return []
    events = [e for e in data["downtime"] if e["line_id"] == incident["line_id"] and e["date"] <= as_of(data).isoformat()]
    minutes = defaultdict(int)
    for event in events:
        minutes[event["cause"]] += event["minutes"]
    total = sum(minutes.values()) or 1
    cumulative = 0
    rows = []
    for cause, value in sorted(minutes.items(),key=lambda x:-x[1]):
        cumulative += value
        rows.append(dict(cause=cause,minutes=value,share=round(value/total,3),cumulative=round(cumulative/total,3)))
    return rows


def benchmark(data):
    """Compare transparent dispatch rules on the selected orders."""
    methods=[("Priority-aware plan",{},"priority"),("First come, first served",{},"fcfs"),("Earliest due date",{},"edd")]
    low_cost={}; high_capacity={}
    for order in data["orders"]:
        compatible=[l for l in data["lines"] if not allocation_check(order,l,data)]
        if compatible:
            low_cost[order["id"]]={"line_id":min(compatible,key=lambda l:(lookup(data["factories"],l["factory_id"])["cost"],l["id"]))["id"]}
            style=lookup(data["styles"],order["style_id"])
            high_capacity[order["id"]]={"line_id":max(compatible,key=lambda l:line_capacity(l,style,as_of(data),data))["id"]}
    methods += [("Lowest-cost factory",low_cost,"fcfs"),("Highest available capacity",high_capacity,"fcfs")]
    results=[]
    for name,overrides,sequence in methods:
        plan=schedule_all(data,overrides,sequence)
        feasible=[o for o in data["orders"] if plan[o["id"]].get("feasible")]
        late=[o for o in feasible if plan[o["id"]]["delay_days"]>0]
        blocked=[o for o in data["orders"] if not plan[o["id"]].get("feasible")]
        operating=sum(o["quantity"]*(lookup(data["factories"],plan[o["id"]]["factory_id"])["cost"]+lookup(data["styles"],o["style_id"])["smv"]*.15) for o in feasible)
        exposure=sum(o["quantity"]*1.15 for o in late)+sum(o["quantity"]*(1.15+o["margin_per_unit"]*.18) for o in blocked)
        displacement=sum(overrides.get(o["id"],{}).get("line_id",o["line_id"])!=o["line_id"] for o in data["orders"])
        units=sum(o["quantity"] for o in feasible)
        available=sum(sum(x["capacity"] for x in plan[o["id"]]["daily"]) for o in feasible)
        results.append(dict(method=name,late_orders=len(late),forecast_otif=round((len(feasible)-len(late))/max(1,len(data["orders"])),3),estimated_cost=round(operating+exposure),plan_changes=displacement,capacity_utilization=round(units/max(1,available),2),constraint_violations=len(blocked),compute_note="Greedy daily dispatch; same selected scenario"))
    return results
