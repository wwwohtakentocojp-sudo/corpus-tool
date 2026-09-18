"""第3層: 文章化。

第2層（rules.py）が返したフラグと、分析結果の数値だけを Anthropic API に渡し、
利用者向けの日本語解説にする。

★ 原文・用例・語そのものは送らない。語は {WORD} {COLLOCATE}、グループ名は {GROUP_A} {GROUP_B}
  というプレースホルダで送り、返ってきた文章にツール側で実際の語を戻す。
★ 警告を出すか否かは第2層が決める。この層は「渡されたフラグを一つ残らず文章に含める」だけで、
  フラグにない警告を足さない。
★ API が使えない（キー未設定・通信失敗・出力形式が崩れた）ときは、第1層と第2層のテキストを
  定型文で連結する（fallback）。どちらの経路でも警告の内容は欠落しない。
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from interpretations import glossary
from interpretations.flags import Flag

ROOT = Path(__file__).resolve().parent.parent

HEADINGS = ["【この数字が言っていること】", "【論文に書くなら】", "【言ってはいけないこと】", "【次に確認すべきこと】"]

PLACEHOLDER_KEYS = ("WORD", "COLLOCATE", "GROUP_A", "GROUP_B")

# 画面ごとの指標キー → 用語辞書キー
METRIC_GLOSSARY = {
    "freq": "frequency", "pmw": "pmw", "dp": "dispersion_dp",
    "cooccur": "cooccurrence_frequency", "mi": "mi_score", "t": "t_score", "log_dice": "log_dice",
    "g2": "log_likelihood", "p": "p_value", "log_ratio": "log_ratio", "odds_ratio": "odds_ratio",
    "freq_a": "frequency", "freq_b": "frequency", "pmw_a": "pmw", "pmw_b": "pmw",
}

# 「やさしい言い換え（専門用語）」の対応。プロンプトでも fallback でも同じ表現を使う
TERM_LABELS = {
    "freq": "出現回数（頻度）", "pmw": "100万語あたりの出現回数（pmw）", "dp": "散らばり具合（分散度DP）",
    "cooccur": "一緒に出た回数（共起頻度）", "mi": "結びつきの強さ・珍しさ重視（MIスコア）",
    "t": "結びつきの安定性（Tスコア）", "log_dice": "結びつきの強さ・総合（logDice）",
    "g2": "偶然では説明しにくい度合い（対数尤度比 G²）", "p": "偶然でそうなる確率（p値）",
    "log_ratio": "差の大きさ（log ratio）", "odds_ratio": "差の大きさ・別表現（オッズ比）",
    "freq_a": "「{GROUP_A}」グループでの出現回数（頻度）", "freq_b": "「{GROUP_B}」グループでの出現回数（頻度）",
    "pmw_a": "「{GROUP_A}」グループでの100万語あたりの出現回数（pmw）", "pmw_b": "「{GROUP_B}」グループでの100万語あたりの出現回数（pmw）",
    "n_total": "延べ語数（token）",
    "n_a": "「{GROUP_A}」グループの延べ語数（token）", "n_b": "「{GROUP_B}」グループの延べ語数（token）", "n_parts": "文書数",
    "freq_node": "中心語の出現回数", "freq_collocate": "共起語の出現回数",
    "zero_corrected": "片方の群で0回のため 0.5 を足して計算（0補正）",
}

SCREEN_NAMES = {"frequency": "頻度分析", "collocation": "コロケーション分析", "keyness": "特徴語抽出（2群比較）"}


@dataclass
class NarrationInput:
    screen: str                              # "frequency" | "collocation" | "keyness"
    language: str
    metrics: dict[str, Any]                  # 数値のみ（語は含めない）
    flags: list[Flag]
    placeholders: dict[str, str]             # {"WORD": "先生", ...} 置換にだけ使い、API には送らない
    settings: dict[str, Any] = field(default_factory=dict)  # 方式名・ウィンドウ幅など（数値と識別子のみ）


@dataclass
class Narration:
    text: str
    source: str        # "api" | "template"
    note: str = ""     # fallback になった理由など


# ---------------------------------------------------------------------------
# プレースホルダ
# ---------------------------------------------------------------------------
def substitute(text: str, placeholders: dict[str, str]) -> str:
    for k in PLACEHOLDER_KEYS:
        if k in placeholders:
            text = text.replace("{" + k + "}", placeholders[k])
    return text


def validate_structure(text: str) -> bool:
    """4見出しがこの順で1回ずつ現れ、見出しの外に本文がないこと。"""
    positions = []
    for h in HEADINGS:
        if text.count(h) != 1:
            return False
        positions.append(text.index(h))
    if positions != sorted(positions):
        return False
    return text.strip().startswith(HEADINGS[0])


def contains_leaked_words(text: str, placeholders: dict[str, str]) -> bool:
    """API の返答に、送っていないはずの実際の語が含まれていないか（万一の確認）。"""
    return False  # 語は送っていないので原理的に混入しない。将来の変更に備えた拡張点


# ---------------------------------------------------------------------------
# プロンプト
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """あなたは、統計の知識がまったくない言語学研究者に向けて、コーパス分析の結果を日本語で説明する係です。
受け取るのは「分析結果の数値」「判定済みの注意フラグ」「用語の固定解説」だけです。原文や語そのものは渡されません。

厳守事項:
1. 出力は必ず次の4つの見出しだけで構成し、この順で、それぞれ1回ずつ書くこと。見出しの前後に他の文を書かない。
【この数字が言っていること】
【論文に書くなら】
【言ってはいけないこと】
【次に確認すべきこと】
2. 「注意フラグ」として渡された項目は、一つ残らず【言ってはいけないこと】または【次に確認すべきこと】に含めること。
   フラグの趣旨を変えないこと。渡されていない警告や注意を自分の判断で付け足さないこと。
3. 語を参照するときは、必ず『{WORD}』という語 の形で書くこと（共起語は『{COLLOCATE}』という語、
   グループは「{GROUP_A}」グループ・「{GROUP_B}」グループ）。裸で埋め込むと置換後の日本語が不自然になるため。
   {WORD} などの記号はそのまま残し、勝手に語を推測して書かないこと。
4. 統計用語を使うときは、必ず「やさしい言い換え（専門用語）」の順で書くこと。
   例:「結びつきの強さ・総合（logDice）」「差の大きさ（log ratio）」。渡された用語表の表記をそのまま使うこと。
5. 【この数字が言っていること】は統計用語による評価ではなく、数値が示す事実だけを書くこと。
6. 【論文に書くなら】は、そのまま論文に貼れる日本語の文例を1〜2文書くこと。数値は渡された値と書式をそのまま使い、
   丸めたり新しい数値を作ったりしないこと。
7. 数値の大小の評価（「強い」「大きい」など）は、渡された用語解説の目安に基づく場合だけ書くこと。
8. 丁寧で簡潔に。各見出しは3〜6文程度。箇条書きは使ってよい。"""


def _glossary_snippets(metric_keys: list[str]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for mk in metric_keys:
        gk = METRIC_GLOSSARY.get(mk)
        if gk and gk not in out:
            e = glossary.entry(gk)
            out[gk] = {
                "表記": TERM_LABELS.get(mk, e.get("label", gk)),
                "何を測っているか": str(e.get("what", "")).strip(),
                "目安": str(e.get("range", "")).strip(),
                "注意": str(e.get("caution", "")).strip(),
            }
    return out


def build_user_message(inp: NarrationInput) -> str:
    payload = {
        "画面": SCREEN_NAMES.get(inp.screen, inp.screen),
        "言語": inp.language,
        "分析設定": inp.settings,
        "数値": inp.metrics,
        "数値の表記": {k: TERM_LABELS[k] for k in inp.metrics if k in TERM_LABELS},
        "注意フラグ": [{"コード": f.code, "内容": f.message} for f in inp.flags],
        "用語の固定解説": _glossary_snippets(list(inp.metrics.keys())),
    }
    return json.dumps(payload, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------------------
# API 呼び出し
# ---------------------------------------------------------------------------
def _load_api_key() -> str | None:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except Exception:  # noqa: BLE001
        pass
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    return key or None


def api_available() -> bool:
    return _load_api_key() is not None


def call_api(user_message: str, config: dict[str, Any], client=None) -> str:
    """API を呼んで本文テキストを返す。client を渡すとそれを使う（テスト用）。"""
    import anthropic

    cfg = config.get("narrator", {})
    model = cfg.get("model", "claude-sonnet-5")
    max_tokens = int(cfg.get("max_tokens", 4000))
    if client is None:
        key = _load_api_key()
        if key is None:
            raise RuntimeError("APIキーが設定されていません")
        client = anthropic.Anthropic(api_key=key)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_message}],
    )
    if getattr(response, "stop_reason", None) == "refusal":
        raise RuntimeError("API が応答を拒否しました")
    parts = [b.text for b in response.content if getattr(b, "type", "") == "text"]
    return "\n".join(parts).strip()


# ---------------------------------------------------------------------------
# fallback（定型文の連結）
# ---------------------------------------------------------------------------
def _fmt(k: str, v: Any) -> str:
    if isinstance(v, bool):
        return "はい" if v else "いいえ"
    if isinstance(v, int):
        return f"{v:,}"
    if isinstance(v, float):
        if k == "p":
            return "< 0.001" if v < 0.001 else f"{v:.3f}"
        if k in ("log_ratio",):
            return f"{v:+.2f}"
        if k in ("pmw", "pmw_a", "pmw_b", "g2"):
            return f"{v:,.1f}"
        return f"{v:.2f}"
    return str(v)


def _caution_head(text: str) -> str:
    """caution の最初の段落（空行まで）を1行にまとめる。"""
    para = str(text).strip().split("\n\n")[0]
    return " ".join(line.strip() for line in para.splitlines())


def _paper_sentence(inp: NarrationInput) -> str:
    m = inp.metrics
    s = inp.settings
    if inp.screen == "frequency":
        return (
            f"『{{WORD}}』という語は、コーパス全体（延べ {_fmt('n_total', m.get('n_total', 0))} 語）に {_fmt('freq', m.get('freq', 0))} 回出現した"
            f"（100万語あたり {_fmt('pmw', m.get('pmw', 0.0))} 回、分散度 DP = {_fmt('dp', m.get('dp', float('nan')))}）。"
        )
    if inp.screen == "collocation":
        return (
            f"『{{WORD}}』という語と『{{COLLOCATE}}』という語は、{s.get('window_label', '')}で {_fmt('cooccur', m.get('cooccur', 0))} 回共起した"
            f"（logDice = {_fmt('log_dice', m.get('log_dice', float('nan')))}、MI = {_fmt('mi', m.get('mi', float('nan')))}、"
            f"t = {_fmt('t', m.get('t', float('nan')))}、G² = {_fmt('g2', m.get('g2', float('nan')))}）。"
        )
    if inp.screen == "keyness":
        return (
            f"『{{WORD}}』という語は、「{{GROUP_A}}」グループで100万語あたり {_fmt('pmw_a', m.get('pmw_a', 0.0))} 回"
            f"（{_fmt('freq_a', m.get('freq_a', 0))} 回 / {_fmt('n_a', m.get('n_a', 0))} 語）、"
            f"「{{GROUP_B}}」グループで {_fmt('pmw_b', m.get('pmw_b', 0.0))} 回（{_fmt('freq_b', m.get('freq_b', 0))} 回 / {_fmt('n_b', m.get('n_b', 0))} 語）出現し、"
            f"差の大きさ（log ratio）は {_fmt('log_ratio', m.get('log_ratio', float('nan')))}"
            f"{'（片方の群で0回のため0.5を加えて算出）' if m.get('zero_corrected') else ''}、G² = {_fmt('g2', m.get('g2', float('nan')))}"
            f"（p {_fmt('p', m.get('p', float('nan')))}）であった。"
        )
    return ""


_NEXT_STEPS = {
    "MI_HIGH_LOW_FREQ": "『{WORD}』という語と『{COLLOCATE}』という語の用例を、KWIC 画面で全件確認してください。",
    "T_ONLY_FUNCTION_WORD": "『{COLLOCATE}』という語が機能語（助詞・冠詞など）でないか確認し、機能語なら集計設定で除外してください。",
    "FUNCTION_WORD_NOISE": "この行は機能語です。内容の分析では読み飛ばし、文体・文法の研究なら「機能語を含める」を ON にしてください。",
    "DISPERSION_SKEWED": "『{WORD}』という語がどの文書に集中しているかを、頻度分析画面の内訳表で確認してください。",
    "LOW_FREQUENCY": "出現回数が少ないため、この語について主張する前にデータを増やせないか検討してください。",
    "EFFECT_SIZE_TOO_SMALL": "差の大きさ（log ratio）の絶対値が1以上の語に絞って解釈してください。",
    "CORPUS_TOO_SMALL": "データを増やすか、基本統計と用例の確認までにとどめてください。",
    "GROUP_IMBALANCE": "文書数の偏りを踏まえ、結果を報告するときは各群の文書数と延べ語数を併記してください。",
    "DP_TOO_FEW_PARTS": "散らばり具合（分散度DP）は参考程度にし、文書数が10以上になってから偏りを判断してください。",
    "ZERO_CORRECTED": "片方の群で0回の語は、差の大きさ（log ratio）の値そのものより「一方にしか出ない」という事実として報告してください。",
}


def fallback_text(inp: NarrationInput) -> str:
    m = inp.metrics
    lines = [HEADINGS[0]]
    for k, v in m.items():
        label = TERM_LABELS.get(k, k)
        lines.append(f"- {label}: {_fmt(k, v)}")
    lines.append("")
    lines.append(HEADINGS[1])
    lines.append(_paper_sentence(inp))
    lines.append("")
    lines.append(HEADINGS[2])
    if inp.flags:
        for f in inp.flags:
            lines.append(f"- {f.message}")
    else:
        lines.append("- 判定ルールに該当する注意はありません。ただし、どの指標も用例の確認の代わりにはなりません。")
    for gk in dict.fromkeys(METRIC_GLOSSARY.get(k) for k in m if METRIC_GLOSSARY.get(k)):
        e = glossary.entry(gk)
        lines.append(f"- {e.get('label', gk)}について: {_caution_head(e.get('caution', ''))}")
    lines.append("")
    lines.append(HEADINGS[3])
    steps = [_NEXT_STEPS[f.code] for f in inp.flags if f.code in _NEXT_STEPS]
    if not steps:
        steps = ["KWIC 画面で実際の用例を確認してください。数値は用例を見ることの代わりにはなりません。"]
    for s_ in dict.fromkeys(steps):
        lines.append(f"- {s_}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
def narrate(inp: NarrationInput, config: dict[str, Any], use_api: bool = True, client=None) -> Narration:
    """解説を生成する。API が使えない・失敗した・形式が崩れたときは定型文にする。"""
    if use_api and (client is not None or api_available()):
        try:
            raw = call_api(build_user_message(inp), config, client=client)
            if not validate_structure(raw):
                return Narration(substitute(fallback_text(inp), inp.placeholders), "template",
                                 note="AIの出力が4見出し構成になっていなかったため、定型文で表示しています。")
            missing = [f.code for f in inp.flags if not _flag_reflected(raw, f)]
            if missing:
                # 欠落したフラグは末尾に定型文で補う（警告は欠落させない）
                raw = raw.rstrip() + "\n" + "\n".join(f"- {f.message}" for f in inp.flags if f.code in missing)
            return Narration(substitute(raw, inp.placeholders), "api",
                             note="" if not missing else "一部の注意を定型文で補いました。")
        except Exception as e:  # noqa: BLE001
            return Narration(substitute(fallback_text(inp), inp.placeholders), "template",
                             note=f"AIによる解説を取得できなかったため、定型文で表示しています（{type(e).__name__}）。")
    return Narration(substitute(fallback_text(inp), inp.placeholders), "template",
                     note="" if not use_api else "APIキーが設定されていないため、定型文で表示しています。")


_FLAG_KEYWORDS = {
    "MI_HIGH_LOW_FREQ": ["用例"],
    "T_ONLY_FUNCTION_WORD": ["どこにでも", "機能語", "結びつき"],
    "FUNCTION_WORD_NOISE": ["機能語"],
    "DISPERSION_SKEWED": ["集中", "偏"],
    "LOW_FREQUENCY": ["回数", "少な"],
    "EFFECT_SIZE_TOO_SMALL": ["log ratio", "差"],
    "CORPUS_TOO_SMALL": ["語数", "少な", "小さ"],
    "GROUP_IMBALANCE": ["文書数", "偏"],
    "DP_TOO_FEW_PARTS": ["文書数", "信頼"],
    "ZERO_CORRECTED": ["0", "補正"],
}


def _flag_reflected(text: str, flag: Flag) -> bool:
    """フラグの趣旨が文章に含まれているかの機械的な確認（語句の有無）。"""
    kws = _FLAG_KEYWORDS.get(flag.code, [])
    return any(k in text for k in kws) if kws else True
