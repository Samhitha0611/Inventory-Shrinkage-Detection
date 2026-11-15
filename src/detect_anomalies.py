"""Evidence-based rules. This module deliberately never reads ground_truth.csv."""
import argparse
import json
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from common import DEFAULT_OUT, read, write, PERMISSIONS
ALERT_FIELDS=['alert_id','store_id','sku_id','movement_id','count_id','reason_code','severity','risk_score','status','created_at','evidence','exposure_inr']
def detect(out):
    out=Path(out); stores={r['store_id'] for r in read(out,'Store')}; shifts={r['shift_id']:r for r in read(out,'Shift')}; roles={r['employee_role_id']:r['role'] for r in read(out,'EmployeeRole')}; costs={r['sku_id']:float(r['unit_cost_inr']) for r in read(out,'SKU')}
    counts=list(read(out,'CycleCount')); wanted={r['reference_movement_id'] for r in counts}; references={}; transfers=defaultdict(list); adjustments=defaultdict(deque); alerts={}
    def emit(r,code,evidence,count=False,qty=None):
        rid=r['count_id'] if count else r['movement_id']; exposure=abs(int(r.get('variance_qty',r.get('signed_qty','0'))) if qty is None else qty)*costs.get(r['sku_id'],0)
        alerts[(rid,code)]=dict(alert_id='',store_id=r['store_id'],sku_id=r['sku_id'],movement_id='' if count else rid,count_id=rid if count else '',reason_code=code,severity='HIGH' if exposure>=1000 else 'MEDIUM',risk_score=0.9 if exposure>=1000 else 0.6,status='OPEN',created_at=r['count_ts'] if count else r['movement_ts'],evidence=json.dumps(evidence,sort_keys=True),exposure_inr=round(exposure,2))
    for r in read(out,'InventoryMovement'):
        rid=r['movement_id']; typ=r['movement_type']; s=shifts.get(r['shift_id']); ts=datetime.fromisoformat(r['movement_ts'])
        if rid in wanted: references[rid]=r
        if r['store_id'] not in stores or (s and s['store_id']!=r['store_id']): emit(r,'WRONG_STORE_REFERENCE',{'movement_store':r['store_id'],'shift_store':s['store_id'] if s else None,'shift_id':r['shift_id']})
        if s and (s['shift_date']!=ts.date().isoformat() or not s['start_time']<=ts.strftime('%H:%M:%S')<=s['end_time']+':00'): emit(r,'OUTSIDE_SHIFT',{'shift_id':r['shift_id'],'movement_ts':r['movement_ts']})
        if typ not in PERMISSIONS.get(roles.get(r['employee_role_id']),set()): emit(r,'UNAUTHORIZED_MOVEMENT',{'role':roles.get(r['employee_role_id']),'movement_type':typ})
        if typ=='ADJUSTMENT':
            if not r['reason'].strip(): emit(r,'MISSING_ADJUSTMENT_REASON',{'reason':r['reason'],'signed_qty':r['signed_qty']})
            if int(r['signed_qty'])<0:
                q=adjustments[(r['store_id'],r['sku_id'])]
                while q and (ts-datetime.fromisoformat(q[0]['movement_ts'])).total_seconds()>60: q.popleft()
                q.append(r)
                if len(q)>=3:
                    ids=[a['movement_id'] for a in q]
                    for a in q: emit(a,'REPEATED_ADJUSTMENTS',{'window_seconds':60,'movement_ids':ids,'threshold':3})
        if r['transfer_id']: transfers[r['transfer_id']].append(r)
        elif typ.startswith('TRANSFER_'): emit(r,'TRANSFER_DOUBLE_COUNT_RISK',{'error':'Missing transfer ID'})
    for tid,pair in transfers.items():
        valid=len(pair)==2 and {r['movement_type'] for r in pair}=={'TRANSFER_IN','TRANSFER_OUT'}
        if valid:
            a,b=pair; valid=a['store_id']!=b['store_id'] and a['sku_id']==b['sku_id'] and int(a['signed_qty'])+int(b['signed_qty'])==0 and a['quantity']==b['quantity'] and a['related_movement_id']==b['movement_id'] and b['related_movement_id']==a['movement_id']
        if not valid:
            for r in pair: emit(r,'TRANSFER_DOUBLE_COUNT_RISK',{'transfer_id':tid,'movements':[{'id':a['movement_id'],'type':a['movement_type'],'store_id':a['store_id'],'quantity':a['quantity'],'signed_qty':a['signed_qty']} for a in pair]})
    for r in counts:
        ref=references.get(r['reference_movement_id'])
        if ref and r['count_ts']<ref['movement_ts']: emit(r,'COUNT_BEFORE_MOVEMENT',{'reference_movement_id':ref['movement_id'],'reference_ts':ref['movement_ts'],'count_ts':r['count_ts']},True)
        if int(r['variance_qty'])<=-5: emit(r,'UNEXPLAINED_COUNT_SHORTAGE',{'expected_qty':r['expected_qty'],'counted_qty':r['counted_qty'],'threshold_units':5},True)
    result=[]
    for i,(_,r) in enumerate(sorted(alerts.items()),1): r['alert_id']=f'SHR-2026-{i:06d}'; result.append(r)
    write(out,'ShrinkageAlert',result,ALERT_FIELDS)
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--out',type=Path,default=DEFAULT_OUT); a=p.parse_args(); print(f'Detected {len(detect(a.out))} alerts')
