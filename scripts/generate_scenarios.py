"""Regenerate the 20 self-contained, synthetic scenario JSON test files."""
from datetime import date, timedelta
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.seed import seed_data
from app.scenarios import validate_document

OUT=ROOT/'test-files'
OUT.mkdir(exist_ok=True)


def by_id(rows,id): return next(x for x in rows if x['id']==id)
def move_date(value,days): return (date.fromisoformat(value)+timedelta(days=days)).isoformat()
def change_material(data,order_id,days):
    order=by_id(data['orders'],order_id)
    order['material_date']=move_date(order['material_date'],days)
    material=next(x for x in data['materials'] if x['order_id']==order_id)
    material['fabric_ready']=move_date(material['fabric_ready'],days)
    material['trims_ready']=move_date(material['trims_ready'],days)


def steady(d):
    for o in d['orders']:
        o['due_date']=move_date(o['due_date'],20)
        o['quality_release']=True
    for material in d['materials']: material['shortage_units']=0
    for hold in d['quality_holds']: hold['status']='closed'
    for incident in d['incidents']: incident['status']='closed'
    for action in d['actions']: action['status']='done'
def material_delay(d): change_material(d,'PO-2607',8)
def needle_breakdown(d):
    by_id(d['lines'],'L7')['efficiency']=.52
    d['downtime'].append(dict(id='DT-SIM-01',date='2026-10-14',line_id='L7',machine='FL-07',cause='Needle failure',minutes=180,shift='B'))
    by_id(d['incidents'],'INC-001')['lost_minutes']=845
def operator_shortage(d):
    by_id(d['lines'],'L7')['operators']=23
    for r in d['labor']:
        if r['line_id']=='L7': r['scheduled']=33;r['present']=22
def quality_hold(d):
    by_id(d['orders'],'PO-2618')['quality_release']=False
    d['quality_holds'].append(dict(id='QH-SIM-01',order_id='PO-2618',date='2026-10-14',hours=24,cause='Seam strength release pending',status='open'))
def urgent_deadline(d): by_id(d['orders'],'PO-2618')['due_date']='2026-10-19'
def demand_surge(d):
    o=by_id(d['orders'],'PO-2618');o['quantity']=2300;o['target_cost']=2300*9.8
def planned_maintenance(d): by_id(d['lines'],'L7')['maintenance']=['2026-10-16','2026-10-17','2026-10-19']
def factory_shutdown(d): by_id(d['factories'],'F3')['shutdown_dates']=['2026-10-15','2026-10-16','2026-10-17','2026-10-19']
def logistics_delay(d): by_id(d['factories'],'F3')['logistics_days']=6
def compliance_hold(d): by_id(d['factories'],'F2')['compliance']=False
def defect_spike(d):
    by_id(d['factories'],'F3')['quality']=.84
    for r in d['production']:
        if r['line_id']=='L7': r['first_pass']=round(r['actual']*.84);r['rework']=r['actual']-r['first_pass']
def rework_growth(d):
    by_id(d['orders'],'PO-2618')['quality_release']=False
    for r in d['production']:
        if r['line_id']=='L7': r['rework']=round(r['actual']*.16);r['first_pass']=r['actual']-r['rework']
def second_shift(d):
    l=by_id(d['lines'],'L7');l['operators']=43;l['efficiency']=.77
def cheap_risky_factory(d):
    f=by_id(d['factories'],'F3');f['cost']=2.8;f['reliability']=.55;f['quality']=.89
def complex_style(d):
    s=by_id(d['styles'],'S08');s['smv']=36.0;s['operations'][2]=('Hood attach',12.0)
def capacity_crunch(d):
    for l in d['lines']:
        if l['factory_id']=='F1':l['efficiency']=.55
def combined_delay(d):
    change_material(d,'PO-2618',5)
    by_id(d['lines'],'L7')['efficiency']=.57
    by_id(d['factories'],'F3')['logistics_days']=4
def fast_quality_tradeoff(d):
    f=by_id(d['factories'],'F1');f['quality']=.81;f['reliability']=.94
    by_id(d['lines'],'L1')['efficiency']=.98
    by_id(d['factories'],'F3')['quality']=.97
def impossible_machine(d): by_id(d['styles'],'S10')['machine']='laser-bond'

CASES=[
    ('01_steady_network','Steady network','All customer due dates have additional buffer; use as a low-risk reference.',steady),
    ('02_late_fabric','Late fabric arrival','Fabric and trims for PO-2607 are delayed eight days.',material_delay),
    ('03_needles_fail','Recurring needle failure','FL-07 loses efficiency and a further breakdown occurs.',needle_breakdown),
    ('04_absenteeism','Operator absenteeism','The critical line loses ten operators and historical attendance weakens.',operator_shortage),
    ('05_quality_release','Quality release hold','PO-2618 cannot clear inspection until the open hold is released.',quality_hold),
    ('06_rush_order','Urgent customer deadline','PO-2618 deadline moves to 19 October.',urgent_deadline),
    ('07_demand_surge','Demand surge','The focal hoodie order rises to 2,300 units.',demand_surge),
    ('08_planned_maintenance','Planned maintenance','L7 is unavailable for three production days.',planned_maintenance),
    ('09_factory_shutdown','Factory shutdown','Gazipur Works is closed for four production days.',factory_shutdown),
    ('10_logistics_delay','Transport disruption','Gazipur transit increases from two to six days.',logistics_delay),
    ('11_compliance_hold','Factory compliance hold','Chattogram Apparel cannot receive production allocation.',compliance_hold),
    ('12_defect_spike','Defect spike','Gazipur first-pass yield falls to 84 percent.',defect_spike),
    ('13_rework_growth','Rework growth','L7 rework reaches 16 percent and the focal order needs quality release.',rework_growth),
    ('14_second_shift','Temporary second shift','L7 receives extra operators and better effective output.',second_shift),
    ('15_low_cost_trap','Low-cost supplier trap','Gazipur becomes cheapest but less reliable and lower quality.',cheap_risky_factory),
    ('16_complex_style','Complex operation','Hoodie SMV rises as the hood operation takes longer.',complex_style),
    ('17_capacity_crunch','Factory capacity crunch','All Dhaka lines operate at lower efficiency.',capacity_crunch),
    ('18_combined_disruption','Combined material and downtime','Material, sewing efficiency, and transport deteriorate together.',combined_delay),
    ('19_fast_quality_tradeoff','Fast line, high quality risk','A faster Dhaka line carries much higher defect exposure.',fast_quality_tradeoff),
    ('20_no_machine','No feasible machine','Denim jacket requires a machine that no factory owns.',impossible_machine),
]


def main():
    for slug,name,description,mutate in CASES:
        data=seed_data();mutate(data)
        document=dict(schema_version=1,meta=dict(id=slug,name=name,description=description,synthetic=True,as_of="2026-10-14",holidays=["2026-10-20"]),data=data)
        validate_document(document)
        path=OUT/f'{slug}.json'
        path.write_text(json.dumps(document,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        print(path.name)


if __name__=='__main__':main()
