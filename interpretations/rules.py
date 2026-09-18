"""第2層: 判定ルール。純粋な Python 関数のみ。AI・API・Streamlit を一切使わない。

閾値はすべて config.yaml の thresholds から受け取る（この層は既定値を持たない）。
境界の扱い:
  CORPUS_TOO_SMALL : total_tokens <  corpus_min_tokens
  DP_TOO_FEW_PARTS : n_parts < dp_min_parts（このとき DISPERSION_SKEWED は一切出さない）
  DISPERSION_SKEWED: dp > dp_skew かつ freq >= dp_min_freq
  LOW_FREQUENCY    : freq < low_freq
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from interpretations.flags import Flag, make_flag


def check_corpus_size(total_tokens: int, thresholds: dict[str, Any]) -> list[Flag]:
    th = int(thresholds["corpus_min_tokens"])
    if total_tokens < th:
        return [make_flag("CORPUS_TOO_SMALL", total_tokens=int(total_tokens), threshold=th)]
    return []


def check_dp_reliability(n_parts: int, thresholds: dict[str, Any]) -> list[Flag]:
    """分割数（文書数・グループ数）が少なすぎて DP の判定自体が信頼できないか。"""
    th = int(thresholds["dp_min_parts"])
    if n_parts < th:
        return [make_flag("DP_TOO_FEW_PARTS", n_parts=int(n_parts), threshold=th)]
    return []


def dp_is_reliable(n_parts: int, thresholds: dict[str, Any]) -> bool:
    return not check_dp_reliability(n_parts, thresholds)


def check_dispersion(word: str, freq: int, dp: float | None, thresholds: dict[str, Any]) -> list[Flag]:
    if dp is None or pd.isna(dp):
        return []
    th = float(thresholds["dp_skew"])
    min_freq = int(thresholds["dp_min_freq"])
    if dp > th and freq >= min_freq:
        return [make_flag("DISPERSION_SKEWED", word=word, freq=int(freq), dp=float(dp), threshold=th)]
    return []


def check_low_frequency(word: str, freq: int, thresholds: dict[str, Any]) -> list[Flag]:
    th = int(thresholds["low_freq"])
    if freq < th:
        return [make_flag("LOW_FREQUENCY", word=word, freq=int(freq), threshold=th)]
    return []


def flag_frequency_table(freq_df: pd.DataFrame, thresholds: dict[str, Any], n_parts: int | None = None) -> pd.DataFrame:
    """頻度表（word, freq, dp 列を持つ）に、フラグ列 (list[str]) を付けて返す。

    画面表示用にベクトル化して計算する。判定条件は上の関数群と同一。
    n_parts（分割数）が dp_min_parts 未満なら、DP の判定は信頼できないので
    DISPERSION_SKEWED は一切付けない（呼び出し側が DP_TOO_FEW_PARTS を1つだけ表示する）。
    """
    df = freq_df.copy()
    th_dp = float(thresholds["dp_skew"])
    min_freq = int(thresholds["dp_min_freq"])
    low = int(thresholds["low_freq"])
    reliable = n_parts is None or dp_is_reliable(n_parts, thresholds)

    skew = (df["dp"] > th_dp) & (df["freq"] >= min_freq) & df["dp"].notna() & reliable
    lowf = df["freq"] < low

    flags: list[list[str]] = []
    for s, l in zip(skew.tolist(), lowf.tolist()):
        f = []
        if s:
            f.append("DISPERSION_SKEWED")
        if l:
            f.append("LOW_FREQUENCY")
        flags.append(f)
    df["flags"] = flags
    return df
