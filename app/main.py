"""Production planning API and local management interface."""
from datetime import datetime, date, timedelta
from html import escape as html_escape
from io import StringIO
import csv
import json
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from . import store
from .scenarios import MAX_BYTES, ScenarioError
from .importers import import_file
from .engine import schedule_all, allocation_candidates, recovery_options, pareto, lookup, benchmark, as_of, line_minutes
from .seed import AS_OF, seed_data

app = FastAPI(title="PlantCore Production Planning", version="0.1.0")
WEB = Path(__file__).resolve().parents[1] / "web"


def now():
    return datetime.now().isoformat(timespec="seconds")


def scenario():
    d=store.data()
    d["_source_counts"]={key:len(d[key]) for key in ("production","downtime","quality_holds","labor","incidents","actions")}
    def add_uncovered_risks(plans):
        for order in d["orders"]:
            plan=plans[order["id"]]
            if (plan.get("feasible") and plan.get("delay_days",0)==0) or any(i["order_id"]==order["id"] for i in d["incidents"]): continue
            material=next(m for m in d["materials"] if m["order_id"]==order["id"])
            release=max(material["fabric_ready"],material["trims_ready"],order["material_date"])
            reason=plan.get("reason") if not plan.get("feasible") else f"Modeled packing completes {plan['packing']} and transit reaches shipment on {plan['expected_ship']}; the source file does not identify a verified disruption cause"
            incident_id=f"AUTO-{order['id']}"
            d["incidents"].append(dict(id=incident_id,order_id=order["id"],factory_id=plan.get("factory_id",order["factory_id"]),line_id=plan.get("line_id",order["line_id"]),type="forecast_risk",title=f"Forecast delivery risk: {order['id']}",detected_at=as_of(d).isoformat(),severity="high",status="open",lost_minutes=None,immediate_cause=reason,verified_root_cause=None,evidence=f"Derived from the imported order and modeled schedule. Material release: {release}; customer deadline: {order['due_date']}.",verification=None,owner="Production manager",source="derived"))
            d["actions"].append(dict(id=f"AUTO-ACT-{order['id']}",incident_id=incident_id,title=f"Confirm capacity and delivery commitment for {order['id']}",owner="Factory production planner",accountable="Production manager",consulted="Material and logistics coordinators",informed="Merchandising representative",due_date=(as_of(d)+timedelta(days=1)).isoformat(),status="open",dependency=None,evidence="Generated from forecast risk; owner to confirm the constraint and response."))
    add_uncovered_risks(schedule_all(d))
    updates={r["action_id"]:r for r in store.rows("SELECT * FROM scenario_action_updates WHERE scenario_id=?",(store.active_id(),))}
    for action in d["actions"]:
        if action["id"] in updates:
            action.update(status=updates[action["id"]]["status"],evidence=updates[action["id"]]["evidence"])
    decisions=store.rows("SELECT * FROM decisions WHERE scenario_id=? ORDER BY id",(store.active_id(),))
    overrides={}
    for decision in decisions:
        incident=next((x for x in d["incidents"] if x["id"]==decision["incident_id"]),None)
        if not incident: continue
        selected=next((x for x in json.loads(decision["alternatives"]) if x["id"]==decision["option_id"]),None)
        if not selected: continue
        option_id=decision["option_id"]
        if option_id in ("baseline","split_shipment") and incident["order_id"] in overrides:
            continue
        config={"line_id":selected.get("line_id",incident["line_id"])}
        if selected.get("not_before"): config["not_before"]=selected["not_before"]
        if option_id=="maintenance_overtime": config.update(repaired=True,overtime=.2)
        if option_id=="subcontract": config["subcontract"]=True
        if option_id=="expedite_freight": config["expedite_freight"]=True
        overrides[incident["order_id"]]=config
    d["active_overrides"]=overrides
    final_plans=schedule_all(d)
    add_uncovered_risks(final_plans)
    for incident in d["incidents"]:
        if incident.get("source") != "derived": continue
        plan=final_plans[incident["order_id"]]
        if plan.get("feasible") and plan.get("delay_days",0)==0:
            incident["status"]="resolved"
        else:
            incident["factory_id"]=plan.get("factory_id",incident["factory_id"])
            incident["line_id"]=plan.get("line_id",incident["line_id"])
            incident["immediate_cause"]=plan.get("reason") if not plan.get("feasible") else f"Modeled packing completes {plan['packing']} and transit reaches shipment on {plan['expected_ship']}; the source file does not identify a verified disruption cause"
    for action in d["actions"]:
        if action["id"] in updates:
            action.update(status=updates[action["id"]]["status"],evidence=updates[action["id"]]["evidence"])
    return d


@app.get("/api/scenarios")
def scenarios():
    return dict(active=store.active_id(),items=store.catalog())


class ScenarioSelect(BaseModel):
    id:str


@app.post("/api/scenarios/select")
def select_scenario(body:ScenarioSelect):
    try:
        meta=store.select_scenario(body.id)
    except KeyError:
        raise HTTPException(404,"Scenario not found") from None
    return dict(active=meta,orders=len(store.data()["orders"]))


@app.post("/api/scenarios/upload")
async def upload_scenario(request:Request,filename:str="scenario.json"):
    payload=await request.body()
    if len(payload)>MAX_BYTES:
        raise HTTPException(413,"Scenario file exceeds 3 MB")
    try:
        document=import_file(payload,filename)
    except ScenarioError as exc:
        raise HTTPException(400,str(exc)) from None
    uploaded_id="upload_"+uuid4().hex[:12]
    meta=store.save_upload(document,uploaded_id,now())
    return dict(active=meta,orders=len(document["data"]["orders"]),assumptions=meta.get("assumptions",[]))


@app.get("/api/scenarios/export")
def export_scenario():
    document=store.document()
    name=store.active_id()
    return Response(json.dumps(document,indent=2),media_type="application/json",headers={"Content-Disposition":f'attachment; filename="{name}.json"'})


@app.get("/")
def home():
    return FileResponse(WEB / "index.html")


@app.get("/app.css")
def css():
    return FileResponse(WEB / "app.css")


@app.get("/app.js")
def javascript():
    return FileResponse(WEB / "app.js")


@app.get("/sample-orders.csv")
def sample_orders():
    path=WEB.parent/"examples"/"sample-orders.csv"
    return FileResponse(path,media_type="text/csv",filename="sample-orders.csv")


@app.get("/api/definitions")
def definitions():
    return {
        "on_time_in_full":"Orders whose forecast shipment date is on/before the customer deadline and whose planned quantity equals ordered quantity / all active orders. Forecast, not actual OTIF.",
        "late_orders":"Active orders with forecast shipment after the customer deadline.",
        "first_pass_yield":"Acceptable units at first inspection / actual produced units in synthetic daily production records.",
        "schedule_adherence":"Actual output / planned output in historical synthetic daily production records.",
        "capacity_utilization":"Scheduled sewing units / available line capacity over days used by the order.",
        "recovery_cost":"Incremental operational spend plus expected late penalty, margin exposure, quality loss, and displacement of other orders; USD.",
        "on_time_probability":"Illustrative normal approximation with 1.8-day forecast standard deviation. Not calibrated against live outcomes.",
        "root_cause_recurrence":"Post-intervention events matching a verified cause / comparable production days, adjusted for volume and style complexity when data exists.",
        "data_note":"Built-in examples are synthetic. Uploaded order tables may use documented inferred values where columns are missing; historical KPIs are unavailable when historical records are absent. All forecasts remain illustrative."
    }


@app.get("/api/network")
def network():
    d=scenario()
    return {k:d[k] for k in ("factories","lines","styles","materials")}


@app.get("/api/validation")
def validation():
    return {"benchmarks":benchmark(scenario()),"note":"Dispatch-rule screening on the selected file. Costs include planned manufacturing, a simple late penalty, and penalty plus margin exposure for blocked orders; compare directionally, not as a calibrated business case."}


@app.get("/api/overview")
def overview(factory_id:str|None=None):
    d=scenario(); plans=schedule_all(d); today=as_of(d)
    if factory_id and factory_id not in {f["id"] for f in d["factories"]}:
        raise HTTPException(400,"Unknown factory filter")
    selected=[o for o in d["orders"] if not factory_id or plans[o["id"]].get("factory_id",o["factory_id"])==factory_id]
    at_risk=[o for o in selected if not plans[o["id"]].get("feasible") or plans[o["id"]].get("delay_days",0)>0]
    selected_lines={line["id"] for line in d["lines"] if not factory_id or line["factory_id"]==factory_id}
    production=[r for r in d["production"] if r["line_id"] in selected_lines and r["date"]<=today.isoformat()]
    produced=sum(r["actual"] for r in production)
    first_pass=sum(r["first_pass"] for r in production)
    target=sum(r["target"] for r in production)
    by_factory=[]
    for f in d["factories"]:
        factory_orders=[o for o in d["orders"] if plans[o["id"]].get("factory_id",o["factory_id"])==f["id"]]
        risk=sum(not plans[o["id"]].get("feasible") or plans[o["id"]].get("delay_days",0)>0 for o in factory_orders)
        factory_line_ids={line["id"] for line in d["lines"] if line["factory_id"]==f["id"]}
        actual=sum(r["actual"] for r in production if r["line_id"] in factory_line_ids)
        acceptable=sum(r["first_pass"] for r in production if r["line_id"] in factory_line_ids)
        by_factory.append(dict(**f,orders=len(factory_orders),late=risk,forecast_otif=round((len(factory_orders)-risk)/max(1,len(factory_orders)),3) if factory_orders else None,historical_first_pass_yield=round(acceptable/actual,3) if actual else None,cost_per_acceptable_unit=round(f["cost"]*actual/acceptable,2) if acceptable else None,open_incidents=sum(i["factory_id"]==f["id"] and i["status"] not in ("closed","resolved") for i in d["incidents"])))
    selected_incidents=[i for i in d["incidents"] if not factory_id or i["factory_id"]==factory_id]
    overdue=sum(a["status"]!="done" and a["due_date"]<today.isoformat() for a in d["actions"] if any(i["id"]==a["incident_id"] for i in selected_incidents))
    by_day=[]
    for day in sorted({r["date"] for r in production}):
        group=[r for r in production if r["date"]==day]
        by_day.append(dict(date=day,target=sum(r["target"] for r in group),actual=sum(r["actual"] for r in group)))
    line_load=[]
    for line in d["lines"]:
        if factory_id and line["factory_id"]!=factory_id: continue
        allocated=[o for o in selected if plans[o["id"]].get("feasible") and plans[o["id"]].get("line_id")==line["id"]]
        planned_units=sum(o["quantity"] for o in allocated)
        scheduled_minutes=sum(day["units"]*lookup(d["styles"],o["style_id"])["smv"] for o in allocated for day in plans[o["id"]]["daily"])
        used_dates={day["date"] for o in allocated for day in plans[o["id"]]["daily"]}
        offered_minutes=sum(line_minutes(line,date.fromisoformat(day),d) for day in used_dates)
        line_load.append(dict(line_id=line["id"],factory_id=line["factory_id"],units=planned_units,orders=len(allocated),at_risk=sum(plans[o["id"]].get("delay_days",0)>0 for o in allocated),utilization=round(scheduled_minutes/max(1,offered_minutes),2)))
    ranked=sorted(at_risk,key=lambda o:(plans[o["id"]].get("feasible",False),-o["priority"],o["due_date"]))
    focus=ranked[0]["id"] if ranked else "none"
    risk_timeline=[]
    for due_date in sorted({o["due_date"] for o in at_risk}):
        group=[o for o in at_risk if o["due_date"]==due_date]
        risk_timeline.append(dict(date=due_date,orders=len(group),units=sum(o["quantity"] for o in group)))
    meta=store.active_meta()
    material_by_order={m["order_id"]:m for m in d["materials"]}
    material_ready=sum(max(material_by_order[o["id"]]["fabric_ready"],material_by_order[o["id"]]["trims_ready"])<=today.isoformat() and material_by_order[o["id"]]["shortage_units"]==0 for o in selected if o["id"] in material_by_order)
    open_hold_orders={h["order_id"] for h in d["quality_holds"] if h["status"]=="open"}
    quality_pending=sum(not o["quality_release"] or o["id"] in open_hold_orders for o in selected)
    open_holds=sum(h["status"]=="open" and any(o["id"]==h["order_id"] for o in selected) for h in d["quality_holds"])
    selected_actions=[a for a in d["actions"] if any(i["id"]==a["incident_id"] for i in selected_incidents)]
    line_events=[e for e in d["downtime"] if e["line_id"] in selected_lines and e["date"]<=today.isoformat()]
    causes={cause:sum(e["minutes"] for e in line_events if e["cause"]==cause) for cause in {e["cause"] for e in line_events}}
    top_cause=max(causes,key=causes.get) if causes else None
    labor=[r for r in d["labor"] if r["line_id"] in selected_lines and r["date"]<=today.isoformat()]
    late_units=sum(o["quantity"] for o in at_risk)
    signals=dict(late_units=late_units,blocked_orders=sum(not plans[o["id"]].get("feasible") for o in selected),downtime_minutes=sum(e["minutes"] for e in line_events),top_downtime_cause=top_cause,absenteeism=round(1-sum(r["present"] for r in labor)/max(1,sum(r["scheduled"] for r in labor)),3) if labor else None,rework_units=sum(r["rework"] for r in production),historical_records=len(production),data_coverage=d["_source_counts"])
    comparison=None
    if meta.get("builtin") and meta["id"]!="baseline" and not factory_id:
        reference=seed_data(); reference["_meta"]=store.DEFAULT_META
        reference_plans=schedule_all(reference)
        reference_risk=[o for o in reference["orders"] if not reference_plans[o["id"]].get("feasible") or reference_plans[o["id"]].get("delay_days",0)>0]
        comparison=dict(reference="Original production network",at_risk_delta=len(at_risk)-len(reference_risk),exposed_units_delta=late_units-sum(o["quantity"] for o in reference_risk))
    priority_orders=[dict(**o,plan=plans[o["id"]],material_release_date=max(material_by_order[o["id"]]["fabric_ready"],material_by_order[o["id"]]["trims_ready"]),material_ready=max(material_by_order[o["id"]]["fabric_ready"],material_by_order[o["id"]]["trims_ready"])<=today.isoformat() and material_by_order[o["id"]]["shortage_units"]==0,material_shortage_units=material_by_order[o["id"]]["shortage_units"]) for o in ranked[:10]]
    return dict(as_of=today.isoformat(),scenario=meta,synthetic=meta["synthetic"],factory_filter=factory_id,comparison=comparison,kpis=dict(active_orders=len(selected),at_risk=len(at_risk),forecast_otif=round((len(selected)-len(at_risk))/max(1,len(selected)),3),first_pass_yield=round(first_pass/max(1,produced),3) if produced else None,schedule_adherence=round(produced/max(1,target),3) if target else None,open_incidents=len([x for x in selected_incidents if x["status"] not in ("closed","resolved")]),overdue_actions=overdue),signals=signals,readiness=dict(material_ready=material_ready,material_pending=len(selected)-material_ready,quality_pending=quality_pending,open_holds=open_holds),actions=[dict(id=a["id"],incident_id=a["incident_id"],title=a["title"],owner=a["owner"],due_date=a["due_date"],status=a["status"]) for a in selected_actions],factories=by_factory,line_load=line_load,risk_timeline=risk_timeline,trend=by_day[-14:],priority_orders=priority_orders,insight=f"{len(at_risk)} of {len(selected)} orders need intervention, representing {late_units:,} units. Review {focus} and its constraint or recovery plan.")


@app.get("/api/orders")
def orders():
    d=scenario(); plans=schedule_all(d); today=as_of(d)
    materials={m["order_id"]:m for m in d["materials"]}
    open_hold_orders={h["order_id"] for h in d["quality_holds"] if h["status"]=="open"}
    return [dict(**o,plan=plans[o["id"]],material_release_date=max(materials[o["id"]]["fabric_ready"],materials[o["id"]]["trims_ready"]),material_ready=max(materials[o["id"]]["fabric_ready"],materials[o["id"]]["trims_ready"])<=today.isoformat() and materials[o["id"]]["shortage_units"]==0,material_shortage_units=materials[o["id"]]["shortage_units"],quality_pending=not o["quality_release"] or o["id"] in open_hold_orders) for o in d["orders"]]


@app.get("/api/orders/{order_id}")
@app.get("/api/order")
def order_detail(order_id:str):
    d=scenario(); order=next((o for o in d["orders"] if o["id"]==order_id),None)
    if not order: raise HTTPException(404,"Order not found")
    style=lookup(d["styles"],order["style_id"])
    return dict(order=order,style=style,plan=schedule_all(d)[order_id],material=next(m for m in d["materials"] if m["order_id"]==order_id),quality_holds=[x for x in d["quality_holds"] if x["order_id"]==order_id],incidents=[x for x in d["incidents"] if x["order_id"]==order_id])


@app.get("/api/allocate/{order_id}")
@app.get("/api/allocation")
def allocate(order_id:str):
    d=scenario(); order=next((o for o in d["orders"] if o["id"]==order_id),None)
    if not order: raise HTTPException(404,"Order not found")
    return allocation_candidates(order,d)


@app.get("/api/incidents")
def incidents():
    d=scenario(); plans=schedule_all(d)
    rows=[]
    for incident in d["incidents"]:
        order=lookup(d["orders"],incident["order_id"])
        line=lookup(d["lines"],incident["line_id"])
        style=lookup(d["styles"],order["style_id"])
        factory=lookup(d["factories"],incident["factory_id"])
        lost=round(incident["lost_minutes"]*line["operators"]*line["efficiency"]/style["smv"]) if incident["lost_minutes"] is not None else None
        deadline=date.fromisoformat(order["due_date"])-timedelta(days=factory["logistics_days"]+3)
        rows.append(dict(**incident,order=order,impact=dict(expected_delay_days=plans[order["id"]].get("delay_days"),lost_capacity_units=lost,required_additional_capacity_units=max(0,lost) if lost is not None else None,recovery_deadline=deadline.isoformat(),commercial_exposure=round(order["quantity"]*order["margin_per_unit"]*.18,0),forecast_range="±2 days; illustrative" if plans[order["id"]].get("feasible") else "Unavailable until the blocking constraint is resolved")))
    return rows


@app.get("/api/incidents/{incident_id}")
@app.get("/api/incident")
def incident_detail(incident_id:str):
    d=scenario(); incident=next((i for i in d["incidents"] if i["id"]==incident_id),None)
    if not incident: raise HTTPException(404,"Incident not found")
    order=lookup(d["orders"],incident["order_id"])
    event_days=len({r["date"] for r in d["production"] if r["line_id"]==incident["line_id"] and r["date"]<=as_of(d).isoformat()})
    event_log=[x for x in d["downtime"] if x["line_id"]==incident["line_id"] and x["date"]<=as_of(d).isoformat()]
    ranked_causes=pareto(incident,d)
    top=ranked_causes[0]["cause"] if ranked_causes else None
    material=next(m for m in d["materials"] if m["order_id"]==order["id"])
    material_evidence=f"Recorded shortage: {material['shortage_units']} units; supplier cause unverified" if material["shortage_units"] else "Material contribution unverified"
    fishbone={"Machine":[f"Observed downtime: {top}" if top else "Machine evidence not supplied"],"Method":["Check operating and maintenance standard"],"Material":[material_evidence],"People":["Skill and attendance contribution unverified"],"Measurement":["Check event logs and output records"],"Environment":["Environmental contribution unverified"]}
    whys=[f"Why is this order at risk? {incident['title']}",f"What immediately disrupted it? {incident['immediate_cause']}"]
    whys.append(f"Verified root cause: {incident['verified_root_cause']}" if incident["verified_root_cause"] else "Further why steps require evidence before confirming a root cause.")
    sid=store.active_id()
    return dict(incident=incident,order=order,plan=schedule_all(d)[order["id"]],pareto=ranked_causes,downtime=event_log,fishbone=fishbone,whys=whys,cause_status="verified" if incident["verified_root_cause"] else "hypothesis only",recurrence=dict(events=len(event_log),observed_production_days=event_days),actions=[x for x in d["actions"] if x["incident_id"]==incident_id],decisions=store.rows("SELECT * FROM decisions WHERE scenario_id=? AND incident_id=? ORDER BY id DESC",(sid,incident_id)),commitments=store.rows("SELECT * FROM commitments WHERE scenario_id=? AND incident_id=? ORDER BY id DESC",(sid,incident_id)))


@app.get("/api/incidents/{incident_id}/options")
@app.get("/api/incident/options")
def options(incident_id:str):
    d=scenario(); incident=next((i for i in d["incidents"] if i["id"]==incident_id),None)
    if not incident: raise HTTPException(404,"Incident not found")
    return recovery_options(incident,d)


class DecisionIn(BaseModel):
    incident_id:str
    option_id:str
    rationale:str=Field(min_length=10)
    approver:str=Field(min_length=2)
    factory_owner:str=Field(min_length=2)
    commitment:str=Field(min_length=10)
    due_date:date


@app.post("/api/decisions")
def decide(body:DecisionIn):
    d=scenario(); incident=next((i for i in d["incidents"] if i["id"]==body.incident_id),None)
    if not incident: raise HTTPException(404,"Incident not found")
    if incident["status"] in ("closed","resolved"): raise HTTPException(400,"Closed or resolved incidents cannot receive new recovery decisions")
    opts=recovery_options(incident,d)
    selected=next((o for o in opts if o["id"]==body.option_id),None)
    if not selected or not selected["feasible"]: raise HTTPException(400,"Select a feasible option")
    if body.due_date < as_of(d): raise HTTPException(400,"Commitment due date precedes scenario date")
    sid=store.active_id()
    decision_id=store.record_decision(sid,body.incident_id,body.option_id,body.rationale,body.approver,now(),json.dumps(opts),body.factory_owner,body.commitment,body.due_date.isoformat())
    return {"decision_id":decision_id,"status":"recorded","selected":selected}


@app.get("/api/actions")
def actions():
    d=scenario()
    return [dict(**a,overdue=a["status"]!="done" and a["due_date"]<as_of(d).isoformat(),blocked=bool(a["dependency"] and next((x for x in d["actions"] if x["id"]==a["dependency"]),{}).get("status")!="done")) for a in d["actions"]]


class ActionUpdate(BaseModel):
    status:str
    evidence:str=Field(min_length=3)


@app.patch("/api/actions/{action_id}")
@app.patch("/api/action")
def update_action(action_id:str, body:ActionUpdate):
    if body.status not in ("open","in_progress","done","blocked"): raise HTTPException(400,"Invalid status")
    d=scenario(); action=next((a for a in d["actions"] if a["id"]==action_id),None)
    if not action: raise HTTPException(404,"Action not found")
    if body.status=="done" and action["dependency"]:
        dep=next((a for a in d["actions"] if a["id"]==action["dependency"]),None)
        if dep and dep["status"]!="done": raise HTTPException(400,"Complete the dependency first")
    store.execute("INSERT INTO scenario_action_updates VALUES (?,?,?,?,?) ON CONFLICT(scenario_id,action_id) DO UPDATE SET status=excluded.status,evidence=excluded.evidence,updated_at=excluded.updated_at",(store.active_id(),action_id,body.status,body.evidence,now()))
    return {"id":action_id,"status":body.status}


class CommitmentUpdate(BaseModel):
    status:str
    actual_date:date|None=None


@app.patch("/api/commitments/{commitment_id}")
def update_commitment(commitment_id:int,body:CommitmentUpdate):
    if body.status not in ("open","fulfilled","missed"): raise HTTPException(400,"Invalid status")
    sid=store.active_id()
    existing=store.rows("SELECT * FROM commitments WHERE scenario_id=? AND id=?",(sid,commitment_id))
    if not existing: raise HTTPException(404,"Commitment not found")
    if body.status=="fulfilled" and not body.actual_date: raise HTTPException(400,"Actual date is required")
    store.execute("UPDATE commitments SET status=?,actual_date=? WHERE scenario_id=? AND id=?",(body.status,body.actual_date.isoformat() if body.actual_date else None,sid,commitment_id))
    return {"id":commitment_id,"status":body.status}


@app.get("/api/improvement")
def improvement(incident_id:str|None=None):
    d=scenario()
    if not d["incidents"]:
        return dict(incident_id=None,records=[],baseline=None,targets=None,assessment="No incident recorded")
    incident=next((x for x in d["incidents"] if x["id"]==incident_id),None) if incident_id else d["incidents"][0]
    if not incident: raise HTTPException(404,"Incident not found")
    line_id=incident["line_id"]
    line_records=[r for r in d["production"] if r["line_id"]==line_id and r["date"]<=as_of(d).isoformat()]
    downtime_case=incident["type"]=="recurring_downtime"
    event_count=len([x for x in d["downtime"] if x["line_id"]==line_id and x["date"]<=as_of(d).isoformat()]) if downtime_case else None
    days=len({x["date"] for x in line_records})
    total_output=sum(x["actual"] for x in line_records)
    first_pass=sum(x["first_pass"] for x in line_records)
    avg_daily=round(total_output/max(1,days))
    style=lookup(d["styles"],lookup(d["orders"],incident["order_id"])["style_id"])
    records=store.rows("SELECT * FROM pdca WHERE scenario_id=? AND incident_id=? ORDER BY id DESC",(store.active_id(),incident["id"]))
    checks=[r for r in records if r["stage"]=="check"]
    target_rate=round(event_count/days*.55,2) if days and downtime_case else None
    comparable=[r for r in checks if r["volume"] is not None and r["complexity"] is not None and abs(r["volume"]-avg_daily)/max(1,avg_daily)<=.2 and abs(r["complexity"]-style["smv"])/style["smv"]<=.1]
    assessment="A downtime recurrence target is unavailable for this incident type; define a relevant measure before claiming improvement" if not downtime_case else "Historical production records are needed before an improvement baseline can be established" if not days else "No post-intervention check yet" if not checks else "Inconclusive: production volume or style complexity differs from baseline" if not comparable else "Preliminary improvement; 30/60/90-day persistence still unverified" if comparable[0]["observed"]<=target_rate else "Target not met; reopen the intervention"
    return dict(incident_id=incident["id"],records=records,baseline=dict(line=line_id,downtime_events=event_count,production_days=days,events_per_day=round(event_count/days,2) if days and downtime_case else None,daily_volume=avg_daily if days else None,style_smv=style["smv"],first_pass_yield=round(first_pass/total_output,3) if total_output else None,method="Compare downtime event rates only for recurring-downtime incidents at similar output volume and style SMV"),targets=dict(events_per_day=target_rate,first_pass_yield=.97 if days else None,checkpoints=[30,60,90]),assessment=assessment,comparable_checks=len(comparable) if downtime_case else 0)


class PDCAIn(BaseModel):
    incident_id:str
    stage:str
    baseline:float|None=Field(default=None,ge=0)
    observed:float|None=Field(default=None,ge=0)
    volume:int|None=Field(default=None,ge=0)
    complexity:float|None=Field(default=None,gt=0)
    observation:str=Field(min_length=8)


@app.post("/api/improvement")
def record_pdca(body:PDCAIn):
    if body.stage not in ("plan","do","check","act"): raise HTTPException(400,"Invalid PDCA stage")
    if body.stage=="check" and (body.observed is None or body.volume is None or body.complexity is None): raise HTTPException(400,"Check requires outcome, volume, and style complexity")
    if body.incident_id not in {x["id"] for x in scenario()["incidents"]}: raise HTTPException(404,"Incident not found")
    id=store.execute("INSERT INTO pdca (scenario_id,incident_id,stage,baseline,observed,volume,complexity,observation,recorded_at) VALUES (?,?,?,?,?,?,?,?,?)",(store.active_id(),body.incident_id,body.stage,body.baseline,body.observed,body.volume,body.complexity,body.observation,now()))
    return {"id":id,"status":"recorded","causal_claim":"pending review"}


@app.get("/api/rules")
def rules():
    return store.rows("SELECT * FROM rules WHERE scenario_id=? ORDER BY id DESC",(store.active_id(),))


class RuleIn(BaseModel):
    incident_id:str
    rule_key:str=Field(min_length=2)
    old_value:str=Field(min_length=1)
    proposed_value:str=Field(min_length=1)
    reason:str=Field(min_length=10)


@app.post("/api/rules")
def propose_rule(body:RuleIn):
    if body.incident_id not in {x["id"] for x in scenario()["incidents"]}: raise HTTPException(404,"Incident not found")
    if body.old_value.strip()==body.proposed_value.strip(): raise HTTPException(400,"Proposed value must differ from the current value")
    id=store.execute("INSERT INTO rules (scenario_id,incident_id,rule_key,old_value,proposed_value,reason,status) VALUES (?,?,?,?,?,?,?)",(store.active_id(),body.incident_id,body.rule_key,body.old_value,body.proposed_value,body.reason,"pending"))
    return {"id":id,"status":"pending management approval"}


class RuleApproval(BaseModel):
    approver:str=Field(min_length=2)
    approve:bool


@app.patch("/api/rules/{rule_id}")
def approve_rule(rule_id:int,body:RuleApproval):
    sid=store.active_id()
    found=store.rows("SELECT * FROM rules WHERE scenario_id=? AND id=?",(sid,rule_id))
    if not found: raise HTTPException(404,"Rule not found")
    if found[0]["status"]!="pending": raise HTTPException(400,"Rule already reviewed")
    status="approved" if body.approve else "rejected"
    store.execute("UPDATE rules SET status=?,approver=?,approved_at=? WHERE scenario_id=? AND id=?",(status,body.approver,now(),sid,rule_id))
    return {"id":rule_id,"status":status,"note":"Approval is recorded; Phase 1 does not auto-deploy rule changes."}


def management_report():
    sid=store.active_id()
    meta=store.active_meta()
    return dict(title="PlantCore Production Management Report",generated_at=now(),as_of=as_of(scenario()).isoformat(),scenario=meta,overview=overview(),orders=orders(),incidents=incidents(),actions=actions(),benchmarks=validation()["benchmarks"],decisions=store.rows("SELECT id,incident_id,option_id,rationale,approver,decided_at FROM decisions WHERE scenario_id=? ORDER BY id DESC",(sid,)),commitments=store.rows("SELECT * FROM commitments WHERE scenario_id=? ORDER BY id DESC",(sid,)),pdca=store.rows("SELECT * FROM pdca WHERE scenario_id=? ORDER BY id DESC",(sid,)),rules=store.rows("SELECT * FROM rules WHERE scenario_id=? ORDER BY id DESC",(sid,)),definitions=definitions(),caveat="Planning forecasts and inferred input values are illustrative. Confirm actual capacity, cost, quality, and customer commitments before operational use.")


@app.get("/api/reports/management.json")
def report_json():
    return Response(json.dumps(management_report(),indent=2),media_type="application/json",headers={"Content-Disposition":f'attachment; filename="production-report-{store.active_id()}.json"'})


@app.get("/api/reports/orders.csv")
def report_csv():
    output=StringIO()
    writer=csv.writer(output)
    def csv_text(value):
        text=str(value)
        return "'"+text if text.lstrip().startswith(("=","+","-","@")) else text
    writer.writerow(["scenario","order_id","customer","style_id","factory_id","line_id","quantity","material_release_date","material_ready","material_shortage_units","quality_pending","due_date","expected_ship","delay_days","status","priority","target_cost_usd"])
    for item in orders():
        plan=item["plan"]
        writer.writerow([store.active_id(),csv_text(item["id"]),csv_text(item["customer"]),csv_text(item["style_id"]),csv_text(plan.get("factory_id",item["factory_id"])),csv_text(plan.get("line_id",item["line_id"])),item["quantity"],item["material_release_date"],item["material_ready"],item["material_shortage_units"],item["quality_pending"],item["due_date"],plan.get("expected_ship",""),plan.get("delay_days",""),"feasible" if plan.get("feasible") else "blocked",item["priority"],round(item["target_cost"],2)])
    return Response(output.getvalue(),media_type="text/csv; charset=utf-8",headers={"Content-Disposition":f'attachment; filename="order-forecast-{store.active_id()}.csv"'})


@app.get("/api/reports/management.html")
def report_html():
    report=management_report(); k=report["overview"]["kpis"]
    e=lambda value:html_escape(str(value))
    order_rows="".join(f"<tr><td>{e(o['id'])}</td><td>{e(o['customer'])}</td><td>{e(o['plan'].get('factory_id',o['factory_id']))}/{e(o['plan'].get('line_id',o['line_id']))}</td><td>{e(o['quantity'])}</td><td>{e(o['due_date'])}</td><td>{e(o['plan'].get('expected_ship','Blocked'))}</td><td>{e(o['plan'].get('delay_days','N/A'))}</td></tr>" for o in report["orders"])
    incident_rows="".join(f"<tr><td>{e(i['id'])}</td><td>{e(i['title'])}</td><td>{e(i['order_id'])}</td><td>{e(i['severity'])}</td><td>{e(i['owner'])}</td></tr>" for i in report["incidents"])
    decision_rows="".join(f"<tr><td>{e(x['incident_id'])}</td><td>{e(x['option_id'])}</td><td>{e(x['approver'])}</td><td>{e(x['rationale'])}</td></tr>" for x in report["decisions"])
    assumptions="".join(f"<li>{e(value)}</li>" for value in report["scenario"].get("assumptions",[]))
    signals=report["overview"]["signals"]
    source_note=f"<section><h2>Source and outcome</h2><p>{e(report['scenario']['description'])}; {e(signals['late_units'])} units on exposed orders; {e(signals['blocked_orders'])} blocked orders.</p><p>Historical production records: {signals['data_coverage']['production']}; downtime events: {signals['data_coverage']['downtime']}.</p>{f'<h3>Assumptions</h3><ul>{assumptions}</ul>' if assumptions else ''}</section>"
    html=f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Production report — {e(report['scenario']['name'])}</title><style>body{{font:14px Arial,sans-serif;color:#202c3a;margin:36px}}h1,h2{{color:#2b5797}}header{{border-bottom:4px solid #ed7d31;padding-bottom:15px}}.meta{{color:#66788a}}.metrics{{display:flex;gap:12px;margin:22px 0}}.metric{{background:#f2f5f8;padding:15px;flex:1;border-radius:6px}}.metric strong{{display:block;font-size:22px}}table{{border-collapse:collapse;width:100%;margin:10px 0 25px}}th,td{{border-bottom:1px solid #dfe5ed;text-align:left;padding:8px;font-size:11px}}th{{background:#eef3f8}}.caveat{{background:#fff3e7;padding:12px;border-left:4px solid #ed7d31}}@media print{{body{{margin:15mm}}section{{break-inside:avoid}}}}</style></head><body><header><h1>Multi-Factory Production Management Report</h1><div class="meta">{e(report['scenario']['name'])} · Scenario date {e(report['as_of'])} · Generated {e(report['generated_at'])} · {'SIMULATED' if report['scenario']['synthetic'] else 'UPLOADED DATA'}</div></header><div class="metrics"><div class="metric">Active orders<strong>{k['active_orders']}</strong></div><div class="metric">At risk / blocked<strong>{k['at_risk']}</strong></div><div class="metric">Forecast OTIF<strong>{k['forecast_otif']*100:.1f}%</strong></div><div class="metric">First-pass yield<strong>{f"{k['first_pass_yield']*100:.1f}%" if k['first_pass_yield'] is not None else 'N/A'}</strong></div></div><p><strong>Management insight:</strong> {e(report['overview']['insight'])}</p>{source_note}<section><h2>Order forecast</h2><table><thead><tr><th>Order</th><th>Customer</th><th>Factory / line</th><th>Units</th><th>Deadline</th><th>Forecast ship</th><th>Delay days</th></tr></thead><tbody>{order_rows}</tbody></table></section><section><h2>Incidents and owners</h2><table><thead><tr><th>Incident</th><th>Disruption</th><th>Order</th><th>Severity</th><th>Owner</th></tr></thead><tbody>{incident_rows}</tbody></table></section><section><h2>Approved recovery decisions</h2><table><thead><tr><th>Incident</th><th>Option</th><th>Approver</th><th>Rationale</th></tr></thead><tbody>{decision_rows or '<tr><td colspan="4">None recorded</td></tr>'}</tbody></table></section><p class="caveat">{e(report['caveat'])}</p></body></html>"""
    return Response(html,media_type="text/html; charset=utf-8",headers={"Content-Disposition":f'attachment; filename="management-report-{store.active_id()}.html"'})
