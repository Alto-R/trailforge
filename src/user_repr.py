"""T2.3(user) assemble the user representation  u = [u_cluster; u_LLM].

For now u_LLM is absent (T0.2 pending an LLM endpoint), so u = u_cluster, the
GMM soft-assignment over the K=5 profile groups (档案A → D0.3). A has_llm_profile
flag is reserved so the column layout is stable when u_LLM is added later.

Only users with >= MIN_TRIPS climbing trips have a cluster vector (603 users);
they are the population for the CF content-tower experiment. Cold users (onboarding)
are out of scope for the offline experiment.

``load_user_matrix()`` returns (DataFrame indexed by userid, feature_cols).

Run:  D:/Anaconda/envs/trailforge/python.exe src/user_repr.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as C  # noqa: E402

SOFT = C.DATA_PROCESSED / "user_cluster_soft.parquet"
LLM = C.DATA_PROCESSED / "user_llm_profile.parquet"
OUT = C.DATA_PROCESSED / "user_features_repr.parquet"


def assemble() -> pd.DataFrame:
    soft = pd.read_parquet(SOFT)
    pcols = [c for c in soft.columns if c.startswith("p") and c[1:].isdigit()]
    u = soft[pcols].copy()
    u.columns = [f"u_cluster_{c[1:]}" for c in pcols]

    # u_LLM (T2.2): merge if available; cold users -> column mean + flag 0
    if LLM.exists():
        llm = pd.read_parquet(LLM)
        u = u.join(llm, how="left")
        llm_cols = list(llm.columns)
        u["has_llm_profile"] = u[llm_cols[0]].notna().astype(int)
        u[llm_cols] = u[llm_cols].fillna(u[llm_cols].mean())
    else:
        u["has_llm_profile"] = 0      # reserved until extraction is run
    u.index.name = "userid"
    return u


def load_user_matrix() -> tuple[pd.DataFrame, list[str]]:
    u = pd.read_parquet(OUT)
    feat_cols = [c for c in u.columns if c.startswith("u_")]
    return u, feat_cols


if __name__ == "__main__":
    u = assemble()
    u.to_parquet(OUT)
    print(f"[OK] {OUT.name}  shape={u.shape}")
    print(f"  users={len(u)}  u_cluster dims={sum(c.startswith('u_cluster') for c in u.columns)}")
    print(u.head().round(3).to_string())
