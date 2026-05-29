"""T1.5 rule-based greedy route generator on the TrailGraph.

Given a start point, a length budget, and preference weights, grow a connected
walkable path by repeatedly stepping to the neighbour with the best
reward-per-cost (主文档 §5.4.2). Reward = preference-weighted sum of the
segment's (normalised) attributes; cost = segment length.

This is the Phase-1 rule version: greedy only, no CF scoring, no loop closure,
no local search (those are T2.6). Constraints enforced: length budget, graph
connectivity (inherent), no immediate revisit.

Preference keys (0-1):  challenge, nature, culture, popularity, scenic
Output: dict with segment path, length_km, ascent-free attrs, and WGS84 GeoJSON.

Run:  D:/Anaconda/envs/trailforge/python.exe src/route_generator.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as C  # noqa: E402
from src.segment_repr import load_segment_matrix  # noqa: E402
from src.trail_graph import TrailGraph  # noqa: E402

# preference key -> normalised segment-feature column it rewards
PREF_MAP = {
    "challenge": "geo_slope_mean",
    "nature": "geo_scene_natural",
    "culture": "geo_scene_manmade",
    "popularity": "beh_traffic_total",
    "scenic": "vis_photo_count",
}


class RouteGenerator:
    def __init__(self, graph: TrailGraph, feat: pd.DataFrame):
        self.g = graph
        self.feat = feat                       # normalised segment matrix (lypID idx)

    def _reward(self, seg_id: int, prefs: dict) -> float:
        row = self.feat.loc[seg_id]
        return float(sum(w * row.get(PREF_MAP[k], 0.0)
                         for k, w in prefs.items() if k in PREF_MAP))

    def generate(self, start_xy: tuple[float, float], budget_km: float,
                 prefs: dict, eps: float = 1e-6, cap: int = 200_000) -> dict:
        """Best-first DFS with backtracking: grow a simple path that reaches the
        budget. Pure greedy dead-ends on this sparse near-linear network (avg
        degree 2.14), so we explore depth-first ordered by reward/cost and
        backtrack when stuck, returning the first path that reaches ~budget
        (or the longest dead-end path found)."""
        start = self.g.find_nearest_segment(*start_xy)
        target = budget_km * 1000.0
        lo, hi = 0.8 * target, 1.1 * target
        L = self.g._length

        def cost(n):
            return max(L.get(n, 50.0), eps)

        stack = [(start, (start,), frozenset((start,)), L.get(start, 50.0))]
        best = (start,), L.get(start, 50.0)
        expan = 0
        while stack and expan < cap:
            cur, path, vis, length = stack.pop()
            expan += 1
            if length >= lo:
                return self._package(list(path), length, prefs)
            cands = [n for n in self.g.neighbors(cur)
                     if n not in vis and length + cost(n) <= hi]
            if not cands:
                if length > best[1]:
                    best = path, length
                continue
            # push best last so it is popped first (best-first)
            cands.sort(key=lambda n: self._reward(n, prefs) / cost(n))
            for n in cands:
                stack.append((n, path + (n,), vis | {n}, length + cost(n)))
        return self._package(list(best[0]), best[1], prefs)

    def _package(self, path, length_m, prefs) -> dict:
        sub = self.g.gdf.loc[path]
        geo_wgs = gpd.GeoSeries(sub.geometry.values, crs=self.g.gdf.crs).to_crs(4326)
        feats = [{"type": "Feature", "properties": {"lypID": int(s)},
                  "geometry": json.loads(gpd.GeoSeries([g], crs=4326).to_json())["features"][0]["geometry"]}
                 for s, g in zip(path, geo_wgs)]
        attrs = self.feat.loc[path]
        return {
            "segments": [int(s) for s in path],
            "n_segments": len(path),
            "length_km": round(length_m / 1000.0, 2),
            "prefs": prefs,
            "mean_attrs": {PREF_MAP[k]: round(float(attrs[PREF_MAP[k]].mean()), 3)
                           for k in prefs if k in PREF_MAP},
            "geojson": {"type": "FeatureCollection", "features": feats},
        }


def load() -> RouteGenerator:
    gdf = gpd.read_file(C.CLIM_SPRING_SEG)
    feat, _ = load_segment_matrix(normalize=True)
    return RouteGenerator(TrailGraph(gdf), feat)


if __name__ == "__main__":
    rg = load()
    # start from a high-traffic segment in the LARGEST connected component
    # (seg 13532; the global max-traffic seg sits in a 7-segment island). The
    # network has 610 components, so the start determines the reachable area.
    pop_seg = 13532
    c = rg.g.gdf.loc[pop_seg].geometry.interpolate(0.5, normalized=True)
    for label, prefs in [("nature+scenic", {"nature": 1.0, "scenic": 0.8, "popularity": 0.3}),
                         ("challenge", {"challenge": 1.0, "popularity": 0.2})]:
        r = rg.generate((c.x, c.y), budget_km=5.0, prefs=prefs)
        print(f"\n[{label}] start_seg={pop_seg} -> {r['n_segments']} segs, "
              f"{r['length_km']} km")
        print(f"  mean_attrs: {r['mean_attrs']}")
        print(f"  first 8 segs: {r['segments'][:8]}")
