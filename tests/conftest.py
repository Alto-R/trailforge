"""Shared fixture for the TrailGraph unit tests (T1.0).

Provides ``tg`` so ``pytest tests/`` runs in two environments:
  - dev with the G: raw shapefile mounted -> load it full-fidelity (52 fields);
  - offline -> rebuild the graph from the cached geometry + adjacency in
    data_processed/ and enrich it with the attribute columns the tests probe
    (geo_length/geo_slope_mean/beh_traffic_total renamed to the shapefile's
    length/slope_mean/joincount). Skips cleanly if neither source exists.

test_trail_graph.py also keeps its own ``main()`` so it still runs standalone
(``python tests/test_trail_graph.py``) when the shapefile is present.
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config as C  # noqa: E402
from src.trail_graph import ADJ_CACHE, TrailGraph  # noqa: E402

GEOM_CACHE = C.DATA_PROCESSED / "segment_geom_climbing.parquet"
SEG_FEATS = C.DATA_PROCESSED / "segment_features_climbing.parquet"
_RENAME = {"geo_length": "length", "geo_slope_mean": "slope_mean",
           "beh_traffic_total": "joincount"}


@pytest.fixture(scope="session")
def tg() -> TrailGraph:
    if C.CLIM_SPRING_SEG.exists():
        return TrailGraph(gpd.read_file(C.CLIM_SPRING_SEG))
    if not (GEOM_CACHE.exists() and ADJ_CACHE.exists()):
        pytest.skip("no segment geometry (G: shapefile or data_processed cache) available")
    gdf = gpd.read_parquet(GEOM_CACHE).reset_index()
    if SEG_FEATS.exists():
        feats = pd.read_parquet(SEG_FEATS)[list(_RENAME)].rename(columns=_RENAME)
        gdf = gdf.merge(feats, left_on="lypID", right_index=True, how="left")
    with open(ADJ_CACHE, "rb") as f:
        adj = {int(k): v for k, v in pickle.load(f).items()}
    return TrailGraph(gdf, adj)
