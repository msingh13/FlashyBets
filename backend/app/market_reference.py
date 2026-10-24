"""Public book quotes for comparison, not independently modeled win probabilities."""
from .model import decimal

def reference(comp,fetched):
    for o in comp.get('odds') or []:
        try:
            ml=o['moneyline'];h=float(ml['home']['close']['odds']);a=float(ml['away']['close']['odds'])
            hp,ap=1/decimal(h),1/decimal(a)
            opening={s:float(ml[s]['open']['odds']) if ml[s].get('open',{}).get('odds') else None for s in ('home','away')}
            return {'home':hp/(hp+ap),'away':ap/(hp+ap),'home_odds':h,'away_odds':a,'open_home_odds':opening['home'],'open_away_odds':opening['away'],
                'source':o.get('provider',{}).get('name','Bookmaker')+' via ESPN','fetched':fetched,'price_updated':None,
                'note':'Proportional no-vig book probability, not a model prediction or Bet365 quote. Pregame quote reference, not an in-play win model. Fetch time is not a bookmaker update timestamp.'}
        except (KeyError,TypeError,ValueError,ZeroDivisionError):continue
    return None

def review(g):
    if g.get('mode')!='live' or g.get('sport')!='nba' or g.get('state')!='pre':return
    p=g.get('prediction')
    if not p:return
    samples=g.get('sample_sizes',{});reasons=[]
    if samples and min(samples.get('home',0),samples.get('away',0))<10:reasons.append('Fewer than ten current-season games per team; sparse scoring baseline')
    absent=[x['name'] for side in ('home','away') for x in g.get('injuries',{}).get(side,[]) if x.get('status','').lower() in ('out','injured reserve','ir','doubtful')]
    if absent and not g.get('context',{}).get('calibrated'):reasons.append('Unavailable players have no validated replacement/minutes effects: '+', '.join(absent[:6]))
    ref=g.get('market_reference')
    if ref and abs(p['home']-ref['home'])>.2:reasons.append('Model and current book reference disagree by more than 20 percentage points')
    if reasons:
        g['forecast_review']={'withheld':True,'reasons':reasons,'baseline_home':p['home'],'baseline_away':p['away']}
        g['prediction']=None;g['markets']={};g['recommendations']=[]
        g['context']['ready']=False;g['context']['decision']='Model withheld · insufficient roster-aware evidence'
        g['explanation']='Current NBA model withheld: '+'. '.join(reasons)+'. Book probabilities below are separate market estimates; no outcome is guaranteed.'
