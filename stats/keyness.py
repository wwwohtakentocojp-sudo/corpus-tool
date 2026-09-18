"""特徴語抽出（2群比較）。

各語について:
  freq_a, freq_b     : 各群での出現回数
  pmw_a, pmw_b       : 100万語あたり（分母は各群の全トークン数）
  g2                 : 対数尤度比（Rayson & Garside 2000）
                       E_a = N_a (f_a + f_b) / (N_a + N_b), E_b 同様、G² = 2 Σ f ln(f/E)
  p                  : G² を自由度1のχ²分布で評価した p 値
  log_ratio          : log2( (f_a/N_a) / (f_b/N_b) )（Hardie 2014）。
                       どちらかが 0 のときは両方に 0.5 を足して計算し zero_corrected=True
  odds_ratio         : (f_a/(N_a−f_a)) / (f_b/(N_b−f_b))。片方が 0 なら算出しない（NaN）

★ G²（と p 値）は「差があるか」、log ratio は「どれくらい違うか」。判断は log ratio で行う。
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.stats import chi2

from stats.basic import select_tokens


def log_likelihood_keyness(fa: float, fb: float, na: float, nb: float) -> float:
    total = na + nb
    if total <= 0 or fa + fb <= 0:
        return 0.0
    ea = na * (fa + fb) / total
    eb = nb * (fa + fb) / total
    g2 = 0.0
    if fa > 0:
        g2 += fa * math.log(fa / ea)
    if fb > 0:
        g2 += fb * math.log(fb / eb)
    return 2 * g2


def log_ratio(fa: float, fb: float, na: float, nb: float) -> tuple[float, bool]:
    corrected = fa == 0 or fb == 0
    if corrected:
        fa, fb = fa + 0.5, fb + 0.5
    return math.log2((fa / na) / (fb / nb)), corrected


def odds_ratio(fa: float, fb: float, na: float, nb: float) -> float:
    """片方が 0 のときは算出しない（NaN）。0 補正のオッズ比は人工的な値で解釈できないため。"""
    if fa == 0 or fb == 0:
        return float("nan")
    return (fa / (na - fa)) / (fb / (nb - fb))


def keyness_table(tokens_a: pd.DataFrame, tokens_b: pd.DataFrame, unit: str = "lemma",
                  include_function_words: bool = False) -> pd.DataFrame:
    """A 群と B 群の特徴語表。log_ratio 降順（正 = A 群に多い）。"""
    na, nb = len(tokens_a), len(tokens_b)
    cols = ["word", "label", "pos", "freq_a", "freq_b", "pmw_a", "pmw_b", "g2", "p", "log_ratio", "odds_ratio",
            "zero_corrected", "direction"]
    if na == 0 or nb == 0:
        return pd.DataFrame(columns=cols)
    sa = select_tokens(tokens_a, include_function_words)
    sb = select_tokens(tokens_b, include_function_words)
    ca = sa[unit].value_counts()
    cb = sb[unit].value_counts()
    words = ca.index.union(cb.index)
    fa = ca.reindex(words, fill_value=0).to_numpy(dtype=float)
    fb = cb.reindex(words, fill_value=0).to_numpy(dtype=float)

    both = pd.concat([sa, sb])
    label_col = "lemma_label" if unit == "lemma" and "lemma_label" in both.columns else unit
    labels = both.groupby(unit)[label_col].first()
    pos_mode = both.groupby(unit)["pos"].agg(lambda x: x.value_counts().index[0])

    rows = []
    for w, a, b in zip(words, fa, fb):
        g2 = log_likelihood_keyness(a, b, na, nb)
        lr, corrected = log_ratio(a, b, na, nb)
        rows.append(
            {
                "word": w,
                "label": labels.get(w, w),
                "pos": pos_mode.get(w, ""),
                "freq_a": int(a),
                "freq_b": int(b),
                "pmw_a": a / na * 1e6,
                "pmw_b": b / nb * 1e6,
                "g2": g2,
                "p": float(chi2.sf(g2, 1)),
                "log_ratio": lr,
                "odds_ratio": odds_ratio(a, b, na, nb),
                "zero_corrected": corrected,
                "direction": "A" if lr > 0 else ("B" if lr < 0 else "="),
            }
        )
    df = pd.DataFrame(rows, columns=cols)
    return df.sort_values(["log_ratio", "g2"], ascending=[False, False]).reset_index(drop=True)


def split_by_group(tokens: pd.DataFrame, documents: pd.DataFrame, group_col: str, value_a, value_b):
    """グループ列の2つの値で tokens を A 群・B 群に分ける。value_b が None なら「その他すべて」。"""
    docs = documents[["doc_id", group_col]].copy()
    docs[group_col] = docs[group_col].astype(str)
    ids_a = set(docs.loc[docs[group_col] == str(value_a), "doc_id"])
    if value_b is None:
        ids_b = set(docs["doc_id"]) - ids_a
    else:
        ids_b = set(docs.loc[docs[group_col] == str(value_b), "doc_id"])
    return tokens[tokens["doc_id"].isin(ids_a)], tokens[tokens["doc_id"].isin(ids_b)]
