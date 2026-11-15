import csv
import hashlib
import json
from pathlib import Path
DEFAULT_OUT = Path(__file__).resolve().parents[1] / 'data' / 'generated'
PERMISSIONS = {'STORE_OPERATOR': {'SALE','RECEIPT','RETURN','DAMAGE','TRANSFER_IN','TRANSFER_OUT'}, 'MANAGER': {'SALE','RECEIPT','RETURN','DAMAGE','TRANSFER_IN','TRANSFER_OUT','ADJUSTMENT'}, 'ANALYST': set(), 'WAREHOUSE_OPERATOR': {'RECEIPT','RETURN','DAMAGE','TRANSFER_IN','TRANSFER_OUT'}}
def read(out, name):
    with (Path(out)/(name+'.csv')).open(encoding='utf-8-sig',newline='') as f:
        yield from csv.DictReader(f)
def write(out,name,rows,fields=None):
    rows=iter(rows); first=next(rows,None); fields=fields or (list(first) if first else [])
    with (Path(out)/(name+'.csv')).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        if first is not None: w.writerow(first)
        w.writerows(rows)
def save_json(out,name,value):
    (Path(out)/(name+'.json')).write_text(json.dumps(value,indent=2),encoding='utf-8')
def manifest(out,seed,profile):
    tables={}
    for p in sorted(Path(out).glob('*.csv')):
        h=hashlib.sha256()
        with p.open('rb') as f:
            for chunk in iter(lambda:f.read(1048576),b''): h.update(chunk)
        with p.open(encoding='utf-8',newline='') as f: count=sum(1 for _ in csv.reader(f))-1
        tables[p.stem]={'rows':count,'sha256':h.hexdigest()}
    save_json(out,'manifest',{'seed':seed,'profile':profile,'tables':tables})
