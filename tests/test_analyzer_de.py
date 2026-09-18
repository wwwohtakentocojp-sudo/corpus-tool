"""ドイツ語解析器のテスト（§11）。"""
import io

import pandas as pd
import pytest

from analyzers import german_normalize as gn
from analyzers.german import GermanAnalyzer, split_compound
from corpus.models import tokens_to_frame
from stats.frequency import expand_compounds, frequency_table


@pytest.fixture(scope="module")
def de():
    return GermanAnalyzer()


def _df(de, text, **opts):
    return tokens_to_frame(de.process(text, 0, opts))


# --- 複合語分割 ------------------------------------------------------------------
def test_compound_split_function():
    assert split_compound("Autobahnraststätte") == ["Autobahn", "Raststätte"]
    assert split_compound("Haus") == []          # 分けられない語
    assert split_compound("Essen") == []


def test_compound_split_on_adds_parts_and_keeps_original(de):
    df = _df(de, "Die Autobahnraststätte war voll.", compound_split=True)
    row = df[df["surface"] == "Autobahnraststätte"].iloc[0]
    assert row["lemma"] == "Autobahnraststätte"           # 元の語はそのまま
    assert row["compound_parts"] == "Autobahn+Raststätte"
    # 「分割した場合」の集計では構成要素が語になる
    ex = expand_compounds(df)
    ft = frequency_table(ex, unit="lemma", include_function_words=True).set_index("word")
    assert ft.loc["Autobahn", "freq"] == 1 and ft.loc["Raststätte", "freq"] == 1
    assert "Autobahnraststätte" not in ft.index


def test_compound_split_off_by_default(de):
    df = _df(de, "Die Autobahnraststätte war voll.")
    assert (df["compound_parts"] == "").all()
    assert de.default_options()["compound_split"] is False


# --- 分離動詞 --------------------------------------------------------------------
def test_separable_verb_recombined(de):
    df = _df(de, "Ich rufe dich an.")
    assert "anrufen" in df["lemma"].tolist()
    # 前綴りは機能語扱いになり、内容語の集計には出ない
    ft = frequency_table(df, unit="lemma", include_function_words=False).set_index("word")
    assert ft.loc["anrufen", "freq"] == 1
    assert "rufen" not in ft.index


def test_separable_verb_off(de):
    df = _df(de, "Ich rufe dich an.", separable_verbs=False)
    lemmas = df["lemma"].tolist()
    assert "rufen" in lemmas and "anrufen" not in lemmas
    assert any("分離動詞" in w for w in de.language_warnings({"separable_verbs": False}))


# --- 小文字化 --------------------------------------------------------------------
def test_essen_noun_and_verb_stay_separate_when_lowercase_off(de):
    df = _df(de, "Das Essen ist gut. Wir essen Brot.")
    ft = frequency_table(df, unit="lemma", include_function_words=True).set_index("word")
    assert ft.loc["Essen", "freq"] == 1
    assert ft.loc["essen", "freq"] == 1
    assert de.default_options()["lowercase"] is False


def test_lowercase_on_merges_and_warns(de):
    df = _df(de, "Das Essen ist gut. Wir essen Brot.", lowercase=True)
    ft = frequency_table(df, unit="lemma", include_function_words=True).set_index("word")
    assert ft.loc["essen", "freq"] == 2
    assert any("Essen" in w and "essen" in w for w in de.language_warnings({"lowercase": True}))


# --- 見出し語化モード ------------------------------------------------------------
def test_lemma_modes(de):
    spacy_df = _df(de, "Die Kinder gingen nach Hause.", lemma_mode="spacy")
    hanta_df = _df(de, "Die Kinder gingen nach Hause.", lemma_mode="hanta")
    both_df = _df(de, "Die Kinder gingen nach Hause.", lemma_mode="both")
    assert "Kind" in spacy_df["lemma"].tolist()
    assert "Kind" in hanta_df["lemma"].tolist()
    assert "gehen" in hanta_df["lemma"].tolist()
    # both: 集計は spaCy、lemma_alt に HanTa
    assert both_df["lemma"].tolist() == spacy_df["lemma"].tolist()
    assert "gehen" in both_df["lemma_alt"].tolist()


# --- 正書法 ----------------------------------------------------------------------
def test_orthography_1996_table():
    assert gn.normalize_1996("Ich weiß, daß er es wußte. Daß!") == "Ich weiß, dass er es wusste. Dass!"
    # 長母音の後の ß は改革後も変わらない
    assert gn.normalize_1996("Die Straße ist groß.") == "Die Straße ist groß."
    assert gn.normalize_ss("Straße groß") == "Strasse gross"
    assert gn.normalize_umlaut("Über Äpfel und Öl für müde Bären") == "Ueber Aepfel und Oel fuer muede Baeren"


def test_orthography_defaults_off_and_applied_via_options(de):
    assert de.normalize("daß") == "daß"
    assert de.normalize("daß", {"norm_1996": True}) == "dass"
    assert de.normalize("Straße", {"norm_ss": True}) == "Strasse"


def test_mixed_orthography_detected_and_suggested(de):
    old = "Er sagte, daß er es wußte. Sie wußte, daß es so war. Ich weiß, daß du mußt. "
    new = "Er sagte, dass er es wusste. Sie wusste, dass es so war. Ich weiß, dass du musst. "
    warnings = de.data_warnings([old, new])
    assert len(warnings) == 1
    assert warnings[0]["suggest_option"] == "norm_1996"
    assert "表記ゆれ" in warnings[0]["message"]
    # どちらか一方だけなら提案しない
    assert de.data_warnings([new]) == []
    # 既に正規化 ON なら提案しない
    assert de.data_warnings([old, new], {"norm_1996": True}) == []


# --- ウムラウトを含む語の頻度と CSV ----------------------------------------------------
def test_umlaut_words_count_and_csv_roundtrip(de):
    from ui.components import csv_bytes

    df = _df(de, "Die Bäume sind schön. Die Bäume blühen. Über den Bäumen.")
    ft = frequency_table(df, unit="lemma", include_function_words=False)
    assert int(ft.set_index("word").loc["Baum", "freq"]) == 3
    data = csv_bytes(ft)
    assert data.startswith(b"\xef\xbb\xbf")  # UTF-8 with BOM（Excel で文字化けしない）
    back = pd.read_csv(io.BytesIO(data), encoding="utf-8-sig")
    assert "Baum" in back["word"].tolist()
    assert "schön" in back["word"].tolist()


def test_dependency_columns_present(de):
    df = _df(de, "Ich rufe dich an.")
    assert de.supports_dependency()
    assert "svp" in df["dep"].tolist()
    prefix = df[df["dep"] == "svp"].iloc[0]
    assert df.loc[df["position"] == prefix["head"], "surface"].iloc[0] == "rufe"
