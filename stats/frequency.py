"""頻度分析: 頻度・pmw・分散度DP（Gries 2008）・Zipf 用データ。

DP の定義（Gries 2008）:
  コーパスを n 個の部分（ここでは文書）に分け、
    s_i = 部分 i の語数 / 全語数           （期待される割合）
    v_i = 部分 i でのその語の頻度 / 語の総頻度 （観察された割合）
    DP  = 0.5 * Σ |v_i - s_i|
  0 に近いほど均等、1 に近いほど偏り。

pmw の分母は「全トークン数（機能語を含む）」で固定する。
機能語を除外して表示しているときも分母は変えない。
分母が表示設定で変わると、同じ語の pmw が設定によって変わってしまい、
論文の数値が再現できなくなるため。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from stats.basic import select_tokens


def dispersion_dp(part_sizes: np.ndarray, part_counts: np.ndarray) -> float:
    """1語分の DP。part_sizes: 各部分の語数、part_counts: 各部分でのその語の頻度。"""
    total = part_sizes.sum()
    f = part_counts.sum()
    if total == 0 or f == 0:
        return float("nan")
    s = part_sizes / total
    v = part_counts / f
    return float(0.5 * np.abs(v - s).sum())


def frequency_table(tokens: pd.DataFrame, unit: str = "lemma", include_function_words: bool = False,
                    part_col: str = "doc_id") -> pd.DataFrame:
    """語彙表。列: rank, word, label, pos, freq, pmw, dp, n_parts

    - word は集計キー（unit 列の値そのもの。同形異義語の区別用の接尾部を含む）
    - label は表示名（unit が lemma なら lemma_label、surface ならそのまま）
    - pos は最頻の品詞
    - pmw の分母は全トークン数（機能語を含む）
    - dp は part_col（既定は文書）を部分として計算
    """
    n_all = len(tokens)
    empty_cols = ["rank", "word", "label", "pos", "freq", "pmw", "dp", "n_parts"]
    if n_all == 0:
        return pd.DataFrame(columns=empty_cols)

    # 部分サイズは全トークンで計算する（DP の s_i も分母を固定する）
    part_sizes_s = tokens.groupby(part_col).size()
    parts = part_sizes_s.index.to_numpy()
    part_sizes = part_sizes_s.to_numpy(dtype=float)

    sel = select_tokens(tokens, include_function_words)
    if len(sel) == 0:
        return pd.DataFrame(columns=empty_cols)

    # 語 × 部分 のクロス表
    ct = pd.crosstab(sel[unit], sel[part_col])
    ct = ct.reindex(columns=parts, fill_value=0)
    counts = ct.to_numpy(dtype=float)
    freq = counts.sum(axis=1)

    total = part_sizes.sum()
    s = part_sizes / total
    v = counts / freq[:, None]
    dp = 0.5 * np.abs(v - s[None, :]).sum(axis=1)
    n_parts = (counts > 0).sum(axis=1)

    # 最頻品詞
    pos_mode = sel.groupby(unit)["pos"].agg(lambda x: x.value_counts().index[0])

    df = pd.DataFrame(
        {
            "word": ct.index.astype(str),
            "freq": freq.astype(int),
            "pmw": freq / n_all * 1_000_000,
            "dp": dp,
            "n_parts": n_parts.astype(int),
        }
    )
    df["pos"] = df["word"].map(pos_mode).fillna("")
    if unit == "lemma" and "lemma_label" in sel.columns:
        labels = sel.groupby("lemma")["lemma_label"].first()
        df["label"] = df["word"].map(labels).fillna(df["word"])
    else:
        df["label"] = df["word"]
    df = df.sort_values(["freq", "word"], ascending=[False, True]).reset_index(drop=True)
    df["rank"] = np.arange(1, len(df) + 1)
    return df[["rank", "word", "label", "pos", "freq", "pmw", "dp", "n_parts"]]


def tokens_with_parts(tokens: pd.DataFrame, documents: pd.DataFrame, part_col: str) -> pd.DataFrame:
    """documents 表のグループ列を tokens に付けて返す（DP をグループ単位で計算するため）。"""
    if part_col == "doc_id" or part_col in tokens.columns:
        return tokens
    return tokens.merge(documents[["doc_id", part_col]], on="doc_id", how="left")


def expand_compounds(tokens: pd.DataFrame) -> pd.DataFrame:
    """複合語を構成要素に置き換えた tokens を返す（「分割した場合」の集計用）。

    compound_parts が空の語はそのまま。分割された語は構成要素ごとの行になり、
    lemma / lemma_label / surface に構成要素が入る。position は元の語の位置を引き継ぐ。
    """
    if "compound_parts" not in tokens.columns:
        return tokens
    is_comp = tokens["compound_parts"].astype(str) != ""
    plain = tokens[~is_comp]
    comp = tokens[is_comp].copy()
    if comp.empty:
        return tokens
    comp["_part"] = comp["compound_parts"].astype(str).str.split("+")
    comp = comp.explode("_part")
    comp["surface"] = comp["_part"]
    comp["lemma"] = comp["_part"]
    comp["lemma_label"] = comp["_part"]
    comp["compound_parts"] = ""
    comp = comp.drop(columns=["_part"])
    out = pd.concat([plain, comp], ignore_index=True)
    return out.sort_values(["doc_id", "position"], kind="stable").reset_index(drop=True)


def word_distribution(tokens: pd.DataFrame, word: str, unit: str = "lemma",
                      part_col: str = "doc_id") -> pd.DataFrame:
    """ある語が各部分（文書）に何回出ているか。DP の警告からの確認用。"""
    part_sizes = tokens.groupby(part_col).size().rename("part_tokens")
    hits = tokens[tokens[unit] == word].groupby(part_col).size().rename("freq")
    df = pd.concat([part_sizes, hits], axis=1).fillna(0)
    df["freq"] = df["freq"].astype(int)
    df["part_tokens"] = df["part_tokens"].astype(int)
    df["pmw_in_part"] = df["freq"] / df["part_tokens"].replace(0, np.nan) * 1_000_000
    total = df["freq"].sum()
    df["share"] = df["freq"] / total if total else 0.0
    return df.reset_index().sort_values("freq", ascending=False).reset_index(drop=True)


def zipf_data(freq_df: pd.DataFrame) -> pd.DataFrame:
    """Zipf プロット用: rank と freq（両対数で描く）。"""
    return freq_df[["rank", "freq", "word"]].copy()
