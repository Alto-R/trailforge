"""T2.3 assemble the segment representation  s = [s_geo; s_visual; s_behavior].

Three layers, per 主文档 §4.2 / §5.2:
  s_geo      terrain + scene + POI/facility, from the 50m segment shp (dense)
  s_visual   彭晓 scene-class histograms, from segment_visual_climbing.parquet
  s_behavior traffic + profile-group distribution, from the interaction matrix

We store RAW (interpretable) features with layer-prefixed columns plus
has_visual / has_behavior flags. ``load_segment_matrix(normalize=True)`` returns
the per-layer L2-normalised concatenation for the CF segment tower.

Notes / known gaps:
  - No DEM available -> ascent/descent/elevation_max not computed (plan §5.2.1).
  - completion_rate / avg_speed need per-trajectory data we don't aggregate; skipped.

Output: data_processed/segment_features_climbing.parquet   (indexed by lypID)

Run:  D:/Anaconda/envs/trailforge/python.exe src/segment_repr.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as C  # noqa: E402

INTER = C.DATA_PROCESSED / "interactions_climbing.parquet"
SOFT = C.DATA_PROCESSED / "user_cluster_soft.parquet"
VISUAL = C.DATA_PROCESSED / "segment_visual_climbing.parquet"
OUT = C.DATA_PROCESSED / "segment_features_climbing.parquet"

# terrain/scene fields kept from the shp -> geo_*
GEO_FIELDS = {
    "length": "geo_length", "slope_mean": "geo_slope_mean",
    "natural": "geo_scene_natural", "man_made": "geo_scene_manmade",
    "daily_life": "geo_scene_daily", "ziran_mean": "geo_ziran_mean",
}
# POI / facility fields -> geo_poi_* (sparse, only near POIs)
POI_FIELDS = {
    "MEAN_score": "geo_poi_rating", "MEAN_emo_L": "geo_poi_emotion",
    "FREQUENCY": "geo_poi_reviews",
    "饮食购": "geo_poi_food", "娱乐活": "geo_poi_entertain", "住宿": "geo_poi_lodging",
    "票": "geo_poi_ticket", "交通": "geo_poi_transport", "环境": "geo_poi_environment",
    "气氛": "geo_poi_atmosphere", "人": "geo_poi_crowd", "价格": "geo_poi_price",
    "体验": "geo_poi_experience",
}


def build_geo() -> pd.DataFrame:
    cols = list(GEO_FIELDS) + list(POI_FIELDS) + ["lypID"]
    g = gpd.read_file(C.CLIM_SPRING_SEG, columns=cols)
    geo = g[["lypID"]].copy()
    for src, dst in {**GEO_FIELDS, **POI_FIELDS}.items():
        geo[dst] = pd.to_numeric(g[src], errors="coerce").fillna(0.0)
    return geo.set_index("lypID")


def build_behavior() -> pd.DataFrame:
    """traffic + seasonal + visiting profile-group distribution, per segment."""
    it = pd.read_parquet(INTER)
    grp = it.groupby("lypID")
    beh = pd.DataFrame({
        "beh_traffic_total": grp["count"].sum(),
        "beh_unique_users": grp["userid"].nunique(),
    })
    # seasonal distribution (proportions over 春/夏/秋/冬)
    seas = (it.pivot_table(index="lypID", columns="season", values="count",
                           aggfunc="sum", fill_value=0))
    seas = seas.div(seas.sum(axis=1), axis=0)
    seas.columns = [f"beh_season_{c}" for c in seas.columns]
    beh = beh.join(seas)

    # profile-group distribution: weight each visiting user's soft assignment by
    # interaction count, then normalise. Only the 603 clustered users contribute.
    soft = pd.read_parquet(SOFT)
    # soft also carries pca1/pca2/hard; keep only the p0..pK probability columns
    pcols = [c for c in soft.columns if c.startswith("p") and c[1:].isdigit()]
    iu = it[["userid", "lypID", "count"]].merge(
        soft[pcols], left_on="userid", right_index=True, how="inner")
    for p in pcols:
        iu[p] = iu[p] * iu["count"]
    cl = iu.groupby("lypID")[pcols].sum()
    cl = cl.div(cl.sum(axis=1), axis=0)            # row-normalise
    cl.columns = [f"beh_cluster_{p[1:]}" for p in pcols]
    beh = beh.join(cl)
    return beh


def assemble() -> pd.DataFrame:
    geo = build_geo()
    beh = build_behavior()
    vis = pd.read_parquet(VISUAL)               # already vis_* + has_visual

    feat = geo.join(beh, how="left").join(vis, how="left")
    feat["has_behavior"] = (feat["beh_traffic_total"].fillna(0) > 0).astype(int)
    if "has_visual" not in feat:
        feat["has_visual"] = 0
    feat["has_visual"] = feat["has_visual"].fillna(0).astype(int)
    feat = feat.fillna(0.0)
    feat.index.name = "lypID"
    return feat


# --- consumption helper ----------------------------------------------------
def _layer_cols(cols, prefix):
    return [c for c in cols if c.startswith(prefix)]


def load_segment_matrix(normalize: bool = True):
    """Return (feature_df, layer_index) ready for the CF segment tower.
    When normalize=True each layer (geo/vis/beh) is L2-normalised per row so no
    single high-dim layer dominates (主文档 §5.2.4)."""
    feat = pd.read_parquet(OUT)
    layers = {"geo": _layer_cols(feat.columns, "geo_"),
              "vis": _layer_cols(feat.columns, "vis_"),
              "beh": _layer_cols(feat.columns, "beh_")}
    if normalize:
        for cols in layers.values():
            block = feat[cols].to_numpy(float)
            norm = np.linalg.norm(block, axis=1, keepdims=True)
            norm[norm == 0] = 1.0
            feat[cols] = block / norm
    return feat, layers


if __name__ == "__main__":
    feat = assemble()
    feat.to_parquet(OUT)
    geo_c = _layer_cols(feat.columns, "geo_")
    vis_c = _layer_cols(feat.columns, "vis_")
    beh_c = _layer_cols(feat.columns, "beh_")
    print(f"[OK] {OUT.name}  shape={feat.shape}")
    print(f"  layers: geo={len(geo_c)}  visual={len(vis_c)}  behavior={len(beh_c)}  "
          f"+ flags(has_visual,has_behavior)")
    print(f"  coverage: has_visual={feat['has_visual'].mean():.1%}  "
          f"has_behavior={feat['has_behavior'].mean():.1%}")
    print(f"  cluster-dist coverage (any beh_cluster>0): "
          f"{(feat[[c for c in beh_c if c.startswith('beh_cluster')]].sum(axis=1) > 0).mean():.1%}")
    print(f"  geo cols: {geo_c}")
    print(f"  beh cols: {beh_c}")
