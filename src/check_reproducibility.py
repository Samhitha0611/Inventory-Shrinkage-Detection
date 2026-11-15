"""Regenerate twice in isolated temporary directories; preserve the active dataset."""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from common import DEFAULT_OUT, save_json
BASE=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser(); p.add_argument('--profile',choices=['starter','full'],default='starter'); p.add_argument('--seed',type=int,default=20261022); p.add_argument('--out',type=Path,default=DEFAULT_OUT); a=p.parse_args()
    runs=[]
    with tempfile.TemporaryDirectory(prefix='inventory_repro_') as root:
        for i in (1,2):
            dest=Path(root)/str(i)
            subprocess.run([sys.executable,str(BASE/'src/generate_data.py'),'--profile',a.profile,'--seed',str(a.seed),'--out',str(dest)],check=True)
            runs.append(json.loads((dest/'manifest.json').read_text(encoding='utf-8')))
    result={'reproducible':runs[0]==runs[1],'profile':a.profile,'seed':a.seed,'first_run':runs[0],'second_run':runs[1]}
    a.out.mkdir(parents=True,exist_ok=True); save_json(a.out,'reproducibility_check',result)
    print('PASS: identical row counts and checksums' if result['reproducible'] else 'FAIL: outputs differ')
    raise SystemExit(not result['reproducible'])
if __name__=='__main__': main()
