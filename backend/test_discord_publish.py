import json,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from discord_publish import plans
class DiscordTests(unittest.TestCase):
 def test_dedup_and_result(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'manifest.json').write_text(json.dumps({'today':'2026-10-28'}))
   leg={'game_key':'live:nhl:1','side':'home','start':'2026-10-28T23:00Z','home':'TOR','away':'MTL','label':'TOR ML','probability':.6,'outcome':None}
   card={'key':'live:2026-10-28','day':'2026-10-28','legs':[leg]}
   (root/'flashy-ai.json').write_text(json.dumps({'days':[card]}));state={'posted':{}}
   now=datetime(2026,10,28,12,tzinfo=timezone.utc)
   jobs=plans(root,state,now);self.assertEqual(len(jobs),1);self.assertIn('60.0%',jobs[0][1]);state['posted'][jobs[0][0]]=jobs[0][2]
   self.assertEqual(plans(root,state,now),[])
   leg['outcome']='win';(root/'flashy-ai.json').write_text(json.dumps({'days':[card]}))
   jobs=plans(root,state,now);self.assertEqual(len(jobs),1);self.assertIn('WIN',jobs[0][1]);state['posted'][jobs[0][0]]=jobs[0][2];self.assertEqual(plans(root,state,now),[])
 def test_no_late_or_withdrawn_picks(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'manifest.json').write_text('{"today":"2026-10-28"}')
   leg={'game_key':'a','side':'home','start':'2026-10-28T01:00Z'}
   card={'key':'a','day':'2026-10-28','legs':[leg]};(root/'flashy-ai.json').write_text(json.dumps({'days':[card]}));self.assertEqual(plans(root,{'posted':{}},datetime(2026,10,28,12,tzinfo=timezone.utc)),[])
 def test_favorites_card(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'manifest.json').write_text('{"today":"2026-10-28"}');(root/'nhl').mkdir()
   leg={'game_key':'a','side':'home','start':'2026-10-28T23:00Z','label':'TOR ML'}
   card={'key':'nhl:a','sport':'nhl','day':'2026-10-28','legs':[leg]};(root/'nhl'/'2026-10-28-favorites.json').write_text(json.dumps({'card':card}));self.assertEqual(len(plans(root,{'posted':{}},datetime(2026,10,28,12,tzinfo=timezone.utc))),1)
if __name__=='__main__':unittest.main()
