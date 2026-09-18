"""2. 前処理の設定（言語固有オプションは analyzer.option_schema() から自動生成）"""
from __future__ import annotations

import streamlit as st

from analyzers.registry import AVAILABLE_LANGUAGES, get_analyzer
from corpus.pipeline import build_corpus
from ui import demo, state

st.title("2. 前処理の設定")
st.markdown("語の区切り方・まとめ方に関する設定です。変更したら、下の「この設定で解析し直す」を押してください。")

settings = state.get_settings()
cfg = state.config()
analyzer = get_analyzer(settings.language, cfg)

st.markdown(f"**言語:** {AVAILABLE_LANGUAGES.get(settings.language, settings.language)}")
if settings.language == "de":
    demo.german_model_note()

# --- 言語固有オプション ---------------------------------------------------------
current = {**analyzer.default_options(), **settings.language_options}
new_opts: dict = {}
st.markdown("#### 語のまとめ方")
for opt in analyzer.option_schema():
    key = opt["key"]
    if key == "model" and demo.is_demo():
        new_opts[key] = "sm"  # デモ版は sm 固定（lg は公開環境のメモリに載らない）
        continue
    if opt["type"] == "bool":
        new_opts[key] = st.checkbox(opt["label"], value=bool(current.get(key, opt["default"])), help=opt.get("help"))
    elif opt["type"] == "choice":
        choices = opt["choices"]  # value -> label
        values = list(choices.keys())
        idx = values.index(current.get(key, opt["default"])) if current.get(key, opt["default"]) in values else 0
        new_opts[key] = st.radio(opt["label"], options=values, index=idx, format_func=lambda v, c=choices: c[v], help=opt.get("help"))

# --- 機能語 ----------------------------------------------------------------------
st.markdown("#### 機能語の扱い")
st.markdown(
    "既定では、以下の品詞を「機能語」として集計から除外します（各分析画面の左側で、ワンクリックで含める／除くを切り替えられます）。"
)
st.code("、".join(sorted(analyzer.function_pos(new_opts))), language=None)
st.caption("助詞や助動詞そのものを研究する場合は、分析画面で「機能語を含める」を ON にしてください。")

# --- 共通設定 --------------------------------------------------------------------
st.markdown("#### 語彙の豊かさ（標準化TTR）の区切り幅")
sttr_window = st.number_input(
    "何語ごとに区切って計算するか",
    min_value=100,
    max_value=10000,
    value=int(settings.sttr_window),
    step=100,
    help="論文には必ずこの値を明記してください（例:「1000語単位で算出」）。値を変えると数値も変わります。",
)

# --- 適用 ------------------------------------------------------------------------
changed_tokenization = new_opts != current
settings.sttr_window = int(sttr_window)

if st.button("この設定で解析し直す", type="primary", disabled=state.get_corpus() is None):
    settings.language_options = new_opts
    docs = state.get_documents()
    bar = st.progress(0.0, text="解析しています...")

    def _progress(i: int, n: int) -> None:
        bar.progress(i / n, text=f"解析しています... {i}/{n} 文書")

    corpus = build_corpus(docs, settings, cfg, progress=_progress)
    bar.empty()
    state.set_corpus(corpus, docs)
    st.success("解析し直しました。")
elif changed_tokenization:
    st.info("設定が変更されています。「この設定で解析し直す」を押すと反映されます。")

if state.get_corpus() is None:
    st.info("データを読み込むと、この設定で解析し直せます。")

st.markdown("---")
st.markdown("#### この言語で注意すること")
for w in analyzer.language_warnings(new_opts):
    st.info(w)

# --- 見出し語化の比較（ドイツ語 lemma_mode = both のとき） -------------------------
corpus = state.get_corpus()
if corpus is not None and "lemma_alt" in corpus.tokens.columns:
    t = corpus.tokens
    diff = t[(t["lemma_alt"] != "") & (t["lemma_alt"] != t["lemma"])]
    if len(diff):
        st.markdown("#### 見出し語化の手法による差異")
        st.markdown(
            f"spaCy と HanTa で見出し語が異なる語が **{diff[['surface', 'lemma', 'lemma_alt']].drop_duplicates().shape[0]} 種類** ありました。"
            " 集計には spaCy の結果を使っています。重要な語が含まれていれば、どちらが正しいかを用例で確認してください。"
        )
        tbl = diff.groupby(["surface", "lemma", "lemma_alt"]).size().rename("出現回数").reset_index()
        tbl = tbl.sort_values("出現回数", ascending=False).rename(columns={"surface": "表層形", "lemma": "spaCy", "lemma_alt": "HanTa"})
        st.dataframe(tbl, width="stretch", hide_index=True, height=400)
        from ui.components import download_csv

        download_csv(tbl, "lemma_comparison.csv", key="dl_lemma_cmp")
