"""Generate publication-style figures for the advisor report (Chinese labels).

Outputs PNG (for markdown) + PDF into trailforge/figures/.
Run:  D:/Anaconda/envs/trailforge/python.exe notebooks/make_report_figures.py
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("MKL_THREADING_LAYER", "SEQUENTIAL")  # avoid native crash in this env

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['font.size'] = 10
plt.rcParams['pdf.fonttype'] = 42

FIG = C.REPO_ROOT / "figures"
FIG.mkdir(exist_ok=True)
C_ACTIVE, C_COLD = '#3C5488', '#E64B35'
C_R, C_N = '#4DBBD5', '#E64B35'


def _save(fig, name):
    fig.savefig(FIG / f"{name}.png", dpi=300, bbox_inches='tight')
    fig.savefig(FIG / f"{name}.pdf", dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"[OK] figures/{name}.png")


def _bars_on(ax):
    ax.grid(axis='y', linestyle='--', alpha=0.3); ax.xaxis.grid(False)
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)


def fig_regime():
    """Headline: active vs cold-start, Recall@10 for E1/E2/E4."""
    extra = pd.read_csv(C.REPORTS / "T2.5_cf_extra_metrics.csv", index_col=0)
    u24 = pd.read_csv(C.REPORTS / "T2.5_cf_metrics_u24.csv", index_col=0)
    cold = pd.read_csv(C.REPORTS / "T2.5_cf_coldstart_metrics.csv", index_col=0)
    labels = ['E1 纯协同', 'E2 纯内容', 'E4 自适应混合']
    active = [u24.loc['E1 pure-collab', 'Recall@10'],
              u24.loc['E2 pure-content', 'Recall@10'],
              extra.loc['E4 hybrid-adaptA', 'Recall@10']]
    coldv = [cold.loc['E1 pure-collab', 'Recall@10'],
             cold.loc['E2 pure-content', 'Recall@10'],
             cold.loc['E4 hybrid-adaptA', 'Recall@10']]
    x = np.arange(len(labels)); w = 0.36
    fig, ax = plt.subplots(figsize=(4.2, 2.8))
    b1 = ax.bar(x - w/2, active, w, label='活跃用户', color=C_ACTIVE)
    b2 = ax.bar(x + w/2, coldv, w, label='冷启动用户', color=C_COLD)
    ax.axhline(0.10, ls='--', color='#333333', lw=1, alpha=0.7)
    ax.text(2.42, 0.115, '随机基线', fontsize=8, color='#333333', ha='right')
    for bars in (b1, b2):
        for b in bars:
            ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.008,
                    f'{b.get_height():.2f}', ha='center', fontsize=8)
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_ylabel('Recall@10'); ax.set_ylim(0, 0.62)
    ax.legend(frameon=False, fontsize=9, loc='upper center', ncol=2,
              bbox_to_anchor=(0.5, 1.12))
    _bars_on(ax); fig.tight_layout(); _save(fig, "fig1_regime_inversion")


def fig_matrix():
    """E0-E6 active-user matrix: Recall@10 + NDCG@10."""
    u24 = pd.read_csv(C.REPORTS / "T2.5_cf_metrics_u24.csv", index_col=0)
    extra = pd.read_csv(C.REPORTS / "T2.5_cf_extra_metrics.csv", index_col=0)
    u5 = pd.read_csv(C.REPORTS / "T2.5_cf_metrics_u5.csv", index_col=0)
    order = [('E0 popularity', extra), ('E2 pure-content', u24),
             ('E5 无LLM', u5), ('E3 hybrid(a=.7)', u24),
             ('E6 hybrid-novis', extra), ('E4 hybrid-adaptA', extra),
             ('E1 pure-collab', u24)]
    src5 = {'E5 无LLM': 'E3 hybrid(a=.7)'}
    labels = ['E0\n流量', 'E2\n内容', 'E5\n无LLM', 'E3\n固定α',
              'E6\n无视觉', 'E4\n自适应', 'E1\n协同']
    rec, ndc = [], []
    for (name, df) in order:
        key = src5.get(name, name)
        rec.append(df.loc[key, 'Recall@10']); ndc.append(df.loc[key, 'NDCG@10'])
    x = np.arange(len(labels)); w = 0.38
    fig, ax = plt.subplots(figsize=(6.2, 2.8))
    ax.bar(x - w/2, rec, w, label='Recall@10', color=C_R)
    ax.bar(x + w/2, ndc, w, label='NDCG@10', color=C_N)
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel('指标值'); ax.set_ylim(0, 0.58)
    ax.legend(frameon=False, fontsize=9, ncol=2, loc='upper left')
    _bars_on(ax); fig.tight_layout(); _save(fig, "fig2_matrix_active")


def fig_bic():
    """GMM BIC vs K (user clustering model selection)."""
    bic = {3: 21105, 4: 18922, 5: 18089, 6: 18610, 7: 19119, 8: 19821,
           9: 19923, 10: 20291, 11: 20830, 12: 21554}
    ks = list(bic); vs = list(bic.values())
    fig, ax = plt.subplots(figsize=(3.5, 2.5))
    ax.plot(ks, vs, '-o', color=C_ACTIVE, lw=1.5, ms=4)
    ax.plot(5, bic[5], 'o', color=C_COLD, ms=9, zorder=5)
    ax.annotate('K=5 (最优)', xy=(5, bic[5]), xytext=(6.5, 18300),
                fontsize=9, color=C_COLD,
                arrowprops=dict(arrowstyle='->', color=C_COLD, lw=1))
    ax.set_xlabel('画像组数 K'); ax.set_ylabel('BIC'); ax.set_xticks(ks)
    ax.grid(axis='y', linestyle='--', alpha=0.3)
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    fig.tight_layout(); _save(fig, "fig3_gmm_bic")


if __name__ == "__main__":
    fig_regime(); fig_matrix(); fig_bic()
    print("done")
