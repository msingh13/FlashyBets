from .sports import SOCCER
"""Context is checked and exposed. Effects require externally fitted, sourced coefficients.
Never infer an arbitrary player penalty from the number of injury reports.
"""
import json,os,math
from datetime import datetime,timezone,timedelta
from .store import instant

def context_for(g):
    starters=all(g.get(s+'_starters') and all(x.get('confirmed') for x in g[s+'_starters']) for s in ('home','away'))
    travel=all(g.get('travel',{}).get(s,{}).get('km') is not None for s in ('home','away'))
    weather=g['sport'] not in ('nfl','ncaaf',*SOCCER) or g.get('indoor') is True or g.get('weather',{}).get('temperature_c') is not None
    checked=g.get('injuries_checked',False)
    # An old injury endpoint timestamp cannot establish current gameday availability.
    fresh=False
    if g.get('injuries_asof'):
        try:fresh=abs((datetime.now(timezone.utc)-instant(g['injuries_asof'])).total_seconds())<=21600
        except ValueError:pass
    checks={'injuries':checked and fresh,'starters':starters,'travel':travel,'weather':weather}
    config={};path=os.getenv('MODEL_CONFIG_PATH')
    if path:
        with open(path) as f:config=json.load(f).get(g['sport'],{})
    # External model config must describe temporal evaluation and feature provenance.
    calibrated=bool(config.get('validated_out_of_sample') and config.get('evaluation_source') and config.get('asof'))
    if calibrated:
        calibrated=instant(config['asof'])<instant(g['start'])
    # Context features are descriptive until a sourced fitted configuration is supplied.
    adjustments={'home':0.,'away':0.};applied=[];missing=[]
    if calibrated:
        coeff=config.get('coefficients',{})
        for side in ('home','away'):
            traveldata=g.get('travel',{}).get(side,{})
            if checks['travel']:
                delta=coeff.get('travel_per_1000km',0)*traveldata['km']/1000
                rest=coeff.get('rest_per_day',0)*min(7,max(0,(traveldata['rest_hours'] or 0)/24))
                adjustments[side]+=delta+rest
                if delta or rest:applied.append(f'{side} travel/rest adjustment: {delta+rest:+.2f}')
            impacts=config.get('player_impacts',{})
            for player in g.get('injuries',{}).get(side,[]):
                # Only definite absences, not questionable players. No double counting of starters.
                if player['status'].lower() in ('out','injured reserve','ir','suspended'):
                    impact=impacts.get(player['name'])
                    if impact is None:missing.append(player['name'])
                    else:adjustments[side]+=float(impact)
        if g['sport'] in ('nfl','ncaaf') and not g.get('indoor') and checks['weather']:
            temperature=g['weather']['temperature_c'];wind=g['weather']['wind_kmh']
            delta=coeff.get('wind_per_kmh',0)*wind+coeff.get('cold_per_degree_below_10c',0)*max(0,10-temperature)
            adjustments['home']+=delta;adjustments['away']+=delta
            if delta:applied.append(f'Weather adjustment per team: {delta:+.2f}')
        # Goalies/rotations require explicit fitted per-starter effects, not confirmation alone.
        effects=config.get('starter_impacts',{})
        if checks['starters']:
            for side in ('home','away'):
                for starter in g[side+'_starters']:
                    impact=effects.get(starter['name'])
                    if impact is None:missing.append(starter['name'])
                    else:adjustments[('away' if side=='home' else 'home') if g['sport']=='nhl' else side]+=float(impact)
    if not all(math.isfinite(v) for v in adjustments.values()):raise ValueError('Nonfinite context adjustment')
    ready=calibrated and all(checks.values()) and not missing and g.get('season_type')==2
    return {'checks':checks,'calibrated':calibrated,'ready':ready,'adjustments':adjustments,'applied':applied,
      'missing_impacts':missing,'decision':'Context ready' if ready else 'Watch only · inputs or calibration incomplete',
      'note':'No public sentiment is used. Observed context only changes probabilities when a sourced, fitted effect is configured.'}
