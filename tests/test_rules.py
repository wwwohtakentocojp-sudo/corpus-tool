"""第2層の全フラグについて、閾値の境界値で ON/OFF が切り替わることを検証する。"""
import pandas as pd
import pytest

from app_config import load_config, thresholds
from interpretations.rules import (
    check_corpus_size,
    check_dispersion,
    check_dp_reliability,
    check_collocation_row,
    check_group_imbalance,
    check_keyness_row,
    check_low_frequency,
    flag_collocation_table,
    flag_frequency_table,
    flag_keyness_table,
    high_frequency_cutoff,
)


# --- BOTH_HIGH_FREQUENCY ---------------------------------------------------------
def test_high_frequency_cutoff():
    # 200 語 → 上位 1% = 2 語 → 2番目に多い語の頻度が境界
    freqs = list(range(1, 201))
    assert high_frequency_cutoff(freqs, TH) == 199
    # 語が少なくても最低1語
    assert high_frequency_cutoff([5, 3, 1], TH) == 5
    assert high_frequency_cutoff([], TH) > 10**6


@pytest.mark.parametrize(
    "fn, fc, cutoff, expected",
    [(100, 100, 100, True), (100, 99, 100, False), (99, 100, 100, False), (500, 2000, 100, True), (100, 100, None, False)],
)
def test_both_high_frequency_boundary(fn, fc, cutoff, expected):
    flags = check_collocation_row(1.0, 1.0, 50, False, True, TH, fn, fc, cutoff)
    assert ("BOTH_HIGH_FREQUENCY" in codes(flags)) is expected
    if expected:
        assert "1%" in flags[0].message


# --- LOW_COOCCURRENCE（段階A / 段階B） ---------------------------------------------
@pytest.mark.parametrize(
    "cooccur, mi, log_dice, g2, expected",
    [
        (19, 3.0, 0.0, 0.0, "A"),       # 回数少 + MI が目安以上
        (19, 0.0, 7.0, 0.0, "A"),       # 回数少 + logDice が目安以上
        (19, 0.0, 0.0, 6.63, "A"),      # 回数少 + G² が目安以上
        (19, 2.9, 6.9, 6.62, "B"),      # 回数少 + どれも目安未満
        (20, 9.0, 12.0, 100.0, None),   # 回数が閾値ちょうどなら出さない
        (16, 3.67, 9.64, 79.4, "A"),    # サンプル7（『先生』×『嘗て』）
        (3, 4.9, 7.25, 14.9, "A"),      # 旧 MI_HIGH_LOW_FREQ では漏れていた MI 4.9 の例
    ],
)
def test_low_cooccurrence_stages(cooccur, mi, log_dice, g2, expected):
    flags = check_collocation_row(mi, 0.0, cooccur, False, True, TH, g2=g2, log_dice=log_dice)
    c = codes(flags)
    assert ("LOW_COOCCURRENCE" in c) is (expected == "A")
    assert ("LOW_COOCCURRENCE_MINOR" in c) is (expected == "B")
    assert not ("LOW_COOCCURRENCE" in c and "LOW_COOCCURRENCE_MINOR" in c)  # 重複しない


def test_low_cooccurrence_mi_note_only_when_mi_high():
    with_note = next(f for f in check_collocation_row(5.2, 0.0, 3, False, True, TH, g2=14.9, log_dice=7.25) if f.code == "LOW_COOCCURRENCE")
    assert "MI = 5.2" in with_note.message and "回数が少ないときに起こりやすい" in with_note.message
    no_note = next(f for f in check_collocation_row(3.67, 0.0, 16, False, True, TH, g2=79.4, log_dice=9.64) if f.code == "LOW_COOCCURRENCE")
    assert "起こりやすい" not in no_note.message and no_note.message.endswith("確認してください。")


# --- T_HIGH_MI_LOW -------------------------------------------------------
@pytest.mark.parametrize(
    "t, mi, expected",
    [(2.0, 2.9, False), (2.01, 2.9, True), (2.01, 3.0, False), (12.1, 0.5, True)],
)
def test_T_HIGH_MI_LOW_boundary(t, mi, expected):
    flags = check_collocation_row(mi, t, 100, False, True, TH)
    assert ("T_HIGH_MI_LOW" in codes(flags)) is expected


# --- EFFECT_SIZE_TOO_SMALL -------------------------------------------------------
@pytest.mark.parametrize("lr, expected", [(0.99, True), (1.0, False), (-0.99, True), (-1.0, False), (3.2, False)])
def test_effect_size_boundary(lr, expected):
    assert ("EFFECT_SIZE_TOO_SMALL" in codes(check_keyness_row(lr, TH, "w"))) is expected


# --- NOT_DISTINGUISHABLE（特徴語） ------------------------------------------------
@pytest.mark.parametrize("g2, expected", [(6.62, True), (6.63, False), (None, False)])
def test_keyness_not_distinguishable(g2, expected):
    assert ("NOT_DISTINGUISHABLE" in codes(check_keyness_row(2.0, TH, "w", g2=g2))) is expected


def test_vectorized_collocation_and_keyness_flags_match_scalar():
    col = pd.DataFrame({"mi": [6.0, 1.0, 0.4, 0.5], "t": [1.0, 5.0, 1.0, 0.5], "cooccur": [3, 50, 23, 2], "is_function": [False, True, False, False],
                        "freq_node": [600, 600, 600, 600], "freq_collocate": [3, 2000, 64, 5], "g2": [14.9, 51.8, 1.4, 0.3],
                        "log_dice": [7.25, 11.68, 9.78, 4.0]})
    out = flag_collocation_table(col, TH, include_function_words=False, high_freq_cutoff=100)
    assert out["flags"].tolist() == [["LOW_COOCCURRENCE"], ["BOTH_HIGH_FREQUENCY", "T_HIGH_MI_LOW"],
                                     ["NOT_DISTINGUISHABLE"], ["LOW_COOCCURRENCE_MINOR", "NOT_DISTINGUISHABLE"]]
    key = pd.DataFrame({"word": ["a", "b", "c", "d"], "log_ratio": [0.5, 2.0, 6.0, 3.0], "zero_corrected": [False, False, True, False],
                        "g2": [20.0, 20.0, 20.0, 1.0]})
    assert flag_keyness_table(key, TH)["flags"].tolist() == [["EFFECT_SIZE_TOO_SMALL"], [], ["ZERO_CORRECTED"], ["NOT_DISTINGUISHABLE"]]
    assert "0.5" in check_keyness_row(6.0, TH, "c", zero_corrected=True)[0].message


# --- GROUP_IMBALANCE ------------------------------------------------------------
@pytest.mark.parametrize(
    "sizes, expected",
    [
        ({"a": 300, "b": 100}, False),   # ちょうど 3.0 倍は出さない
        ({"a": 301, "b": 100}, True),
        ({"a": 87, "b": 313}, True),     # 指示書の例
        ({"a": 100}, False),             # 1群だけなら判定しない
        ({"a": 10, "b": 10, "c": 40}, True),  # 最大/最小で判定
    ],
)
def test_group_imbalance_boundary(sizes, expected):
    flags = check_group_imbalance(sizes, TH)
    assert ("GROUP_IMBALANCE" in codes(flags)) is expected
    if expected:
        assert "倍" in flags[0].message

TH = {"corpus_min_tokens": 10000, "dp_skew": 0.5, "dp_min_freq": 10, "dp_min_parts": 10, "low_freq": 5,
      "group_imbalance_ratio": 3.0, "mi_high": 5.0, "low_cooccur_threshold": 20, "t_high": 2.0, "mi_low": 3.0,
      "log_ratio_min": 1.0, "high_freq_top_ratio": 0.01, "g2_significant": 6.63, "log_dice_strong": 7.0,
      "mi_meaningful": 3.0}


# --- NOT_DISTINGUISHABLE ---------------------------------------------------------
@pytest.mark.parametrize("g2, expected", [(6.62, True), (6.63, False), (1.4, True), (None, False), (float("nan"), False)])
def test_not_distinguishable_boundary(g2, expected):
    flags = check_collocation_row(1.0, 1.0, 50, False, True, TH, g2=g2, log_dice=1.0)
    assert ("NOT_DISTINGUISHABLE" in codes(flags)) is expected
    if expected:
        msg = flags[0].message
        assert "判断がつかない" in msg and "結びつきがない" in msg
        assert "有意" not in msg and "偶然の範囲" not in msg


def codes(flags):
    return [f.code for f in flags]


# --- CORPUS_TOO_SMALL -----------------------------------------------------------
@pytest.mark.parametrize("n, expected", [(9999, True), (10000, False), (10001, False), (0, True)])
def test_corpus_too_small_boundary(n, expected):
    assert ("CORPUS_TOO_SMALL" in codes(check_corpus_size(n, TH))) is expected


def test_corpus_too_small_message_has_numbers():
    f = check_corpus_size(500, TH)[0]
    assert "500" in f.message and "10,000" in f.message
    assert f.level == "warning"


# --- DISPERSION_SKEWED ----------------------------------------------------------
@pytest.mark.parametrize(
    "dp, freq, expected",
    [
        (0.5, 10, False),     # 閾値ちょうどは出さない（「超えたら」）
        (0.5001, 10, True),   # わずかに超える
        (0.9, 9, False),      # 頻度が最低値未満なら出さない
        (0.9, 10, True),      # 頻度が最低値ちょうどで出す
        (0.0, 100, False),
        (None, 100, False),
        (float("nan"), 100, False),
    ],
)
def test_dispersion_boundary(dp, freq, expected):
    assert ("DISPERSION_SKEWED" in codes(check_dispersion("語", freq, dp, TH))) is expected


# --- DP_TOO_FEW_PARTS -----------------------------------------------------------
@pytest.mark.parametrize("n_parts, expected", [(9, True), (10, False), (11, False), (1, True)])
def test_dp_too_few_parts_boundary(n_parts, expected):
    flags = check_dp_reliability(n_parts, TH)
    assert ("DP_TOO_FEW_PARTS" in codes(flags)) is expected
    if expected:
        assert flags[0].level == "info"
        assert str(n_parts) in flags[0].message


def test_skew_flags_suppressed_when_too_few_parts():
    df = pd.DataFrame({"word": ["a", "b"], "freq": [100, 3], "dp": [0.9, 0.9]})
    few = flag_frequency_table(df, TH, n_parts=9)
    enough = flag_frequency_table(df, TH, n_parts=10)
    # 分割数が足りないときは、どの語にも偏り警告を付けない（低頻度の注意は残る）
    assert few["flags"].tolist() == [[], ["LOW_FREQUENCY"]]
    assert enough["flags"].tolist() == [["DISPERSION_SKEWED"], ["LOW_FREQUENCY"]]
    # n_parts を渡さない場合は従来どおり判定する
    assert flag_frequency_table(df, TH)["flags"].tolist() == [["DISPERSION_SKEWED"], ["LOW_FREQUENCY"]]


# --- LOW_FREQUENCY --------------------------------------------------------------
@pytest.mark.parametrize("freq, expected", [(4, True), (5, False), (1, True)])
def test_low_frequency_boundary(freq, expected):
    assert ("LOW_FREQUENCY" in codes(check_low_frequency("語", freq, TH))) is expected


# --- 表へのベクトル適用が個別関数と一致する ------------------------------------------
def test_flag_frequency_table_matches_scalar_rules():
    df = pd.DataFrame(
        {
            "word": ["a", "b", "c", "d", "e"],
            "freq": [100, 10, 9, 4, 3],
            "dp": [0.6, 0.5, 0.9, 0.9, float("nan")],
        }
    )
    out = flag_frequency_table(df, TH)
    for r in out.itertuples():
        expected = codes(check_dispersion(r.word, r.freq, r.dp, TH)) + codes(check_low_frequency(r.word, r.freq, TH))
        assert r.flags == expected, r.word


# --- config.yaml が第2層に必要な閾値を全て持っている ----------------------------------
def test_config_has_all_thresholds():
    th = thresholds(load_config())
    for k in TH:
        assert k in th, f"config.yaml の thresholds に {k} がありません"
