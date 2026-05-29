"""T2.2 batch LLM profile extraction -> numeric u_LLM for all text users.

Extracts a structured profile (cached) for every user with >= MIN_CHARS text,
then maps the 18 schema fields to an 18-dim numeric u_LLM vector:
  8 continuous + 4 season binary + 4 daypart one-hot + experience + equipment.

Output: data_processed/user_llm_profile.parquet  (userid -> llm_* columns)

Run:  D:/Anaconda/envs/trailforge/python.exe src/llm_extract_all.py
(key auto-loaded from .env via config)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("MKL_THREADING_LAYER", "SEQUENTIAL")
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as C  # noqa: E402  (loads .env)
from src.llm_profile import extract  # noqa: E402
from src.llm_run_t02 import make_call_fn, CONT, SEASON  # noqa: E402

USER_TEXT = C.DATA_PROCESSED / "user_text_climbing.parquet"
OUT = C.DATA_PROCESSED / "user_llm_profile.parquet"
MIN_CHARS = 50
DAYPARTS = ["early", "day", "late", "night"]
EXP = {"novice": 0.0, "intermediate": 0.5, "advanced": 1.0}
EQUIP = {"light": 0.0, "standard": 0.5, "professional": 1.0}


def _f01(v) -> float:
    try:
        return min(1.0, max(0.0, float(v)))
    except (TypeError, ValueError):
        return 0.5


def to_vec(p: dict) -> dict:
    out = {f"llm_{k}": _f01(p.get(k)) for k in CONT}
    for s in SEASON:
        out[f"llm_{s}"] = 1.0 if str(p.get(s)) in ("1", "1.0", "True") else 0.0
    dp = str(p.get("daypart", "")).lower()
    for d in DAYPARTS:
        out[f"llm_daypart_{d}"] = 1.0 if dp == d else 0.0
    out["llm_experience"] = EXP.get(str(p.get("experience_level", "")).lower(), 0.5)
    out["llm_equipment"] = EQUIP.get(str(p.get("equipment_level", "")).lower(), 0.5)
    return out


def build() -> pd.DataFrame:
    call = make_call_fn()
    ut = pd.read_parquet(USER_TEXT)
    users = ut[ut["n_chars"] >= MIN_CHARS]
    print(f"[extract] {len(users)} users with >= {MIN_CHARS} chars", flush=True)
    rows, fail = {}, 0
    for i, (uid, row) in enumerate(users.iterrows(), 1):
        try:
            prof = extract(row["text"], call)
            rows[int(uid)] = to_vec(prof)
        except Exception as e:  # noqa: BLE001
            fail += 1
            if fail <= 5:
                print(f"  fail uid={uid}: {type(e).__name__}", flush=True)
        if i % 50 == 0:
            print(f"  [{i}/{len(users)}] ok={len(rows)} fail={fail}", flush=True)
    df = pd.DataFrame.from_dict(rows, orient="index")
    df.index.name = "userid"
    print(f"[extract] done: {len(df)} profiles, {fail} failures, dims={df.shape[1]}")
    return df


if __name__ == "__main__":
    df = build()
    df.to_parquet(OUT)
    print(f"[OK] {OUT.name} shape={df.shape}")
    print(df.describe().round(2).T[["mean", "std", "min", "max"]].to_string())
