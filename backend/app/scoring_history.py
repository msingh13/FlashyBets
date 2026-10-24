"""Dated scoring evidence; older seasons inform sparse starts at reduced weight."""
import math
from .store import instant

def weighted_rates(rows,team_id,start,season_year,baseline,prior):
    cutoff=instant(start);gf=ga=mass=0.;used=0
    for r in rows:
        age=(cutoff-instant(r['start'])).total_seconds()/86400
        if age<=0 or age>550 or r.get('season_type')!=2:continue
        weight=math.exp(-math.log(2)*age/120)
        if r.get('season_year')!=season_year:weight*=.5
        home=r['home_id']==team_id
        gf+=weight*r['home_score' if home else 'away_score']
        ga+=weight*r['away_score' if home else 'home_score'];mass+=weight;used+=1
    return (gf+baseline*prior)/(mass+prior),(ga+baseline*prior)/(mass+prior),{'games':used,'effective_games':round(mass,2),'half_life_days':120,'previous_season_multiplier':.5}
