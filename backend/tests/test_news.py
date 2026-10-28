from datetime import datetime,timezone
from app.news import headlines,category

def test_news_dates_sources_dedup_and_video_filter():
    now=datetime(2026,10,27,20,tzinfo=timezone.utc)
    a={'id':1,'headline':'Player ruled out with knee injury','published':'2026-10-27T18:00Z','byline':'Named reporter','links':{'web':{'href':'https://www.espn.com/story/1'}}}
    rows=headlines({'articles':[a,a,dict(a,published='2026-10-20T18:00Z'),dict(a,published='2026-11-20T18:00Z'),dict(a,links={'web':{'href':'javascript:alert(1)'}})]},now)
    assert len(rows)==1 and rows[0]['source']=='ESPN' and rows[0]['byline']=='Named reporter' and rows[0]['category']=='Injuries'
    assert category('Team signs player to new contract')=='Transactions'
