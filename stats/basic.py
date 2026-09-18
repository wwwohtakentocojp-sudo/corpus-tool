"""基本統計: 延べ語数・異なり語数・TTR・標準化TTR・品詞構成比。

すべて tokens DataFrame（corpus.models.TOKEN_COLUMNS）を受け取る純粋関数。
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def select_tokens(tokens: pd.DataFrame, include_function_words: bool) -> pd.DataFrame:
    if include_function_words:
        return tokens
    return tokens[~tokens["is_function"]]


def ttr(words: pd.Series | list[str]) -> float | None:
    """異なり語数 / 延べ語数。語が0なら None。"""
    n = len(words)
    if n == 0:
        return None
    return float(len(set(words)) / n)


def standardized_ttr(words: list[str] | pd.Series, window: int = 1000) -> float | None:
    """window 語ずつに区切って TTR を計算し平均する。
    末尾の window 未満の端数は捨てる。window 未満なら None。"""
    words = list(words)
    n = len(words)
    if window <= 0 or n < window:
        return None
    vals = []
    for start in range(0, n - window + 1, window):
        chunk = words[start : start + window]
        vals.append(len(set(chunk)) / window)
    return float(np.mean(vals))


def basic_stats(tokens: pd.DataFrame, unit: str = "lemma", include_function_words: bool = False,
                sttr_window: int = 1000) -> dict:
    """コーパス全体の基本統計。"""
    sel = select_tokens(tokens, include_function_words)
    words = sel[unit]
    return {
        "n_tokens_all": int(len(tokens)),
        "n_tokens": int(len(sel)),
        "n_types": int(words.nunique()),
        "ttr": ttr(words),
        "sttr": standardized_ttr(words, sttr_window),
        "sttr_window": int(sttr_window),
        "n_documents": int(tokens["doc_id"].nunique()) if len(tokens) else 0,
    }


def per_document_stats(tokens: pd.DataFrame, unit: str = "lemma", include_function_words: bool = False,
                       sttr_window: int = 1000) -> pd.DataFrame:
    sel = select_tokens(tokens, include_function_words)
    rows = []
    for doc_id, g in sel.groupby("doc_id", sort=True):
        w = g.sort_values("position")[unit]
        rows.append(
            {
                "doc_id": int(doc_id),
                "n_tokens": int(len(w)),
                "n_types": int(w.nunique()),
                "ttr": ttr(w),
                "sttr": standardized_ttr(w, sttr_window),
            }
        )
    return pd.DataFrame(rows, columns=["doc_id", "n_tokens", "n_types", "ttr", "sttr"])


def per_group_stats(tokens: pd.DataFrame, doc_groups: pd.Series, unit: str = "lemma",
                    include_function_words: bool = False, sttr_window: int = 1000) -> pd.DataFrame:
    """グループごとの基本統計。doc_groups は doc_id → グループ値 の Series。

    グループ内の全文書を（文書順に）連結してから標準化TTRを計算するので、
    1文書が短くてもグループ全体が区切り幅以上あれば値が出る。
    """
    sel = select_tokens(tokens, include_function_words)
    sel = sel.assign(_group=sel["doc_id"].map(doc_groups))
    rows = []
    for g, grp in sel.groupby("_group", sort=True, dropna=False):
        w = grp.sort_values(["doc_id", "position"])[unit]
        rows.append(
            {
                "group": g,
                "n_documents": int(grp["doc_id"].nunique()),
                "n_tokens": int(len(w)),
                "n_types": int(w.nunique()),
                "ttr": ttr(w),
                "sttr": standardized_ttr(w, sttr_window),
            }
        )
    return pd.DataFrame(rows, columns=["group", "n_documents", "n_tokens", "n_types", "ttr", "sttr"])


def pos_composition(tokens: pd.DataFrame, include_function_words: bool = True) -> pd.DataFrame:
    """品詞別構成比。既定では機能語も含めて全トークンで計算する
    （構成比は「文章がどんな品詞でできているか」を見るものなので除外しない）。"""
    sel = select_tokens(tokens, include_function_words)
    if len(sel) == 0:
        return pd.DataFrame(columns=["pos", "count", "ratio"])
    vc = sel["pos"].value_counts()
    df = pd.DataFrame({"pos": vc.index, "count": vc.values})
    df["ratio"] = df["count"] / df["count"].sum()
    return df.reset_index(drop=True)
