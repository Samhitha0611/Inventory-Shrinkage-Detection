"""Build complete field documentation from the exported CSV schema."""
import csv
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/generated'
PK={'Store':'store_id','SKU':'sku_id','EmployeeRole':'employee_role_id','Shift':'shift_id','Promotion':'promotion_id','InventoryMovement':'movement_id','CycleCount':'count_id','Return':'return_id','ShrinkageAlert':'alert_id','Investigation':'investigation_id','InvestigationEvent':'event_id'}
RULES={
'store_id':'Existing Store primary key; STORE- plus six digits.',
'store_name':'Nonempty synthetic store display name.', 'city':'Nonempty city; synthetic geography aligned with region.', 'region':'SOUTH, WEST or NORTH in this generator.', 'store_type':'RETAIL or WAREHOUSE.', 'active':'True or False; master records are active in generated snapshots.',
'sku_id':'Existing SKU primary key; SKU- plus six digits.', 'sku_name':'Nonempty synthetic product name.', 'category':'GROCERY, HOME, APPAREL or ELECTRONICS.', 'unit_cost_inr':'Nonnegative acquisition cost, rounded to two decimal places.', 'unit_price_inr':'Nonnegative selling price; generated above cost, rounded to two decimal places.',
'employee_role_id':'Existing EmployeeRole primary key; ROLE- plus four digits.', 'employee_id':'Unique synthetic employee identifier; EMP- plus five digits.', 'role':'Permitted role enum; movement and count permissions follow BUSINESS_RULES.md.',
'shift_id':'Existing Shift primary key; linked store must match movement store.', 'shift_date':'Valid YYYY-MM-DD date.', 'start_time':'Valid HH:MM time; strictly earlier than end_time.', 'end_time':'Valid HH:MM time; strictly after start_time.', 'shift_name':'DAY in generated data.',
'promotion_id':'Existing Promotion key when provided; movement SKU/date must match its promotion.', 'start_date':'Valid YYYY-MM-DD date; not after end_date.', 'end_date':'Valid YYYY-MM-DD date; not before start_date.', 'discount_pct':'Between 0 and 80 inclusive.',
'opening_qty':'Integer >= 0; initial stock for this unique store/SKU pair.',
'movement_id':'Existing InventoryMovement key; MOV-2026- plus eight digits.', 'movement_type':'Permitted movement enum; direction must agree with signed_qty except declared double-debit injections.', 'quantity':'Positive integer units; absolute signed_qty for movement rows.', 'signed_qty':'Nonzero signed integer; magnitude equals quantity. Stock at any time uses the signed ledger.', 'movement_ts':'Valid ISO-8601 timestamp within the linked store shift.', 'reason':'Required for adjustment; damage, receipt, return and transfer have documented reasons; sale may be empty.', 'transfer_id':'Required for transfer types; groups exactly two reciprocal rows; empty for non-transfers.', 'related_movement_id':'Required for paired transfers; reciprocal InventoryMovement link; same SKU and different store.',
'count_id':'Existing CycleCount key; CNT-2026- plus six digits.', 'count_ts':'Valid ISO-8601 timestamp. Expected stock includes only movements at or before this time.', 'expected_qty':'Integer >= 0; opening plus signed ledger at count_ts.', 'counted_qty':'Integer >= 0; observed physical quantity.', 'variance_qty':'Integer equal to counted_qty minus expected_qty.', 'reference_movement_id':'Required InventoryMovement FK; same store/SKU and timestamp <= count_ts, except declared order anomaly.',
'return_id':'Unique RET-2026- plus six digits.', 'original_sale_movement_id':'Required earlier SALE of the same store/SKU. Cumulative returns cannot exceed sale quantity.', 'condition':'SELLABLE or DAMAGED. Current generator produces SELLABLE returns; damage uses separate DAMAGE movements.', 'return_ts':'Valid ISO-8601 timestamp equal to linked RETURN movement timestamp.',
'alert_id':'Existing ShrinkageAlert key; SHR-2026- plus six digits.', 'reason_code':'Evidence-based detector rule code.', 'severity':'LOW, MEDIUM or HIGH; current detector emits MEDIUM or HIGH by exposure.', 'risk_score':'Real in [0,1]; ordinal tiers, not calibrated probabilities.', 'status':'OPEN, IN_PROGRESS or CLOSED. CSV alert status is an initial snapshot; live dashboard derives status from its investigation.', 'created_at':'Valid ISO-8601 source-event timestamp.', 'evidence':'Required valid JSON object containing source IDs, conflicting values or thresholds.', 'exposure_inr':'Nonnegative affected units multiplied by unit cost, rounded to two decimals; not confirmed loss.',
'investigation_id':'Existing Investigation key; INV-2026- plus six digits.', 'owner_employee_role_id':'Required EmployeeRole FK with MANAGER role.', 'outcome':'Required for CLOSED; empty while active. Live enum: CONFIRMED_LOSS, PROCESS_ERROR, LEGITIMATE_VARIANCE, INCONCLUSIVE.', 'opened_at':'Valid ISO-8601 timestamp equal to the initial creation event.', 'closed_at':'Required for CLOSED, >= opened_at and equal to closing event time; otherwise empty.',
'event_id':'Unique immutable event identifier; generated CSV uses IEV- plus eight digits.', 'from_status':'Empty only on creation; otherwise preceding state in the event history.', 'to_status':'OPEN, IN_PROGRESS or CLOSED; valid generated transitions are creation -> OPEN -> IN_PROGRESS -> CLOSED.', 'event_ts':'Valid chronological ISO-8601 timestamp; final transition must agree with case snapshot.',
'record_id':'Existing movement_id or count_id in the evaluation population.', 'issue_type':'Known planted anomaly family or explicit LEGITIMATE_DAMAGE / LEGITIMATE_RETURN.', 'expected_label':'ANOMALY or BENIGN; evaluation-only.', 'expected_decision':'Documented expected rule decision; evaluation-only.',
'dataset_id':'SHA-256 of alerts, initial investigations/events and roles; isolates each baseline dataset.', 'version':'Nonnegative integer; incremented once per committed live update; optimistic concurrency token.', 'action':'CREATE, ASSIGN or TRANSITION. ASSIGN preserves state while changing owner.', 'actor_employee_role_id':'EmployeeRole FK with MANAGER role; demo acting identity, not authenticated login.', 'note':'Free text; nonempty investigation notes required when closing.'}
ENUMS={'store_type':['RETAIL','WAREHOUSE'],'active':['True','False'],'region':['SOUTH','WEST','NORTH'],'category':['GROCERY','HOME','APPAREL','ELECTRONICS'],'role':['STORE_OPERATOR','MANAGER','ANALYST','WAREHOUSE_OPERATOR'],'movement_type':['SALE','RECEIPT','RETURN','DAMAGE','ADJUSTMENT','TRANSFER_IN','TRANSFER_OUT'],'condition':['SELLABLE','DAMAGED'],'severity':['LOW','MEDIUM','HIGH'],'status':['OPEN','IN_PROGRESS','CLOSED'],'from_status':['','OPEN','IN_PROGRESS'],'to_status':['OPEN','IN_PROGRESS','CLOSED'],'expected_label':['ANOMALY','BENIGN'],'action':['CREATE','ASSIGN','TRANSITION'],'shift_name':['DAY']}
INTEGERS={'opening_qty','quantity','signed_qty','expected_qty','counted_qty','variance_qty','version'}
REALS={'unit_cost_inr','unit_price_inr','discount_pct','risk_score','exposure_inr'}
FOREIGN={'store_id':'Store.store_id','sku_id':'SKU.sku_id','employee_role_id':'EmployeeRole.employee_role_id','shift_id':'Shift.shift_id','promotion_id':'Promotion.promotion_id','movement_id':'InventoryMovement.movement_id','related_movement_id':'InventoryMovement.movement_id','reference_movement_id':'InventoryMovement.movement_id','original_sale_movement_id':'InventoryMovement.movement_id','count_id':'CycleCount.count_id','alert_id':'ShrinkageAlert.alert_id','owner_employee_role_id':'EmployeeRole.employee_role_id','investigation_id':'Investigation.investigation_id','actor_employee_role_id':'EmployeeRole.employee_role_id'}

def build():
    dictionary={}
    for p in sorted(DATA.glob('*.csv')):
        with p.open(encoding='utf-8-sig',newline='') as f: fields=next(csv.reader(f))
        rows=[]
        for field in fields:
            rule=RULES[field]
            kind='integer' if field in INTEGERS else 'decimal' if field in REALS else 'boolean' if field=='active' else 'JSON object' if field=='evidence' else 'ISO timestamp' if field.endswith('_ts') or field in ('created_at','opened_at','closed_at') else 'date' if field in ('shift_date','start_date','end_date') else 'time' if field in ('start_time','end_time') else 'string'
            requirement='required'
            if field in ('reason','transfer_id','related_movement_id','outcome','closed_at','from_status'): requirement='conditional (see rule)'
            if field=='promotion_id' and p.stem=='InventoryMovement': requirement='optional'
            if p.stem=='ShrinkageAlert' and field in ('movement_id','count_id'): requirement='exactly one of movement_id / count_id'
            unique='primary key' if PK.get(p.stem)==field else 'unique' if field=='employee_id' else 'part of composite PK' if p.stem=='StoreSKUOpeningBalance' and field in ('store_id','sku_id') else 'not unique'
            fk=FOREIGN.get(field) if PK.get(p.stem)!=field else None
            if p.stem=='ground_truth': fk='InventoryMovement.movement_id or CycleCount.count_id' if field=='record_id' else None
            units='INR' if field.endswith('_inr') else 'units' if field in INTEGERS-{'version'} else 'percent' if field=='discount_pct' else 'dimensionless' if field=='risk_score' else 'n/a'
            rows.append(dict(field=field,type=kind,requirement=requirement,allowed_values=ENUMS.get(field,'See validation rule'),units=units,uniqueness=unique,foreign_key=fk,validation=rule))
        dictionary[p.stem]=rows
    # Live database fields, separate from deterministic CSV snapshots.
    for name,fields in {'LiveDataset':['dataset_id'],'LiveCaseRecord':['dataset_id','investigation_id','alert_id','owner_employee_role_id','status','outcome','opened_at','closed_at','version'],'LiveAuditEvent':['event_id','dataset_id','investigation_id','action','from_status','to_status','event_ts','outcome','owner_employee_role_id','actor_employee_role_id','note']}.items():
        rows=[]
        for field in fields:
            kind='integer' if field in ('version','event_id') else 'ISO timestamp' if field.endswith('_ts') or field.endswith('_at') else 'string'
            unique='primary key' if (name=='LiveDataset' or (name=='LiveAuditEvent' and field=='event_id')) else 'composite PK with dataset_id' if name=='LiveCaseRecord' and field in ('dataset_id','investigation_id') else 'unique within dataset' if name=='LiveCaseRecord' and field=='alert_id' else 'not unique'
            rule=RULES[field]
            if name=='LiveAuditEvent' and field=='event_id': rule='SQLite AUTOINCREMENT integer; immutable and unique across dataset namespaces.'
            if field in ('from_status','to_status'): rule+=' Live ASSIGN events preserve the status.'
            rows.append(dict(field=field,type=kind,requirement='conditional (see rule)' if field in ('outcome','closed_at','from_status','note') else 'required',allowed_values=ENUMS.get(field,'See validation rule'),units='n/a',uniqueness=unique,foreign_key='LiveDataset.dataset_id' if field=='dataset_id' and name!='LiveDataset' else 'LiveCaseRecord (dataset_id, investigation_id)' if field=='investigation_id' and name=='LiveAuditEvent' else FOREIGN.get(field) if field not in ('investigation_id','alert_id') else 'source CSV identifier',validation=rule))
        dictionary[name]=rows
    (ROOT/'docs/data_dictionary.json').write_text(json.dumps(dictionary,indent=2),encoding='utf-8')
    lines=['# Data dictionary','','CSV empty strings represent absent conditional/optional fields; convert optional foreign keys to SQL NULL on import. CSV booleans True/False map to SQL 1/0. Quantities are whole units; money is INR. Generated timestamps are fictional naive ISO-8601 values; live audit updates are stored as UTC ISO values without a suffix for compatibility.','','Every field below documents the data contract. The validator checks structural/accounting rules and reports exact planted exceptions separately. Master snapshots do not model effective-dated role or store history; Promotion and Shift have explicit effective dates. Refer to [relationships](ER_DIAGRAM.md) and [business rules](BUSINESS_RULES.md).','']
    for table,rows in dictionary.items():
        lines.extend(['## '+table,'','| Field | Type | Required | Allowed values | Units | Uniqueness | FK / validation |','|---|---|---|---|---|---|---|'])
        for r in rows:
            allowed=', '.join(r['allowed_values']) if isinstance(r['allowed_values'],list) else r['allowed_values']
            lines.append('| '+' | '.join([r['field'],r['type'],r['requirement'],allowed,r['units'],r['uniqueness'],((r['foreign_key']+'; ') if r['foreign_key'] else '')+r['validation']])+' |')
        lines.append('')
    lines.extend(['Live tables use the same namespace-scoped case IDs as source CSVs. Source CSVs stay immutable during review. SQLite protects audit events against UPDATE/DELETE; the service serializes writes and checks a version token. Generated and live snapshots have separate validation scopes.','','Ground truth is an evaluation-only sidecar and is never an operational feature or dashboard input.'])
    (ROOT/'docs/DATA_DICTIONARY.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Documented',sum(map(len,dictionary.values())),'fields across',len(dictionary),'tables')
if __name__=='__main__': build()
