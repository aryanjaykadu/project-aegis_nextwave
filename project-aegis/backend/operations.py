"""In-memory operational services used by the Aegis demo and API adapters."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
import threading
from typing import Any
from backend.storage import load, save, audit
INCIDENTS=load('incident'); RESPONDERS=load('responder'); RESOURCES=load('resource'); ALERTS=load('alert'); SHELTERS=load('shelter')
_incident_lock=threading.Lock()
def now(): return datetime.now(timezone.utc).isoformat()
def risk_severity(score:float)->str:
    return 'critical' if score>=.75 else 'high' if score>=.5 else 'moderate' if score>=.25 else 'low'
def simulate_scenario(rainfall_delta:float=0,river_delta:float=0,road_closed:bool=False,power_outage:bool=False,shelter_closed:bool=False)->dict[str,Any]:
    score=min(1,max(0,.35+rainfall_delta/200+river_delta/5+(.12 if road_closed else 0)+(.08 if power_outage else 0)+(.1 if shelter_closed else 0))); sev=risk_severity(score)
    actions={'critical':'Evacuate low-lying areas and dispatch emergency response teams.','high':'Pre-position rescue teams, supplies, and public warnings.','moderate':'Monitor river gauges and prepare shelters for activation.','low':'Continue routine monitoring and keep response routes available.'}
    return {'risk_score':round(score,3),'severity':sev,'recommended_action':actions[sev],'inputs':{'rainfall_delta':rainfall_delta,'river_delta':river_delta,'road_closed':road_closed,'power_outage':power_outage,'shelter_closed':shelter_closed}}
def create_incident(payload):
    with _incident_lock:
        key=payload.get('idempotency_key')
        if key:
            existing=next((x for x in INCIDENTS if x.get('idempotency_key')==key),None)
            if existing:return existing
        item={'id':f'INC-{uuid4().hex[:10].upper()}','timestamp':now(),'urgency':payload.get('urgency','medium'),'status':'open','verification_status':'unverified','history':[],'created_by':payload.get('created_by','public'),**payload}; item['history'].append({'timestamp':item['timestamp'],'status':'open'}); INCIDENTS.append(item); save('incident',item); audit('incident_created',item['created_by'],item['id'],{'verification_status':item['verification_status']}); return item
def update_incident(incident_id,payload):
    item=next((x for x in INCIDENTS if x['id']==incident_id),None)
    if not item:return None
    item.update(payload); item.setdefault('history',[]).append({'timestamp':now(),'status':item.get('status'),'update':payload}); save('incident',item); audit('incident_updated','operator',incident_id,payload); return item
def register(collection,payload,prefix):
    item={'id':f'{prefix}-{uuid4().hex[:10].upper()}','timestamp':now(),'status':'available','readiness_status':'unverified','last_confirmed_at':None,**payload}; collection.append(item); kind={'RSP':'responder','RES':'resource','SHL':'shelter'}.get(prefix,'resource'); save(kind,item); audit('resource_registered','operator',item['id'],{'kind':kind}); return item
def analytics():
    return {'incidents_total':len(INCIDENTS),'open_incidents':sum(x.get('status') not in ('resolved','closed') for x in INCIDENTS),'critical_incidents':sum(x.get('urgency')=='critical' for x in INCIDENTS),'responders_total':len(RESPONDERS),'responders_available':sum(x.get('status')=='available' for x in RESPONDERS),'resources_total':len(RESOURCES),'resources_available':sum(x.get('status')=='available' for x in RESOURCES),'alerts_total':len(ALERTS),'shelters_total':len(SHELTERS),'shelters_open':sum(x.get('status')=='open' for x in SHELTERS)}
def create_alert(payload):
    item={'id':f'ALT-{uuid4().hex[:10].upper()}','timestamp':now(),'status':'draft',**payload}; ALERTS.append(item); save('alert',item); return item
def forecast_from_swarm(swarm):
    metadata=swarm.get('model_metadata',{}); probabilities=metadata.get('horizon_probabilities',{})
    horizons=[]
    for hours in (24,48,72):
        p=probabilities.get(str(hours))
        horizons.append({'hours':hours,'probability':round(float(p),3) if p is not None else None,'severity':risk_severity(float(p)) if p is not None else 'unavailable','status':'estimate' if p is not None else 'unavailable','validation':metadata.get('horizon_metrics',{}).get(str(hours))})
    return {'horizons':horizons,'basis':swarm.get('inference_source'),'live_weather':swarm.get('live_weather_available',False),'weather_data_availability':swarm.get('weather_data_availability',{}),'data_health':swarm.get('data_health',[]),'confidence':swarm.get('confidence'),'model_metadata':metadata,'geography_warning':swarm.get('geography_warning'),'target_within_training_region':metadata.get('target_within_training_region'),'training_notice':metadata.get('training_notice'),'label_provenance':metadata.get('label_provenance'),'probability_calibration':metadata.get('probability_calibration'),'operationally_validated':swarm.get('operationally_validated',False),'input_window':metadata.get('input_window'),'coverage_region':metadata.get('coverage_region')}
