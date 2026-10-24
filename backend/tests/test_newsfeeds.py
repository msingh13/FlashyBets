import json
import pytest
from app.newsfeeds import rotowire,faceoff
from app.market_reference import reference,review

def test_rotowire_date_and_confirmed_vs_expected():
    players=''.join(f'<li class="lineup__player"><div class="lineup__pos">G</div><a title="Player {n}" href="/player/{n}">P</a></li>' for n in range(5))
    html='<main data-gamedate="2026-10-24"><div class="lineup is-nba">'+''.join(f'<a class="lineup__team {side}"><div class="lineup__abbr">{team}</div></a><ul class="lineup__list {side}"><li class="lineup__status {status}"></li>{players}</ul>' for side,team,status in [('is-home','DAL','is-confirmed'),('is-visit','SAS','is-expected')])+'</div></main>'
    r=rotowire(html,'2026-10-24')[0]
    assert len(r['home']['starters'])==5 and all(p['confirmed'] for p in r['home']['starters'])
    assert not any(p['confirmed'] for p in r['away']['starters'])
    with pytest.raises(ValueError):rotowire(html,'2026-10-25')

def test_faceoff_requires_structured_date():
    html='<script id="__NEXT_DATA__">'+json.dumps({'props':{'pageProps':{'data':[{'date':'2026-10-24','dateGmt':'2026-10-24T23:00Z'},{'date':'2026-10-23','dateGmt':'2026-10-23T23:00Z'}]}}})+'</script>'
    assert len(faceoff(html,'2026-10-24'))==1
    with pytest.raises(ValueError):faceoff('<h1>Blocked</h1>','2026-10-24')

def test_market_reference_is_no_vig_not_fake_model():
    o={'odds':[{'provider':{'name':'DraftKings'},'moneyline':{'home':{'close':{'odds':'+600'},'open':{'odds':'+360'}},'away':{'close':{'odds':'-900'},'open':{'odds':'-470'}}}}]}
    r=reference(o,'2026-10-24T18:00Z')
    assert r['away']==pytest.approx(.8630136986) and r['home']+r['away']==pytest.approx(1)
    assert r['price_updated'] is None and r['open_away_odds']==-470
    assert reference({'odds':[]},'2026-10-24T18:00Z') is None
    assert reference({'odds':None},'2026-10-24T18:00Z') is None

def test_independent_reference_remains_visible_with_context_note():
    p={'home':.59,'away':.41};g={'mode':'live','sport':'nba','state':'pre','prediction':p.copy(),'sample_sizes':{'home':2,'away':2},'injuries':{'home':[{'name':'Unavailable player','status':'Out'}]},'context':{'calibrated':False,'ready':False},'markets':{}}
    review(g)
    assert g['prediction']==p and 'model_note' in g and 'forecast_review' not in g
    assert g['context']['ready'] is False and p=={'home':.59,'away':.41}
    g['state']='post';g['prediction']=p.copy();review(g)
    assert g['prediction']==p
