"""6. コロケーション分析（共起頻度・MI・T・logDice・G²、3つのウィンドウ方式、共起ネットワーク）"""
from __future__ import annotations

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from analyzers.registry import get_analyzer
from app_config import thresholds
from interpretations import glossary
from interpretations.flags import make_flag
from interpretations.rules import flag_collocation_table
from stats.collocation import DEFAULT_METHOD, METHOD_REASON, METHODS, collocation_table
from stats.network import build_network, network_html
from ui import state
from ui.components import download_csv, glossary_expander, show_flags

st.title("6. コロケーション分析")
corpus = state.require_corpus()
s = state.sidebar_display_options()
cfg = state.config()
th = thresholds(cfg)
ccfg = cfg.get("collocation", {})
analyzer = get_analyzer(corpus.language, cfg)

glossary_expander(["cooccurrence_frequency", "log_dice", "mi_score", "t_score", "log_likelihood", "network_centrality"])

# --- 検索条件 ------------------------------------------------------------------
with st.form("colloc_form"):
    c1, c2 = st.columns([3, 2])
    node = c1.text_input("中心語", value=st.session_state.get("colloc_node", ""), placeholder="例: 先生")
    unit_label = c2.radio("何で探すか", ["見出し語", "表層形"], index=0 if s.unit == "lemma" else 1, horizontal=True)

    methods = dict(METHODS)
    if not analyzer.supports_dependency():
        methods["dependency"] = METHODS["dependency"] + "（この言語では未対応: 日本語は GiNZA の導入が必要）"
    default_method = DEFAULT_METHOD.get(corpus.language, "fixed")
    method_keys = list(methods.keys())
    method = st.selectbox(
        "共起の範囲（ウィンドウ方式）",
        method_keys,
        index=method_keys.index(default_method),
        format_func=lambda k: methods[k] + ("　← 既定" if k == default_method else ""),
    )
    st.caption(METHOD_REASON.get(default_method, ""))
    c3, c4 = st.columns(2)
    window = c3.slider("前後の語数（固定ウィンドウのとき）", 1, 15, int(ccfg.get("default_window", 5)))
    min_cooccur = c4.number_input("表に載せる最低共起回数", min_value=1, value=int(ccfg.get("min_cooccur", 2)))
    submitted = st.form_submit_button("分析する", type="primary")

if submitted:
    st.session_state["colloc_node"] = node
node = st.session_state.get("colloc_node", "")
if not node:
    st.info("中心語を入力して「分析する」を押してください。")
    st.stop()
if method == "dependency" and not analyzer.supports_dependency():
    st.warning("この言語では係り受け方式は使えません。同一文内か固定ウィンドウを選んでください。")
    st.stop()

unit = "lemma" if unit_label == "見出し語" else "surface"
table = state.cached(
    ("colloc", node, unit, method, window, min_cooccur),
    lambda: flag_collocation_table(collocation_table(corpus.tokens, node, unit, method, window, min_cooccur), th, s.include_function_words),
)
if table.empty:
    st.warning(f"「{node}」の共起語が見つかりませんでした。見出し語で探す場合は辞書形で入力してください。")
    st.stop()

view = table if s.include_function_words else table[~table["is_function"]]
window_label = {"fixed": f"前後{window}語", "sentence": "同一文内", "dependency": "係り受け"}[method]
st.markdown(
    f"中心語「{node}」: {int(table['freq_node'].iloc[0]):,} 回出現。共起語 **{len(view):,} 語**（{window_label}）。"
    " 表は結びつきの強さ・総合（logDice）の高い順です。列見出しを押すと他の指標でも並べ替えられます。"
)


def _flag_label(flags: list[str]) -> str:
    marks = []
    if "MI_HIGH_LOW_FREQ" in flags:
        marks.append("⚠ 低頻度・要用例")
    if "T_ONLY_FUNCTION_WORD" in flags:
        marks.append("△ 高頻度語")
    if "FUNCTION_WORD_NOISE" in flags:
        marks.append("機能語")
    return " ".join(marks)


shown = view.copy()
shown["注意"] = shown["flags"].map(_flag_label)
cols = ["label", "pos"] + (["relation"] if method == "dependency" else []) + ["cooccur", "freq_collocate", "log_dice", "mi", "t", "g2", "注意"]
shown_view = shown[cols].head(int(ccfg.get("max_rows", 300)))

event = st.dataframe(
    shown_view,
    width="stretch",
    hide_index=True,
    height=480,
    on_select="rerun",
    selection_mode="single-row",
    column_config={
        "label": st.column_config.Column("共起語"),
        "pos": st.column_config.Column("品詞"),
        "relation": st.column_config.Column("関係", help="係り受けラベル。→ は中心語がその語に係ることを示します。"),
        "cooccur": st.column_config.NumberColumn("一緒に出た回数", format="%d", help=glossary.tooltip("cooccurrence_frequency")),
        "freq_collocate": st.column_config.NumberColumn("共起語の総出現回数", format="%d"),
        "log_dice": st.column_config.NumberColumn("結びつき・総合（logDice）", format="%.2f", help=glossary.tooltip("log_dice")),
        "mi": st.column_config.NumberColumn("珍しさ重視（MI）", format="%.2f", help=glossary.tooltip("mi_score")),
        "t": st.column_config.NumberColumn("安定性（Tスコア）", format="%.2f", help=glossary.tooltip("t_score")),
        "g2": st.column_config.NumberColumn("偶然でない度合い（G²）", format="%.1f", help=glossary.tooltip("log_likelihood")),
        "注意": st.column_config.Column("注意", help="⚠ 低頻度・要用例: MIが高いが回数が少ない。△ 高頻度語: どこにでも出る語による見かけの共起。"),
    },
)


def _goto_kwic(collocate_key: str) -> None:
    st.session_state["kwic_prefill"] = {
        "query": node, "unit": unit, "collocate": collocate_key,
        "scope": "sentence" if method != "fixed" else "fixed", "window": window,
        "reason": f"コロケーション分析から: 『{node}』と『{collocate_key}』が{window_label}で共起している用例",
    }
    st.switch_page("views/p5_kwic.py")


sel_rows = event.selection.rows if event and event.selection else []
if sel_rows:
    r = view.iloc[sel_rows[0]]
    st.markdown(f"選択中: **{r['label']}**（一緒に出た回数 {int(r['cooccur'])} 回）")
    if st.button(f"『{node}』と『{r['label']}』の用例を KWIC で見る →", type="primary", key="kwic_selected"):
        _goto_kwic(str(r["collocate"]))
else:
    st.caption("表の行を選ぶと、その組み合わせの用例を KWIC 画面で確認できます。")

export = shown.rename(columns={"collocate": "集計キー", "label": "共起語", "pos": "品詞", "relation": "関係", "cooccur": "共起頻度",
                               "freq_node": "中心語頻度", "freq_collocate": "共起語頻度", "expected": "期待値", "mi": "MI",
                               "t": "Tスコア", "log_dice": "logDice", "g2": "G2", "p": "p値"}).drop(columns=["flags", "is_function"])
download_csv(export, f"collocation_{node}_{method}.csv", key="dl_colloc")

# --- 用例確認が必要な組み合わせ（フラグ → KWIC の導線） ------------------------------
need_check = view[view["flags"].map(lambda f: "MI_HIGH_LOW_FREQ" in f)]
st.markdown("### 用例の確認が必要な組み合わせ")
if len(need_check) == 0:
    st.success("結びつきが強く見えるのに回数が少ない組み合わせはありません。")
else:
    st.markdown(
        f"結びつきの強さ・珍しさ重視（MIスコア）が高いのに、一緒に出た回数が {th['mi_min_cooccur']} 回未満の組み合わせが **{len(need_check)} 組** あります。"
        " 用例を確認せずに論文に書くのは危険です。各行のボタンから用例を確認してください。"
    )
    for i, r in enumerate(need_check.head(10).itertuples()):
        cA, cB = st.columns([5, 2])
        with cA:
            show_flags([make_flag("MI_HIGH_LOW_FREQ", mi=float(r.mi), cooccur=int(r.cooccur), threshold=int(th["mi_min_cooccur"]))])
        with cB:
            st.write("")
            if st.button(f"『{r.label}』の用例を確認 →", key=f"kwic_flag_{i}"):
                _goto_kwic(str(r.collocate))
    if len(need_check) > 10:
        st.caption(f"上位10組のみ表示。残り {len(need_check) - 10} 組は表の「注意」列で確認できます。")

noise = view[view["flags"].map(lambda f: "T_ONLY_FUNCTION_WORD" in f)]
if len(noise):
    with st.expander(f"どこにでも出る語による見かけの共起（{len(noise)} 語）"):
        st.markdown("結びつきの安定性（Tスコア）は高いのに、珍しさ重視（MIスコア）は低い組み合わせです。単にその語がどこにでも出るというだけで、発見ではありません。")
        st.dataframe(noise[["label", "pos", "cooccur", "t", "mi"]].rename(columns={"label": "共起語", "pos": "品詞", "cooccur": "共起頻度", "t": "Tスコア", "mi": "MI"}), width="stretch", hide_index=True)

# --- 共起ネットワーク --------------------------------------------------------------
st.markdown("### 共起ネットワーク")
ncfg = cfg.get("network", {})
st.caption("頻度上位の語を節点にし、同じ文（または前後 n 語）に一緒に出た語同士を線で結びます。設定で見た目が大きく変わるので、論文には必ず設定値を明記してください。")
n1, n2, n3 = st.columns(3)
top_n = n1.slider("節点にする語数（頻度上位）", 10, 150, int(ncfg.get("top_n", 60)))
min_ld = n2.slider("線を引く logDice の下限", 0.0, 14.0, float(ncfg.get("min_log_dice", 7.0)), 0.5)
net_method = n3.selectbox("共起の単位", ["sentence", "fixed"], index=0 if method != "fixed" else 1, format_func=lambda k: METHODS[k])
if st.button("ネットワークを描く"):
    g, edges, nodes = build_network(corpus.tokens, unit, s.include_function_words, top_n, net_method, window, min_ld, int(ncfg.get("min_cooccur", 2)))
    if g.number_of_edges() == 0:
        st.warning("線を引ける組み合わせがありません。logDice の下限を下げるか、語数を増やしてください。")
    else:
        st.markdown(f"節点 {g.number_of_nodes()} 語、線 {g.number_of_edges()} 本（設定: 上位 {top_n} 語、logDice ≥ {min_ld}、{METHODS[net_method]}）")
        components.html(network_html(g), height=620, scrolling=False)
        st.caption("図の保存は、図の上で右クリック → 画像として保存、またはスクリーンショットをお使いください。")
        st.markdown("#### 中心性（つながりの多さ）")
        st.dataframe(
            nodes.rename(columns={"label": "語", "freq": "出現回数", "degree": "つながる語の数", "degree_centrality": "次数中心性", "betweenness": "媒介中心性"}).drop(columns=["word"]),
            width="stretch", hide_index=True,
            column_config={"次数中心性": st.column_config.NumberColumn(format="%.3f", help=glossary.tooltip("network_centrality")),
                           "媒介中心性": st.column_config.NumberColumn(format="%.3f", help=glossary.tooltip("network_centrality"))},
        )
        st.info(glossary.entry("network_centrality")["caution"].strip().splitlines()[0])
        cx, cy = st.columns(2)
        with cx:
            download_csv(edges.rename(columns={"a": "語1", "b": "語2", "cooccur": "共起回数", "log_dice": "logDice"}), "network_edges.csv", "線の一覧を CSV で保存", key="dl_edges")
        with cy:
            download_csv(nodes, "network_nodes.csv", "中心性を CSV で保存", key="dl_nodes")
