from __future__ import annotations
import os, json, time, threading, ipaddress, re
from pathlib import Path
from typing import Any
import requests, joblib, pandas as pd
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, Request
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.operations import INCIDENTS, RESPONDERS, RESOURCES, ALERTS, SHELTERS, analytics, create_alert, create_incident, forecast_from_swarm, register, simulate_scenario, update_incident
from backend.swarm import MODEL_PATH, model_input_ranges as get_model_input_ranges, predict_what_if, run_aegis_swarm
from backend.integrations import gauge_feed, satellite_config, send_sms
from backend.security import decode_token, enabled as auth_enabled, login as authenticate
from backend.storage import load, save, audit, delete_record
from backend.feature_logic import community_trust
from backend.resource_catalog import (
    OSM_ATTRIBUTION,
    OSM_COPYRIGHT_URL,
    OSM_DATA_URL,
    OSM_TRUST_TIER,
    RESOURCE_CATEGORIES,
    public_categories,
)
from backend.weather_forecast import ForecastUnavailable, get_forecast as get_weather_forecast
app=FastAPI(title='Project Aegis API',version='2.0')
_allowed_origins=[origin.strip() for origin in os.getenv('AEGIS_ALLOWED_ORIGINS','http://localhost:8000,http://127.0.0.1:8000').split(',') if origin.strip()]
if '*' in _allowed_origins: raise RuntimeError('AEGIS_ALLOWED_ORIGINS must list exact trusted origins; wildcard CORS is not supported.')
app.add_middleware(CORSMiddleware,allow_origins=_allowed_origins,allow_methods=['GET','POST','PATCH','OPTIONS'],allow_headers=['Authorization','Content-Type','Idempotency-Key','X-Aegis-Key'])
_rate_lock=threading.Lock(); _rate_buckets={}
_nearby_cache_lock=threading.Lock(); _nearby_cache={}
RESOURCE_PACK_DIR=Path(__file__).resolve().parents[1]/'data'/'region-packs'
def enforce_rate_limit(request:Request,limit:int,window_seconds:int=60):
    key=(request.client.host if request.client else 'unknown',request.url.path); now=time.monotonic()
    with _rate_lock:
        if len(_rate_buckets)>2048:
            for bucket in [name for name,times in _rate_buckets.items() if not times or now-times[-1]>=window_seconds]: _rate_buckets.pop(bucket,None)
        recent=[t for t in _rate_buckets.get(key,[]) if now-t<window_seconds]
        if len(recent)>=limit: raise HTTPException(429,'Too many requests; retry shortly.')
        recent.append(now); _rate_buckets[key]=recent
class IncidentPayload(BaseModel):
    description: str = Field(min_length=1, max_length=2000)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    urgency: str = Field(default='medium', pattern='^(low|medium|high|critical)$')
    people_affected: int = Field(default=1, ge=1, le=10000000)
    created_by: str = Field(default='public', max_length=120)
    idempotency_key: str|None = Field(default=None, max_length=128)
    water_depth_cm: float|None = Field(default=None, ge=0, le=1000)
    photo_url: str|None = Field(default=None, max_length=2048)
class LoginPayload(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=512)
class UpdatePayload(BaseModel):
    status: str|None = Field(default=None, pattern='^(open|acknowledged|assigned|in_progress|resolved|closed)$')
    urgency: str|None = Field(default=None, pattern='^(low|medium|high|critical)$')
    assigned_to: str|None = None
    note: str|None = Field(default=None, max_length=2000)
    verification_status: str|None = Field(default=None, pattern='^(unverified|reviewing|verified|rejected)$')
class FeedbackPayload(BaseModel):
    category: str = Field(default='other', pattern='^(bug|data|accessibility|other)$')
    message: str = Field(min_length=3, max_length=2000)
    page: str|None = Field(default=None, max_length=200)
class TriagePayload(BaseModel):
    description: str = Field(min_length=1, max_length=2000)
    urgency: str = Field(default='medium', pattern='^(low|medium|high|critical)$')
    people_affected: int = Field(default=1, ge=1, le=10000000)
class NotificationPayload(BaseModel):
    channel: str = Field(default='sms', pattern='^(sms|email|push)$')
    message: str = Field(min_length=1, max_length=1400)
    to: str|None = Field(default=None, max_length=80)
class AlertCreatePayload(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    message: str = Field(min_length=10, max_length=1400)
    severity: str = Field(default='moderate', pattern='^(low|moderate|high|critical)$')
    area: str = Field(min_length=2, max_length=160)
    language: str = Field(default='en', max_length=15)
    issuing_authority: str = Field(min_length=2, max_length=120)
    source_url: str = Field(min_length=10, max_length=2048)
class AlertSendPayload(BaseModel):
    to: str|None = Field(default=None, max_length=80)
class ScenarioInput(BaseModel):
    name: str = Field(default='Scenario', max_length=80)
    rainfall_delta: float = Field(default=0, ge=0, le=200)
    river_delta: float = Field(default=0, ge=0, le=5)
    road_closed: bool = False
    power_outage: bool = False
    shelter_closed: bool = False
class ScenarioComparePayload(BaseModel):
    scenarios: list[ScenarioInput] = Field(min_length=2, max_length=4)
class WhatIfPayload(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    inputs: dict[str, float]
class ObservationPayload(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    description: str = Field(min_length=1, max_length=2000)
    water_depth_cm: float|None = Field(default=None, ge=0, le=1000)
    category: str = Field(default='water_level', pattern='^(water_level|blocked_road|rescue_needed|shelter|infrastructure|other)$')
    reporter_key: str = Field(default='', max_length=128)
    photo_data: str|None = Field(default=None, max_length=140000)
class ObservationSignalPayload(BaseModel):
    reporter_key: str = Field(min_length=12, max_length=128)
    signal: str = Field(pattern='^(confirm|dispute|abuse)$')
class ObservationDeletePayload(BaseModel):
    reporter_key: str = Field(min_length=12, max_length=128)
class ObservationReviewPayload(BaseModel):
    verification_status: str = Field(pattern='^(reviewing|verified|rejected|unverified)$')
    review_note: str = Field(default='', max_length=500)
class ResourceReadinessPayload(BaseModel):
    readiness_status: str = Field(pattern='^(confirmed|unverified|unavailable)$')
class ShelterCheckInPayload(BaseModel):
    capacity: int = Field(ge=0, le=1000000)
    occupied: int = Field(ge=0, le=1000000)

def _records(kind:str): return load(kind)
def _record(kind:str,payload:dict[str,Any],prefix:str):
    from uuid import uuid4
    item={'id':f'{prefix}-{uuid4().hex[:10].upper()}','created_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),'status':'open',**payload}
    save(kind,item); audit(f'{kind}_created',str(payload.get('created_by','operator')),item['id'],{'status':item['status']}); return item

def require_operator(request:Request, roles:tuple[str,...]=('admin','responder')):
    if not auth_enabled():
        client=request.client.host if request.client else ''
        try: is_loopback=ipaddress.ip_address(client).is_loopback
        except ValueError: is_loopback=False
        lan_mode=os.getenv('AEGIS_LAN_MODE','false').lower() in ('1','true','yes')
        if lan_mode or not is_loopback:
            raise HTTPException(503,'Operator actions require configured authentication when accessed over a network. Configure AEGIS_AUTH_ENABLED, AEGIS_AUTH_SECRET, and AEGIS_USERS_JSON.')
        return {'sub':'local-demo','role':'admin'}
    header=request.headers.get('authorization','')
    if not header.startswith('Bearer '): raise HTTPException(401,'Bearer token required')
    user=decode_token(header[7:])
    if not user: raise HTTPException(401,'Invalid or expired bearer token')
    if user.get('role') not in roles: raise HTTPException(403,'Insufficient role')
    return user
@app.post('/api/auth/login')
def auth_login(payload:LoginPayload,request:Request):
    enforce_rate_limit(request,8)
    result=authenticate(payload.username,payload.password)
    if not result: raise HTTPException(401,'Invalid credentials or auth secret is not configured')
    return result
@app.get('/api/trigger')
def trigger(request:Request,lat:float=Query(25.5941,ge=-90,le=90),lon:float=Query(85.1376,ge=-180,le=180)):
    enforce_rate_limit(request,12);return run_aegis_swarm(lat,lon)
@app.get('/api/forecast')
def forecast(request:Request,lat:float=Query(25.5941,ge=-90,le=90),lon:float=Query(85.1376,ge=-180,le=180)):
    enforce_rate_limit(request,12);return forecast_from_swarm(run_aegis_swarm(lat,lon))
@app.get('/api/weather-forecast')
def weather_forecast(request:Request,lat:float=Query(25.5941,ge=-90,le=90),lon:float=Query(85.1376,ge=-180,le=180)):
    enforce_rate_limit(request,30)
    try:
        return get_weather_forecast(lat,lon)
    except ForecastUnavailable as exc:
        raise HTTPException(503,str(exc)) from exc
@app.get('/api/geocode')
def geocode(request:Request,q:str=Query(...,min_length=2,max_length=200),limit:int=Query(5,ge=1,le=10)):
    enforce_rate_limit(request,20)
    try:
        r=requests.get('https://nominatim.openstreetmap.org/search',params={'q':q,'format':'jsonv2','addressdetails':1,'limit':limit},headers={'User-Agent':'Project-Aegis/2.0'},timeout=6); r.raise_for_status(); return {'results':r.json()}
    except requests.RequestException as exc: raise HTTPException(502,f'Geocoding unavailable: {exc}')
@app.get('/api/nearby')
def nearby(request:Request,lat:float=Query(...,ge=-90,le=90),lon:float=Query(...,ge=-180,le=180),kind:str=Query('hospital'),radius:int=Query(5000,ge=100,le=25000)):
    enforce_rate_limit(request,12)
    category=RESOURCE_CATEGORIES.get(kind)
    if category is None: raise HTTPException(400,'Unsupported facility kind')
    rounded_lat,rounded_lon=round(lat,3),round(lon,3)
    cache_key=(kind,rounded_lat,rounded_lon,radius)
    now=time.monotonic()
    with _nearby_cache_lock:
        cached=_nearby_cache.get(cache_key)
        if cached and now-cached['cached_at']<900:
            return {**cached['response'],'cache_status':'fresh'}
    around=f'(around:{radius},{rounded_lat},{rounded_lon})'
    statements=''.join(f'nwr["{key}"="{value}"]{around};' for key,value in category['selectors'])
    query=f'[out:json][timeout:12];({statements});out center meta tags;'
    endpoints=('https://overpass-api.de/api/interpreter','https://overpass.kumi.systems/api/interpreter','https://overpass.private.coffee/api/interpreter')
    for endpoint in endpoints:
        try:
            r=requests.post(endpoint,data={'data':query},headers={'User-Agent':'Project-Aegis/2.2 (nearby facility lookup)'},timeout=15); r.raise_for_status(); out=[]
            seen=set()
            for e in r.json().get('elements',[]):
                c=e.get('center',{}); tags_found=e.get('tags',{}); plat=e.get('lat',c.get('lat')); plon=e.get('lon',c.get('lon'))
                item_id=(e.get('type'),e.get('id'))
                if plat is None or plon is None or item_id in seen: continue
                try:
                    plat,plon=float(plat),float(plon)
                    if not (-90<=plat<=90 and -180<=plon<=180): continue
                except (TypeError,ValueError,OverflowError): continue
                seen.add(item_id)
                osm_url=f"https://www.openstreetmap.org/{e.get('type')}/{e.get('id')}" if e.get('type') and e.get('id') else OSM_DATA_URL
                out.append({
                    'id':e.get('id'),'osm_type':e.get('type'),
                    'name':tags_found.get('name') or tags_found.get('brand') or category['label'],
                    'lat':plat,'lon':plon,'kind':kind,'phone':tags_found.get('phone') or tags_found.get('contact:phone'),
                    'address':', '.join(x for x in (tags_found.get('addr:street'),tags_found.get('addr:city')) if x),
                    'osm_url':osm_url,'last_edited_at':e.get('timestamp'),
                    'source':'OpenStreetMap','source_url':osm_url,'license':'Open Database License (ODbL)',
                    'license_url':OSM_COPYRIGHT_URL,'retrieved_at':None,'trust_tier':OSM_TRUST_TIER,
                    'availability':'unverified','tags':tags_found,
                })
            fetched=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
            for item in out: item['retrieved_at']=fetched
            response={'kind':kind,'category':category,'results':out,'live_available':True,'provider':'OpenStreetMap Overpass','attribution':OSM_ATTRIBUTION,'attribution_url':OSM_COPYRIGHT_URL,'license':'ODbL','license_url':OSM_COPYRIGHT_URL,'trust_tier':OSM_TRUST_TIER,'source_url':OSM_DATA_URL,'fetched_at':fetched,'radius_m':radius,'cache_status':'live','message':f'{len(out)} map listings found' if out else f'No mapped {category["label"].lower()} found nearby.'}
            with _nearby_cache_lock:
                _nearby_cache[cache_key]={'cached_at':now,'response':response}
                if len(_nearby_cache)>256:
                    oldest=sorted(_nearby_cache,key=lambda key:_nearby_cache[key]['cached_at'])[:64]
                    for key in oldest: _nearby_cache.pop(key,None)
            return response
        except (requests.RequestException,ValueError,TypeError):
            continue
    with _nearby_cache_lock:
        cached=_nearby_cache.get(cache_key)
    if cached:
        response={**cached['response'],'live_available':False,'cache_status':'stale','message':'Live map lookup unavailable; showing previously retrieved OpenStreetMap listings.'}
        return response
    return {'kind':kind,'category':category,'results':[],'live_available':False,'provider':'OpenStreetMap Overpass','attribution':OSM_ATTRIBUTION,'attribution_url':OSM_COPYRIGHT_URL,'license':'ODbL','license_url':OSM_COPYRIGHT_URL,'trust_tier':OSM_TRUST_TIER,'source_url':OSM_DATA_URL,'fetched_at':None,'radius_m':radius,'cache_status':'unavailable','message':'Nearby places service is temporarily unavailable and no cached results exist.'}
@app.get('/api/resource-categories')
def resource_categories():
    return {'categories':public_categories(),'source':'OpenStreetMap','source_url':OSM_DATA_URL,'attribution':OSM_ATTRIBUTION,'attribution_url':OSM_COPYRIGHT_URL,'license':'ODbL','license_url':OSM_COPYRIGHT_URL,'trust_tier':OSM_TRUST_TIER,'notice':'These categories query community-mapped listings. Coverage varies and facilities may be missing, duplicated, outdated, or unavailable.'}
@app.get('/api/resource-packs')
def list_resource_packs():
    packs=[]
    if not RESOURCE_PACK_DIR.exists():
        return {'packs':packs,'message':'No regional resource packs have been built or published. This is not nationwide facility coverage.'}
    for path in sorted(RESOURCE_PACK_DIR.glob('*.geojson.gz')):
        filename=path.name
        if not filename.endswith('.geojson.gz'): continue
        base=filename[:-len('.geojson.gz')]
        quality_path=RESOURCE_PACK_DIR/f'{base}.quality.json'
        try:
            quality=json.loads(quality_path.read_text(encoding='utf-8')) if quality_path.is_file() else {}
        except (OSError,ValueError):
            quality={}
        packs.append({'filename':filename,'download_url':f'/api/resource-packs/{filename}','pack_bytes':path.stat().st_size,'feature_count':quality.get('feature_count'),'region_id':quality.get('region_id'),'version':quality.get('version'),'source':quality.get('source','OpenStreetMap via Overpass'),'attribution':quality.get('attribution',OSM_ATTRIBUTION),'license':quality.get('license','ODbL'),'trust_tier':quality.get('trust_tier',OSM_TRUST_TIER),'quality':quality.get('quality')})
    return {'packs':packs,'message':'Regional OpenStreetMap packs are community map data, may be incomplete or outdated, and do not verify facility availability.'}
@app.get('/api/resource-packs/{filename}')
def download_resource_pack(filename:str):
    if filename!=Path(filename).name or not filename.endswith('.geojson.gz') or not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,63}-(?:\d{4}-\d{2}-\d{2}|\d{8}T\d{6}Z)\.geojson\.gz',filename):
        raise HTTPException(400,'Invalid regional pack name.')
    path=RESOURCE_PACK_DIR/filename
    if not path.is_file():
        raise HTTPException(404,'Regional pack not found.')
    return FileResponse(path,media_type='application/gzip',filename=filename)
@app.get('/api/model')
def model_metadata():
    if not MODEL_PATH.exists(): return {'artifact':MODEL_PATH.name,'available':False}
    try:
        a=joblib.load(MODEL_PATH); return {'artifact':MODEL_PATH.name,'available':True,'model_family':a.get('model_family'),'features':a.get('features',[]),'label':a.get('label'),'dataset_rows':a.get('dataset_rows'),'positive_rows':a.get('positive_rows'),'roc_auc':a.get('roc_auc'),'dataset':os.path.basename(a.get('source_path','')),'event_dataset':os.path.basename(a.get('event_source_path','')),'label_provenance':a.get('label_provenance'),'coverage_region':a.get('coverage_region'),'training_notice':a.get('training_notice'),'operationally_validated':a.get('operationally_validated',False),'horizon_metrics':a.get('horizon_metrics',{}),'horizon_counts':a.get('horizon_counts',{}),'probability_calibration':a.get('probability_calibration')}
    except Exception as exc: return {'artifact':MODEL_PATH.name,'available':False,'error':str(exc)}

@app.get('/api/model/input-ranges')
def model_input_range_metadata():
    try:
        if not MODEL_PATH.exists(): raise FileNotFoundError('Trained Patna model is unavailable.')
        return {'available':True,'ranges':get_model_input_ranges(),'source':'Local Patna training CSV; observed minimum and maximum values.'}
    except Exception as exc:
        return {'available':False,'ranges':{},'message':str(exc)}

@app.post('/api/model/what-if')
def model_what_if(payload:WhatIfPayload,request:Request):
    enforce_rate_limit(request,20)
    if not (25.05<=payload.lat<=26.05 and 84.55<=payload.lon<=85.75):
        raise HTTPException(422,'The trained model is only supported within its approximate Patna-area coverage.')
    if not MODEL_PATH.exists(): raise HTTPException(503,'The trained model is unavailable; no model-backed scenario was calculated.')
    try:
        result=predict_what_if(payload.inputs)
        return {'status':'simulation','model':'Patna event Extra Trees','probabilities':result['probabilities'],'inputs':result['inputs'],'notice':'Model output for user-adjusted inputs only. Uncalibrated research prototype; not a forecast or official warning. No spatial flood extent is modeled.'}
    except ValueError as exc:
        raise HTTPException(422,str(exc))
    except Exception:
        raise HTTPException(503,'Model-backed scenario is unavailable; the current estimate was not changed.')

@app.get('/api/evacuation')
def evacuation(lat:float=Query(...,ge=-90,le=90),lon:float=Query(...,ge=-180,le=180),population:int=Query(1000,ge=1,le=10000000),accessible:bool=False):
    """Return a deterministic evacuation plan that can later be backed by live routing."""
    factor=1.35 if accessible else 1.0
    return {'target':{'lat':lat,'lon':lon},'population':population,'accessible_route':accessible,'assembly_points':[{'name':'Illustrative candidate point · unverified','lat':lat+0.025,'lon':lon+0.02,'capacity':max(500,int(population*.7)),'capacity_estimate':max(500,int(population*.7))},{'name':'Illustrative secondary point · unverified','lat':lat-0.02,'lon':lon-0.025,'capacity':max(300,int(population*.5)),'capacity_estimate':max(300,int(population*.5))}],'waves':[{'wave':1,'people':int(population*.35),'people_estimate':int(population*.35),'eta_minutes':round(18*factor),'eta_estimate_minutes':round(18*factor)},{'wave':2,'people':int(population*.35),'people_estimate':int(population*.35),'eta_minutes':round(35*factor),'eta_estimate_minutes':round(35*factor)},{'wave':3,'people':population-int(population*.7),'people_estimate':population-int(population*.7),'eta_minutes':round(55*factor),'eta_estimate_minutes':round(55*factor)}],'route_status':'illustrative_planning_fallback','safety_status':'not_verified','warning':'Candidate coordinates, capacities, and travel times are generated examples. They are not verified shelters or safe evacuation directions.'}
@app.get('/api/route')
def route(request:Request,lat:float=Query(...,ge=-90,le=90),lon:float=Query(...,ge=-180,le=180),destination_lat:float=Query(...,ge=-90,le=90),destination_lon:float=Query(...,ge=-180,le=180),mode:str=Query('responder',pattern='^(public|responder)$')):
    enforce_rate_limit(request,20)
    try:
        url=f'https://router.project-osrm.org/route/v1/driving/{lon},{lat};{destination_lon},{destination_lat}'
        rr=requests.get(url,params={'overview':'full','geometries':'geojson'},timeout=8); rr.raise_for_status(); data=rr.json(); r=data['routes'][0]
        coords=[[y,x] for x,y in r['geometry']['coordinates']]
        return {'mode':mode,'coordinates':coords,'distance_km':round(r['distance']/1000,2),'duration_minutes':round(r['duration']/60,1),'routing_source':'osrm','road_closure_data_available':False,'safety_status':'not_verified','warning':'Road route is not checked against live flood depth or closure data.'}
    except Exception:
        return {'mode':mode,'coordinates':[[lat,lon],[(lat+destination_lat)/2,(lon+destination_lon)/2],[destination_lat,destination_lon]],'distance_km':round(((lat-destination_lat)**2+(lon-destination_lon)**2)**.5*111,2),'routing_source':'straight_line_fallback','road_closure_data_available':False,'safety_status':'not_verified','warning':'Straight-line fallback is not a navigable or verified safe route.'}
@app.post('/api/ai/triage')
def triage(payload:TriagePayload):
    text=payload.description.lower(); critical_words=('trapped','injured','child','fire','drowning','urgent','missing'); urgency='critical' if any(w in text for w in critical_words) else payload.urgency; people=payload.people_affected
    return {'urgency':urgency,'people_affected':people,'recommended_team':'medical_rescue' if any(w in text for w in ('injured','medical','hospital')) else 'water_rescue' if any(w in text for w in ('drowning','boat','water')) else 'general_response','summary':payload.description.strip()[:280],'triage_method':'keyword_rules','is_ai_model':False,'requires_human_review':True}
@app.get('/api/relief-demand')
def relief_demand(population:int=Query(1000,ge=1,le=10000000),severity:str='high',days:int=Query(3,ge=1,le=30)):
    mult={'low':.5,'moderate':1,'high':1.5,'critical':2}.get(severity,1); return {'population':population,'severity':severity,'days':days,'water_liters':int(population*3*days*mult),'meal_portions':int(population*2*days*mult),'blankets':int(population*.4*mult),'medical_kits':max(1,int(population/100*mult))}
@app.get('/api/guidance')
def public_guidance(lang:str='en',severity:str='moderate'):
    level=severity.lower() if severity.lower() in ('low','moderate','high','critical') else 'moderate'
    messages={'en':{'low':'Stay informed. Keep essential medicines and a charged phone ready.','moderate':'Monitor official alerts, avoid waterlogged roads, and prepare essential supplies.','high':'Move to a safer place if local authorities advise it. Keep children and essential medicines close.','critical':'Follow official evacuation instructions now. Do not walk or drive through floodwater. Call local emergency services if in immediate danger.'},'hi':{'low':'आधिकारिक सूचना देखते रहें। जरूरी दवाइयाँ और चार्ज किया हुआ फोन तैयार रखें।','moderate':'आधिकारिक चेतावनियाँ देखें, जलभराव वाली सड़कों से बचें और जरूरी सामान तैयार रखें।','high':'स्थानीय प्रशासन की सलाह पर सुरक्षित स्थान पर जाएँ। बच्चों और जरूरी दवाइयों को साथ रखें।','critical':'अभी आधिकारिक निकासी निर्देशों का पालन करें। बाढ़ के पानी में पैदल या वाहन से न जाएँ। तत्काल खतरे में स्थानीय आपातकालीन सेवा को कॉल करें।'}}
    language='hi' if lang.lower().startswith('hi') else 'en'
    return {'language':language,'severity':level,'message':messages[language][level],'source':'Prepared public safety guidance; follow current official instructions.','is_machine_translated':False}
@app.get('/api/data-sources')
def data_sources():
    from backend.integrations import gauge_feed, satellite_config
    gauge=gauge_feed(); sat=satellite_config()
    return {'sources':[{'name':'Open-Meteo weather and GloFAS discharge','status':'live_on_request_with_fallback','freshness':'request-time','note':'Modeled discharge, not a Patna gauge reading'},{'name':'Gauge feed','status':gauge.get('status'),'freshness':'request-time','records':len(gauge.get('gauges',[]))},{'name':'Aegis Extra Trees model','status':'available' if MODEL_PATH.exists() else 'unavailable','freshness':'trained-artifact','coverage':'Patna-area single-point weather history; exploratory and not operationally validated'},{'name':'India Flood Inventory','status':'local historical records','coverage':'Documented Bihar/Patna flood events through 2023; sparse and incomplete'},{'name':'Bihar satellite inundation history','status':'bundled_reference_data' if (Path(__file__).resolve().parent.parent/'data'/'bihar_subdistrict_inundation_2021_2025.csv').exists() else 'unavailable','coverage':'Monthly sub-district flood extent, 2021–2025; not a forecast'},{'name':'OpenStreetMap/Overpass','status':'live_on_request_with_fallback','freshness':'request-time'},{'name':'Satellite imagery','status':sat.get('status'),'freshness':'tile-provider; imagery is not flood classification'}]}

@app.get('/api/historical-events')
def historical_events(district:str=Query('Patna',min_length=2,max_length=80),limit:int=Query(50,ge=1,le=200)):
    """District-scope historical inventory; records are not exact flood footprints."""
    path=Path(__file__).resolve().parent.parent/'data'/'india_flood_inventory_v3.csv'
    if not path.exists(): return {'available':False,'events':[],'message':'Historical event inventory is not installed.'}
    df=pd.read_csv(path,low_memory=False)
    subset=df[df['Districts'].fillna('').str.contains(district,case=False,regex=False)].copy()
    subset['start_parsed']=pd.to_datetime(subset['Start Date'],format='%d-%m-%Y %H:%M',errors='coerce')
    subset=subset.dropna(subset=['start_parsed']).sort_values('start_parsed',ascending=False).head(limit)
    events=[]
    for _,row in subset.iterrows():
        clean=lambda key: None if pd.isna(row.get(key)) else str(row.get(key)).strip()
        events.append({'id':clean('UEI') or '','date':row['start_parsed'].date().isoformat(),'end_date':clean('End Date'),'districts':clean('Districts') or district,'state':clean('State'),'cause':clean('Main Cause') or 'Flood event','severity':clean('Severity'),'fatalities':clean('Human fatality'),'latitude':None if pd.isna(row.get('Latitude')) else float(row.get('Latitude')),'longitude':None if pd.isna(row.get('Longitude')) else float(row.get('Longitude'))})
    return {'available':True,'district_query':district,'events':events,'count':len(events),'scope':'Inventory reports are often multi-district and may lack coordinates; these are contextual records, not street-level observed flood extents.','source':'IIT Delhi India Flood Inventory v3, 1967–2023','source_url':'https://zenodo.org/records/11275211'}

@app.get('/api/inundation-history')
def inundation_history(lat:float=Query(25.5941,ge=-90,le=90),lon:float=Query(85.1376,ge=-180,le=180)):
    """Return observed monthly Patna-district satellite inundation, not a forecast."""
    if not (25.05<=lat<=26.05 and 84.55<=lon<=85.75):
        return {'available':False,'district':'Patna','reason':'The bundled reference covers Patna district only; this target is outside its approximate bounds.'}
    path=Path(__file__).resolve().parent.parent/'data'/'bihar_subdistrict_inundation_2021_2025.csv'
    if not path.exists(): return {'available':False,'district':'Patna','reason':'Bundled satellite history is unavailable.'}
    try:
        df=pd.read_csv(path)
        df['district_code']=df['object_id'].astype(str).str.split('-').str[1]
        patna=df[df['district_code']=='230'].copy()
        if patna.empty: return {'available':False,'district':'Patna','reason':'No Patna sub-district rows were found in the bundled file.'}
        for col in ('count_bhuvan_pixels','count_inundated_pixels'):
            patna[col]=pd.to_numeric(patna[col],errors='coerce').fillna(0)
        grouped=patna.groupby(['year','month_num'],as_index=False).agg(total_pixels=('count_bhuvan_pixels','sum'),inundated_pixels=('count_inundated_pixels','sum'),subdistricts=('object_id','nunique'),observed_subdistricts=('inundation_pct','count'))
        history=[]
        for row in grouped.to_dict('records'):
            total=row['total_pixels'] or 0
            history.append({'year':int(row['year']),'month':int(row['month_num']),'inundated_percent':round(100*row['inundated_pixels']/total,4) if total else 0,'subdistricts':int(row['subdistricts']),'inundated_pixels':int(row['inundated_pixels']),'total_pixels':int(total)})
        history.sort(key=lambda x:(x['year'],x['month']))
        return {'available':True,'district':'Patna','history':history,'spatial_scope':'District aggregate across 23 sub-district map IDs; not point-specific. Only months present in the source are included.','label':'Observed satellite inundation share','source':'CivicDataLab, Bihar Sub-District Level Flood Inundation (2021–2025)','license':'CC BY-SA 4.0','source_url':'https://civicdataspace.in/datasets/2c10ed21-6f6b-4f58-83dc-5406fb048e25','is_forecast':False}
    except Exception as exc:
        raise HTTPException(500,f'Could not read local inundation history: {exc}')
@app.get('/api/evidence-timeline')
def evidence_timeline(lat:float=Query(25.5941,ge=-90,le=90),lon:float=Query(85.1376,ge=-180,le=180),district:str=Query('Patna',min_length=2,max_length=80)):
    from datetime import datetime,timezone
    entries=[]; events=historical_events(district,200)
    for event in events.get('events',[]):
        entries.append({'date':event['date'],'kind':'documented_event','title':f"{event.get('cause') or 'Flood event'} · {event.get('districts') or district}",'status':'historical_context','spatial_scope':'district inventory; not a street-level footprint','source':events.get('source'),'source_url':events.get('source_url'),'latitude':event.get('latitude'),'longitude':event.get('longitude')})
    extent=inundation_history(lat,lon)
    for month in extent.get('history',[]):
        entries.append({'date':f"{month['year']:04d}-{month['month']:02d}-01",'kind':'satellite_monthly_summary','title':f"{month['inundated_percent']}% district inundation share · {month['year']}-{month['month']:02d}",'status':'observed_historical_summary','spatial_scope':extent.get('spatial_scope'),'source':extent.get('source'),'source_url':extent.get('source_url')})
    for incident in INCIDENTS:
        stamp=incident.get('timestamp') or incident.get('created_at')
        if stamp: entries.append({'date':str(stamp)[:10],'kind':'community_incident','title':f"Incident report · {incident.get('urgency','medium')} urgency",'status':incident.get('verification_status','unverified'),'spatial_scope':'user-submitted target; verify before acting','source':'Aegis community report','id':incident.get('id'),'latitude':incident.get('lat'),'longitude':incident.get('lon')})
    for report in _records('observation'):
        stamp=report.get('created_at') or report.get('timestamp')
        if stamp: entries.append({'date':str(stamp)[:10],'kind':'community_observation','title':'Community water observation','status':report.get('verification_status','unverified'),'spatial_scope':'user-submitted target; verify before acting','source':'Aegis community report','id':report.get('id'),'latitude':report.get('lat'),'longitude':report.get('lon')})
    entries.sort(key=lambda item:item['date'],reverse=True)
    return {'generated_at':datetime.now(timezone.utc).isoformat(),'entries':entries[:500],'count':min(len(entries),500),'sources':{'events':events.get('source'),'satellite':extent.get('source')},'limits':['This timeline aligns records by date only; it does not claim spatial overlap or cause.','District event records are contextual and can include multi-district events.','Satellite values are monthly Patna-district aggregates, not target-point observations.','Community reports are unverified unless explicitly reviewed.','Live gauge observations are not included unless a verified feed is configured.']}
@app.post('/api/feedback')
def feedback(payload:FeedbackPayload,request:Request):
    enforce_rate_limit(request,12)
    item=_record('feedback',{'category':payload.category,'message':payload.message.strip(),'page':payload.page,'status':'received','created_by':'public'},'FDB')
    return {'status':'recorded','id':item['id'],'timestamp':item['created_at'],'message':'Feedback stored for project review.'}
@app.get('/api/feedback')
def feedback_inbox(request:Request):
    require_operator(request,('admin',))
    return {'feedback':list(reversed(load('feedback')[-200:])),'count':len(load('feedback')),'message':'Feedback is project feedback, not an emergency report.'}
@app.get('/api/export/incidents')
def export_incidents():
    from fastapi.responses import PlainTextResponse
    import csv,io
    buf=io.StringIO(); fields=['id','timestamp','status','urgency','description','lat','lon']; w=csv.DictWriter(buf,fieldnames=fields); w.writeheader(); w.writerows([{k:x.get(k,'') for k in fields} for x in INCIDENTS]); return PlainTextResponse(buf.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename=aegis-incidents.csv'})

@app.get('/api/gauges')
def gauges(): return gauge_feed()
@app.get('/api/satellite')
def satellite(): return satellite_config()
@app.post('/api/notifications/send')
def send_notification(payload:NotificationPayload,request:Request):
    require_operator(request,('admin','supervisor'))
    raise HTTPException(410,'Direct notification sending is disabled. Create an alert draft, obtain an authenticated approval, then submit that approved alert for delivery.')
@app.websocket('/ws/telemetry')
async def telemetry(websocket:WebSocket):
    await websocket.accept()
    try:
        while True:
            payload=await websocket.receive_json(); payload['received_at']=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(); await websocket.send_json({'status':'accepted','telemetry':payload})
    except WebSocketDisconnect: pass

@app.get('/api/admin/audit')
def admin_audit(request:Request):
    require_operator(request,('admin',))
    return {'audit_ready':True,'records':list(reversed(load('audit')[-500:])),'message':'Audit actions are stored in the local SQLite database.'}
@app.get('/api/auth/status')
def auth_status():
    import os
    
    try: user_count=len(json.loads(os.getenv('AEGIS_USERS_JSON','{}'))) if auth_enabled() else 0
    except Exception: user_count=0
    return {'authentication_enabled':auth_enabled(),'configured_users':user_count,'mode':'configured' if auth_enabled() else 'local_demo'}
@app.get('/api/status')
def status(request:Request):
    client=request.client.host if request.client else ''
    try: local_access=ipaddress.ip_address(client).is_loopback
    except ValueError: local_access=False
    configured=auth_enabled()
    return {'status':'demo_ready' if MODEL_PATH.exists() else 'degraded','service':'aegis','model_available':MODEL_PATH.exists(),'incident_count':len(INCIDENTS),'analytics':analytics(),'authentication_enabled':configured,'operator_actions_available':configured or (local_access and os.getenv('AEGIS_LAN_MODE','false').lower() not in ('1','true','yes')),'lan_mode':os.getenv('AEGIS_LAN_MODE','false').lower() in ('1','true','yes'),'limitations':['Research model is not operationally validated.','Live gauge and flood-depth road closure feeds are not configured by default.']}
@app.get('/api/situation-room')
def situation_room():
    from datetime import datetime,timezone
    sources=data_sources()['sources']; gauges=gauge_feed(); observations=_records('observation'); verified=sum(x.get('verification_status')=='verified' for x in observations); unverified=len(observations)-verified
    pending=sum(1 for item in INCIDENTS if item.get('verification_status','unverified') in ('unverified','reviewing'))
    signal_status='insufficient_comparable_evidence' if not gauges.get('gauges') or verified==0 else 'multi_source_context_available'
    return {'generated_at':datetime.now(timezone.utc).isoformat(),'target':{'lat':25.5941,'lon':85.1376,'label':'Patna default view'},'incident_summary':{'total':len(INCIDENTS),'open':sum(x.get('status') not in ('resolved','closed') for x in INCIDENTS),'awaiting_verification':pending},'resource_summary':{'total':len(RESOURCES),'available':sum(x.get('status')=='available' for x in RESOURCES),'confirmed':sum(x.get('readiness_status')=='confirmed' for x in RESOURCES)},'signals':{'gauge_feed_status':gauges.get('status'),'gauge_records':len(gauges.get('gauges',[])) if isinstance(gauges.get('gauges'),list) else 0,'verified_community_observations':verified,'unverified_community_observations':unverified,'satellite_history':'monthly historical district reference; not live','rainfall':'modeled Open-Meteo history/forecast; not station observation','agreement_status':signal_status,'conflict_assessment':'not_computed','explanation':'Aegis reports evidence availability; it does not infer agreement or disagreement from incomparable or missing sources.'},'sources':sources,'limits':['Forecast is research-only and not operationally validated.','Facility records may be incomplete; verify by phone.','Routes are not checked against flood depth or road closures.']}
@app.get('/api/activity')
def activity(limit:int=Query(30,ge=1,le=100)):
    events=[]
    for item in INCIDENTS: events.append({'timestamp':item.get('timestamp'),'kind':'incident','id':item.get('id'),'status':item.get('status'),'verification_status':item.get('verification_status','unverified'),'summary':f"Incident {item.get('id','')} · {item.get('urgency','medium')} urgency"})
    for item in _records('observation'): events.append({'timestamp':item.get('created_at'),'kind':'community_observation','id':item.get('id'),'status':item.get('verification_status','unverified'),'summary':f"Community observation {item.get('id','')} · {'verified' if item.get('verification_status')=='verified' else 'unverified'}"})
    for item in _records('handoff'): events.append({'timestamp':item.get('created_at'),'kind':'supply_handoff','id':item.get('id'),'status':item.get('status'),'summary':f"Supply handoff {item.get('id','')} · {item.get('status','pending')}"})
    events.sort(key=lambda x:str(x.get('timestamp') or ''),reverse=True)
    return {'events':events[:limit],'generated_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),'message':'Activity includes records entered into this Aegis instance only.'}
@app.get('/api/simulate')
def simulate(request:Request,rainfall_delta:float=Query(0,ge=0,le=200),river_delta:float=Query(0,ge=0,le=5),road_closed:bool=False,power_outage:bool=False,shelter_closed:bool=False):
    enforce_rate_limit(request,60);return simulate_scenario(rainfall_delta,river_delta,road_closed,power_outage,shelter_closed)
@app.get('/api/incidents')
def incidents(status_filter:str|None=None,page:int=1,limit:int=50):
    page=max(1,int(page)); limit=min(200,max(1,int(limit))); rows=[x for x in INCIDENTS if not status_filter or x.get('status')==status_filter]; start=(page-1)*limit; return {'incidents':rows[start:start+limit],'page':page,'limit':limit,'total':len(rows)}
@app.post('/api/incidents')
def add_incident(payload:IncidentPayload,request:Request):
    enforce_rate_limit(request,30)
    if payload.photo_url and not payload.photo_url.startswith('https://'): raise HTTPException(400,'Photo reference must use HTTPS.')
    return create_incident(payload.model_dump())
@app.patch('/api/incidents/{incident_id}')
def patch_incident(incident_id:str,payload:UpdatePayload,request:Request):
    operator=require_operator(request,('admin','supervisor','responder'))
    changes=payload.model_dump(exclude_none=True)
    audit('incident_review','operator',incident_id,{'changes':changes,'role':operator.get('role')})
    item=update_incident(incident_id,changes)
    if not item: raise HTTPException(404,'Incident not found')
    return item
@app.get('/api/responders')
def responders(request:Request): require_operator(request,('admin','supervisor','responder')); return {'responders':RESPONDERS}
@app.post('/api/responders')
def add_responder(payload:dict[str,Any],request:Request):
    require_operator(request); return register(RESPONDERS,payload,'RSP')
@app.get('/api/resources')
def resources(request:Request): require_operator(request,('admin','supervisor','responder')); return {'resources':RESOURCES,'summary':{'total':len(RESOURCES),'available':sum(x.get('status')=='available' for x in RESOURCES),'confirmed':sum(x.get('readiness_status')=='confirmed' for x in RESOURCES),'unverified':sum(x.get('readiness_status')!='confirmed' for x in RESOURCES)}}
@app.post('/api/resources')
def add_resource(payload:dict[str,Any],request:Request):
    require_operator(request); return register(RESOURCES,payload,'RES')
@app.patch('/api/resources/{resource_id}/readiness')
def confirm_resource_readiness(resource_id:str,payload:ResourceReadinessPayload,request:Request):
    operator=require_operator(request,('admin','supervisor','responder'))
    item=next((x for x in RESOURCES if x.get('id')==resource_id),None)
    if not item: raise HTTPException(404,'Resource not found')
    readiness=payload.readiness_status
    item['readiness_status']=readiness; item['last_confirmed_at']=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat() if readiness=='confirmed' else item.get('last_confirmed_at'); item['confirmed_by']=operator.get('sub','operator'); save('resource',item); audit('resource_readiness_updated',operator.get('sub','operator'),resource_id,{'readiness_status':readiness}); return item
@app.get('/api/shelters')
def shelters(request:Request): require_operator(request,('admin','supervisor','responder')); return {'shelters':SHELTERS}
@app.post('/api/shelters')
def add_shelter(payload:dict[str,Any],request:Request):
    require_operator(request); return register(SHELTERS,payload,'SHL')
@app.patch('/api/shelters/{shelter_id}/check-in')
def shelter_check_in(shelter_id:str,payload:ShelterCheckInPayload,request:Request):
    operator=require_operator(request,('admin','supervisor','responder'));item=next((x for x in SHELTERS if x.get('id')==shelter_id),None)
    if not item: raise HTTPException(404,'Shelter record not found')
    capacity=payload.capacity;occupied=payload.occupied
    if capacity<0 or occupied<0 or occupied>capacity: raise HTTPException(422,'Occupancy must be between zero and the stated capacity.')
    item.update({'capacity':capacity,'occupied':occupied,'readiness_status':'confirmed','last_confirmed_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),'confirmed_by':operator.get('sub','operator')});save('shelter',item);audit('shelter_checked_in',operator.get('sub','operator'),shelter_id,{'capacity':capacity,'occupied':occupied});return item
@app.get('/api/alerts')
def alerts(request:Request): require_operator(request,('admin','supervisor')); return {'alerts':ALERTS}
@app.post('/api/alerts')
def add_alert(payload:AlertCreatePayload,request:Request):
    operator=require_operator(request,('admin','supervisor'))
    if not payload.source_url.startswith('https://'): raise HTTPException(422,'Alert source links must use HTTPS.')
    item=create_alert({**payload.model_dump(),'created_by':operator.get('sub','operator'),'history':[{'status':'draft','at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}]});audit('alert_drafted',operator.get('sub','operator'),item['id'],{'severity':item.get('severity'),'issuing_authority':item.get('issuing_authority')});return item
@app.patch('/api/alerts/{alert_id}')
def update_alert(alert_id:str,payload:dict[str,Any],request:Request):
    operator=require_operator(request,('admin','supervisor'));item=next((entry for entry in ALERTS if entry.get('id')==alert_id),None)
    if not item: raise HTTPException(404,'Alert draft not found')
    next_status=payload.get('status')
    allowed={'draft':('approved','cancelled'),'approved':('cancelled',)}
    if next_status not in allowed.get(item.get('status','draft'),()): raise HTTPException(409,'Alert status transition is not allowed')
    if next_status=='approved' and item.get('created_by')==operator.get('sub'): raise HTTPException(409,'A different authenticated operator must approve this alert draft.')
    from datetime import datetime,timezone
    stamp=datetime.now(timezone.utc).isoformat();item.update({'status':next_status,'reviewed_by':operator.get('sub','operator'),'reviewed_at':stamp});item.setdefault('history',[]).append({'status':next_status,'at':stamp,'actor':operator.get('sub','operator')});save('alert',item);audit(f'alert_{next_status}',operator.get('sub','operator'),alert_id,{});return item
@app.post('/api/alerts/{alert_id}/send')
def send_alert(alert_id:str,payload:AlertSendPayload,request:Request):
    operator=require_operator(request,('admin',));
    enforce_rate_limit(request,3)
    item=next((entry for entry in ALERTS if entry.get('id')==alert_id),None)
    if not item: raise HTTPException(404,'Alert draft not found')
    if item.get('status')!='approved': raise HTTPException(409,'Only an approved alert can be submitted for delivery')
    if not auth_enabled(): raise HTTPException(503,'Live alert delivery is disabled until operator authentication is enabled.')
    outbound=f"{item['issuing_authority']}: {item['message']} Source: {item['source_url']}"
    result=send_sms(outbound,payload.to)
    if result.get('status')=='accepted_by_provider':
        from datetime import datetime,timezone
        stamp=datetime.now(timezone.utc).isoformat();item.update({'status':'accepted_by_provider','provider_message_id':result.get('message_sid'),'provider_accepted_at':stamp,'delivery_confirmed':False});item.setdefault('history',[]).append({'status':'accepted_by_provider','at':stamp,'actor':operator.get('sub','operator'),'delivery_confirmed':False});save('alert',item)
    audit('alert_delivery_attempt',operator.get('sub','operator'),alert_id,{'provider':result.get('provider'),'status':result.get('status'),'delivery_confirmed':result.get('delivery_confirmed',False)});return {'alert_id':alert_id,**result}
@app.get('/api/analytics')
def get_analytics(): return analytics()
@app.post('/api/simulate/compare')
def compare_scenarios(payload:ScenarioComparePayload,request:Request):
    enforce_rate_limit(request,30);results=[]
    for scenario in payload.scenarios:
        values=scenario.model_dump(exclude={'name'})
        results.append({'name':scenario.name,**simulate_scenario(**values)})
    return {'results':results,'notice':'Simplified comparison only; not a location-specific forecast.'}
@app.post('/api/notifications/test')
def notification_test(payload:dict[str,Any],request:Request):
    operator=require_operator(request,('admin','supervisor'))
    if not auth_enabled(): raise HTTPException(503,'SMS testing is disabled until operator authentication is enabled.')
    enforce_rate_limit(request,3)
    channel=payload.get('channel','sms')
    if channel!='sms': raise HTTPException(400,'Only SMS delivery can be tested; in-app notices are local UI events.')
    result=send_sms(str(payload.get('message','Aegis delivery test')),payload.get('to'))
    audit('notification_test',operator.get('sub','operator'),result.get('message_sid'),{'status':result.get('status'),'provider':result.get('provider')})
    return result

@app.get('/api/observations')
def observations():
    rows=_records('observation')[-500:]
    for item in rows:
        item['trust_score'],item['age_hours']=_community_score(item,rows)
    rows.sort(key=lambda x:(x.get('trust_score',0),x.get('created_at','')),reverse=True)
    public_rows=[]
    for item in rows:
        public={k:v for k,v in item.items() if k not in ('reporter_id','signals','photo_data')}
        public['photo_attached']=bool(item.get('photo_data'))
        public_rows.append(public)
    return {'observations':public_rows,'verification_required':True,'trust_method':'50 base + up to 20 for confirmations − up to 30 for disputes + limited reporter history − up to 15 for age; crowd signal only, not official verification.'}
@app.post('/api/observations')
def add_observation(payload:ObservationPayload,request:Request):
    enforce_rate_limit(request,8)
    data=payload.model_dump(); data['lat']=round(data['lat'],3); data['lon']=round(data['lon'],3)
    data['description']=' '.join(data['description'].split())[:500]
    if data.get('photo_data') and not data['photo_data'].startswith('data:image/jpeg;base64,'):
        raise HTTPException(422,'Photo must be a compressed JPEG image.')
    # Suppress near-identical reports from the same category/location in a short window.
    rows=_records('observation'); now=__import__('datetime').datetime.now(__import__('datetime').timezone.utc)
    normalized=data['description'].casefold()
    for old in rows[-300:]:
        try: age=(now-__import__('datetime').datetime.fromisoformat(old['created_at'])).total_seconds()
        except Exception: continue
        if age<600 and old.get('category')==data['category'] and round(float(old.get('lat',999)),3)==data['lat'] and round(float(old.get('lon',999)),3)==data['lon'] and ' '.join(str(old.get('description','')).casefold().split())==normalized:
            raise HTTPException(409,'A similar report was already received recently.')
    reporter=data.pop('reporter_key','')
    import hashlib
    data['reporter_id']=hashlib.sha256(reporter.encode()).hexdigest()[:24] if reporter else ''
    if data.get('photo_data'):
        # Keep only the compressed image payload. Client must provide JPEG at <= 100 KB.
        try:
            import base64
            encoded=data['photo_data'].split(',',1)[1]; raw=base64.b64decode(encoded,validate=True)
            if len(raw)>100_000: raise ValueError
        except Exception: raise HTTPException(413,'Compressed photo must be 100 KB or smaller.')
    data.update({'verification_status':'unverified','source_type':'community_report','confirmations':0,'disputes':0,'abuse_flags':0,'trust_score':50,'moderation_status':'unreviewed'})
    item=_record('observation',data,'OBS')
    result={k:v for k,v in item.items() if k not in ('reporter_id','signals','photo_data')};result['photo_attached']=bool(item.get('photo_data'));return result
def _community_score(item,rows):
    return community_trust(item,rows)
@app.post('/api/observations/{observation_id}/signal')
def signal_observation(observation_id:str,payload:ObservationSignalPayload,request:Request):
    enforce_rate_limit(request,30); rows=_records('observation'); item=next((x for x in rows if x.get('id')==observation_id),None)
    if not item: raise HTTPException(404,'Report not found')
    import hashlib
    voter=hashlib.sha256(payload.reporter_key.encode()).hexdigest()[:24]
    votes=item.setdefault('signals',{})
    if voter==item.get('reporter_id'): raise HTTPException(409,'Report authors cannot signal their own report.')
    if voter in votes: raise HTTPException(409,'This device already sent a signal for this report.')
    votes[voter]=payload.signal
    if payload.signal=='confirm': item['confirmations']=int(item.get('confirmations',0))+1
    elif payload.signal=='dispute': item['disputes']=int(item.get('disputes',0))+1
    else: item['abuse_flags']=int(item.get('abuse_flags',0))+1; item['moderation_status']='review_requested'
    item['trust_score'],item['age_hours']=_community_score(item,rows);save('observation',item);audit('community_report_signal',voter,observation_id,{'signal':payload.signal});return {k:v for k,v in item.items() if k not in ('signals','reporter_id')}
@app.get('/api/observations/{observation_id}/photo')
def observation_photo(observation_id:str,request:Request):
    enforce_rate_limit(request,30); item=next((x for x in _records('observation') if x.get('id')==observation_id),None)
    if not item or not item.get('photo_data'): raise HTTPException(404,'No report photo is available.')
    return {'photo_data':item['photo_data'],'content_type':'image/jpeg','notice':'Community-submitted image; unverified.'}
@app.post('/api/observations/delete-own')
def delete_own_observations(payload:ObservationDeletePayload,request:Request):
    enforce_rate_limit(request,5)
    import hashlib
    owner=hashlib.sha256(payload.reporter_key.encode()).hexdigest()[:24]; rows=_records('observation')
    owned=[x for x in rows if owner and x.get('reporter_id')==owner]
    for item in owned: delete_record('observation',item['id'])
    audit('community_reports_deleted',owner,None,{'count':len(owned)})
    return {'deleted':len(owned),'message':'Your community reports were deleted from the local Aegis database.'}
@app.patch('/api/observations/{observation_id}')
def verify_observation(observation_id:str,payload:ObservationReviewPayload,request:Request):
    user=require_operator(request,('admin','supervisor','responder')); rows=_records('observation'); item=next((x for x in rows if x.get('id')==observation_id),None)
    if not item: raise HTTPException(404,'Observation not found')
    state=payload.verification_status
    item.update({'verification_status':state,'reviewed_by':user.get('sub','operator'),'reviewed_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),'review_note':payload.review_note});save('observation',item);audit('observation_reviewed',user.get('sub','operator'),observation_id,{'verification_status':state});return item
@app.post('/api/handoffs')
def add_handoff(payload:dict[str,Any],request:Request):
    user=require_operator(request,('admin','supervisor','responder')); note=str(payload.get('note','')).strip()
    if not note: raise HTTPException(422,'Handover note is required.')
    return _record('handoff',{**payload,'note':note[:3000],'created_by':user.get('sub','operator'),'status':'pending_acknowledgement'},'HOF')
@app.get('/api/handoffs')
def handoffs(request:Request): require_operator(request,('admin','supervisor','responder'));return {'handoffs':list(reversed(_records('handoff')[-200:]))}
@app.post('/api/preparedness')
def save_preparedness(payload:dict[str,Any],request:Request):
    enforce_rate_limit(request,15);title=str(payload.get('title','Household preparedness plan')).strip()[:120]
    return _record('preparedness',{'title':title,'checklist':payload.get('checklist',[]),'location':payload.get('location',''),'created_by':'public_local'},'PRE')
@app.post('/api/corrections')
def public_correction(payload:dict[str,Any],request:Request):
    enforce_rate_limit(request,20);description=str(payload.get('description','')).strip()
    if not description: raise HTTPException(422,'Correction details are required.')
    return _record('correction',{'description':description[:1500],'feature_id':str(payload.get('feature_id',''))[:120],'status':'needs_review'},'COR')
@app.post('/api/drills')
def create_drill(payload:dict[str,Any],request:Request):
    user=require_operator(request,('admin','supervisor','responder'));return _record('drill',{'name':str(payload.get('name','Flood response exercise'))[:120],'scenario':payload.get('scenario',{}),'status':'practice_only','created_by':user.get('sub','operator')},'DRL')
@app.get('/api/after-action')
def after_action():
    incidents=list(INCIDENTS); return {'generated_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),'incidents_total':len(incidents),'open':sum(x.get('status') not in ('resolved','closed') for x in incidents),'verified_observations':sum(x.get('verification_status')=='verified' for x in _records('observation')),'unverified_observations':sum(x.get('verification_status')!='verified' for x in _records('observation')),'handoffs_pending':sum(x.get('status')=='pending_acknowledgement' for x in _records('handoff')),'note':'Operational review summary only; completeness depends on entered records.'}
@app.get('/api/model-monitor')
def model_monitor():
    model=model_metadata();return {'model_available':model.get('available',False),'coverage_region':model.get('coverage_region'),'operationally_validated':model.get('operationally_validated',False),'training_rows':model.get('dataset_rows'),'positive_rows':model.get('positive_rows'),'validation':model.get('horizon_metrics'),'monitoring_status':'Research-only; live performance/drift cannot be measured without reviewed outcome labels.','last_training':'See bundled artifact metadata.'}
@app.get('/api/rainfall-history')
def rainfall_history(lat:float=Query(25.5941,ge=-90,le=90),lon:float=Query(85.1376,ge=-180,le=180)):
    try:
        r=requests.get('https://api.open-meteo.com/v1/forecast',params={'latitude':lat,'longitude':lon,'daily':'precipitation_sum','past_days':7,'forecast_days':1,'timezone':'auto'},timeout=12);r.raise_for_status();d=r.json()['daily'];return {'available':True,'times':d['time'],'precipitation_mm':d['precipitation_sum'],'source':'Open-Meteo forecast/reanalysis blend','fetched_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),'classification':'modeled, not a local rain gauge'}
    except Exception:return {'available':False,'times':[],'precipitation_mm':[],'source':'Open-Meteo','message':'Rainfall series unavailable; no values were substituted.'}
frontend_path=os.path.abspath(os.path.join(os.path.dirname(__file__),'..','frontend'))
app.mount('/',StaticFiles(directory=frontend_path,html=True),name='frontend')
