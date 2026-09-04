from __future__ import annotations
import os, json, statistics
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from .ver2_integrated_mc import load_race, run_mc, RaceInput, Fronting, BoatInput
from .data_store import init_db, save_race, save_simulation, save_observation, save_validation, stats, active_model
from .ver2_official_live_fetcher import build_race
from .ver2_live_engine import run_live, settle
app=FastAPI(title='浜名湖1M 展開予想AI Ver.2 API',version='2.1')
app.add_middleware(CORSMiddleware,allow_origins=os.getenv('CORS_ORIGINS','*').split(','),allow_methods=['*'],allow_headers=['*'])
init_db()
class FrontingIn(BaseModel):
    boat_no:int=Field(ge=1,le=6); strength:float=Field(ge=0,le=100); start_aggression:float=Field(ge=0,le=100); depth:float=Field(ge=0,le=100); give_up:float=Field(ge=0,le=100); target_course:int|None=Field(default=None,ge=1,le=6)
class SimIn(BaseModel):
    race:dict; simulations:int=Field(default=10000,ge=1000,le=100000); seed:int=20260904; fronting:list[FrontingIn]=[]; save:bool=True
class ObservationIn(BaseModel):
    race_id:str; payload:dict

def _race(x):
    d=dict(x.race); d['fronting']=[f.model_dump() for f in x.fronting]; return load_race_from_dict(d)
def load_race_from_dict(d):
    boats=[BoatInput(**b) for b in d['boats']]; fs=[Fronting(**f) for f in d.get('fronting',[])]; return RaceInput(boats=boats,wind=d.get('wind',0),wave=d.get('wave',0),base_entry=d.get('base_entry'),slow_dash=d.get('slow_dash','auto'),fronting=fs)
@app.get('/health')
def health(): return {'status':'ok','engine':'ver2','model':active_model()['version'],'data_calibration':'pending','store':stats()}
@app.get('/model')
def model(): return active_model()
@app.post('/simulate')
def simulate(x:SimIn):
    try:
        race=_race(x); result=run_mc(race,x.simulations,x.seed)
        if x.save:
            rid=x.race.get('race_id','unspecified'); save_race(rid,x.race); save_simulation(rid,{'input':x.model_dump(),'result':result})
        return result
    except Exception as e: raise HTTPException(400,str(e))
@app.post('/observations')
def observation(x:ObservationIn):
    save_observation(x.race_id,x.payload); return {'status':'saved','race_id':x.race_id}
@app.post('/validation')
def validation(x:ObservationIn):
    p=x.payload
    errors=[]
    for k in ('predicted','actual'):
        if k not in p: errors.append(f'missing:{k}')
    result={'ok':not errors,'errors':errors}
    if not errors:
        result['notes']='Validation record stored. Coefficients are not auto-changed by one race.'
    save_validation(x.race_id,result|{'payload':p}); return result
@app.post('/calibrate')
def calibrate():
    from .calibrator import build_candidate
    return build_candidate()
@app.get('/stats')
def site_stats(): return {'store':stats(),'model':active_model()}


@app.get('/live/prepare')
def live_prepare(date:str, race_no:int):
    if not (len(date)==8 and date.isdigit() and 1 <= race_no <= 12):
        raise HTTPException(400,'date=YYYYMMDD and race_no=1..12 required')
    try:
        return build_race(date, race_no, fetch_before=True, fetch_result=False)
    except Exception as e:
        raise HTTPException(502,str(e))

class LiveSimIn(BaseModel):
    race:dict; simulations:int=Field(default=10000,ge=1000,le=100000); seed:int=20260904; fronting:list[FrontingIn]=[]

@app.post('/live/simulate')
def live_simulate(x:LiveSimIn):
    try:
        return run_live(x.race,x.simulations,x.seed,[Fronting(**f.model_dump()) for f in x.fronting])
    except Exception as e:
        raise HTTPException(400,str(e))

class LiveSettleIn(BaseModel):
    race:dict; prediction_id:int|None=None

@app.post('/live/settle')
def live_settle(x:LiveSettleIn):
    try:
        return settle(x.race,x.prediction_id)
    except Exception as e:
        raise HTTPException(400,str(e))
