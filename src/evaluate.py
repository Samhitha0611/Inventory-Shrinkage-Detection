"""Evaluate predictions after detection; all movements/counts form the population."""
import argparse
from collections import Counter
from pathlib import Path
from common import DEFAULT_OUT, read, save_json

def evaluate(out):
    truth=list(read(out,'ground_truth')); alerts=list(read(out,'ShrinkageAlert'))
    positive={r['record_id'] for r in truth if r['expected_label']=='ANOMALY'}
    predicted={r['movement_id'] or r['count_id'] for r in alerts}
    population={r['movement_id'] for r in read(out,'InventoryMovement')} | {r['count_id'] for r in read(out,'CycleCount')}
    if not positive<=population or not predicted<=population: raise ValueError('Evaluation references missing records')
    def scores(tp,fp,fn,tn):
        p=tp/(tp+fp) if tp+fp else 0; r=tp/(tp+fn) if tp+fn else 0
        return dict(tp=tp,fp=fp,fn=fn,tn=tn,precision=p,recall=r,f1=2*p*r/(p+r) if p+r else 0,false_positive_rate=fp/(fp+tn) if fp+tn else 0)
    report={'evaluation_unit':'record (movement or count)','population':len(population),'label_policy':'All unplanted records are synthetic negatives; explicit benign damage and returns are also audited.','overall':scores(len(positive&predicted),len(predicted-positive),len(positive-predicted),len(population-positive-predicted)),'per_issue':{},'benign':{}}
    for issue in sorted({r['issue_type'] for r in truth if r['expected_label']=='ANOMALY'} | {r['reason_code'] for r in alerts}):
        actual={r['record_id'] for r in truth if r['expected_label']=='ANOMALY' and r['issue_type']==issue}; guess={r['movement_id'] or r['count_id'] for r in alerts if r['reason_code']==issue}
        report['per_issue'][issue]=scores(len(actual&guess),len(guess-actual),len(actual-guess),len(population-actual-guess))
    for issue in sorted({r['issue_type'] for r in truth if r['expected_label']=='BENIGN'}):
        ids={r['record_id'] for r in truth if r['expected_label']=='BENIGN' and r['issue_type']==issue}; report['benign'][issue]={'records':len(ids),'false_positives':len(ids&predicted),'false_positive_rate':len(ids&predicted)/len(ids) if ids else 0}
    report['limitations']='Synthetic rule-based benchmark; does not establish real-world detection accuracy or theft.'
    save_json(out,'evaluation_report',report); return report
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--out',type=Path,default=DEFAULT_OUT); a=p.parse_args(); print(evaluate(a.out)['overall'])
