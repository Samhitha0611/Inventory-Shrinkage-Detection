"""Workflow transaction, audit, namespace and dashboard regression coverage."""
import json
import shutil
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
import pandas as pd
from test_pipeline import generate
from src.workflow import Workflow, ConflictError
from src.dashboard import filter_alerts, exposure

class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=tempfile.TemporaryDirectory(); cls.base=Path(cls.root.name)/'source'; generate(cls.base,'starter',20261022)
    @classmethod
    def tearDownClass(cls): cls.root.cleanup()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.data=Path(self.temp.name)/'generated'; shutil.copytree(self.base,self.data)
        self.service=Workflow(self.data); self.case=self.service.cases()[0]; self.iid=self.case['investigation_id']
    def tearDown(self): self.temp.cleanup()
    def update(self,**changes):
        args=dict(expected_version=0,actor='ROLE-0002',owner='ROLE-0002',target='IN_PROGRESS'); args.update(changes)
        return self.service.update(self.iid,**args)
    def test_assignment_and_persistent_lifecycle(self):
        source={p.name:p.read_bytes() for p in self.data.glob('*.csv')}
        assigned=self.update(target='OPEN',owner='ROLE-0005'); self.assertEqual(assigned['version'],1)
        self.update(expected_version=1,owner='ROLE-0005'); closed=self.update(expected_version=2,owner='ROLE-0005',target='CLOSED',outcome='PROCESS_ERROR',note='Verified transfer double debit')
        self.assertEqual(closed['version'],3); self.assertTrue(closed['closed_at'])
        reloaded=Workflow(self.data); self.assertEqual(reloaded.case(self.iid)['status'],'CLOSED')
        events=reloaded.history(self.iid); self.assertEqual([e['action'] for e in events],['CREATE','ASSIGN','TRANSITION','TRANSITION'])
        self.assertEqual(events[-1]['note'],'Verified transfer double debit'); self.assertEqual(events[-1]['owner_employee_role_id'],'ROLE-0005')
        self.assertEqual(source,{p.name:p.read_bytes() for p in self.data.glob('*.csv')})
    def test_skip_transition_rejected(self):
        with self.assertRaises(ValueError): self.update(target='CLOSED',outcome='PROCESS_ERROR',note='x')
        self.assertEqual(len(self.service.history(self.iid)),1)
    def test_close_requires_outcome_and_notes(self):
        self.update()
        for outcome,note in [('', 'verified'),('INVALID','verified'),('PROCESS_ERROR',' ')]:
            with self.assertRaises(ValueError): self.update(expected_version=1,target='CLOSED',outcome=outcome,note=note)
        self.assertEqual(self.service.case(self.iid)['status'],'IN_PROGRESS'); self.assertEqual(len(self.service.history(self.iid)),2)
    def test_closed_is_read_only(self):
        self.update(); self.update(expected_version=1,target='CLOSED',outcome='INCONCLUSIVE',note='No supporting evidence')
        with self.assertRaises(ValueError): self.update(expected_version=2,target='CLOSED',owner='ROLE-0005')
    def test_invalid_manager(self):
        for changes in ({'owner':'ROLE-0003'},{'actor':'MISSING'}):
            with self.assertRaises(ValueError): self.update(**changes)
    def test_stale_update_is_rejected(self):
        self.update()
        with self.assertRaises(ConflictError): self.update()
        self.assertEqual(len(self.service.history(self.iid)),2)
    def test_concurrent_updates_commit_once(self):
        def attempt(_):
            try: self.update(); return 'saved'
            except ConflictError: return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(attempt,range(2)))
        self.assertCountEqual(results,['saved','conflict']); self.assertEqual(len(self.service.history(self.iid)),2)
    def test_audit_append_only(self):
        for sql in ('DELETE FROM AuditEvent','UPDATE AuditEvent SET note=\'edited\''):
            with self.assertRaises(sqlite3.IntegrityError):
                with self.service.connect() as db: db.execute(sql)
    def test_dataset_change_preserves_old_history(self):
        self.update()
        p=self.data/'ShrinkageAlert.csv'; p.write_text(p.read_text(encoding='utf-8')+'\n',encoding='utf-8')
        new=Workflow(self.data); self.assertNotEqual(new.dataset_id,self.service.dataset_id)
        self.assertEqual(new.case(self.iid)['status'],'OPEN'); self.assertEqual(self.service.case(self.iid)['status'],'IN_PROGRESS')
        self.assertEqual(len(new.history(self.iid)),1)
    def test_filter_combination_and_empty(self):
        df=pd.read_csv(self.data/'ShrinkageAlert.csv',keep_default_na=False); r=df.iloc[0]; day=pd.Timestamp(r['created_at']).date()
        filtered=filter_alerts(df,store=r['store_id'],sku=r['sku_id'],severity=r['severity'],reason=r['reason_code'],status='OPEN',start=day,end=day)
        self.assertIn(r['alert_id'],filtered['alert_id'].tolist())
        self.assertTrue(filter_alerts(df,start=date(2030,1,1)).empty)
    def test_exposure_deduplicates_events_and_transfers(self):
        rows=[dict(movement_id='A',count_id='',exposure_inr=100,evidence='{}'),dict(movement_id='A',count_id='',exposure_inr=100,evidence='{}'),dict(movement_id='B',count_id='',exposure_inr=300,evidence=json.dumps({'transfer_id':'T'})),dict(movement_id='C',count_id='',exposure_inr=300,evidence=json.dumps({'transfer_id':'T'}))]
        self.assertEqual(exposure(pd.DataFrame(rows)),400)
        self.assertEqual(exposure(pd.DataFrame(columns=rows[0])),0)
if __name__=='__main__': unittest.main()
