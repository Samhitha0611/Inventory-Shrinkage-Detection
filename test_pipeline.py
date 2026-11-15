"""Regression checks for accounting, rule independence and validation failures."""
import csv
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'src'))
from generate_data import generate
from detect_anomalies import detect
from evaluate import evaluate
from validate_data import validate
from common import read,write
class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=tempfile.TemporaryDirectory(); cls.base=Path(cls.root.name)/'base'; generate(cls.base,'starter',20261022)
    @classmethod
    def tearDownClass(cls): cls.root.cleanup()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.out=Path(self.temp.name)/'data'; shutil.copytree(self.base,self.out)
    def tearDown(self): self.temp.cleanup()
    def mutate(self,table,fn):
        rows=list(read(self.out,table)); fn(rows); write(self.out,table,rows)
    def assert_invalid(self,check):
        r=validate(self.out); self.assertEqual(r['status'],'FAIL'); self.assertTrue(any(check in e['check'] for e in r['errors']),r['errors'])
    def test_baseline_and_metrics(self):
        r=validate(self.out); self.assertEqual(r['status'],'PASS',r['errors']); self.assertEqual(r['missing_expected_exceptions'],0)
        e=evaluate(self.out); self.assertEqual(e['overall']['fn'],0); self.assertEqual(e['overall']['fp'],0); self.assertGreater(e['overall']['tp'],0)
    def test_detector_independent_of_truth(self):
        original=(self.out/'ShrinkageAlert.csv').read_bytes(); (self.out/'ground_truth.csv').unlink(); detect(self.out); self.assertEqual(original,(self.out/'ShrinkageAlert.csv').read_bytes())
    def test_unlabelled_evidence_is_detected(self):
        def change(rows):
            r=next(r for r in rows if r['movement_type']=='ADJUSTMENT' and r['reason']); self.rid=r['movement_id']; r['reason']=''
        self.mutate('InventoryMovement',change); alerts=detect(self.out)
        self.assertTrue(any(a['movement_id']==self.rid and a['reason_code']=='MISSING_ADJUSTMENT_REASON' for a in alerts)); self.assert_invalid('missing_adjustment_reason')
    def test_reconciliation_corruption(self):
        def change(rows): rows[1]['expected_qty']=str(int(rows[1]['expected_qty'])+1); rows[1]['variance_qty']=str(int(rows[1]['counted_qty'])-int(rows[1]['expected_qty']))
        self.mutate('CycleCount',change); self.assert_invalid('count_as_of_reconciliation')
    def test_negative_stock(self):
        self.mutate('StoreSKUOpeningBalance',lambda rows:[r.update(opening_qty='0') for r in rows]); self.assert_invalid('negative_running_stock')
    def test_foreign_key(self):
        self.mutate('Return',lambda rows:rows[0].update(original_sale_movement_id='MISSING')); self.assert_invalid('Return_original_sale_movement_id_FK')
    def test_shift_time(self):
        self.mutate('InventoryMovement',lambda rows:rows[0].update(movement_ts='2026-01-10T23:00:00.000000')); self.assert_invalid('shift_time')
    def test_authorization(self):
        self.mutate('InventoryMovement',lambda rows:rows[0].update(employee_role_id='ROLE-0003')); self.assert_invalid('authorization_ANALYST')
    def test_enum(self):
        self.mutate('InventoryMovement',lambda rows:rows[0].update(movement_type='INVALID')); self.assert_invalid('movement_enum')
    def test_invalid_count_number(self):
        self.mutate('CycleCount',lambda rows:rows[0].update(counted_qty='not-a-number')); self.assert_invalid('CycleCount_counted_qty_integer')
    def test_primary_key(self):
        self.mutate('SKU',lambda rows:rows.append(rows[0].copy())); self.assert_invalid('SKU_primary_key')
    def test_transfer_corruption(self):
        def change(rows):
            r=next(r for r in rows if r['movement_type']=='TRANSFER_IN' and int(r['signed_qty'])>0); r['related_movement_id']=''
        self.mutate('InventoryMovement',change); self.assert_invalid('transfer_pair')
    def test_missing_expected_exception(self):
        self.mutate('InventoryMovement',lambda rows:[r.update(reason='FIXED') for r in rows if r['movement_type']=='ADJUSTMENT' and not r['reason']]); self.assert_invalid('planted_exception_not_present')
    def test_lifecycle_requires_history(self):
        self.mutate('Investigation',lambda rows:rows[0].update(status='CLOSED',outcome='CONFIRMED_DATA_ERROR',closed_at='2026-01-07T20:00:00.000000')); self.assert_invalid('history_final_state')
    def test_valid_lifecycle(self):
        inv=list(read(self.out,'Investigation'))[0]; opened=inv['opened_at']; progress='2026-01-07T18:00:00.000000'; closed='2026-01-07T19:00:00.000000'
        self.mutate('Investigation',lambda rows:rows[0].update(status='CLOSED',outcome='CONFIRMED_DATA_ERROR',closed_at=closed))
        def change(rows):
            rows.extend([dict(event_id='TEST-1',investigation_id=inv['investigation_id'],from_status='OPEN',to_status='IN_PROGRESS',event_ts=progress,outcome=''),dict(event_id='TEST-2',investigation_id=inv['investigation_id'],from_status='IN_PROGRESS',to_status='CLOSED',event_ts=closed,outcome='CONFIRMED_DATA_ERROR')])
        self.mutate('InvestigationEvent',change); r=validate(self.out); self.assertEqual(r['status'],'PASS',r['errors'])
if __name__=='__main__': unittest.main()
