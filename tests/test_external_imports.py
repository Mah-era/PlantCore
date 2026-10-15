"""External files must drive forecasts and report values, not reuse the demo network."""
import asyncio
from datetime import date
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi import Request
from openpyxl import Workbook

from app import store
from app.importers import import_file
from app.engine import recovery_options, schedule_all, line_capacity, line_minutes
from app.main import incidents, orders, overview, report_csv, report_html, upload_scenario, decide, DecisionIn
from app.scenarios import ScenarioError
from app.scenarios import builtin_document, validate_document
from app.seed import seed_data


EXAMPLE=Path(__file__).resolve().parents[1]/"examples"/"sample-orders.csv"


def request(payload):
    async def receive(): return {"type":"http.request","body":payload,"more_body":False}
    return Request({"type":"http","method":"POST","headers":[]},receive)


class ExternalImportTests(unittest.TestCase):
    def test_csv_upload_changes_every_major_result(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(store,"DB_PATH",Path(tmp)/"test.db"):
            original=overview()
            response=asyncio.run(upload_scenario(request(EXAMPLE.read_bytes()),filename=EXAMPLE.name))
            self.assertEqual(response["orders"],3)
            current=overview()
            self.assertEqual(current["as_of"],"2026-11-01")
            self.assertEqual(current["kpis"]["active_orders"],3)
            self.assertNotEqual(current["kpis"]["at_risk"],original["kpis"]["at_risk"])
            self.assertEqual(current["kpis"]["first_pass_yield"],None)
            self.assertEqual({x["id"] for x in orders()},{"EXT-1001","EXT-1002","EXT-1003"})
            self.assertTrue(any(x["id"].startswith("AUTO-") for x in incidents()))
            self.assertIn(b"EXT-1001",report_csv().body)
            self.assertIn(b"2026-11-01",report_html().body)
            self.assertIn(b"N/A",report_html().body)

    def test_csv_contents_change_outcome(self):
        raw=EXAMPLE.read_text()
        changed=raw.replace("1800,2026-11-03,2026-11-10","1800,2026-11-03,2026-12-10")
        with tempfile.TemporaryDirectory() as tmp, patch.object(store,"DB_PATH",Path(tmp)/"test.db"):
            asyncio.run(upload_scenario(request(raw.encode()),filename="first.csv"))
            first=overview()
            asyncio.run(upload_scenario(request(changed.encode()),filename="second.csv"))
            second=overview()
            self.assertLess(second["kpis"]["at_risk"],first["kpis"]["at_risk"])
            self.assertNotEqual(second["risk_timeline"],first["risk_timeline"])

    def test_excel_orders_sheet_imports(self):
        book=Workbook(); sheet=book.active; sheet.title="Orders"
        for row in EXAMPLE.read_text().splitlines(): sheet.append(row.split(","))
        output=BytesIO(); book.save(output)
        document=import_file(output.getvalue(),"another-network.xlsx")
        self.assertEqual(len(document["data"]["orders"]),3)
        self.assertEqual(document["meta"]["source_format"],"xlsx")
        self.assertTrue(document["meta"]["synthetic"])

    def test_bad_csv_explains_missing_field(self):
        with self.assertRaisesRegex(ScenarioError,"quantity"):
            import_file(b"order_id,due_date,material_date\nX,2026-11-10,2026-11-01\n","bad.csv")

    def test_huge_numeric_values_fail_validation_cleanly(self):
        document=builtin_document('01_steady_network')
        document['data']['orders'][0]['target_cost']=10**1000
        with self.assertRaises(ScenarioError):
            validate_document(document)
        changed=EXAMPLE.read_text().replace('1800,2026-11-03','1e1000,2026-11-03')
        with self.assertRaises(ScenarioError):
            import_file(changed.encode(),'huge.csv')

    def test_json_order_rows_must_be_objects(self):
        with self.assertRaisesRegex(ScenarioError,"Row 2 must be an object"):
            import_file(b'["not an order"]','bad.json')

    def test_slash_id_and_spreadsheet_formula_are_safe_in_exports(self):
        changed=EXAMPLE.read_text().replace('EXT-1001,Acme Retail','PO/2026/17,=1+1')
        with tempfile.TemporaryDirectory() as tmp, patch.object(store,"DB_PATH",Path(tmp)/"test.db"):
            asyncio.run(upload_scenario(request(changed.encode()),filename="unusual-ids.csv"))
            self.assertIn('PO/2026/17',orders()[0]['id'])
            csv_body=report_csv().body.decode()
            self.assertIn("'=1+1",csv_body)
            self.assertIn('PO/2026/17',csv_body)

    def test_fractional_staffing_is_rejected_instead_of_truncated(self):
        changed=EXAMPLE.read_text().replace('16,24,0.78','16,24.5,0.78')
        with self.assertRaisesRegex(ScenarioError,'operators must be a whole number'):
            import_file(changed.encode(),'staffing.csv')

    def test_invalid_incident_minutes_get_upload_error(self):
        document=builtin_document('03_needles_fail')
        document['data']['incidents'][0]['lost_minutes']='unknown'
        with self.assertRaisesRegex(ScenarioError,'invalid lost_minutes'):
            validate_document(document)

    def test_blocked_assignment_still_checks_compatible_recovery_lines(self):
        data=seed_data(); data["_meta"]={"as_of":"2026-10-14","holidays":["2026-10-20"]}
        order=next(x for x in data["orders"] if x["id"]=="PO-2618")
        order.update(factory_id="F1",line_id="L2")  # L2 cannot make this knit style.
        incident=next(x for x in data["incidents"] if x["id"]=="INC-001")
        incident.update(factory_id="F1",line_id="L2")
        options=recovery_options(incident,data)
        self.assertFalse(next(x for x in options if x["id"]=="baseline")["feasible"])
        self.assertTrue(next(x for x in options if x["id"]=="same_factory_line")["feasible"])

    def test_failed_order_does_not_reserve_capacity_for_later_orders(self):
        data=seed_data(); data["_meta"]={"as_of":"2026-10-14","holidays":[]}
        data["orders"]=[x for x in data["orders"] if x["id"] in ("PO-2618","PO-2619")]
        first,second=sorted(data["orders"],key=lambda x:x["id"])
        first.update(priority=5,quantity=50000,quality_release=True)
        second.update(priority=1,quantity=250,quality_release=True,factory_id=first["factory_id"],line_id=first["line_id"],style_id=first["style_id"],material_date="2026-10-14")
        data["materials"]=[dict(order_id=x["id"],fabric_ready="2026-10-14",trims_ready="2026-10-14",shortage_units=0) for x in data["orders"]]
        with_failed=schedule_all(data)
        self.assertFalse(with_failed[first["id"]]["feasible"])
        data["orders"]=[second];data["materials"]=[data["materials"][1]]
        alone=schedule_all(data)
        self.assertEqual(with_failed[second["id"]]["expected_ship"],alone[second["id"]]["expected_ship"])

    def test_subcontracting_never_overbooks_in_house_line(self):
        data=seed_data();data["_meta"]={"as_of":"2026-10-14","holidays":[]}
        orders=[x for x in data["orders"] if x["id"] in ("PO-2618","PO-2619")]
        first,second=sorted(orders,key=lambda x:x["id"])
        second.update(factory_id=first["factory_id"],line_id=first["line_id"],style_id=first["style_id"],quantity=250,material_date="2026-10-14")
        data["orders"]=orders
        data["materials"]=[dict(order_id=x["id"],fabric_ready="2026-10-14",trims_ready="2026-10-14",shortage_units=0) for x in orders]
        plans=schedule_all(data,{first["id"]:{"subcontract":True}})
        self.assertTrue(all(plan["feasible"] for plan in plans.values()))
        # The combined output can exceed line capacity only by the modeled subcontract allowance.
        by_day={}
        for plan in plans.values():
            for row in plan["daily"]: by_day[row["date"]]=by_day.get(row["date"],0)+row["units"]
        line=next(x for x in data["lines"] if x["id"]==first["line_id"])
        style=next(x for x in data["styles"] if x["id"]==first["style_id"])
        for day,units in by_day.items():
            cap=line_capacity(line,style,date.fromisoformat(day),data)
            self.assertLessEqual(units,cap+int(cap*.35))

    def test_mixed_smv_orders_share_minutes_not_units(self):
        data=seed_data();data['_meta']={'as_of':'2026-10-14','holidays':[]}
        selected=[x for x in data['orders'] if x['id'] in ('PO-2601','PO-2618')]
        selected[0].update(factory_id='F3',line_id='L7',style_id='S01',quantity=700,material_date='2026-10-14',quality_release=True)
        selected[1].update(factory_id='F3',line_id='L7',style_id='S08',quantity=700,material_date='2026-10-14',quality_release=True)
        data['orders']=selected
        data['materials']=[dict(order_id=x['id'],fabric_ready='2026-10-14',trims_ready='2026-10-14',shortage_units=0) for x in selected]
        plans=schedule_all(data)
        self.assertTrue(all(p['feasible'] for p in plans.values()))
        line=next(x for x in data['lines'] if x['id']=='L7')
        used={}
        for order in selected:
            style=next(x for x in data['styles'] if x['id']==order['style_id'])
            for row in plans[order['id']]['daily']:
                used[row['date']]=used.get(row['date'],0)+row['units']*style['smv']
        for day,minutes in used.items():
            self.assertLessEqual(minutes,line_minutes(line,date.fromisoformat(day),data)+.001)

    def test_recovery_resolves_derived_exception_after_reforecast(self):
        raw=EXAMPLE.read_text().replace('2026-11-03,2026-11-10','2026-11-03,2026-11-12')
        with tempfile.TemporaryDirectory() as tmp, patch.object(store,'DB_PATH',Path(tmp)/'test.db'):
            asyncio.run(upload_scenario(request(raw.encode()),filename='recover.csv'))
            incident=next(x for x in incidents() if x['id']=='AUTO-EXT-1001')
            self.assertEqual(incident['status'],'open')
            self.assertEqual(next(x for x in orders() if x['id']=='EXT-1001')['plan']['delay_days'],1)
            decide(DecisionIn(incident_id=incident['id'],option_id='expedite_freight',rationale='Confirm faster transport to meet the customer deadline',approver='Production manager',factory_owner='Factory manager',commitment='Book approved expedited freight and confirm departure',due_date=date(2026,11,5)))
            self.assertEqual(next(x for x in orders() if x['id']=='EXT-1001')['plan']['delay_days'],0)
            self.assertEqual(next(x for x in incidents() if x['id']==incident['id'])['status'],'resolved')
            self.assertEqual(len(store.rows('SELECT * FROM decisions')),1)
            self.assertEqual(len(store.rows('SELECT * FROM commitments')),1)

    def test_future_history_does_not_change_present_capacity(self):
        data=seed_data();data['_meta']={'as_of':'2026-10-14','holidays':[]}
        line=next(x for x in data['lines'] if x['id']=='L7')
        style=next(x for x in data['styles'] if x['id']=='S08')
        original=line_capacity(line,style,date(2026,10,15),data)
        data['labor'].append(dict(date='2026-12-01',line_id='L7',scheduled=33,present=1))
        data['downtime'].append(dict(id='FUTURE',date='2026-12-01',line_id='L7',machine='FL-07',cause='Future',minutes=3000,shift='A'))
        self.assertEqual(line_capacity(line,style,date(2026,10,15),data),original)

    def test_recovery_prices_another_order_becoming_blocked(self):
        data=seed_data();data['_meta']={'as_of':'2026-10-14','holidays':[]}
        data['orders']=[x for x in data['orders'] if x['id'] in ('PO-2618','PO-2619')]
        target,other=data['orders']
        target.update(factory_id='F3',line_id='L8',style_id='S08',quantity=15000,quality_release=True,material_date='2026-10-14')
        other.update(factory_id='F3',line_id='L7',style_id='S08',quantity=12000,quality_release=True,material_date='2026-10-14')
        data['materials']=[dict(order_id=x['id'],fabric_ready='2026-10-14',trims_ready='2026-10-14',shortage_units=0) for x in data['orders']]
        incident=next(x for x in data['incidents'] if x['id']=='INC-001')
        incident.update(factory_id='F3',line_id='L8')
        self.assertTrue(schedule_all(data)[other['id']]['feasible'])
        transfer=next(x for x in recovery_options(incident,data) if x['id']=='same_factory_line')
        self.assertTrue(transfer['feasible'])
        self.assertIn(other['id'],transfer['affected_other_orders'])
        self.assertGreater(transfer['other_order_cost'],other['quantity']*.35)


if __name__=="__main__": unittest.main()
