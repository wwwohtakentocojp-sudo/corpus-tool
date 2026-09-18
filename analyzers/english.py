"""英語解析器（spaCy en_core_web_sm / lg）。"""
from __future__ import annotations

from typing import Any

from analyzers.base import BaseAnalyzer
from analyzers.spacy_common import DEFAULT_FUNCTION_UPOS, load_model, tokenize_with_spacy
from corpus.models import Token

MODELS = {"sm": "en_core_web_sm", "lg": "en_core_web_lg"}


class EnglishAnalyzer(BaseAnalyzer):
    code = "en"
    display_name = "英語"

    def __init__(self, config: dict[str, Any] | None = None):
        cfg = (config or {}).get("languages", {}).get("en", {})
        self._function_pos = set(cfg.get("function_pos", DEFAULT_FUNCTION_UPOS))
        self._model = cfg.get("model", "sm")
        self._lowercase = bool(cfg.get("lowercase", True))

    def option_schema(self) -> list[dict[str, Any]]:
        return [
            {
                "key": "model",
                "label": "解析モデル",
                "type": "choice",
                "default": self._model,
                "choices": {"sm": "標準（速い・同梱）", "lg": "精度重視（大きい・別途導入が必要）"},
                "help": "精度重視モデルは `uv sync --extra large-models` で導入します。",
            },
            {
                "key": "lowercase",
                "label": "大文字と小文字を区別しない（The と the を同じ語にする）",
                "type": "bool",
                "default": self._lowercase,
                "help": "OFF にすると文頭の The と文中の the が別の語として数えられます。固有名詞と一般名詞（Apple / apple）を分けたい場合は OFF にしてください。",
            },
        ]

    def normalize(self, text: str, options: dict[str, Any] | None = None) -> str:
        return text.replace("\r\n", "\n").replace("\r", "\n")

    def tokenize(self, text: str, doc_id: int = 0, options: dict[str, Any] | None = None) -> list[Token]:
        options = options or {}
        nlp = load_model(MODELS.get(options.get("model", self._model), MODELS["sm"]))
        lower = bool(options.get("lowercase", self._lowercase))

        def lemma_fn(tok) -> str:
            if tok.pos_ == "PUNCT":
                return tok.text
            lem = tok.lemma_ or tok.text
            return lem.lower() if lower else lem

        return tokenize_with_spacy(nlp, text, doc_id, lemma_fn)

    def lemmatize(self, tokens: list[Token], options: dict[str, Any] | None = None) -> list[Token]:
        return tokens

    def get_pos(self, tokens: list[Token]) -> list[str]:
        return [t.pos for t in tokens]

    def default_stopwords(self) -> set[str]:
        return set()

    def function_pos(self, options: dict[str, Any] | None = None) -> set[str]:
        return set(self._function_pos)

    def supports_dependency(self) -> bool:
        return True

    def language_warnings(self, options: dict[str, Any] | None = None) -> list[str]:
        options = options or {}
        ws = [
            "英語は spaCy の Universal 品詞（NOUN, VERB, ADJ …）で集計しています。"
            "論文には使用モデル名（en_core_web_sm など）とバージョンを明記してください。",
        ]
        if options.get("lowercase", self._lowercase):
            ws.append("大文字と小文字を区別していません。固有名詞（Apple 社）と一般名詞（apple）が同じ語として数えられます。区別したい場合は前処理設定で OFF にしてください。")
        return ws
