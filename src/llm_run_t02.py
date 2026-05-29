"""Run the T0.2 protocol against DeepSeek (OpenAI-compatible API).

Reads the key from env DEEPSEEK_API_KEY only — never hardcoded/committed.
Responses are disk-cached (md5 of prompt) so re-runs are free.

Protocol (主文档 6.5 / T0.2):
  - extract a structured profile for N rich-text users (full text)
  - split-half consistency: split each user's text, extract twice, correlate
  - emit 10 samples for the mentor's manual reasonableness scoring

Run:
  DEEPSEEK_API_KEY=... D:/Anaconda/envs/trailforge/python.exe src/llm_run_t02.py --n 25
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

# BLAS calls (np.corrcoef/std) native-crash in this conda env unless MKL is
# sequential. Must precede numpy import. (Same fix as user_features.py.)
os.environ.setdefault("MKL_THREADING_LAYER", "SEQUENTIAL")

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as C  # noqa: E402
from src.llm_profile import SCHEMA, build_prompt, extract  # noqa: E402

USER_TEXT = C.DATA_PROCESSED / "user_text_climbing.parquet"
CACHE = C.DATA_PROCESSED / "llm_cache"
CACHE.mkdir(exist_ok=True)
OUT_JSON = C.DATA_PROCESSED / "t02_profiles.json"
REPORT = C.REPORTS / "T0.2_llm_profile_result.md"

CONT = ["challenge_pref", "nature_pref", "culture_pref", "solo_pref",
        "novelty_pref", "comfort_sens", "regularity", "uncertainty"]
CATEG = ["daypart", "experience_level", "equipment_level"]
SEASON = ["season_spring", "season_summer", "season_autumn", "season_winter"]

API_URL = "https://api.deepseek.com/chat/completions"


def make_call_fn():
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise SystemExit("set DEEPSEEK_API_KEY env var")
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    def call(prompt: str) -> str:
        h = hashlib.md5(prompt.encode()).hexdigest()
        cf = CACHE / f"{h}.txt"
        if cf.exists():
            return cf.read_text(encoding="utf-8")
        body = {"model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3, "stream": False}
        for attempt in range(4):
            try:
                r = requests.post(API_URL, headers=headers, json=body, timeout=90)
                r.raise_for_status()
                txt = r.json()["choices"][0]["message"]["content"]
                cf.write_text(txt, encoding="utf-8")
                return txt
            except Exception as e:  # noqa: BLE001
                if attempt == 3:
                    raise
                time.sleep(2 * (attempt + 1))
    return call


def split_half(text: str, rng):
    lines = [l for l in text.split("\n") if l.strip()]
    idx = rng.permutation(len(lines))
    a = sorted(idx[: len(lines) // 2]); b = sorted(idx[len(lines) // 2:])
    return "\n".join(lines[i] for i in a), "\n".join(lines[i] for i in b)


def vec(profile: dict) -> np.ndarray:
    return np.array([float(profile.get(k, np.nan)) for k in CONT], float)


def run(n: int):
    call = make_call_fn()
    ut = pd.read_parquet(USER_TEXT)
    rich = ut[ut["n_chars"] >= 200].sort_values("n_chars", ascending=False)
    users = rich.head(n)
    rng = np.random.default_rng(42)

    profiles, corrs, cat_agree, season_agree = {}, [], [], []
    for i, (uid, row) in enumerate(users.iterrows(), 1):
        text = row["text"]
        full = extract(text, call)
        ta, tb = split_half(text, rng)
        pa = extract(ta, call) if ta.strip() else full
        pb = extract(tb, call) if tb.strip() else full
        profiles[int(uid)] = {"full": full, "halfA": pa, "halfB": pb,
                              "n_chars": int(row["n_chars"])}
        va, vb = vec(pa), vec(pb)
        ok = ~(np.isnan(va) | np.isnan(vb))
        if ok.sum() >= 2 and np.std(va[ok]) > 0 and np.std(vb[ok]) > 0:
            corrs.append(float(np.corrcoef(va[ok], vb[ok])[0, 1]))
        cat_agree.append(np.mean([pa.get(c) == pb.get(c) for c in CATEG]))
        season_agree.append(np.mean([pa.get(s) == pb.get(s) for s in SEASON]))
        print(f"  [{i}/{len(users)}] uid={uid} done", flush=True)

    OUT_JSON.write_text(json.dumps(profiles, ensure_ascii=False, indent=2), encoding="utf-8")

    # per-continuous-field mean abs error across users
    mae = {}
    for j, k in enumerate(CONT):
        diffs = [abs(float(p["halfA"].get(k, np.nan)) - float(p["halfB"].get(k, np.nan)))
                 for p in profiles.values()]
        diffs = [d for d in diffs if not np.isnan(d)]
        mae[k] = float(np.mean(diffs)) if diffs else float("nan")

    med_corr = float(np.median(corrs)) if corrs else float("nan")
    write_report(profiles, med_corr, corrs, mae, np.mean(cat_agree), np.mean(season_agree))
    print(f"\n[RESULT] users={len(users)} | split-half median corr={med_corr:.3f} "
          f"| categ agree={np.mean(cat_agree):.2f} | season agree={np.mean(season_agree):.2f}")
    print(f"[RESULT] continuous-field MAE: " + ", ".join(f"{k}={v:.2f}" for k, v in mae.items()))
    print(f"[OK] {REPORT.name} + {OUT_JSON.name}")


def write_report(profiles, med_corr, corrs, mae, cat_agree, season_agree):
    L = ["# T0.2 LLM 画像提取实测结果 (DeepSeek)\n"]
    L.append(f"- 样本: **{len(profiles)}** 个 ≥200 字用户 | 模型 deepseek-chat (temp 0.3)")
    L.append(f"- **split-half 一致性中位相关 = {med_corr:.3f}** "
             f"(判断标准: >0.6 通过 / <0.4 失败)")
    L.append(f"- 分类字段(daypart/experience/equipment) 半分一致率 = {cat_agree:.2f}")
    L.append(f"- 季节字段半分一致率 = {season_agree:.2f}\n")
    L.append("## 连续字段半分平均绝对差 (越小越稳)")
    L.append("```\n" + "\n".join(f"{k:16s} {v:.3f}" for k, v in mae.items()) + "\n```")
    L.append("\n## 一致性相关分布")
    if corrs:
        a = np.array(corrs)
        L.append(f"- n={len(a)} mean={a.mean():.3f} median={np.median(a):.3f} "
                 f"min={a.min():.3f} max={a.max():.3f}")
    L.append("\n## 合理性人工评分样本 (导师 5 分制填写)\n")
    for uid, p in list(profiles.items())[:10]:
        L.append(f"### user {uid} ({p['n_chars']} 字)")
        L.append("```json\n" + json.dumps(p["full"], ensure_ascii=False) + "\n```")
        L.append("合理性评分(1-5): ____\n")
    L.append("\n## 结论(待导师确认)")
    verdict = ("通过" if med_corr > 0.6 else "有限通过" if med_corr > 0.4 else "失败")
    L.append(f"- 一致性初判: **{verdict}** (中位相关 {med_corr:.3f})。"
             "若通过→批量提取并入 u_LLM(T2.2)；若失败→仅用 u_cluster+onboarding。")
    REPORT.write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=25)
    args = ap.parse_args()
    run(args.n)
