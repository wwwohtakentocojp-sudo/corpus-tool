"""7. 特徴語抽出（2群比較: G² と log ratio）"""
from __future__ import annotations

import streamlit as st

from app_config import thresholds
from corpus.checks import group_columns, group_sizes
from interpretations import glossary
from interpretations.explainer import ExplainInput
from interpretations.rules import check_group_imbalance, check_keyness_row, flag_keyness_table
from stats.keyness import keyness_table, split_by_group
from ui import state
from ui.components import download_csv, explanation_panel, glossary_expander, show_flags

st.title("7. 特徴語抽出（2つのグループの比較）")
corpus = state.require_corpus()
s = state.sidebar_display_options()
cfg = state.config()
th = thresholds(cfg)
kcfg = cfg.get("keyness", {})

st.warning(
    "★ データが大きいと、検定（p値）はほとんど全ての語で「有意」になります。"
    " p値ではなく **差の大きさ（log ratio）** で判断してください。+1 で2倍、+2 で4倍、+3 で8倍。目安は絶対値 1 以上です。"
)
glossary_expander(["log_ratio", "log_likelihood", "p_value", "odds_ratio", "pmw"])

gcols = group_columns(corpus)
if not gcols:
    st.info("グループ列がありません。CSV / Excel で読み込み、年・ジャンルなどの列を「グループ分けに使う列」に指定してください。")
    st.stop()

c1, c2, c3 = st.columns(3)
gcol = c1.selectbox("グループ列", gcols)
values = [str(v) for v in corpus.documents[gcol].astype(str).unique().tolist()]
value_a = c2.selectbox("グループ A", values, index=0)
value_b = c3.selectbox("グループ B（比較相手）", ["（A 以外のすべて）"] + [v for v in values if v != value_a], index=0)
vb = None if value_b == "（A 以外のすべて）" else value_b

sizes = group_sizes(corpus, gcol)
sa = sizes[sizes[gcol].astype(str) == value_a]
sb = sizes[sizes[gcol].astype(str) != value_a] if vb is None else sizes[sizes[gcol].astype(str) == vb]
n_docs_a, n_docs_b = int(sa["n_documents"].sum()), int(sb["n_documents"].sum())
st.caption(f"A「{value_a}」: {n_docs_a} 文書 / B「{value_b}」: {n_docs_b} 文書")
imbalance_flags = check_group_imbalance({value_a: n_docs_a, str(value_b): n_docs_b}, th)
show_flags(imbalance_flags)

tokens_a, tokens_b = split_by_group(corpus.tokens, corpus.documents, gcol, value_a, vb)
if len(tokens_a) == 0 or len(tokens_b) == 0:
    st.warning("どちらかのグループに語がありません。")
    st.stop()

table = state.cached(
    ("keyness", gcol, value_a, str(vb), s.unit, s.include_function_words),
    lambda: flag_keyness_table(keyness_table(tokens_a, tokens_b, s.unit, s.include_function_words), th),
)

f1, f2, f3 = st.columns(3)
min_g2 = f1.number_input("「差があるか」の足切り（G² がこれ以上）", min_value=0.0, value=float(kcfg.get("min_g2", 6.63)), step=0.5,
                         help="6.63 は p<0.01、10.83 は p<0.001 に相当します。これは足切りであって、重要さの順位ではありません。")
min_total = f2.number_input("両群合計の出現回数がこれ以上", min_value=1, value=int(kcfg.get("min_total_freq", 5)))
direction = f3.radio("表示", ["A に多い語", "B に多い語", "両方"], horizontal=True)

view = table[(table["g2"] >= min_g2) & ((table["freq_a"] + table["freq_b"]) >= min_total)]
if direction == "A に多い語":
    view = view[view["log_ratio"] > 0]
elif direction == "B に多い語":
    view = view[view["log_ratio"] < 0].sort_values("log_ratio")

shown = view.copy()
shown["注意"] = shown["flags"].map(lambda f: ("△ 差が小さい " if "EFFECT_SIZE_TOO_SMALL" in f else "") + ("（0 補正）" if "ZERO_CORRECTED" in f else ""))
shown["odds"] = [("片方が0回のため算出しません" if z else f"{o:.2f}") for o, z in zip(shown["odds_ratio"], shown["zero_corrected"])]
shown = shown[["label", "pos", "freq_a", "freq_b", "pmw_a", "pmw_b", "log_ratio", "g2", "p", "odds", "注意"]]

n_small = int(view["flags"].map(lambda f: "EFFECT_SIZE_TOO_SMALL" in f).sum())
st.markdown(f"**{len(view):,} 語**（足切り前 {len(table):,} 語）。差の大きさ（log ratio）の順に並んでいます。")
if n_small:
    st.info(f"このうち {n_small} 語は差の大きさ（log ratio）の絶対値が {th['log_ratio_min']} 未満です。p値が小さくても、実質的な発見として扱わないでください（「注意」列）。")

event = st.dataframe(
    shown,
    width="stretch",
    hide_index=True,
    height=480,
    on_select="rerun",
    selection_mode="single-row",
    column_config={
        "label": st.column_config.Column("語"),
        "pos": st.column_config.Column("品詞"),
        "freq_a": st.column_config.NumberColumn(f"回数 A", format="%d", help=glossary.tooltip("frequency")),
        "freq_b": st.column_config.NumberColumn(f"回数 B", format="%d", help=glossary.tooltip("frequency")),
        "pmw_a": st.column_config.NumberColumn("pmw A", format="%.1f", help=glossary.tooltip("pmw")),
        "pmw_b": st.column_config.NumberColumn("pmw B", format="%.1f", help=glossary.tooltip("pmw")),
        "log_ratio": st.column_config.NumberColumn("差の大きさ（log ratio）", format="%+.2f", help=glossary.tooltip("log_ratio")),
        "g2": st.column_config.NumberColumn("偶然でない度合い（G²）", format="%.1f", help=glossary.tooltip("log_likelihood")),
        "p": st.column_config.NumberColumn("p値", format="%.4f", help=glossary.tooltip("p_value")),
        "odds": st.column_config.Column("オッズ比", help=glossary.tooltip("odds_ratio")),
        "注意": st.column_config.Column("注意", help="△ 差が小さい: log ratio の絶対値が目安未満。（0 補正）: 片方の群で 0 回のため log ratio は 0.5 を足して計算。オッズ比は算出しない。"),
    },
)
sel_rows = event.selection.rows if event and event.selection else []
if sel_rows:
    r = view.iloc[sel_rows[0]]
    grp = value_a if r["log_ratio"] > 0 else value_b
    gval = value_a if r["log_ratio"] > 0 else vb
    row_flags = check_keyness_row(float(r["log_ratio"]), th, str(r["label"]), bool(r["zero_corrected"])) + imbalance_flags
    inp = ExplainInput(
        screen="keyness",
        metrics={"freq_a": int(r["freq_a"]), "freq_b": int(r["freq_b"]), "n_a": len(tokens_a), "n_b": len(tokens_b),
                 "pmw_a": float(r["pmw_a"]), "pmw_b": float(r["pmw_b"]), "log_ratio": float(r["log_ratio"]),
                 "g2": float(r["g2"]), "p": float(r["p"]), "odds_ratio": float(r["odds_ratio"])},
        flags=row_flags, words={"WORD": str(r["label"]), "GROUP_A": str(value_a), "GROUP_B": str(value_b)},
    )
    explanation_panel(inp, th, title=f"『{r['label']}』の読み方")
    if st.button(f"『{r['label']}』の用例を KWIC で見る（{grp} の文書に絞る）→", type="primary"):
        st.session_state["kwic_prefill"] = {
            "query": str(r["word"]), "unit": s.unit, "group_col": gcol, "group_value": gval, "exclude_value": value_a if gval is None else None,
            "reason": f"特徴語抽出から: 『{r['label']}』が「{grp}」グループでどう使われているかの用例",
        }
        st.switch_page("views/p5_kwic.py")
else:
    st.caption("表の行を選ぶと、その語の読み方（解説）と、該当グループの文書に絞って用例を KWIC 画面で確認するボタンが出ます。")

export = view.drop(columns=["flags"]).rename(columns={"word": "集計キー", "label": "語", "pos": "品詞", "freq_a": f"回数_{value_a}", "freq_b": f"回数_{value_b}",
                                                     "pmw_a": f"pmw_{value_a}", "pmw_b": f"pmw_{value_b}", "g2": "G2", "p": "p値",
                                                     "log_ratio": "log_ratio", "odds_ratio": "オッズ比", "zero_corrected": "0補正", "direction": "多い側"})
download_csv(export, f"keyness_{gcol}_{value_a}_vs_{value_b}.csv", key="dl_keyness")
st.caption(f"設定: グループ列 = {gcol}、A = {value_a}、B = {value_b}、G² ≥ {min_g2}、合計出現 ≥ {min_total}、機能語 {'含む' if s.include_function_words else '除く'}、単位 = {'見出し語' if s.unit == 'lemma' else '表層形'}。論文にはこれらを明記してください。")
