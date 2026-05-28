"""D0.1 data inventory & verification.

Read-only audit of the G: drive assets. Writes a markdown report to
reports/data_inventory.md and prints a short summary. Each check is isolated
so one failure does not abort the rest.

Run:  conda activate trailforge && python notebooks/00_data_audit.py
"""
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as C  # noqa: E402

import pandas as pd  # noqa: E402
import geopandas as gpd  # noqa: E402
import fiona  # noqa: E402

lines: list[str] = ["# D0.1 数据清点与核验报告", ""]


def section(title: str):
    lines.append("")
    lines.append(f"## {title}")


def kv(k, v):
    lines.append(f"- **{k}**: {v}")


def guard(fn):
    try:
        fn()
    except Exception as e:  # noqa: BLE001
        lines.append(f"- ❌ ERROR: `{e}`")
        lines.append("```")
        lines.append(traceback.format_exc().strip())
        lines.append("```")


# 1) climbing-spring 50m segments (the demo's processed centerline) ----------
section("1. 登山-春 50m 中心线（邓钰桥 demo）")


def _seg():
    kv("path", C.CLIM_SPRING_SEG)
    kv("exists", C.CLIM_SPRING_SEG.exists())
    if C.CLIM_SPRING_SEG.exists():
        seg = gpd.read_file(C.CLIM_SPRING_SEG)
        kv("crs", seg.crs)
        kv("n_segments", len(seg))
        kv("columns", list(seg.columns))
        kv("geom_types", seg.geom_type.value_counts().to_dict())


guard(_seg)


# 2) interaction csv truncation check ---------------------------------------
section("2. 交互链 lypid_userid_tripid.csv（截断核实）")


def _link():
    kv("path", C.INTERACTION_CSV)
    link = pd.read_csv(C.INTERACTION_CSV)
    n = len(link)
    kv("n_rows", f"{n:,}")
    kv("== 1,048,576 (Excel 上限)?", n == 1048576)
    kv("columns", list(link.columns))
    for col in ("userid", "tripid", "lypID"):
        if col in link.columns:
            kv(f"n_unique_{col}", f"{link[col].nunique():,}")
    lines.append("- tail (看 tripid 是否在尾部突然中断):")
    lines.append("```")
    lines.append(link.tail(8).to_string())
    lines.append("```")


guard(_link)


# 3) climbing-spring attribute table (xls) ----------------------------------
section("3. 登山-春属性表 北京登山中心线_春.xls")


def _xls():
    kv("path", C.CLIM_SPRING_XLS)
    df = pd.read_excel(C.CLIM_SPRING_XLS)
    kv("shape", df.shape)
    kv("columns", list(df.columns))
    lines.append("```")
    lines.append(df.describe(include="all").to_string())
    lines.append("```")


guard(_xls)


# 4) base un-split centerlines ----------------------------------------------
section("4. 基础中心线（未切 50m）：登山 / 徒步")


def _base():
    for label, p in (("climbing", C.CLIM_CENTERLINE), ("hiking", C.HIKING_CENTERLINE)):
        kv(f"{label} exists", f"{p.exists()}  ({p.name})")
        if p.exists():
            g = gpd.read_file(p)
            kv(f"{label} crs / n / cols", f"{g.crs} / {len(g)} / {list(g.columns)}")


guard(_base)


# 5) seasonal 50m split availability (夏/秋/冬) ------------------------------
section("5. 登山 夏/秋/冬 的 50m 切片 + 属性是否存在")


def _seasonal():
    hits = []
    for pat in ("*50m*.shp", "*夏*.shp", "*秋*.shp", "*冬*.shp", "*夏*.xls*", "*秋*.xls*", "*冬*.xls*"):
        for d in (C.DEMO_DIR, C.CENTERLINE_DIR, C.TRDA_DIR):
            hits += [str(x) for x in d.rglob(pat)]
    hits = sorted(set(hits))
    kv("found seasonal/50m files", len(hits))
    for h in hits[:40]:
        lines.append(f"  - {h}")
    if not hits:
        lines.append("  - ⚠️ 未找到夏/秋/冬 50m 切片或属性表 → 需重生成（用 TRDA 季节脚本）")


guard(_seasonal)


# 6) 彭晓 image deep-learning results ----------------------------------------
section("6. 彭晓 图片深度学习成果 lzj_youxiao.shp")


def _pengxiao():
    kv("path", C.PENGXIAO_SHP)
    kv("exists", C.PENGXIAO_SHP.exists())
    if C.PENGXIAO_SHP.exists():
        g = gpd.read_file(C.PENGXIAO_SHP)
        kv("crs", g.crs)
        kv("n_points", len(g))
        kv("columns", list(g.columns))
        lines.append("- head:")
        lines.append("```")
        lines.append(g.drop(columns=g.geometry.name).head(5).to_string())
        lines.append("```")


guard(_pengxiao)


# 7) 高德 POI gdb layers -----------------------------------------------------
section("7. 高德 POI 地理数据库 (.gdb)")


def _poi():
    kv("path", C.GAODE_POI_GDB)
    kv("exists", C.GAODE_POI_GDB.exists())
    if C.GAODE_POI_GDB.exists():
        layers = fiona.listlayers(str(C.GAODE_POI_GDB))
        kv("n_layers", len(layers))
        kv("layers", layers)


guard(_poi)


# 8) raw 六只脚 track/footprints/basic sample --------------------------------
section("8. 原始六只脚 track / footprints / basic 抽样")


def _raw():
    kv("SIXFOOT_RAW exists", C.SIXFOOT_RAW.exists())
    if not C.SIXFOOT_RAW.exists():
        return
    tracks = list(C.SIXFOOT_RAW.rglob("track*.shp"))[:3]
    foots = list(C.SIXFOOT_RAW.rglob("footprints*.shp"))[:3]
    basics = list(C.SIXFOOT_RAW.rglob("basic*.xlsx"))[:3]
    kv("#track shp (sample)", f"{len(list(C.SIXFOOT_RAW.rglob('track*.shp')))} found")
    kv("#footprints shp", f"{len(list(C.SIXFOOT_RAW.rglob('footprints*.shp')))} found")
    kv("#basic xlsx", f"{len(list(C.SIXFOOT_RAW.rglob('basic*.xlsx')))} found")
    if tracks:
        g = gpd.read_file(tracks[0], rows=5)
        kv("track sample", tracks[0].name)
        kv("track crs / cols", f"{g.crs} / {list(g.columns)}")
    if foots:
        g = gpd.read_file(foots[0], rows=5)
        kv("footprints sample", foots[0].name)
        kv("footprints cols", list(g.columns))
    if basics:
        df = pd.read_excel(basics[0], nrows=5)
        kv("basic sample", basics[0].name)
        kv("basic cols", list(df.columns))


guard(_raw)


# 9) downloaded photos on disk? ---------------------------------------------
section("9. 原始照片是否已下载到本地")


def _photos():
    exts = (".jpg", ".jpeg", ".png")
    found = []
    for root in (C.RAW, C.CODE):
        for p in root.rglob("*"):
            if p.suffix.lower() in exts:
                found.append(str(p))
                if len(found) >= 5:
                    break
        if len(found) >= 5:
            break
    if found:
        kv("photos found (sample)", "")
        for f in found:
            lines.append(f"  - {f}")
        lines.append("  - ⚠️ 仅为是否存在的抽样，未统计总量")
    else:
        kv("photos found", "❌ 未发现本地图片文件 → CLIP 路线需先用 crawler/download.py 下载，或改用彭晓成果")


guard(_photos)


# write report ---------------------------------------------------------------
out = C.REPORTS / "data_inventory.md"
out.write_text("\n".join(str(x) for x in lines), encoding="utf-8")
print(f"[OK] report written: {out}")
print(f"[OK] {sum(1 for x in lines if str(x).startswith('## '))} sections audited")
