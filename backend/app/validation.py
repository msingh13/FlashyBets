from .sports import SOCCER
"""Prospective validation of immutable forecasts; neutral probability benchmarks."""
import math
from zoneinfo import ZoneInfo
from datetime import datetime,timezone
from . import store

def report(sport,mode,path=None):
    ledger=store.ledger(sport,mode,path);rows=ledger['forecasts'];groups={'ml':[],'total':[]}
    if sport in SOCCER:groups['btts']=[]
    dates=set()
    for r in rows:
        if not r['result']:continue
        dates.add(store.instant(r['start']).astimezone(ZoneInfo('America/Toronto')).date().isoformat())
        for kind in groups:
            sides=('home','away','draw') if kind=='ml' and sport in SOCCER else ('home','away') if kind=='ml' else ('over','under') if kind=='total' else ('btts_yes','btts_no')
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
    diagnostics=selection_diagnostics(rows,groups)
    return {'diagnostics':diagnostics,'generated':store.now(),'mode':mode,'settled_dates':len(dates),'recorded':len(rows),'pending':sum(not r['result'] for r in rows),'first_capture':min((r['captured'] for r in rows),default=None),'status':'Collecting prospective evidence' if len(dates)<28 or any(x['samples']<100 for x in scores.values()) else 'Review eligible; not proof of profitability','benchmarks':scores,'note':'Same settled games: uniform home/away/draw for UCL ML; equal probabilities for two-way markets. Brier is the sum across outcomes; lower Brier and log loss are better. Pushes excluded. These results do not establish a betting edge. Target: 28 settled dates and 100 games per market before review. Demo results are not evidence.'}


def wilson(wins,n):
    if not n:return None
    z=1.96;p=wins/n;den=1+z*z/n
    middle=(p+z*z/(2*n))/den;radius=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0,middle-radius),min(1,middle+radius)]

def selection_diagnostics(rows,groups):
    result={}
    for kind in groups:
        settled=[]
        for row in sorted(rows,key=lambda r:r['start']):
            pick=row.get('picks',{}).get(kind)
            if not pick or pick.get('outcome') not in ('win','loss'):continue
            names=('home','away','draw') if kind=='ml' else ('over','under') if kind=='total' else ('btts_yes','btts_no')
            mass=sum(m['probability'] for m in row['markets'] if m['name'] in names)
            if mass>0:settled.append(dict(pick,conditional=pick['probability']/mass))
        n=len(settled);wins=sum(x['outcome']=='win' for x in settled)
        bins=[]
        for lo,hi in [(0,.5),(.5,.6),(.6,.7),(.7,.8),(.8,1.000001)]:
            sample=[r for r in settled if lo<=r['conditional']<hi]
            if sample:bins.append({'range':f'{lo:.0%}–{min(hi,1):.0%}','samples':len(sample),'predicted':sum(r['conditional'] for r in sample)/len(sample),'observed':sum(r['outcome']=='win' for r in sample)/len(sample)})
        recent=settled[-30:]
        result[kind]={'samples':n,'wins':wins,'hit_rate':wins/n if n else None,'hit_rate_interval':wilson(wins,n),
            'recent_count':len(recent),'recent_hit_rate':sum(r['outcome']=='win' for r in recent)/len(recent) if recent else None,
            'priced':sum(r.get('odds') is not None for r in settled),'reliability':bins,
            'note':'95% Wilson interval describes hit-rate sampling uncertainty, not profit or the probability of an individual pick; games may be correlated. Reliability is conditional on no push.'}
    return result
