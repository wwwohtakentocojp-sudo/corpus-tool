"""日本語解析器（fugashi + unidic-lite）。

UniDic 短単位で解析する。長単位は出せない（用語辞書で説明のみ）。

見出し語の粒度（language_options["lemma_unit"]）:
  "lemma"     : UniDic の「語彙素」。「言う」「いう」のような表記ゆれも統合する。
  "orth_base" : 「書字形基本形」。活用は戻すが、表記の違いは保つ。
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Any

from analyzers.base import BaseAnalyzer
from corpus.models import Token

# 文の区切り。句点・感嘆符・疑問符の直後、または改行。
_SENT_SPLIT = re.compile(r"(?<=[。！？!?])|\n+")

# 空白のみのトークンや、改行を除外するための判定
_WS_ONLY = re.compile(r"^\s*$")


@lru_cache(maxsize=1)
def _tagger():
    from fugashi import Tagger  # 遅延 import（起動を速くする・テストを軽くする）

    return Tagger()


def _feat(feature, name: str) -> str | None:
    """fugashi の feature オブジェクトから属性を安全に取り出す。未知語では None。"""
    v = getattr(feature, name, None)
    if v is None or v == "*" or v == "":
        return None
    return str(v)


def display_label(lemma: str, surface: str) -> str:
    """表示用の見出し語。UniDic の語彙素に付く区別用の接尾部
    （「私-代名詞」「シャツ-shirt」「ライト-light（光）」）を取り除いた形。

    ★ 集計には使わない。接尾部は同形異義語（ライト-light（光）／ライト-light（軽い））を
    区別するためのものなので、集計キー（Token.lemma）には接尾部付きのまま残す。
    表層形そのものにハイフンが含まれる語（記号など）はそのまま返す。"""
    if "-" in lemma and "-" not in surface:
        head = lemma.split("-", 1)[0]
        if head:
            return head
    return lemma


class JapaneseAnalyzer(BaseAnalyzer):
    code = "ja"
    display_name = "日本語"

    DEFAULT_FUNCTION_POS = {"助詞", "助動詞", "補助記号", "記号", "空白"}

    def __init__(self, config: dict[str, Any] | None = None):
        cfg = (config or {}).get("languages", {}).get("ja", {})
        self._cfg_function_pos = set(cfg.get("function_pos", self.DEFAULT_FUNCTION_POS))
        self._cfg_lemma_unit = cfg.get("lemma_unit", "lemma")
        self._cfg_nfkc = bool(cfg.get("nfkc", True))

    # ------------------------------------------------------------------
    def option_schema(self) -> list[dict[str, Any]]:
        return [
            {
                "key": "lemma_unit",
                "label": "見出し語のまとめ方",
                "type": "choice",
                "default": self._cfg_lemma_unit,
                "choices": {
                    "lemma": "語彙素（表記ゆれも統合: 「いう」と「言う」を同じ語にする）",
                    "orth_base": "書字形基本形（活用だけ戻す: 「いう」と「言う」は別の語のまま）",
                },
                "help": "表記ゆれ自体を研究する場合は「書字形基本形」を選んでください。",
            },
            {
                "key": "nfkc",
                "label": "文字の正規化（全角の英数字・記号を半角にそろえる）",
                "type": "bool",
                "default": self._cfg_nfkc,
                "help": "「ＡＢＣ」と「ABC」を同じ語として数えます。全角・半角の違いを研究する場合はOFFにしてください。",
            },
        ]

    # ------------------------------------------------------------------
    def normalize(self, text: str, options: dict[str, Any] | None = None) -> str:
        options = options or {}
        if options.get("nfkc", self._cfg_nfkc):
            text = unicodedata.normalize("NFKC", text)
        # 改行コードの統一
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        return text

    def tokenize(self, text: str, doc_id: int = 0, options: dict[str, Any] | None = None) -> list[Token]:
        options = options or {}
        lemma_unit = options.get("lemma_unit", self._cfg_lemma_unit)
        tagger = _tagger()
        tokens: list[Token] = []
        position = 0
        sentence_id = 0
        for sent in _SENT_SPLIT.split(text):
            if sent is None or _WS_ONLY.match(sent):
                continue
            for w in tagger(sent):
                surface = w.surface
                if _WS_ONLY.match(surface):
                    continue
                f = w.feature
                pos1 = _feat(f, "pos1") or "未知語"
                pos2 = _feat(f, "pos2")
                pos_detail = f"{pos1}-{pos2}" if pos2 else pos1
                if lemma_unit == "orth_base":
                    lemma = _feat(f, "orthBase") or _feat(f, "lemma") or surface
                else:
                    lemma = _feat(f, "lemma") or _feat(f, "orthBase") or surface
                tokens.append(
                    Token(
                        surface=surface,
                        lemma=lemma,
                        pos=pos1,
                        doc_id=doc_id,
                        position=position,
                        sentence_id=sentence_id,
                        pos_detail=pos_detail,
                        lemma_label=display_label(lemma, surface),
                    )
                )
                position += 1
            sentence_id += 1
        return tokens

    def lemmatize(self, tokens: list[Token], options: dict[str, Any] | None = None) -> list[Token]:
        # tokenize の時点で lemma を埋めているので、そのまま返す
        return tokens

    def get_pos(self, tokens: list[Token]) -> list[str]:
        return [t.pos for t in tokens]

    def default_stopwords(self) -> set[str]:
        # 日本語は品詞ベース（function_pos）で除外するため、語形リストは空
        return set()

    def function_pos(self, options: dict[str, Any] | None = None) -> set[str]:
        return set(self._cfg_function_pos)

    def language_warnings(self, options: dict[str, Any] | None = None) -> list[str]:
        options = options or {}
        warnings = [
            "日本語は「短単位」（UniDic の最小単位）で区切っています。"
            "「東京都」は「東京」「都」の2語、「食べている」は「食べ」「て」「いる」の3語と数えられます。"
            "複合語や複合動詞をひとまとまり（長単位）で数えたい場合、このツールでは対応できません。"
            "論文には「UniDic 短単位で集計」と明記してください。",
        ]
        if options.get("lemma_unit", self._cfg_lemma_unit) == "lemma":
            warnings.append(
                "見出し語は「語彙素」でまとめています。「いう」と「言う」、「こと」と「事」は同じ語として数えられます。"
                "表記の違いを研究する場合は、前処理設定で「書字形基本形」に切り替えてください。"
            )
            warnings.append(
                "同じ読み・同じ表記でも意味が違う語（「ライト（光）」と「ライト（軽い）」など）は、別の語として数えています。"
                "画面には「ライト」とだけ表示されるため、同じ語が2行に分かれて見えることがあります。"
                "頻度分析画面の「集計キーを表示」を ON にすると、区別の内訳を確認できます。"
            )
        return warnings
