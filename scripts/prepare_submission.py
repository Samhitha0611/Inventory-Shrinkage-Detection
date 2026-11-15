"""Prepare a runnable sample and a shareable source/documentation ZIP."""
import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def run(script,*args):
    subprocess.run([sys.executable,str(ROOT/script),*args],cwd=ROOT,check=True)
def main():
    p=argparse.ArgumentParser(); p.add_argument('--skip-sample',action='store_true',help='Repackage an already validated sample'); a=p.parse_args()
    sample=ROOT/'examples/sample'
    if not a.skip_sample:
        run('src/generate_data.py','--profile','starter','--out',str(sample))
        run('src/validate_data.py','--out',str(sample))
        run('src/evaluate.py','--out',str(sample))
        run('src/check_reproducibility.py','--profile','starter','--out',str(sample))
    checks=json.loads((sample/'validation_summary.json').read_text())
    assert checks['status']=='PASS', 'Sample must pass validation'
    run('scripts/build_documentation.py')
    paths=[]
    for name in ('README.md','app.py','requirements.txt','requirements-dev.txt','test_pipeline.py','test_workflow.py','test_app.py','.gitignore'):
        paths.append(ROOT/name)
    for directory in ('src','scripts','docs'):
        paths.extend(p for p in (ROOT/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py','.md','.sql','.json','.png'))
    paths.append(ROOT/'examples/README.md')
    paths.extend(p for p in sample.iterdir() if p.suffix in ('.csv','.json'))
    # Preserve full-run evidence without including the million-row source data.
    for name in ('manifest.json','validation_summary.json','evaluation_report.json','reproducibility_check.json'):
        paths.append(ROOT/'data/generated'/name)
    artifacts=ROOT/'artifacts'; artifacts.mkdir(exist_ok=True)
    archive=artifacts/'inventory_shrinkage_submission.zip'
    hashes={}
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path in sorted(set(paths)):
            contents=path.read_bytes(); name=path.relative_to(ROOT).as_posix()
            if name.startswith('data/generated/'): name='verification/full/'+path.name
            z.writestr(name,contents); hashes[name]=hashlib.sha256(contents).hexdigest()
        z.writestr('SUBMISSION_MANIFEST.json',json.dumps({'files':hashes,'excluded':'Virtual environment, live workflow databases, full-size CSVs, credentials and temporary artifacts.'},indent=2))
    print(f'Submission package: {archive} ({archive.stat().st_size:,} bytes, {len(hashes)} files)')
if __name__=='__main__': main()
