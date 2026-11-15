"""Pure dashboard filtering and event-deduplicated exposure calculations."""
import pandas as pd

def filter_alerts(alerts, *, store='All', sku='All', severity='All', reason='All', status='All', start=None, end=None):
    view = alerts.copy()
    for col,value in [('store_id',store),('sku_id',sku),('severity',severity),('reason_code',reason),('status',status)]:
        if value != 'All': view = view[view[col] == value]
    dates = pd.to_datetime(view['created_at'], format='ISO8601').dt.date
    if start is not None: view = view[dates >= start]
    if end is not None: view = view[pd.to_datetime(view['created_at'],format='ISO8601').dt.date <= end]
    return view

def exposure(view):
    # Several rules can refer to one event, and both rows of a transfer can alert.
    # Use the maximum exposure per evidence group, never sum the pair twice.
    groups = {}
    import json
    for r in view.to_dict('records'):
        evidence = json.loads(r['evidence'])
        key = evidence.get('transfer_id') or r['movement_id'] or r['count_id']
        groups[key] = max(groups.get(key,0),float(r['exposure_inr']))
    return round(sum(groups.values()),2)
