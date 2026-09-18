"""1. データを読み込む（Phase 0: .txt 複数ファイル、またはサンプルデータ）"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from analyzers.detect import detect_language
from analyzers.registry import AVAILABLE_LANGUAGES, get_analyzer
from app_config import ROOT, thresholds
from corpus.checks import corpus_summary, pre_analysis_flags
from corpus.cleaners import looks_like_aozora
from corpus.loaders import read_txt_bytes
from corpus.models import Document
from corpus.pipeline import build_corpus
from ui import state
from ui.components import metric_help, show_flags

st.title("1. データを読み込む")
st.markdown(
    "分析したいテキストファイル（.txt）を選んでください。複数まとめて選べます。"
    " 1ファイルが1文書として扱われます。"
)
st.caption("読み込んだテキストは外部に送信されません。CSV / Excel の読み込みは次の段階で追加されます。")

settings = state.get_settings()
cfg = state.config()

# --- 入力元: アップロード、またはサンプル ----------------------------------------
tab_upload, tab_sample = st.tabs(["自分のファイルを読み込む", "サンプルデータで試す"])
decoded: list[tuple[str, str, str]] = []

with tab_upload:
    uploaded = st.file_uploader("テキストファイル（.txt）", type=["txt"], accept_multiple_files=True)
    if uploaded:
        for f in uploaded:
            decoded.append(read_txt_bytes(f.name, f.getvalue()))

with tab_sample:
    sample_dir = ROOT / "samples"
    sample_files = sorted(sample_dir.glob("*/*.txt")) if sample_dir.exists() else []
    if not sample_files:
        st.info("サンプルデータがまだありません。プロジェクトのフォルダで `uv run python scripts/download_samples.py` を実行すると用意されます。")
    else:
        chosen = st.multiselect(
            "サンプル（青空文庫の著作権切れ作品）",
            options=sample_files,
            default=sample_files if not uploaded else [],
            format_func=lambda p: f"{p.parent.name}/{p.name}",
        )
        if not uploaded:
            for p in chosen:
                decoded.append(read_txt_bytes(p.name, p.read_bytes()))

if not decoded:
    corpus = state.get_corpus()
    if corpus is not None:
        st.success(f"現在、{corpus.n_documents} 文書・{corpus.n_tokens:,} 語のデータが読み込まれています。左のメニューから分析に進めます。")
    st.stop()

# --- 文字コードの判定結果 -----------------------------------------------------
st.markdown("#### 読み込むファイル")
st.dataframe(
    [{"ファイル": n, "文字数": len(t), "文字コード": e} for n, t, e in decoded],
    width="stretch",
    hide_index=True,
)

# --- 言語の選択（自動判定は初期値の提案のみ） --------------------------------
detected = detect_language("\n".join(t[:5000] for _, t, _ in decoded))
codes = list(AVAILABLE_LANGUAGES.keys())
default_idx = codes.index(detected) if detected in codes else 0
if detected not in codes:
    st.warning(
        f"このファイルは日本語以外（推定: {detected}）のようです。現在の段階では日本語のみ分析できます。"
        " 英語・ドイツ語は次の段階で追加されます。"
    )
lang = st.selectbox(
    "言語（自動判定の結果を初期値にしています。違っていれば選び直してください）",
    options=codes,
    index=default_idx,
    format_func=lambda c: AVAILABLE_LANGUAGES[c],
)

# --- 整形オプション ------------------------------------------------------------
aozora_detected = any(looks_like_aozora(t) for _, t, _ in decoded)
aozora = st.checkbox(
    "青空文庫の形式（ルビ《》・注記［＃］・底本情報）を取り除く",
    value=aozora_detected,
    help="青空文庫からダウンロードしたファイルには、ルビや編集注記が含まれています。そのまま数えると「《」などが語として数えられてしまいます。",
)
if aozora_detected and not aozora:
    st.info("青空文庫の注記らしきものが見つかりました。取り除かない場合、ルビや記号が語として数えられます。")

# --- 読み込み実行 --------------------------------------------------------------
if st.button("この内容で読み込む", type="primary"):
    settings.language = lang
    settings.cleaning = {"aozora": bool(aozora)}
    analyzer = get_analyzer(lang, cfg)
    if not settings.language_options:
        settings.language_options = analyzer.default_options()

    docs = [Document(doc_id=i, name=n, text=t, meta={"encoding": e}) for i, (n, t, e) in enumerate(decoded)]

    bar = st.progress(0.0, text="解析しています...")

    def _progress(i: int, n: int) -> None:
        bar.progress(i / n, text=f"解析しています... {i}/{n} 文書")

    corpus = build_corpus(docs, settings, cfg, progress=_progress)
    bar.empty()
    state.set_corpus(corpus, docs)
    st.session_state["_just_loaded"] = True

# --- 読み込み結果のサマリ ------------------------------------------------------
corpus = state.get_corpus()
if corpus is not None and corpus.n_tokens > 0:
    st.markdown("---")
    st.markdown("### 読み込み結果")
    summ = corpus_summary(corpus, unit=settings.unit)
    c1, c2, c3, c4 = st.columns(4)
    metric_help(c1, "文書数", summ["n_documents"])
    metric_help(c2, "延べ語数（token）", summ["n_tokens"], "token_type")
    metric_help(c3, "異なり語数（type）", summ["n_types"], "token_type")
    c4.metric("言語", AVAILABLE_LANGUAGES.get(corpus.language, corpus.language))
    st.caption(
        f"機能語（助詞・記号など）を除くと、延べ {summ['n_tokens_content']:,} 語・異なり {summ['n_types_content']:,} 語です。"
    )

    st.markdown("#### 分析を始める前の確認")
    flags = pre_analysis_flags(corpus, thresholds(cfg))
    show_flags(flags, empty_message="データ量に大きな問題はありません。左のメニューから分析に進んでください。")

    analyzer = get_analyzer(corpus.language, cfg)
    for w in analyzer.language_warnings(settings.language_options):
        st.info(w)

    with st.expander("文書ごとの内訳"):
        per_doc = corpus.tokens.groupby("doc_id").size().rename("延べ語数").reset_index()
        per_doc = per_doc.merge(corpus.documents[["doc_id", "name", "n_chars"]], on="doc_id")
        per_doc = per_doc.rename(columns={"name": "文書", "n_chars": "文字数"})[["文書", "文字数", "延べ語数"]]
        st.dataframe(per_doc, width="stretch", hide_index=True)
