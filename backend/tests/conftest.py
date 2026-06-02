"""Shared fixtures for the backend tests (板块E).

Full real data + real model, no stubs (per design §7). The heavy RouteEngine
(model + graph + features) loads ONCE per session and is shared by every test;
the FastAPI TestClient reuses that same instance via dependency override. Tests
skip cleanly if the export artifacts are missing (run src/cf_export.py first).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.cf_export import E4_META, E4_PT  # noqa: E402


@pytest.fixture(scope="session")
def meta() -> dict:
    if not E4_META.exists():
        pytest.skip("run `python src/cf_export.py` first (e4_meta.json missing)")
    return json.loads(E4_META.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def engine():
    if not E4_PT.exists() or not E4_META.exists():
        pytest.skip("run `python src/cf_export.py` first (e4.pt/e4_meta.json missing)")
    from backend.engine import RouteEngine
    return RouteEngine()


@pytest.fixture()
def client(engine):
    from fastapi.testclient import TestClient
    from backend import app as app_module
    app_module.app.dependency_overrides[app_module.get_engine] = lambda: engine
    with TestClient(app_module.app) as c:
        yield c
    app_module.app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def components(engine) -> list[set]:
    """Connected components of the trail graph, largest first."""
    adj = engine.graph.adjacency
    seen: set = set()
    comps: list[set] = []
    for s in adj:
        if s in seen:
            continue
        stack = [s]; comp = {s}; seen.add(s)
        while stack:
            c = stack.pop()
            for nb in adj.get(c, []):
                if nb not in seen:
                    seen.add(nb); comp.add(nb); stack.append(nb)
        comps.append(comp)
    comps.sort(key=len, reverse=True)
    return comps


def seg_lnglat(engine, seg: int) -> tuple[float, float]:
    """WGS84 [lng, lat] of a segment's midpoint."""
    x, y = engine.graph.gdf.loc[seg].geometry.interpolate(0.5, normalized=True).coords[0]
    return engine._to_wgs84.transform(x, y)


@pytest.fixture(scope="session")
def start_point(engine, components) -> dict:
    """A valid clicked start in the largest component + a default persona."""
    seg = next(iter(components[0]))
    lng, lat = seg_lnglat(engine, seg)
    return {"lng": lng, "lat": lat, "persona": engine.catalog[0]["id"]}


@pytest.fixture(scope="session")
def junction_start(engine, components) -> dict:
    """A start on a branch node (degree>=4) where preferences can steer routes."""
    seg = next(s for s in components[0] if len(engine.graph.neighbors(s)) >= 4)
    lng, lat = seg_lnglat(engine, seg)
    return {"lng": lng, "lat": lat, "seg": int(seg)}
