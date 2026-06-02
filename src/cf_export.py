"""板块A：train + persist the production E4 model for serving.

cf_train.py only *evaluates* E0–E6; it never saves a model. The backend needs a
trained checkpoint to score segments at request time. This script trains the
E4 config (hybrid two-tower + explicit collaborative factor + adaptive alpha,
the only model robust in BOTH the active and cold-start domains) on the full
603-user training split and writes three artifacts under data_processed/:

  e4.pt                       torch checkpoint: state_dict + arch hyper-params
  e4_meta.json                inference metadata:
                                u_cols (24, ordered) / cluster_cols / llm_cols /
                                flag_col / llm_means (cold-user fill, == training
                                cold encoding) / s_cols (83, ordered) / arch /
                                eval metrics (active-domain sanity anchor)
  segment_geom_climbing.parquet   per-lypID LineString geometry (Krasovsky
                                Albers) so the backend draws routes WITHOUT the
                                G: shapefile. Built once from CLIM_SPRING_SEG.

Serving uses ONLY the content towers (g_u, g_s): a new onboarding user has no
collaborative u_id embedding, so r_hat = <g_u(u_feat), g_s(s_feat)> — exactly
the cold-start content path that scored 0.457 (2.5x collab) in T2.5.

Run:  PYTHONNOUSERSITE=1 PYTHONUTF8=1 D:/Anaconda/envs/trailforge/python.exe src/cf_export.py
      (optional: --epochs 15 --seed 42)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as C  # noqa: E402
from src.cf_model import TwoTowerCF, bpr_loss  # noqa: E402
from src.cf_train import (SEED, evaluate_fast, load_data,  # noqa: E402
                          sample_neg_fast)
from src.segment_repr import load_segment_matrix  # noqa: E402
from src.user_repr import load_user_matrix  # noqa: E402

E4_PT = C.DATA_PROCESSED / "e4.pt"
E4_META = C.DATA_PROCESSED / "e4_meta.json"
GEOM_CACHE = C.DATA_PROCESSED / "segment_geom_climbing.parquet"
SEG_LOGCNT = C.DATA_PROCESSED / "segment_logcnt_climbing.parquet"
TRAIN_PARQUET = C.DATA_PROCESSED / "interactions_train.parquet"

# E4 = hybrid, both towers, adaptive alpha; visual layer kept (novis=False)
D_EMB = 32          # content embedding dim (TwoTowerCF default)
D_COLLAB = 32       # collaborative embedding dim
ALPHA0 = 0.7


def train_e4(d: dict, epochs: int, seed: int = SEED, lr: float = 1e-3,
             bs: int = 1024) -> TwoTowerCF:
    """Train the E4 model on the full train split and return it (eval mode).

    Mirrors cf_train.train_one's loop for the E4 config but returns the model
    instead of only metrics. Uses the fast (searchsorted) geo-negative sampler.
    """
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    S = d["S"]
    model = TwoTowerCF(d["u_dim"], d["s_dim"], d["n_users"], d["n_segs"],
                       d=D_EMB, d_collab=D_COLLAB, alpha=ALPHA0,
                       use_content=True, use_collab=True, adaptive_alpha=True)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-5)
    U, lcu, lcs = d["U"], d["log_cnt_u"], d["log_cnt_s"]
    tr_u, tr_s = d["tr_u"], d["tr_s"]
    n = len(tr_u)
    for ep in range(epochs):
        model.train()
        perm = rng.permutation(n)
        tot = 0.0
        for b in range(0, n, bs):
            idx = perm[b:b + bs]
            u_b, sp_b = tr_u[idx], tr_s[idx]
            sn_b = sample_neg_fast(u_b, sp_b, d["nn_idx"], d["pos_packed"],
                                   d["n_segs"], rng)
            ut = torch.tensor(u_b); spt = torch.tensor(sp_b); snt = torch.tensor(sn_b)
            pos, neg = model(U[ut], None, ut, spt, snt, S[spt], S[snt],
                             lcu[ut], lcs[spt], lcs[snt])
            loss = bpr_loss(pos, neg)
            opt.zero_grad(); loss.backward(); opt.step()
            tot += loss.item() * len(idx)
        if ep == epochs - 1 or ep % 5 == 0:
            w = model.alpha_w.detach().numpy().round(3).tolist()
            print(f"  [E4] epoch {ep+1}/{epochs} bpr_loss={tot/n:.4f} alpha_w={w}",
                  flush=True)
    model.eval()
    return model


def _arch(d: dict) -> dict:
    return {"n_user_feat": d["u_dim"], "n_seg_feat": d["s_dim"],
            "n_users": d["n_users"], "n_segs": d["n_segs"],
            "d": D_EMB, "d_collab": D_COLLAB, "alpha": ALPHA0,
            "use_content": True, "use_collab": True, "adaptive_alpha": True}


def build_seg_logcnt() -> int:
    """Cache per-segment log1p(unique-user train count) — the ``log_cnt_s`` the
    adaptive alpha uses. Serving a cold user needs it to weight the content score
    by alpha(s) = sigmoid(w0 + w2*log_cnt_s) (log_cnt_u=0), matching the E4
    cold-start path. Computed directly from the train split (no retrain)."""
    u_df, _ = load_user_matrix()
    s_df, _ = load_segment_matrix(normalize=False)
    tr = pd.read_parquet(TRAIN_PARQUET)
    tr = tr[tr.userid.isin(u_df.index)]
    pairs = tr[["userid", "lypID"]].drop_duplicates()
    cnt = pairs.groupby("lypID").size()
    log_cnt = np.log1p(cnt.reindex(s_df.index).fillna(0.0))
    log_cnt.name = "log_cnt_s"
    log_cnt.to_frame().to_parquet(SEG_LOGCNT)
    return len(log_cnt)


def build_geom_cache() -> int:
    """Cache per-lypID LineString geometry (Albers) so serving never touches the
    G: shapefile. Returns row count written."""
    g = gpd.read_file(C.CLIM_SPRING_SEG, columns=["lypID"])
    g = g.set_index("lypID")[["geometry"]]
    g.to_parquet(GEOM_CACHE)
    return len(g)


def export(epochs: int = 15, seed: int = SEED) -> dict:
    """Train E4, persist checkpoint + meta + geometry cache. Returns a summary."""
    u_df, u_cols = load_user_matrix()
    s_df, layers = load_segment_matrix(normalize=True)
    s_cols = layers["geo"] + layers["vis"] + layers["beh"]

    cluster_cols = [c for c in u_cols if c.startswith("u_cluster")]
    llm_cols = [c for c in u_cols if c.startswith("llm_")]
    flag_col = "has_llm_profile"
    # cold-user llm fill == training cold encoding (user_repr fills NaN with the
    # column mean over profiled users; mean over the post-fill matrix is identical)
    llm_means = {c: float(u_df[c].mean()) for c in llm_cols}

    d = load_data()
    model = train_e4(d, epochs=epochs, seed=seed)
    metrics = evaluate_fast(model, d, d["S"], np.random.default_rng(seed))
    print(f"[eval] active-domain {({k: round(v, 4) for k, v in metrics.items()})}",
          flush=True)

    arch = _arch(d)
    torch.save({"state_dict": model.state_dict(), "arch": arch,
                "config": "E4 hybrid-adaptA", "seed": seed, "epochs": epochs}, E4_PT)
    meta = {"u_cols": list(u_cols), "cluster_cols": cluster_cols,
            "llm_cols": llm_cols, "flag_col": flag_col, "llm_means": llm_means,
            "s_cols": s_cols, "arch": arch, "metrics": metrics,
            "n_users": d["n_users"], "n_segs": d["n_segs"]}
    E4_META.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    n_geom = build_geom_cache()
    n_lc = build_seg_logcnt()
    print(f"[OK] {E4_PT.name} + {E4_META.name} (u={len(u_cols)} s={len(s_cols)}) "
          f"+ {GEOM_CACHE.name} ({n_geom} segs) + {SEG_LOGCNT.name} ({n_lc})",
          flush=True)
    return {"metrics": metrics, "n_geom": n_geom, "u_dim": d["u_dim"], "s_dim": d["s_dim"]}


def load_model() -> tuple[TwoTowerCF, dict]:
    """Reconstruct the trained E4 model + load its meta, for serving/tests.

    Returns (model in eval mode, meta dict). Raises FileNotFoundError if export
    has not been run."""
    if not E4_PT.exists() or not E4_META.exists():
        raise FileNotFoundError(
            f"missing {E4_PT.name}/{E4_META.name}; run `python src/cf_export.py` first")
    ckpt = torch.load(E4_PT, map_location="cpu", weights_only=False)
    a = ckpt["arch"]
    model = TwoTowerCF(a["n_user_feat"], a["n_seg_feat"], a["n_users"], a["n_segs"],
                       d=a["d"], d_collab=a["d_collab"], alpha=a["alpha"],
                       use_content=a["use_content"], use_collab=a["use_collab"],
                       adaptive_alpha=a["adaptive_alpha"])
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    meta = json.loads(E4_META.read_text(encoding="utf-8"))
    return model, meta


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()
    export(epochs=args.epochs, seed=args.seed)
