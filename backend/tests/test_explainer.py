"""Explainer label unit tests (fast, no model)."""
from __future__ import annotations

import pandas as pd

from src import explainer


def _stats():
    raw = pd.DataFrame({
        "geo_slope_mean": [0.0, 1.0, 2.0],
        "geo_scene_natural": [0.0, 1.0, 2.0],
        "geo_scene_manmade": [0.0, 1.0, 2.0],
        "beh_traffic_total": [0.0, 1.0, 2.0],
        "vis_photo_count": [0.0, 1.0, 2.0],
    }, index=[1, 2, 3])
    return raw, explainer.attr_stats(raw)


def test_label_surfaces_above_average():
    raw, stats = _stats()
    high_slope = {"geo_slope_mean": 5.0, "geo_scene_natural": 1.0,
                  "geo_scene_manmade": 1.0, "beh_traffic_total": 1.0,
                  "vis_photo_count": 1.0}
    labels = explainer.label_route(high_slope, stats, top_k=1)
    assert labels == [explainer.ATTR_PHRASES["geo_slope_mean"]]


def test_label_falls_back_when_unremarkable():
    raw, stats = _stats()
    avg = {c: float(raw[c].mean()) for c in stats["cols"]}
    assert explainer.label_route(avg, stats) == ["均衡常规"]


def test_route_attrs():
    raw, stats = _stats()
    attrs = explainer.route_attrs([1, 3], raw, stats["cols"])
    assert attrs["geo_slope_mean"] == 1.0           # mean of 0 and 2
