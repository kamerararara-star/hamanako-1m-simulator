"""Conservative multi-race calibration gate for Ver.2.
Never changes the active model from a single race. It creates a candidate only
when enough validated races exist; activation is an explicit deployment step.
"""
from __future__ import annotations
import json, sqlite3, time
from pathlib import Path
DB=Path(__file__).with_name('ver2_site.sqlite3')
MIN_RACES=30

def build_candidate():
    with sqlite3.connect(DB) as c:
        rows=c.execute('SELECT payload FROM validation_runs ORDER BY id').fetchall()
        active=c.execute("SELECT version,config FROM model_versions WHERE status='active' ORDER BY created_at DESC LIMIT 1").fetchone()
    if len(rows)<MIN_RACES:return {'status':'waiting','validated_races':len(rows),'minimum_races':MIN_RACES}
    payloads=[json.loads(r[0]) for r in rows]
    # Framework is intentionally conservative: calculate monitoring metrics first.
    ok=sum(1 for p in payloads if p.get('ok'))
    cfg=json.loads(active[1]) if active else {}
    candidate={'base_version':active[0] if active else '2.0-structural','calibration':'candidate','validated_races':len(rows),'valid_records':ok,'generated_at':time.time(),'changes':{},'note':'候補モデル。自動でactiveにはしない。'}
    with sqlite3.connect(DB) as c:
        version=f"2.{len(rows)//MIN_RACES}.candidate"
        c.execute('INSERT OR REPLACE INTO model_versions(version,status,config,metrics,created_at) VALUES(?,?,?,?,?)',(version,'candidate',json.dumps(cfg,ensure_ascii=False),json.dumps(candidate,ensure_ascii=False),time.time()))
    return candidate|{'version':version}
if __name__=='__main__': print(json.dumps(build_candidate(),ensure_ascii=False,indent=2))
