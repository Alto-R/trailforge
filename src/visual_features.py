"""T1.4' build the segment visual layer (s_visual) from 彭晓's photo points.

CLIP is shelved (original photos unobtainable, see D0.4 / plan). Instead we
aggregate 彭晓's 538k geotagged scene-classification points onto the 50m
climbing segments: each segment gets histograms over main/med/fine scene
classes, a photo-density count, a season distribution, and a has_visual flag.

Each photo is assigned to its NEAREST segment within ``MATCH_M`` metres
(sjoin_nearest), so density stays meaningful (no double counting).

Output: data_processed/segment_visual_climbing.parquet  (indexed by lypID)

Run:  D:/Anaconda/envs/trailforge/python.exe src/visual_features.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as C  # noqa: E402

MATCH_M = 100.0          # photo within 100m of a segment counts toward it
FINE_TOPK = 30           # keep top-K fine_cla categories, rest -> "other"
BJ_BBOX = (114.5, 38.0, 118.5, 41.0)  # lng/lat clip, matches interaction.py
OUT = C.DATA_PROCESSED / "segment_visual_climbing.parquet"
MED_CLASSES = ["MT", "FR", "HB", "TP", "WT", "PS", "VB", "LB", "SC", "CM",
               "AL", "WK", "DW"]


def _season(m) -> str | None:
    for s, months in C.SEASONS.items():
        if m in months:
            return s
    return None


def load_photos_on_segments() -> tuple[pd.DataFrame, int, gpd.GeoDataFrame]:
    """Assign each 彭晓 photo to its nearest climbing segment (<= MATCH_M).
    Returns (joined_df, n_photos_total, segments_gdf)."""
    segs = gpd.read_file(C.CLIM_SPRING_SEG, columns=["lypID"])[["lypID", "geometry"]]
    pts = gpd.read_file(C.PENGXIAO_SHP)
    n_total = len(pts)
    pts = pts.set_crs(C.CRS_WGS84, allow_override=True)
    minx, miny, maxx, maxy = BJ_BBOX
    pts = pts.cx[minx:maxx, miny:maxy]
    pts = pts.to_crs(segs.crs)

    joined = gpd.sjoin_nearest(
        pts[["main_cla", "med_cla", "fine_cla", "month", "geometry"]],
        segs, how="inner", max_distance=MATCH_M,
    ).reset_index(drop=True)  # sjoin keeps point index; ties create dup labels
    joined["season"] = pd.to_numeric(joined["month"], errors="coerce").map(_season)
    return joined.drop(columns="geometry"), n_total, segs


def _hist(joined: pd.DataFrame, col: str, prefix: str,
          keep: list[str] | None = None) -> pd.DataFrame:
    """Row-normalised crosstab of lypID x category, with a fixed/limited
    category set. Unlisted categories collapse into ``{prefix}_other``."""
    s = joined[col].fillna("none").astype(str)
    if keep is not None:
        s = s.where(s.isin(keep), other="other")
    ct = pd.crosstab(joined["lypID"], s)
    ct = ct.div(ct.sum(axis=1), axis=0)  # proportions
    ct.columns = [f"{prefix}_{c}" for c in ct.columns]
    return ct


def build() -> pd.DataFrame:
    joined, n_total, segs = load_photos_on_segments()
    n_matched = len(joined)
    print(f"[photos] total={n_total}  matched(<= {MATCH_M:.0f}m)={n_matched} "
          f"({n_matched/n_total:.1%})")

    fine_top = (joined["fine_cla"].value_counts().head(FINE_TOPK).index.tolist())

    count = joined.groupby("lypID").size().rename("vis_photo_count")
    main = _hist(joined, "main_cla", "vis_main")
    med = _hist(joined, "med_cla", "vis_med", keep=MED_CLASSES)
    fine = _hist(joined, "fine_cla", "vis_fine", keep=fine_top)
    season = _hist(joined, "season", "vis_season", keep=list(C.SEASONS))

    feat = pd.concat([count, main, med, fine, season], axis=1)
    # reindex to ALL segments; segments with no photo -> zeros, has_visual=0
    feat = feat.reindex(segs["lypID"].to_numpy())
    feat["vis_photo_count"] = feat["vis_photo_count"].fillna(0).astype(int)
    feat["has_visual"] = (feat["vis_photo_count"] > 0).astype(int)
    feat = feat.fillna(0.0)
    feat.index.name = "lypID"

    cov = feat["has_visual"].mean()
    print(f"[segments] {len(feat)} total | has_visual={feat['has_visual'].sum()} "
          f"({cov:.1%}) | feature dims={feat.shape[1]}")
    print(f"[density] photo_count per covered segment: "
          f"median={feat.loc[feat.has_visual==1,'vis_photo_count'].median():.0f} "
          f"mean={feat.loc[feat.has_visual==1,'vis_photo_count'].mean():.1f} "
          f"max={feat['vis_photo_count'].max()}")
    return feat


if __name__ == "__main__":
    feat = build()
    feat.to_parquet(OUT)
    print(f"[OK] written {OUT}  shape={feat.shape}")
    print("columns:", list(feat.columns))
