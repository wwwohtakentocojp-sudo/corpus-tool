"""1. データを読み込む

入力: .txt（複数 / zip / フォルダのパス）、CSV / Excel（1行 = 1文書）、サンプルデータ
読み込み後: サマリ、分析前のデータ量チェック、言語固有の注意、データに対する提案（表記ゆれなど）
"""
from __future__ import annotations

import streamlit as st

from analyzers.detect import detect_language
from analyzers.registry import AVAILABLE_LANGUAGES, get_analyzer
from app_config import ROOT, thresholds
from corpus.checks import corpus_summary, group_columns, group_sizes, pre_analysis_flags
from corpus.cleaners import looks_like_aozora
from corpus.loaders import (
    guess_group_columns,
    guess_text_column,
    read_folder_txt,
    read_table,
    read_text_file_bytes,
    read_txt_bytes,
    read_zip_txt,
    table_to_documents,
)
from corpus.models import Document
from corpus.pipeline import build_corpus
from ui import demo, state
from ui.components import glossary_expander, metric_help, show_flags

st.title("1. データを読み込む")
if demo.is_demo():
    st.caption("デモ版です。同梱サンプルで機能を体験してください。ご自身の資料はアップロードせず、ローカル版で分析してください。")
else:
    st.caption("読み込んだテキストは外部に送信されません。すべての処理はこのパソコンの中で行われます。")

settings = state.get_settings()
cfg = state.config()

docs: list[Document] = []
source_label = ""

tab_txt, tab_table, tab_sample = st.tabs(["テキスト / PDF（.txt / .pdf / zip / フォルダ）", "CSV / Excel（1行 = 1文書）", "サンプルデータで試す"])

# ---------------------------------------------------------------------------
with tab_txt:
    st.markdown(
        "1ファイルが1文書として扱われます。zip の中の .txt / .pdf もまとめて読み込みます。"
        " PDF は文字を取り出して使います（論文の行末で切れた単語はつなぎ、ページ番号の行は除きます）。"
    )
    uploaded = st.file_uploader("ファイルを選ぶ（複数可）", type=["txt", "pdf", "zip"], accept_multiple_files=True)
    folder = st.text_input("または、フォルダのパスを入力（例: C:\\data\\interviews。中の .txt / .pdf を読みます）", value=st.session_state.get("folder_path", ""))
    if folder != st.session_state.get("folder_path", ""):
        st.session_state["folder_path"] = folder
    decoded: list[tuple[str, str, str]] = []
    for f in uploaded or []:
        if not demo.check_upload_size(f.name, f.size):
            continue
        if f.name.lower().endswith(".zip"):
            try:
                decoded.extend(read_zip_txt(f.getvalue()))
            except Exception:  # noqa: BLE001
                st.error(f"{f.name} を zip として開けませんでした。zip 形式か確認してください。")
        elif f.name.lower().endswith(".pdf"):
            try:
                decoded.append(read_text_file_bytes(f.name, f.getvalue()))
            except Exception:  # noqa: BLE001
                st.error(f"{f.name} を PDF として開けませんでした。パスワード付きや壊れたファイルの可能性があります。")
        else:
            decoded.append(read_txt_bytes(f.name, f.getvalue()))
    empty_pdfs = [n for n, t, e in decoded if e.startswith("PDF") and len(t.strip()) < 50]
    if empty_pdfs:
        st.warning(
            "次の PDF からは文字がほとんど取り出せませんでした: " + "、".join(empty_pdfs) + "。"
            " スキャン画像だけの PDF（文字情報のない PDF）の可能性があります。その場合は OCR ソフトで文字にしてから .txt で読み込んでください。"
        )
    pdf_loaded = [n for n, t, e in decoded if e.startswith("PDF") and len(t.strip()) >= 50]
    if pdf_loaded:
        st.info(
            "PDF の文字取り出しは完全ではありません。2段組の論文では左右の段が入り混じることがあり、"
            " ヘッダ・脚注・参考文献も本文と一緒に数えられます。重要な語は「5. 用例検索（KWIC）」で実際の文脈を確認してください。"
        )
    if folder.strip():
        try:
            decoded.extend(read_folder_txt(folder.strip()))
        except FileNotFoundError:
            st.error("そのフォルダが見つかりません。パスを確認してください。")
    if decoded:
        docs = [Document(doc_id=i, name=n, text=t, meta={"encoding": e}) for i, (n, t, e) in enumerate(decoded)]
        source_label = "テキスト / PDF"
        st.dataframe([{"ファイル": n, "文字数": len(t), "文字コード / 種別": e} for n, t, e in decoded], width="stretch", hide_index=True)

# ---------------------------------------------------------------------------
with tab_table:
    st.markdown("1行を1文書として読み込みます。本文の列と、比較に使うグループ列（年・ジャンル・話者など）を選んでください。")
    table_file = st.file_uploader("CSV / TSV / Excel", type=["csv", "tsv", "xlsx", "xlsm", "xls"], accept_multiple_files=False)
    if table_file is not None and not demo.check_upload_size(table_file.name, table_file.size):
        table_file = None
    if table_file is not None:
        try:
            df = read_table(table_file.name, table_file.getvalue())
        except Exception as e:  # noqa: BLE001
            st.error(f"ファイルを表として読めませんでした。CSV は1行目が列名になっている必要があります。（{e}）")
            df = None
        if df is not None and len(df):
            st.dataframe(df.head(5), width="stretch", hide_index=True)
            st.caption(f"{len(df):,} 行 × {len(df.columns)} 列（先頭5行を表示）")
            cols = list(df.columns)
            guess_text = guess_text_column(df)
            text_col = st.selectbox("本文はどの列ですか", cols, index=cols.index(guess_text) if guess_text in cols else 0)
            group_default = guess_group_columns(df, text_col)
            group_cols = st.multiselect(
                "グループ分けに使う列（複数可・任意）",
                [c for c in cols if c != text_col],
                default=group_default,
                help="年・ジャンル・話者などの列。あとで群間比較や、グループ単位の散らばり計算に使います。",
            )
            name_opts = ["（行番号）"] + [c for c in cols if c != text_col]
            name_col = st.selectbox("文書名に使う列（任意）", name_opts, index=0)
            docs = table_to_documents(df, text_col, group_cols, None if name_col == "（行番号）" else name_col)
            docs = [d for d in docs if d.text.strip()]
            source_label = f"{table_file.name}"
            if len(docs) < len(df):
                st.caption(f"本文が空の {len(df) - len(docs)} 行は除きました。")

# ---------------------------------------------------------------------------
with tab_sample:
    sample_dir = ROOT / "samples"
    # デモ用の加工済みサンプル（同梱）と、ローカルで取得した完全版（samples/ja など）の両方を出す
    sample_files = sorted(sample_dir.rglob("*.txt")) if sample_dir.exists() else []
    sample_files = [p for p in sample_files if not p.name.endswith("-words.txt")]
    if not sample_files:
        st.info("サンプルデータがありません。プロジェクトのフォルダで `uv run python scripts/download_samples.py` を実行すると用意されます。")
    else:
        st.caption("出典とライセンスは samples/README.md を参照してください（青空文庫・Project Gutenberg・Leipzig Corpora Collection）。")
        chosen = st.multiselect(
            "サンプル",
            options=sample_files,
            default=[],
            format_func=lambda p: str(p.relative_to(sample_dir)).replace("\\", "/"),
        )
        if chosen and not docs:
            decoded = [read_txt_bytes(p.name, p.read_bytes()) for p in chosen]
            docs = [Document(doc_id=i, name=n, text=t, meta={"encoding": e}) for i, (n, t, e) in enumerate(decoded)]
            source_label = "サンプル"

# ---------------------------------------------------------------------------
if not docs:
    corpus = state.get_corpus()
    if corpus is not None:
        st.success(f"現在、{corpus.n_documents} 文書・{corpus.n_tokens:,} 語のデータが読み込まれています。左のメニューから分析に進めます。")
    st.stop()

st.markdown("---")
st.markdown(f"#### 読み込み設定（{source_label}: {len(docs)} 文書）")

detected = detect_language("\n".join(d.text[:5000] for d in docs[:50]))
codes = list(AVAILABLE_LANGUAGES.keys())
lang = st.selectbox(
    "言語（自動判定の結果を初期値にしています。違っていれば選び直してください）",
    options=codes,
    index=codes.index(detected) if detected in codes else 0,
    format_func=lambda c: AVAILABLE_LANGUAGES[c],
)
if lang == "de":
    demo.german_model_note()

aozora_detected = any(looks_like_aozora(d.text) for d in docs[:50])
aozora = st.checkbox(
    "青空文庫の形式（ルビ《》・注記［＃］・底本情報）を取り除く",
    value=aozora_detected,
    help="青空文庫からダウンロードしたファイルには、ルビや編集注記が含まれています。そのまま数えると「《」などが語として数えられてしまいます。",
)


def _run_build(docs_: list[Document], settings_) -> None:
    bar = st.progress(0.0, text="解析しています...")

    def _progress(i: int, n: int) -> None:
        bar.progress(i / n, text=f"解析しています... {i}/{n} 文書")

    corpus_ = build_corpus(docs_, settings_, cfg, progress=_progress)
    bar.empty()
    state.set_corpus(corpus_, docs_)


if st.button("この内容で読み込む", type="primary"):
    if settings.language != lang:
        settings.language_options = {}
    settings.language = lang
    settings.cleaning = {"aozora": bool(aozora)}
    analyzer = get_analyzer(lang, cfg)
    settings.language_options = {**analyzer.default_options(), **settings.language_options}
    _run_build(docs, settings)

# ---------------------------------------------------------------------------
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
    st.caption(f"機能語（助詞・冠詞・記号など）を除くと、延べ {summ['n_tokens_content']:,} 語・異なり {summ['n_types_content']:,} 語です。")

    st.markdown("#### 分析を始める前の確認")
    flags = pre_analysis_flags(corpus, thresholds(cfg))
    show_flags(flags, empty_message="データ量に大きな問題はありません。左のメニューから分析に進んでください。")
    glossary_expander(["data_size", "token_type"], title="❓ データ量の目安と、延べ語数・異なり語数について")

    analyzer = get_analyzer(corpus.language, cfg)
    loaded_docs = state.get_documents()
    for w in analyzer.data_warnings([d.text for d in loaded_docs], settings.language_options):
        st.warning(w["message"])
        if w.get("suggest_option"):
            if st.button("提案どおりに設定して解析し直す", key=f"suggest_{w['suggest_option']}"):
                settings.language_options[w["suggest_option"]] = w.get("suggest_value", True)
                _run_build(loaded_docs, settings)
                st.rerun()
    for w in analyzer.language_warnings(settings.language_options):
        st.info(w)

    gcols = group_columns(corpus)
    if gcols:
        st.markdown("#### グループごとの文書数")
        for col in gcols:
            g = group_sizes(corpus, col).rename(columns={col: col, "n_documents": "文書数", "n_tokens": "延べ語数"})
            st.dataframe(g, width="stretch", hide_index=True)

    with st.expander("文書ごとの内訳"):
        per_doc = corpus.tokens.groupby("doc_id").size().rename("延べ語数").reset_index()
        per_doc = per_doc.merge(corpus.documents[["doc_id", "name", "n_chars"] + gcols], on="doc_id")
        per_doc = per_doc.rename(columns={"name": "文書", "n_chars": "文字数"}).drop(columns=["doc_id"])
        st.dataframe(per_doc, width="stretch", hide_index=True)
