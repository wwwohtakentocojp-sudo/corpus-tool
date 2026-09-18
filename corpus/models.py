"""言語に依存しないデータモデル。

Token   : 1語の情報
Document: 1文書（テキストとメタデータ）
Corpus  : 文書集合と、全文書のトークンを1つにまとめた表

トークンは大量になるため、Corpus 内では list[Token] ではなく
pandas.DataFrame（列指向）で保持する。KWIC 検索などはこの表の上で
numpy 配列として処理する。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

# tokens DataFrame が必ず持つ列
TOKEN_COLUMNS = [
    "doc_id",       # 文書ID（documents 表の doc_id と対応）
    "sentence_id",  # 文書内の文番号（0始まり）
    "position",     # 文書内の語の位置（0始まり）
    "surface",      # 表層形（実際に書かれていた形）
    "lemma",        # 見出し語（集計キー。同形異義語を区別する接尾部を含むことがある: 「ライト-light（光）」）
    "lemma_label",  # 見出し語の表示名（接尾部なし: 「ライト」）。集計には使わない
    "pos",          # 品詞（大分類）
    "pos_detail",   # 品詞（細分類。無ければ pos と同じ）
    "is_function",  # 機能語（既定で除外対象）なら True
    "dep",          # 係り受けラベル（無い言語では ""）
    "head",         # 係り先の position（無ければ -1）
    "lemma_alt",    # 比較用の別手法の見出し語（ドイツ語の HanTa など。無ければ ""）
    "compound_parts",  # 複合語の構成要素を "+" で連結（分割していなければ ""）
]


@dataclass(frozen=True)
class Token:
    surface: str
    lemma: str
    pos: str
    doc_id: int
    position: int
    sentence_id: int = 0
    pos_detail: str = ""
    is_function: bool = False
    lemma_label: str = ""   # 空なら lemma と同じ
    dep: str = ""
    head: int = -1
    lemma_alt: str = ""
    compound_parts: str = ""

    @property
    def label(self) -> str:
        return self.lemma_label or self.lemma


@dataclass
class Document:
    doc_id: int
    name: str
    text: str
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Corpus:
    language: str
    documents: pd.DataFrame  # columns: doc_id, name, n_chars, + meta列
    tokens: pd.DataFrame     # columns: TOKEN_COLUMNS

    @property
    def n_documents(self) -> int:
        return int(len(self.documents))

    @property
    def n_tokens(self) -> int:
        return int(len(self.tokens))

    def doc_name(self, doc_id: int) -> str:
        row = self.documents.loc[self.documents["doc_id"] == doc_id, "name"]
        return str(row.iloc[0]) if len(row) else str(doc_id)


def tokens_to_frame(tokens: list[Token]) -> pd.DataFrame:
    """Token のリストを tokens DataFrame に変換する。"""
    if not tokens:
        return pd.DataFrame({c: pd.Series(dtype=object) for c in TOKEN_COLUMNS})
    df = pd.DataFrame(
        {
            "doc_id": [t.doc_id for t in tokens],
            "sentence_id": [t.sentence_id for t in tokens],
            "position": [t.position for t in tokens],
            "surface": [t.surface for t in tokens],
            "lemma": [t.lemma for t in tokens],
            "lemma_label": [t.label for t in tokens],
            "pos": [t.pos for t in tokens],
            "pos_detail": [t.pos_detail for t in tokens],
            "is_function": [t.is_function for t in tokens],
            "dep": [t.dep for t in tokens],
            "head": [t.head for t in tokens],
            "lemma_alt": [t.lemma_alt for t in tokens],
            "compound_parts": [t.compound_parts for t in tokens],
        }
    )
    df["head"] = df["head"].astype("int64")
    df["doc_id"] = df["doc_id"].astype("int64")
    df["sentence_id"] = df["sentence_id"].astype("int64")
    df["position"] = df["position"].astype("int64")
    df["is_function"] = df["is_function"].astype(bool)
    return df


def documents_to_frame(docs: list[Document]) -> pd.DataFrame:
    rows = []
    for d in docs:
        row = {"doc_id": d.doc_id, "name": d.name, "n_chars": len(d.text)}
        row.update(d.meta)
        rows.append(row)
    return pd.DataFrame(rows)
