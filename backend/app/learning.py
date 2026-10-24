"""Daily, chronological temperature-calibration audit. No promise of daily improvement."""
import json,math
from datetime import datetime,timezone
from . import store
TEMPERATURES=(.5,.65,.8,1.,1.2,1.5,2.)
MIN_GAMES=100

def adjust(p,t):
    p=min(1-1e-9,max(1e-9,p))
    x=math.log(p/(1-p))/t
    return 1/(1+math.exp(-x))

def score(rows,t):
    brier=loss=0.
    for r in rows:
        p=adjust(r['p'],t);y=r['y'];brier+=(p-y)**2
        loss-=math.log(max(1e-12,p if y else 1-p))
    return {'brier':brier/len(rows),'log_loss':loss/len(rows)}

def active(sport,kind,path=None):
    with store.connect(path) as c:r=c.execute('SELECT * FROM model_versions WHERE sport=? AND kind=? AND active=1',(sport,kind)).fetchone()
    return dict(r) if r else {'version':'baseline','temperature':1.,'training_through':None}

def apply(g,path=None):
    p=g['prediction'];raw={n:p[n] for n in ('home','away','over','under')};p['raw']=raw
    versions={}
    if g['mode']=='live' and g['sport']!='ucl':
        for kind,sides in [('ml',('home','away')),('total',('over','under'))]:
            model=active(g['sport'],kind,path)
            if model.get('created') and store.instant(model['created'])>=store.instant(g['start']):model={'temperature':1.,'version':'baseline'}
            t=model['temperature'];versions[kind]=model['version']
            push=p.get('ml_push',0) if kind=='ml' else p['push'];mass=1-push
            p[sides[0]]=adjust(raw[sides[0]]/mass,t)*mass;p[sides[1]]=mass-p[sides[0]]
    p['calibration_versions']=versions
    if any(v!='baseline' for v in versions.values()):p['version']+=' / temperature-calibrated'

def audit(sport,day,path=None):
    if sport=='ucl':return []
    # Real prospective forecasts only; never learn from synthetic demo fixtures.
    with store.connect(path) as c:
        existing=c.execute('SELECT kind,payload FROM model_checks WHERE sport=? AND day=?',(sport,day)).fetchall()
        prior_checks=c.execute('SELECT payload FROM model_checks WHERE sport=? AND day<=?',(sport,day)).fetchall()
        forecasts=c.execute("SELECT * FROM forecasts WHERE sport=? AND mode='live' AND result IS NOT NULL ORDER BY start",(sport,)).fetchall()
    reports=[]
    for kind in ('ml','total'):
        rows=[]
        for f in forecasts:
            g=json.loads(f['payload']);r=json.loads(f['result']);p=g['prediction'];raw=p.get('raw',p)
            from zoneinfo import ZoneInfo
            if store.instant(f['start']).astimezone(ZoneInfo('America/Toronto')).date().isoformat()>=day:continue
            n='home' if kind=='ml' else 'over';result=store.outcome(n,r['home_score'],r['away_score'],g['reference_line'])
            if result=='push':continue
            push=p.get('ml_push',0) if kind=='ml' else p['push']
            rows.append({'p':raw[n]/(1-push),'y':int(result=='win'),'start':f['start'],
                'day':store.instant(f['start']).astimezone(ZoneInfo('America/Toronto')).date().isoformat()})
        report={'kind':kind,'day':day,'samples':len(rows),'status':'Collecting results','promoted':False,
          'evaluated_at':store.now(),'minimum':MIN_GAMES,'note':'No automatic guarantee of improvement. Synthetic games are excluded.'}
        watermarks=[json.loads(r['payload']).get('holdout_through') for r in prior_checks if json.loads(r['payload']).get('kind')==kind]
        watermarks=[x for x in watermarks if x]
        if watermarks:report['holdout_through']=max(watermarks,key=store.instant)
        distinct=sorted({r['day'] for r in rows})
        if len(rows)>=MIN_GAMES and len(distinct)>=10:
            split=distinct[max(1,int(len(distinct)*.7))];train=[r for r in rows if r['day']<split];valid=[r for r in rows if r['day']>=split]
            if len(train)>=60 and len(valid)>=20:
                used=[json.loads(r['payload']).get('holdout_through') for r in prior_checks if json.loads(r['payload']).get('kind')==kind]
                used=[x for x in used if x]
                cutoff=max(used,key=store.instant) if used else None
                if cutoff:
                    # Previously tested dates may train future candidates, but never test them again.
                    cutoff_day=store.instant(cutoff).astimezone(ZoneInfo('America/Toronto')).date().isoformat()
                    train=[r for r in rows if r['day']<=cutoff_day]
                    valid=[r for r in rows if r['day']>cutoff_day]
                if len(valid)<20 or len({r['day'] for r in valid})<2:
                    report.update(status='Waiting for fresh holdout',note='Need 20 new settled games across two new dates after the last promotion test; old holdout results are never reused.')
                    with store.connect(path) as c:c.execute('INSERT OR REPLACE INTO model_checks VALUES(?,?,?,?)',(sport,day,kind,json.dumps(report)))
                    reports.append(report)
                    continue
                champion=active(sport,kind,path)
                # Candidate selection uses only older dates; the newest dates are untouched holdout.
                candidate=min(TEMPERATURES,key=lambda t:score(train,t)['log_loss'])
                cs,old=score(valid,candidate),score(valid,champion['temperature'])
                clean=not champion['training_through'] or store.instant(champion['training_through'])<store.instant(valid[0]['start'])
                promoted=clean and cs['brier']<old['brier']-.002 and cs['log_loss']<old['log_loss']-1e-6
                report.update(status='Promoted update' if promoted else 'Current model retained',promoted=promoted,
                    training_count=len(train),holdout_count=len(valid),training_through=train[-1]['start'],holdout_from=valid[0]['start'],
                    holdout_through=valid[-1]['start'],candidate_temperature=candidate,champion_temperature=champion['temperature'],candidate=cs,champion=old,
                    note='Older dates fit the candidate; later dates compare Brier and log loss. This is a promotion check, not an independent final performance estimate.')
                if promoted:
                    version=f'{sport}-{kind}-temp-{day}'
                    with store.connect(path) as c:
                        c.execute('UPDATE model_versions SET active=0 WHERE sport=? AND kind=?',(sport,kind))
                        c.execute('INSERT OR REPLACE INTO model_versions VALUES(?,?,?,?,?,?,?,1)',
                          (version,sport,kind,candidate,store.now(),train[-1]['start'],json.dumps(report)))
                    report['version']=version
        with store.connect(path) as c:c.execute('INSERT OR REPLACE INTO model_checks VALUES(?,?,?,?)',(sport,day,kind,json.dumps(report)))
        reports.append(report)
    return reports

def status(sport,mode,path=None):
    if sport=='ucl':return {'status':'Baseline · collecting results','checks':[],'versions':{},'note':'Three-way and BTTS calibration need a separate chronological evaluation; binary moneyline calibration is not applied.'}
    if mode=='demo':return {'status':'Demo · learning disabled','checks':[],'versions':{},'note':'Synthetic fixtures never train the live models.'}
    with store.connect(path) as c:
        rs=c.execute('SELECT payload FROM model_checks WHERE sport=? ORDER BY day DESC,kind LIMIT 2',(sport,)).fetchall()
    return {'status':'Evaluated every refresh','checks':[json.loads(r['payload']) for r in rs],
        'versions':{k:active(sport,k,path)['version'] for k in ('ml','total')},
        'note':'Every successful refresh settles results and evaluates calibration. Model promotion needs 100 settled games, fresh, non-overlapping dated holdouts and improvement in both Brier score and log loss.'}
