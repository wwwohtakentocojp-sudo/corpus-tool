"""Streamlit の session_state 管理。画面間で共有する状態はここを通す。"""
from __future__ import annotations

from typing import Any

import streamlit as st

from app_config import load_config
from corpus.models import Corpus, Document
from corpus.settings import AnalysisSettings

KEY_CORPUS = "corpus"
KEY_DOCS = "documents"
KEY_SETTINGS = "settings"
KEY_VERSION = "corpus_version"   # 解析し直すたびに +1（結果キャッシュのキー）
KEY_CACHE = "_result_cache"
KEY_FILE_INFO = "file_info"


def config() -> dict[str, Any]:
    return load_config()


def get_settings() -> AnalysisSettings:
    if KEY_SETTINGS not in st.session_state:
        cfg = config()
        st.session_state[KEY_SETTINGS] = AnalysisSettings(
            language="ja",
            sttr_window=int(cfg.get("basic_stats", {}).get("sttr_window", 1000)),
            kwic_window=int(cfg.get("kwic", {}).get("default_window", 5)),
        )
    return st.session_state[KEY_SETTINGS]


def get_corpus() -> Corpus | None:
    return st.session_state.get(KEY_CORPUS)


def set_corpus(corpus: Corpus, docs: list[Document]) -> None:
    st.session_state[KEY_CORPUS] = corpus
    st.session_state[KEY_DOCS] = docs
    st.session_state[KEY_VERSION] = st.session_state.get(KEY_VERSION, 0) + 1
    st.session_state[KEY_CACHE] = {}


def get_documents() -> list[Document]:
    return st.session_state.get(KEY_DOCS, [])


def corpus_version() -> int:
    return int(st.session_state.get(KEY_VERSION, 0))


def cached(key: tuple, compute):
    """結果キャッシュ。corpus_version が変わると自動的に無効になる。"""
    cache = st.session_state.setdefault(KEY_CACHE, {})
    full_key = (corpus_version(),) + tuple(key)
    if full_key not in cache:
        cache[full_key] = compute()
    return cache[full_key]


def require_corpus() -> Corpus:
    corpus = get_corpus()
    if corpus is None or corpus.n_tokens == 0:
        st.info("まだデータが読み込まれていません。左のメニューから「1. データを読み込む」を開いて、テキストファイルを読み込んでください。")
        st.stop()
    return corpus


def sidebar_display_options() -> AnalysisSettings:
    """全分析画面に共通の表示オプション（ワンクリックで切替）。"""
    s = get_settings()
    with st.sidebar:
        st.markdown("### 集計の設定")
        s.include_function_words = st.toggle(
            "機能語（助詞・記号など）を含める",
            value=s.include_function_words,
            help="OFF: 内容語だけを数えます（既定）。ON: 助詞や助動詞も数えます。文体研究・文法研究では ON にしてください。",
        )
        unit_label = st.radio(
            "語の数え方",
            options=["見出し語（活用をまとめる）", "表層形（書かれた形のまま）"],
            index=0 if s.unit == "lemma" else 1,
            help="「行った」「行きます」を「行く」1語として数えるなら見出し語。活用形の違いを研究するなら表層形。",
        )
        s.unit = "lemma" if unit_label.startswith("見出し語") else "surface"
    return s
