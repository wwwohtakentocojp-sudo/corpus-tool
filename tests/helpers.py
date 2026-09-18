"""テスト用: 語のリストから tokens DataFrame を組み立てる。"""
from __future__ import annotations

from corpus.models import Token, tokens_to_frame


def make_tokens(docs: list[list[str]], function_words: set[str] | None = None):
    """docs[i] = 文書 i の語（lemma = surface）のリスト。"""
    function_words = function_words or set()
    toks = []
    for doc_id, words in enumerate(docs):
        for pos, w in enumerate(words):
            toks.append(
                Token(
                    surface=w,
                    lemma=w,
                    pos="機能" if w in function_words else "内容",
                    doc_id=doc_id,
                    position=pos,
                    sentence_id=0,
                    pos_detail="",
                    is_function=w in function_words,
                )
            )
    return tokens_to_frame(toks)
