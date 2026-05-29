"""TrailGraph: in-memory trail network over the 50m climbing segments.

The segment network is a set of ~50m LineStrings (Krasovsky Albers, metres).
Two segments are adjacent when they share an endpoint node (snapped to a small
tolerance). Adjacency is stored as a plain ``dict[int, list[int]]`` keyed by the
segment id (``lypID``), matching the structure used by the original Vispath
``workingdata5`` adjacency, so downstream code (route generator) stays familiar.

Interface follows 主文档 §5.4.1. Built once at startup and kept resident.

Run as a script to build + cache the adjacency and print connectivity stats:
    D:/Anaconda/envs/trailforge/python.exe src/trail_graph.py
"""
from __future__ import annotations

import pickle
import sys
from collections import defaultdict, deque
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.geometry import Point

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C

ID_COL = "lypID"
SNAP_M = 1.0  # endpoint snap tolerance in metres (Albers units)
ADJ_CACHE = C.DATA_PROCESSED / "adjacency_climbing.pkl"


def _node_key(x: float, y: float, snap: float = SNAP_M) -> tuple[int, int]:
    """Snap a coordinate to a grid of ``snap`` metres so coincident endpoints
    collapse to one node despite floating-point noise."""
    return (round(x / snap), round(y / snap))


def build_adjacency(gdf: gpd.GeoDataFrame, id_col: str = ID_COL,
                    snap: float = SNAP_M) -> dict[int, list[int]]:
    """Build segment-level adjacency: seg_id -> sorted list of neighbour seg_ids
    that share at least one endpoint node."""
    node_to_segs: dict[tuple, set] = defaultdict(set)
    seg_nodes: dict[int, tuple] = {}
    for sid, geom in zip(gdf[id_col].to_numpy(), gdf.geometry.to_numpy()):
        coords = list(geom.coords)
        a = _node_key(*coords[0][:2], snap)
        b = _node_key(*coords[-1][:2], snap)
        seg_nodes[int(sid)] = (a, b)
        node_to_segs[a].add(int(sid))
        node_to_segs[b].add(int(sid))

    adjacency: dict[int, set] = defaultdict(set)
    for sid, (a, b) in seg_nodes.items():
        for nb in node_to_segs[a] | node_to_segs[b]:
            if nb != sid:
                adjacency[sid].add(nb)
    return {sid: sorted(nbs) for sid, nbs in adjacency.items()}


class TrailGraph:
    """Resident trail network. See 主文档 §5.4.1."""

    def __init__(self, segments_gdf: gpd.GeoDataFrame,
                 adjacency: dict[int, list[int]] | None = None,
                 id_col: str = ID_COL):
        self.id_col = id_col
        self.gdf = segments_gdf.set_index(id_col, drop=False)
        self.adjacency = adjacency if adjacency is not None else build_adjacency(
            segments_gdf, id_col)
        self._sindex = self.gdf.sindex  # spatial index for nearest lookup
        # cache geometry length (metres) for weighting
        if "length" in self.gdf.columns:
            self._length = self.gdf["length"].to_dict()
        else:
            self._length = self.gdf.geometry.length.to_dict()

    # --- core queries ------------------------------------------------------
    def neighbors(self, segment_id: int, direction: str = "out") -> list[int]:
        """Adjacent segment ids. ``direction`` is accepted for API parity with
        the planned directed graph; the current network is undirected so both
        directions return the same set."""
        return self.adjacency.get(int(segment_id), [])

    def attributes(self, segment_id: int) -> dict:
        return self.gdf.loc[int(segment_id)].drop(labels="geometry").to_dict()

    def subgraph(self, center_segment: int, radius_km: float) -> set[int]:
        """All segments within ``radius_km`` *graph distance* (summed segment
        lengths along the shortest hop path) of ``center_segment``."""
        budget = radius_km * 1000.0
        start = int(center_segment)
        dist = {start: 0.0}
        dq = deque([start])
        while dq:
            cur = dq.popleft()
            for nb in self.neighbors(cur):
                step = self._length.get(nb, 50.0)
                nd = dist[cur] + step
                if nd <= budget and (nb not in dist or nd < dist[nb]):
                    dist[nb] = nd
                    dq.append(nb)
        return set(dist)

    def shortest_path(self, start: int, end: int, weight: str = "length") -> list[int]:
        """Dijkstra over segments (hop weight = neighbour segment length).
        Returns the segment-id path inclusive of start and end, or [] if
        unreachable."""
        import heapq
        start, end = int(start), int(end)
        pq = [(0.0, start, [start])]
        seen = set()
        while pq:
            cost, cur, path = heapq.heappop(pq)
            if cur == end:
                return path
            if cur in seen:
                continue
            seen.add(cur)
            for nb in self.neighbors(cur):
                if nb in seen:
                    continue
                w = self._length.get(nb, 50.0) if weight == "length" else 1.0
                heapq.heappush(pq, (cost + w, nb, path + [nb]))
        return []

    def find_nearest_segment(self, x: float, y: float) -> int:
        """Nearest segment id to a point given in the graph CRS (Albers metres)."""
        pt = Point(x, y)
        idx = self._sindex.nearest(pt, return_all=False)[1][0]
        return int(self.gdf.iloc[idx][self.id_col])

    # --- factory -----------------------------------------------------------
    @classmethod
    def load(cls, seg_path: Path = C.CLIM_SPRING_SEG,
             adj_cache: Path = ADJ_CACHE) -> "TrailGraph":
        gdf = gpd.read_file(seg_path)
        adjacency = None
        if adj_cache.exists():
            with open(adj_cache, "rb") as f:
                adjacency = {int(k): v for k, v in pickle.load(f).items()}
        return cls(gdf, adjacency)


def _connectivity_stats(adjacency: dict[int, list[int]]) -> dict:
    degs = np.array([len(v) for v in adjacency.values()])
    # connected components over the undirected adjacency
    seen, n_comp, sizes = set(), 0, []
    for s in adjacency:
        if s in seen:
            continue
        n_comp += 1
        sz, dq = 0, deque([s])
        seen.add(s)
        while dq:
            c = dq.popleft(); sz += 1
            for nb in adjacency.get(c, []):
                if nb not in seen:
                    seen.add(nb); dq.append(nb)
        sizes.append(sz)
    return {
        "n_segments_with_adj": len(adjacency),
        "deg_mean": round(float(degs.mean()), 3),
        "deg_max": int(degs.max()),
        "deg_zero": int((degs == 0).sum()),
        "n_components": n_comp,
        "largest_component": max(sizes) if sizes else 0,
    }


if __name__ == "__main__":
    print(f"loading segments from {C.CLIM_SPRING_SEG} ...")
    gdf = gpd.read_file(C.CLIM_SPRING_SEG)
    print(f"  {len(gdf)} segments")
    print("building adjacency ...")
    adj = build_adjacency(gdf)
    with open(ADJ_CACHE, "wb") as f:
        pickle.dump(adj, f)
    print(f"  cached -> {ADJ_CACHE}")
    stats = _connectivity_stats(adj)
    for k, v in stats.items():
        print(f"  {k:24s} = {v}")
