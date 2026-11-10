import unittest,json
from datetime import datetime,timezone
from discord_publish import fresh_state,prepare,sync
class MorningTests(unittest.TestCase):
 def setUp(self):
  self.now=datetime(2026,10,28,7,tzinfo=timezone.utc)
  self.legs=[{'game_key':str(i),'side':'home','home':'CLE','away':'WSH','label':'CLE ML','start':'2026-10-28T23:00Z','probability':.65,'outcome':None} for i in range(5)]
  self.feed={'updated':self.now.isoformat(),'days':[{'day':'2026-10-28','legs':self.legs}]}
 def test_six_am_plain_three_max(self):
  s=fresh_state();s['sent']['results:2026-10-28']='sent';job=prepare(s,self.feed,self.now);self.assertEqual(len(job[2]['legs']),3);self.assertEqual(job[1],'CLE ML\nCLE ML\nCLE ML');self.assertNotIn('http',job[1]);self.assertNotIn('@',job[1]);s['sent'][job[0]]='sent';self.assertIsNone(prepare(s,self.feed,self.now))
 def test_initial_zero_and_results(self):
  s=fresh_state();now=datetime(2026,10,28,6,tzinfo=timezone.utc);job=prepare(s,self.feed,now);self.assertIn('AI Play 0-0',job[1])
  s['slates']['2026-10-27']={'legs':[dict(self.legs[0])]};self.legs[0]['outcome']='win';sync(s,self.feed);self.assertEqual(s['record']['wins'],1);self.assertIn('AI Play 1-0',prepare(s,self.feed,now)[1])
 def test_timezone_and_off_hours(self):
  self.assertIsNone(prepare(fresh_state(),self.feed,datetime(2026,10,28,5,tzinfo=timezone.utc)))
  winter=datetime(2026,12,1,7,tzinfo=timezone.utc);self.assertIn('AI Play 0-0',prepare(fresh_state(),{},winter)[1])
 def test_no_backfill_no_stale_picks(self):
  s=fresh_state();s['sent']['results:2026-10-28']='sent';self.feed['updated']='2026-10-27T01:00Z'
  with self.assertRaises(RuntimeError):prepare(s,self.feed,self.now)
  self.assertEqual(s['record']['wins'],0)
 def test_pending_not_a_loss(self):
  s=fresh_state();s['slates']['2026-10-27']={'legs':[dict(self.legs[0])]};sync(s,self.feed);self.assertEqual(s['record']['pending'],1);self.assertEqual(s['record']['losses'],0)
if __name__=='__main__':unittest.main()

class TopListsTests(unittest.TestCase):
 def test_rank_five_and_soccer_combined(self):
  from discord_publish import top_plans
  now=datetime(2026,10,28,7,tzinfo=timezone.utc)
  legs=[{'game_key':str(i),'side':'home','home':'CLE','away':'WSH','label':'CLE ML','start':'2026-10-28T23:00Z','probability':.5+i*.02} for i in range(8)]
  jobs=top_plans(fresh_state(),{'nba':{'moneylines':legs},'ucl':{'moneylines':legs[:3]},'epl':{'moneylines':legs[3:]}},now)
  self.assertEqual(len(jobs),2);self.assertEqual(len(jobs[0][2]['legs']),5);self.assertEqual(jobs[0][2]['legs'][0]['game_key'],'7');self.assertEqual(len(jobs[-1][2]['legs']),5)
 def test_no_fabricated_five(self):
  from discord_publish import top_plans
  jobs=top_plans(fresh_state(),{},datetime(2026,10,28,7,tzinfo=timezone.utc))
  self.assertEqual(jobs,[])

class StyledMessagesTests(unittest.TestCase):
 def test_threshold_strict_and_style(self):
  from discord_publish import top_plans,card_message
  now=datetime(2026,10,28,7,tzinfo=timezone.utc)
  base={'game_key':'a','side':'home','home':'CLE','away':'WSH','label':'CLE ML','start':'2026-10-28T23:00Z'}
  picks=[dict(base,game_key=str(i),probability=p) for i,p in enumerate([.536,.535,.537,.70])]
  state=fresh_state();jobs=top_plans(state,{'nba':{'moneylines':picks}},now)
  self.assertEqual(len(jobs),1);self.assertEqual(len(jobs[0][2]['legs']),2)
  out=card_message(*jobs[0],state['record']);e=out['embeds'][0]
  self.assertIn('NBA',e['title']);self.assertEqual(e['color'],0xF59E0B);self.assertEqual(len(e['fields']),2)
  self.assertNotIn('http',json.dumps(out))

class RecapTests(unittest.TestCase):
 def test_totals_deduplicate_and_pending(self):
  from discord_publish import recap_jobs,result_summary,sync_top
  s=fresh_state();p={'game_key':'a','side':'home','label':'CLE ML','home':'CLE','away':'WSH','sport':'nba','outcome':None}
  s['top_slates']={'top:NBA:2026-10-27':{'day':'2026-10-27','sport':'NBA','legs':[dict(p)]}}
  s['slates']['2026-10-27']={'legs':[dict(p)]}
  sync_top(s,{'nba':{'forecasts':[{'game_key':'a','result':{},'markets':[{'name':'home','outcome':'win'}]}]}})
  s['slates']['2026-10-27']['legs'][0]['outcome']='win'
  jobs=recap_jobs(s,datetime(2026,10,28,6,tzinfo=timezone.utc))
  self.assertIn('✅',jobs[0][1]);self.assertIn('100% Win Rate',jobs[0][1]);self.assertIn('1 unique selections',jobs[-1][1]);self.assertIn('pending',result_summary([p]))

class CatchupTests(unittest.TestCase):
 def test_late_recap(self):
  now=datetime(2026,10,29,15,tzinfo=timezone.utc);s=fresh_state();job=prepare(s,{},now)
  self.assertEqual(job[0],'results:2026-10-29')
 def test_completed_nhl_settles_without_snapshot_refresh(self):
  from discord_publish import apply_finals
  p={'game_key':'live:nhl:1','id':'1','side':'home','sport':'nhl','outcome':None}
  state=fresh_state();state['top_slates']={'a':{'legs':[p]}}
  e={'id':'1','status':{'type':{'completed':True}},'competitions':[{'competitors':[{'homeAway':'home','score':'4'},{'homeAway':'away','score':'0'}]}]}
  apply_finals(state,'nhl',[e]);self.assertEqual(p['outcome'],'win')
 def test_live_game_not_graded(self):
  from discord_publish import apply_finals
  p={'game_key':'live:nhl:1','id':'1','side':'home','sport':'nhl','outcome':None};state=fresh_state();state['top_slates']={'a':{'legs':[p]}}
  apply_finals(state,'nhl',[{'id':'1','status':{'type':{'completed':False}},'competitions':[]}]);self.assertIsNone(p['outcome'])

class AutomaticFreshnessTests(unittest.TestCase):
 def test_missing_due_picks_refresh_automatically(self):
  from discord_preflight import needs_refresh
  now=datetime(2026,10,29,14,tzinfo=timezone.utc)
  self.assertTrue(needs_refresh({'sent':{}},{'updated':'2026-10-29T09:00Z'},now))
  self.assertFalse(needs_refresh({'sent':{}},{'updated':now.isoformat()},now))
 def test_completed_day_does_not_keep_rebuilding(self):
  from discord_preflight import needs_refresh
  now=datetime(2026,10,29,14,tzinfo=timezone.utc)
  self.assertFalse(needs_refresh({'sent':{'slip:2026-10-29':'sent'}},{},now))
 def test_results_do_not_wait_for_model_refresh(self):
  from discord_preflight import needs_refresh
  now=datetime(2026,10,29,6,tzinfo=timezone.utc)
  self.assertFalse(needs_refresh({'sent':{}},{},now))
 def test_refresh_force_and_bad_timestamp(self):
  from discord_preflight import needs_refresh
  now=datetime(2026,10,29,6,tzinfo=timezone.utc)
  self.assertTrue(needs_refresh({'sent':{}},{},now,True))

class QuietRefreshTests(unittest.TestCase):
 def run_stale_refresh(self, already_sent):
  import tempfile,os
  from pathlib import Path
  from unittest.mock import patch
  import discord_publish as publisher
  now=datetime(2026,11,2,18,tzinfo=timezone.utc)
  state=fresh_state()
  # Recaps are already delivered; isolate a routine afternoon refresh.
  state['sent']={'results:2026-11-02':'sent','recap:TOTAL:2026-11-02':'sent'}
  if already_sent:state['sent']['slip:2026-11-02']='sent'
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'state.json';path.write_text(json.dumps(state))
   with patch.dict(os.environ,{'DISCORD_STATE':str(path),'POST_NOW':'false','REPLACE_POSTS':'false','CORRECT_RECAP':'false'},clear=True), patch.object(publisher,'datetime') as clock, patch.object(publisher,'load_feed',return_value={'updated':'2026-11-01T00:00:00Z','days':[]}), patch.object(publisher,'send') as send:
    clock.now.return_value=now
    clock.fromisoformat.side_effect=datetime.fromisoformat
    publisher.main()
    send.assert_not_called()
   saved=json.loads(path.read_text())
   self.assertEqual(saved['sent'],state['sent'])
   self.assertFalse(any(key.startswith('delay:') for key in saved['sent']))
 def test_no_false_delay_after_daily_delivery(self):self.run_stale_refresh(True)
 def test_stale_retry_stays_quiet_without_consuming_delivery_key(self):self.run_stale_refresh(False)

class RecapGraceTests(unittest.TestCase):
 def test_pending_sport_holds_entire_recap_until_230_eastern(self):
  from discord_publish import recap_jobs
  state=fresh_state()
  leg={'game_key':'live:nhl:1','side':'home','label':'BUF ML','outcome':None}
  state['top_slates']={'top:NHL:2026-11-08':{'day':'2026-11-08','sport':'NHL','legs':[leg]}}
  start=datetime(2026,11,9,7,tzinfo=timezone.utc)
  self.assertIsNone(prepare(state,{},start))
  self.assertEqual(recap_jobs(state,start),[])
  leg['outcome']='win'
  self.assertIsNone(prepare(state,{},start.replace(minute=29)))
  self.assertTrue(recap_jobs(state,start.replace(minute=30)))

 def test_pending_after_grace_is_reported_as_pending(self):
  from discord_publish import recap_jobs
  state=fresh_state()
  leg={'game_key':'live:nfl:1','side':'home','label':'BUF ML','outcome':None}
  state['slates']={'2026-11-08':{'legs':[leg]}}
  now=datetime(2026,11,9,7,30,tzinfo=timezone.utc)
  self.assertIn('pending',prepare(state,{},now)[1])
  self.assertIn('1 pending',recap_jobs(state,now)[-1][1])

 def test_live_final_can_settle_ai_total_before_recap(self):
  from discord_publish import apply_finals,update_record
  state=fresh_state()
  leg={'game_key':'live:nhl:1','side':'over','label':'Over 5.5','line':5.5}
  state['slates']={'2026-11-08':{'legs':[leg]}}
  event={'id':'1','status':{'type':{'completed':True}},'competitions':[{'competitors':[
   {'homeAway':'home','score':'4'},{'homeAway':'away','score':'2'}]}]}
  apply_finals(state,'nhl',[event])
  update_record(state)
  self.assertEqual(state['record']['wins'],1)
  self.assertEqual(leg['outcome'],'win')

 def test_warmup_refreshes_feed_that_would_expire_at_three(self):
  from discord_preflight import needs_refresh
  now=datetime(2026,11,9,7,42,tzinfo=timezone.utc)
  state=fresh_state()
  self.assertTrue(needs_refresh(state,{'updated':'2026-11-09T06:00Z'},now))
  self.assertFalse(needs_refresh(state,{'updated':'2026-11-09T07:40Z'},now))

class EmptyPlayRecoveryTests(unittest.TestCase):
 def test_empty_announcement_does_not_block_later_research_play(self):
  now=datetime(2026,11,10,10,tzinfo=timezone.utc)
  state=fresh_state()
  state['sent']={'results:2026-11-10':'sent','slip:2026-11-10':'sent'}
  state['slates']['2026-11-10']={'day':'2026-11-10','legs':[]}
  feed={'updated':now.isoformat(),'days':[]}
  self.assertIsNone(prepare(state,feed,now))
  pick={'game_key':'live:ncaaf:1','side':'home','label':'BGSU ML',
        'start':'2026-11-11T00:00Z','probability':.591,'research_fallback':True}
  feed['days']=[{'day':'2026-11-10','legs':[dict(pick,reference_odds=-1100)]}]
  self.assertIsNone(prepare(state,feed,now))
  feed['days'][0]['legs']=[dict(pick,reference_odds=-218)]
  job=prepare(state,feed,now)
  self.assertEqual(job[1],'BGSU ML')
  state['slates']['2026-11-10']=job[2]
  self.assertIsNone(prepare(state,feed,now))
