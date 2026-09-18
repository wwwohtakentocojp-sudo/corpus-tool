"""5. 用例検索（KWIC）— 研究者が最も長く使う画面。速度と操作性を最優先。

他の画面からの導線: st.session_state["kwic_prefill"] に
  {query, unit, collocate?, scope?, window?, group_col?, group_value?, exclude_value?, reason}
が入っていれば、その条件で絞り込んだ状態で開く。
"""
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

prefill = st.session_state.pop("kwic_prefill", None)
if prefill:
    st.session_state["kwic_query"] = prefill.get("query", "")
    st.session_state["kwic_collocate"] = prefill.get("collocate", "") or ""
    st.session_state["kwic_scope"] = prefill.get("scope", "sentence")
    st.session_state["kwic_group"] = (prefill.get("group_col"), prefill.get("group_value"), prefill.get("exclude_value"))
    st.session_state["kwic_reason"] = prefill.get("reason", "")
    st.session_state["kwic_unit"] = prefill.get("unit", s.unit)
    if prefill.get("window"):
        st.session_state["kwic_window"] = int(prefill["window"])

reason = st.session_state.get("kwic_reason", "")
if reason:
    c_msg, c_btn = st.columns([5, 1])
    c_msg.info(reason)
    if c_btn.button("絞り込みを解除"):
        for k in ("kwic_collocate", "kwic_group", "kwic_reason"):
            st.session_state.pop(k, None)
        st.rerun()

# --- 検索条件 ------------------------------------------------------------------
unit_default = st.session_state.get("kwic_unit", s.unit)
with st.form("kwic_form"):
    c1, c2, c3 = st.columns([3, 2, 2])
    query = c1.text_input("検索する語", value=st.session_state.get("kwic_query", ""), placeholder="例: 先生")
    unit_label = c2.radio(
        "何で探すか",
        ["見出し語（活用形をまとめて探す）", "表層形（書かれた形そのもの）"],
        index=0 if unit_default == "lemma" else 1,
    )
    window = c3.slider("前後に表示する語数", 1, 15, int(st.session_state.get("kwic_window", s.kwic_window)))
    c4, c5, c6 = st.columns([2, 3, 3])
    regex = c4.checkbox("パターンで探す（正規表現）", value=False, help="例: 行.* は「行く」「行う」などにマッチ")
    include_fw_ctx = c5.checkbox("前後の文脈に機能語も表示する", value=True, help="OFF にすると前後の語から助詞・記号を除きます。検索対象は変わりません。")
    collocate = c6.text_input("共起語で絞り込む（任意）", value=st.session_state.get("kwic_collocate", ""), help="この語が近くにある用例だけを表示します。")
    scope_label = st.radio("「近く」の範囲", ["同一文内", "前後の語数の範囲"], index=0 if st.session_state.get("kwic_scope", "sentence") == "sentence" else 1, horizontal=True)
    submitted = st.form_submit_button("検索", type="primary")

if submitted:
    st.session_state["kwic_query"] = query
    st.session_state["kwic_collocate"] = collocate
    st.session_state["kwic_scope"] = "sentence" if scope_label == "同一文内" else "fixed"
    st.session_state["kwic_unit"] = "lemma" if unit_label.startswith("見出し語") else "surface"
    st.session_state["kwic_window"] = window
query = st.session_state.get("kwic_query", "")
collocate = st.session_state.get("kwic_collocate", "") or None
scope = st.session_state.get("kwic_scope", "sentence")
if not query:
    st.info("語を入力して「検索」を押してください。")
    st.stop()

unit = "lemma" if unit_label.startswith("見出し語") else "surface"

# --- 対象トークン（グループ絞り込み、文脈の機能語） --------------------------------------
tokens = corpus.tokens
group = st.session_state.get("kwic_group")
if group and group[0]:
    gcol, gval, excl = group
    docs = corpus.documents
    if gval is not None:
        ids = docs.loc[docs[gcol].astype(str) == str(gval), "doc_id"]
    else:
        ids = docs.loc[docs[gcol].astype(str) != str(excl), "doc_id"]
    tokens = tokens[tokens["doc_id"].isin(set(ids))]
if not include_fw_ctx:
    tokens = tokens[~tokens["is_function"] | (tokens[unit] == query)]

result = state.cached(
    ("kwic", query, unit, window, regex, include_fw_ctx, collocate, scope, str(group)),
    lambda: kwic(tokens, query, unit=unit, window=window, regex=regex, collocate=collocate, collocate_scope=scope),
)

n = len(result)
if n == 0:
    msg = f"「{query}」は見つかりませんでした。"
    if collocate:
        msg += f" 共起語「{collocate}」で絞り込んでいます。絞り込みを解除して確認してください。"
    else:
        msg += " 見出し語で探している場合は、辞書形（「行く」「先生」など）で入力してください。表層形に切り替えると、書かれた形そのもの（「行った」など）で探せます。"
    st.warning(msg)
    st.stop()

st.markdown(f"**{n:,} 件** 見つかりました。" + (f"（共起語「{collocate}」で絞り込み）" if collocate else ""))

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
