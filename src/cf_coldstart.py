"""Cold-start evaluation: the regime where content SHOULD beat collaboration.

The T2.5 matrix (active users) is structurally collab-favouring: every eval
user has a trained ID embedding. Here we hold out a fraction of users entirely
from training (cold users); their ID embedding stays at init (no collab signal),
so pure-collab (E1) should collapse to ~random while pure-content (E2) still
predicts from their u features. This isolates the content tower's cold-start value.

Protocol: 20% users held out (seeded). Train each config on the warm 80% only.
Evaluate on the cold users' test positives (same 99-geo-neg ranking).

Run:  D:/Anaconda/envs/trailforge/python.exe src/cf_coldstart.py --epochs 15
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as C  # noqa: E402
from src.cf_train import CONFIGS, load_data, train_one, evaluate, SEED  # noqa: E402

COLD_FRAC = 0.20
COLD_CONFIGS = ["E1 pure-collab", "E2 pure-content", "E4 hybrid-adaptA"]


def make_cold_split(d, cold_frac=COLD_FRAC, seed=SEED):
    rng = np.random.default_rng(seed)
    n_users = d["n_users"]
    cold = set(rng.choice(n_users, int(n_users * cold_frac), replace=False).tolist())
    # train only on warm users; evaluate only on cold users
    tr_mask = np.array([u not in cold for u in d["tr_u"]])
    te_mask = np.array([u in cold for u in d["te_u"]])
    d2 = dict(d)
    d2["tr_u"] = d["tr_u"][tr_mask]; d2["tr_s"] = d["tr_s"][tr_mask]
    d2["te_u"] = d["te_u"][te_mask]; d2["te_s"] = d["te_s"][te_mask]
    print(f"[cold] {len(cold)} cold users | warm train pairs={len(d2['tr_u'])} | "
          f"cold test pairs={len(d2['te_u'])}")
    return d2


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=15)
    args = ap.parse_args()
    d = load_data()
    d_cold = make_cold_split(d)
    rows = {}
    for name in COLD_CONFIGS:
        print(f"\n=== {name} (cold-start) ===", flush=True)
        rows[name] = train_one(name, CONFIGS[name], d_cold, args.epochs)
    res = pd.DataFrame(rows).T
    print("\n" + "=" * 70 + "\n" + res.round(4).to_string())
    res.to_csv(C.REPORTS / "T2.5_cf_coldstart_metrics.csv")
    print("\n[OK] reports/T2.5_cf_coldstart_metrics.csv")
