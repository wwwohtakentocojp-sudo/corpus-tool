from interpretations.explainer import H_DONT, H_FACT, H_NEXT, H_PAPER, ExplainInput, explain, explain_sections
from interpretations.flags import make_flag

TH = {"log_dice_strong": 7.0, "dp_skew": 0.5, "mi_meaningful": 3.0, "g2_significant": 6.63}


def _colloc(flags):
    return ExplainInput(
        screen="collocation",
        metrics={"cooccur": 12, "freq_node": 644, "freq_collocate": 30, "mi": 9.8, "t": 3.4, "log_dice": 8.1, "g2": 45.2, "p": 0.0001, "n_total": 170478},
        flags=flags, words={"WORD": "先生", "COLLOCATE": "奥さん"}, settings={"window_label": "同一文内"},
    )


def test_no_flags_only_fact_and_paper():
    secs = explain_sections(_colloc([]), TH)
    assert [h for h, _ in secs] == [H_FACT, H_PAPER]
    text = explain(_colloc([]), TH)
    assert H_DONT not in text and H_NEXT not in text
    assert "注意" not in text.split(H_PAPER)[0]  # 代替文を出さない
    assert "『先生』と『奥さん』は 12 回一緒に出ており" in text and "目安の 7 を上回り" in text
    assert "結びつきありの水準" in text and "偶然では説明しにくい水準です。" in text


def _disagree(flags):
    return ExplainInput(
        screen="collocation",
        metrics={"cooccur": 23, "freq_node": 644, "freq_collocate": 64, "mi": 0.36, "t": 1.05, "log_dice": 9.78, "g2": 1.4, "p": 0.24, "n_total": 170478},
        flags=flags, words={"WORD": "先生", "COLLOCATE": "顔"}, settings={"window_label": "同一文内"},
    )


def test_disagreement_stated_first_and_not_called_strong():
    text = explain(_disagree([]), TH)
    assert "結びつきが強い水準" not in text
    facts = dict(explain_sections(_disagree([]), TH))[H_FACT]
    assert facts[0].startswith("『先生』と『顔』は、指標によって評価が分かれます。")
    assert "特別な結びつきとは言えません" in facts[0]


def test_not_distinguishable_gives_dont_section_and_avoids_significance_wording():
    flags = [make_flag("NOT_DISTINGUISHABLE", g2=1.4, threshold=6.63)]
    secs = dict(explain_sections(_disagree(flags), TH))
    assert H_DONT in secs and "判断がつかない" in secs[H_DONT][0]
    assert secs[H_NEXT] == ["この組み合わせについては結論を出さず、データを増やすか、別の組み合わせを検討してください。"]
    assert secs[H_FACT][0].startswith("『先生』と『顔』は、指標によって評価が分かれます。")
    text = explain(_disagree(flags), TH)
    assert "有意" not in text and "偶然の範囲" not in text


def test_disagreement_not_repeated_when_both_high_flag_present():
    flags = [make_flag("BOTH_HIGH_FREQUENCY", freq_node=644, freq_collocate=2721, top_percent=1.0)]
    facts = dict(explain_sections(_disagree(flags), TH))[H_FACT]
    assert not any("指標によって評価が分かれます" in f for f in facts)


def test_flag_rows_only_and_no_generic_cautions():
    flags = [make_flag("LOW_COOCCURRENCE", cooccur=12, threshold=20, mi_note="特に珍しさ重視の指標（MI = 9.8）が高く出ていますが、これは回数が少ないときに起こりやすい現象です。")]
    secs = dict(explain_sections(_colloc(flags), TH))
    assert secs[H_DONT] == [flags[0].message]           # フラグ由来の行だけ
    assert len(secs[H_NEXT]) == 1 and "KWIC" in secs[H_NEXT][0] and "12 件" in secs[H_NEXT][0]
    assert "指標の値自体が安定しません" in secs[H_FACT][0]
    text = explain(_colloc(flags), TH)
    assert "過大評価" not in text  # 用語辞書の一般的注意は出さない


def test_table_only_flag_is_not_explained():
    flags = [make_flag("LOW_COOCCURRENCE_MINOR", cooccur=2)]
    secs = dict(explain_sections(_colloc(flags), TH))
    assert H_DONT not in secs and H_NEXT not in secs
    assert "一緒に出ており" in secs[H_FACT][0]  # フラグ無し扱いで水準文になる
    assert "少ない" not in explain(_colloc(flags), TH)


def test_different_flags_give_different_dont_sections():
    a = dict(explain_sections(_colloc([make_flag("LOW_COOCCURRENCE", cooccur=12, threshold=20, mi_note="")]), TH))
    b = dict(explain_sections(_colloc([make_flag("BOTH_HIGH_FREQUENCY", freq_node=644, freq_collocate=2721, top_percent=1.0)]), TH))
    assert a[H_DONT] != b[H_DONT] and a[H_NEXT] != b[H_NEXT] and a[H_FACT] != b[H_FACT]


def test_zero_corrected_keyness_names_groups_and_omits_odds_ratio():
    inp = ExplainInput(
        screen="keyness",
        metrics={"freq_a": 0, "freq_b": 44, "n_a": 166535, "n_b": 3943, "pmw_a": 0.0, "pmw_b": 11159.0,
                 "log_ratio": -11.88, "g2": 331.5, "p": 1e-10, "odds_ratio": float("nan")},
        flags=[make_flag("ZERO_CORRECTED", word="下人")],
        words={"WORD": "下人", "GROUP_A": "夏目漱石", "GROUP_B": "芥川龍之介"},
    )
    text = explain(inp, TH)
    assert "「芥川龍之介」グループに 44 回出ていますが、「夏目漱石」グループには一度も出ていません" in text
    assert "0.5 を加えて算出" in text
    assert "オッズ比は算出していません" in text
    assert "3801" not in text  # 補正で生じる人工的な値を出さない


def test_frequency_dp_unreliable_omits_dp_from_paper_sentence():
    inp = ExplainInput(
        screen="frequency", metrics={"freq": 507, "pmw": 2974.0, "dp": 0.6, "n_parts": 3, "n_total": 170478},
        flags=[make_flag("DP_TOO_FEW_PARTS", n_parts=3, threshold=10)], words={"WORD": "俺"},
    )
    secs = dict(explain_sections(inp, TH))
    assert "DP" not in secs[H_PAPER][0]
    assert "参考値" in secs[H_FACT][0]


def test_fact_section_at_most_two_sentences():
    flags = [
        make_flag("BOTH_HIGH_FREQUENCY", freq_node=644, freq_collocate=2721, top_percent=1.0),
        make_flag("T_HIGH_MI_LOW", t=5.97, mi=0.57),
        make_flag("LOW_COOCCURRENCE", cooccur=12, threshold=20, mi_note=""),
    ]
    secs = dict(explain_sections(_colloc(flags), TH))
    assert len(secs[H_FACT]) == 2
    assert len(secs[H_DONT]) == 3  # 言ってはいけないことは全フラグ分
