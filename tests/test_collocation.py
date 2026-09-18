"""コロケーション指標を手計算値と照合する。"""
import math

import pytest

from corpus.models import Token, tokens_to_frame
from stats.collocation import association_measures, collocate_occurrences, collocation_table, log_likelihood_2x2
from stats.kwic import find_hits
from tests.helpers import make_tokens


def test_association_measures_hand_computed():
    # N=100, f(n)=10, f(c)=5, W=2, O=3 → E = 10*5*2/100 = 1
    m = association_measures(o=3, fn=10, fc=5, n=100, w=2)
    assert m["expected"] == pytest.approx(1.0)
    assert m["mi"] == pytest.approx(math.log2(3))                      # 1.585
    assert m["t"] == pytest.approx((3 - 1) / math.sqrt(3))              # 1.155
    assert m["log_dice"] == pytest.approx(14 + math.log2(6 / 15))       # 12.678
    # G²: a=3, b=5-3=2, c=10*2-3=17, d=100-3-2-17=78
    assert m["g2"] == pytest.approx(log_likelihood_2x2(3, 2, 17, 78))
    assert 0 < m["p"] < 1


def test_log_likelihood_2x2_hand_computed():
    # a=10,b=20,c=30,d=40: 行和 30/70, 列和 40/60, N=100
    a, b, c, d = 10, 20, 30, 40
    ea, eb, ec, ed = 30 * 40 / 100, 30 * 60 / 100, 70 * 40 / 100, 70 * 60 / 100
    expected = 2 * (a * math.log(a / ea) + b * math.log(b / eb) + c * math.log(c / ec) + d * math.log(d / ed))
    assert log_likelihood_2x2(a, b, c, d) == pytest.approx(expected)
    # 独立なら 0
    assert log_likelihood_2x2(10, 10, 10, 10) == pytest.approx(0.0)


def _sent_tokens():
    # 文0: 私 は 本 を 読む / 文1: 本 を 買う / 文2（別文書）: 読む
    toks = []
    for i, w in enumerate(["私", "は", "本", "を", "読む"]):
        toks.append(Token(w, w, "機能" if w in {"は", "を"} else "内容", 0, i, 0, is_function=w in {"は", "を"}))
    for i, w in enumerate(["本", "を", "買う"]):
        toks.append(Token(w, w, "機能" if w == "を" else "内容", 0, 5 + i, 1, is_function=w == "を"))
    toks.append(Token("読む", "読む", "内容", 1, 0, 0))
    return tokens_to_frame(toks)


def test_fixed_window_respects_doc_boundary_and_counts():
    t = _sent_tokens()
    hits = find_hits(t, "本")
    occ, w = collocate_occurrences(t, hits, "fixed", window=1)
    assert w == 2.0
    # 本(位置2): は(1), を(3) / 本(位置5): 読む(4), を(6)。別文書の 読む(doc1) は拾わない
    words = sorted(t.iloc[occ["idx"]]["lemma"].tolist())
    assert words == sorted(["は", "を", "読む", "を"])
    assert set(t.iloc[occ["idx"]]["doc_id"]) == {0}


def test_sentence_window():
    t = _sent_tokens()
    hits = find_hits(t, "本")
    occ, w = collocate_occurrences(t, hits, "sentence")
    # 文0 は本を除いて 4 語、文1 は 2 語 → W = 3.0
    assert w == pytest.approx(3.0)
    assert len(occ) == 6


def test_collocation_table_sorted_by_logdice_and_excludes_self():
    t = _sent_tokens()
    df = collocation_table(t, "本", unit="lemma", method="sentence", min_cooccur=1)
    assert "本" not in df["collocate"].tolist()
    assert df["log_dice"].is_monotonic_decreasing
    row = df.set_index("collocate").loc["を"]
    assert row["cooccur"] == 2 and row["freq_node"] == 2 and row["freq_collocate"] == 2
    # N=9, W=3: E = 2*2*3/9 = 1.333, MI = log2(2/1.333)
    assert row["mi"] == pytest.approx(math.log2(2 / (4 * 3 / 9)))
    assert bool(row["is_function"]) is True


def test_dependency_window():
    toks = [
        Token("She", "she", "PRON", 0, 0, 0, dep="nsubj", head=1, is_function=True),
        Token("reads", "read", "VERB", 0, 1, 0, dep="ROOT", head=-1),
        Token("books", "book", "NOUN", 0, 2, 0, dep="obj", head=1),
        Token(".", ".", "PUNCT", 0, 3, 0, dep="punct", head=1, is_function=True),
    ]
    t = tokens_to_frame(toks)
    df = collocation_table(t, "read", unit="lemma", method="dependency", min_cooccur=1).set_index("collocate")
    assert df.loc["book", "relation"] == "obj"
    assert df.loc["she", "relation"] == "nsubj"
    # 逆方向: book の係り先が read
    df2 = collocation_table(t, "book", unit="lemma", method="dependency", min_cooccur=1).set_index("collocate")
    assert df2.loc["read", "relation"] == "→obj"


def test_no_hits_returns_empty():
    assert collocation_table(_sent_tokens(), "存在しない").empty
