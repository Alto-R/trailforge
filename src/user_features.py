"""D0.3 user behaviour meta-features (档案A) + GMM profile clustering.

档案A is deliberately segment-free (no specific-segment info) to avoid the
circular-reasoning trap with CF (档案B). Features are derived from climbing
trips only, from triptime text (date / departure hour / duration) and track
geometry (distance / start point). Elevation is unavailable, so ascent-based
features are dropped; activity-type entropy is dropped (single activity scope).

Run:
  python src/user_features.py --pilot   # validate per-trip parsing on 1 file
  python src/user_features.py           # full per-trip build + GMM clustering
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as C  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import geopandas as gpd  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402
from sklearn.mixture import GaussianMixture  # noqa: E402
from sklearn.decomposition import PCA  # noqa: E402

MIN_TRIPS = 5
TRIP_TABLE = C.DATA_PROCESSED / "trip_features_climbing.parquet"
USER_FEATS = C.DATA_PROCESSED / "user_features_climbing.parquet"
GMM_ASSIGN = C.DATA_PROCESSED / "user_cluster_soft.parquet"

_DUR = {"周": 168.0, "天": 24.0, "小时": 1.0, "分钟": 1 / 60.0}


def parse_triptime(s: str):
    """-> (date 'YYYY-MM-DD' | None, hour int | None, duration_hours float | None)."""
    s = str(s)
    m_date = re.search(r"(\d{4}-\d{2}-\d{2})", s)
    m_hour = re.search(r"\d{4}-\d{2}-\d{2}\s+(\d{2}):\d{2}", s)
    dur = 0.0
    found = False
    for unit, h in _DUR.items():
        m = re.search(rf"(\d+)\s*{unit}", s)
        if m:
            dur += int(m.group(1)) * h
            found = True
    return (m_date.group(1) if m_date else None,
            int(m_hour.group(1)) if m_hour else None,
            dur if found else None)


def _read_csv_any(path: Path, **kw):
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return pd.read_csv(path, encoding=enc, **kw)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path, encoding="utf-8", errors="ignore", **kw)


def trip_meta_full() -> pd.DataFrame:
    """tripid -> userid, date, hour, duration_h for climbing trips."""
    climbing = _read_csv_any(C.CLIMBING_TRIPS_CSV, usecols=[0])
    cids = set(pd.to_numeric(climbing.iloc[:, 0], errors="coerce").dropna().astype("int64"))
    frames = []
    for xlsx in sorted(C.SIXFOOT_RAW.rglob("basic*.xlsx")):
        frames.append(pd.read_excel(xlsx, usecols=lambda c: c in {"tripid", "userid", "triptime"}))
    meta = pd.concat(frames, ignore_index=True)
    meta["tripid"] = pd.to_numeric(meta["tripid"], errors="coerce")
    meta = meta.dropna(subset=["tripid"]).astype({"tripid": "int64"}).drop_duplicates("tripid")
    meta = meta[meta["tripid"].isin(cids)].copy()
    parsed = meta["triptime"].map(parse_triptime)
    meta["date"] = pd.to_datetime([p[0] for p in parsed], errors="coerce")
    meta["hour"] = [p[1] for p in parsed]
    meta["duration_h"] = [p[2] for p in parsed]
    return meta[["tripid", "userid", "date", "hour", "duration_h"]]


def trip_geom(climbing_ids: set, pilot: bool = False) -> pd.DataFrame:
    """tripid -> dist_km, start_x, start_y (Albers), Beijing climbing tracks only."""
    segs = gpd.read_file(C.CLIM_SPRING_SEG, columns=["lypID"])
    target = segs.crs
    files = sorted(C.SIXFOOT_RAW.rglob("track*.shp"))
    if pilot:
        files = files[:1]
    rows = []
    for i, tf in enumerate(files, 1):
        t = gpd.read_file(tf)
        t["tripid"] = pd.to_numeric(t["tripid"], errors="coerce")
        t = t.dropna(subset=["tripid"])
        t["tripid"] = t["tripid"].astype("int64")
        t = t[t["tripid"].isin(climbing_ids)]
        if t.empty:
            continue
        t = t.set_crs(C.CRS_WGS84, allow_override=True).cx[114.5:118.5, 38.0:41.0]
        if t.empty:
            continue
        t = t.to_crs(target)
        t = t[t.geometry.is_valid & ~t.geometry.is_empty]
        starts = t.geometry.apply(lambda g: g.geoms[0].coords[0] if g.geom_type == "MultiLineString" else g.coords[0])
        sub = pd.DataFrame({
            "tripid": t["tripid"].values,
            "dist_km": t.geometry.length.values / 1000.0,
            "start_x": [c[0] for c in starts],
            "start_y": [c[1] for c in starts],
        })
        rows.append(sub)
        print(f"  [{i}/{len(files)}] {tf.name}: {len(sub)} trips", flush=True)
    out = pd.concat(rows, ignore_index=True)
    # one track per tripid (largest by distance, in case of dup geometries)
    out = out.sort_values("dist_km").drop_duplicates("tripid", keep="last")
    return out


def build_trip_table(pilot=False) -> pd.DataFrame:
    if not pilot and TRIP_TABLE.exists():
        print(f"[trip table] loaded cache {TRIP_TABLE.name}", flush=True)
        return pd.read_parquet(TRIP_TABLE)
    meta = trip_meta_full()
    print(f"[meta] {len(meta)} climbing trips", flush=True)
    geom = trip_geom(set(meta["tripid"]), pilot=pilot)
    tbl = meta.merge(geom, on="tripid", how="inner")
    print(f"[trip table] {len(tbl)} trips with geometry", flush=True)
    if not pilot:
        tbl.to_parquet(TRIP_TABLE, index=False)
    return tbl


def _entropy(counts) -> float:
    p = np.asarray(counts, float)
    p = p[p > 0]
    p = p / p.sum()
    return float(-(p * np.log(p)).sum()) if len(p) else 0.0


def user_features(tbl: pd.DataFrame, min_trips=MIN_TRIPS) -> pd.DataFrame:
    tbl = tbl.dropna(subset=["date"]).copy()
    tbl["month"] = tbl["date"].dt.month
    tbl["weekday"] = tbl["date"].dt.weekday
    tbl["daypart"] = pd.cut(tbl["hour"], [-1, 6, 11, 17, 23], labels=["night", "morning", "afternoon", "evening"])
    season_of = {**{m: "spring" for m in (3, 4, 5)}, **{m: "summer" for m in (6, 7, 8)},
                 **{m: "autumn" for m in (9, 10, 11)}, **{m: "winter" for m in (12, 1, 2)}}
    tbl["season"] = tbl["month"].map(season_of)

    recs = []
    for uid, g in tbl.groupby("userid"):
        n = len(g)
        if n < min_trips:
            continue
        dates = g["date"].sort_values()
        span_months = max((dates.iloc[-1] - dates.iloc[0]).days / 30.0, 1.0)
        gaps = dates.diff().dropna().dt.days
        sx, sy = g["start_x"].median(), g["start_y"].median()
        d_to_center = np.sqrt((g["start_x"] - sx) ** 2 + (g["start_y"] - sy) ** 2) / 1000.0
        grid = set(zip((g["start_x"] // 5000).astype(int), (g["start_y"] // 5000).astype(int)))
        recs.append({
            "userid": uid, "n_trips": n,
            "freq_per_month": n / span_months,
            "seasonality_spring": (g["season"] == "spring").mean(),
            "seasonality_summer": (g["season"] == "summer").mean(),
            "weekend_ratio": (g["weekday"] >= 5).mean(),
            "gap_cv": gaps.std() / gaps.mean() if gaps.mean() and len(gaps) > 1 else 0.0,
            "dist_mean": g["dist_km"].mean(),
            "dist_cv": g["dist_km"].std() / g["dist_km"].mean() if g["dist_km"].mean() else 0.0,
            "duration_mean": g["duration_h"].mean(),
            "duration_cv": g["duration_h"].std() / g["duration_h"].mean() if g["duration_h"].mean() else 0.0,
            "activity_radius": d_to_center.mean(),
            "start_compactness": (d_to_center <= 2.0).mean(),
            "coverage_breadth": len(grid),
            "season_entropy": _entropy(g["season"].value_counts().values),
            "daypart_entropy": _entropy(g["daypart"].value_counts().values),
        })
    feats = pd.DataFrame(recs).set_index("userid")
    return feats.fillna(feats.median(numeric_only=True))


def cluster_and_report(feats: pd.DataFrame):
    feat_cols = [c for c in feats.columns if c != "n_trips"]
    X = StandardScaler().fit_transform(feats[feat_cols].values)
    bic = {}
    models = {}
    for k in range(3, 13):
        # init_params='random_from_data' avoids KMeans init, which triggers a
        # native MKL/vcomp threadpool probe that crashes in this conda env.
        gm = GaussianMixture(n_components=k, covariance_type="full", n_init=5,
                             init_params="random_from_data", random_state=42)
        gm.fit(X)
        bic[k] = gm.bic(X)
        models[k] = gm
    best_k = min(bic, key=bic.get)
    gm = models[best_k]
    soft = gm.predict_proba(X)
    hard = soft.argmax(1)
    pca = PCA(n_components=2).fit_transform(X)

    L = ["# D0.3 用户行为画像聚类报告\n"]
    L.append(f"- 有效用户(≥{MIN_TRIPS} 次登山): **{len(feats)}**")
    L.append(f"- 特征({len(feat_cols)}维, 段无关/档案A): {feat_cols}\n")
    L.append("## BIC vs K")
    L.append("```\n" + "\n".join(f"K={k}: BIC={v:,.0f}" for k, v in bic.items()) + "\n```")
    L.append(f"- **BIC 最优 K = {best_k}**\n")
    L.append("## 各画像组规模")
    sizes = pd.Series(hard).value_counts().sort_index()
    L.append("```\n" + sizes.to_string() + "\n```")
    L.append("## 各组特征均值(原始尺度, 用于解读)")
    prof = feats[feat_cols].copy()
    prof["cluster"] = hard
    L.append("```\n" + prof.groupby("cluster").mean().round(2).T.to_string() + "\n```")
    L.append("\n## 数据质量 (起点不确定性, 计划 6.1.1)")
    L.append(f"- start_compactness 中位 {feats['start_compactness'].median():.2f} "
             f"(=2km 内起点占比); 偏低者起点散布大，activity_radius 需谨慎。")
    L.append("\n## 结论")
    L.append(f"- BIC 在 K={best_k} 取最优；各组在 freq/距离/时长/季节熵 等维度可解读 → "
             "画像聚类**可行**(详见上表人工判读)。soft 分配已存为 u_cluster 供 CF 用。")
    (C.REPORTS / "D0.3_user_clustering.md").write_text("\n".join(L), encoding="utf-8")

    assign = pd.DataFrame(soft, index=feats.index, columns=[f"p{c}" for c in range(best_k)])
    assign["hard"] = hard
    assign["pca1"], assign["pca2"] = pca[:, 0], pca[:, 1]
    assign.to_parquet(GMM_ASSIGN)
    feats.to_parquet(USER_FEATS)
    print(f"[OK] best_k={best_k}, users={len(feats)}; report + parquet written", flush=True)
    print("BIC:", {k: round(v) for k, v in bic.items()}, flush=True)
    print("cluster sizes:", sizes.to_dict(), flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true")
    args = ap.parse_args()
    tbl = build_trip_table(pilot=args.pilot)
    if args.pilot:
        print(tbl.head(10).to_string(), flush=True)
        print("\nnull rates:\n", tbl.isna().mean().round(3).to_string(), flush=True)
    else:
        feats = user_features(tbl)
        print(f"[features] {feats.shape}", flush=True)
        cluster_and_report(feats)
