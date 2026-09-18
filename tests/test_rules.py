"""第2層の全フラグについて、閾値の境界値で ON/OFF が切り替わることを検証する。"""
import pandas as pd
import pytest

from app_config import load_config, thresholds
from interpretations.rules import (
    check_corpus_size,
    check_dispersion,
    check_dp_reliability,
    check_low_frequency,
    flag_frequency_table,
)

TH = {"corpus_min_tokens": 10000, "dp_skew": 0.5, "dp_min_freq": 10, "dp_min_parts": 10, "low_freq": 5}


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
