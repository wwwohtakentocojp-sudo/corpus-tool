"""第3層: 解説文の組み立て（AI は使わない。純粋な定型文の選別）。

設計方針:
  - 何を言うかは第2層（rules.py）のフラグだけが決める。ここは選ばれたフラグに対応する
    文を並べるだけで、フラグにない注意を足さない。
  - 指標の一般的な注意（「MI は低頻度語を過大評価する」など）はここでは出さない。
    それは「?」（用語辞書）から参照するもので、毎回表示するものではない。
    毎回同じ注意が並ぶと利用者は読まなくなり、警告そのものが無効になる。
  - フラグが1つも無ければ【言ってはいけないこと】【次に確認すべきこと】は出さない。
    代替文（「特に注意はありません」）も出さない。

出力の見出し（該当する部分だけ出す）:
  【この数字が言っていること】 フラグに応じた1〜2文の判定。フラグが無ければ水準を1文で
  【論文に書くなら】           そのまま貼れる文例
  【言ってはいけないこと】     フラグ由来の行のみ
  【次に確認すべきこと】       フラグ由来の行のみ
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from interpretations.flags import Flag

H_FACT = "【この数字が言っていること】"
H_PAPER = "【論文に書くなら】"
H_DONT = "【言ってはいけないこと】"
H_NEXT = "【次に確認すべきこと】"


@dataclass
class ExplainInput:
    screen: str                      # "frequency" | "collocation" | "keyness"
    metrics: dict[str, Any]
    flags: list[Flag]
    words: dict[str, str]            # WORD / COLLOCATE / GROUP_A / GROUP_B
    settings: dict[str, Any] = field(default_factory=dict)   # window_label など


# ---------------------------------------------------------------------------
# 書式
# ---------------------------------------------------------------------------
def fmt(key: str, v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "はい" if v else "いいえ"
    if isinstance(v, int):
        return f"{v:,}"
    if isinstance(v, float):
        if v != v:  # NaN
            return "—"
        if key == "p":
            return "< 0.001" if v < 0.001 else f"{v:.3f}"
        if key == "log_ratio":
            return f"{v:+.2f}"
        if key in ("pmw", "pmw_a", "pmw_b", "g2"):
            return f"{v:,.1f}"
        if key in ("ratio",):
            return f"{v:.1f}"
        return f"{v:.2f}"
    return str(v)


class _Safe(dict):
    def __missing__(self, k):
        return "{" + k + "}"


def _render(template: str, inp: ExplainInput, flag: Flag | None = None) -> str:
    ctx: dict[str, Any] = {}
    ctx.update({k: fmt(k, v) for k, v in inp.metrics.items()})
    if flag:
        ctx.update({k: fmt(k, v) for k, v in flag.details.items()})
    ctx.update(inp.words)
    return template.format_map(_Safe(ctx))


# ---------------------------------------------------------------------------
# フラグ → 判定文（【この数字が言っていること】用。1文ずつ）
# ---------------------------------------------------------------------------
JUDGMENTS: dict[str, str] = {
    "BOTH_HIGH_FREQUENCY": "『{WORD}』と『{COLLOCATE}』はどちらも非常によく使われる語です。結びつきの強さ・総合（logDice）が {log_dice} と高いのは両方がよく出る語だからで、特別な結びつきとは言えません。",
    "T_ONLY_FUNCTION_WORD": "『{WORD}』と『{COLLOCATE}』は {cooccur} 回一緒に出ていますが、珍しさ重視の結びつき（MIスコア）は {mi} と低く、『{COLLOCATE}』がどこにでも出る語であるために並んでいるだけです。",
    "LOW_COOCCURRENCE": "『{WORD}』と『{COLLOCATE}』は指標の上では結びつきがありそうに見えますが（logDice = {log_dice}、MI = {mi}）、一緒に出た回数が {cooccur} 回しかなく、この回数では指標の値自体が安定しません。",
    "NOT_DISTINGUISHABLE": "『{WORD}』と『{COLLOCATE}』は {cooccur} 回一緒に出ていますが、偶然では説明しにくい度合い（G²）は {g2} で目安の {threshold} に達しておらず、偶然そうなったのかどうかを今のデータでは区別できません。",
    "FUNCTION_WORD_NOISE": "『{COLLOCATE}』は機能語（助詞・冠詞など）で、内容の分析では読み飛ばす行です。",
    "DP_TOO_FEW_PARTS": "『{WORD}』は {freq} 回出現しています。文書数が {n_parts} と少ないため、散らばり具合（分散度DP）= {dp} は参考値にとどまります。",
    "DISPERSION_SKEWED": "『{WORD}』は {freq} 回出現していますが、散らばり具合（分散度DP）が {dp} で、一部の文書に集中しています。",
    "LOW_FREQUENCY": "『{WORD}』の出現回数は {freq} 回で、主張の根拠にするには少なすぎます。",
    "ZERO_CORRECTED": "『{WORD}』は「{GROUP_PRESENT}」グループに {freq_present} 回出ていますが、「{GROUP_ABSENT}」グループには一度も出ていません。差の大きさ（log ratio）= {log_ratio} は、0 回の側に 0.5 を足して求めた補正値です。",
    "EFFECT_SIZE_TOO_SMALL": "『{WORD}』の差の大きさ（log ratio）は {log_ratio} で、目安の 1（2倍）に達していません。実質的な差はごくわずかです。",
    "GROUP_IMBALANCE": "比較した2つのグループは文書数に {ratio} 倍の偏りがあります（「{group_a}」{size_a} 文書、「{group_b}」{size_b} 文書）。",
    "CORPUS_TOO_SMALL": "総語数が {total_tokens} 語で、目安の {threshold} 語に達していません。",
}

# フラグ → 次に確認すべきこと
NEXT_STEPS: dict[str, str] = {
    "LOW_COOCCURRENCE": "『{WORD}』と『{COLLOCATE}』の用例を、KWIC 画面で全件（{cooccur} 件）確認してください。",
    "NOT_DISTINGUISHABLE": "この組み合わせについては結論を出さず、データを増やすか、別の組み合わせを検討してください。",
    "BOTH_HIGH_FREQUENCY": "この組み合わせは発見として扱わず、logDice が高く、かつ共起語の出現回数が際立って多くはない組み合わせを探してください。",
    "T_ONLY_FUNCTION_WORD": "『{COLLOCATE}』が機能語なら、集計設定で機能語を除外してください。内容語なら、この行は読み飛ばしてください。",
    "FUNCTION_WORD_NOISE": "文体・文法の研究で機能語を対象にする場合だけ「機能語を含める」を ON にしてください。",
    "DISPERSION_SKEWED": "『{WORD}』がどの文書に集中しているかを、頻度分析画面の内訳表で確認してください。",
    "LOW_FREQUENCY": "『{WORD}』について主張する前に、データを増やせないか検討してください。",
    "DP_TOO_FEW_PARTS": "散らばり具合（分散度DP）は、文書数が 10 以上になってから判断してください。",
    "ZERO_CORRECTED": "『{WORD}』は、差の大きさの数値ではなく「{GROUP_ABSENT}」グループには出ないという事実として報告し、KWIC 画面で「{GROUP_PRESENT}」グループでの用例を確認してください。",
    "EFFECT_SIZE_TOO_SMALL": "差の大きさ（log ratio）の絶対値が 1 以上の語に絞って解釈してください。",
    "GROUP_IMBALANCE": "結果を報告するときは、各グループの文書数と延べ語数を併記してください。",
    "CORPUS_TOO_SMALL": "データを増やすか、基本統計と用例の確認までにとどめてください。",
}

# 判定文を出す順（重要なものを先に）
_ORDER = ["CORPUS_TOO_SMALL", "GROUP_IMBALANCE", "BOTH_HIGH_FREQUENCY", "T_ONLY_FUNCTION_WORD", "LOW_COOCCURRENCE",
          "NOT_DISTINGUISHABLE", "FUNCTION_WORD_NOISE", "DP_TOO_FEW_PARTS", "DISPERSION_SKEWED", "LOW_FREQUENCY",
          "ZERO_CORRECTED", "EFFECT_SIZE_TOO_SMALL"]

# 表の注意列にだけ出し、解説文には出さないフラグ（弱い注記）
TABLE_ONLY = {"LOW_COOCCURRENCE_MINOR"}

# 「よく使われる語どうし」の趣旨を既に述べるフラグ。これらがあれば食い違いの文は重複するので出さない
_ALREADY_EXPLAINS_DISAGREEMENT = {"BOTH_HIGH_FREQUENCY", "T_ONLY_FUNCTION_WORD"}


def _disagreement_sentence(inp: ExplainInput, th: dict[str, Any]) -> str | None:
    """指標の示す方向が食い違うとき（logDice は目安以上なのに MI または G² が目安未満）、
    食い違っていること自体を先に述べる。該当しなければ None。"""
    if inp.screen != "collocation":
        return None
    m, w = inp.metrics, inp.words
    ld, mi, g2 = m.get("log_dice"), m.get("mi"), m.get("g2")
    if ld is None or ld != ld or ld < float(th.get("log_dice_strong", 7.0)):
        return None
    mi_low = mi is not None and mi == mi and mi < float(th.get("mi_meaningful", 3.0))
    g2_low = g2 is not None and g2 == g2 and g2 < float(th.get("g2_significant", 6.63))
    if not (mi_low or g2_low):
        return None
    head = f"『{w.get('WORD')}』と『{w.get('COLLOCATE')}』は、指標によって評価が分かれます。総合的な強さ（logDice = {fmt('log_dice', ld)}）は高い一方、"
    if mi_low:
        return head + (f"珍しさ（MI = {fmt('mi', mi)}）は偶然に近い水準です。"
                       "これは『よく使われる語どうしなので自然と一緒に出る』という状態で、特別な結びつきとは言えません。")
    return head + (f"偶然では説明しにくい度合い（G² = {fmt('g2', g2)}）は目安に達していません。"
                   "回数が少なく、偶然そうなったのかどうかを区別できない状態です。")


def _sorted_flags(flags: list[Flag]) -> list[Flag]:
    rank = {c: i for i, c in enumerate(_ORDER)}
    return sorted(flags, key=lambda f: rank.get(f.code, 99))


# ---------------------------------------------------------------------------
# フラグが無いときの水準判定（1文）
# ---------------------------------------------------------------------------
def _level_sentence(inp: ExplainInput, th: dict[str, Any]) -> str:
    m = inp.metrics
    w = inp.words
    if inp.screen == "collocation":
        ld, mi, g2 = m.get("log_dice"), m.get("mi"), m.get("g2")
        strong = float(th.get("log_dice_strong", 7.0))
        mi_ok = float(th.get("mi_meaningful", 3.0))
        g2_ok = float(th.get("g2_significant", 6.63))
        head = f"『{w.get('WORD')}』と『{w.get('COLLOCATE')}』は {fmt('cooccur', m.get('cooccur'))} 回一緒に出ており"
        parts = []
        if ld is not None and ld == ld:
            parts.append(f"結びつきの強さ・総合（logDice）は {fmt('log_dice', ld)} で目安の {strong:g} を{'上回り' if ld >= strong else '下回り'}")
        if mi is not None and mi == mi:
            parts.append(f"珍しさ重視（MIスコア）は {fmt('mi', mi)} で{'結びつきありの水準' if mi >= mi_ok else '偶然に近い水準'}")
        if g2 is not None and g2 == g2:
            parts.append(f"偶然では説明しにくい度合い（G²）は {fmt('g2', g2)} で{'偶然では説明しにくい水準' if g2 >= g2_ok else f'目安の {g2_ok:g} 未満'}")
        return head + ("、" + "、".join(parts) + "です" if parts else "ます") + "。"
    if inp.screen == "frequency":
        dp = m.get("dp")
        skew = float(th.get("dp_skew", 0.5))
        if dp is not None and dp == dp:
            rel = "上回っています（一部に偏り）" if dp > skew else "下回っており、全体にまんべんなく出ています"
            return f"『{w.get('WORD')}』は {fmt('freq', m.get('freq'))} 回（100万語あたり {fmt('pmw', m.get('pmw'))} 回）出現し、散らばり具合（分散度DP）は {fmt('dp', dp)} で、目安の {skew:g} を{rel}。"
        return f"『{w.get('WORD')}』は {fmt('freq', m.get('freq'))} 回（100万語あたり {fmt('pmw', m.get('pmw'))} 回）出現しています。"
    if inp.screen == "keyness":
        lr = m.get("log_ratio")
        side = w.get("GROUP_A") if (lr or 0) > 0 else w.get("GROUP_B")
        times = 2 ** abs(lr) if lr is not None and lr == lr else None
        times_s = f"（約 {times:.1f} 倍）" if times is not None and times < 100 else ""
        return f"『{w.get('WORD')}』は「{side}」グループのほうに多く、差の大きさ（log ratio）は {fmt('log_ratio', lr)}{times_s} で、目安の 1（2倍）以上です。"
    return ""


# ---------------------------------------------------------------------------
# 論文用の文例
# ---------------------------------------------------------------------------
def _paper_sentence(inp: ExplainInput, codes: set[str]) -> str:
    m, w, s = inp.metrics, inp.words, inp.settings
    if inp.screen == "frequency":
        base = f"『{w.get('WORD')}』は、コーパス全体（延べ {fmt('n_total', m.get('n_total'))} 語）に {fmt('freq', m.get('freq'))} 回出現した（100万語あたり {fmt('pmw', m.get('pmw'))} 回"
        if "DP_TOO_FEW_PARTS" in codes:
            return base + "）。"
        return base + f"、分散度 DP = {fmt('dp', m.get('dp'))}）。"
    if inp.screen == "collocation":
        return (
            f"『{w.get('WORD')}』と『{w.get('COLLOCATE')}』は、{s.get('window_label', '')}で {fmt('cooccur', m.get('cooccur'))} 回共起した"
            f"（logDice = {fmt('log_dice', m.get('log_dice'))}、MI = {fmt('mi', m.get('mi'))}、t = {fmt('t', m.get('t'))}、G² = {fmt('g2', m.get('g2'))}）。"
        )
    if inp.screen == "keyness":
        corr = "（片方の群で 0 回のため 0.5 を加えて算出）" if "ZERO_CORRECTED" in codes else ""
        return (
            f"『{w.get('WORD')}』は、「{w.get('GROUP_A')}」グループで100万語あたり {fmt('pmw_a', m.get('pmw_a'))} 回"
            f"（{fmt('freq_a', m.get('freq_a'))} 回 / {fmt('n_a', m.get('n_a'))} 語）、"
            f"「{w.get('GROUP_B')}」グループで {fmt('pmw_b', m.get('pmw_b'))} 回（{fmt('freq_b', m.get('freq_b'))} 回 / {fmt('n_b', m.get('n_b'))} 語）出現し、"
            f"差の大きさ（log ratio）は {fmt('log_ratio', m.get('log_ratio'))}{corr}、G² = {fmt('g2', m.get('g2'))}（p {fmt('p', m.get('p'))}）であった。"
        )
    return ""


# ---------------------------------------------------------------------------
def _augment_words(inp: ExplainInput) -> ExplainInput:
    """ZERO_CORRECTED 用に、出ている側／出ていない側のグループ名を用意する。"""
    if inp.screen != "keyness":
        return inp
    m, w = inp.metrics, dict(inp.words)
    if (m.get("freq_a") or 0) > 0 and (m.get("freq_b") or 0) == 0:
        w["GROUP_PRESENT"], w["GROUP_ABSENT"], freq_present = w.get("GROUP_A", ""), w.get("GROUP_B", ""), m.get("freq_a")
    elif (m.get("freq_b") or 0) > 0 and (m.get("freq_a") or 0) == 0:
        w["GROUP_PRESENT"], w["GROUP_ABSENT"], freq_present = w.get("GROUP_B", ""), w.get("GROUP_A", ""), m.get("freq_b")
    else:
        return inp
    metrics = dict(m)
    metrics["freq_present"] = freq_present
    return ExplainInput(inp.screen, metrics, inp.flags, w, inp.settings)


def explain_sections(inp: ExplainInput, thresholds: dict[str, Any]) -> list[tuple[str, list[str]]]:
    """(見出し, 行のリスト) の並び。空になる見出しは含めない。"""
    inp = _augment_words(inp)
    flags = _sorted_flags([f for f in inp.flags if f.code not in TABLE_ONLY])
    codes = {f.code for f in flags}
    sections: list[tuple[str, list[str]]] = []

    facts: list[str] = []
    if not (codes & _ALREADY_EXPLAINS_DISAGREEMENT):
        d = _disagreement_sentence(inp, thresholds)
        if d:
            facts.append(d)
    facts += [_render(JUDGMENTS[f.code], inp, f) for f in flags if f.code in JUDGMENTS]
    facts = list(dict.fromkeys(facts))[:2] if facts else [_level_sentence(inp, thresholds)]
    sections.append((H_FACT, [x for x in facts if x]))

    sections.append((H_PAPER, [_paper_sentence(inp, codes)]))

    donts = list(dict.fromkeys(f.message for f in flags))
    if donts:
        sections.append((H_DONT, donts))

    nexts = list(dict.fromkeys(_render(NEXT_STEPS[f.code], inp, f) for f in flags if f.code in NEXT_STEPS))
    if nexts:
        sections.append((H_NEXT, nexts))
    return sections


def explain(inp: ExplainInput, thresholds: dict[str, Any]) -> str:
    """プレーンテキスト。見出しの下に、1行なら本文、複数行なら箇条書き。"""
    out: list[str] = []
    for heading, lines in explain_sections(inp, thresholds):
        out.append(heading)
        if len(lines) == 1:
            out.append(lines[0])
        else:
            out.extend(f"- {ln}" for ln in lines)
        out.append("")
    return "\n".join(out).rstrip()
