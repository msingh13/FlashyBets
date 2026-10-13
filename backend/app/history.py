import csv, math
from datetime import datetime
from .model import NHLModel, decimal

def timestamp(value):
    t=datetime.fromisoformat(value.replace("Z","+00:00"))
    if t.tzinfo is None: raise ValueError("Timestamps must include a timezone")
    return t

def evaluate(rows):
    predictions=[]
    for r in sorted(rows,key=lambda x:timestamp(x['start'])):
        if timestamp(r['feature_asof'])>=timestamp(r['start']) or timestamp(r['odds_asof'])>=timestamp(r['start']):
            raise ValueError('Features and odds must precede game start')
        p=NHLModel().predict(float(r['home_rate']),float(r['away_rate']),float(r['line']))
        h,a=int(r['home_score']),int(r['away_score'])
        if min(h,a)<0 or h==a: raise ValueError('Final NHL score must be nonnegative and cannot be tied')
        y=int(h>a);pick=p['home']>=.5;prob=p['home'] if pick else p['away']
        odds=int(r['home_odds'] if pick else r['away_odds'])
        win=pick==bool(y);profit=decimal(odds)-1 if win else -1
        predictions.append({"start":r['start'],"home":r['home'],"away":r['away'],"probability":prob,
            "win":win,"profit":profit,"brier":(p['home']-y)**2,
            "log_loss":-math.log(max(1e-12,p['home'] if y else p['away']))})
    n=len(predictions)
    return {"count":n,"brier":sum(x['brier'] for x in predictions)/n if n else None,
      "log_loss":sum(x['log_loss'] for x in predictions)/n if n else None,
      "roi":sum(x['profit'] for x in predictions)/n if n else None,
      "hit_rate":sum(x['win'] for x in predictions)/n if n else None,"rows":predictions,
      "method":"Chronological replay of pregame rates and odds; one unit on model ML favorite per game."}

def load(path):
    with open(path) as f: return evaluate(list(csv.DictReader(f)))
