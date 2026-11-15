"""Load operational CSVs into an indexed scratch SQLite DB, never ground truth."""
import csv
import sqlite3
from pathlib import Path
TABLES=['Store','SKU','EmployeeRole','Shift','Promotion','StoreSKUOpeningBalance','InventoryMovement','CycleCount','Return','ShrinkageAlert','Investigation','InvestigationEvent']
def load_database(out):
    db=sqlite3.connect(':memory:'); db.execute('PRAGMA temp_store=MEMORY')
    for name in TABLES:
        with (Path(out)/(name+'.csv')).open(encoding='utf-8-sig',newline='') as f:
            reader=csv.reader(f); fields=next(reader)
            db.execute('CREATE TABLE "'+name+'" ('+','.join('"'+x+'" TEXT' for x in fields)+')')
            query='INSERT INTO "'+name+'" VALUES ('+','.join('?' for _ in fields)+')'
            batch=[]
            for row in reader:
                batch.append(row)
                if len(batch)==10000: db.executemany(query,batch); batch=[]
            if batch: db.executemany(query,batch)
    for table,cols in [('InventoryMovement','store_id,sku_id,movement_ts'),('InventoryMovement','movement_id'),('InventoryMovement','transfer_id'),('Shift','shift_id'),('Store','store_id'),('SKU','sku_id'),('EmployeeRole','employee_role_id'),('Promotion','promotion_id'),('CycleCount','count_id'),('ShrinkageAlert','alert_id'),('Investigation','investigation_id'),('InvestigationEvent','investigation_id'),('StoreSKUOpeningBalance','store_id,sku_id')]: db.execute(f'CREATE INDEX "idx_{table}_{cols.replace(",","_")}" ON "{table}" ({cols})')
    return db
