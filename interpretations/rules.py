"""第2層: 判定ルール。純粋な Python 関数のみ。AI・API・Streamlit を一切使わない。

閾値はすべて config.yaml の thresholds から受け取る（この層は既定値を持たない）。
境界の扱い:
  CORPUS_TOO_SMALL : total_tokens <  corpus_min_tokens
  DP_TOO_FEW_PARTS : n_parts < dp_min_parts（このとき DISPERSION_SKEWED は一切出さない）
  DISPERSION_SKEWED: dp > dp_skew かつ freq >= dp_min_freq
  LOW_FREQUENCY    : freq < low_freq
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd

from interpretations.flags import Flag, make_flag


def check_corpus_size(total_tokens: int, thresholds: dict[str, Any]) -> list[Flag]:
    th = int(thresholds["corpus_min_tokens"])
    if total_tokens < th:
        return [make_flag("CORPUS_TOO_SMALL", total_tokens=int(total_tokens), threshold=th)]
    return []


def check_group_imbalance(group_sizes: dict[str, int], thresholds: dict[str, Any]) -> list[Flag]:
    """グループ間の文書数の偏り。最大/最小の比が group_imbalance_ratio を超えたら警告。"""
    sizes = {k: int(v) for k, v in group_sizes.items() if int(v) > 0}
    if len(sizes) < 2:
        return []
    th = float(thresholds["group_imbalance_ratio"])
    big = max(sizes, key=sizes.get)
    small = min(sizes, key=sizes.get)
    ratio = sizes[big] / sizes[small]
    if ratio > th:
        return [make_flag("GROUP_IMBALANCE", group_a=big, size_a=sizes[big], group_b=small, size_b=sizes[small], ratio=ratio)]
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


def high_frequency_cutoff(freqs, thresholds: dict[str, Any]) -> int:
    """異なり語の頻度上位 high_freq_top_ratio（既定 1%）に入るための最低出現回数。
    freqs: 各異なり語の出現回数（順不同でよい）。語が無ければ十分大きな値を返す（誰も該当しない）。"""
    vals = sorted((int(v) for v in freqs), reverse=True)
    if not vals:
        return 2**31
    k = max(1, math.ceil(len(vals) * float(thresholds["high_freq_top_ratio"])))
    return vals[k - 1]


def check_collocation_row(mi: float, t: float, cooccur: int, is_function: bool, include_function_words: bool,
                          thresholds: dict[str, Any], freq_node: int | None = None, freq_collocate: int | None = None,
                          high_freq_cutoff: int | None = None) -> list[Flag]:
    """コロケーション表の1行に対するフラグ。
      MI_HIGH_LOW_FREQ     : mi > mi_high かつ cooccur < mi_min_cooccur
      BOTH_HIGH_FREQUENCY  : freq_node >= cutoff かつ freq_collocate >= cutoff（双方が頻度上位）
      T_ONLY_FUNCTION_WORD : t > t_high かつ mi < mi_low
      FUNCTION_WORD_NOISE  : 機能語 かつ 機能語を含めない設定
    """
    flags: list[Flag] = []
    if not pd.isna(mi) and mi > float(thresholds["mi_high"]) and cooccur < int(thresholds["mi_min_cooccur"]):
        flags.append(make_flag("MI_HIGH_LOW_FREQ", mi=float(mi), cooccur=int(cooccur), threshold=int(thresholds["mi_min_cooccur"])))
    if high_freq_cutoff is not None and freq_node is not None and freq_collocate is not None:
        if freq_node >= high_freq_cutoff and freq_collocate >= high_freq_cutoff:
            flags.append(make_flag("BOTH_HIGH_FREQUENCY", freq_node=int(freq_node), freq_collocate=int(freq_collocate),
                                   top_percent=float(thresholds["high_freq_top_ratio"]) * 100))
    if not pd.isna(t) and not pd.isna(mi) and t > float(thresholds["t_high"]) and mi < float(thresholds["mi_low"]):
        flags.append(make_flag("T_ONLY_FUNCTION_WORD", t=float(t), mi=float(mi)))
    if is_function and not include_function_words:
        flags.append(make_flag("FUNCTION_WORD_NOISE", word=""))
    return flags


def flag_collocation_table(df: pd.DataFrame, thresholds: dict[str, Any], include_function_words: bool,
                           high_freq_cutoff: int | None = None) -> pd.DataFrame:
    out = df.copy()
    out["flags"] = [
        [f.code for f in check_collocation_row(r.mi, r.t, int(r.cooccur), bool(r.is_function), include_function_words, thresholds,
                                               int(r.freq_node), int(r.freq_collocate), high_freq_cutoff)]
        for r in out.itertuples()
    ]
    return out


def check_keyness_row(log_ratio: float, thresholds: dict[str, Any], word: str = "",
                      zero_corrected: bool = False) -> list[Flag]:
    """EFFECT_SIZE_TOO_SMALL: |log_ratio| < log_ratio_min
       ZERO_CORRECTED     : 片方の群で 0 回（0.5 補正値）"""
    flags: list[Flag] = []
    th = float(thresholds["log_ratio_min"])
    if not pd.isna(log_ratio) and abs(log_ratio) < th:
        flags.append(make_flag("EFFECT_SIZE_TOO_SMALL", word=word, log_ratio=float(log_ratio), threshold=th))
    if zero_corrected:
        flags.append(make_flag("ZERO_CORRECTED", word=word))
    return flags


def flag_keyness_table(df: pd.DataFrame, thresholds: dict[str, Any]) -> pd.DataFrame:
    out = df.copy()
    zc = out["zero_corrected"] if "zero_corrected" in out.columns else pd.Series(False, index=out.index)
    out["flags"] = [
        [f.code for f in check_keyness_row(r.log_ratio, thresholds, str(r.word), bool(z))]
        for r, z in zip(out.itertuples(), zc.tolist())
    ]
    return out


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
