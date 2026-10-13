"""Prospective validation of immutable forecasts; neutral probability benchmarks."""
import math
from datetime import datetime,timezone
from . import store

def report(sport,mode,path=None):
    ledger=store.ledger(sport,mode,path);rows=ledger['forecasts'];groups={'ml':[],'total':[]}
    if sport=='ucl':groups['btts']=[]
    dates=set()
    for r in rows:
        if not r['result']:continue
        dates.add(r['start'][:10])
        for kind in groups:
            sides=('home','away','draw') if kind=='ml' and sport=='ucl' else ('home','away') if kind=='ml' else ('over','under') if kind=='total' else ('btts_yes','btts_no')
            markets=[m for n in sides for m in r['markets'] if m['name']==n]
            if any(m['outcome']=='push' for m in markets):continue
            mass=sum(m['probability'] for m in markets)
            if mass<=0:continue
            ps=[m['probability']/mass for m in markets];ys=[int(m['outcome']=='win') for m in markets]
            if sum(ys)!=1:continue
            base=1/len(ps)
            groups[kind].append((sum((p-y)**2 for p,y in zip(ps,ys)),-math.log(max(1e-12,ps[ys.index(1)])),sum((base-y)**2 for y in ys),-math.log(base)))
    scores={}
    for kind,values in groups.items():
        scores[kind]={'samples':len(values),'model_brier':sum(x[0] for x in values)/len(values) if values else None,'model_log_loss':sum(x[1] for x in values)/len(values) if values else None,'baseline_brier':sum(x[2] for x in values)/len(values) if values else None,'baseline_log_loss':sum(x[3] for x in values)/len(values) if values else None}
    return {'generated':store.now(),'mode':mode,'settled_dates':len(dates),'recorded':len(rows),'pending':sum(not r['result'] for r in rows),'first_capture':min((r['captured'] for r in rows),default=None),'status':'Collecting prospective evidence' if len(dates)<28 or any(x['samples']<100 for x in scores.values()) else 'Review eligible; not proof of profitability','benchmarks':scores,'note':'Same settled games: uniform home/away/draw for UCL ML; equal probabilities for two-way markets. Brier is the sum across outcomes; lower Brier and log loss are better. Pushes excluded. These results do not establish a betting edge. Target: 28 settled dates and 100 games per market before review. Demo results are not evidence.'}
