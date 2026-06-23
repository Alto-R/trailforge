"""T2.6 route generator tests: loop closure + local search, on real cached data.

Builds a RouteGenerator from the cached geometry/adjacency (no G: shapefile) and
the normalised segment matrix. Skips cleanly if the cache is absent.
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import geopandas as gpd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config as C  # noqa: E402
from src.route_generator import RouteGenerator  # noqa: E402
from src.segment_repr import load_segment_matrix  # noqa: E402
from src.trail_graph import ADJ_CACHE, TrailGraph  # noqa: E402

GEOM_CACHE = C.DATA_PROCESSED / "segment_geom_climbing.parquet"
BUDGET = 4.0


@pytest.fixture(scope="module")
def rg() -> RouteGenerator:
    if not (GEOM_CACHE.exists() and ADJ_CACHE.exists()):
        pytest.skip("segment geometry/adjacency cache missing (run src/cf_export.py)")
    gdf = gpd.read_parquet(GEOM_CACHE).reset_index()
    with open(ADJ_CACHE, "rb") as f:
        adj = {int(k): v for k, v in pickle.load(f).items()}
    feat, _ = load_segment_matrix(normalize=True)
    return RouteGenerator(TrailGraph(gdf, adj), feat)


@pytest.fixture(scope="module")
def junction_xy(rg):
    """Albers (x,y) midpoint of a branch segment (degree>=4) in the largest
    component, where a loop has room to form."""
    adj = rg.g.adjacency
    seen, comps = set(), []
    for s in adj:
        if s in seen:
            continue
        st, comp = [s], {s}; seen.add(s)
        while st:
            c = st.pop()
            for nb in adj.get(c, []):
                if nb not in seen:
                    seen.add(nb); comp.add(nb); st.append(nb)
        comps.append(comp)
    comps.sort(key=len, reverse=True)
    seg = next(s for s in comps[0] if len(rg.g.neighbors(s)) >= 4)
    p = rg.g.gdf.loc[seg].geometry.interpolate(0.5, normalized=True)
    return (p.x, p.y)


def _connected(rg, segs):
    return all(b in rg.g.neighbors(a) for a, b in zip(segs, segs[1:]))


def test_loop_returns_to_start(rg, junction_xy):
    prefs = {"challenge": 1.0, "popularity": 0.3}
    r = rg.generate_loop(junction_xy, BUDGET, prefs=prefs)
    segs = r["segments"]
    assert r["loop"] is True
    assert segs[0] == segs[-1]                      # closes back to the start segment
    assert _connected(rg, segs)                     # every hop is a real graph edge
    assert r["length_km"] >= 0.6 * BUDGET           # covered a meaningful distance
    assert isinstance(r["closed"], bool)
    assert 0.0 <= r["return_overlap"] <= 1.0


def test_loop_first_step_seeds_direction(rg, junction_xy):
    start = rg.g.find_nearest_segment(*junction_xy)
    nbrs = rg.g.neighbors(start)
    a = rg.generate_loop(junction_xy, BUDGET, prefs={"nature": 1.0}, first_step=nbrs[0])
    b = rg.generate_loop(junction_xy, BUDGET, prefs={"nature": 1.0}, first_step=nbrs[1])
    assert a["segments"][1] == nbrs[0]              # forced first hop honoured
    assert b["segments"][1] == nbrs[1]


def test_local_search_budget_safe_and_non_worsening(rg, junction_xy):
    prefs = {"scenic": 1.0, "nature": 0.5}
    base = rg.generate(junction_xy, BUDGET, prefs=prefs)
    segs = base["segments"]
    reward = rg._reward_fn(None, prefs)
    base_r = sum(reward(s) for s in segs)
    refined, rlen = rg.local_search(segs, BUDGET, prefs=prefs)
    assert _connected(rg, refined)                  # still a valid connected path
    assert 0.8 * BUDGET * 1000 <= rlen <= 1.1 * BUDGET * 1000   # stays in budget band
    assert sum(reward(s) for s in refined) >= base_r - 1e-9     # never worse


def test_loop_determinism(rg, junction_xy):
    kw = dict(prefs={"challenge": 1.0})
    r1 = rg.generate_loop(junction_xy, BUDGET, **kw)
    r2 = rg.generate_loop(junction_xy, BUDGET, **kw)
    assert r1["segments"] == r2["segments"]
