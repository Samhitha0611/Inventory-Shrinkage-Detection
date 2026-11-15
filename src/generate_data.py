"""Generate source evidence; ground truth never enters operational tables."""
import argparse
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path
from common import DEFAULT_OUT, read, write, manifest
START=datetime(2026,1,1,8)
def generate(out,profile,seed):
    out=Path(out); out.mkdir(parents=True,exist_ok=True); rng=random.Random(seed)
    for name in ('validation_summary.json','evaluation_report.json','reproducibility_check.json'):
        (out/name).unlink(missing_ok=True)
    ns,nk,nm,nc=(100,5000,1000000,20000) if profile=='full' else (10,100,10000,500)
    stores=[dict(store_id=f'STORE-{i:06d}',store_name=f'Store {i:03d}',city=['Hyderabad','Pune','Delhi'][(i-1)%3],region=['SOUTH','WEST','NORTH'][(i-1)%3],store_type='WAREHOUSE' if i%10==0 else 'RETAIL',active=True) for i in range(1,ns+1)]
    skus=[dict(sku_id=f'SKU-{i:06d}',sku_name=f'Product {i:05d}',category=['GROCERY','HOME','APPAREL','ELECTRONICS'][i%4],unit_cost_inr=round(rng.uniform(20,2500),2),unit_price_inr=0,active=True) for i in range(1,nk+1)]
    for s in skus: s['unit_price_inr']=round(s['unit_cost_inr']*rng.uniform(1.15,1.8),2)
    roles=[dict(employee_role_id=f'ROLE-{i:04d}',employee_id=f'EMP-{i:05d}',role=r) for i,r in enumerate(['STORE_OPERATOR','MANAGER','ANALYST','WAREHOUSE_OPERATOR','MANAGER'],1)]
    shifts=[dict(shift_id=f"SHIFT-{s['store_id'][-6:]}-{d+1:03d}",store_id=s['store_id'],shift_date=(START+timedelta(days=d)).date().isoformat(),start_time='08:00',end_time='20:00',shift_name='DAY') for s in stores for d in range(7)]
    promos=[dict(promotion_id=f'PROMO-{i:06d}',sku_id=skus[i-1]['sku_id'],start_date='2026-01-01',end_date='2026-01-07',discount_pct=10) for i in range(1,max(2,nk//20)+1)]
    balances={(s['store_id'],k['sku_id']):rng.randint(30,100) for s in stores for k in skus}
    for name,rows in [('Store',stores),('SKU',skus),('EmployeeRole',roles),('Shift',shifts),('Promotion',promos),('StoreSKUOpeningBalance',(dict(store_id=s,sku_id=k,opening_qty=v) for (s,k),v in balances.items()))]: write(out,name,rows)
    truth=[]; returns=[]; repeated_key=None; pending=None; last_by_key={}; snapshots={}; previous_sale={}; remaining_sale={}
    fields=['movement_id','store_id','sku_id','movement_type','quantity','signed_qty','movement_ts','reason','employee_role_id','shift_id','promotion_id','transfer_id','related_movement_id']
    def label(rid,issue,decision): truth.append(dict(record_id=rid,issue_type=issue,expected_label='ANOMALY',expected_decision=decision))
    def event_time(i): return START+timedelta(days=(i-1)//200000,seconds=((i-1)%200000)*43200/200000)
    with (out/'InventoryMovement.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for i in range(1,nm+1):
            sid=rng.choice(stores)['store_id']; kid=rng.choice(skus)['sku_id']; key=(sid,kid)
            ts=event_time(i); day=(ts.date()-START.date()).days+1
            typ=rng.choices(['SALE','RECEIPT','DAMAGE','RETURN','ADJUSTMENT'],[60,22,7,5,6])[0]
            qty=rng.randint(1,5); reason={'SALE':'','RECEIPT':'SUPPLIER_RECEIPT','DAMAGE':'DAMAGED_GOODS','RETURN':'CUSTOMER_RETURN','ADJUSTMENT':'STOCK_CORRECTION'}[typ]
            issue=None; transfer=''; related=''
            if pending:
                sid,kid,qty,transfer,related,broken=pending; key=(sid,kid); typ='TRANSFER_IN'; reason='STORE_TRANSFER'; pending=None
                if broken: issue='TRANSFER_DOUBLE_COUNT_RISK'
            elif i%50==0 and i<nm:
                typ='TRANSFER_OUT'; reason='STORE_TRANSFER'; transfer=f'TRF-2026-{i:08d}'; related=f'MOV-2026-{i+1:08d}'
                dest=stores[int(sid[-6:])%ns]['store_id']; broken=i%1000==0
                qty=min(qty,balances[key],balances[(dest,kid)])
                if qty==0: qty=1; typ='RECEIPT'; reason='LOW_STOCK_REPLENISHMENT'; transfer=''; related=''
                else:
                    pending=(dest,kid,qty,transfer,f'MOV-2026-{i:08d}',broken)
                    if broken: issue='TRANSFER_DOUBLE_COUNT_RISK'
            elif i%4000 in (11,12,13):
                if i%4000==11: repeated_key=key
                sid,kid=repeated_key; key=(sid,kid); typ='ADJUSTMENT'; qty=1; reason='STOCK_CORRECTION'; issue='REPEATED_ADJUSTMENTS'
            elif i%997==0: typ='ADJUSTMENT'; reason=''; issue='MISSING_ADJUSTMENT_REASON'
            elif i%1291==0: issue='WRONG_STORE_REFERENCE'
            if typ=='RETURN':
                if remaining_sale.get(key,0)<=0: typ='RECEIPT'; reason='SUPPLIER_RECEIPT'
                else: qty=min(qty,remaining_sale[key]); remaining_sale[key]-=qty
            signed=qty if typ in ('RECEIPT','RETURN','TRANSFER_IN') else -qty
            if typ=='TRANSFER_IN' and issue=='TRANSFER_DOUBLE_COUNT_RISK': signed=-qty
            if signed<0 and balances[key]<qty: typ='RECEIPT'; reason='LOW_STOCK_REPLENISHMENT'; signed=qty; issue=None
            rid=f'MOV-2026-{i:08d}'
            shift_sid=stores[int(sid[-6:])%ns]['store_id'] if issue=='WRONG_STORE_REFERENCE' else sid
            row=dict(zip(fields,[rid,sid,kid,typ,qty,signed,ts.isoformat(timespec='microseconds'),reason,'ROLE-0002' if typ=='ADJUSTMENT' else 'ROLE-0001',f'SHIFT-{shift_sid[-6:]}-{day:03d}','',transfer,related]))
            if typ=='SALE': previous_sale[key]=rid; remaining_sale[key]=qty
            if typ=='RETURN': returns.append(dict(return_id=f'RET-2026-{len(returns)+1:06d}',store_id=sid,sku_id=kid,original_sale_movement_id=previous_sale[key],movement_id=rid,quantity=qty,condition='SELLABLE',return_ts=row['movement_ts']))
            snapshots[key]=(balances[key],row['movement_ts'],rid)
            balances[key]+=signed; last_by_key[key]=row
            if issue: label(rid,issue,{'WRONG_STORE_REFERENCE':'QUARANTINE_INVALID_STORE','TRANSFER_DOUBLE_COUNT_RISK':'RECONCILE_TRANSFER_PAIR','REPEATED_ADJUSTMENTS':'REVIEW_ADJUSTMENT_PATTERN','MISSING_ADJUSTMENT_REASON':'FLAG_MISSING_REASON'}[issue])
            elif typ in ('DAMAGE','RETURN'): truth.append(dict(record_id=rid,issue_type='LEGITIMATE_'+typ,expected_label='BENIGN',expected_decision='ACCEPT_WITH_REASON'))
            w.writerow(row)
    counts=[]; end=event_time(nm)+timedelta(hours=1); keys=list(last_by_key)
    for i in range(1,nc+1):
        sid,kid=rng.choice(keys); key=(sid,kid); expected=balances[key]; counted=max(0,expected+rng.choice([-2,-1,0,0,0,1,2])); ts=end+timedelta(seconds=i); reference=last_by_key[key]['movement_id']; cid=f'CNT-2026-{i:06d}'
        if i==1:
            expected,raw_ts,reference=snapshots[key]; ts=datetime.fromisoformat(raw_ts)-timedelta(microseconds=1); counted=expected; label(cid,'COUNT_BEFORE_MOVEMENT','REVIEW_EVENT_ORDER')
        elif i%101==0 and expected>=5:
            counted=expected-min(expected,rng.randint(5,15)); label(cid,'UNEXPLAINED_COUNT_SHORTAGE','INVESTIGATE_SHORTAGE')
        counts.append(dict(count_id=cid,store_id=sid,sku_id=kid,count_ts=ts.isoformat(timespec='microseconds'),expected_qty=expected,counted_qty=counted,variance_qty=counted-expected,employee_role_id='ROLE-0002',reference_movement_id=reference))
    write(out,'CycleCount',counts)
    write(out,'Return',returns,['return_id','store_id','sku_id','original_sale_movement_id','movement_id','quantity','condition','return_ts'])
    write(out,'ground_truth',truth)
    from detect_anomalies import detect
    detect(out)
    alerts=list(read(out,'ShrinkageAlert'))
    investigations=[dict(investigation_id=f'INV-2026-{i:06d}',alert_id=a['alert_id'],owner_employee_role_id='ROLE-0002',status='OPEN',outcome='',opened_at=a['created_at'],closed_at='') for i,a in enumerate(alerts,1)]
    write(out,'Investigation',investigations)
    write(out,'InvestigationEvent',[dict(event_id=f'IEV-{i:08d}',investigation_id=r['investigation_id'],from_status='',to_status='OPEN',event_ts=r['opened_at'],outcome='') for i,r in enumerate(investigations,1)])
    manifest(out,seed,profile)
    print(f'Generated {profile}: {nm:,} movements, {nc:,} counts, {len(alerts):,} alerts in {out}')
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--profile',choices=['starter','full'],default='starter'); p.add_argument('--seed',type=int,default=20261022); p.add_argument('--out',type=Path,default=DEFAULT_OUT); a=p.parse_args(); generate(a.out,a.profile,a.seed)
