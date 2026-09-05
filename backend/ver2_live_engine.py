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

    # Motor pedigree: 2-rentai is used as the current provisional pedigree
    # signal. 3-rentai is deliberately display/reference-only.  The baseline
    # and scale are kept explicit so they can be calibrated later against
    # Hamanako historical motor data.
    m2=b.get('motor_2rentai_rate')
    try: m2=float(m2) if m2 is not None else 30.0
    except (TypeError,ValueError): m2=30.0
    motor_strength=max(-1.0,min(1.0,(m2-30.0)/20.0))

    # Current finish proxy: exhibition time affects acceleration/stretch,
    # while pedigree remains a separate, smaller prior.
    ex=b.get('exhibition_time')
    exq=0.0
    if isinstance(ex,(int,float)):
        exq=max(-1.0,min(1.0,(6.84-float(ex))*3.0))
    stretch=0.10*exq + 0.04*motor_strength
    accel=0.08*exq + 0.05*motor_strength
    return BoatInput(boat_no=int(b['boat_no']), exhibition_st=float(est or 0.15),
                     stretch=stretch, accel=accel, turn=class_base,
                     pressure_resistance=max(0.0,0.05-0.03*motor_strength),
                     attack=max(0,class_base)+0.10*max(0,motor_strength),
                     defend=max(0,class_base)+0.06*max(0,motor_strength),
                     psychology=0.0, start_quality=stq,
                     motor_2rentai_rate=m2, motor_strength=motor_strength,
                     motor_3rentai_rate=float(b.get('motor_3rentai_rate') or 0.0))

def to_race(data,fronting=None):
    boats=[feature_defaults(b) for b in data['boats']]
    return RaceInput(boats=boats,wind=float(data.get('wind',0) or 0),wave=float(data.get('wave',0) or 0),
                     base_entry=data.get('base_entry') or [1,2,3,4,5,6],slow_dash=data.get('slow_dash','auto'),fronting=fronting or [])

def run_live(data, simulations=10000, seed=20260904, fronting=None, model_version='2.1-live-skeleton'):
    boats=data.get('boats') or []
    boat_nos=sorted(int(b.get('boat_no',0)) for b in boats)
    if len(boats)!=6 or boat_nos != [1,2,3,4,5,6]:
        raise ValueError('race data incomplete: six boats required')
    missing_names=[int(b['boat_no']) for b in boats if not b.get('racer_name')]
    if missing_names: raise ValueError(f'racer data missing: boats {missing_names}')
    missing=[int(b['boat_no']) for b in boats if b.get('exhibition_time') is None or b.get('exhibition_st') is None]
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
