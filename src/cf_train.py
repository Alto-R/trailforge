"""T2.4/T2.5 train + evaluate the hybrid CF model with geo-aware negatives.

Pipeline:
  - population = the 603 clustered users (have u_cluster). Interactions filtered
    to them, using the existing time-based train/test split (D0.5).
  - geo-aware negatives: for each segment, precompute its K_GEO nearest segments
    (KDTree on centroids); negatives are drawn from a positive's geo-neighbours
    minus that user's known positives -> "why this segment not the nearby one".
  - loss: BPR.  eval: per test positive, 99 geo negatives + 1 positive -> rank;
    Recall@K / NDCG@K for K in {5,10,20} (主文档 §5.3.4).

Runs the E1/E2/E3 comparison (§8.1.2). CPU-friendly (small towers).

Run:  D:/Anaconda/envs/trailforge/python.exe src/cf_train.py --epochs 15
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import torch
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as C  # noqa: E402
from src.cf_model import TwoTowerCF, bpr_loss  # noqa: E402
from src.segment_repr import load_segment_matrix  # noqa: E402
from src.user_repr import load_user_matrix  # noqa: E402

TRAIN = C.DATA_PROCESSED / "interactions_train.parquet"
TEST = C.DATA_PROCESSED / "interactions_test.parquet"
K_GEO = 200          # geo-candidate pool size per segment (nearest neighbours)
N_EVAL_NEG = 99
KS = [5, 10, 20]
SEED = 42


def _seg_centroids(seg_ids: np.ndarray) -> np.ndarray:
    g = gpd.read_file(C.CLIM_SPRING_SEG, columns=["lypID"]).set_index("lypID")
    cen = g.geometry.centroid
    xy = np.c_[cen.x.values, cen.y.values]
    pos = {sid: i for i, sid in enumerate(g.index.to_numpy())}
    return np.array([xy[pos[s]] for s in seg_ids])


def load_data():
    u_df, u_cols = load_user_matrix()
    s_df, _ = load_segment_matrix(normalize=True)
    s_cols = [c for c in s_df.columns if c.split("_")[0] in {"geo", "vis", "beh"}]

    users = u_df.index.to_numpy()
    uidx = {u: i for i, u in enumerate(users)}
    segs = s_df.index.to_numpy()
    sidx = {s: i for i, s in enumerate(segs)}

    tr = pd.read_parquet(TRAIN); tr = tr[tr.userid.isin(uidx)]
    te = pd.read_parquet(TEST); te = te[te.userid.isin(uidx)]
    # collapse season rows -> (user, seg) pairs
    tr_pairs = tr[["userid", "lypID"]].drop_duplicates()
    te_pairs = te[["userid", "lypID"]].drop_duplicates()

    U = torch.tensor(u_df[u_cols].to_numpy(np.float32))
    S = torch.tensor(s_df[s_cols].to_numpy(np.float32))

    # geo neighbour table: K_GEO nearest segments per segment (indices into segs)
    cent = _seg_centroids(segs)
    tree = cKDTree(cent)
    _, nn_idx = tree.query(cent, k=K_GEO + 1)        # +1: self included
    nn_idx = nn_idx[:, 1:].astype(np.int32)

    # per-user positive segment index sets (train+test, to exclude as negatives)
    pos_by_user: dict[int, set] = {}
    for uid, s in pd.concat([tr_pairs, te_pairs]).itertuples(index=False):
        pos_by_user.setdefault(uidx[uid], set()).add(sidx[s])

    tr_u = tr_pairs.userid.map(uidx).to_numpy()
    tr_s = tr_pairs.lypID.map(sidx).to_numpy()
    te_u = te_pairs.userid.map(uidx).to_numpy()
    te_s = te_pairs.lypID.map(sidx).to_numpy()
    print(f"[data] users={len(users)} segs={len(segs)} | u_dim={len(u_cols)} "
          f"s_dim={len(s_cols)} | train pairs={len(tr_u)} test pairs={len(te_u)}")
    return dict(U=U, S=S, nn_idx=nn_idx, pos_by_user=pos_by_user,
                tr_u=tr_u, tr_s=tr_s, te_u=te_u, te_s=te_s,
                n_users=len(users), n_segs=len(segs),
                u_dim=len(u_cols), s_dim=len(s_cols))


def sample_neg(u_arr, s_arr, nn_idx, pos_by_user, rng):
    """One geo-negative per positive: random from positive seg's geo-neighbours,
    rejecting the user's known positives (fallback: any neighbour)."""
    neg = np.empty(len(s_arr), dtype=np.int64)
    for i in range(len(s_arr)):
        pool = nn_idx[s_arr[i]]
        seen = pos_by_user.get(u_arr[i], ())
        for _ in range(8):
            cand = pool[rng.integers(len(pool))]
            if cand not in seen:
                neg[i] = cand
                break
        else:
            neg[i] = pool[rng.integers(len(pool))]
    return neg


def evaluate(model, d, rng) -> dict:
    model.eval()
    U, S, nn_idx, pos_by_user = d["U"], d["S"], d["nn_idx"], d["pos_by_user"]
    recall = {k: [] for k in KS}; ndcg = {k: [] for k in KS}
    with torch.no_grad():
        for u, sp in zip(d["te_u"], d["te_s"]):
            pool = nn_idx[sp]; seen = pos_by_user.get(u, ())
            negs = [c for c in pool if c not in seen]
            if len(negs) < N_EVAL_NEG:
                continue
            negs = rng.choice(negs, N_EVAL_NEG, replace=False)
            cand = np.concatenate([[sp], negs])
            uf = U[u].expand(len(cand), -1)
            uidx = torch.full((len(cand),), u, dtype=torch.long)
            sidx = torch.tensor(cand, dtype=torch.long)
            scores = model.score(uf, S[sidx], uidx, sidx).numpy()
            rank = (scores > scores[0]).sum()        # rank of positive (0-based)
            for k in KS:
                recall[k].append(1.0 if rank < k else 0.0)
                ndcg[k].append(1.0 / np.log2(rank + 2) if rank < k else 0.0)
    return {**{f"Recall@{k}": np.mean(recall[k]) for k in KS},
            **{f"NDCG@{k}": np.mean(ndcg[k]) for k in KS},
            "n_eval": len(recall[KS[0]])}


def train_one(name, use_content, use_collab, d, epochs, lr=1e-3, bs=1024):
    torch.manual_seed(SEED)
    rng = np.random.default_rng(SEED)
    model = TwoTowerCF(d["u_dim"], d["s_dim"], d["n_users"], d["n_segs"],
                       alpha=0.7, use_content=use_content, use_collab=use_collab)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-5)
    U, S = d["U"], d["S"]
    tr_u, tr_s = d["tr_u"], d["tr_s"]
    n = len(tr_u)
    for ep in range(epochs):
        model.train()
        perm = rng.permutation(n)
        tot = 0.0
        for b in range(0, n, bs):
            idx = perm[b:b + bs]
            u_b, sp_b = tr_u[idx], tr_s[idx]
            sn_b = sample_neg(u_b, sp_b, d["nn_idx"], d["pos_by_user"], rng)
            u_t = torch.tensor(u_b, dtype=torch.long)
            sp_t = torch.tensor(sp_b, dtype=torch.long)
            sn_t = torch.tensor(sn_b, dtype=torch.long)
            pos, neg = model(U[u_t], None, u_t, sp_t, sn_t, S[sp_t], S[sn_t])
            loss = bpr_loss(pos, neg)
            opt.zero_grad(); loss.backward(); opt.step()
            tot += loss.item() * len(idx)
        if ep == epochs - 1 or ep % 5 == 0:
            print(f"  [{name}] epoch {ep+1}/{epochs} bpr_loss={tot/n:.4f}", flush=True)
    return evaluate(model, d, np.random.default_rng(SEED))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=15)
    args = ap.parse_args()
    d = load_data()
    configs = [("E2 pure-content", True, False),
               ("E1 pure-collab", False, True),
               ("E3 hybrid(a=.7)", True, True)]
    rows = {}
    for name, uc, ucol in configs:
        print(f"\n=== {name} ===", flush=True)
        rows[name] = train_one(name, uc, ucol, d, args.epochs)
    res = pd.DataFrame(rows).T
    print("\n" + "=" * 70)
    print(res.round(4).to_string())
    res.to_csv(C.REPORTS / "T2.5_cf_baseline_metrics.csv")
    print(f"\n[OK] metrics -> reports/T2.5_cf_baseline_metrics.csv")
