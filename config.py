"""Central configuration for the trailforge project.

All raw data lives on the G: drive (read-only source of truth). Processed
artifacts are written under data_processed/ inside this repo.
"""
import os
from pathlib import Path

# --- repo layout -----------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent


def _load_dotenv() -> None:
    """Minimal .env loader (no python-dotenv dep). Reads KEY=VALUE lines from
    REPO_ROOT/.env into os.environ without overriding existing vars. .env is
    gitignored (holds secrets like DEEPSEEK_API_KEY)."""
    env = REPO_ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()
DATA_PROCESSED = REPO_ROOT / "data_processed"
REPORTS = REPO_ROOT / "reports"
DATA_PROCESSED.mkdir(exist_ok=True)
REPORTS.mkdir(exist_ok=True)

# --- raw data root (G: drive) ---------------------------------------------
G_ROOT = Path(r"G:/游憩线路生成")

RAW = G_ROOT / "1.sixfoot全部相关数据"
CODE = G_ROOT / "2.相关代码及说明"
OTHER = G_ROOT / "3.其他数据"

# 六只脚 raw data (initial backup, no projection assigned yet)
SIXFOOT_RAW = RAW / "六只脚基本数据" / "【六只脚初始数据备份】（未给投影）"
SIXFOOT_PROCESSED = RAW / "六只脚基本数据" / "处理过的六只脚数据（可能不完整，供参考，建议直接处理初始数据）"

# Base (un-split) extracted centerlines
CENTERLINE_DIR = SIXFOOT_PROCESSED / "线数据" / "北京地区的处理数据" / "轨迹中心线提取"
CLIM_CENTERLINE = CENTERLINE_DIR / "bj_clim_centerline.shp"       # climbing, un-split
HIKING_CENTERLINE = CENTERLINE_DIR / "bj_hiking_centerline.shp"   # hiking, un-split

# 邓钰桥 demo: climbing-spring, 50m split, with continuous attributes
DEMO_DIR = CODE / "线路推荐demo(邓钰桥)"
CLIM_SPRING_SEG = DEMO_DIR / "data" / "clim_春_centerline_50m_line_fix_AllMessage.shp"
CLIM_SPRING_XLS = DEMO_DIR / "data" / "北京登山中心线_春.xls"
INTERACTION_CSV = DEMO_DIR / "data" / "lypid_userid_tripid.csv"   # likely Excel-truncated
DEMO_SCRIPT = DEMO_DIR / "线路推荐_demo_邓钰桥.py"

# 邓钰桥 TRDA growth algorithm (李羿蒲 thesis algorithm), seasonal variants
TRDA_DIR = CODE / "轨迹生长算法(邓钰桥)"

# 胡宝生 cleaning + trip-type classification
CLEAN_DIR = CODE / "轨迹数据清洗代码及说明(胡宝生)"
TRIPTYPE_DIR = CLEAN_DIR / "轨迹数据分类(可能不完整，需核验)"
CLIMBING_TRIPS_CSV = TRIPTYPE_DIR / "climbing_all.csv"           # tripid -> triptype

# 六只脚 crawler (schema reference; check for downloaded photos)
CRAWLER_DIR = CODE / "六只脚爬虫(胡宝生)"

# 彭晓 image deep-learning results (point shapefile)
PENGXIAO_SHP = RAW / "图片深度学习成果数据-京津冀（彭晓）" / "lzj_bj_youxiao" / "lzj_youxiao.shp"

# 高德 POI (file geodatabase, classified by type)
GAODE_POI_GDB = OTHER / "高德POI-京津冀" / "京津冀merge_poi_分类型.gdb"

# --- analysis constants ----------------------------------------------------
# CRS decision pending (D0.1): Albers (matches G:'s *_albers files) vs UTM 50N.
CRS_WGS84 = "EPSG:4326"
CRS_UTM50N = "EPSG:32650"

SEASONS = {  # month -> season label, matching 邓钰桥 seasonal naming (春/夏/秋/冬)
    "春": (3, 4, 5),
    "夏": (6, 7, 8),
    "秋": (9, 10, 11),
    "冬": (12, 1, 2),
}
