"""RouteEngine: exploration-aid route recommendation (设计 R1.3).

Loaded once at app startup, kept resident. All artifacts come from
data_processed/ (no G: shapefile).

Per-request flow:
  preferences (explicit sliders, else persona defaults, else balanced)
    -> per-segment preference score  (PREF_MAP attributes, weighted)
    +  CF prior  (E4 content-tower segment score, user-independent learned quality)
    = seg_scores
    -> RouteGenerator.generate_pool  (candidate pool from the clicked start)
    -> MMR  (diversify, plan §5.4.5)  -> 3-5 candidates
    -> each candidate: geojson + attributes + explainable labels (§5.4.6)

Why preferences and not the CF user signal: the E4 content tower maps every user
to ~the same embedding (it does NOT personalize cold users — see design R1.1), so
visible personalization comes from the explicit preferences; the CF score serves
only as a flat learned relevance/quality prior.
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import torch
from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402
from src import diversifier, explainer, persona  # noqa: E402
from src.cf_export import GEOM_CACHE, SEG_LOGCNT, load_model  # noqa: E402
from src.persona import PREF_MAP  # noqa: E402
from src.route_generator import RouteGenerator  # noqa: E402
from src.segment_repr import load_segment_matrix  # noqa: E402
from src.trail_graph import ADJ_CACHE, TrailGraph  # noqa: E402

RAW_SEG = C.DATA_PROCESSED / "segment_features_climbing.parquet"
PREF_KEYS = list(PREF_MAP)
W_PREF = 1.0        # explicit preferences dominate (the visible personalization)
W_CF = 0.3          # CF content-tower prior (flat across users, learned quality)
POOL_SIZE = 60
DEFAULT_N_ROUTES = 4


def _minmax(a: np.ndarray) -> np.ndarray:
    lo, hi = float(a.min()), float(a.max())
    return (a - lo) / ((hi - lo) or 1.0)


class RouteEngine:
    def __init__(self):
        self.model, self.meta = load_model()
        self.s_cols = self.meta["s_cols"]

        s_df, _ = load_segment_matrix(normalize=True)
        self.s_df = s_df                                     # normalised, for prefs
        S = torch.tensor(s_df[self.s_cols].to_numpy(np.float32))
        with torch.no_grad():
            self.seg_emb = self.model.g_s(S)                 # [n_segs, d]
        self.seg_ids = s_df.index.to_numpy()                 # lypID order == rows

        # adaptive-alpha per segment (cold user => log_cnt_u=0, user-independent)
        log_cnt = pd.read_parquet(SEG_LOGCNT)["log_cnt_s"].reindex(s_df.index).fillna(0.0)
        lcs = torch.tensor(log_cnt.to_numpy(np.float32))
        if getattr(self.model, "adaptive_alpha", False):
            w = self.model.alpha_w.detach()
            alpha_seg = torch.sigmoid(w[0] + w[2] * lcs)
        else:
            alpha_seg = torch.full((len(lcs),), float(self.model.alpha))
        # CF prior: the E4 content score (flat across users) -> [0,1] over segments
        self.catalog = persona.personas()
        u_feat = persona.persona_u_feat(self.catalog[0]["id"], self.meta, self.catalog)
        with torch.no_grad():
            u_emb = self.model.g_u(torch.from_numpy(u_feat).unsqueeze(0))
            cf_raw = (alpha_seg * (self.seg_emb * u_emb).sum(-1)).numpy()
        self.cf_prior = _minmax(cf_raw)                      # [n_segs], aligned to seg_ids

        # preference feature columns (normalised), as a matrix for fast weighting
        self.pref_cols = [PREF_MAP[k] for k in PREF_KEYS if PREF_MAP[k] in s_df.columns]
        self._pref_mat = s_df[self.pref_cols].to_numpy(np.float32)   # [n_segs, n_pref]

        # trail graph from cached geometry (Albers) + adjacency — no G: shapefile
        geom = gpd.read_parquet(GEOM_CACHE).reset_index()
        with open(ADJ_CACHE, "rb") as f:
            adj = {int(k): v for k, v in pickle.load(f).items()}
        self.graph = TrailGraph(geom, adj)
        self.gen = RouteGenerator(self.graph, s_df)

        crs = self.graph.gdf.crs
        self._to_albers = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        self._to_wgs84 = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)

        self.raw_feat = pd.read_parquet(RAW_SEG)
        self.attr_stats = explainer.attr_stats(self.raw_feat)
        self._trails = None

    # --- public API --------------------------------------------------------
    def personas(self) -> list[dict]:
        return [{"id": p["id"], "label": p["label"], "description": p["description"],
                 "size": p["size"], "default_prefs": p.get("default_prefs", {})}
                for p in self.catalog]

    @property
    def n_segments(self) -> int:
        return len(self.seg_ids)

    def trails_geojson(self) -> dict:
        if self._trails is None:
            wgs = self.graph.gdf[["lypID", "geometry"]].to_crs(4326)
            self._trails = json.loads(wgs.to_json())
        return self._trails

    # --- scoring -----------------------------------------------------------
    def resolve_prefs(self, persona_id: str | None, preferences: dict | None) -> dict:
        if preferences:                                      # explicit override
            return {k: float(v) for k, v in preferences.items() if k in PREF_MAP}
        if persona_id:
            return persona.default_prefs_of(persona_id, self.catalog)
        return {k: 0.2 for k in PREF_KEYS}                   # balanced fallback

    def _seg_scores(self, prefs: dict) -> dict:
        w = np.array([float(prefs.get(k, 0.0)) for k in PREF_KEYS
                      if PREF_MAP[k] in self.s_df.columns], dtype=np.float32)
        pref_raw = self._pref_mat @ w                        # [n_segs]
        combined = W_PREF * _minmax(pref_raw) + W_CF * self.cf_prior
        return dict(zip((int(s) for s in self.seg_ids), combined.tolist()))

    # --- core --------------------------------------------------------------
    def _candidate(self, item: dict, seg_scores: dict, rel: float) -> dict:
        segs = item["segments"]
        attrs = explainer.route_attrs(segs, self.raw_feat, self.attr_stats["cols"])
        return {
            "length_km": item["length_km"],
            "n_segments": item["n_segments"],
            "reachable": item["reached"],
            "segments": segs,
            "geojson": self.gen.route_geojson(segs),
            "attributes": attrs,
            "labels": explainer.label_route(attrs, self.attr_stats),
            "score": round(float(rel), 4),
        }

    def route(self, lng: float, lat: float, persona_id: str | None,
              preferences: dict | None, budget_km: float,
              n_routes: int = DEFAULT_N_ROUTES) -> dict:
        x, y = self._to_albers.transform(lng, lat)
        prefs = self.resolve_prefs(persona_id, preferences)
        seg_scores = self._seg_scores(prefs)

        pool = self.gen.generate_pool((x, y), budget_km, seg_scores=seg_scores,
                                      pool_size=POOL_SIZE)
        seg_sets = [set(it["segments"]) for it in pool]
        rel = [float(np.mean([seg_scores.get(s, 0.0) for s in it["segments"]]))
               for it in pool]
        order = diversifier.mmr_select(seg_sets, rel, n=n_routes)

        candidates = [self._candidate(pool[i], seg_scores, rel[i]) for i in order]
        start_seg = pool[0]["start_segment"]
        sx, sy = self.graph.gdf.loc[start_seg].geometry.interpolate(
            0.5, normalized=True).coords[0]
        slng, slat = self._to_wgs84.transform(sx, sy)
        reachable = any(c["reachable"] for c in candidates)
        note = None if reachable else (
            f"该起点所在片区凑不满 {budget_km}km（最多约 {candidates[0]['length_km']}km）")
        return {
            "candidates": candidates,
            "start_snapped": (round(slng, 6), round(slat, 6)),
            "reachable": reachable,
            "prefs_used": prefs,
            "note": note,
        }
