"""5. 用例検索（KWIC）— 研究者が最も長く使う画面。速度と操作性を最優先。"""
from __future__ import annotations

import streamlit as st

from interpretations import glossary
from stats.kwic import kwic, sort_kwic
from ui import state
from ui.components import download_csv

st.title("5. 用例検索（KWIC）")
corpus = state.require_corpus()
s = state.sidebar_display_options()
cfg = state.config()
max_rows = int(cfg.get("kwic", {}).get("max_rows_display", 5000))

# --- 検索条件 ------------------------------------------------------------------
with st.form("kwic_form"):
    c1, c2, c3 = st.columns([3, 2, 2])
    query = c1.text_input("検索する語", value=st.session_state.get("kwic_query", ""), placeholder="例: 先生")
    unit_label = c2.radio(
        "何で探すか",
        ["見出し語（活用形をまとめて探す）", "表層形（書かれた形そのもの）"],
        index=0 if s.unit == "lemma" else 1,
        horizontal=False,
    )
    window = c3.slider("前後に表示する語数", 1, 15, int(s.kwic_window))
    c4, c5 = st.columns([2, 3])
    regex = c4.checkbox("パターンで探す（正規表現）", value=False, help="例: 行.* は「行く」「行う」などにマッチ")
    include_fw_ctx = c5.checkbox("前後の文脈に機能語も表示する", value=True, help="OFF にすると前後の語から助詞・記号を除きます。検索対象は変わりません。")
    submitted = st.form_submit_button("検索", type="primary")

if submitted:
    st.session_state["kwic_query"] = query
query = st.session_state.get("kwic_query", "")
if not query:
    st.info("語を入力して「検索」を押してください。")
    st.stop()

unit = "lemma" if unit_label.startswith("見出し語") else "surface"
tokens = corpus.tokens if include_fw_ctx else corpus.tokens[~corpus.tokens["is_function"] | (corpus.tokens[unit] == query)]

result = state.cached(
    ("kwic", query, unit, window, regex, include_fw_ctx),
    lambda: kwic(tokens, query, unit=unit, window=window, regex=regex),
)

n = len(result)
if n == 0:
    st.warning(
        f"「{query}」は見つかりませんでした。"
        " 見出し語で探している場合は、辞書形（「行く」「先生」など）で入力してください。"
        " 表層形に切り替えると、書かれた形そのもの（「行った」など）で探せます。"
    )
    st.stop()

st.markdown(f"**{n:,} 件** 見つかりました。")

# 同形異義語が混ざっている場合は内訳を示す
keys = result["key"].value_counts()
if len(keys) > 1:
    breakdown = "、".join(f"「{k}」{v:,} 件" for k, v in keys.items())
    st.info(
        f"「{query}」には、意味の違う語が {len(keys)} 種類含まれています: {breakdown}。"
        " 1つに絞りたい場合は、集計キー（例: 「{0}」）をそのまま検索語に入力してください。".format(keys.index[0]),
        icon="ℹ️",
    )
    with st.expander("集計キーとは"):
        st.markdown(glossary.full_text("lemma_key"))

# --- 並べ替え ------------------------------------------------------------------
sort_options = ["出現順"] + [f"L{i}" for i in range(1, window + 1)] + [f"R{i}" for i in range(1, window + 1)]
c1, c2 = st.columns([2, 5])
sort_by = c1.selectbox("並べ替え", sort_options, help="L1 = 直前の語、R1 = 直後の語。同じ語で並べると、前後のパターンが見えやすくなります。")
view = result if sort_by == "出現順" else sort_kwic(result, sort_by)

# --- 表示 ----------------------------------------------------------------------
view = view.merge(corpus.documents[["doc_id", "name"]], on="doc_id", how="left")
display_cols = ["name", "left", "KWIC", "right", "position"] + (["key"] if len(keys) > 1 else [])
shown = view[display_cols]

page_size = 500
if n > page_size:
    n_pages = (min(n, max_rows) + page_size - 1) // page_size
    page = c2.number_input(f"ページ（1ページ {page_size} 件、全 {n_pages} ページ）", min_value=1, max_value=n_pages, value=1)
    shown = shown.iloc[(page - 1) * page_size : page * page_size]

st.dataframe(
    shown,
    width="stretch",
    hide_index=True,
    height=600,
    column_config={
        "name": st.column_config.Column("文書", width="small"),
        "left": st.column_config.Column("前の文脈", width="large"),
        "KWIC": st.column_config.Column("検索語", width="small"),
        "right": st.column_config.Column("後の文脈", width="large"),
        "position": st.column_config.NumberColumn("位置", format="%d", width="small"),
        "key": st.column_config.Column("集計キー", width="small", help=glossary.tooltip("lemma_key")),
    },
)

export = view.drop(columns=["doc_id"]).rename(columns={"name": "文書", "position": "位置", "sentence_id": "文番号", "key": "集計キー", "left": "前の文脈", "right": "後の文脈"})
download_csv(export, f"kwic_{query}.csv", label=f"全 {n:,} 件を CSV で保存", key="dl_kwic")
