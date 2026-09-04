#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,random
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
from ver2_integrated_mc import RaceInput,BoatInput,Fronting,run_mc
from ver2_live_store import init_db,upsert_race,save_prediction,save_observation,save_validation,validation_count

def feature_defaults(b):
    cls=b.get('racer_class') or 'B1'
    # Deliberately conservative priors. These are not learned real-race coefficients.
    class_base={'A1':0.15,'A2':0.08,'A3':0.03,'B1':0.0,'B2':-0.03,'B3':-0.05}.get(cls,0.0)
    est=b.get('exhibition_st')
    stq=class_base
    if isinstance(est,(int,float)):
        stq += max(-0.25,min(0.25,(0.15-float(est))*4.0))
    return BoatInput(boat_no=int(b['boat_no']), exhibition_st=float(est or 0.15), stretch=0.0, accel=0.0,
                     turn=class_base, pressure_resistance=0.05, attack=max(0,class_base),
                     defend=max(0,class_base), psychology=0.0, start_quality=stq)

def to_race(data,fronting=None):
    boats=[feature_defaults(b) for b in data['boats']]
    return RaceInput(boats=boats,wind=float(data.get('wind',0) or 0),wave=float(data.get('wave',0) or 0),
                     base_entry=data.get('base_entry') or [1,2,3,4,5,6],slow_dash=data.get('slow_dash','auto'),fronting=fronting or [])

def run_live(data, simulations=10000, seed=20260904, fronting=None, model_version='2.1-live-skeleton'):
    if data.get('status') not in ('ready_for_simulation','needs_exhibition'):
        raise ValueError('race data incomplete')
    missing=[b['boat_no'] for b in data.get('boats',[]) if b.get('exhibition_time') is None or b.get('exhibition_st') is None]
    if missing: raise ValueError(f'exhibition data missing: boats {missing}')
    race=to_race(data,fronting); out=run_mc(race,simulations,seed)
    pid=save_prediction(data['race_id'],model_version,simulations,seed,data,out)
    return {'prediction_id':pid,'model_version':model_version,'race_id':data['race_id'],'result':out}

def settle(data,prediction_id=None):
    actual=data.get('result') or []
    if len(actual)!=6: raise ValueError('6-boat result required')
    # Validation is intentionally event-level and conservative until real teacher features exist.
    by={x['boat_no']:x for x in actual}
    metrics={'actual_course_present':sum('actual_course' in x for x in actual),'actual_st_present':sum('actual_st' in x for x in actual),'finish_present':sum('finish' in x for x in actual)}
    labels=[]
    if metrics['actual_course_present']<6: labels.append('entry_data_missing')
    if metrics['actual_st_present']<6: labels.append('st_data_missing')
    if metrics['finish_present']<6: labels.append('finish_data_missing')
    vid=save_validation(data['race_id'],prediction_id,metrics,labels,'review' if not labels else 'incomplete')
    return {'validation_id':vid,'metrics':metrics,'error_labels':labels,'validation_count':validation_count()}

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('json'); ap.add_argument('--simulations',type=int,default=10000); ap.add_argument('--seed',type=int,default=20260904); ap.add_argument('--output',required=True)
    a=ap.parse_args(); init_db(); d=json.loads(Path(a.json).read_text(encoding='utf-8')); upsert_race(d); out=run_live(d,a.simulations,a.seed); Path(a.output).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(out,ensure_ascii=False,indent=2))
