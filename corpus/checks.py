"""読み込み完了時のサマリと、分析「前」のデータ量チェック。

判定そのものは interpretations/rules.py（第2層）に委ね、ここは呼び出すだけ。
"""
from __future__ import annotations

from typing import Any

from corpus.models import Corpus
from interpretations.flags import Flag
from interpretations.rules import check_corpus_size


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


def pre_analysis_flags(corpus: Corpus, thresholds: dict[str, Any]) -> list[Flag]:
    flags: list[Flag] = []
    flags += check_corpus_size(corpus.n_tokens, thresholds)
    # Phase 1: GROUP_IMBALANCE をここに追加
    return flags
