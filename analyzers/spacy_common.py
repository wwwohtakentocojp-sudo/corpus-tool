"""spaCy を使う言語（英語・ドイツ語）の共通処理。"""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Callable

from corpus.models import Token

# spaCy の 1 doc あたりの上限（既定 1,000,000 文字）に余裕をもたせて分割する
_CHUNK_CHARS = 200_000


@lru_cache(maxsize=4)
def load_model(name: str):
    import spacy

    try:
        return spacy.load(name, disable=["ner"])
    except OSError as e:  # モデル未導入
        raise RuntimeError(
            f"言語モデル {name} が見つかりません。"
            " 大モデル（lg）を使う場合は `uv sync --extra large-models` を実行してください。"
        ) from e


def _hard_split(text: str, max_chars: int) -> list[str]:
    """空白の位置でできるだけ切りながら max_chars 以下に分ける（最後の手段）。"""
    out: list[str] = []
    while len(text) > max_chars:
        cut = text.rfind(" ", 0, max_chars)
        if cut <= 0:
            cut = max_chars
        out.append(text[:cut])
        text = text[cut:]
    if text:
        out.append(text)
    return out


def _pack(units: list[str], sep: str, max_chars: int) -> list[str]:
    chunks: list[str] = []
    buf: list[str] = []
    size = 0
    for u in units:
        if size + len(u) > max_chars and buf:
            chunks.append(sep.join(buf))
            buf, size = [], 0
        buf.append(u)
        size += len(u) + len(sep)
    if buf:
        chunks.append(sep.join(buf))
    return chunks


def split_chunks(text: str, max_chars: int = _CHUNK_CHARS) -> list[str]:
    """max_chars 以下のかたまりに分ける。段落（空行）→ 行 → 空白 の順に細かい境界で切る。
    spaCy の 1 doc あたりの上限（1,000,000 文字）と、解析時のメモリを抑えるため。"""
    if len(text) <= max_chars:
        return [text]
    units: list[str] = []
    for para in text.split("\n\n"):
        if len(para) <= max_chars:
            units.append(para)
            continue
        for line in para.split("\n"):
            if len(line) <= max_chars:
                units.append(line)
            else:
                units.extend(_hard_split(line, max_chars))
    return _pack(units, "\n\n", max_chars)


def tokenize_with_spacy(
    nlp,
    text: str,
    doc_id: int,
    lemma_fn: Callable[[Any], str],
    post_doc: Callable[[Any, list[Token], int], list[Token]] | None = None,
) -> list[Token]:
    """spaCy で文分割・品詞・係り受けを付けて Token 列にする。

    lemma_fn(token) -> str : 見出し語の決め方（言語ごと）
    post_doc(doc, tokens, offset) -> tokens : 1 doc 分の後処理（分離動詞の再結合など）
    head は文書内 position で表す。空白トークンは飛ばす。
    """
    tokens: list[Token] = []
    position = 0
    sentence_id = 0
    for chunk in split_chunks(text):
        if not chunk.strip():
            continue
        doc = nlp(chunk)
        offset = position
        # spaCy の i（doc 内 index）→ 文書内 position の対応（空白を飛ばすのでずれる）
        idx_to_pos: dict[int, int] = {}
        chunk_tokens: list[Token] = []
        for sent in doc.sents:
            for tok in sent:
                if tok.is_space:
                    continue
                idx_to_pos[tok.i] = position
                chunk_tokens.append(
                    Token(
                        surface=tok.text,
                        lemma=lemma_fn(tok),
                        pos=tok.pos_,
                        doc_id=doc_id,
                        position=position,
                        sentence_id=sentence_id,
                        pos_detail=tok.tag_,
                        dep=tok.dep_,
                        head=tok.head.i,  # いったん doc 内 index。下で position に変換
                    )
                )
                position += 1
            sentence_id += 1
        # head を position に変換
        fixed: list[Token] = []
        for t in chunk_tokens:
            head_pos = idx_to_pos.get(t.head, -1)
            fixed.append(Token(**{**t.__dict__, "head": head_pos if head_pos != t.position else -1}))
        if post_doc:
            fixed = post_doc(doc, fixed, offset)
        tokens.extend(fixed)
    return tokens


# Universal POS のうち機能語として扱うもの（英独共通の既定）
DEFAULT_FUNCTION_UPOS = {"DET", "ADP", "PRON", "AUX", "CCONJ", "SCONJ", "PART", "PUNCT", "SYM", "SPACE"}
