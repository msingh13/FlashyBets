import json,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from discord_publish import plans,slip
class DiscordTests(unittest.TestCase):
 def test_slip_and_silent_tracker(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'manifest.json').write_text('{"today":"2026-10-28"}')
   leg={'game_key':'a','side':'home','start':'2026-10-28T23:00Z','sport':'nhl','home':'TOR','away':'MTL','label':'TOR ML','outcome':None}
   card={'key':'live:2026-10-28','day':'2026-10-28','legs':[leg]}
   path=root/'flashy-ai.json';path.write_text(json.dumps({'days':[card]}));state={'posted':{}}
   now=datetime(2026,10,28,12,tzinfo=timezone.utc);jobs=plans(root,state,now,'123456789')
   self.assertEqual(len(jobs),1);self.assertTrue(jobs[0][1].startswith('<@123456789>'));self.assertNotIn('http',jobs[0][1]);self.assertNotIn('model',jobs[0][1]);self.assertIn('TOR ML',jobs[0][1])
   state['posted'][jobs[0][0]]=jobs[0][2];self.assertEqual(plans(root,state,now,'123456789'),[])
   leg['outcome']='win';path.write_text(json.dumps({'days':[card]}));self.assertEqual(plans(root,state,now,'123456789'),[]);self.assertEqual(state['tracker'][jobs[0][0]]['wins'],1)
 def test_invalid_id(self):
  with self.assertRaises(ValueError):slip([], '@GamblyBot')
 def test_bets_individual_vs_parlay(self):
  self.assertIn('straight-bet',slip([],'123'));self.assertIn('parlay',slip([],'123',True))
if __name__=='__main__':unittest.main()
