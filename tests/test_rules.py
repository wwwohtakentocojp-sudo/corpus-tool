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


# --- MI_HIGH_LOW_FREQ ------------------------------------------------------------
@pytest.mark.parametrize(
    "mi, cooccur, expected",
    [(5.0, 19, False), (5.01, 19, True), (5.01, 20, False), (9.8, 12, True), (float("nan"), 3, False)],
)
def test_mi_high_low_freq_boundary(mi, cooccur, expected):
    flags = check_collocation_row(mi, 0.0, cooccur, False, True, TH)
    assert ("MI_HIGH_LOW_FREQ" in codes(flags)) is expected


# --- T_ONLY_FUNCTION_WORD -------------------------------------------------------
@pytest.mark.parametrize(
    "t, mi, expected",
    [(2.0, 2.9, False), (2.01, 2.9, True), (2.01, 3.0, False), (12.1, 0.5, True)],
)
def test_t_only_function_word_boundary(t, mi, expected):
    flags = check_collocation_row(mi, t, 100, False, True, TH)
    assert ("T_ONLY_FUNCTION_WORD" in codes(flags)) is expected


# --- FUNCTION_WORD_NOISE --------------------------------------------------------
@pytest.mark.parametrize(
    "is_function, include_fw, expected",
    [(True, False, True), (True, True, False), (False, False, False)],
)
def test_function_word_noise(is_function, include_fw, expected):
    flags = check_collocation_row(1.0, 1.0, 10, is_function, include_fw, TH)
    assert ("FUNCTION_WORD_NOISE" in codes(flags)) is expected


# --- EFFECT_SIZE_TOO_SMALL -------------------------------------------------------
@pytest.mark.parametrize("lr, expected", [(0.99, True), (1.0, False), (-0.99, True), (-1.0, False), (3.2, False)])
def test_effect_size_boundary(lr, expected):
    assert ("EFFECT_SIZE_TOO_SMALL" in codes(check_keyness_row(lr, TH, "w"))) is expected


def test_vectorized_collocation_and_keyness_flags_match_scalar():
    col = pd.DataFrame({"mi": [6.0, 1.0], "t": [1.0, 5.0], "cooccur": [3, 50], "is_function": [False, True],
                        "freq_node": [600, 600], "freq_collocate": [3, 2000]})
    out = flag_collocation_table(col, TH, include_function_words=False, high_freq_cutoff=100)
    assert out["flags"].tolist() == [["MI_HIGH_LOW_FREQ"], ["BOTH_HIGH_FREQUENCY", "T_ONLY_FUNCTION_WORD", "FUNCTION_WORD_NOISE"]]
    key = pd.DataFrame({"word": ["a", "b", "c"], "log_ratio": [0.5, 2.0, 6.0], "zero_corrected": [False, False, True]})
    assert flag_keyness_table(key, TH)["flags"].tolist() == [["EFFECT_SIZE_TOO_SMALL"], [], ["ZERO_CORRECTED"]]
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
      "group_imbalance_ratio": 3.0, "mi_high": 5.0, "mi_min_cooccur": 20, "t_high": 2.0, "mi_low": 3.0,
      "log_ratio_min": 1.0, "high_freq_top_ratio": 0.01}


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
