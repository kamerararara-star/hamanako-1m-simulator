#!/usr/bin/env python3
import json, sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).with_name('ver2_hamanako_live.sqlite3')

def connect():
    con=sqlite3.connect(DB_PATH)
    con.row_factory=sqlite3.Row
    return con

def init_db():
    with connect() as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS live_races(
          race_id TEXT PRIMARY KEY, race_date TEXT NOT NULL, venue TEXT NOT NULL,
          race_no INTEGER NOT NULL, event_name TEXT, deadline TEXT,
          status TEXT NOT NULL, source_url TEXT, fetched_at TEXT, raw_json TEXT
        );
        CREATE TABLE IF NOT EXISTS live_predictions(
          id INTEGER PRIMARY KEY AUTOINCREMENT, race_id TEXT NOT NULL,
          model_version TEXT NOT NULL, simulations INTEGER NOT NULL, seed INTEGER NOT NULL,
          created_at TEXT NOT NULL, input_json TEXT NOT NULL, output_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS live_observations(
          id INTEGER PRIMARY KEY AUTOINCREMENT, race_id TEXT NOT NULL,
          observation_type TEXT NOT NULL, created_at TEXT NOT NULL,
          payload_json TEXT NOT NULL, source TEXT, status TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS live_validation(
          id INTEGER PRIMARY KEY AUTOINCREMENT, race_id TEXT NOT NULL,
          prediction_id INTEGER, created_at TEXT NOT NULL,
          metrics_json TEXT NOT NULL, error_labels_json TEXT NOT NULL,
          status TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS model_candidates(
          id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
          base_version TEXT NOT NULL, sample_count INTEGER NOT NULL,
          metrics_json TEXT NOT NULL, candidate_json TEXT NOT NULL,
          status TEXT NOT NULL
        );
        ''')

def upsert_race(race):
    init_db(); now=datetime.now(timezone.utc).isoformat()
    with connect() as con:
        con.execute('''INSERT INTO live_races
          (race_id,race_date,venue,race_no,event_name,deadline,status,source_url,fetched_at,raw_json)
          VALUES(?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(race_id) DO UPDATE SET
          event_name=excluded.event_name,deadline=excluded.deadline,status=excluded.status,
          source_url=excluded.source_url,fetched_at=excluded.fetched_at,raw_json=excluded.raw_json''',
          (race['race_id'],race['race_date'],race.get('venue','浜名湖'),race['race_no'],race.get('event_name'),
           race.get('deadline'),race.get('status','needs_data'),race.get('source_url'),now,json.dumps(race,ensure_ascii=False)))

def save_prediction(race_id, model_version, simulations, seed, input_data, output_data):
    init_db(); now=datetime.now(timezone.utc).isoformat()
    with connect() as con:
        cur=con.execute('''INSERT INTO live_predictions
        (race_id,model_version,simulations,seed,created_at,input_json,output_json)
        VALUES(?,?,?,?,?,?,?)''',(race_id,model_version,simulations,seed,now,json.dumps(input_data,ensure_ascii=False),json.dumps(output_data,ensure_ascii=False)))
        return cur.lastrowid

def save_observation(race_id, observation_type, payload, source, status='measured'):
    init_db(); now=datetime.now(timezone.utc).isoformat()
    with connect() as con:
        cur=con.execute('''INSERT INTO live_observations
        (race_id,observation_type,created_at,payload_json,source,status) VALUES(?,?,?,?,?,?)''',
        (race_id,observation_type,now,json.dumps(payload,ensure_ascii=False),source,status))
        return cur.lastrowid

def save_validation(race_id,prediction_id,metrics,error_labels,status='review'):
    init_db(); now=datetime.now(timezone.utc).isoformat()
    with connect() as con:
        cur=con.execute('''INSERT INTO live_validation
        (race_id,prediction_id,created_at,metrics_json,error_labels_json,status) VALUES(?,?,?,?,?,?)''',
        (race_id,prediction_id,now,json.dumps(metrics,ensure_ascii=False),json.dumps(error_labels,ensure_ascii=False),status))
        return cur.lastrowid

def validation_count():
    init_db()
    with connect() as con:
        return con.execute("SELECT COUNT(*) FROM live_validation WHERE status IN ('review','approved')").fetchone()[0]
