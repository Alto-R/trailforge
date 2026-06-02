"""RouteEngine exploration-aid flow on real data + real model (设计 R1)."""
from __future__ import annotations

import itertools

import numpy as np

from src.diversifier import jaccard
from src.persona import PREF_MAP
from backend.tests.conftest import seg_lnglat


def test_resolve_prefs(engine):
    cat = engine.catalog
    # explicit overrides persona
    assert engine.resolve_prefs(cat[0]["id"], {"challenge": 1.0}) == {"challenge": 1.0}
    # persona -> its data-derived defaults
    assert engine.resolve_prefs(cat[0]["id"], None) == cat[0]["default_prefs"]
    # neither -> balanced over the 5 preferences
    bal = engine.resolve_prefs(None, None)
    assert set(bal) == set(PREF_MAP)
    assert all(v == 0.2 for v in bal.values())


def test_seg_scores_finite(engine):
    scores = engine._seg_scores({"challenge": 1.0})
    assert len(scores) == engine.n_segments
    assert np.isfinite(np.array(list(scores.values()))).all()


def test_route_returns_distinct_connected_candidates(engine, junction_start):
    r = engine.route(junction_start["lng"], junction_start["lat"],
                     None, {"challenge": 1.0}, budget_km=4.0, n_routes=4)
    cands = r["candidates"]
    assert 1 <= len(cands) <= 4
    for c in cands:
        segs = c["segments"]
        for a, b in zip(segs, segs[1:]):          # real graph connectivity
            assert b in engine.graph.neighbors(a)
        assert c["geojson"]["type"] == "FeatureCollection"
        assert c["labels"]                         # non-empty explanation
    # MMR: returned candidates are mutually distinct (<= max_sim)
    sets = [set(c["segments"]) for c in cands]
    for a, b in itertools.combinations(sets, 2):
        assert jaccard(a, b) <= 0.86


def test_preferences_change_the_routes(engine, junction_start):
    a = engine.route(junction_start["lng"], junction_start["lat"], None,
                     {"challenge": 1.0}, 4.0, 4)
    b = engine.route(junction_start["lng"], junction_start["lat"], None,
                     {"scenic": 1.0, "nature": 0.6}, 4.0, 4)
    sa = {tuple(c["segments"]) for c in a["candidates"]}
    sb = {tuple(c["segments"]) for c in b["candidates"]}
    assert sa != sb                                # personalization is visible


def test_infeasible_start(engine, components):
    small = min(components, key=len)
    seg = next(iter(small))
    lng, lat = seg_lnglat(engine, seg)
    r = engine.route(lng, lat, None, {"challenge": 1.0}, budget_km=20.0)
    assert r["reachable"] is False
    assert r["note"]
    assert len(r["candidates"]) == 1


def test_route_determinism(engine, junction_start):
    kw = dict(persona_id=None, preferences={"nature": 1.0}, budget_km=4.0, n_routes=4)
    r1 = engine.route(junction_start["lng"], junction_start["lat"], **kw)
    r2 = engine.route(junction_start["lng"], junction_start["lat"], **kw)
    assert [c["segments"] for c in r1["candidates"]] == \
           [c["segments"] for c in r2["candidates"]]
