"""コーパス分析ツール — Streamlit エントリポイント。ページの振り分けだけを行う。"""
from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="コーパス分析ツール", page_icon="📚", layout="wide")

pages = [
    st.Page("views/p1_load.py", title="1. データを読み込む", icon="📂", default=True),
    st.Page("views/p2_preprocess.py", title="2. 前処理の設定", icon="⚙️"),
    st.Page("views/p3_basic_stats.py", title="3. 基本統計", icon="📊"),
    st.Page("views/p4_frequency.py", title="4. 頻度分析", icon="🔢"),
    st.Page("views/p5_kwic.py", title="5. 用例検索（KWIC）", icon="🔍"),
]

nav = st.navigation(pages)

with st.sidebar:
    st.markdown("---")
    st.caption(
        "このツールは読み込んだテキストを外部に送信しません。"
        "すべての処理はこのパソコンの中で行われます。"
    )

nav.run()
