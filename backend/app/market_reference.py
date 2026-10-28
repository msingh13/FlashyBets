"""Public book quotes for comparison, not independently modeled win probabilities."""
from .model import decimal

def reference(comp,fetched,require_draw=False):
    for o in comp.get('odds') or []:
        try:
            ml=o['moneyline'];h=float(ml['home']['close']['odds']);a=float(ml['away']['close']['odds'])
            hp,ap=1/decimal(h),1/decimal(a)
            draw=(o.get('drawOdds') or {}).get('moneyLine') or (ml.get('draw') or {}).get('close',{}).get('odds')
            if not require_draw:draw=None
            dp=1/decimal(float(draw)) if draw is not None else 0
            if require_draw and not dp:continue
            mass=hp+ap+dp
            opening={s:float(ml[s]['open']['odds']) if ml[s].get('open',{}).get('odds') else None for s in ('home','away')}
            return {**({'draw':dp/mass,'draw_odds':float(draw)} if dp else {}),'home':hp/mass,'away':ap/mass,'home_odds':h,'away_odds':a,'open_home_odds':opening['home'],'open_away_odds':opening['away'],
                'source':o.get('provider',{}).get('name','Bookmaker')+' via ESPN','fetched':fetched,'price_updated':None,
                'note':'Proportional no-vig book probability, not a model prediction or Bet365 quote. Pregame quote reference, not an in-play win model. Fetch time is not a bookmaker update timestamp.'}
        except (KeyError,TypeError,ValueError,ZeroDivisionError):continue
    return None

def review(g):
    """Expose uncertainty without removing the independent model reference."""
    g.pop('forecast_review',None)
    if g.get('mode')!='live' or g.get('state')!='pre' or not g.get('prediction'):return
    reasons=[]
    samples=g.get('sample_sizes',{})
    if samples and min(samples.values())<10:reasons.append('Limited current-season sample; historical games are weighted when available')
    if not g.get('context',{}).get('calibrated'):reasons.append('Player and goalie effects are not fitted')
    ref=g.get('market_reference')
    if ref and abs(g['prediction']['home']-ref['home'])>.2:reasons.append('Large model–sportsbook disagreement; this is not evidence of betting value')
    g['model_note']='. '.join(reasons)
