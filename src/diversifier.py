"""MMR diversity control (主计划 §5.4.5).

From a pool of candidate routes, pick ``n`` that balance relevance against
mutual diversity, so the user sees genuinely different-style options rather than
near-duplicates. Relevance = each route's mean injected segment score; route
similarity = Jaccard over segment sets. Maximal Marginal Relevance:

    next = argmax_i [ beta * rel_i - (1 - beta) * max_j Jaccard(i, selected_j) ]

beta = 0.7 (plan default). The seed is the highest-relevance route.
"""
from __future__ import annotations


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def mmr_select(seg_sets: list[set], relevance: list[float],
               n: int = 4, beta: float = 0.7, max_sim: float = 0.85) -> list[int]:
    """Return indices of the selected routes, in selection order (most relevant
    first, then diversified). Stops early when no remaining route is diverse
    enough (similarity to every selected route > ``max_sim``): on this sparse
    network a start may support fewer than ``n`` genuinely distinct routes, and
    padding with near-duplicates is worse than returning fewer (honest §95)."""
    k = len(seg_sets)
    if k == 0:
        return []
    lo, hi = min(relevance), max(relevance)
    rng = (hi - lo) or 1.0
    rel = [(r - lo) / rng for r in relevance]        # normalise to [0, 1]

    remaining = set(range(k))
    seed = max(remaining, key=lambda i: rel[i])
    chosen = [seed]
    remaining.discard(seed)

    def sim_to_chosen(i: int) -> float:
        return max(jaccard(seg_sets[i], seg_sets[j]) for j in chosen)

    while remaining and len(chosen) < n:
        diverse = [i for i in remaining if sim_to_chosen(i) <= max_sim]
        if not diverse:                              # nothing distinct enough left
            break
        nxt = max(diverse, key=lambda i: beta * rel[i] - (1.0 - beta) * sim_to_chosen(i))
        chosen.append(nxt)
        remaining.discard(nxt)
    return chosen
