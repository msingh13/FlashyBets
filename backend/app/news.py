"""Linked public headlines and availability facts; never invented news or social sentiment."""
from datetime import datetime,timezone,timedelta
import re
from urllib.parse import urlparse
import httpx
from . import providers,store
from .sports import SOCCER

def category(title):
    if re.search(r'\b(trade|traded|trades|deal|signs|waived|waiver|transfer|contract)\b',title,re.I):return 'Transactions'
    if re.search(r'\b(injury|injured|surgery|out for|ruled out|questionable|doubtful|concussion|hamstring|ankle|knee)\b',title,re.I):return 'Injuries'
    return 'Updates'

def headlines(body,now=None):
    now=now or datetime.now(timezone.utc);items=[];seen=set()
    for a in body.get('articles',[]):
        title=a.get('headline');url=a.get('links',{}).get('web',{}).get('href');published=a.get('published')
        try:date=store.instant(published)
        except (ValueError,TypeError,AttributeError):continue
        if not title or not url or urlparse(url).scheme not in ('http','https') or date>now+timedelta(minutes=5) or now-date>timedelta(days=3):continue
        if a.get('type')=='Media' or '/video/' in url:continue
        if url in seen:continue
        seen.add(url);items.append({'id':str(a.get('id') or url),'title':title,'url':url,'published':published,'source':'ESPN','byline':a.get('byline'),'category':category(title),'premium':bool(a.get('premium'))})
    return sorted(items,key=lambda a:a['published'],reverse=True)[:18]

async def fetch(sport):
    slug='soccer/'+SOCCER[sport][1] if sport in SOCCER else providers.PATHS[sport]
    async with httpx.AsyncClient(timeout=20) as client:
        body,error=await providers.optional(client,providers.BASE+slug+'/news',{'limit':30})
        injury,injury_error=await providers.optional(client,providers.BASE+slug+'/injuries')
    injuries=[]
    for t in (injury or {}).get('injuries',[]):
        for r in t.get('injuries',[]):
            athlete=r.get('athlete',{});name=athlete.get('displayName')
            if name and r.get('status') not in ('Active','Healthy'):
                injuries.append({'name':name,'team':t.get('displayName','Team unavailable'),'status':r.get('status','Unknown'),'reported_at':r.get('date'),'url':next((x['href'] for x in athlete.get('links',[]) if 'playercard' in x.get('rel',[])),None)})
    return {'sport':sport,'fetched':store.now(),'articles':headlines(body or {}),'injuries':injuries,'injuries_asof':(injury or {}).get('timestamp'),'status':'ESPN feed unavailable' if error else 'ESPN public headlines','injury_status':'Injury coverage unavailable' if injury_error else 'Latest ESPN availability listings; completeness unverified','social_status':'Direct X / Underdog headline feeds are not connected. Source links in game reports remain available.'}
