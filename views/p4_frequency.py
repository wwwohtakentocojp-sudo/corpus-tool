"""4. 頻度分析（頻度・pmw・分散度DP・Zipf）"""
from __future__ import annotations

import plotly.express as px
import streamlit as st

from app_config import thresholds
from interpretations import glossary
from interpretations.flags import make_flag
from interpretations.rules import check_dp_reliability, flag_frequency_table
from stats.frequency import frequency_table, word_distribution
from ui import state
from ui.components import download_csv, glossary_expander, plotly_config, png_hint, show_flags

st.title("4. 頻度分析")
corpus = state.require_corpus()
s = state.sidebar_display_options()
th = thresholds(state.config())

# DP の分割単位は文書（Phase 1 でグループ列を選べるようにする）
n_parts = corpus.n_documents
dp_flags = check_dp_reliability(n_parts, th)

freq_df = state.cached(
    ("freq", s.unit, s.include_function_words),
    lambda: flag_frequency_table(frequency_table(corpus.tokens, s.unit, s.include_function_words), th, n_parts=n_parts),
)

glossary_expander(["frequency", "pmw", "dispersion_dp", "lemma_key"])

# --- 絞り込み ------------------------------------------------------------------
c1, c2, c3, c4 = st.columns([2, 2, 3, 2])
min_freq = c1.number_input("出現回数がこれ以上", min_value=1, value=1, step=1)
pos_options = ["（すべて）"] + sorted(freq_df["pos"].dropna().unique().tolist())
pos_sel = c2.selectbox("品詞", pos_options)
search = c3.text_input("語で絞り込む（部分一致）", "")
show_key = c4.toggle(
    "集計キーを表示",
    value=False,
    help=glossary.tooltip("lemma_key"),
)

view = freq_df[freq_df["freq"] >= min_freq]
if pos_sel != "（すべて）":
    view = view[view["pos"] == pos_sel]
if search:
    view = view[view["label"].str.contains(search, regex=False) | view["word"].str.contains(search, regex=False)]

# --- 表 ------------------------------------------------------------------------
def _flag_label(flags: list[str]) -> str:
    marks = []
    if "DISPERSION_SKEWED" in flags:
        marks.append("⚠ 偏り")
    if "LOW_FREQUENCY" in flags:
        marks.append("△ 低頻度")
    return " ".join(marks)


shown = view.copy()
shown["注意"] = shown["flags"].map(_flag_label)
cols = ["rank", "label", "word", "pos", "freq", "pmw", "dp", "n_parts", "注意"] if show_key else ["rank", "label", "pos", "freq", "pmw", "dp", "n_parts", "注意"]
shown = shown[cols]

dup_labels = int(view["label"].duplicated(keep=False).sum())
st.markdown(f"**{len(view):,} 語**（全 {len(freq_df):,} 語のうち）")
if dup_labels and not show_key:
    st.caption(
        f"表示名が同じ行が {dup_labels} 行あります。意味の違う同形の語を別々に数えているためです。"
        "「集計キーを表示」を ON にすると区別が見えます。"
    )
st.dataframe(
    shown,
    width="stretch",
    hide_index=True,
    height=520,
    column_config={
        "rank": st.column_config.NumberColumn("順位", format="%d"),
        "label": st.column_config.Column("語", help=glossary.tooltip("lemma_key")),
        "word": st.column_config.Column("集計キー", help=glossary.tooltip("lemma_key")),
        "pos": st.column_config.Column("品詞"),
        "freq": st.column_config.NumberColumn("出現回数", format="%d", help=glossary.tooltip("frequency")),
        "pmw": st.column_config.NumberColumn("100万語あたり（pmw）", format="%.1f", help=glossary.tooltip("pmw")),
        "dp": st.column_config.NumberColumn("散らばり（DP）", format="%.3f", help=glossary.tooltip("dispersion_dp")),
        "n_parts": st.column_config.NumberColumn("出現文書数", format="%d"),
        "注意": st.column_config.Column("注意", help="⚠ 偏り: 一部の文書に集中。△ 低頻度: 主張の根拠にしない。"),
    },
)
# CSV には常に集計キーを含める（再現性のため）
export = view.copy()
export["注意"] = export["flags"].map(_flag_label)
export = export[["rank", "label", "word", "pos", "freq", "pmw", "dp", "n_parts", "注意"]].rename(
    columns={"rank": "順位", "label": "語", "word": "集計キー", "pos": "品詞", "freq": "出現回数", "pmw": "pmw", "dp": "分散度DP", "n_parts": "出現文書数"}
)
download_csv(export, "frequency_table.csv", key="dl_freq")

# --- 偏りの警告と、該当文書の確認 ------------------------------------------------
st.markdown("### 一部の文書に偏っている語")
if dp_flags:
    # 分割数が少なすぎる: 個別の警告は出さず、注意を1つだけ
    show_flags(dp_flags)
else:
    skewed = freq_df[freq_df["flags"].map(lambda f: "DISPERSION_SKEWED" in f)]
    if len(skewed) == 0:
        st.success(f"出現回数 {th['dp_min_freq']} 回以上の語で、散らばりが目安（DP {th['dp_skew']}）を超える語はありません。")
    else:
        st.markdown(
            f"出現回数 {th['dp_min_freq']} 回以上で、散らばり具合（DP）が {th['dp_skew']} を超える語が **{len(skewed)} 語** あります。"
            " これらを「このデータでよく使われる語」と呼んではいけません。どの文書に集中しているかを確認してください。"
        )
        top = skewed.head(10)
        show_flags(
            make_flag("DISPERSION_SKEWED", word=r.label, freq=int(r.freq), dp=float(r.dp), threshold=th["dp_skew"])
            for r in top.itertuples()
        )
        if len(skewed) > 10:
            st.caption(f"上位10語のみ表示。残り {len(skewed) - 10} 語は表の「注意」列で確認できます。")

# 語ごとの文書内訳は、警告の有無にかかわらず確認できるようにする
pick = st.selectbox(
    "どの文書に出ているか確認する語（集計キー）",
    options=[""] + freq_df["word"].tolist(),
    format_func=lambda w: "（選んでください）" if w == "" else w,
)
if pick:
    dist = word_distribution(corpus.tokens, pick, s.unit)
    dist = dist.merge(corpus.documents[["doc_id", "name"]], on="doc_id", how="left")
    dist = dist[["name", "freq", "part_tokens", "pmw_in_part", "share"]]
    st.dataframe(
        dist,
        width="stretch",
        hide_index=True,
        column_config={
            "name": st.column_config.Column("文書"),
            "freq": st.column_config.NumberColumn("出現回数", format="%d"),
            "part_tokens": st.column_config.NumberColumn("文書の延べ語数", format="%d"),
            "pmw_in_part": st.column_config.NumberColumn("文書内 pmw", format="%.1f"),
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
