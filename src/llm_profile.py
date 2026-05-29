"""T0.2 LLM user-profile extraction harness (u_LLM).

Extracts a structured preference vector from a user's free-text trip titles +
descriptions, per 主文档 §5.1.3. The LLM call is abstracted behind a pluggable
``call_fn(prompt) -> str`` so this runs against any provider (Anthropic / OpenAI
/ local transformers) the moment one is available — none is wired yet.

Runnable WITHOUT an LLM:
  - build_user_text(): aggregate per-user climbing text (data-readiness check)
  - build_prompt(): the exact prompt that would be sent

T0.2 protocol (needs call_fn):
  - extract() each of ~20-30 users
  - consistency: split each user's text in half, extract twice, correlate
  - reasonableness: mentor scores 10 samples on a 5-pt scale (manual)

Run:  D:/Anaconda/envs/trailforge/python.exe src/llm_profile.py   # text readiness
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as C  # noqa: E402

USER_TEXT = C.DATA_PROCESSED / "user_text_climbing.parquet"
MAX_CHARS = 6000           # truncate very prolific users

# --- schema (主文档 §5.1.3): ~18 dims -------------------------------------
SCHEMA = {
    "challenge_pref": "0-1 偏好挑战(难/累/险/陡且正面情绪)",
    "nature_pref": "0-1 自然景观偏好(山/水/林/花)",
    "culture_pref": "0-1 人文景观偏好(古迹/寺庙/村落)",
    "solo_pref": "0-1 独行偏好(我 vs 我们)",
    "novelty_pref": "0-1 新奇偏好(第一次/新发现)",
    "comfort_sens": "0-1 舒适度敏感(对天气/装备/设施的负面描述)",
    "season_spring": "0/1 偏好春", "season_summer": "0/1 偏好夏",
    "season_autumn": "0/1 偏好秋", "season_winter": "0/1 偏好冬",
    "daypart": "枚举 early/day/late/night 偏好时段",
    "experience_level": "枚举 novice/intermediate/advanced",
    "equipment_level": "枚举 light/standard/professional",
    "regularity": "0-1 出行规律性",
    "uncertainty": "0-1 你对本次判断的不确定度(文本越少越高)",
}

# 户外黑话词典 (主文档 §4.1) — 帮助 LLM 不把关键词当噪声
TERM_GLOSSARY = {
    "穿越": "跨越山岭的长距离徒步(挑战性强)", "重装": "背全套露营装备(强度高)",
    "轻装": "仅当日装备", "拉练/虐": "高强度体能训练式出行(挑战偏好)",
    "FB": "腐败=轻松休闲吃喝", "AA": "费用均摊(小队社交)",
    "刷山": "反复爬同一座山(低新奇)", "驴友": "户外爱好者",
}

FEWSHOT = [
    {"text": "周末重装穿越箭扣到慕田峪，云海太美了，虽然很虐但值了！",
     "json": {"challenge_pref": 0.9, "nature_pref": 0.9, "culture_pref": 0.3,
              "solo_pref": 0.3, "novelty_pref": 0.5, "comfort_sens": 0.2,
              "season_spring": 0, "season_summer": 1, "season_autumn": 0,
              "season_winter": 0, "daypart": "day", "experience_level": "advanced",
              "equipment_level": "professional", "regularity": 0.7, "uncertainty": 0.2}},
    {"text": "今天带家人去香山走走，台阶修得不错，就是人有点多。",
     "json": {"challenge_pref": 0.2, "nature_pref": 0.6, "culture_pref": 0.4,
              "solo_pref": 0.1, "novelty_pref": 0.2, "comfort_sens": 0.6,
              "season_spring": 0, "season_summer": 0, "season_autumn": 1,
              "season_winter": 0, "daypart": "day", "experience_level": "novice",
              "equipment_level": "light", "regularity": 0.3, "uncertainty": 0.4}},
]


def build_prompt(user_text: str) -> str:
    gloss = "\n".join(f"  {k}: {v}" for k, v in TERM_GLOSSARY.items())
    schema = "\n".join(f"  {k}: {v}" for k, v in SCHEMA.items())
    shots = "\n".join(
        f"文本: {ex['text']}\n输出: {json.dumps(ex['json'], ensure_ascii=False)}"
        for ex in FEWSHOT)
    return (
        "你是户外运动用户画像分析专家。根据用户的全部行程文字，"
        "严格按 schema 输出一个 JSON 偏好画像，所有字段都要给值"
        "(不确定就基于线索猜测并提高 uncertainty)。只输出 JSON。\n\n"
        f"【schema】\n{schema}\n\n【户外术语词典】\n{gloss}\n\n"
        f"【示例】\n{shots}\n\n【待分析文本】\n{user_text}\n\n【输出 JSON】")


def extract(user_text: str, call_fn) -> dict:
    """call_fn(prompt:str)->str (raw JSON). Returns validated dict or raises."""
    raw = call_fn(build_prompt(user_text))
    start, end = raw.find("{"), raw.rfind("}")
    obj = json.loads(raw[start:end + 1])
    missing = set(SCHEMA) - set(obj)
    if missing:
        raise ValueError(f"missing fields: {missing}")
    return obj


def _read_xlsx_text():
    climbing = pd.read_csv(C.CLIMBING_TRIPS_CSV, usecols=[0], encoding="utf-8",
                           on_bad_lines="skip")
    cids = set(pd.to_numeric(climbing.iloc[:, 0], errors="coerce").dropna().astype("int64"))
    frames = []
    for xlsx in sorted(C.SIXFOOT_RAW.rglob("basic*.xlsx")):
        frames.append(pd.read_excel(
            xlsx, usecols=lambda c: c in {"tripid", "userid", "title", "description"}))
    df = pd.concat(frames, ignore_index=True)
    df["tripid"] = pd.to_numeric(df["tripid"], errors="coerce")
    df = df.dropna(subset=["tripid"]).astype({"tripid": "int64"})
    return df[df["tripid"].isin(cids)].drop_duplicates("tripid")


def build_user_text() -> pd.DataFrame:
    """Per-user concatenated climbing text (title + description), for the CF
    population (clustered users). Data-readiness check for T0.2."""
    df = _read_xlsx_text()
    for col in ("title", "description"):
        df[col] = df[col].fillna("").astype(str).str.strip()
    df["text"] = (df["title"] + "。" + df["description"]).str.strip("。 ")
    agg = (df.groupby("userid")["text"]
           .apply(lambda s: "\n".join(t for t in s if t)[:MAX_CHARS]))
    out = agg.to_frame("text")
    out["n_chars"] = out["text"].str.len()
    out["n_trips_with_text"] = df[df["text"] != ""].groupby("userid").size()
    # restrict to CF population if available
    repr_path = C.DATA_PROCESSED / "user_features_repr.parquet"
    if repr_path.exists():
        pop = pd.read_parquet(repr_path).index
        out = out[out.index.isin(pop)]
    return out.fillna(0)


if __name__ == "__main__":
    ut = build_user_text()
    ut.to_parquet(USER_TEXT)
    rich = ut[ut["n_chars"] >= 50]
    print(f"[OK] {USER_TEXT.name}  users={len(ut)}")
    print(f"  n_chars: median={ut['n_chars'].median():.0f} "
          f"mean={ut['n_chars'].mean():.0f} max={ut['n_chars'].max():.0f}")
    print(f"  users with >=50 chars (T0.2-usable): {len(rich)} ({len(rich)/len(ut):.1%})")
    print(f"  users with >=200 chars: {(ut['n_chars']>=200).sum()}")
    print("\n--- sample prompt (first rich user) ---")
    if len(rich):
        print(build_prompt(rich.iloc[0]["text"])[:1200], "...")
