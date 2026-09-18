"""文書 → Corpus を作る処理。言語は analyzers/registry 経由でのみ触る。"""
from __future__ import annotations

from typing import Any

from analyzers.registry import get_analyzer
from corpus.cleaners import apply_cleaning
from corpus.models import Corpus, Document, documents_to_frame, tokens_to_frame
from corpus.settings import AnalysisSettings


def build_corpus(docs: list[Document], settings: AnalysisSettings, config: dict[str, Any] | None = None,
                 progress=None) -> Corpus:
    """docs を整形・解析して Corpus を返す。progress は (i, n) を受け取る任意のコールバック。"""
    analyzer = get_analyzer(settings.language, config)
    options = {**analyzer.default_options(), **settings.language_options}
    all_tokens = []
    n = len(docs)
    for i, d in enumerate(docs):
        text = apply_cleaning(d.text, settings.cleaning)
        all_tokens.extend(analyzer.process(text, d.doc_id, options))
        if progress:
            progress(i + 1, n)
    tokens = tokens_to_frame(all_tokens)
    tokens = tokens.sort_values(["doc_id", "position"], kind="stable").reset_index(drop=True)
    return Corpus(language=settings.language, documents=documents_to_frame(docs), tokens=tokens)
