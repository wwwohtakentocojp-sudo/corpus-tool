"""4. 頻度分析（頻度・pmw・分散度DP・Zipf）"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from app_config import thresholds
from corpus.checks import group_columns
from interpretations import glossary
from interpretations.flags import make_flag
from interpretations.explainer import ExplainInput
from interpretations.rules import check_dispersion, check_dp_reliability, check_low_frequency, flag_frequency_table
from stats.frequency import expand_compounds, frequency_table, tokens_with_parts, word_distribution
from ui import state
from ui.components import download_csv, explanation_panel, glossary_expander, plotly_config, png_hint, show_flags

st.title("4. 頻度分析")
corpus = state.require_corpus()
s = state.sidebar_display_options()
th = thresholds(state.config())

glossary_expander(["frequency", "pmw", "dispersion_dp", "lemma_key"])

# --- 散らばりの単位（文書 or グループ列） ---------------------------------------------
gcols = group_columns(corpus)
part_options = {"doc_id": "文書ごと"} | {c: f"グループ列「{c}」ごと" for c in gcols}
part_col = st.selectbox(
    "散らばり（DP）を計算する単位",
    options=list(part_options.keys()),
    format_func=lambda k: part_options[k],
    help="どの単位で「まんべんなく出ているか」を見るか。グループ列を選ぶと、そのグループ間の偏りを見ます。",
)
tokens_dp = tokens_with_parts(corpus.tokens, corpus.documents, part_col)
n_parts = int(corpus.documents[part_col].nunique()) if part_col != "doc_id" else corpus.n_documents
dp_flags = check_dp_reliability(n_parts, th)

# --- 複合語（ドイツ語で分割 ON のとき） ----------------------------------------------
has_compounds = bool((corpus.tokens["compound_parts"].astype(str) != "").any()) if "compound_parts" in corpus.tokens.columns else False


def _freq(expand: bool) -> pd.DataFrame:
    src = expand_compounds(tokens_dp) if expand else tokens_dp
    return flag_frequency_table(frequency_table(src, s.unit, s.include_function_words, part_col=part_col), th, n_parts=n_parts)


def _flag_label(flags: list[str]) -> str:
    marks = []
    if "DISPERSION_SKEWED" in flags:
        marks.append("⚠ 偏り")
    if "LOW_FREQUENCY" in flags:
        marks.append("△ 低頻度")
    return " ".join(marks)


def render_table(freq_df: pd.DataFrame, key: str) -> str | None:
    """表を描き、選択された行の集計キーを返す（未選択なら None）。"""
    c1, c2, c3, c4 = st.columns([2, 2, 3, 2])
    min_freq = c1.number_input("出現回数がこれ以上", min_value=1, value=1, step=1, key=f"minf_{key}")
    pos_options = ["（すべて）"] + sorted(freq_df["pos"].dropna().unique().tolist())
    pos_sel = c2.selectbox("品詞", pos_options, key=f"pos_{key}")
    search = c3.text_input("語で絞り込む（部分一致）", "", key=f"search_{key}")
    show_key = c4.toggle("集計キーを表示", value=False, help=glossary.tooltip("lemma_key"), key=f"key_{key}")

    view = freq_df[freq_df["freq"] >= min_freq]
    if pos_sel != "（すべて）":
        view = view[view["pos"] == pos_sel]
    if search:
        view = view[view["label"].str.contains(search, regex=False) | view["word"].str.contains(search, regex=False)]

    shown = view.copy()
    shown["注意"] = shown["flags"].map(_flag_label)
    cols = ["rank", "label", "word", "pos", "freq", "pmw", "dp", "n_parts", "注意"] if show_key else ["rank", "label", "pos", "freq", "pmw", "dp", "n_parts", "注意"]
    shown = shown[cols]

    dup_labels = int(view["label"].duplicated(keep=False).sum())
    st.markdown(f"**{len(view):,} 語**（全 {len(freq_df):,} 語のうち）")
    if dup_labels and not show_key:
        st.caption(f"表示名が同じ行が {dup_labels} 行あります。意味の違う同形の語を別々に数えているためです。「集計キーを表示」を ON にすると区別が見えます。")
    event = st.dataframe(
        shown,
        width="stretch",
        hide_index=True,
        height=520,
        on_select="rerun",
        selection_mode="single-row",
        key=f"table_{key}",
        column_config={
            "rank": st.column_config.NumberColumn("順位", format="%d"),
            "label": st.column_config.Column("語", help=glossary.tooltip("lemma_key")),
            "word": st.column_config.Column("集計キー", help=glossary.tooltip("lemma_key")),
            "pos": st.column_config.Column("品詞"),
            "freq": st.column_config.NumberColumn("出現回数", format="%d", help=glossary.tooltip("frequency")),
            "pmw": st.column_config.NumberColumn("100万語あたり（pmw）", format="%.1f", help=glossary.tooltip("pmw")),
            "dp": st.column_config.NumberColumn("散らばり（DP）", format="%.3f", help=glossary.tooltip("dispersion_dp")),
            "n_parts": st.column_config.NumberColumn("出現" + ("文書数" if part_col == "doc_id" else "グループ数"), format="%d"),
            "注意": st.column_config.Column("注意", help="⚠ 偏り: 一部に集中。△ 低頻度: 主張の根拠にしない。"),
        },
    )
    export = view.copy()
    export["注意"] = export["flags"].map(_flag_label)
    export = export[["rank", "label", "word", "pos", "freq", "pmw", "dp", "n_parts", "注意"]].rename(
        columns={"rank": "順位", "label": "語", "word": "集計キー", "pos": "品詞", "freq": "出現回数", "pmw": "pmw", "dp": "分散度DP", "n_parts": "出現数（単位別）"}
    )
    download_csv(export, f"frequency_table_{key}.csv", key=f"dl_{key}")
    rows = event.selection.rows if event and event.selection else []
    return str(view.iloc[rows[0]]["word"]) if rows else None


freq_df = state.cached(("freq", s.unit, s.include_function_words, part_col), lambda: _freq(False))
selected_word: str | None = None

if has_compounds:
    tab_orig, tab_parts = st.tabs(["元の語（複合語は1語のまま）", "複合語を構成要素に分けた場合"])
    with tab_orig:
        selected_word = render_table(freq_df, "orig")
    with tab_parts:
        st.caption(
            "複合語を構成要素に置き換えて数え直した表です。どちらを採用するかは研究目的で決めてください。"
            " 分割は辞書を使わない推定なので、誤って分けられた語がないか確認してください（pmw の分母も語数が増える分だけ変わります）。"
        )
        freq_parts = state.cached(("freq_parts", s.unit, s.include_function_words, part_col), lambda: _freq(True))
        render_table(freq_parts, "parts")
        with st.expander("分割された語の一覧"):
            comp = corpus.tokens[corpus.tokens["compound_parts"].astype(str) != ""]
            tbl = comp.groupby(["surface", "compound_parts"]).size().rename("出現回数").reset_index().sort_values("出現回数", ascending=False)
            st.dataframe(tbl.rename(columns={"surface": "元の語", "compound_parts": "構成要素"}), width="stretch", hide_index=True)
else:
    selected_word = render_table(freq_df, "orig")

# --- 選択した語の読み方（解説） --------------------------------------------------
if selected_word:
    r = freq_df.set_index("word").loc[selected_word]
    row_flags = list(dp_flags) + check_low_frequency(str(r["label"]), int(r["freq"]), th)
    if not dp_flags:
        row_flags += check_dispersion(str(r["label"]), int(r["freq"]), float(r["dp"]), th)
    inp = ExplainInput(
        screen="frequency",
        metrics={"freq": int(r["freq"]), "pmw": float(r["pmw"]), "dp": float(r["dp"]), "n_parts": n_parts, "n_total": corpus.n_tokens},
        flags=row_flags, words={"WORD": str(r["label"])},
    )
    explanation_panel(inp, th, title=f"『{r['label']}』の読み方")
else:
    st.caption("表の行を選ぶと、その語の読み方（解説）が出ます。")

# --- 偏りの警告と、該当文書の確認 ------------------------------------------------
st.markdown("### 一部に偏っている語")
if dp_flags:
    show_flags(dp_flags)
else:
    skewed = freq_df[freq_df["flags"].map(lambda f: "DISPERSION_SKEWED" in f)]
    if len(skewed) == 0:
        st.success(f"出現回数 {th['dp_min_freq']} 回以上の語で、散らばりが目安（DP {th['dp_skew']}）を超える語はありません。")
    else:
        st.markdown(
            f"出現回数 {th['dp_min_freq']} 回以上で、散らばり具合（DP）が {th['dp_skew']} を超える語が **{len(skewed)} 語** あります。"
            " これらを「このデータでよく使われる語」と呼んではいけません。どこに集中しているかを確認してください。"
        )
        show_flags(
            make_flag("DISPERSION_SKEWED", word=r.label, freq=int(r.freq), dp=float(r.dp), threshold=th["dp_skew"])
            for r in skewed.head(10).itertuples()
        )
        if len(skewed) > 10:
            st.caption(f"上位10語のみ表示。残り {len(skewed) - 10} 語は表の「注意」列で確認できます。")

pick_options = [""] + freq_df["word"].tolist()
pick = st.selectbox(
    "どこに出ているか確認する語（集計キー）",
    options=pick_options,
    index=pick_options.index(selected_word) if selected_word in pick_options else 0,
    format_func=lambda w: "（選んでください）" if w == "" else w,
)
if pick:
    dist = word_distribution(tokens_dp, pick, s.unit, part_col=part_col)
    if part_col == "doc_id":
        dist = dist.merge(corpus.documents[["doc_id", "name"]], on="doc_id", how="left").rename(columns={"name": "単位"})
    else:
        dist = dist.rename(columns={part_col: "単位"})
    dist = dist[["単位", "freq", "part_tokens", "pmw_in_part", "share"]]
    st.dataframe(
        dist,
        width="stretch",
        hide_index=True,
        column_config={
            "単位": st.column_config.Column("文書" if part_col == "doc_id" else part_col),
            "freq": st.column_config.NumberColumn("出現回数", format="%d"),
            "part_tokens": st.column_config.NumberColumn("延べ語数", format="%d"),
            "pmw_in_part": st.column_config.NumberColumn("内部 pmw", format="%.1f"),
            "share": st.column_config.NumberColumn("全出現のうちの割合", format="%.1%"),
        },
    )

# --- Zipf ----------------------------------------------------------------------
st.markdown("### 順位と出現回数の関係（Zipf 分布）")
st.caption(
    "横軸が順位、縦軸が出現回数（どちらも対数目盛）。自然な文章ではおおむね右下がりの直線になります。"
    " 直線から大きく外れる場合、特定の語の極端な繰り返しや、読み込み時の注記の混入などを疑ってください。"
)
zipf = freq_df[["rank", "freq", "label"]]
fig = px.scatter(zipf, x="rank", y="freq", hover_name="label", log_x=True, log_y=True)
fig.update_layout(xaxis_title="順位（対数）", yaxis_title="出現回数（対数）", height=420)
fig.update_traces(marker=dict(size=4))
st.plotly_chart(fig, width="stretch", config=plotly_config("zipf"))
png_hint()
