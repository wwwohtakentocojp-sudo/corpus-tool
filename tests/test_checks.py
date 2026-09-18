import pandas as pd

from corpus.checks import group_columns, group_sizes, pre_analysis_flags
from corpus.models import Corpus
from stats.basic import per_group_stats
from tests.helpers import make_tokens

TH = {"corpus_min_tokens": 5, "group_imbalance_ratio": 3.0}


def _corpus():
    toks = make_tokens([["a", "b"], ["c", "d", "e"], ["f"], ["g", "h"]])
    docs = pd.DataFrame(
        {"doc_id": [0, 1, 2, 3], "name": ["d0", "d1", "d2", "d3"], "n_chars": [2, 3, 1, 2],
         "year": ["2000", "2000", "2000", "2020"], "encoding": ["utf-8"] * 4}
    )
    return Corpus(language="ja", documents=docs, tokens=toks)


def test_group_columns_excludes_standard_columns():
    assert group_columns(_corpus()) == ["year"]


def test_group_sizes():
    g = group_sizes(_corpus(), "year").set_index("year")
    assert g.loc["2000", "n_documents"] == 3 and g.loc["2000", "n_tokens"] == 6
    assert g.loc["2020", "n_documents"] == 1 and g.loc["2020", "n_tokens"] == 2


def test_pre_analysis_flags_include_group_imbalance():
    # 2000年代 3文書 vs 2020年代 1文書 = 3.0 倍。閾値ちょうどでは出ず、閾値を下回れば出る
    assert [f.code for f in pre_analysis_flags(_corpus(), TH)] == []
    flags = pre_analysis_flags(_corpus(), {"corpus_min_tokens": 5, "group_imbalance_ratio": 2.5})
    assert [f.code for f in flags] == ["GROUP_IMBALANCE"]
    assert "2000" in flags[0].message and "2020" in flags[0].message


def test_per_group_stats_concatenates_documents():
    c = _corpus()
    dg = c.documents.set_index("doc_id")["year"]
    df = per_group_stats(c.tokens, dg, unit="lemma", include_function_words=True, sttr_window=2).set_index("group")
    assert df.loc["2000", "n_documents"] == 3 and df.loc["2000", "n_tokens"] == 6
    # 2語ずつ [a,b],[c,d],[e,f] → 各 TTR 1.0 → 平均 1.0
    assert df.loc["2000", "sttr"] == 1.0
    assert df.loc["2020", "sttr"] == 1.0
