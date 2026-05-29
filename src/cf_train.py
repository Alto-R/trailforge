"""T2.4/T2.5 train + evaluate the hybrid CF model with geo-aware negatives.

Pipeline:
  - population = the 603 clustered users (have u_cluster). Interactions filtered
    to them, using the existing time-based train/test split (D0.5).
  - geo-aware negatives: for each segment, precompute its K_GEO nearest segments
    (KDTree on centroids); negatives are drawn from a positive's geo-neighbours
    minus that user's known positives.
  - loss: BPR.  eval: per test positive, 99 geo negatives + 1 positive -> rank;
    Recall@K / NDCG@K for K in {5,10,20} (主文档 §5.3.4).

Configs (主文档 §8.1.2):
  E0 popularity   non-personalised: rank by segment train-traffic (TRDA-ish floor)
  E1 pure-collab  E2 pure-content  E3 hybrid(a=.7)
  E4 hybrid adaptive-alpha(u,s)
  E6 hybrid, segment features WITHOUT the visual layer (s_visual ablation)

Run:  D:/Anaconda/envs/trailforge/python.exe src/cf_train.py --configs E0,E4,E6 --epochs 15
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
K_GEO = 200
N_EVAL_NEG = 99
KS = [5, 10, 20]
SEED = 42

CONFIGS = {  # name -> (use_content, use_collab, adaptive_alpha, novis)
    "E1 pure-collab": (False, True, False, False),
    "E2 pure-content": (True, False, False, False),
    "E3 hybrid(a=.7)": (True, True, False, False),
    "E4 hybrid-adaptA": (True, True, True, False),
    "E6 hybrid-novis": (True, True, False, True),
}


def _seg_centroids(seg_ids: np.ndarray) -> np.ndarray:
    g = gpd.read_file(C.CLIM_SPRING_SEG, columns=["lypID"]).set_index("lypID")
    cen = g.geometry.centroid
    xy = np.c_[cen.x.values, cen.y.values]
    pos = {sid: i for i, sid in enumerate(g.index.to_numpy())}
    return np.array([xy[pos[s]] for s in seg_ids])


def load_data():
    u_df, u_cols = load_user_matrix()
    s_df, layers = load_segment_matrix(normalize=True)
    s_cols = layers["geo"] + layers["vis"] + layers["beh"]
    s_cols_novis = layers["geo"] + layers["beh"]            # E6 ablation

    users = u_df.index.to_numpy()
    uidx = {u: i for i, u in enumerate(users)}
    segs = s_df.index.to_numpy()
    sidx = {s: i for i, s in enumerate(segs)}

    tr = pd.read_parquet(TRAIN); tr = tr[tr.userid.isin(uidx)]
    te = pd.read_parquet(TEST); te = te[te.userid.isin(uidx)]
    tr_pairs = tr[["userid", "lypID"]].drop_duplicates()
    te_pairs = te[["userid", "lypID"]].drop_duplicates()

    U = torch.tensor(u_df[u_cols].to_numpy(np.float32))
    S = torch.tensor(s_df[s_cols].to_numpy(np.float32))
    S_novis = torch.tensor(s_df[s_cols_novis].to_numpy(np.float32))

    cent = _seg_centroids(segs)
    tree = cKDTree(cent)
    _, nn_idx = tree.query(cent, k=K_GEO + 1)
    nn_idx = nn_idx[:, 1:].astype(np.int32)

    pos_by_user: dict[int, set] = {}
    for uid, s in pd.concat([tr_pairs, te_pairs]).itertuples(index=False):
        pos_by_user.setdefault(uidx[uid], set()).add(sidx[s])

    tr_u = tr_pairs.userid.map(uidx).to_numpy()
    tr_s = tr_pairs.lypID.map(sidx).to_numpy()
    te_u = te_pairs.userid.map(uidx).to_numpy()
    te_s = te_pairs.lypID.map(sidx).to_numpy()

    # interaction counts (train) -> log1p, for adaptive alpha & popularity (E0)
    cnt_u = np.bincount(tr_u, minlength=len(users)).astype(np.float32)
    cnt_s = np.bincount(tr_s, minlength=len(segs)).astype(np.float32)
    log_cnt_u = torch.tensor(np.log1p(cnt_u))
    log_cnt_s = torch.tensor(np.log1p(cnt_s))
    print(f"[data] users={len(users)} segs={len(segs)} | u_dim={len(u_cols)} "
          f"s_dim={len(s_cols)} (novis {len(s_cols_novis)}) | "
          f"train={len(tr_u)} test={len(te_u)}")
    return dict(U=U, S=S, S_novis=S_novis, nn_idx=nn_idx, pos_by_user=pos_by_user,
                tr_u=tr_u, tr_s=tr_s, te_u=te_u, te_s=te_s,
                log_cnt_u=log_cnt_u, log_cnt_s=log_cnt_s,
                n_users=len(users), n_segs=len(segs),
                u_dim=len(u_cols), s_dim=len(s_cols), s_dim_novis=len(s_cols_novis))


def sample_neg(u_arr, s_arr, nn_idx, pos_by_user, rng):
    neg = np.empty(len(s_arr), dtype=np.int64)
    for i in range(len(s_arr)):
        pool = nn_idx[s_arr[i]]; seen = pos_by_user.get(u_arr[i], ())
        for _ in range(8):
            cand = pool[rng.integers(len(pool))]
            if cand not in seen:
                neg[i] = cand; break
        else:
            neg[i] = pool[rng.integers(len(pool))]
    return neg


def _metrics(ranks):
    out = {}
    ranks = np.asarray(ranks)
    for k in KS:
        out[f"Recall@{k}"] = float(np.mean(ranks < k))
        out[f"NDCG@{k}"] = float(np.mean(np.where(ranks < k, 1.0 / np.log2(ranks + 2), 0.0)))
    out["n_eval"] = int(len(ranks))
    return out


def evaluate(model, d, S, rng) -> dict:
    model.eval()
    nn_idx, pos_by_user = d["nn_idx"], d["pos_by_user"]
    U, lcu, lcs = d["U"], d["log_cnt_u"], d["log_cnt_s"]
    ranks = []
    with torch.no_grad():
        for u, sp in zip(d["te_u"], d["te_s"]):
            pool = nn_idx[sp]; seen = pos_by_user.get(u, ())
            negs = [c for c in pool if c not in seen]
            if len(negs) < N_EVAL_NEG:
                continue
            negs = rng.choice(negs, N_EVAL_NEG, replace=False)
            cand = np.concatenate([[sp], negs])
            ci = torch.tensor(cand, dtype=torch.long)
            uf = U[u].expand(len(cand), -1)
            ui = torch.full((len(cand),), u, dtype=torch.long)
            scores = model.score(uf, S[ci], ui, ci,
                                 lcu[u].expand(len(cand)), lcs[ci]).numpy()
            ranks.append(int((scores > scores[0]).sum()))
    return _metrics(ranks)


def popularity_eval(d, rng) -> dict:
    """E0: non-personalised — rank candidates by segment train-traffic."""
    nn_idx, pos_by_user, lcs = d["nn_idx"], d["pos_by_user"], d["log_cnt_s"].numpy()
    ranks = []
    for u, sp in zip(d["te_u"], d["te_s"]):
        pool = nn_idx[sp]; seen = pos_by_user.get(u, ())
        negs = [c for c in pool if c not in seen]
        if len(negs) < N_EVAL_NEG:
            continue
        negs = rng.choice(negs, N_EVAL_NEG, replace=False)
        cand = np.concatenate([[sp], negs])
        sc = lcs[cand]
        ranks.append(int((sc > sc[0]).sum()))
    return _metrics(ranks)


def train_one(name, cfg, d, epochs, lr=1e-3, bs=1024):
    use_content, use_collab, adaptive, novis = cfg
    torch.manual_seed(SEED)
    rng = np.random.default_rng(SEED)
    S = d["S_novis"] if novis else d["S"]
    s_dim = d["s_dim_novis"] if novis else d["s_dim"]
    model = TwoTowerCF(d["u_dim"], s_dim, d["n_users"], d["n_segs"], alpha=0.7,
                       use_content=use_content, use_collab=use_collab,
                       adaptive_alpha=adaptive)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-5)
    U, lcu, lcs = d["U"], d["log_cnt_u"], d["log_cnt_s"]
    tr_u, tr_s = d["tr_u"], d["tr_s"]; n = len(tr_u)
    for ep in range(epochs):
        model.train(); perm = rng.permutation(n); tot = 0.0
        for b in range(0, n, bs):
            idx = perm[b:b + bs]
            u_b, sp_b = tr_u[idx], tr_s[idx]
            sn_b = sample_neg(u_b, sp_b, d["nn_idx"], d["pos_by_user"], rng)
            ut = torch.tensor(u_b); spt = torch.tensor(sp_b); snt = torch.tensor(sn_b)
            pos, neg = model(U[ut], None, ut, spt, snt, S[spt], S[snt],
                             lcu[ut], lcs[spt], lcs[snt])
            loss = bpr_loss(pos, neg)
            opt.zero_grad(); loss.backward(); opt.step()
            tot += loss.item() * len(idx)
        if ep == epochs - 1 or ep % 5 == 0:
            extra = ""
            if adaptive:
                w = model.alpha_w.detach().numpy()
                extra = f" alpha_w={w.round(3).tolist()}"
            print(f"  [{name}] epoch {ep+1}/{epochs} bpr_loss={tot/n:.4f}{extra}", flush=True)
    return evaluate(model, d, S, np.random.default_rng(SEED))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--configs", type=str, default="E1,E2,E3",
                    help="comma codes: E0,E1,E2,E3,E4,E6")
    ap.add_argument("--out", type=str, default="T2.5_cf_baseline_metrics.csv")
    args = ap.parse_args()
    d = load_data()
    want = set(args.configs.split(","))
    rows = {}
    if "E0" in want:
        print("\n=== E0 popularity ===", flush=True)
        rows["E0 popularity"] = popularity_eval(d, np.random.default_rng(SEED))
    for name, cfg in CONFIGS.items():
        code = name.split()[0]
        if code in want:
            print(f"\n=== {name} ===", flush=True)
            rows[name] = train_one(name, cfg, d, args.epochs)
    res = pd.DataFrame(rows).T
    print("\n" + "=" * 70 + "\n" + res.round(4).to_string())
    res.to_csv(C.REPORTS / args.out)
    print(f"\n[OK] metrics -> reports/{args.out}")
