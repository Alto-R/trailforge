"""persona catalog + default prefs + cold-user u_feat construction (板块B)."""
from __future__ import annotations

import numpy as np
import pytest

from src import persona


def test_catalog_has_five():
    cat = persona.personas()
    assert len(cat) == 5
    for p in cat:
        assert {"id", "label", "description", "size", "default_prefs"} <= set(p)
    assert sum(p["size"] for p in cat) == 603        # the clustered active users


def test_default_prefs_sum_to_one():
    for p in persona.personas():
        dp = p["default_prefs"]
        assert set(dp) == set(persona.PREF_MAP)
        assert sum(dp.values()) == pytest.approx(1.0, abs=1e-2)


def test_default_prefs_of():
    cat = persona.personas()
    dp = persona.default_prefs_of(cat[0]["id"], cat)
    assert dp == cat[0]["default_prefs"]
    with pytest.raises(KeyError):
        persona.default_prefs_of("nope", cat)


def test_u_feat_layout(meta):
    cat = persona.personas()
    u_cols = meta["u_cols"]
    p0 = cat[0]
    vec = persona.persona_u_feat(p0["id"], meta, cat)

    assert vec.shape == (len(u_cols),) == (24,)
    onehot = np.array([vec[u_cols.index(c)] for c in meta["cluster_cols"]])
    assert onehot.sum() == pytest.approx(1.0)
    assert vec[u_cols.index(f"u_cluster_{p0['cluster']}")] == pytest.approx(1.0)
    for c, m in meta["llm_means"].items():
        assert vec[u_cols.index(c)] == pytest.approx(m, abs=1e-5)
    assert vec[u_cols.index(meta["flag_col"])] == 0.0


def test_unknown_persona_raises(meta):
    with pytest.raises(KeyError):
        persona.persona_u_feat("does-not-exist", meta)
