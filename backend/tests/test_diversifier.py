"""MMR diversity unit tests (fast, no model/data)."""
from __future__ import annotations

from src.diversifier import jaccard, mmr_select


def test_jaccard():
    assert jaccard({1, 2, 3}, {1, 2, 3}) == 1.0
    assert jaccard({1, 2}, {3, 4}) == 0.0
    assert jaccard({1, 2, 3, 4}, {3, 4}) == 0.5


def test_mmr_prefers_diverse():
    # 0 and 1 are identical; 2 is disjoint. With 0 as seed, MMR should pick 2 next.
    sets = [{1, 2, 3}, {1, 2, 3}, {7, 8, 9}]
    rel = [1.0, 0.99, 0.5]
    chosen = mmr_select(sets, rel, n=2)
    assert chosen[0] == 0
    assert chosen[1] == 2


def test_mmr_drops_near_duplicates():
    # two clusters, each with a >0.85-similar pair -> asking for 4 returns 2
    sets = [set(range(10)), set(range(11)),            # Jaccard 10/11 = 0.909
            set(range(20, 30)), set(range(20, 31))]    # Jaccard 0.909
    rel = [1.0, 0.9, 0.8, 0.7]
    chosen = mmr_select(sets, rel, n=4, max_sim=0.85)
    assert len(chosen) == 2                            # one per distinct cluster


def test_mmr_empty():
    assert mmr_select([], []) == []
