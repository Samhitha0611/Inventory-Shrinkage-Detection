"""Transactional investigation snapshots and append-only audit events.

Generated CSVs remain reproducible. Each source dataset has a separate namespace
in the local workflow database, so regeneration cannot reuse unrelated cases.
"""
import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from .common import read

OUTCOMES = ('CONFIRMED_LOSS', 'PROCESS_ERROR', 'LEGITIMATE_VARIANCE', 'INCONCLUSIVE')
NEXT = {'OPEN': 'IN_PROGRESS', 'IN_PROGRESS': 'CLOSED'}

class ConflictError(ValueError):
    """The selected case changed since the user opened it."""

class Workflow:
    def __init__(self, data, database=None):
        self.data = Path(data)
        self.database = Path(database) if database else self.data.parent / 'workflow.sqlite3'
        self.database.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        for name in ('ShrinkageAlert', 'Investigation', 'InvestigationEvent', 'EmployeeRole'):
            digest.update(name.encode())
            digest.update((self.data / (name + '.csv')).read_bytes())
        self.dataset_id = digest.hexdigest()
        self.managers = {r['employee_role_id']: r for r in read(self.data, 'EmployeeRole') if r['role'] == 'MANAGER'}
        self._initialize()

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _initialize(self):
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS Dataset(dataset_id TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS CaseRecord(
                dataset_id TEXT NOT NULL REFERENCES Dataset(dataset_id),
                investigation_id TEXT NOT NULL, alert_id TEXT NOT NULL,
                owner_employee_role_id TEXT NOT NULL, status TEXT NOT NULL,
                outcome TEXT NOT NULL, opened_at TEXT NOT NULL, closed_at TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(dataset_id, investigation_id), UNIQUE(dataset_id, alert_id),
                CHECK(status IN ('OPEN','IN_PROGRESS','CLOSED')));
            CREATE TABLE IF NOT EXISTS AuditEvent(
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_id TEXT NOT NULL, investigation_id TEXT NOT NULL,
                action TEXT NOT NULL, from_status TEXT NOT NULL, to_status TEXT NOT NULL,
                event_ts TEXT NOT NULL, outcome TEXT NOT NULL,
                owner_employee_role_id TEXT NOT NULL, actor_employee_role_id TEXT NOT NULL,
                note TEXT NOT NULL,
                FOREIGN KEY(dataset_id,investigation_id) REFERENCES CaseRecord(dataset_id,investigation_id));
            CREATE INDEX IF NOT EXISTS audit_case ON AuditEvent(dataset_id,investigation_id,event_id);
            CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON AuditEvent
                BEGIN SELECT RAISE(ABORT,'Audit history is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON AuditEvent
                BEGIN SELECT RAISE(ABORT,'Audit history is append-only'); END;
            ''')
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM Dataset WHERE dataset_id=?', (self.dataset_id,)).fetchone():
                return
            cases = list(read(self.data, 'Investigation'))
            events = list(read(self.data, 'InvestigationEvent'))
            alerts = {r['alert_id'] for r in read(self.data, 'ShrinkageAlert')}
            if any(c['alert_id'] not in alerts or c['owner_employee_role_id'] not in self.managers for c in cases):
                raise ValueError('Invalid source investigation alert or manager')
            db.execute('INSERT INTO Dataset VALUES (?)', (self.dataset_id,))
            for c in cases:
                db.execute('INSERT INTO CaseRecord VALUES (?,?,?,?,?,?,?,?,0)',
                           (self.dataset_id, c['investigation_id'], c['alert_id'], c['owner_employee_role_id'], c['status'], c['outcome'], c['opened_at'], c['closed_at']))
            owners = {c['investigation_id']: c['owner_employee_role_id'] for c in cases}
            for e in sorted(events, key=lambda e: (e['event_ts'], e['event_id'])):
                owner = owners[e['investigation_id']]
                db.execute('INSERT INTO AuditEvent(dataset_id,investigation_id,action,from_status,to_status,event_ts,outcome,owner_employee_role_id,actor_employee_role_id,note) VALUES (?,?,?,?,?,?,?,?,?,?)',
                           (self.dataset_id,e['investigation_id'],'CREATE' if not e['from_status'] else 'TRANSITION',e['from_status'],e['to_status'],e['event_ts'],e['outcome'],owner,owner,'Imported generated history'))

    def cases(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM CaseRecord WHERE dataset_id=? ORDER BY investigation_id',(self.dataset_id,))]

    def case(self, investigation_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM CaseRecord WHERE dataset_id=? AND investigation_id=?',(self.dataset_id,investigation_id)).fetchone()
            if row is None:
                raise ValueError('Unknown investigation')
            return dict(row)

    def history(self, investigation_id):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM AuditEvent WHERE dataset_id=? AND investigation_id=? ORDER BY event_id',(self.dataset_id,investigation_id))]

    def update(self, investigation_id, *, expected_version, actor, owner, target, outcome='', note=''):
        if actor not in self.managers or owner not in self.managers:
            raise ValueError('Actor and owner must be valid managers')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM CaseRecord WHERE dataset_id=? AND investigation_id=?',(self.dataset_id,investigation_id)).fetchone()
            if row is None:
                raise ValueError('Unknown investigation')
            c = dict(row)
            if c['version'] != expected_version:
                raise ConflictError('This investigation changed. Reload it before saving.')
            if c['status'] == 'CLOSED':
                raise ValueError('Closed investigations are read-only')
            transition = target != c['status']
            if transition and NEXT.get(c['status']) != target:
                raise ValueError('Follow OPEN -> IN_PROGRESS -> CLOSED')
            if not transition and owner == c['owner_employee_role_id']:
                raise ValueError('Choose a new owner or advance the status')
            if target == 'CLOSED' and (outcome not in OUTCOMES or not note.strip()):
                raise ValueError('Closing requires a valid outcome and investigation notes')
            if target != 'CLOSED' and outcome:
                raise ValueError('Outcomes can only be set when closing')
            # Persist UTC instants in the same naive ISO format as generated history.
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            latest = db.execute('SELECT MAX(event_ts) FROM AuditEvent WHERE dataset_id=? AND investigation_id=?',(self.dataset_id,investigation_id)).fetchone()[0]
            stamp = max(now, datetime.fromisoformat(latest) + timedelta(microseconds=1)).isoformat(timespec='microseconds')
            db.execute('UPDATE CaseRecord SET owner_employee_role_id=?,status=?,outcome=?,closed_at=?,version=version+1 WHERE dataset_id=? AND investigation_id=?',
                       (owner,target,outcome,stamp if target=='CLOSED' else '',self.dataset_id,investigation_id))
            db.execute('INSERT INTO AuditEvent(dataset_id,investigation_id,action,from_status,to_status,event_ts,outcome,owner_employee_role_id,actor_employee_role_id,note) VALUES (?,?,?,?,?,?,?,?,?,?)',
                       (self.dataset_id,investigation_id,'TRANSITION' if transition else 'ASSIGN',c['status'],target,stamp,outcome,owner,actor,note.strip()))
        return self.case(investigation_id)
