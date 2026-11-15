"""Inventory alert review and persistent investigation dashboard."""
import json
import os
import sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st
from src.dashboard import filter_alerts, exposure
from src.workflow import Workflow, OUTCOMES, NEXT

DATA = Path(os.environ.get('INVENTORY_DATA_DIR', Path(__file__).parent / 'data' / 'generated'))
st.set_page_config(page_title='Inventory Shrinkage Detection', layout='wide')
st.title('Inventory Shrinkage Detection')
st.caption('Review inventory exceptions, inspect evidence, and track investigations. Alerts are leads, not proof of theft.')

@st.cache_data(show_spinner=False)
def read_csv(path, signature):
    return pd.read_csv(path, keep_default_na=False)

def load(name):
    p = DATA / f'{name}.csv'
    return read_csv(str(p), (p.stat().st_mtime_ns, p.stat().st_size)) if p.exists() else pd.DataFrame()

@st.cache_data(show_spinner=False, max_entries=32)
def movement_details(path, signature, ids):
    frames = []
    for chunk in pd.read_csv(path, keep_default_na=False, chunksize=100000):
        found = chunk[chunk['movement_id'].isin(ids)]
        if not found.empty: frames.append(found)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

alerts, counts, stores, skus = (load(n) for n in ('ShrinkageAlert','CycleCount','Store','SKU'))
if not (DATA / 'ShrinkageAlert.csv').exists():
    st.warning('Generate data first: py src/generate_data.py --profile starter')
    st.stop()
if alerts.empty:
    st.info('This dataset has no detected alerts.')
    st.stop()
try:
    workflow = Workflow(DATA, os.environ.get('INVENTORY_WORKFLOW_DB'))
    cases = pd.DataFrame(workflow.cases())
except (ValueError, sqlite3.Error, OSError) as error:
    st.error(f'Unable to load investigations: {error}')
    st.stop()
if not cases.empty:
    alerts = alerts.drop(columns=['status']).merge(cases[['alert_id','investigation_id','owner_employee_role_id','status']],on='alert_id',how='left').fillna('')
manifest_path = DATA / 'manifest.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
summary_cols = st.columns(4)
for col,label,value in zip(summary_cols,['Stores','SKUs','Movements','Alerts'],[len(stores),len(skus),manifest.get('tables',{}).get('InventoryMovement',{}).get('rows',0),len(alerts)]):
    col.metric(label,f'{value:,}')

report_path = DATA / 'evaluation_report.json'
validation_path = DATA / 'validation_summary.json'
if validation_path.exists():
    validation = json.loads(validation_path.read_text(encoding='utf-8'))
    st.caption(f"Generated dataset validation: {validation['status']} | Unexpected errors: {len(validation['errors'])}")
if report_path.exists():
    report = json.loads(report_path.read_text(encoding='utf-8'))
    with st.expander('Synthetic benchmark results'):
        cols = st.columns(4)
        for col,label,key in zip(cols,['Precision','Recall','F1','False positives'],['precision','recall','f1','fp']):
            value = report['overall'][key]
            col.metric(label,f'{value:.1%}' if key in ('precision','recall') else f'{value:.3f}' if key=='f1' else value)
        st.dataframe(pd.DataFrame(report['per_issue']).T, width='stretch')
        st.caption('Controlled synthetic benchmark; real-world accuracy needs separate evaluation.')

st.subheader('Find alerts')
a,b,c = st.columns(3)
with a:
    store = st.selectbox('Store',['All']+sorted(alerts['store_id'].unique()),key='filter_store')
    severity = st.selectbox('Severity',['All']+sorted(alerts['severity'].unique()),key='filter_severity')
with b:
    sku = st.selectbox('SKU',['All']+sorted(alerts['sku_id'].unique()),key='filter_sku')
    reason = st.selectbox('Reason',['All']+sorted(alerts['reason_code'].unique()),key='filter_reason')
with c:
    status = st.selectbox('Investigation status',['All','OPEN','IN_PROGRESS','CLOSED'],key='filter_status')
    dates = pd.to_datetime(alerts['created_at'],format='ISO8601').dt.date
    date_range = st.date_input('Alert date range',value=(dates.min(),dates.max()),key='filter_dates')
if len(date_range)!=2:
    st.info('Choose both the start and end date.')
    st.stop()
view = filter_alerts(alerts,store=store,sku=sku,severity=severity,reason=reason,status=status,start=date_range[0],end=date_range[1])
a,b,c = st.columns(3)
a.metric('Matching alerts',f'{len(view):,}')
b.metric('Estimated exposure (INR)',f'{exposure(view):,.2f}')
c.metric('Active investigations',f"{int(view['status'].isin(['OPEN','IN_PROGRESS']).sum()):,}")
st.caption('Exposure groups repeated alerts for one event and paired transfers. It is an amount to review, not confirmed loss; separate related events may still overlap.')
if view.empty:
    st.info('No alerts match these filters. Broaden the filters to review investigations.')
    st.stop()
a,b = st.columns(2)
with a: st.bar_chart(view['severity'].value_counts())
with b: st.bar_chart(view['reason_code'].value_counts())
st.dataframe(view.head(250),width='stretch',hide_index=True)
st.caption(f'Showing the first {min(len(view),250):,} rows. The download includes all {len(view):,} matching alerts.')
st.download_button('Download filtered alerts (CSV)',view.to_csv(index=False).encode('utf-8'),'inventory_alerts.csv','text/csv',key='download_alerts')
st.download_button('Download review summary (JSON)',json.dumps({'filters':{'store':store,'sku':sku,'severity':severity,'reason':reason,'status':status,'start':str(date_range[0]),'end':str(date_range[1])},'matching_alerts':len(view),'estimated_exposure_inr':exposure(view),'active_investigations':int(view['status'].isin(['OPEN','IN_PROGRESS']).sum()),'exposure_note':'Event and transfer deduplicated review exposure, not confirmed loss.'},indent=2),'review_summary.json','application/json')

st.subheader('Review an alert')
selected = st.selectbox('Alert ID',view['alert_id'].tolist(),key='selected_alert')
alert = view[view['alert_id']==selected].iloc[0]
st.write(f"**{alert['reason_code']}** | {alert['severity']} | {alert['store_id']} | {alert['sku_id']}")
evidence = json.loads(alert['evidence'])
st.json(evidence,expanded=True)
ids = {alert['movement_id']} if alert['movement_id'] else set()
ids.update(evidence.get('movement_ids',[]))
ids.update(r['id'] for r in evidence.get('movements',[]))
if alert['count_id']:
    count_view = counts[counts['count_id']==alert['count_id']]
    st.dataframe(count_view,width='stretch',hide_index=True)
    ids.update(count_view['reference_movement_id'].tolist())
if st.checkbox('Load linked inventory records',key='load_evidence') and ids:
    p = DATA / 'InventoryMovement.csv'
    with st.spinner('Loading source evidence...'):
        st.dataframe(movement_details(str(p),(p.stat().st_mtime_ns,p.stat().st_size),tuple(sorted(ids))),width='stretch',hide_index=True)

if not alert.get('investigation_id',''):
    st.warning('No investigation is linked to this alert. Regenerate downstream investigation records.')
    st.stop()
case = workflow.case(alert['investigation_id'])
st.subheader('Investigation')
st.write(f"**{case['investigation_id']}** | Status: **{case['status']}** | Owner: **{case['owner_employee_role_id']}**")
if case['status']=='CLOSED':
    st.success(f"Closed: {case['outcome']}")
else:
    suffix = f"{case['investigation_id']}_{case['version']}"
    with st.form('update_'+suffix):
        managers = sorted(workflow.managers)
        actor = st.selectbox('Acting manager (demo identity)',managers,key='actor_'+suffix)
        owner = st.selectbox('Assign owner',managers,index=managers.index(case['owner_employee_role_id']),key='owner_'+suffix)
        target = st.selectbox('Next status',[case['status'],NEXT[case['status']]],key='target_'+suffix)
        outcome = st.selectbox('Resolution (required when closing)',['']+list(OUTCOMES),key='outcome_'+suffix)
        note = st.text_area('Investigation notes (required when closing)',key='note_'+suffix)
        submitted = st.form_submit_button('Save investigation')
    if submitted:
        try:
            workflow.update(case['investigation_id'],expected_version=case['version'],actor=actor,owner=owner,target=target,outcome=outcome,note=note)
            st.session_state['saved_notice'] = f"Saved {case['investigation_id']} as {target}."
            st.rerun()
        except (ValueError,sqlite3.Error) as error:
            st.error(str(error))
if notice := st.session_state.pop('saved_notice',None): st.success(notice)
history = pd.DataFrame(workflow.history(case['investigation_id'])).drop(columns=['dataset_id'])
st.dataframe(history,width='stretch',hide_index=True)
st.download_button('Download investigation history (CSV)',history.to_csv(index=False).encode('utf-8'),case['investigation_id']+'_history.csv','text/csv')
st.caption('History is append-only. Live audit times use UTC. The acting-manager selector is a demo identity, not authentication.')
