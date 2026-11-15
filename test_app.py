"""End-to-end Streamlit interaction checks, isolated from user investigations."""
import os
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from test_pipeline import generate
from src.workflow import Workflow

class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(); cls.base=Path(cls.temp.name)/'base'; generate(cls.base,'starter',20261022)
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.data=Path(self.temp.name)/'generated'; shutil.copytree(self.base,self.data)
        self.env=patch.dict(os.environ,{'INVENTORY_DATA_DIR':str(self.data),'INVENTORY_WORKFLOW_DB':str(Path(self.temp.name)/'workflow.sqlite3')}); self.env.start()
        self.app=AppTest.from_file('app.py',default_timeout=30).run(); self.assertFalse(self.app.exception)
    def tearDown(self): self.env.stop(); self.temp.cleanup()
    def select(self,prefix,value):
        next(w for w in self.app.selectbox if w.key.startswith(prefix)).select(value)
    def save(self):
        next(b for b in self.app.button if b.label=='Save investigation').click().run(); self.assertFalse(self.app.exception)
    def test_assign_progress_close_and_reload(self):
        self.select('owner_','ROLE-0005'); self.save()
        self.select('target_','IN_PROGRESS'); self.save()
        self.select('target_','CLOSED'); self.select('outcome_','PROCESS_ERROR')
        self.app.text_area[0].set_value('Reconciled source inventory documents'); self.save()
        workflow=Workflow(self.data,Path(self.temp.name)/'workflow.sqlite3'); c=workflow.cases()[0]
        self.assertEqual((c['status'],c['owner_employee_role_id']),('CLOSED','ROLE-0005'))
        self.assertEqual(len(workflow.history(c['investigation_id'])),4)
        self.app.run(); self.assertFalse(self.app.exception); self.assertTrue(any('Closed: PROCESS_ERROR' in s.value for s in self.app.success))
    def test_empty_filters(self):
        self.app.date_input[0].set_value((date(2030,1,1),date(2030,1,2))).run()
        self.assertFalse(self.app.exception); self.assertTrue(any('No alerts match' in i.value for i in self.app.info))
    def test_required_closure_notes(self):
        self.select('target_','IN_PROGRESS'); self.save(); self.select('target_','CLOSED'); self.select('outcome_','PROCESS_ERROR'); self.save()
        self.assertTrue(any('notes' in e.value for e in self.app.error))
    def test_filtered_count_evidence(self):
        self.app.selectbox(key='filter_reason').select('UNEXPLAINED_COUNT_SHORTAGE').run()
        self.app.checkbox(key='load_evidence').check().run(); self.assertFalse(self.app.exception)
        self.assertTrue(any('reference_movement_id' in df.value.columns for df in self.app.dataframe))
if __name__=='__main__': unittest.main()
