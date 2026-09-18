"""3. 基本統計"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from stats.basic import basic_stats, per_document_stats, pos_composition
from ui import state
from ui.components import caution_box, download_csv, glossary_expander, metric_help, plotly_config, png_hint

st.title("3. 基本統計")
corpus = state.require_corpus()
s = state.sidebar_display_options()

stats = state.cached(
    ("basic", s.unit, s.include_function_words, s.sttr_window),
    lambda: basic_stats(corpus.tokens, s.unit, s.include_function_words, s.sttr_window),
)

st.markdown("### データ全体")
c1, c2, c3, c4 = st.columns(4)
metric_help(c1, "延べ語数（token）", stats["n_tokens"], "token_type")
metric_help(c2, "異なり語数（type）", stats["n_types"], "token_type")
metric_help(c3, "語彙の豊かさ（TTR）", stats["ttr"], "ttr", fmt=".3f")
metric_help(c4, f"比較用（標準化TTR, {stats['sttr_window']}語単位）", stats["sttr"], "ttr_standardized", fmt=".3f")
if not s.include_function_words:
    st.caption(f"機能語を除いた数です。機能語を含めると延べ {stats['n_tokens_all']:,} 語です。")
if stats["sttr"] is None:
    st.info(f"全体が {stats['sttr_window']} 語に満たないため、標準化TTR は計算できません。")

caution_box("ttr")
glossary_expander(["token_type", "ttr", "ttr_standardized", "lemma", "function_words", "short_long_unit"])

# --- 文書ごと ------------------------------------------------------------------
st.markdown("### 文書ごと")
per_doc = state.cached(
    ("per_doc", s.unit, s.include_function_words, s.sttr_window),
    lambda: per_document_stats(corpus.tokens, s.unit, s.include_function_words, s.sttr_window),
)
per_doc = per_doc.merge(corpus.documents[["doc_id", "name"]], on="doc_id", how="left")
per_doc = per_doc[["name", "n_tokens", "n_types", "ttr", "sttr"]]
st.dataframe(
    per_doc,
    width="stretch",
    hide_index=True,
    column_config={
        "name": st.column_config.Column("文書"),
        "n_tokens": st.column_config.NumberColumn("延べ語数", format="%d"),
        "n_types": st.column_config.NumberColumn("異なり語数", format="%d"),
        "ttr": st.column_config.NumberColumn("TTR（長さの違う文書の比較には使わない）", format="%.3f"),
        "sttr": st.column_config.NumberColumn(f"標準化TTR（{s.sttr_window}語単位）", format="%.3f"),
    },
)
if per_doc["sttr"].isna().any():
    st.caption(f"「—」の文書は {s.sttr_window} 語に満たないため、標準化TTR を計算していません。")
download_csv(per_doc, "basic_stats_per_document.csv", key="dl_perdoc")

# --- 品詞構成比 ----------------------------------------------------------------
st.markdown("### 品詞別の構成比")
st.caption("構成比は、機能語を含めた全ての語で計算しています（文章が何でできているかを見るため）。")
pos_df = state.cached(("pos", ), lambda: pos_composition(corpus.tokens, include_function_words=True))
fig = px.bar(pos_df, x="pos", y="ratio", text=pos_df["ratio"].map(lambda r: f"{r:.1%}"))
fig.update_layout(xaxis_title="品詞", yaxis_title="割合", yaxis_tickformat=".0%", height=400)
st.plotly_chart(fig, width="stretch", config=plotly_config("pos_composition"))
png_hint()
download_csv(pos_df.rename(columns={"pos": "品詞", "count": "出現回数", "ratio": "割合"}), "pos_composition.csv", key="dl_pos")
