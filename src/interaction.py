"""D0.2 rebuild the climbing user-segment interaction matrix (all seasons).

Strategy (per D0.1 conclusions): the climbing 50m network geometry is
season-independent, so we use the spring "AllMessage" file (29941 segments
with stable lypID, Krasovsky Albers) as the canonical segment set and derive
all-season behaviour by spatially joining raw climbing tracks to a buffer
around each segment, stratified by trip season.

Output: data_processed/interactions_climbing.parquet
        columns = [userid, lypID, season, count, first_ts]

Run:
  python src/interaction.py --pilot     # one track file, quick logic check
  python src/interaction.py             # full run over all track files
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as C  # noqa: E402

import pandas as pd  # noqa: E402
import geopandas as gpd  # noqa: E402

BUFFER_M = 25  # half the 50m segment length; "passes near this segment"
META_CACHE = C.DATA_PROCESSED / "trip_meta_climbing.parquet"
OUT = C.DATA_PROCESSED / "interactions_climbing.parquet"


def _read_csv_any(path: Path, **kw) -> pd.DataFrame:
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return pd.read_csv(path, encoding=enc, **kw)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path, encoding="utf-8", errors="ignore", **kw)


def month_to_season(m) -> str | None:
    for season, months in C.SEASONS.items():
        if m in months:
            return season
    return None


def load_segments() -> gpd.GeoDataFrame:
    """Canonical climbing 50m segments (geometry + lypID), in Albers."""
    segs = gpd.read_file(C.CLIM_SPRING_SEG, columns=["lypID"])
    segs = segs[["lypID", "geometry"]].copy()
    return segs


def segment_buffers(segs: gpd.GeoDataFrame, dist: float = BUFFER_M) -> gpd.GeoDataFrame:
    buf = segs.copy()
    buf["geometry"] = segs.geometry.buffer(dist)
    return buf


def load_trip_meta(use_cache: bool = True) -> pd.DataFrame:
    """tripid -> userid, season, first_ts for climbing trips only."""
    if use_cache and META_CACHE.exists():
        return pd.read_parquet(META_CACHE)

    climbing = _read_csv_any(C.CLIMBING_TRIPS_CSV, usecols=[0])
    climbing_ids = set(pd.to_numeric(climbing.iloc[:, 0], errors="coerce").dropna().astype("int64"))

    frames = []
    for xlsx in sorted(C.SIXFOOT_RAW.rglob("basic*.xlsx")):
        df = pd.read_excel(xlsx, usecols=lambda c: c in {"tripid", "userid", "triptime", "triptype"})
        frames.append(df)
    meta = pd.concat(frames, ignore_index=True)
    meta["tripid"] = pd.to_numeric(meta["tripid"], errors="coerce")
    meta = meta.dropna(subset=["tripid"]).astype({"tripid": "int64"})
    meta = meta.drop_duplicates(subset="tripid")
    meta = meta[meta["tripid"].isin(climbing_ids)].copy()

    # triptime is free text, e.g. "于 2018-05-26 19:01 出发,历时 1 小时, 6 分钟"
    date_str = meta["triptime"].astype(str).str.extract(r"(\d{4}-\d{2}-\d{2})")[0]
    ts = pd.to_datetime(date_str, errors="coerce")
    meta["first_ts"] = ts
    meta["season"] = ts.dt.month.map(month_to_season)
    meta = meta[["tripid", "userid", "season", "first_ts"]]

    C.DATA_PROCESSED.mkdir(exist_ok=True)
    meta.to_parquet(META_CACHE, index=False)
    return meta


def track_to_segments(track_shp: Path, seg_buf: gpd.GeoDataFrame,
                      climbing_ids: set[int]) -> pd.DataFrame:
    """Return distinct (tripid, lypID) pairs for climbing tracks in one file."""
    tracks = gpd.read_file(track_shp)
    tracks["tripid"] = pd.to_numeric(tracks["tripid"], errors="coerce")
    tracks = tracks.dropna(subset=["tripid"])
    tracks["tripid"] = tracks["tripid"].astype("int64")
    tracks = tracks[tracks["tripid"].isin(climbing_ids)]
    if tracks.empty:
        return pd.DataFrame(columns=["tripid", "lypID"])
    tracks = tracks.set_crs(C.CRS_WGS84, allow_override=True)
    # raw geometries contain corrupt out-of-range coords; keep only Beijing bbox
    tracks = tracks.cx[114.5:118.5, 38.0:41.0]
    if tracks.empty:
        return pd.DataFrame(columns=["tripid", "lypID"])
    tracks = tracks.to_crs(seg_buf.crs)
    joined = gpd.sjoin(tracks[["tripid", "geometry"]], seg_buf, predicate="intersects")
    return joined[["tripid", "lypID"]].drop_duplicates()


def build(pilot: bool = False) -> pd.DataFrame:
    segs = load_segments()
    print(f"[segs] {len(segs)} segments, crs={segs.crs.name}")
    seg_buf = segment_buffers(segs)

    meta = load_trip_meta()
    climbing_ids = set(meta["tripid"])
    print(f"[meta] {len(meta)} climbing trips, {meta['userid'].nunique()} users")
    print(f"[meta] season dist:\n{meta['season'].value_counts(dropna=False).to_string()}")

    track_files = sorted(C.SIXFOOT_RAW.rglob("track*.shp"))
    if pilot:
        track_files = track_files[:1]
    print(f"[tracks] processing {len(track_files)} file(s)")

    pairs = []
    for i, tf in enumerate(track_files, 1):
        p = track_to_segments(tf, seg_buf, climbing_ids)
        print(f"  [{i}/{len(track_files)}] {tf.name}: {len(p)} (trip,seg) pairs")
        pairs.append(p)
    pair_df = pd.concat(pairs, ignore_index=True).drop_duplicates()

    merged = pair_df.merge(meta, on="tripid", how="left")
    inter = (merged.groupby(["userid", "lypID", "season"], dropna=False)
             .agg(count=("tripid", "nunique"), first_ts=("first_ts", "min"))
             .reset_index())

    print(f"[result] {len(inter)} (user,seg,season) rows | "
          f"{inter['userid'].nunique()} users | {inter['lypID'].nunique()} segs")
    return inter, pair_df


def cross_check(pair_df: pd.DataFrame) -> None:
    """Compare reconstructed (tripid,lypID) pairs vs the (truncated) old csv."""
    old = _read_csv_any(C.INTERACTION_CSV, usecols=["lypID", "tripid"])
    old_pairs = set(map(tuple, old[["tripid", "lypID"]].dropna().astype("int64").values))
    new_pairs = set(map(tuple, pair_df[["tripid", "lypID"]].dropna().astype("int64").values))
    common_trips = {t for t, _ in old_pairs} & {t for t, _ in new_pairs}
    o = {p for p in old_pairs if p[0] in common_trips}
    n = {p for p in new_pairs if p[0] in common_trips}
    inter = o & n
    print(f"[xcheck] trips in both: {len(common_trips)}")
    print(f"[xcheck] old pairs: {len(o)} | new pairs: {len(n)} | overlap: {len(inter)}")
    if o:
        print(f"[xcheck] recall vs old (overlap/old): {len(inter)/len(o):.3f}")
    if n:
        print(f"[xcheck] precision vs old (overlap/new): {len(inter)/len(n):.3f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true", help="one track file only")
    ap.add_argument("--no-xcheck", action="store_true")
    args = ap.parse_args()

    inter, pair_df = build(pilot=args.pilot)
    if not args.no_xcheck:
        cross_check(pair_df)
    if not args.pilot:
        inter.to_parquet(OUT, index=False)
        print(f"[OK] written {OUT}")
    else:
        print("[pilot] not writing output")
