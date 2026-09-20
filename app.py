"""コーパス分析ツール — Streamlit エントリポイント。ページの振り分けだけを行う。"""
from __future__ import annotations

import streamlit as st

from interpretations import glossary
from ui import demo

st.set_page_config(page_title="コーパス分析ツール", page_icon="📚", layout="wide")

# 用語辞書のテンプレート変数が config.yaml で全て解決できることを起動時に確認する
# （未定義の変数があれば、ここで GlossaryTemplateError を出して止める）
glossary.load_glossary()

pages = [
    st.Page("views/p0_guide.py", title="使い方・できること", icon="📖", default=True),
    st.Page("views/p1_load.py", title="1. データを読み込む", icon="📂"),
    st.Page("views/p2_preprocess.py", title="2. 前処理の設定", icon="⚙️"),
    st.Page("views/p3_basic_stats.py", title="3. 基本統計", icon="📊"),
    st.Page("views/p4_frequency.py", title="4. 頻度分析", icon="🔢"),
    st.Page("views/p5_kwic.py", title="5. 用例検索（KWIC）", icon="🔍"),
    st.Page("views/p6_collocation.py", title="6. コロケーション", icon="🔗"),
    st.Page("views/p7_keyness.py", title="7. 特徴語（2群比較）", icon="⚖️"),
]

nav = st.navigation(pages)

demo.banner()

with st.sidebar:
    st.markdown("---")
    if demo.is_demo():
        st.caption("デモ版: アップロードしたファイルはサーバーを経由します。同梱サンプルでの体験用です。")
    else:
        st.caption(
            "このツールは読み込んだテキストを外部に送信しません。"
            "すべての処理はこのパソコンの中で行われます。"
        )
demo.sidebar_links()

nav.run()
