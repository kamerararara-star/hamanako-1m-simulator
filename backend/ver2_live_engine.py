#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,random
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
from ver2_integrated_mc import RaceInput,BoatInput,Fronting,run_mc
from player_profiles import get_profile
from ver2_live_store import init_db,upsert_race,save_prediction,save_observation,save_validation,validation_count

def feature_defaults(b, field_stats=None):
    """Convert official live inputs into conditional simulation features.

    Motor nature and current form are kept separate.  No missing motor value is
    invented: absent motor stats contribute zero. Player quirks are loaded from
    the conservative profile layer and remain neutral when no history exists.
    """
    cls=b.get('racer_class') or 'B1'
    class_base={'A1':0.10,'A2':0.06,'A3':0.025,'B1':0.0,'B2':-0.025,'B3':-0.04}.get(cls,0.0)
    est=b.get('exhibition_st'); et=b.get('exhibition_time')
    mean_et=(field_stats or {}).get('mean_et',6.85); mean_st=(field_stats or {}).get('mean_st',0.15)
    motor_rates=(field_stats or {}).get('motor_rates',[])
    mr=b.get('motor_2rentai_rate')
    if mr is not None and motor_rates:
        mmean=sum(motor_rates)/len(motor_rates)
        mstd=(sum((v-mmean)**2 for v in motor_rates)/len(motor_rates))**0.5 or 1.0
        motor_nature=max(-1.5,min(1.5,(float(mr)-mmean)/mstd))*0.20
    else:
        motor_nature=0.0
    # Current form: exhibition evidence is intentionally separate from motor nature.
    et_edge=0.0 if et is None else max(-1.0,min(1.0,(mean_et-float(et))/0.20))
    st_edge=0.0 if est is None else max(-1.0,min(1.0,(mean_st-float(est))/0.025))
    motor_form=0.18*et_edge + 0.10*st_edge
    stretch=0.12*et_edge + 0.05*motor_nature + 0.03*motor_form
    accel=0.10*et_edge + 0.06*st_edge + 0.05*motor_nature + 0.04*motor_form
    turn=class_base + 0.025*et_edge
    attack=max(0.0, class_base + 0.045*et_edge + 0.035*st_edge + 0.18*motor_nature + 0.10*motor_form)
    defend=max(0.0, class_base + 0.035*et_edge + 0.08*motor_nature)
    start_quality=class_base + 0.12*st_edge + 0.05*motor_nature
    profile=get_profile(b.get('registration_no'),b.get('racer_name'),cls)
    return BoatInput(
        boat_no=int(b['boat_no']), exhibition_st=float(est if est is not None else mean_st),
        stretch=stretch, accel=accel, turn=turn,
        pressure_resistance=0.04+0.03*max(0,class_base)+0.05*profile['resist'],
        attack=attack, defend=defend, psychology=0.0, start_quality=start_quality,
        motor_nature=motor_nature, motor_form=motor_form,
        player_attack=profile['attack'], player_defend=profile['defend'],
        player_resist=profile['resist'], player_retreat=profile['retreat'],
        player_reaction=profile['reaction'], player_change=profile['change_after_failure'],
        player_pickup=profile['pickup'], player_inside=profile['inside'], player_outside=profile['outside'])

def to_race(data,fronting=None):
    raw=data['boats']
    ets=[float(b['exhibition_time']) for b in raw if b.get('exhibition_time') is not None]
    sts=[float(b['exhibition_st']) for b in raw if b.get('exhibition_st') is not None]
    mrs=[float(b['motor_2rentai_rate']) for b in raw if b.get('motor_2rentai_rate') is not None]
    stats={'mean_et':sum(ets)/len(ets) if ets else 6.85,
           'mean_st':sum(sts)/len(sts) if sts else 0.15,
           'motor_rates':mrs}
    boats=[feature_defaults(b,stats) for b in raw]
    return RaceInput(boats=boats,wind=float(data.get('wind',0) or 0),wave=float(data.get('wave',0) or 0),
                     base_entry=data.get('base_entry') or [1,2,3,4,5,6],slow_dash=data.get('slow_dash','auto'),fronting=fronting or [],entry_order=data.get('entry_order'))

def run_live(data, simulations=10000, seed=20260904, fronting=None, entry_order=None, model_version='2.3-conditional-player-motor'):
    if data.get('status') not in ('ready_for_simulation','needs_exhibition'):
        raise ValueError('race data incomplete')
    missing=[b['boat_no'] for b in data.get('boats',[]) if b.get('exhibition_time') is None or b.get('exhibition_st') is None]
    if missing: raise ValueError(f'exhibition data missing: boats {missing}')
    if entry_order is not None:
        data=dict(data); data['entry_order']=entry_order
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
