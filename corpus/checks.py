"""読み込み完了時のサマリと、分析「前」のデータ量チェック。

判定そのものは interpretations/rules.py（第2層）に委ね、ここは呼び出すだけ。
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from corpus.models import Corpus
from interpretations.flags import Flag
from interpretations.rules import check_corpus_size, check_group_imbalance


def corpus_summary(corpus: Corpus, unit: str = "lemma") -> dict[str, Any]:
    tokens = corpus.tokens
    content = tokens[~tokens["is_function"]]
    return {
        "n_documents": corpus.n_documents,
        "n_tokens": int(len(tokens)),
        "n_types": int(tokens[unit].nunique()) if len(tokens) else 0,
        "n_tokens_content": int(len(content)),
        "n_types_content": int(content[unit].nunique()) if len(content) else 0,
        "language": corpus.language,
    }


def group_columns(corpus: Corpus) -> list[str]:
    """documents 表のうち、グループ列として使える列（標準列以外）。"""
    return [c for c in corpus.documents.columns if c not in {"doc_id", "name", "n_chars", "encoding"}]


def group_sizes(corpus: Corpus, col: str) -> pd.DataFrame:
    """グループごとの文書数と延べ語数。"""
    docs = corpus.documents[["doc_id", col]]
    tok = corpus.tokens.groupby("doc_id").size().rename("n_tokens")
    df = docs.merge(tok, left_on="doc_id", right_index=True, how="left").fillna({"n_tokens": 0})
    g = df.groupby(col).agg(n_documents=("doc_id", "count"), n_tokens=("n_tokens", "sum")).reset_index()
    g["n_tokens"] = g["n_tokens"].astype(int)
    return g.sort_values("n_documents", ascending=False).reset_index(drop=True)


def pre_analysis_flags(corpus: Corpus, thresholds: dict[str, Any]) -> list[Flag]:
    flags: list[Flag] = []
    flags += check_corpus_size(corpus.n_tokens, thresholds)
    for col in group_columns(corpus):
        sizes = group_sizes(corpus, col)
        flags += check_group_imbalance(dict(zip(sizes[col].astype(str), sizes["n_documents"])), thresholds)
    return flags
