"""Optional external integrations. They remain usable without provider credentials."""
from __future__ import annotations
import os, secrets, math
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit
from typing import Any
import requests
try:
    from twilio.rest import Client
except Exception:
    Client=None
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception: pass

def configured(name): return bool(os.getenv(name) and not os.getenv(name,'').startswith('your_'))
def send_sms(body:str,to:str|None=None)->dict[str,Any]:
    sid,token,from_number=os.getenv('TWILIO_ACCOUNT_SID'),os.getenv('TWILIO_AUTH_TOKEN'),os.getenv('TWILIO_PHONE_NUMBER'); to=to or os.getenv('TARGET_PHONE_NUMBER')
    if not (Client and sid and token and from_number and to and not sid.startswith('your_')): return {'status':'not_configured','provider':'local_adapter','reason':'Twilio credentials or destination not configured; no message was sent.'}
    try:
        msg=Client(sid,token).messages.create(body=body,from_=from_number,to=to); return {'status':'accepted_by_provider','provider':'twilio','message_sid':msg.sid,'delivery_confirmed':False,'delivery_status':getattr(msg,'status','queued')}
    except Exception as exc: return {'status':'failed','provider':'twilio','error':str(exc)}
def gauge_feed()->dict[str,Any]:
    url=os.getenv('GAUGE_FEED_URL')
    if not url: return {'status':'not_configured','gauges':[],'source':'GAUGE_FEED_URL'}
    parsed=urlsplit(url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:
        return {'status':'invalid_configuration','gauges':[],'source':'configured gauge provider','message':'Gauge feed must use HTTPS and must not embed credentials in the URL.'}
    safe_source=urlunsplit((parsed.scheme,parsed.netloc,parsed.path,'',''))
    try:
        r=requests.get(url,timeout=10); r.raise_for_status(); data=r.json(); records=data if isinstance(data,list) else data.get('gauges') if isinstance(data,dict) else None
        if not isinstance(records,list) or len(records)>10000: return {'status':'invalid_response','gauges':[],'source':safe_source,'message':'Expected a JSON array or an object with a gauges array (maximum 10,000 readings).'}
        normalized=[]; now=datetime.now(timezone.utc); max_age=max(1,min(168,int(os.getenv('GAUGE_MAX_AGE_HOURS','12'))))
        for record in records:
            if not isinstance(record,dict): continue
            try:
                lat=float(record['lat']); lon=float(record['lon']); level=float(record['level_m']); observed=datetime.fromisoformat(str(record['observed_at']).replace('Z','+00:00'))
                if observed.tzinfo is None or not all(map(math.isfinite,(lat,lon,level))) or not -90<=lat<=90 or not -180<=lon<=180 or level<0: continue
                age_hours=(now-observed.astimezone(timezone.utc)).total_seconds()/3600
                if age_hours < -0.083: continue
                age_hours=max(0,age_hours)
                normalized.append({**record,'id':str(record.get('id') or record.get('station_id') or '')[:120],'lat':lat,'lon':lon,'level_m':level,'observed_at':observed.astimezone(timezone.utc).isoformat(),'source':str(record.get('source') or safe_source)[:200],'freshness':'fresh' if age_hours<=max_age else 'stale','age_hours':round(age_hours,1)})
            except (KeyError,TypeError,ValueError,OverflowError): continue
        fresh=any(item['freshness']=='fresh' for item in normalized)
        return {'status':'live' if fresh else 'stale' if normalized else 'no_valid_readings','gauges':normalized,'source':safe_source,'fetched_at':now.isoformat(),'fresh_records':sum(item['freshness']=='fresh' for item in normalized),'stale_records':sum(item['freshness']=='stale' for item in normalized),'message':'Gauge timestamps and coordinates were validated; stale readings are marked individually.'}
    except Exception: return {'status':'unavailable','gauges':[],'source':safe_source,'message':'Configured gauge provider could not be reached or returned invalid JSON.'}
def satellite_config()->dict[str,Any]:
    return {'status':'configured' if configured('SATELLITE_TILE_URL') else 'fallback','tile_url':os.getenv('SATELLITE_TILE_URL','https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'),'attribution':'Esri World Imagery; verify usage terms before production'}
def issue_api_key()->str: return secrets.token_urlsafe(24)
