"""Strict operational validation with separately accounted planted exceptions."""
import argparse
import json
from collections import Counter
from pathlib import Path
from common import DEFAULT_OUT, read, save_json, PERMISSIONS
from database import load_database, TABLES
KEYS={'Store':'store_id','SKU':'sku_id','EmployeeRole':'employee_role_id','Shift':'shift_id','Promotion':'promotion_id','InventoryMovement':'movement_id','CycleCount':'count_id','Return':'return_id','ShrinkageAlert':'alert_id','Investigation':'investigation_id','InvestigationEvent':'event_id'}
def validate(out):
    db=load_database(out); truth=list(read(out,'ground_truth'))
    allowed={'WRONG_STORE_REFERENCE','MISSING_ADJUSTMENT_REASON','TRANSFER_DOUBLE_COUNT_RISK','COUNT_BEFORE_MOVEMENT'}
    expected={(r['record_id'],r['issue_type']) for r in truth if r['issue_type'] in allowed and r['expected_label']=='ANOMALY'}
    observed=set(); errors=[]; checks=[]; exceptions=Counter()
    def check(name,sql,exception=None):
        n=0
        for row in db.execute(sql):
            n+=1; rid=str(row[0]); code=exception or name
            if exception and (rid,code) in expected:
                observed.add((rid,code)); exceptions[code]+=1
            elif len(errors)<100: errors.append({'check':name,'record_id':rid,'details':list(row[1:])})
        checks.append({'check':name,'violations':n})
    for table,key in KEYS.items():
        check(table+'_primary_key',f'SELECT "{key}",COUNT(*) FROM "{table}" GROUP BY "{key}" HAVING COUNT(*)>1 OR "{key}"=""')
    check('opening_composite_key','SELECT store_id,sku_id FROM StoreSKUOpeningBalance GROUP BY store_id,sku_id HAVING COUNT(*)>1')
    refs={
      'Shift':[('store_id','Store','store_id')], 'Promotion':[('sku_id','SKU','sku_id')],
      'StoreSKUOpeningBalance':[('store_id','Store','store_id'),('sku_id','SKU','sku_id')],
      'InventoryMovement':[('store_id','Store','store_id'),('sku_id','SKU','sku_id'),('employee_role_id','EmployeeRole','employee_role_id'),('shift_id','Shift','shift_id'),('promotion_id','Promotion','promotion_id'),('related_movement_id','InventoryMovement','movement_id')],
      'CycleCount':[('store_id','Store','store_id'),('sku_id','SKU','sku_id'),('employee_role_id','EmployeeRole','employee_role_id'),('reference_movement_id','InventoryMovement','movement_id')],
      'Return':[('store_id','Store','store_id'),('sku_id','SKU','sku_id'),('movement_id','InventoryMovement','movement_id'),('original_sale_movement_id','InventoryMovement','movement_id')],
      'ShrinkageAlert':[('store_id','Store','store_id'),('sku_id','SKU','sku_id'),('movement_id','InventoryMovement','movement_id'),('count_id','CycleCount','count_id')],
      'Investigation':[('alert_id','ShrinkageAlert','alert_id'),('owner_employee_role_id','EmployeeRole','employee_role_id')],
      'InvestigationEvent':[('investigation_id','Investigation','investigation_id')]}
    optional={'promotion_id','related_movement_id'}
    for table,items in refs.items():
        for col,parent,pk in items:
            nullable=col in optional or (table=='ShrinkageAlert' and col in ('movement_id','count_id'))
            where=f'a."{col}"<>\'\' AND ' if nullable else ''
            key=KEYS.get(table,'store_id')
            check(f'{table}_{col}_FK',f'SELECT a."{key}",a."{col}" FROM "{table}" a LEFT JOIN "{parent}" b ON a."{col}"=b."{pk}" WHERE {where}b."{pk}" IS NULL')
    integer_fields={'StoreSKUOpeningBalance':['opening_qty'],'InventoryMovement':['quantity','signed_qty'],'CycleCount':['expected_qty','counted_qty','variance_qty'],'Return':['quantity']}
    for table,columns in integer_fields.items():
        for col in columns:
            check(f'{table}_{col}_integer',f'SELECT "{KEYS.get(table,"store_id")}" FROM "{table}" WHERE CAST(CAST("{col}" AS INTEGER) AS TEXT)<>"{col}"')
    check('count_authorization',"SELECT c.count_id FROM CycleCount c JOIN EmployeeRole e USING(employee_role_id) WHERE e.role NOT IN ('MANAGER','STORE_OPERATOR','WAREHOUSE_OPERATOR')")
    check('movement_promotion',"SELECT m.movement_id FROM InventoryMovement m JOIN Promotion p USING(promotion_id) WHERE m.sku_id<>p.sku_id OR SUBSTR(m.movement_ts,1,10)<p.start_date OR SUBSTR(m.movement_ts,1,10)>p.end_date")
    check('event_timestamp',"SELECT event_id FROM InvestigationEvent WHERE julianday(event_ts) IS NULL")
    check('investigation_timestamp',"SELECT investigation_id FROM Investigation WHERE julianday(opened_at) IS NULL OR (closed_at<>'' AND julianday(closed_at) IS NULL)")
    check('alert_timestamp',"SELECT alert_id FROM ShrinkageAlert WHERE julianday(created_at) IS NULL")
    check('return_timestamp',"SELECT return_id FROM \"Return\" WHERE julianday(return_ts) IS NULL")
    check('movement_timestamp',"SELECT movement_id FROM InventoryMovement WHERE julianday(movement_ts) IS NULL")
    check('count_timestamp',"SELECT count_id FROM CycleCount WHERE julianday(count_ts) IS NULL")
    check('shift_interval',"SELECT shift_id FROM Shift WHERE date(shift_date) IS NULL OR time(start_time) IS NULL OR time(end_time) IS NULL OR start_time>=end_time")
    check('movement_enum',"SELECT movement_id FROM InventoryMovement WHERE movement_type NOT IN ('SALE','RECEIPT','RETURN','DAMAGE','TRANSFER_IN','TRANSFER_OUT','ADJUSTMENT')")
    check('movement_quantity_sign',"SELECT movement_id FROM InventoryMovement WHERE CAST(quantity AS INTEGER)<=0 OR ABS(CAST(signed_qty AS INTEGER))<>CAST(quantity AS INTEGER) OR (movement_type IN ('SALE','DAMAGE','TRANSFER_OUT') AND CAST(signed_qty AS INTEGER)>=0) OR (movement_type IN ('RECEIPT','RETURN','TRANSFER_IN') AND CAST(signed_qty AS INTEGER)<=0)",'TRANSFER_DOUBLE_COUNT_RISK')
    check('missing_adjustment_reason',"SELECT movement_id FROM InventoryMovement WHERE movement_type='ADJUSTMENT' AND TRIM(reason)=''",'MISSING_ADJUSTMENT_REASON')
    check('wrong_store',"SELECT m.movement_id,m.store_id,s.store_id FROM InventoryMovement m JOIN Shift s USING(shift_id) WHERE m.store_id<>s.store_id",'WRONG_STORE_REFERENCE')
    check('shift_time',"SELECT m.movement_id FROM InventoryMovement m JOIN Shift s USING(shift_id) WHERE SUBSTR(m.movement_ts,1,10)<>s.shift_date OR SUBSTR(m.movement_ts,12,8)<s.start_time||':00' OR SUBSTR(m.movement_ts,12,8)>s.end_time||':00'")
    for role,types in PERMISSIONS.items():
        quoted=','.join("'"+t+"'" for t in sorted(types)) or "''"
        check('authorization_'+role,f"SELECT m.movement_id FROM InventoryMovement m JOIN EmployeeRole e USING(employee_role_id) WHERE e.role='{role}' AND m.movement_type NOT IN ({quoted})")
    check('role_enum',"SELECT employee_role_id FROM EmployeeRole WHERE role NOT IN ('STORE_OPERATOR','MANAGER','ANALYST','WAREHOUSE_OPERATOR')")
    check('opening_qty',"SELECT store_id,sku_id FROM StoreSKUOpeningBalance WHERE CAST(opening_qty AS INTEGER)<0")
    check('movement_opening_pair',"SELECT m.movement_id FROM InventoryMovement m LEFT JOIN StoreSKUOpeningBalance o USING(store_id,sku_id) WHERE o.store_id IS NULL")
    check('negative_running_stock',"SELECT movement_id,balance FROM (SELECT m.movement_id, CAST(o.opening_qty AS INTEGER)+SUM(CAST(m.signed_qty AS INTEGER)) OVER (PARTITION BY m.store_id,m.sku_id ORDER BY m.movement_ts,m.movement_id ROWS UNBOUNDED PRECEDING) balance FROM InventoryMovement m JOIN StoreSKUOpeningBalance o USING(store_id,sku_id)) WHERE balance<0")
    check('count_arithmetic',"SELECT count_id FROM CycleCount WHERE CAST(variance_qty AS INTEGER)<>CAST(counted_qty AS INTEGER)-CAST(expected_qty AS INTEGER) OR CAST(counted_qty AS INTEGER)<0 OR CAST(expected_qty AS INTEGER)<0")
    check('count_as_of_reconciliation',"SELECT c.count_id,c.expected_qty FROM CycleCount c LEFT JOIN StoreSKUOpeningBalance o USING(store_id,sku_id) WHERE o.store_id IS NULL OR CAST(c.expected_qty AS INTEGER)<>CAST(o.opening_qty AS INTEGER)+COALESCE((SELECT SUM(CAST(m.signed_qty AS INTEGER)) FROM InventoryMovement m WHERE m.store_id=c.store_id AND m.sku_id=c.sku_id AND m.movement_ts<=c.count_ts),0)")
    check('count_reference_pair',"SELECT c.count_id FROM CycleCount c JOIN InventoryMovement m ON m.movement_id=c.reference_movement_id WHERE c.store_id<>m.store_id OR c.sku_id<>m.sku_id")
    check('count_reference_time',"SELECT c.count_id FROM CycleCount c JOIN InventoryMovement m ON m.movement_id=c.reference_movement_id WHERE c.count_ts<m.movement_ts",'COUNT_BEFORE_MOVEMENT')
    check('transfer_pair',"SELECT m.movement_id,m.transfer_id FROM InventoryMovement m LEFT JOIN InventoryMovement p ON m.related_movement_id=p.movement_id WHERE (m.movement_type IN ('TRANSFER_IN','TRANSFER_OUT') OR m.transfer_id<>'') AND (m.transfer_id='' OR p.movement_id IS NULL OR m.transfer_id<>p.transfer_id OR m.movement_id<>p.related_movement_id OR m.store_id=p.store_id OR m.sku_id<>p.sku_id OR CAST(m.signed_qty AS INTEGER)+CAST(p.signed_qty AS INTEGER)<>0 OR m.quantity<>p.quantity OR m.movement_type=p.movement_type OR (SELECT COUNT(*) FROM InventoryMovement t WHERE t.transfer_id=m.transfer_id)<>2)",'TRANSFER_DOUBLE_COUNT_RISK')
    check('return_link',"SELECT r.return_id FROM \"Return\" r JOIN InventoryMovement m ON r.movement_id=m.movement_id JOIN InventoryMovement s ON r.original_sale_movement_id=s.movement_id WHERE m.movement_type<>'RETURN' OR s.movement_type<>'SALE' OR m.store_id<>r.store_id OR m.sku_id<>r.sku_id OR s.store_id<>r.store_id OR s.sku_id<>r.sku_id OR r.quantity<>m.quantity OR r.return_ts<>m.movement_ts OR s.movement_ts>r.return_ts OR r.condition NOT IN ('SELLABLE','DAMAGED')")
    check('return_exceeds_sale',"SELECT r.original_sale_movement_id FROM \"Return\" r JOIN InventoryMovement s ON s.movement_id=r.original_sale_movement_id GROUP BY r.original_sale_movement_id HAVING SUM(CAST(r.quantity AS INTEGER))>CAST(s.quantity AS INTEGER)")
    check('return_coverage',"SELECT m.movement_id FROM InventoryMovement m LEFT JOIN \"Return\" r ON m.movement_id=r.movement_id WHERE m.movement_type='RETURN' GROUP BY m.movement_id HAVING COUNT(r.return_id)<>1")
    check('promotion',"SELECT promotion_id FROM Promotion WHERE start_date>end_date OR CAST(discount_pct AS REAL)<0 OR CAST(discount_pct AS REAL)>80")
    check('sku_money',"SELECT sku_id FROM SKU WHERE CAST(unit_cost_inr AS REAL)<0 OR CAST(unit_price_inr AS REAL)<0")
    check('store_enum',"SELECT store_id FROM Store WHERE store_type NOT IN ('RETAIL','WAREHOUSE') OR active NOT IN ('True','False')")
    check('alert_values',"SELECT alert_id FROM ShrinkageAlert WHERE severity NOT IN ('LOW','MEDIUM','HIGH') OR status NOT IN ('OPEN','IN_PROGRESS','CLOSED') OR CAST(risk_score AS REAL)<0 OR CAST(risk_score AS REAL)>1 OR evidence='' OR ((movement_id='')=(count_id=''))")
    check('alert_movement_pair',"SELECT a.alert_id FROM ShrinkageAlert a JOIN InventoryMovement m USING(movement_id) WHERE a.store_id<>m.store_id OR a.sku_id<>m.sku_id")
    check('alert_count_pair',"SELECT a.alert_id FROM ShrinkageAlert a JOIN CycleCount c USING(count_id) WHERE a.store_id<>c.store_id OR a.sku_id<>c.sku_id")
    check('investigation_alert_unique',"SELECT alert_id FROM Investigation GROUP BY alert_id HAVING COUNT(*)>1")
    check('investigation_lifecycle',"SELECT investigation_id FROM Investigation WHERE status NOT IN ('OPEN','IN_PROGRESS','CLOSED') OR (status='CLOSED' AND (outcome='' OR closed_at='' OR closed_at<opened_at)) OR (status<>'CLOSED' AND (closed_at<>'' OR outcome<>''))")
    check('investigation_owner',"SELECT i.investigation_id FROM Investigation i JOIN EmployeeRole e ON i.owner_employee_role_id=e.employee_role_id WHERE e.role<>'MANAGER'")
    check('investigation_history',"SELECT i.investigation_id FROM Investigation i LEFT JOIN InvestigationEvent e USING(investigation_id) GROUP BY i.investigation_id HAVING COUNT(e.event_id)=0")
    check('event_transition',"SELECT event_id FROM InvestigationEvent WHERE NOT ((from_status='' AND to_status='OPEN') OR (from_status='OPEN' AND to_status='IN_PROGRESS') OR (from_status='IN_PROGRESS' AND to_status='CLOSED')) OR (to_status='CLOSED' AND outcome='')")
    for r in db.execute('SELECT investigation_id,status,opened_at,closed_at,outcome FROM Investigation'):
        history=list(db.execute('SELECT from_status,to_status,event_ts,outcome FROM InvestigationEvent WHERE investigation_id=? ORDER BY event_ts,event_id',(r[0],)))
        state=''; prev=r[2]
        for before,after,ts,outcome in history:
            if before!=state or ts<prev or (state=='' and ts!=r[2]): errors.append({'check':'history_sequence','record_id':r[0]}); break
            state=after; prev=ts
        if state!=r[1] or (state=='CLOSED' and (prev!=r[3] or history[-1][3]!=r[4])): errors.append({'check':'history_final_state','record_id':r[0]})
    missing=expected-observed
    for rid,code in sorted(missing): errors.append({'check':'planted_exception_not_present','record_id':rid,'issue':code})
    counts={n:db.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in TABLES}
    # Labels are forbidden in operational schemas, including issue_type proxies.
    for n in TABLES:
        cols={r[1] for r in db.execute(f'PRAGMA table_info("{n}")')}
        if cols & {'issue_type','expected_label','expected_decision','ground_truth'}: errors.append({'check':'label_leakage','table':n})
    result={'status':'PASS' if not errors else 'FAIL','errors':errors,'error_output_limit':100,'expected_exception_counts':dict(Counter(code for _,code in observed)),'missing_expected_exceptions':len(missing),'checks':checks,'row_counts':counts,'ground_truth_rows':len(truth),'policy':'PASS requires no unexpected violations; exact planted record/rule exceptions must be observed. Count expected quantities reconcile at count timestamps.'}
    save_json(out,'validation_summary',result); db.close(); return result
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--out',type=Path,default=DEFAULT_OUT); a=p.parse_args(); r=validate(a.out); print(json.dumps(r,indent=2)); raise SystemExit(r['status']!='PASS')
