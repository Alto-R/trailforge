"""T2.7 multi-seed significance + cold-start internal ablation.

Two gaps the single-run T2.5 left open (主文档发表方向一的收尾):
  (A) the E0-E6 matrix and the cold-start numbers were one run each -> no error
      bars, no significance. Here we repeat over N seeds and report mean +/- std
      plus paired t-tests on the headline contrasts.
  (B) T2.5 proved the content *tower* is decisive in cold-start, but not WHICH
      layer. Here we ablate the content signal inside the cold regime:
      E2 full content  vs  -u_LLM  vs  -visual  vs  -both, to locate the layer
      that actually drives the cold-start gain.

What varies per seed: model init, BPR negative sampling, eval-negative draw,
and (cold) the held-out 20% user set -- so the error bars cover both optimisation
and split variance.

Run:  PYTHONUTF8=1 D:/Anaconda/envs/trailforge/python.exe src/cf_significance.py
      [--seeds 42,43,44,45,46] [--epochs 15] [--quick]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as C  # noqa: E402
from src.cf_train import CONFIGS, load_data, train_one, popularity_eval_fast, SEED  # noqa: E402
from src.cf_coldstart import make_cold_split  # noqa: E402
from src.user_repr import load_user_matrix  # noqa: E402

KEY = "Recall@10"

# active-user matrix (E0 handled separately as it is non-parametric)
ACTIVE_TRAINED = ["E1 pure-collab", "E2 pure-content", "E3 hybrid(a=.7)",
                  "E4 hybrid-adaptA", "E6 hybrid-novis"]

# cold-start content-tower ablation.  spec = (config-tuple, use_cluster_only_U)
# config tuple = (use_content, use_collab, adaptive_alpha, novis)
PURE_CONTENT = (True, False, False, False)        # full s (geo+visual+beh)
PURE_CONTENT_NOVIS = (True, False, False, True)   # s without the visual layer
COLD_SPECS = {
    "E1 collab (floor)":   (CONFIGS["E1 pure-collab"], False),
    "E2 content (full)":   (PURE_CONTENT, False),
    "E2 -u_LLM":           (PURE_CONTENT, True),
    "E2 -visual":          (PURE_CONTENT_NOVIS, False),
    "E2 -u_LLM -visual":   (PURE_CONTENT_NOVIS, True),
    "E4 adaptive (ref)":   (CONFIGS["E4 hybrid-adaptA"], False),
}

# headline contrasts for paired t-tests (config_a, config_b) on Recall@10
ACTIVE_CONTRASTS = [("E4 hybrid-adaptA", "E1 pure-collab"),
                    ("E2 pure-content", "E0 popularity")]
COLD_CONTRASTS = [("E2 content (full)", "E1 collab (floor)"),
                  ("E2 content (full)", "E2 -u_LLM"),
                  ("E2 content (full)", "E2 -visual"),
                  ("E2 content (full)", "E2 -u_LLM -visual")]


def cluster_only_U() -> tuple[torch.Tensor, int]:
    """User tensor with only the K=5 GMM cluster dims (drop llm_* and the
    has_llm_profile flag).  Row order matches load_data's U (same parquet)."""
    u_df, u_cols = load_user_matrix()
    cols = [c for c in u_cols if c.startswith("u_cluster_")]
    return torch.tensor(u_df[cols].to_numpy(np.float32)), len(cols)


def _append(path: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_csv(path, mode="a", header=not path.exists(), index=False)


def _done_seeds(path: Path) -> set:
    return set(pd.read_csv(path)["seed"].tolist()) if path.exists() else set()


def run_active(d, seeds, epochs, path: Path) -> None:
    done = _done_seeds(path)
    for sd in seeds:
        if sd in done:
            print(f"  [active seed={sd}] already in {path.name}, skip", flush=True)
            continue
        rows = [{"seed": sd, "config": "E0 popularity",
                 **popularity_eval_fast(d, np.random.default_rng(sd))}]
        for name in ACTIVE_TRAINED:
            m = train_one(name, CONFIGS[name], d, epochs, seed=sd, fast=True)
            rows.append({"seed": sd, "config": name, **m})
            print(f"  [active seed={sd}] {name}: {KEY}={m[KEY]:.4f}", flush=True)
        _append(path, rows)                       # persist after each seed (resumable)


def run_cold(d, seeds, epochs, path: Path) -> None:
    done = _done_seeds(path)
    U_red, dim_red = cluster_only_U()
    for sd in seeds:
        if sd in done:
            print(f"  [cold seed={sd}] already in {path.name}, skip", flush=True)
            continue
        d_cold = make_cold_split(d, seed=sd)
        rows = []
        for name, (cfg, use_red) in COLD_SPECS.items():
            dd = dict(d_cold, U=U_red, u_dim=dim_red) if use_red else d_cold
            m = train_one(name, cfg, dd, epochs, seed=sd, fast=True)
            rows.append({"seed": sd, "config": name, **m})
            print(f"  [cold seed={sd}] {name}: {KEY}={m[KEY]:.4f}", flush=True)
        _append(path, rows)                       # persist after each seed (resumable)


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    """config -> 'mean ± std' string per metric, preserving config order."""
    mcols = [c for c in df.columns if c.startswith(("Recall@", "NDCG@"))]
    order = list(dict.fromkeys(df["config"]))
    g = df.groupby("config")[mcols]
    mean, std = g.mean(), g.std(ddof=1)
    out = pd.DataFrame(index=order)
    for c in mcols:
        out[c] = [f"{mean.loc[i, c]:.4f} ± {std.loc[i, c]:.4f}" for i in order]
    out["n_seeds"] = [int((df["config"] == i).sum()) for i in order]
    return out


def paired_tests(df: pd.DataFrame, contrasts, metric=KEY) -> pd.DataFrame:
    rows = []
    for a, b in contrasts:
        xa = df[df.config == a].sort_values("seed")[metric].to_numpy()
        xb = df[df.config == b].sort_values("seed")[metric].to_numpy()
        if len(xa) != len(xb) or len(xa) < 2:
            continue
        t, p = stats.ttest_rel(xa, xb)
        rows.append({"contrast": f"{a}  -  {b}", "metric": metric,
                     "mean_diff": round(float((xa - xb).mean()), 4),
                     "t": round(float(t), 3), "p_value": float(f"{p:.2e}"),
                     "n_seeds": len(xa)})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=str, default="42,43,44,45,46")
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--quick", action="store_true",
                    help="1 seed, 2 epochs -- plumbing smoke test only")
    ap.add_argument("--prefix", type=str, default="T2.7")
    args = ap.parse_args()
    seeds = [42] if args.quick else [int(s) for s in args.seeds.split(",")]
    epochs = 2 if args.quick else args.epochs
    prefix = args.prefix + ("_smoke" if args.quick else "")
    print(f"[run] seeds={seeds} epochs={epochs} prefix={prefix}", flush=True)

    d = load_data()
    act_path = C.REPORTS / f"{prefix}_active_seeds.csv"
    cold_path = C.REPORTS / f"{prefix}_cold_seeds.csv"

    print("\n========== (A) active-user matrix ==========", flush=True)
    run_active(d, seeds, epochs, act_path)
    print("\n========== (B) cold-start ablation ==========", flush=True)
    run_cold(d, seeds, epochs, cold_path)

    # summarise over whatever seeds have accumulated in the CSVs (resumable)
    act, cold = pd.read_csv(act_path), pd.read_csv(cold_path)
    act_sum, cold_sum = summarize(act), summarize(cold)
    act_sum.to_csv(C.REPORTS / f"{prefix}_active_summary.csv")
    cold_sum.to_csv(C.REPORTS / f"{prefix}_cold_summary.csv")
    sig = pd.concat([paired_tests(act, ACTIVE_CONTRASTS),
                     paired_tests(cold, COLD_CONTRASTS)], ignore_index=True)
    sig.to_csv(C.REPORTS / f"{prefix}_significance.csv", index=False)

    print("\n===== ACTIVE (mean ± std over seeds) =====")
    print(act_sum.to_string())
    print("\n===== COLD-START ablation (mean ± std over seeds) =====")
    print(cold_sum.to_string())
    print("\n===== paired t-tests (Recall@10) =====")
    print(sig.to_string(index=False))
    print(f"\n[OK] reports/{args.prefix}_*.csv", flush=True)
