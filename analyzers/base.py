"""言語解析器の共通インターフェース。

言語固有の知識（形態素解析器の使い方、品詞体系、ストップワード、正書法…）は
必ずこのクラスのサブクラスの中に閉じ込める。analyzers/ の外のコードは
BaseAnalyzer のメソッドだけを呼び、言語名で分岐しないこと。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from corpus.models import Token


class BaseAnalyzer(ABC):
    #: 言語コード（"ja", "en", "de"）
    code: str = ""
    #: UI に表示する言語名
    display_name: str = ""

    # ------------------------------------------------------------------
    # 必須インターフェース
    # ------------------------------------------------------------------
    @abstractmethod
    def tokenize(self, text: str, doc_id: int = 0, options: dict[str, Any] | None = None) -> list[Token]:
        """文書を Token のリストにする。surface / pos / position / sentence_id を埋める。
        lemma は表層形のままでもよい（lemmatize が埋める）。"""

    @abstractmethod
    def lemmatize(self, tokens: list[Token], options: dict[str, Any] | None = None) -> list[Token]:
        """各 Token の lemma を埋める。"""

    @abstractmethod
    def get_pos(self, tokens: list[Token]) -> list[str]:
        """各 Token の品詞（大分類）を返す。"""

    @abstractmethod
    def normalize(self, text: str, options: dict[str, Any] | None = None) -> str:
        """トークン化前の文字列正規化。"""

    @abstractmethod
    def default_stopwords(self) -> set[str]:
        """語形ベースのストップワード。品詞ベースの除外は is_function で扱う。"""

    @abstractmethod
    def function_pos(self, options: dict[str, Any] | None = None) -> set[str]:
        """機能語として扱う品詞（大分類）の集合。"""

    @abstractmethod
    def language_warnings(self, options: dict[str, Any] | None = None) -> list[str]:
        """現在の設定で利用者に伝えるべき注意（統計用語なしの日本語）。"""

    @abstractmethod
    def option_schema(self) -> list[dict[str, Any]]:
        """UI が設定画面を自動生成するためのオプション定義。
        各要素: {key, label, type('bool'|'choice'), default, choices?, help}"""

    # ------------------------------------------------------------------
    # 共通処理（サブクラスで上書き可）
    # ------------------------------------------------------------------
    def process(self, text: str, doc_id: int, options: dict[str, Any] | None = None) -> list[Token]:
        """normalize → tokenize → lemmatize → pos → 機能語フラグ を一括で行う。"""
        options = options or {}
        text = self.normalize(text, options)
        tokens = self.tokenize(text, doc_id, options)
        tokens = self.lemmatize(tokens, options)
        fpos = self.function_pos(options)
        stop = self.default_stopwords()
        out: list[Token] = []
        for t in tokens:
            is_fn = (t.pos in fpos) or (t.surface in stop)
            out.append(
                Token(
                    surface=t.surface,
                    lemma=t.lemma,
                    pos=t.pos,
                    doc_id=t.doc_id,
                    position=t.position,
                    sentence_id=t.sentence_id,
                    pos_detail=t.pos_detail,
                    is_function=is_fn,
                    lemma_label=t.lemma_label,
                )
            )
        return out

    def default_options(self) -> dict[str, Any]:
        return {o["key"]: o["default"] for o in self.option_schema()}
