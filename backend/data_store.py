from __future__ import annotations
import json, sqlite3, time
from pathlib import Path
DB_PATH=Path(__file__).with_name('ver2_site.sqlite3')
SCHEMA='''
CREATE TABLE IF NOT EXISTS races(race_id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS simulations(id INTEGER PRIMARY KEY AUTOINCREMENT, race_id TEXT, payload TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS observations(id INTEGER PRIMARY KEY AUTOINCREMENT, race_id TEXT NOT NULL, payload TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS validation_runs(id INTEGER PRIMARY KEY AUTOINCREMENT, race_id TEXT NOT NULL, payload TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS model_versions(version TEXT PRIMARY KEY, status TEXT NOT NULL, config TEXT NOT NULL, metrics TEXT, created_at REAL NOT NULL);
'''
def conn():
    c=sqlite3.connect(DB_PATH); c.execute('PRAGMA journal_mode=WAL'); return c
def init_db():
    with conn() as c:
        c.executescript(SCHEMA)
        c.execute("INSERT OR IGNORE INTO model_versions(version,status,config,metrics,created_at) VALUES(?,?,?,?,?)",('2.0-structural','active',json.dumps({'calibration':'pending'},ensure_ascii=False),json.dumps({},ensure_ascii=False),time.time()))
def save_race(race_id,payload):
    with conn() as c:c.execute('INSERT OR REPLACE INTO races VALUES(?,?,?)',(race_id,json.dumps(payload,ensure_ascii=False),time.time()))
def save_simulation(race_id,payload):
    with conn() as c:c.execute('INSERT INTO simulations(race_id,payload,created_at) VALUES(?,?,?)',(race_id,json.dumps(payload,ensure_ascii=False),time.time()))
def save_observation(race_id,payload):
    with conn() as c:c.execute('INSERT INTO observations(race_id,payload,created_at) VALUES(?,?,?)',(race_id,json.dumps(payload,ensure_ascii=False),time.time()))
def save_validation(race_id,payload):
    with conn() as c:c.execute('INSERT INTO validation_runs(race_id,payload,created_at) VALUES(?,?,?)',(race_id,json.dumps(payload,ensure_ascii=False),time.time()))
def stats():
    with conn() as c:
        return {k:c.execute(q).fetchone()[0] for k,q in [('races','SELECT COUNT(*) FROM races'),('simulations','SELECT COUNT(*) FROM simulations'),('observations','SELECT COUNT(*) FROM observations'),('validation_runs','SELECT COUNT(*) FROM validation_runs')]}
def active_model():
    with conn() as c:
        r=c.execute("SELECT version,status,config,metrics FROM model_versions WHERE status='active' ORDER BY created_at DESC LIMIT 1").fetchone()
    return {'version':r[0],'status':r[1],'config':json.loads(r[2]),'metrics':json.loads(r[3] or '{}')} if r else None
