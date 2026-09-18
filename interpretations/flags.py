"""第2層のフラグ定義と、それぞれに対応する固定文言。

フラグ = 「警告を出すべき状況」の識別子。
文言はここに固定テキストとして持つ。第3層（explainer）は、立っているフラグの
この文言をそのまま【言ってはいけないこと】に並べる。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# レベル: "warning" は赤/黄で目立たせる、"info" は補足
WARNING = "warning"
INFO = "info"


@dataclass(frozen=True)
class Flag:
    code: str
    level: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


# code -> (level, テンプレート文)
# テンプレートには details のキーを {name} 形式で埋め込める。
FLAG_TEXTS: dict[str, tuple[str, str]] = {
    "CORPUS_TOO_SMALL": (
        WARNING,
        "総語数が {total_tokens:,} 語で、目安の {threshold:,} 語に達していません。"
        "このデータ量では、語の出現回数の違いが「偶然そうなっただけ」である可能性が高く、"
        "特徴語や共起の分析結果はほぼ信用できません。"
        "基本統計と用例（KWIC）の確認までにとどめるか、データを増やしてから分析してください。",
    ),
    "DISPERSION_SKEWED": (
        WARNING,
        "『{word}』は {freq:,} 回出ていますが、散らばり具合（分散度DP）が {dp:.2f} で、"
        "一部の文書に集中しています（目安 {threshold} 超）。"
        "この語を「このデータでよく使われる語」と呼ぶのは危険です。"
        "どの文書に集中しているかを必ず確認してください。",
    ),
    "DP_TOO_FEW_PARTS": (
        INFO,
        "文書数が {n_parts} と少ないため（目安 {threshold} 未満）、散らばり具合（分散度DP）の判定は信頼できません。"
        "この列は参考程度にしてください。文書数が {threshold} 以上になると、偏りのある語への個別の警告が有効になります。",
    ),
    "LOW_FREQUENCY": (
        INFO,
        "『{word}』の出現回数は {freq} 回です。{threshold} 回未満の語について何かを主張するのは避けてください。",
    ),
    # --- Phase 1 以降 ---
    "GROUP_IMBALANCE": (
        WARNING,
        "グループ「{group_a}」が {size_a:,} 文書、「{group_b}」が {size_b:,} 文書で、"
        "文書数に {ratio:.1f} 倍の偏りがあります。文書数の偏りにより結果が歪む可能性があります。",
    ),
    "MI_HIGH_LOW_FREQ": (
        WARNING,
        "MIスコアは高い（{mi:.1f}）ですが、一緒に出た回数が {cooccur} 回しかありません。"
        "回数が {threshold} 回未満の組み合わせは、用例を全て自分の目で確認してから扱ってください。",
    ),
    "BOTH_HIGH_FREQUENCY": (
        WARNING,
        "どちらも非常によく使われる語どうしの組み合わせです（中心語 {freq_node:,} 回、共起語 {freq_collocate:,} 回。"
        "いずれも頻度上位 {top_percent:g}% 以内）。logDice が高くても、特別な結びつきとは言えません。",
    ),
    "T_ONLY_FUNCTION_WORD": (
        WARNING,
        "Tスコアは高い（{t:.1f}）のにMIスコアは低い（{mi:.1f}）組み合わせです。"
        "単にどこにでも出る語が隣にあっただけで、結びつきが強いわけではありません。",
    ),
    "FUNCTION_WORD_NOISE": (
        INFO,
        "『{word}』は機能語です。機能語を除外する設定になっているため、この行はノイズとして読み飛ばしてください。",
    ),
    "ZERO_CORRECTED": (
        INFO,
        "『{word}』は片方のグループで出現回数が 0 です。差の大きさ（log ratio）は 0 回の側に 0.5 を足した補正値で、"
        "オッズ比は算出していません。値そのものより「一方のグループにしか出ない」という事実として扱ってください。",
    ),
    "EFFECT_SIZE_TOO_SMALL": (
        WARNING,
        "『{word}』の差の大きさ（log ratio）は {log_ratio:+.2f} で、絶対値が {threshold} 未満です。"
        "p値が小さくても、実質的な差としては小さすぎます。発見として扱わないでください。",
    ),
}


def make_flag(code: str, **details: Any) -> Flag:
    level, template = FLAG_TEXTS[code]
    try:
        message = template.format(**details)
    except (KeyError, ValueError):
        message = template
    return Flag(code=code, level=level, message=message, details=dict(details))
