"""Capture the actual dashboard and verify browser downloads using installed Edge.

Uses an isolated temporary workflow database, leaving user investigations intact.
Install requirements-dev.txt before running this optional script.
"""
import csv
import io
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]

def choose(page,label,value):
    field=page.get_by_test_id('stSelectbox').filter(has=page.get_by_text(label,exact=True)).get_by_role('combobox')
    field.click()
    page.get_by_role('option',name=value,exact=True).click()

def main():
    screenshots=ROOT/'docs/screenshots'; screenshots.mkdir(parents=True,exist_ok=True)
    with socket.socket() as sock: sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix='inventory_browser_') as temp:
        env=os.environ.copy(); env['INVENTORY_WORKFLOW_DB']=str(Path(temp)/'workflow.sqlite3'); env['INVENTORY_DATA_DIR']=str(ROOT/'data/generated')
        with (Path(temp)/'streamlit.log').open('w',encoding='utf-8') as log:
            server=subprocess.Popen([sys.executable,'-m','streamlit','run',str(ROOT/'app.py'),'--server.headless=true','--server.address=127.0.0.1',f'--server.port={port}','--browser.gatherUsageStats=false'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            try:
                url=f'http://127.0.0.1:{port}'
                for _ in range(100):
                    try:
                        with urllib.request.urlopen(url+'/_stcore/health',timeout=1) as response:
                            if response.status==200: break
                    except OSError: time.sleep(0.1)
                else: raise RuntimeError('Local dashboard did not start')
                with sync_playwright() as p:
                    browser=p.chromium.launch(channel='msedge',headless=True)
                    page=browser.new_page(viewport={'width':1440,'height':1100},device_scale_factor=1)
                    page.goto(url); page.get_by_text('Matching alerts',exact=True).wait_for(timeout=60000)
                    page.get_by_text('Review an alert',exact=True).wait_for()
                    page.get_by_test_id('stVegaLiteChart').first.locator('canvas, svg').first.wait_for(state='visible')
                    page.get_by_test_id('stVegaLiteChart').nth(1).locator('canvas, svg').first.wait_for(state='visible')
                    page.screenshot(path=str(screenshots/'01_overview.png'))
                    choose(page,'Reason','TRANSFER_DOUBLE_COUNT_RISK')
                    page.get_by_test_id('stMetric').filter(has=page.get_by_text('Matching alerts',exact=True)).get_by_text('1,998',exact=True).wait_for()
                    page.get_by_role('heading',name='Review an alert',exact=True).scroll_into_view_if_needed()
                    page.screenshot(path=str(screenshots/'02_transfer_evidence.png'))
                    with page.expect_download() as download:
                        page.get_by_text('Download filtered alerts (CSV)',exact=True).click()
                    csv_path=Path(temp)/'alerts.csv'; download.value.save_as(csv_path)
                    with csv_path.open(encoding='utf-8',newline='') as f: rows=list(csv.DictReader(f))
                    assert len(rows)==1998 and all(r['reason_code']=='TRANSFER_DOUBLE_COUNT_RISK' for r in rows)
                    with page.expect_download() as download:
                        page.get_by_text('Download review summary (JSON)',exact=True).click()
                    json_path=Path(temp)/'summary.json'; download.value.save_as(json_path)
                    assert json.loads(json_path.read_text())['matching_alerts']==1998
                    choose(page,'Next status','IN_PROGRESS'); page.get_by_role('button',name='Save investigation',exact=True).click()
                    page.get_by_text(re.compile('Saved .* as IN_PROGRESS')).wait_for()
                    choose(page,'Next status','CLOSED'); choose(page,'Resolution (required when closing)','PROCESS_ERROR')
                    page.get_by_role('textbox',name='Investigation notes (required when closing)').fill('Demo: reviewed paired transfer records and identified destination double debit. Requires inventory correction.')
                    page.get_by_role('button',name='Save investigation',exact=True).click()
                    page.get_by_text('Closed: PROCESS_ERROR',exact=True).wait_for()
                    page.get_by_role('heading',name='Investigation',exact=True).scroll_into_view_if_needed()
                    page.screenshot(path=str(screenshots/'03_closed_investigation.png'))
                    with page.expect_download() as download:
                        page.get_by_text('Download investigation history (CSV)',exact=True).click()
                    history=Path(temp)/'history.csv'; download.value.save_as(history)
                    with history.open(encoding='utf-8',newline='') as f: events=list(csv.DictReader(f))
                    assert len(events)==3 and events[-1]['to_status']=='CLOSED' and events[-1]['outcome']=='PROCESS_ERROR'
                    browser.close()
                print('Browser: filters, CSV/JSON downloads, investigation transitions and history export PASS')
                print('Saved real dashboard screenshots to',screenshots)
            finally:
                if os.name=='nt':
                    subprocess.run(['taskkill','/PID',str(server.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                else:
                    server.terminate()
                try: server.wait(timeout=10)
                except subprocess.TimeoutExpired: server.kill(); server.wait()
if __name__=='__main__': main()
