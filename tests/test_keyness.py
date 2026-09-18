import math

import pytest

from stats.keyness import keyness_table, log_likelihood_keyness, log_ratio, odds_ratio, split_by_group
from tests.helpers import make_tokens


def test_log_ratio_hand_computed():
    # A: 10/1000 = 0.01, B: 5/2000 = 0.0025 → 4倍 → log2 = 2
    lr, corrected = log_ratio(10, 5, 1000, 2000)
    assert lr == pytest.approx(2.0) and corrected is False
    # 片方が 0 なら 0.5 補正
    lr0, corrected0 = log_ratio(10, 0, 1000, 2000)
    assert corrected0 is True
    assert lr0 == pytest.approx(math.log2((10.5 / 1000) / (0.5 / 2000)))
    # 逆方向は負
    assert log_ratio(5, 10, 2000, 1000)[0] == pytest.approx(-2.0)


def test_log_likelihood_keyness_hand_computed():
    fa, fb, na, nb = 10, 5, 1000, 2000
    ea = na * 15 / 3000
    eb = nb * 15 / 3000
    expected = 2 * (fa * math.log(fa / ea) + fb * math.log(fb / eb))
    assert log_likelihood_keyness(fa, fb, na, nb) == pytest.approx(expected)
    # 比率が同じなら 0
    assert log_likelihood_keyness(10, 20, 1000, 2000) == pytest.approx(0.0)


def test_odds_ratio():
    assert odds_ratio(10, 5, 1000, 2000) == pytest.approx((10 / 990) / (5 / 1995))
    # 片方が 0 なら算出しない
    assert math.isnan(odds_ratio(10, 0, 1000, 2000))


def test_keyness_table_and_direction():
    a = make_tokens([["x"] * 10 + ["y"] * 10 + ["z"] * 80])
    b = make_tokens([["x"] * 2 + ["y"] * 10 + ["w"] * 88])
    df = keyness_table(a, b, unit="lemma", include_function_words=True).set_index("word")
    assert df.loc["x", "freq_a"] == 10 and df.loc["x", "freq_b"] == 2
    assert df.loc["x", "log_ratio"] == pytest.approx(math.log2((10 / 100) / (2 / 100)))
    assert df.loc["x", "direction"] == "A"
    assert df.loc["y", "log_ratio"] == pytest.approx(0.0) and df.loc["y", "direction"] == "="
    assert df.loc["w", "direction"] == "B" and bool(df.loc["w", "zero_corrected"]) is True
    assert math.isnan(df.loc["w", "odds_ratio"])
    assert df.loc["x", "pmw_a"] == pytest.approx(100000.0)
    # 並びは log_ratio 降順
    assert df["log_ratio"].is_monotonic_decreasing


def test_split_by_group_rest():
    import pandas as pd

    toks = make_tokens([["a"], ["b"], ["c"]])
    docs = pd.DataFrame({"doc_id": [0, 1, 2], "year": ["2000", "2010", "2020"]})
    ta, tb = split_by_group(toks, docs, "year", "2000", None)
    assert ta["lemma"].tolist() == ["a"] and sorted(tb["lemma"].tolist()) == ["b", "c"]
    ta, tb = split_by_group(toks, docs, "year", "2000", "2020")
    assert tb["lemma"].tolist() == ["c"]
