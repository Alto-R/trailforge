"""Unit tests for TrailGraph (T1.0). Pure stdlib — no pytest needed.

Run:  D:/Anaconda/envs/trailforge/python.exe tests/test_trail_graph.py
"""
import sys
from collections import deque
from pathlib import Path

import geopandas as gpd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C
from src.trail_graph import TrailGraph


def _components(tg, limit=2):
    seen, comps = set(), []
    for s in tg.adjacency:
        if s in seen:
            continue
        comp, dq = set(), deque([s]); seen.add(s)
        while dq:
            c = dq.popleft(); comp.add(c)
            for x in tg.neighbors(c):
                if x not in seen:
                    seen.add(x); dq.append(x)
        comps.append(comp)
        if len(comps) >= limit:
            break
    return comps


def test_all_segments_loaded(tg):
    assert len(tg.gdf) == 29941
    assert tg.id_col == "lypID"


def test_adjacency_symmetric(tg):
    a = next(iter(tg.adjacency))
    for b in tg.neighbors(a):
        assert a in tg.neighbors(b)


def test_neighbors_nonempty_and_bounded(tg):
    sample = list(tg.adjacency)[:500]
    assert all(len(tg.neighbors(s)) >= 1 for s in sample)
    assert max(len(tg.neighbors(s)) for s in tg.adjacency) <= 7


def test_attributes_has_geo_fields(tg):
    sid = int(tg.gdf["lypID"].iloc[0])
    attrs = tg.attributes(sid)
    assert "geometry" not in attrs
    for f in ["length", "slope_mean", "joincount"]:
        assert f in attrs


def test_shortest_path_direct_neighbour(tg):
    start = next(s for s in tg.adjacency if tg.neighbors(s))
    nb = tg.neighbors(start)[0]
    path = tg.shortest_path(start, nb)
    assert path[0] == start and path[-1] == nb and len(path) == 2


def test_shortest_path_unreachable_returns_empty(tg):
    comps = _components(tg, limit=2)
    a, b = next(iter(comps[0])), next(iter(comps[1]))
    assert tg.shortest_path(a, b) == []


def test_subgraph_radius_monotonic(tg):
    center = next(s for s in tg.adjacency if len(tg.neighbors(s)) >= 2)
    small, big = tg.subgraph(center, 0.2), tg.subgraph(center, 1.0)
    assert center in small and small.issubset(big)


def test_find_nearest_segment(tg):
    sid = int(tg.gdf["lypID"].iloc[1000])
    c = tg.gdf.loc[sid].geometry.interpolate(0.5, normalized=True)
    found = tg.find_nearest_segment(c.x, c.y)
    assert found == sid or found in tg.neighbors(sid)


def main():
    print("loading TrailGraph ...")
    tg = TrailGraph(gpd.read_file(C.CLIM_SPRING_SEG))
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        try:
            t(tg)
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:  # noqa: BLE001
            print(f"  FAIL  {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    sys.exit(main())
