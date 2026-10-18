from app.nfl import parse_depth,summary

def test_depth_is_team_and_season_bound_and_never_confirmed():
    body={'team':{'id':'21'},'season':{'year':2026},'depthchart':[{'name':'Offense','positions':{'qb':{'athletes':[{'id':'1','displayName':'Backup QB'}]}}}]}
    assert not parse_depth(body,'22',2026)
    assert not parse_depth(body,'21',2025)
    row=parse_depth(body,'21',2026)[0]
    assert row['rank']==1 and row['position']=='QB' and row['confirmed'] is False

def test_summary_explains_actual_favorite_and_qb_absence():
    g={'home':'Philadelphia Eagles','away':'Carolina Panthers','home_abbr':'PHI','away_abbr':'CAR','prediction':{'home':.6,'away':.39,'home_rate':24.,'away_rate':21.},'injuries':{'home':[{'name':'Jalen Hurts','position':'QB','status':'Injured Reserve'}]},'nfl_depth':{'home':{'players':[{'name':'Tanner McKee','position':'QB','rank':1}]},'away':{'players':[]}}}
    text=summary(g)
    assert 'Philadelphia Eagles leads at 60%' in text
    assert 'Jalen Hurts Injured Reserve' in text and 'Tanner McKee atop' in text
    assert 'not fitted probability adjustments' in text
    g['prediction']['home']=.39;g['prediction']['away']=.6
    assert summary(g).startswith('Carolina Panthers leads')
    g['prediction']=None
    assert 'no model favorite' in summary(g)
