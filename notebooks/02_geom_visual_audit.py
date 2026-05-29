"""D0 audit: geometry source verification (risk ③) + 彭晓 visual coverage (T0.3').

Run:  D:/Anaconda/envs/trailforge/python.exe notebooks/02_geom_visual_audit.py

Outputs a short report to stdout (and reports/D0.4_geom_visual_audit.md is written
by a later step once findings are confirmed).
"""
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C

CENTERLINE_DIR = C.CENTERLINE_DIR
FIX3 = CENTERLINE_DIR / "bj_clim_50m_line_fix3.shp"


def audit_geometry():
    print("=" * 60)
    print("① 几何基准源核验")
    print("=" * 60)
    for name, p in {"demo_AllMessage": C.CLIM_SPRING_SEG, "fix3": FIX3}.items():
        print(f"\n[{name}] exists={p.exists()}  path={p}")
        if not p.exists():
            continue
        g = gpd.read_file(p)
        print(f"  n_features = {len(g)}")
        print(f"  crs        = {str(g.crs)[:60]}")
        print(f"  geom_types = {g.geom_type.value_counts().to_dict()}")
        print(f"  n_columns  = {len(g.columns)}")
        print(f"  columns    = {list(g.columns)}")


def audit_pengxiao():
    print("\n" + "=" * 60)
    print("② T0.3' 彭晓视觉标签覆盖度")
    print("=" * 60)
    pts = gpd.read_file(C.PENGXIAO_SHP)
    print(f"  n_points = {len(pts)}  crs={pts.crs}")
    for col in ["main_cla", "med_cla", "fine_cla"]:
        vc = pts[col].value_counts(dropna=False)
        print(f"\n  [{col}] n_unique={pts[col].nunique(dropna=True)}  top15:")
        print(vc.head(15).to_string())
    if "year" in pts.columns:
        print("\n  [year] distribution:")
        print(pts["year"].value_counts(dropna=False).sort_index().to_string())


if __name__ == "__main__":
    audit_geometry()
    audit_pengxiao()
