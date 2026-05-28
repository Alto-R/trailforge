"""D0.2 summary: distributions + report for the interaction matrix.

Report (text) is written first so a matplotlib hiccup can't lose it; figures
are attempted last and are non-essential.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as C

import pandas as pd

N_SEGS_TOTAL = 29941
XCHECK = dict(common_trips=3882, recall=0.972, precision=0.900)  # from full build log

print("reading parquet...", flush=True)
df = pd.read_parquet(C.DATA_PROCESSED / "interactions_climbing.parquet")
print(f"rows={len(df):,}", flush=True)

segs_per_user = df.groupby("userid")["lypID"].nunique()
users_per_seg = df.groupby("lypID")["userid"].nunique()
season_tot = df.groupby("season", dropna=False)["count"].sum()
season_users = df.groupby("season", dropna=False)["userid"].nunique()

L = []
L.append("# D0.2 登山全季节交互矩阵报告\n")
L.append("- 输出: `data_processed/interactions_climbing.parquet`")
L.append(f"- 列: {list(df.columns)}")
L.append(f"- **{len(df):,}** (user,seg,season) 行 | **{df.userid.nunique():,}** 用户 | "
         f"**{df.lypID.nunique():,}** 段 | 交互次数合计 **{int(df['count'].sum()):,}**")
L.append(f"- 片段覆盖率: {df.lypID.nunique()}/{N_SEGS_TOTAL} = {df.lypID.nunique()/N_SEGS_TOTAL:.1%}\n")
L.append("## 与旧 csv 交叉校验（全量）")
L.append(f"- 共同行程 {XCHECK['common_trips']}，**recall {XCHECK['recall']}** / precision {XCHECK['precision']}")
L.append("- 旧 csv 因 Excel 截断仅 2832 用户/6458 行程；本重建 3630 用户，更完整。\n")
L.append("## 每用户访问的不同片段数")
L.append("```\n" + segs_per_user.describe(percentiles=[.25, .5, .75, .9, .95]).to_string() + "\n```")
L.append("## 每片段被访问的不同用户数")
L.append("```\n" + users_per_seg.describe(percentiles=[.25, .5, .75, .9, .95]).to_string() + "\n```")
L.append("## 分季节")
L.append("```\n" + pd.DataFrame({"interactions": season_tot, "users": season_users}).to_string() + "\n```")
L.append("\n## 已知 caveat")
L.append("- 部分 tripid 区段(300k–500k、630k–700k、750k、850k–864k、950k)的 track 文件产出 0 对，"
         "疑为该区段非北京登山为主或抓取批次差异；recall 0.972 表明已覆盖行程的归属准确，"
         "但**总行程完整性需后续核验**。")
L.append("- train/test 80/20 时间划分留待 CF 训练(Phase 2)前再做。")

out = C.REPORTS / "D0.2_interaction_matrix.md"
out.write_text("\n".join(L), encoding="utf-8")
print(f"[OK] report written: {out.name}", flush=True)
print("segs_per_user median/mean:", int(segs_per_user.median()), round(segs_per_user.mean(), 1), flush=True)
print("users_per_seg median/mean:", int(users_per_seg.median()), round(users_per_seg.mean(), 1), flush=True)
