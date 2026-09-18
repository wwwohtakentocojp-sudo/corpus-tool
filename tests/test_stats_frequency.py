"""頻度・pmw・DP を、手計算できる小さなデータで照合する。"""
import numpy as np
import pytest

from stats.frequency import dispersion_dp, frequency_table, word_distribution
from tests.helpers import make_tokens


def _corpus():
    # 文書サイズ 10, 20, 30（全60語）。語 X は 2, 0, 4 回。語 Y は 1, 2, 3 回（比例 = 均等）
    d0 = ["X", "X", "Y"] + ["z"] * 7
    d1 = ["Y", "Y"] + ["z"] * 18
    d2 = ["X"] * 4 + ["Y"] * 3 + ["z"] * 23
    assert (len(d0), len(d1), len(d2)) == (10, 20, 30)
    return make_tokens([d0, d1, d2])


def test_dispersion_dp_hand_computed():
    sizes = np.array([10.0, 20.0, 30.0])
    # s = 1/6, 1/3, 1/2 ; v = 1/3, 0, 2/3 → 0.5 * (1/6 + 1/3 + 1/6) = 1/3
    assert dispersion_dp(sizes, np.array([2.0, 0.0, 4.0])) == pytest.approx(1 / 3)
    # 完全に比例していれば 0
    assert dispersion_dp(sizes, np.array([1.0, 2.0, 3.0])) == pytest.approx(0.0)
    # 1文書に集中: v = (1,0,0), s = (1/6,1/3,1/2) → 0.5*(5/6+1/3+1/2) = 5/6
    assert dispersion_dp(sizes, np.array([5.0, 0.0, 0.0])) == pytest.approx(5 / 6)


def test_frequency_table_freq_pmw_dp():
    df = frequency_table(_corpus(), unit="lemma", include_function_words=True).set_index("word")
    assert df.loc["X", "freq"] == 6
    assert df.loc["Y", "freq"] == 6
    assert df.loc["z", "freq"] == 48
    # pmw: 6/60 * 1e6 = 100000
    assert df.loc["X", "pmw"] == pytest.approx(100000.0)
    assert df.loc["X", "dp"] == pytest.approx(1 / 3)
    assert df.loc["Y", "dp"] == pytest.approx(0.0)
    assert df.loc["X", "n_parts"] == 2
    assert df.loc["Y", "n_parts"] == 3
    # 順位は頻度の降順
    assert df.loc["z", "rank"] == 1


def test_pmw_denominator_is_all_tokens_even_when_function_words_excluded():
    toks = make_tokens([["a", "の", "a", "の"]], function_words={"の"})
    df = frequency_table(toks, unit="lemma", include_function_words=False).set_index("word")
    assert "の" not in df.index
    # 分母は 4（機能語込み）: 2/4 * 1e6
    assert df.loc["a", "pmw"] == pytest.approx(500000.0)


def test_homographs_stay_separate_but_share_label():
    """同形異義語は集計キー（接尾部付き）で別々に数え、表示名だけが同じになる。"""
    from corpus.models import Token, tokens_to_frame

    toks = [
        Token("ライト", "ライト-light（光）", "名詞", 0, 0, lemma_label="ライト"),
        Token("ライト", "ライト-light（光）", "名詞", 0, 1, lemma_label="ライト"),
        Token("ライト", "ライト-light（軽い）", "名詞", 0, 2, lemma_label="ライト"),
        Token("本", "本", "名詞", 0, 3),
    ]
    df = frequency_table(tokens_to_frame(toks), unit="lemma", include_function_words=True)
    light = df[df["label"] == "ライト"]
    assert len(light) == 2, "同形異義語が1行に統合されてはいけない"
    assert dict(zip(light["word"], light["freq"])) == {"ライト-light（光）": 2, "ライト-light（軽い）": 1}
    # 表層形で数えれば1行
    df_s = frequency_table(tokens_to_frame(toks), unit="surface", include_function_words=True)
    assert int(df_s.loc[df_s["word"] == "ライト", "freq"].iloc[0]) == 3
    assert (df_s["label"] == df_s["word"]).all()


def test_word_distribution():
    dist = word_distribution(_corpus(), "X", unit="lemma").set_index("doc_id")
    assert dist.loc[0, "freq"] == 2 and dist.loc[1, "freq"] == 0 and dist.loc[2, "freq"] == 4
    assert dist.loc[2, "share"] == pytest.approx(4 / 6)
    assert dist.loc[0, "pmw_in_part"] == pytest.approx(200000.0)
