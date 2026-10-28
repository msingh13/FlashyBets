import unittest
from datetime import datetime,timezone
from discord_publish import fresh_state,prepare,sync
class MorningTests(unittest.TestCase):
 def setUp(self):
  self.now=datetime(2026,10,28,10,tzinfo=timezone.utc)
  self.legs=[{'game_key':str(i),'side':'home','home':'CLE','away':'WSH','label':'CLE ML','start':'2026-10-28T23:00Z','probability':.65,'outcome':None} for i in range(5)]
  self.feed={'updated':self.now.isoformat(),'days':[{'day':'2026-10-28','legs':self.legs}]}
 def test_six_am_plain_three_max(self):
  s=fresh_state();job=prepare(s,self.feed,self.now);self.assertEqual(len(job[2]['legs']),3);self.assertEqual(job[1],'CLE ML\nCLE ML\nCLE ML');self.assertNotIn('http',job[1]);self.assertNotIn('@',job[1]);s['sent'][job[0]]='sent';self.assertIsNone(prepare(s,self.feed,self.now))
 def test_initial_zero_and_results(self):
  s=fresh_state();now=datetime(2026,10,28,7,tzinfo=timezone.utc);job=prepare(s,self.feed,now);self.assertIn('AI Play 0-0',job[1])
  s['slates']['2026-10-27']={'legs':[dict(self.legs[0])]};self.legs[0]['outcome']='win';sync(s,self.feed);self.assertEqual(s['record']['wins'],1);self.assertIn('AI Play 1-0',prepare(s,self.feed,now)[1])
 def test_timezone_and_off_hours(self):
  self.assertIsNone(prepare(fresh_state(),self.feed,datetime(2026,10,28,8,tzinfo=timezone.utc)))
  winter=datetime(2026,12,1,8,tzinfo=timezone.utc);self.assertIn('AI Play 0-0',prepare(fresh_state(),{},winter)[1])
 def test_no_backfill_no_stale_picks(self):
  s=fresh_state();self.feed['updated']='2026-10-27T01:00Z'
  with self.assertRaises(RuntimeError):prepare(s,self.feed,self.now)
  self.assertEqual(s['record']['wins'],0)
 def test_pending_not_a_loss(self):
  s=fresh_state();s['slates']['2026-10-27']={'legs':[dict(self.legs[0])]};sync(s,self.feed);self.assertEqual(s['record']['pending'],1);self.assertEqual(s['record']['losses'],0)
if __name__=='__main__':unittest.main()

class TopListsTests(unittest.TestCase):
 def test_rank_five_and_soccer_combined(self):
  from discord_publish import top_plans
  now=datetime(2026,10,28,10,tzinfo=timezone.utc)
  legs=[{'game_key':str(i),'side':'home','home':'CLE','away':'WSH','label':'CLE ML','start':'2026-10-28T23:00Z','probability':.5+i*.02} for i in range(8)]
  jobs=top_plans(fresh_state(),{'nba':{'moneylines':legs},'ucl':{'moneylines':legs[:3]},'epl':{'moneylines':legs[3:]}},now)
  self.assertEqual(len(jobs),4);self.assertEqual(len(jobs[0][2]['legs']),5);self.assertEqual(jobs[0][2]['legs'][0]['game_key'],'7');self.assertEqual(len(jobs[-1][2]['legs']),5)
 def test_no_fabricated_five(self):
  from discord_publish import top_plans
  jobs=top_plans(fresh_state(),{},datetime(2026,10,28,10,tzinfo=timezone.utc))
  self.assertTrue(all(len(j[2]['legs'])==0 for j in jobs))
