from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ver2_official_live_fetcher import build_race
from ver2_live_engine import run_live

app = FastAPI(title="Hamanako 1M Simulator Ver.2", version="clean-1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class LiveSimulationRequest(BaseModel):
    race: dict
    simulations: int = Field(default=10000, ge=100, le=100000)
    seed: int = Field(default=20260904, ge=0)
    fronting: list[dict] = Field(default_factory=list)
    entry_order: list[int] = Field(default_factory=lambda: [1, 2, 3, 4, 5, 6])


@app.get("/health")
def health():
    return {"ok": True, "service": "hamanako-1m-simulator", "venue": "浜名湖", "version": "clean-1.0"}


@app.get("/live/prepare")
def live_prepare(date: str, race_no: int):
    if not date.isdigit() or len(date) != 8:
        raise HTTPException(status_code=400, detail="date must be YYYYMMDD")
    if not 1 <= race_no <= 12:
        raise HTTPException(status_code=400, detail="race_no must be 1..12")
    try:
        return build_race(date, race_no, fetch_before=True, fetch_result=False)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post("/live/simulate")
def live_simulate(payload: LiveSimulationRequest):
    race = dict(payload.race)
    race["entry_order"] = list(payload.entry_order)
    try:
        return run_live(
            race,
            simulations=payload.simulations,
            seed=payload.seed,
            fronting=payload.fronting,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
