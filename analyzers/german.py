"""ドイツ語解析器（spaCy de_core_news_sm / lg + HanTa + compound-split）。

ドイツ語固有の処理:
  1. 複合語分割（既定 OFF）: compound_parts 列に構成要素を入れる。元の語はそのまま数える。
  2. 分離動詞の再結合（既定 ON）: 係り受けラベル svp の前綴りを親動詞の lemma に結合する。
  3. 小文字化は既定 OFF（Essen / essen の統合を防ぐ）。
  4. 見出し語化: spaCy / HanTa / 両方比較 の3モード。
  5. 正書法の正規化: ß→ss、ウムラウト、1996年改革。すべて既定 OFF。
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from analyzers import german_normalize as gn
from analyzers.base import BaseAnalyzer
from analyzers.spacy_common import DEFAULT_FUNCTION_UPOS, load_model, tokenize_with_spacy
from corpus.models import Token

MODELS = {"sm": "de_core_news_sm", "lg": "de_core_news_lg"}

# 複合語分割の対象にする品詞
_COMPOUND_POS = {"NOUN", "PROPN"}


@lru_cache(maxsize=1)
def _hanta():
    from HanTa import HanoverTagger as ht

    return ht.HanoverTagger("morphmodel_ger.pgz")


def hanta_lemma(word: str) -> str:
    try:
        lemma, _pos = _hanta().analyze(word)
        return lemma or word
    except Exception:  # noqa: BLE001
        return word


def split_compound(word: str, min_score: float = 0.5, min_part_len: int = 3) -> list[str]:
    """CharSplit で複合語を2つに分ける。信頼度が低い・部品が短い場合は分けない。"""
    from compound_split import char_split

    if len(word) < min_part_len * 2:
        return []
    try:
        cands = char_split.split_compound(word)
    except Exception:  # noqa: BLE001
        return []
    if not cands:
        return []
    score, left, right = cands[0][0], cands[0][1], cands[0][2]
    if score < min_score or len(left) < min_part_len or len(right) < min_part_len:
        return []
    return [left, right]


class GermanAnalyzer(BaseAnalyzer):
    code = "de"
    display_name = "ドイツ語"

    def __init__(self, config: dict[str, Any] | None = None):
        cfg = (config or {}).get("languages", {}).get("de", {})
        self._function_pos = set(cfg.get("function_pos", DEFAULT_FUNCTION_UPOS))
        self._model = cfg.get("model", "sm")
        self._defaults = {
            "model": self._model,
            "lowercase": bool(cfg.get("lowercase", False)),
            "lemma_mode": cfg.get("lemma_mode", "spacy"),
            "separable_verbs": bool(cfg.get("separable_verbs", True)),
            "compound_split": bool(cfg.get("compound_split", False)),
            "norm_ss": bool(cfg.get("norm_ss", False)),
            "norm_umlaut": bool(cfg.get("norm_umlaut", False)),
            "norm_1996": bool(cfg.get("norm_1996", False)),
        }
        self._compound_min_score = float(cfg.get("compound_min_score", 0.5))
        self._compound_min_part_len = int(cfg.get("compound_min_part_len", 3))

    # ------------------------------------------------------------------
    def option_schema(self) -> list[dict[str, Any]]:
        d = self._defaults
        return [
            {"key": "model", "label": "解析モデル", "type": "choice", "default": d["model"],
             "choices": {"sm": "標準（速い・同梱）", "lg": "精度重視（大きい・別途導入が必要）"},
             "help": "精度重視モデルは `uv sync --extra large-models` で導入します。"},
            {"key": "lemma_mode", "label": "見出し語化の方法", "type": "choice", "default": d["lemma_mode"],
             "choices": {"spacy": "spaCy（標準）", "hanta": "HanTa", "both": "両方を比較（集計は spaCy、HanTa との差異を一覧表示）"},
             "help": "ドイツ語は屈折が強く、手法によって見出し語が変わることがあります。重要な語は「両方を比較」で確認してください。"},
            {"key": "separable_verbs", "label": "分離動詞を元の形に戻す（rufe … an → anrufen）", "type": "bool", "default": d["separable_verbs"],
             "help": "OFF にすると rufen と an が別々に数えられ、anrufen の出現回数が 0 になります。離れた形そのものを研究する場合だけ OFF にしてください。"},
            {"key": "compound_split", "label": "複合語を構成要素に分ける（Autobahnraststätte → Autobahn + Raststätte）", "type": "bool", "default": d["compound_split"],
             "help": "ON にすると頻度分析に「構成要素」タブが追加されます。元の複合語の集計はそのまま残ります。造語そのものを研究する場合は OFF のままにしてください。"},
            {"key": "lowercase", "label": "大文字と小文字を区別しない", "type": "bool", "default": d["lowercase"],
             "help": "★ 注意: ドイツ語は名詞が大文字始まりです。ON にすると Essen（食事）と essen（食べる）が同じ語に統合されます。"},
            {"key": "norm_1996", "label": "1996年正書法改革の前後を統一する（daß → dass など）", "type": "bool", "default": d["norm_1996"],
             "help": "1990年代をまたぐデータで OFF のままだと「dass が2000年代に急増」という偽の発見が出ます。通時的な表記変化そのものを研究する場合は OFF にしてください。"},
            {"key": "norm_ss", "label": "ß を ss に統一する（スイス表記に合わせる）", "type": "bool", "default": d["norm_ss"],
             "help": "スイスのデータと他地域のデータを混ぜるときに使います。"},
            {"key": "norm_umlaut", "label": "ä/ö/ü を ae/oe/ue に統一する", "type": "bool", "default": d["norm_umlaut"],
             "help": "ウムラウトを使わずに書かれたデータ（古い電子テキスト、SNS など）と混ぜるときに使います。"},
        ]

    # ------------------------------------------------------------------
    def normalize(self, text: str, options: dict[str, Any] | None = None) -> str:
        o = {**self._defaults, **(options or {})}
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        if o["norm_1996"]:
            text = gn.normalize_1996(text)
        if o["norm_ss"]:
            text = gn.normalize_ss(text)
        if o["norm_umlaut"]:
            text = gn.normalize_umlaut(text)
        return text

    def tokenize(self, text: str, doc_id: int = 0, options: dict[str, Any] | None = None) -> list[Token]:
        o = {**self._defaults, **(options or {})}
        nlp = load_model(MODELS.get(o["model"], MODELS["sm"]))
        lower = bool(o["lowercase"])
        mode = o["lemma_mode"]

        def lemma_fn(tok) -> str:
            if tok.pos_ == "PUNCT":
                return tok.text
            if mode == "hanta":
                lem = hanta_lemma(tok.text)
            else:
                lem = tok.lemma_ or tok.text
            if lower:
                return lem.lower()
            # spaCy は名詞の見出し語を小文字にすることがある（Essen → essen）。
            # ドイツ語の名詞は必ず大文字始まりなので、小文字化 OFF のときは戻す。
            # これをしないと Essen（食事）と essen（食べる）が見出し語で統合されてしまう。
            if tok.pos_ in ("NOUN", "PROPN") and lem[:1].islower() and tok.text[:1].isupper():
                lem = lem[0].upper() + lem[1:]
            return lem

        def post_doc(doc, tokens: list[Token], offset: int) -> list[Token]:
            by_pos = {t.position: t for t in tokens}
            # --- 分離動詞の再結合 ---
            if o["separable_verbs"]:
                for t in list(tokens):
                    if t.dep == "svp" and t.head in by_pos:
                        verb = by_pos[t.head]
                        prefix = t.surface.lower()
                        new_lemma = prefix + verb.lemma.lower() if lower else prefix + verb.lemma
                        by_pos[verb.position] = Token(**{**verb.__dict__, "lemma": new_lemma, "lemma_label": new_lemma})
                        # 前綴り側は機能語扱い（集計から外れる）。pos_detail=PTKVZ のまま
                        by_pos[t.position] = Token(**{**t.__dict__, "pos": "PART"})
            # --- HanTa 比較 ---
            if mode == "both":
                for p, t in by_pos.items():
                    if t.pos in {"NOUN", "VERB", "ADJ", "ADV", "PROPN"}:
                        alt = hanta_lemma(t.surface)
                        by_pos[p] = Token(**{**t.__dict__, "lemma_alt": alt.lower() if lower else alt})
            # --- 複合語分割 ---
            if o["compound_split"]:
                for p, t in by_pos.items():
                    if t.pos in _COMPOUND_POS:
                        parts = split_compound(t.surface, self._compound_min_score, self._compound_min_part_len)
                        if parts:
                            joined = "+".join(x.lower() for x in parts) if lower else "+".join(parts)
                            by_pos[p] = Token(**{**t.__dict__, "compound_parts": joined})
            return [by_pos[p] for p in sorted(by_pos)]

        return tokenize_with_spacy(nlp, text, doc_id, lemma_fn, post_doc)

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

    # ------------------------------------------------------------------
    def language_warnings(self, options: dict[str, Any] | None = None) -> list[str]:
        o = {**self._defaults, **(options or {})}
        ws = [
            "ドイツ語は spaCy の Universal 品詞で集計しています。論文には使用モデル名（de_core_news_sm など）と見出し語化の方法を明記してください。",
        ]
        if o["lowercase"]:
            ws.append(
                "★ 大文字と小文字を区別しない設定です。ドイツ語は名詞が大文字始まりなので、"
                "Essen（食事・名詞）と essen（食べる・動詞）が1つの語に統合されています。意図した設定か確認してください。"
            )
        if not o["separable_verbs"]:
            ws.append(
                "分離動詞を元に戻さない設定です。\"Ich rufe dich an.\" の anrufen は rufen と an に分解して数えられ、"
                "anrufen の出現回数は 0 になります。"
            )
        if not o["compound_split"]:
            ws.append(
                "複合語は分割していません。Autobahnraststätte のような連結語は1語として数えられ、"
                "出現回数 1 回の語が多くなります。統計（特徴語・共起）が機能しにくい場合は、前処理設定で分割を ON にしてください。"
            )
        else:
            ws.append(
                "複合語の分割は辞書を使わない推定なので、単純な名詞を誤って分ける場合があります。"
                "頻度分析の「構成要素」タブで分割結果を確認してください。"
            )
        if o["lemma_mode"] == "both":
            ws.append("見出し語化を spaCy と HanTa で比較しています。集計には spaCy の結果を使い、差異のある語は前処理設定画面に一覧表示します。")
        return ws

    def data_warnings(self, texts: list[str], options: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        o = {**self._defaults, **(options or {})}
        out: list[dict[str, Any]] = []
        if not o["norm_1996"]:
            counts = gn.detect_orthography_mix("\n".join(texts))
            if gn.is_mixed(counts):
                out.append(
                    {
                        "message": (
                            f"表記ゆれを検出しました: 1996年改革前の表記（daß, muß など）が {counts['old']} 回、"
                            f"改革後の表記（dass, muss など）が {counts['new']} 回あります。"
                            " このまま分析すると、表記の違いが語の増減として現れます（例:「dass が2000年代に急増」）。"
                            " 新表記に統一しますか？（通時的な表記変化そのものを研究する場合は統一しないでください）"
                        ),
                        "suggest_option": "norm_1996",
                        "suggest_value": True,
                    }
                )
        return out
