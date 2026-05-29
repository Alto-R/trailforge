"""T1.2 train/test split of the user-segment interaction matrix (档案B).

Per 主文档 §5.3.2: split each user's interactions on the TIME axis — earliest
80% -> train, latest 20% -> test — to mimic "predict the future from history".
This is a pure 档案B operation (interactions only); it deliberately does NOT
touch 档案A user features, preserving the dual-archive isolation.

A user needs >= MIN_ROWS interaction rows to contribute test positives;
shorter-history users go entirely to train (kept for content signal, not
evaluable for ranking).

Outputs:
  data_processed/interactions_train.parquet
  data_processed/interactions_test.parquet

Run:  D:/Anaconda/envs/trailforge/python.exe src/split.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as C  # noqa: E402

INTER = C.DATA_PROCESSED / "interactions_climbing.parquet"
TRAIN = C.DATA_PROCESSED / "interactions_train.parquet"
TEST = C.DATA_PROCESSED / "interactions_test.parquet"
MIN_ROWS = 5          # users with fewer rows -> all train (not evaluable)
TEST_FRAC = 0.20


def split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = df.sort_values(["userid", "first_ts", "lypID"]).reset_index(drop=True)
    n = df.groupby("userid").cumcount()                 # 0-based rank within user
    size = df.groupby("userid")["userid"].transform("size")
    # number of test rows per user (latest TEST_FRAC), 0 if too short
    n_test = (size * TEST_FRAC).astype(int).where(size >= MIN_ROWS, 0)
    is_test = n >= (size - n_test)
    return df[~is_test].copy(), df[is_test].copy()


def report(train: pd.DataFrame, test: pd.DataFrame) -> None:
    # "new" test positives = (user,segment) not seen in that user's train history
    train_pairs = set(map(tuple, train[["userid", "lypID"]].to_numpy()))
    test_pairs = test[["userid", "lypID"]].to_numpy()
    new_mask = [tuple(p) not in train_pairs for p in test_pairs]
    n_new = sum(new_mask)
    print(f"[split] train rows={len(train):,}  test rows={len(test):,}")
    print(f"[split] users total={pd.concat([train.userid, test.userid]).nunique()} "
          f"| users with test={test.userid.nunique()}")
    print(f"[split] test positives that are NEW (unseen in user's train): "
          f"{n_new:,}/{len(test):,} ({n_new/max(len(test),1):.1%})")
    # temporal sanity: no test ts earlier than that user's max train ts
    tmax = train.groupby("userid")["first_ts"].max()
    tt = test.merge(tmax.rename("train_max_ts"), on="userid", how="left")
    bad = (tt["first_ts"] < tt["train_max_ts"]).sum()
    print(f"[split] temporal violations (test ts < user train max ts): {bad}")


if __name__ == "__main__":
    df = pd.read_parquet(INTER)
    train, test = split(df)
    report(train, test)
    train.to_parquet(TRAIN, index=False)
    test.to_parquet(TEST, index=False)
    print(f"[OK] written {TRAIN.name} + {TEST.name}")
