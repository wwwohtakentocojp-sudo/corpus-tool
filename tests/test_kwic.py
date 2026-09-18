from stats.kwic import find_hits, kwic, sort_kwic
from tests.helpers import make_tokens


def _toks():
    return make_tokens([["a", "b", "c", "d", "e"], ["c", "f", "g"]])


def test_kwic_respects_document_boundaries():
    df = kwic(_toks(), "c", unit="lemma", window=2)
    assert len(df) == 2
    r0 = df.iloc[0]
    assert (r0.L2, r0.L1, r0.KWIC, r0.R1, r0.R2) == ("a", "b", "c", "d", "e")
    r1 = df.iloc[1]
    # 文書2の先頭なので、左文脈は空（文書1の末尾 e を拾ってはいけない）
    assert (r1.L2, r1.L1, r1.KWIC, r1.R1, r1.R2) == ("", "", "c", "f", "g")
    assert r1.left == "" and r1.right == "f g"


def test_kwic_right_edge():
    df = kwic(_toks(), "e", unit="lemma", window=2)
    r = df.iloc[0]
    assert (r.L2, r.L1, r.R1, r.R2) == ("c", "d", "", "")


def test_kwic_no_hits_returns_empty_with_columns():
    df = kwic(_toks(), "zzz", unit="lemma", window=3)
    assert len(df) == 0
    assert "KWIC" in df.columns and "L3" in df.columns and "R3" in df.columns


def test_kwic_regex_and_sort():
    df = kwic(_toks(), "[cf]", unit="lemma", window=1, regex=True)
    assert sorted(df["KWIC"].tolist()) == ["c", "c", "f"]
    s = sort_kwic(df, "R1")
    assert s["R1"].tolist() == sorted(df["R1"].tolist())


def test_kwic_matches_label_and_reports_key():
    from corpus.models import Token, tokens_to_frame
    from stats.kwic import matched_keys

    toks = tokens_to_frame([
        Token("ライト", "ライト-light（光）", "名詞", 0, 0, lemma_label="ライト"),
        Token("を", "を", "助詞", 0, 1),
        Token("ライト", "ライト-light（軽い）", "名詞", 0, 2, lemma_label="ライト"),
    ])
    # 表示名で検索すると両方ヒットし、key 列で区別できる
    df = kwic(toks, "ライト", unit="lemma", window=1)
    assert df["key"].tolist() == ["ライト-light（光）", "ライト-light（軽い）"]
    assert matched_keys(toks, find_hits(toks, "ライト"), "lemma").to_dict() == {"ライト-light（光）": 1, "ライト-light（軽い）": 1}
    # 集計キーで検索すると1つに絞れる
    assert len(kwic(toks, "ライト-light（光）", unit="lemma", window=1)) == 1


def test_find_hits_case():
    toks = make_tokens([["Essen", "essen"]])
    assert find_hits(toks, "Essen", unit="lemma", case_sensitive=True).tolist() == [0]
    assert find_hits(toks, "essen", unit="lemma", case_sensitive=False).tolist() == [0, 1]
