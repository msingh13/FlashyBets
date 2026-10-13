"""Frozen model-favorite cards; not sportsbook tickets or public-consensus picks."""
import json,math
from . import store

def chosen(g,kind):
    p=g['prediction'];sides=('home','away') if kind=='ml' else ('over','under');side=max(sides,key=lambda n:p[n])
    m=g['markets'].get(side);push=p.get('ml_push',0) if kind=='ml' else p['push']
    return {'game_key':store.key(g),'id':g['id'],'home':g['home_abbr'],'away':g['away_abbr'],'start':g['start'],
      'side':side,'label':g[side+'_abbr']+' ML' if kind=='ml' else side.title()+' '+str(g['reference_line']),
      'probability':p[side],'conditional':p[side]/(1-push),'push':push,'odds':m['odds'] if m else None,
      'ev':m['ev'] if m else None,'line':g['reference_line'],'market_line':g['line'] is not None,
      'context_ready':g['context']['ready'],'model':p['version'],'outcome':None}

def build(sport,day,mode,path=None,at=None):
    card_key=f'{mode}:{sport}:{day}';at=at or store.now()
    with store.connect(path) as c:
        old=c.execute('SELECT payload FROM cards WHERE card_key=?',(card_key,)).fetchone()
        if old:return json.loads(old['payload'])
        fs=c.execute('SELECT * FROM forecasts WHERE sport=? AND mode=?',(sport,mode)).fetchall()
    from zoneinfo import ZoneInfo
    candidates=[]
    for f in fs:
        g=json.loads(f['payload'])
        if store.instant(g['start']).astimezone(ZoneInfo('America/Toronto')).date().isoformat()!=day or store.instant(g['start'])<=store.instant(at):continue
        pick=chosen(g,'ml')
        if pick['conditional']>=.52:candidates.append(pick)
    legs=sorted(candidates,key=lambda x:(-x['probability'],x['start'],x['game_key']))[:5]
    if len(legs)<4:return None
    card={'key':card_key,'day':day,'sport':sport,'mode':mode,'created':at,'legs':legs,'experimental':not all(x['context_ready'] for x in legs),
       'joint_probability':math.prod(x['probability'] for x in legs),'decimal_odds':math.prod(1+(x['odds']/100 if x['odds']>0 else 100/abs(x['odds'])) for x in legs) if all(x['odds'] for x in legs) else None,
       'note':'Top model win probabilities, one leg per game. Joint probability assumes independence; not a validated parlay probability or an executable sportsbook ticket.'}
    with store.connect(path) as c:c.execute('INSERT OR IGNORE INTO cards VALUES(?,?,?,?,?,?)',(card_key,sport,mode,day,at,json.dumps(card)))
    return card

def settled_cards(sport,mode,path=None):
    with store.connect(path) as c:
        cs=c.execute('SELECT payload FROM cards WHERE sport=? AND mode=? ORDER BY day DESC',(sport,mode)).fetchall()
        fs={r['game_key']:json.loads(r['result']) for r in c.execute('SELECT game_key,result FROM forecasts WHERE sport=? AND mode=? AND result IS NOT NULL',(sport,mode))}
    cards=[]
    for row in cs:
        card=json.loads(row['payload']);wins=losses=pushes=pending=0
        for leg in card['legs']:
            r=fs.get(leg['game_key']);leg['outcome']=store.outcome(leg['side'],r['home_score'],r['away_score']) if r else None
            if leg['outcome']=='win':wins+=1
            elif leg['outcome']=='loss':losses+=1
            elif leg['outcome']=='push':pushes+=1
            else:pending+=1
        result='loss' if losses else 'pending' if pending else 'push' if pushes==len(card['legs']) else 'win'
        card.update(wins=wins,losses=losses,pushes=pushes,pending=pending,result=result)
        card['hit_fraction']=f'{wins}/{len(card["legs"])}'
        cards.append(card)
    return cards

def favorites(sport,day,mode,path=None):
    record=store.ledger(sport,mode,path);ml=[];totals=[]
    with store.connect(path) as c:fs=c.execute('SELECT payload,result FROM forecasts WHERE sport=? AND mode=?',(sport,mode)).fetchall()
    from zoneinfo import ZoneInfo
    for f in fs:
        g=json.loads(f['payload'])
        if store.instant(g['start']).astimezone(ZoneInfo('America/Toronto')).date().isoformat()!=day:continue
        r=json.loads(f['result']) if f['result'] else None
        for kind,target in [('ml',ml),('total',totals)]:
            p=chosen(g,kind)
            if r:p['outcome']=store.outcome(p['side'],r['home_score'],r['away_score'],p['line'])
            target.append(p)
    ml.sort(key=lambda x:-x['probability']);totals.sort(key=lambda x:-x['conditional'])
    cards=settled_cards(sport,mode,path)
    return {'moneylines':ml[:5],'totals':totals[:5],'card':next((c for c in cards if c['day']==day),None),
        'reason':'At least four recorded pregame ML favorites above 52% conditional probability are needed to create a card.'}
