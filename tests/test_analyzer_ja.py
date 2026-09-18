"""日本語解析器（fugashi + unidic-lite）のテスト。"""
import pytest

from analyzers.japanese import JapaneseAnalyzer
from corpus.models import tokens_to_frame


@pytest.fixture(scope="module")
def ja():
    return JapaneseAnalyzer()


def _lemmas(ja, text, **opts):
    return [t.lemma for t in ja.process(text, 0, opts)]


def test_conjugated_forms_merge_into_lemma(ja):
    l1 = _lemmas(ja, "学校に行った。")
    l2 = _lemmas(ja, "学校に行きます。")
    assert "行く" in l1
    assert "行く" in l2


def test_function_words_flagged(ja):
    toks = ja.process("私は本を読む。", 0, {})
    df = tokens_to_frame(toks)
    fn = set(df.loc[df["is_function"], "surface"])
    content = set(df.loc[~df["is_function"], "surface"])
    assert {"は", "を", "。"} <= fn
    assert {"私", "本", "読む"} <= content


def test_function_word_toggle_changes_counts(ja):
    df = tokens_to_frame(ja.process("私は本を読む。", 0, {}))
    n_all = len(df)
    n_content = int((~df["is_function"]).sum())
    assert n_all > n_content
    assert n_content == 3


def test_lemma_unit_orth_base_keeps_spelling(ja):
    text = "そういうことだと言う。"
    merged = _lemmas(ja, text, lemma_unit="lemma")
    kept = _lemmas(ja, text, lemma_unit="orth_base")
    # 語彙素では「いう」と「言う」が同じ見出し語に統合される
    assert merged.count("言う") == 2
    # 書字形基本形では表記が保たれる
    assert "いう" in kept and "言う" in kept


def test_sentence_ids(ja):
    toks = ja.process("今日は晴れだ。明日は雨だ。", 0, {})
    assert {t.sentence_id for t in toks} == {0, 1}
    assert [t.position for t in toks] == list(range(len(toks)))


def test_nfkc_option(ja):
    with_norm = [t.surface for t in ja.process("ＡＢＣ", 0, {"nfkc": True})]
    without = [t.surface for t in ja.process("ＡＢＣ", 0, {"nfkc": False})]
    assert "ABC" in with_norm
    assert "ＡＢＣ" in without


def test_lemma_key_keeps_suffix_and_label_drops_it(ja):
    # UniDic の語彙素は「私-代名詞」「シャツ-shirt」のような区別用の接尾部を持つ。
    # 集計キー（lemma）には残し、表示名（lemma_label）では落とす。
    toks = ja.process("私はシャツを着た。", 0, {})
    by_surface = {t.surface: t for t in toks}
    assert by_surface["シャツ"].lemma == "シャツ-shirt"
    assert by_surface["シャツ"].lemma_label == "シャツ"
    assert by_surface["私"].lemma == "私-代名詞"
    assert by_surface["私"].lemma_label == "私"


def test_homographs_are_distinct_keys_with_same_label(ja):
    # unidic-lite は「ライト（光）」と「ライト（軽い）」を別の語彙素にする
    light = next(t for t in ja.process("右のライトを点けた。", 0, {}) if t.surface == "ライト")
    lite = next(t for t in ja.process("彼はライトだ。", 0, {}) if t.surface == "ライト")
    assert light.lemma_label == lite.lemma_label == "ライト"
    assert light.lemma != lite.lemma, "同形異義語の集計キーが統合されている"
    assert light.lemma == "ライト-light（光）"
    assert lite.lemma == "ライト-light（軽い）"


def test_language_warnings_mention_short_unit(ja):
    ws = ja.language_warnings({})
    assert any("短単位" in w for w in ws)
