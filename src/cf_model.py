"""T2.4 hybrid CF model: two content towers + explicit collaborative factor.

  r_hat(u,s) = alpha * <g_u(u), g_s(s)>  +  (1-alpha) * <u_id, s_id>
                 content path                  collaborative path

Per 主文档 §5.3.1. The three experiment variants are obtained via flags:
  E2 pure content     use_content=True,  use_collab=False
  E1 pure collab      use_content=False, use_collab=True
  E3 hybrid           use_content=True,  use_collab=True, alpha=0.7
"""
from __future__ import annotations

import torch
import torch.nn as nn


def _mlp(sizes: list[int], dropout: float) -> nn.Sequential:
    layers = []
    for i in range(len(sizes) - 1):
        layers.append(nn.Linear(sizes[i], sizes[i + 1]))
        if i < len(sizes) - 2:                      # no activation on last layer
            layers += [nn.ReLU(), nn.Dropout(dropout)]
    return nn.Sequential(*layers)


class TwoTowerCF(nn.Module):
    def __init__(self, n_user_feat: int, n_seg_feat: int, n_users: int, n_segs: int,
                 d: int = 32, d_collab: int = 32, alpha: float = 0.7,
                 use_content: bool = True, use_collab: bool = True,
                 adaptive_alpha: bool = False):
        super().__init__()
        self.alpha = alpha
        self.use_content = use_content
        self.use_collab = use_collab
        self.adaptive_alpha = adaptive_alpha and use_content and use_collab
        if use_content:
            self.g_u = _mlp([n_user_feat, 64, 64, d], 0.2)
            self.g_s = _mlp([n_seg_feat, 256, 128, 64, d], 0.3)
        if use_collab:
            self.u_id = nn.Embedding(n_users, d_collab)
            self.s_id = nn.Embedding(n_segs, d_collab)
            nn.init.normal_(self.u_id.weight, std=0.01)
            nn.init.normal_(self.s_id.weight, std=0.01)
        if self.adaptive_alpha:
            # alpha(u,s) = sigmoid(w0 + w1*log_cnt_u + w2*log_cnt_s); init -> ~0.7
            self.alpha_w = nn.Parameter(torch.tensor([0.85, 0.0, 0.0]))

    def _alpha(self, log_cnt_u, log_cnt_s):
        if not self.adaptive_alpha:
            return self.alpha
        w = self.alpha_w
        return torch.sigmoid(w[0] + w[1] * log_cnt_u + w[2] * log_cnt_s)

    def score(self, u_feat, s_feat, u_idx, s_idx, log_cnt_u=None, log_cnt_s=None):
        out = 0.0
        if self.use_content:
            content = (self.g_u(u_feat) * self.g_s(s_feat)).sum(-1)
            a = self._alpha(log_cnt_u, log_cnt_s) if self.use_collab else 1.0
            out = out + a * content
        if self.use_collab:
            collab = (self.u_id(u_idx) * self.s_id(s_idx)).sum(-1)
            if self.use_content:
                a = self._alpha(log_cnt_u, log_cnt_s)
                out = out + (1 - a) * collab
            else:
                out = out + collab
        return out

    def forward(self, u_feat, s_feat, u_idx, s_pos, s_neg,
                s_feat_pos, s_feat_neg, log_cnt_u=None, log_cnt_s_pos=None,
                log_cnt_s_neg=None):
        pos = self.score(u_feat, s_feat_pos, u_idx, s_pos, log_cnt_u, log_cnt_s_pos)
        neg = self.score(u_feat, s_feat_neg, u_idx, s_neg, log_cnt_u, log_cnt_s_neg)
        return pos, neg


def bpr_loss(pos: torch.Tensor, neg: torch.Tensor) -> torch.Tensor:
    return -torch.log(torch.sigmoid(pos - neg) + 1e-8).mean()
