from __future__ import annotations
import argparse,json,statistics
from pathlib import Path
from ver2_integrated_mc import load_race, RaceInput, Fronting, run_mc, simulate_once

def pct(x): return round(100*x,3)

def condition_summary(r):
    return {
      "representative_start_slit":r["representative_start_slit"],
      "representative_start_slit_rate_pct":pct(r["representative_start_slit_rate"]),
      "decisive_method_rate_pct":{k:pct(v) for k,v in r["decisive_method_rate"].items()},
      "top3_rate_pct":{k:pct(v) for k,v in r["top3_rate"].items()},
      "rank_rates_pct":{b:{k:pct(v) for k,v in rr.items()} for b,rr in r["rank_rates"].items()},
      "representative_back_middle":r["representative_back_middle"],
      "representative_back_middle_rate_pct":pct(r["representative_back_middle_rate"]),
      "fronting_effect_events":r["fronting_effect_events"]
    }

def compare_conditions(race,conditions,n,seed):
    raw={name:run_mc(RaceInput(race.boats,race.wind,race.wave,race.base_entry,race.slow_dash,fs),n,seed) for name,fs in conditions.items()}
    base=raw[next(iter(raw))]
    effects={}
    for name,r in raw.items():
      effects[name]={
        "top3_delta_pp":{b:round(100*(r["top3_rate"][b]-base["top3_rate"][b]),3) for b in r["top3_rate"]},
        "slit_rate_delta_pp":round(100*(r["representative_start_slit_rate"]-base["representative_start_slit_rate"]),3),
      }
    return {"simulations":n,"seed":seed,"conditions":{k:condition_summary(v) for k,v in raw.items()},"effects_vs_first_condition":effects}

def reproducibility(race,fs,n,seeds):
    runs=[run_mc(RaceInput(race.boats,race.wind,race.wave,race.base_entry,race.slow_dash,fs),n,s) for s in seeds]
    boats=[b for b in runs[0]["top3_rate"]]
    spread={b:round(100*(max(r["top3_rate"][b] for r in runs)-min(r["top3_rate"][b] for r in runs)),3) for b in boats}
    return {"seeds":seeds,"top3_range_pp":spread,"reproducibility":"high" if max(spread.values(),default=0)<2 else "medium" if max(spread.values(),default=0)<5 else "low"}

def main():
  ap=argparse.ArgumentParser(); ap.add_argument("--input",required=True); ap.add_argument("--simulations",type=int,default=10000); ap.add_argument("--seed",type=int,default=20260904); ap.add_argument("--output",required=True); ap.add_argument("--compare",action="store_true"); a=ap.parse_args()
  race=load_race(a.input)
  if a.compare:
    conds={"前付けなし":[],"前付け中":[Fronting(3,50,60,50,50,2)],"前付け強め":[Fronting(3,80,70,65,30,2)],"前付け強・深・粘り":[Fronting(3,95,90,90,10,2)]}
    result=compare_conditions(race,conds,a.simulations,a.seed)
    result["reproducibility"]={k:reproducibility(race,fs,max(1000,a.simulations//5),[a.seed,a.seed+1,a.seed+2]) for k,fs in conds.items()}
  else:
    result=condition_summary(run_mc(race,a.simulations,a.seed)); result["reproducibility"]=reproducibility(race,race.fronting or [],max(1000,a.simulations//5),[a.seed,a.seed+1,a.seed+2])
  Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
