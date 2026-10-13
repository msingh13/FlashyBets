"""Export clearly labeled synthetic snapshots; never export credentials or personal bets."""
import json,tempfile
from pathlib import Path
from datetime import datetime,timedelta,timezone
from app import service,store,picks,learning
from app.demo import games
out=Path(__file__).parent.parent/'frontend/public/demo'
out.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory() as scratch:
    db=str(Path(scratch)/'demo.db')
    for sport in service.MODELS:
        rows=games(sport,'2026-10-13')
        for g in rows:
            # This frozen fixture is intentionally synthetic, not an as-of live prediction.
            g['state']='pre';g['home_score']=None;g['away_score']=None;service.enrich(g)
            g['updated']='2026-10-13T14:00:00Z'
            g['injuries_asof']='2026-10-13T14:00:00Z'
            store.capture(g,db,at='2026-10-13T14:00:00Z')
        picks.build(sport,'2026-10-13','demo',db,at='2026-10-13T14:00:00Z')
        (out/(sport+'-favorites.json')).write_text(json.dumps(picks.favorites(sport,'2026-10-13','demo',db),indent=2))
        (out/(sport+'.json')).write_text(json.dumps({'games':rows,'updated':'2026-10-13T14:00:00Z','refresh_seconds':600,'mode':'demo','sport':sport,'date':'2026-10-13'},indent=2))
        past=games(sport,'2026-10-12')
        for i,g in enumerate(past):
            g['state']='pre';g['home_score']=None;g['away_score']=None;service.enrich(g)
            store.capture(g,db,at='2026-10-12T14:00:00Z')
            g.update(state='post',home_score={'nhl':4,'nba':118,'nfl':27,'ucl':2}[sport]+i,away_score={'nhl':3,'nba':111,'nfl':24,'ucl':1}[sport]+i)
            store.settle(g,db)
        picks.build(sport,'2026-10-12','demo',db,at='2026-10-12T14:00:00Z')
        ledger=store.ledger(sport,'demo',db);ledger['cards']=picks.settled_cards(sport,'demo',db);ledger['learning']=learning.status(sport,'demo',db)
        (out/(sport+'-tracker.json')).write_text(json.dumps(ledger,indent=2))
print('Exported synthetic demo boards and trackers for NHL, NBA, NFL and UCL.')
