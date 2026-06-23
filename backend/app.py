"""TrailForge exploration-aid API (设计 R1.3) — FastAPI app.

  GET  /health    model + data readiness
  GET  /personas  the 5 onboarding personas (+ default preferences)
  POST /route     ranked, MMR-diversified candidate routes from a clicked start
  GET  /trails    full trail network GeoJSON (so the map shows where trails are)
  POST /feedback  record which candidate the user chose + a rating (Module E)

The RouteEngine (model + graph + features) is a lazy singleton; tests override
get_engine via app.dependency_overrides to share one loaded instance.

Run:  PYTHONNOUSERSITE=1 PYTHONUTF8=1 D:/Anaconda/envs/trailforge/python.exe -m uvicorn backend.app:app --reload
"""
from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend import feedback
from backend.engine import RouteEngine
from backend.schemas import (FeedbackIn, FeedbackOut, HealthOut, PersonaOut,
                             RouteRequest, RouteResponse)

app = FastAPI(title="TrailForge exploration-aid API", version="0.2.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

_engine: RouteEngine | None = None


def get_engine() -> RouteEngine:
    """Lazy singleton; overridable in tests via app.dependency_overrides."""
    global _engine
    if _engine is None:
        _engine = RouteEngine()
    return _engine


@app.get("/health", response_model=HealthOut)
def health(engine: RouteEngine = Depends(get_engine)) -> HealthOut:
    return HealthOut(model_loaded=True, n_segments=engine.n_segments,
                     n_personas=len(engine.catalog))


@app.get("/personas", response_model=list[PersonaOut])
def list_personas(engine: RouteEngine = Depends(get_engine)) -> list[dict]:
    return engine.personas()


@app.post("/route", response_model=RouteResponse)
def make_route(req: RouteRequest,
               engine: RouteEngine = Depends(get_engine)) -> dict:
    try:
        return engine.route(req.lng, req.lat, req.persona, req.preferences,
                            req.budget_km, req.n_routes, req.loop)
    except KeyError as e:                       # unknown persona id
        raise HTTPException(status_code=422, detail=str(e))


@app.get("/trails")
def trails(engine: RouteEngine = Depends(get_engine)) -> dict:
    return engine.trails_geojson()


@app.post("/feedback", response_model=FeedbackOut)
def post_feedback(fb: FeedbackIn) -> FeedbackOut:
    stored = feedback.record(fb.model_dump())
    return FeedbackOut(stored=stored)
