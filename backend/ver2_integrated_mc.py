from __future__ import annotations
import argparse, json, math, random
from dataclasses import dataclass, asdict
from collections import Counter, defaultdict
from typing import Dict, List, Optional

BOATS=range(1,7)

@dataclass
class Fronting:
    boat_no:int
    strength:float=0; start_aggression:float=50; depth:float=50; give_up:float=50; target_course:Optional[int]=None

@dataclass
class BoatInput:
    boat_no:int
    exhibition_st:float=0.0
    stretch:float=0.0      # relative boat-length capability, centered 0
    accel:float=0.0        # relative acceleration capability
    turn:float=0.0         # turning propulsion/skill
    pressure_resistance:float=0.0
    attack:float=0.0
    defend:float=0.0
    psychology:float=0.0
    start_quality:float=0.0
    motor_2rentai_rate:float=30.0
    motor_strength:float=0.0
    motor_3rentai_rate:float=0.0

@dataclass
class RaceInput:
    boats:List[BoatInput]
    wind:float=0.0
    wave:float=0.0
    base_entry:List[int]=None
    slow_dash:str='auto'
    fronting:List[Fronting]=None
    entry_order:List[int]=None


def clamp(x,a=0.0,b=1.0): return max(a,min(b,x))
def sigmoid(x): return 1/(1+math.exp(-max(-30,min(30,x))))
def norm100(x): return clamp(x/100.0)

def translate_fronting(f:Fronting):
    s=norm100(f.strength); a=norm100(f.start_aggression); d=norm100(f.depth); g=norm100(f.give_up)
    return {
        'pressure': s*(0.45+0.55*a),
        'resistance_load': s*(0.35+0.65*(1-g)),
        'runup_ratio': clamp(1-0.22*s*(0.45+0.55*d)),
        'start_shift': -0.45*s*(0.35+0.65*d),
        'accel_factor': 1-0.12*s*d,
        'target_course': f.target_course,
    }

def resolve_entry(race:RaceInput, rng:random.Random):
    bi={x.boat_no:x for x in race.boats}
    base=race.base_entry or list(BOATS)
    courses={b:base[b-1] for b in BOATS}
    fronting=sorted(race.fronting or [], key=lambda f:f.boat_no)
    notes=[]
    # Entry/fronting is user-controlled only.
    # The AI must not autonomously change the entry formation. Randomness is
    # applied later to ST, approach and 1M battle, not to course assignment.
    requested=race.entry_order or []
    if requested and sorted(requested)==list(BOATS):
        courses={b:i+1 for i,b in enumerate(requested)}
        notes.append('指定進入を固定')
        entry_pos={b:(courses[b]-1)*1.0 for b in BOATS}
        return courses, entry_pos, notes
    for f in fronting:
        if f.strength<=0: continue
        tr=translate_fronting(f); b=f.boat_no; target=f.target_course
        if target is None: target=max(1, min(5, courses[b]-1))
        inner=[x for x in BOATS if courses[x] < target and x!=b]
        resistance=sum((1-norm100(next((q.give_up for q in fronting if q.boat_no==x),20)))*0.5 for x in inner)
        settle=sigmoid((tr['pressure']+0.35*resistance-0.38)*7)
        if rng.random() < settle:
            old=courses[b]
            # shift one lane toward target; stronger/deeper may shift another lane with diminishing probability
            step=1 if target<old else -1
            new=old-step*0
            new=old-1 if target<old else old+1
            if target<old: new=max(target,new)
            else: new=min(target,new)
            if new!=old:
                # occupant at target lane yields/gets displaced probabilistically
                occ=next((x for x in BOATS if x!=b and courses[x]==new),None)
                if occ:
                    og=norm100(next((q.give_up for q in fronting if q.boat_no==occ),20))
                    occ_obj=bi[occ]
                    fail_prob=clamp(0.05+0.20*occ_obj.pressure_resistance+0.10*(1-og)+0.10*race.wave)
                    if rng.random()<fail_prob:
                        notes.append(f'{occ}抵抗→{b}前付け不成立寄り')
                    else:
                        courses[occ]=old
                        courses[b]=new
                        notes.append(f'{b}前付け成立→{occ}抵抗')
                else: courses[b]=new; notes.append(f'{b}前付け成立')
        # preserve unique course ordering by repair later
    # Repair duplicate/missing courses minimally
    vals=list(courses.values()); missing=[x for x in BOATS if x not in vals]
    seen=set()
    for b in BOATS:
        if courses[b] in seen or courses[b] not in BOATS:
            courses[b]=missing.pop(0) if missing else b
        seen.add(courses[b])
    entry_pos={b:(courses[b]-1)*1.0 for b in BOATS}
    return courses, entry_pos, notes

def simulate_once(race:RaceInput, rng:random.Random):
    courses,pos,entry_notes=resolve_entry(race,rng)
    bi={b:race.boats[b-1] for b in BOATS}
    # start: ST around course-specific baseline, exhibition and fronting run-up effects
    st={}; speed={}; runup={}; lateral={}
    for b in BOATS:
        x=bi[b]
        front=next((q for q in race.fronting or [] if q.boat_no==b),None)
        tr=translate_fronting(front) if front else {'runup_ratio':1,'start_shift':0,'accel_factor':1}
        runup[b]=max(0.72, tr['runup_ratio'] + rng.gauss(0,0.025))
        mean_st=0.14 - 0.012*x.start_quality - 0.008*x.accel + 0.004*(x.exhibition_st-0.15)/0.02
        mean_st += 0.004*(1-runup[b]) + race.wave*0.002
        st[b]=max(0.04,rng.gauss(mean_st,0.018*(1.0-clamp(abs(x.start_quality)/2))))
        # quality: lower ST is better
        speed[b]=1.0 + x.accel*0.06 + x.stretch*0.08 + (0.03 if st[b]<0.13 else -0.02) + rng.gauss(0,0.025)
        lateral[b]=pos[b]
    # ③-1 matching/reaction and ③-2 stretch over run to 1M
    order=sorted(BOATS,key=lambda b:(st[b], courses[b]))
    for i,b in enumerate(order):
        if i>0:
            lead=order[i-1]
            if abs(st[b]-st[lead])<0.012 and rng.random()<sigmoid(0.8+bi[b].psychology):
                st[b]=(st[b]+st[lead])/2
                speed[b]+=0.015*bi[b].psychology
    # common movement steps; positions are longitudinal advantage in boat lengths
    long={b:(0.15*(0.14-st[b])/0.03 + 0.12*bi[b].stretch + 0.10*bi[b].accel + rng.gauss(0,0.06)) for b in BOATS}
    # interactions before 1M
    for b in BOATS:
        for c in BOATS:
            if b>=c: continue
            if abs(courses[b]-courses[c])==1:
                gap=long[b]-long[c]
                if gap>0.25:
                    long[c]-=0.08*bi[c].pressure_resistance; long[b]+=0.03
                elif gap<-0.25:
                    long[b]-=0.08*bi[b].pressure_resistance; long[c]+=0.03
    # ④ choose intent among candidates
    intents={}
    for b in BOATS:
        lane=courses[b]; x=bi[b]
        if lane==1:
            weights={'逃げ':2.0+x.defend+0.5*x.turn,'差し':0.2,'まくり':0.1+x.attack*0.3,'まくり差し':0.15,'恵まれ':0.02}
        elif lane == 2:
            # 2コースは差しを基本。まくりもあるが、まくり差しは通常の2コース決まり手として扱わない。
            weights={'逃げ':0.0,'差し':1.25+0.6*x.attack+0.5*x.stretch,'まくり':0.70+0.8*x.attack+0.35*max(0, long[b]),'まくり差し':0.0,'恵まれ':0.03}
        elif lane == 3:
            # 3コースはまくり差し・まくりを中心に、差しは補助。
            weights={'逃げ':0.0,'差し':0.22+0.18*x.attack,'まくり':0.80+0.85*x.attack+0.35*max(0, long[b]),'まくり差し':1.10+0.75*x.attack+0.45*x.turn,'恵まれ':0.03}
        else:
            # 4〜6コースは「外からの攻め」を基本。差しは通常の決まり手候補から外し、
            # 1Mで内側が崩れた特殊ケースは別のイベントとして後段で扱う。
            weights={'逃げ':0.0,'差し':0.0,'まくり':0.70+0.6*x.attack,'まくり差し':0.80+0.7*x.attack,'恵まれ':0.05}
        # outside/distance reduces immediate attack unless speed advantage is clear
        for k in weights: weights[k]*=math.exp(0.12*long[b])
        s=sum(max(0.001,v) for v in weights.values()); r=rng.random()*s
        acc=0
        for k,v in weights.items():
            acc+=max(0.001,v)
            if r<=acc: intents[b]=k; break
    # ④ attack execution / reaction. Conservative inner default.
    attack_score={}
    for b in BOATS:
        x=bi[b]; lane=courses[b]
        target=next((c for c in BOATS if courses[c]==lane-1),None)
        score=0.45+0.55*sigmoid(long[b]*2.2+0.7*x.stretch+0.5*x.accel+0.4*x.attack+0.2*(st.get(target,st[b])-st[b] if target else 0))
        if target:
            score*=0.75+0.25*(1-bi[target].pressure_resistance)
        attack_score[b]=clamp(score)
    decisive=None; decisive_boat=None; collapse=[]
    # prioritize fastest credible attack among 2-6; lane1 escape if not seriously collapsed
    candidates=[]
    for b in BOATS:
        if intents[b] in ('まくり','まくり差し','差し'):
            candidates.append((attack_score[b],b,intents[b]))
    candidates.sort(reverse=True)
    if candidates and candidates[0][0]>0.58 and rng.random()<candidates[0][0]*0.75:
        sc,b,typ=candidates[0]; decisive=typ; decisive_boat=b
        # inner resistance can stop it
        inner=next((c for c in BOATS if courses[c]==courses[b]-1),None)
        if inner and rng.random()<0.32*bi[inner].pressure_resistance:
            decisive=None; decisive_boat=None
        elif typ=='まくり':
            for c in BOATS:
                if courses[c]<courses[b]: long[c]-=0.22*sc
            long[b]+=0.35*sc
        elif typ in ('差し','まくり差し'):
            long[b]+=0.28*sc
            if inner: long[inner]-=0.12*sc
    # inner escape baseline unless collapse evidence
    if decisive is None:
        b1=next(b for b in BOATS if courses[b]==1)
        escape_strength=0.62+0.20*bi[b1].defend+0.15*bi[b1].turn+0.08*bi[b1].stretch
        if long[b1] < -0.28 and rng.random()>clamp(escape_strength):
            collapse.append(b1); long[b1]-=0.20
            decisive='恵まれ'; decisive_boat=next((b for b in BOATS if b not in collapse),None)
    # ⑤ turn: entry speed/angle/wake, then exit and back middle
    turn_speed={b:speed[b] + 0.16*bi[b].turn + 0.10*bi[b].accel - 0.18*abs(long[b])*0.25 + rng.gauss(0,0.03) for b in BOATS}
    # wake penalty based on nearby prior boat, decays with distance
    for b in BOATS:
        inner=next((c for c in BOATS if courses[c]==courses[b]-1),None)
        if inner and long[inner]>long[b]+0.15:
            penalty=0.06*(1-bi[b].turn*0.4)*(1+0.5*race.wave)
            turn_speed[b]-=penalty
            long[b]-=penalty*0.8
    exit_long={b:long[b]+0.18*turn_speed[b]+0.10*bi[b].turn+rng.gauss(0,0.05) for b in BOATS}
    back_order=sorted(BOATS,key=lambda b:-exit_long[b])
    # back-middle preserves near-1M relationships; do not model 2M
    outcome={
      'courses':courses,'st':st,'long_1m':long,'exit_long':exit_long,'back_order':back_order,
      'intent':intents,'decisive':decisive,'decisive_boat':decisive_boat,'collapse':collapse,
      'entry_notes':entry_notes,'runup':runup
    }
    return outcome

def run_mc(race:RaceInput,n:int,seed:int):
    rng=random.Random(seed); decisive=Counter(); boat_dec=Counter(); top=Counter(); slits=Counter(); back=Counter(); notes=Counter(); attack_pattern=Counter()
    back_time_sum=defaultdict(float); back_time_sq=defaultdict(float); back_gap_sum=defaultdict(float); st_sum=defaultdict(float)
    reps=[]
    for _ in range(n):
        o=simulate_once(race,rng); slit=tuple(o['courses'][b] for b in BOATS); slits[slit]+=1
        if o['decisive']: decisive[o['decisive']]+=1; boat_dec[(o['decisive_boat'],o['decisive'])]+=1
        for b,m in o['intent'].items(): attack_pattern[(b,m)]+=1
        for b in BOATS: st_sum[b]+=o['st'][b]
        for rank,b in enumerate(o['back_order'][:3],1): top[(b,rank)]+=1
        bo=tuple(o['back_order']); back[bo]+=1
        # Relative back-reference arrival time derived from each simulation's 1M-exit state.
        # This is a model-estimated time, not a measured race/video time.
        raw={b:8.60 - 0.22*o['exit_long'][b] + rng.gauss(0,0.018) for b in BOATS}
        lead_t=min(raw.values())
        for b in BOATS:
            back_time_sum[b]+=raw[b]; back_time_sq[b]+=raw[b]*raw[b]; back_gap_sum[b]+=(raw[b]-lead_t)
        for x in o['entry_notes']: notes[x]+=1
        if len(reps)<3: reps.append(o)
    rep_slit,count=slits.most_common(1)[0]
    return {
      'simulations':n,'seed':seed,
      'representative_start_slit':list(rep_slit),'representative_start_slit_rate':count/n,
      'decisive_method_rate':{k:v/n for k,v in decisive.items()},
      'decisive_by_boat':{f'{b}_{m}':v/n for (b,m),v in boat_dec.items()},
      'top3_rate':{str(b):sum(top[(b,r)] for r in (1,2,3))/n for b in BOATS},
      'rank_rates':{str(b):{str(r):top[(b,r)]/n for r in (1,2,3)} for b in BOATS},
      'predicted_st':{str(b):st_sum[b]/n for b in BOATS},
      'attack_pattern_rate':{str(b):{m:attack_pattern[(b,m)]/n for m in ('逃げ','差し','まくり','まくり差し')} for b in BOATS},
      'representative_back_middle':list(back.most_common(1)[0][0]),
      'representative_back_middle_rate':back.most_common(1)[0][1]/n,
      'back_timing':{str(b):{
          'mean_sec':back_time_sum[b]/n,
          'gap_to_leader_sec':back_gap_sum[b]/n,
          'sd_sec':max(0.0,(back_time_sq[b]/n-(back_time_sum[b]/n)**2))**0.5
        } for b in BOATS},
      'fronting_effect_events':dict(notes),
    }

def load_race(path):
    d=json.load(open(path,encoding='utf-8'))
    boats=[BoatInput(**x) for x in d['boats']]
    fs=[Fronting(**x) for x in d.get('fronting',[])]
    return RaceInput(boats=boats,wind=d.get('wind',0),wave=d.get('wave',0),base_entry=d.get('base_entry'),slow_dash=d.get('slow_dash','auto'),fronting=fs,entry_order=d.get('entry_order'))

def compare(race:RaceInput, conditions:Dict[str,List[Fronting]], n:int, seed:int):
    out={}
    for name,fs in conditions.items():
        rr=RaceInput(race.boats,race.wind,race.wave,race.base_entry,race.slow_dash,fs)
        out[name]=run_mc(rr,n,seed)
    return out

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--input',required=True); ap.add_argument('--simulations',type=int,default=10000); ap.add_argument('--seed',type=int,default=20260904); ap.add_argument('--output',required=True)
    a=ap.parse_args(); race=load_race(a.input); result=run_mc(race,a.simulations,a.seed); json.dump(result,open(a.output,'w',encoding='utf-8'),ensure_ascii=False,indent=2); print(json.dumps(result,ensure_ascii=False,indent=2))
