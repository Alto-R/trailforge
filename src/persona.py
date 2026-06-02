"""板块B：onboarding personas + cold-user representation.

A brand-new user has no trip history, so we cannot compute the 14-dim behavioural
meta-features the GMM was trained on. Instead the user picks one of the K=5 GMM
profile groups (presented as an interpretable *persona*). The chosen cluster
becomes the one-hot ``u_cluster`` block of the content-tower input ``u_feat``;
the ``llm_*`` block is filled with the training cold-user value (column mean) and
``has_llm_profile`` = 0 — identical to user_repr.py's cold encoding, so the input
stays in-distribution.

Two halves:
  build_catalog()         profile the 5 clusters from user_features_climbing +
                          user_cluster_soft, auto-draft a Chinese label +
                          description from each cluster's most distinguishing
                          features. Cached to data_processed/personas.json so a
                          human can refine labels and the edits persist.
  persona_u_feat(cluster, meta)
                          build the 24-dim u_feat (ordered by meta["u_cols"]).

Run:  PYTHONNOUSERSITE=1 D:/Anaconda/envs/trailforge/python.exe src/persona.py [--rebuild]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as C  # noqa: E402

USER_FEATS = C.DATA_PROCESSED / "user_features_climbing.parquet"
GMM_ASSIGN = C.DATA_PROCESSED / "user_cluster_soft.parquet"
INTER = C.DATA_PROCESSED / "interactions_climbing.parquet"
SEG_FEATS = C.DATA_PROCESSED / "segment_features_climbing.parquet"
PERSONAS = C.DATA_PROCESSED / "personas.json"

# the 5 content preferences -> the raw segment column each rewards
# (keep in sync with route_generator.PREF_MAP)
PREF_MAP = {
    "challenge": "geo_slope_mean",
    "nature": "geo_scene_natural",
    "culture": "geo_scene_manmade",
    "popularity": "beh_traffic_total",
    "scenic": "vis_photo_count",
}

# the 14 behavioural meta-features (== user_features.py feat_cols, sans n_trips),
# each mapped to a (high, low) Chinese phrase for auto-drafting persona labels.
FEATURE_PHRASES = {
    "freq_per_month": ("高频出行", "偶尔出行"),
    "seasonality_spring": ("偏好春季", "少在春季"),
    "seasonality_summer": ("偏好夏季", "少在夏季"),
    "weekend_ratio": ("周末为主", "工作日也常出行"),
    "gap_cv": ("节奏不规律", "节奏规律"),
    "dist_mean": ("长距离", "短途"),
    "dist_cv": ("距离跨度大", "距离稳定"),
    "duration_mean": ("耗时长·常全天", "短时"),
    "duration_cv": ("时长跨度大", "时长稳定"),
    "activity_radius": ("活动范围大", "活动范围小"),
    "start_compactness": ("起点集中", "起点分散"),
    "coverage_breadth": ("足迹广·爱探索", "足迹集中"),
    "season_entropy": ("全年均衡", "集中某季"),
    "daypart_entropy": ("出发时段多样", "出发时段固定"),
}


def _phrase(feat: str, z: float) -> str:
    hi, lo = FEATURE_PHRASES[feat]
    return hi if z >= 0 else lo


def _cluster_default_prefs() -> dict[int, dict]:
    """Data-driven default preference weights per cluster: the z-scored mean
    profile of the 5 PREF attributes over segments that cluster's users visited,
    taken RELATIVE to the cross-cluster mean (so each persona's *distinctive*
    leanings show), relu'd + floored + normalised to sum 1.

    Differentiation is modest (clusters mostly differ in popularity); the user's
    sliders are the dominant personalization driver (design R1.2)."""
    inter = pd.read_parquet(INTER)
    soft = pd.read_parquet(GMM_ASSIGN)[["hard"]]
    seg = pd.read_parquet(SEG_FEATS)
    cols = list(PREF_MAP.values())
    segz = (seg[cols] - seg[cols].mean()) / seg[cols].std().replace(0, 1.0)
    iu = inter.merge(soft, left_on="userid", right_index=True, how="inner") \
              .merge(segz, left_on="lypID", right_index=True, how="inner")
    for c in cols:
        iu[c] = iu[c] * iu["count"]
    prof = iu.groupby("hard").apply(
        lambda g: pd.Series({c: g[c].sum() / g["count"].sum() for c in cols}),
        include_groups=False)
    prof.columns = list(PREF_MAP)                    # pref keys
    dev = (prof - prof.mean(axis=0)).clip(lower=0) + 0.1   # distinctive + floor
    w = dev.div(dev.sum(axis=1), axis=0)             # rows sum to 1
    return {int(k): {p: round(float(w.loc[k, p]), 3) for p in PREF_MAP}
            for k in w.index}


def build_catalog(top_k: int = 3) -> list[dict]:
    """Profile the K clusters and draft a persona per cluster. Pure function of
    the clustering artifacts; does NOT touch the torch model."""
    feats = pd.read_parquet(USER_FEATS)
    assign = pd.read_parquet(GMM_ASSIGN)
    feat_cols = [c for c in FEATURE_PHRASES if c in feats.columns]
    hard = assign["hard"]
    X = feats[feat_cols]
    pop_mean, pop_std = X.mean(), X.std().replace(0, 1.0)
    default_prefs = _cluster_default_prefs()

    n_clusters = int(hard.max()) + 1
    catalog = []
    for k in range(n_clusters):
        members = X[hard == k]
        size = int((hard == k).sum())
        if size == 0:
            continue
        z = (members.mean() - pop_mean) / pop_std        # standardized signature
        top = z.reindex(z.abs().sort_values(ascending=False).index)[:top_k]
        phrases = [_phrase(f, top[f]) for f in top.index]
        signature = {f: {"z": round(float(z[f]), 2),
                         "mean": round(float(members[f].mean()), 2)}
                     for f in top.index}
        catalog.append({
            "id": f"c{k}",
            "cluster": k,
            "label": "·".join(phrases[:2]),          # short draft name (refine me)
            "description": "；".join(phrases),         # 3 traits
            "size": size,
            "default_prefs": default_prefs.get(k, {p: 0.2 for p in PREF_MAP}),
            "signature": signature,
        })
    return catalog


def personas(rebuild: bool = False) -> list[dict]:
    """Return the persona catalog. Loads the cached (human-editable) personas.json
    if present; otherwise builds, caches, and returns it. ``rebuild=True`` forces
    regeneration (overwrites manual label edits)."""
    if PERSONAS.exists() and not rebuild:
        return json.loads(PERSONAS.read_text(encoding="utf-8"))
    cat = build_catalog()
    PERSONAS.write_text(json.dumps(cat, ensure_ascii=False, indent=2), encoding="utf-8")
    return cat


def _cluster_of(persona_id: str, catalog: list[dict]) -> int:
    for p in catalog:
        if p["id"] == persona_id:
            return p["cluster"]
    raise KeyError(f"unknown persona id {persona_id!r}; "
                   f"have {[p['id'] for p in catalog]}")


def default_prefs_of(persona_id: str, catalog: list[dict] | None = None) -> dict:
    """The data-derived default preference weights for a persona (R1.2)."""
    catalog = catalog if catalog is not None else personas()
    for p in catalog:
        if p["id"] == persona_id:
            return dict(p.get("default_prefs", {k: 0.2 for k in PREF_MAP}))
    raise KeyError(f"unknown persona id {persona_id!r}; "
                   f"have {[p['id'] for p in catalog]}")


def persona_u_feat(persona_id: str, meta: dict,
                   catalog: list[dict] | None = None) -> np.ndarray:
    """Build the 24-dim cold-user u_feat for a chosen persona, ordered by
    meta["u_cols"]: chosen cluster one-hot + llm column means + flag 0."""
    catalog = catalog if catalog is not None else personas()
    k = _cluster_of(persona_id, catalog)
    u_cols = meta["u_cols"]
    cluster_cols = meta["cluster_cols"]
    llm_means = meta["llm_means"]
    flag_col = meta["flag_col"]
    target_col = f"u_cluster_{k}"
    if target_col not in cluster_cols:
        raise KeyError(f"{target_col} not in meta cluster_cols {cluster_cols}")

    values = {c: 0.0 for c in u_cols}
    values[target_col] = 1.0                              # one-hot persona cluster
    for c, m in llm_means.items():
        values[c] = float(m)                             # cold llm = training mean
    values[flag_col] = 0.0                               # no LLM profile
    return np.array([values[c] for c in u_cols], dtype=np.float32)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true",
                    help="regenerate personas.json from clustering (overwrites label edits)")
    args = ap.parse_args()
    cat = personas(rebuild=args.rebuild)
    print(f"[OK] {len(cat)} personas -> {PERSONAS.name}")
    for p in cat:
        print(f"  {p['id']} (n={p['size']:3d}) {p['label']}")
        print(f"      {p['description']}")
        print(f"      signature: {p['signature']}")
