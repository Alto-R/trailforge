"""Explainable route labels (主计划 §5.4.6).

For the MVP the explanation is data-only: surface the 1-3 segment attributes a
route is most ABOVE the network average on, as short Chinese phrases. This gives
the user a quick "why this route" without exposing model internals.
"""
from __future__ import annotations

import pandas as pd

# the 5 interpretable attributes (== PREF_MAP targets) -> a display phrase
ATTR_PHRASES = {
    "geo_slope_mean": "坡陡·有挑战",
    "geo_scene_natural": "自然野趣",
    "geo_scene_manmade": "人文古迹",
    "beh_traffic_total": "热门成熟",
    "vis_photo_count": "风景打卡多",
}


def attr_stats(raw_feat: pd.DataFrame) -> dict:
    """Network-wide mean/std for the explainable attributes (computed once)."""
    cols = [c for c in ATTR_PHRASES if c in raw_feat.columns]
    mean = raw_feat[cols].mean()
    std = raw_feat[cols].replace([float("inf")], 0).std().replace(0, 1.0)
    return {"cols": cols, "mean": mean.to_dict(), "std": std.to_dict()}


def route_attrs(segments: list[int], raw_feat: pd.DataFrame, cols: list[str]) -> dict:
    rows = raw_feat.reindex(segments)
    return {c: round(float(rows[c].mean()), 3) for c in cols if c in rows.columns}


def label_route(mean_attrs: dict, stats: dict, top_k: int = 2,
                z_thresh: float = 0.15) -> list[str]:
    """Phrases for the attributes this route is most above-average on."""
    z = {a: (mean_attrs[a] - stats["mean"][a]) / stats["std"][a]
         for a in ATTR_PHRASES if a in mean_attrs and a in stats["mean"]}
    top = sorted(z, key=lambda a: z[a], reverse=True)[:top_k]
    labels = [ATTR_PHRASES[a] for a in top if z[a] > z_thresh]
    return labels or ["均衡常规"]
