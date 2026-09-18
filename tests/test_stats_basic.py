import pytest

from stats.basic import basic_stats, per_document_stats, pos_composition, standardized_ttr, ttr
from tests.helpers import make_tokens


def test_ttr_hand_computed():
    assert ttr(["a", "a", "b"]) == pytest.approx(2 / 3)
    assert ttr([]) is None


def test_standardized_ttr_hand_computed():
    # 区切り幅2: [a,a]→0.5, [b,c]→1.0, 端数 [d] は捨てる → 平均 0.75
    assert standardized_ttr(["a", "a", "b", "c", "d"], window=2) == pytest.approx(0.75)
    # 区切り幅より短ければ計算しない
    assert standardized_ttr(["a", "b"], window=3) is None


def test_basic_stats_with_and_without_function_words():
    toks = make_tokens([["私", "は", "本", "を", "読む"], ["本", "を", "読む"]], function_words={"は", "を"})
    s_ex = basic_stats(toks, unit="lemma", include_function_words=False, sttr_window=1000)
    s_in = basic_stats(toks, unit="lemma", include_function_words=True, sttr_window=1000)
    assert s_ex["n_tokens_all"] == 8
    assert s_ex["n_tokens"] == 5           # 私 本 読む 本 読む
    assert s_ex["n_types"] == 3            # 私 本 読む
    assert s_ex["ttr"] == pytest.approx(3 / 5)
    assert s_in["n_tokens"] == 8
    assert s_in["n_types"] == 5            # 私 は 本 を 読む
    assert s_ex["sttr"] is None            # 1000語未満
    assert s_ex["n_documents"] == 2


def test_per_document_stats():
    toks = make_tokens([["a", "a", "b"], ["c"]])
    df = per_document_stats(toks, unit="lemma", include_function_words=True, sttr_window=1000)
    assert df["n_tokens"].tolist() == [3, 1]
    assert df["n_types"].tolist() == [2, 1]
    assert df["ttr"].tolist() == pytest.approx([2 / 3, 1.0])


def test_pos_composition():
    toks = make_tokens([["私", "は", "本"]], function_words={"は"})
    df = pos_composition(toks)
    assert dict(zip(df["pos"], df["count"])) == {"内容": 2, "機能": 1}
    assert df["ratio"].sum() == pytest.approx(1.0)
