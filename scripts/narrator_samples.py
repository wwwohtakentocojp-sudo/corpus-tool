"""narrator.py の出力サンプルを実データで生成する（全画面に組み込む前の確認用）。

  uv run python scripts/narrator_samples.py            # API キーがあれば API、無ければ定型文
  uv run python scripts/narrator_samples.py --no-api   # 定型文のみ

青空文庫3作品（日本語）と Leipzig（ドイツ語）から、頻度・コロケーション・特徴語の
実際の数値とフラグを取り、narrator に渡した結果をプレーンテキストで出力する。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app_config import load_config, thresholds  # noqa: E402
from corpus.checks import group_sizes  # noqa: E402
from corpus.cleaners import clean_aozora  # noqa: E402
from corpus.loaders import read_txt_bytes  # noqa: E402
from corpus.models import Corpus, Document  # noqa: E402
from corpus.pipeline import build_corpus  # noqa: E402
from corpus.settings import AnalysisSettings  # noqa: E402
from interpretations.narrator import NarrationInput, api_available, build_user_message, narrate  # noqa: E402
from interpretations.rules import (  # noqa: E402
    check_collocation_row,
    check_dispersion,
    check_dp_reliability,
    check_group_imbalance,
    check_keyness_row,
    check_low_frequency,
)
from stats.collocation import collocation_table  # noqa: E402
from stats.frequency import frequency_table  # noqa: E402
from stats.keyness import keyness_table, split_by_group  # noqa: E402


def load_ja() -> Corpus:
    docs = []
    for i, p in enumerate(sorted((ROOT / "samples" / "ja").glob("*.txt"))):
        name, text, _ = read_txt_bytes(p.name, p.read_bytes())
        # 作品ごとに「作者」をグループ列にする（特徴語サンプル用）
        docs.append(Document(i, name, clean_aozora(text), meta={"author": name.split("_")[0]}))
    return build_corpus(docs, AnalysisSettings(language="ja"), load_config())


def sample_collocation(corpus: Corpus, node: str, collocate_pick: str | None, th, cfg) -> tuple[NarrationInput, str]:
    tbl = collocation_table(corpus.tokens, node, "lemma", "sentence", 5, 2)
    tbl = tbl[~tbl["is_function"]]
    if collocate_pick == "flagged":
        # MI が高いのに回数が少ない（要用例確認）組を実データから選ぶ
        flagged = tbl[[any(f.code == "MI_HIGH_LOW_FREQ" for f in check_collocation_row(r.mi, r.t, int(r.cooccur), False, False, th)) for r in tbl.itertuples()]]
        row = flagged.iloc[0]
    elif collocate_pick:
        row = tbl[tbl["label"] == collocate_pick].iloc[0]
    else:
        row = tbl.iloc[0]
    flags = check_collocation_row(row["mi"], row["t"], int(row["cooccur"]), bool(row["is_function"]), False, th)
    inp = NarrationInput(
        screen="collocation", language="ja",
        metrics={"cooccur": int(row["cooccur"]), "freq_node": int(row["freq_node"]), "freq_collocate": int(row["freq_collocate"]),
                 "mi": round(float(row["mi"]), 2), "t": round(float(row["t"]), 2), "log_dice": round(float(row["log_dice"]), 2),
                 "g2": round(float(row["g2"]), 1), "p": float(row["p"]), "n_total": corpus.n_tokens},
        flags=flags, placeholders={"WORD": node, "COLLOCATE": str(row["label"])},
        settings={"window_method": "sentence", "window_label": "同一文内"},
    )
    return inp, f"コロケーション: 『{node}』×『{row['label']}』（フラグ: {[f.code for f in flags] or 'なし'}）"


def sample_frequency(corpus: Corpus, word: str, th) -> tuple[NarrationInput, str]:
    ft = frequency_table(corpus.tokens, "lemma", False).set_index("word")
    row = ft.loc[word]
    n_parts = corpus.n_documents
    flags = check_dp_reliability(n_parts, th) + check_low_frequency(word, int(row["freq"]), th)
    if not check_dp_reliability(n_parts, th):
        flags += check_dispersion(word, int(row["freq"]), float(row["dp"]), th)
    inp = NarrationInput(
        screen="frequency", language="ja",
        metrics={"freq": int(row["freq"]), "pmw": round(float(row["pmw"]), 1), "dp": round(float(row["dp"]), 2),
                 "n_parts": n_parts, "n_total": corpus.n_tokens},
        flags=flags, placeholders={"WORD": str(row["label"])},
        settings={"dp_unit": "document"},
    )
    return inp, f"頻度: 『{row['label']}』（フラグ: {[f.code for f in flags] or 'なし'}）"


def sample_keyness(corpus: Corpus, word: str, a: str, th) -> tuple[NarrationInput, str]:
    ta, tb = split_by_group(corpus.tokens, corpus.documents, "author", a, None)
    kt = keyness_table(ta, tb, "lemma", False).set_index("word")
    row = kt.loc[word]
    sizes = group_sizes(corpus, "author")
    n_a = int(sizes.loc[sizes["author"] == a, "n_documents"].sum())
    n_b = int(sizes.loc[sizes["author"] != a, "n_documents"].sum())
    flags = check_keyness_row(float(row["log_ratio"]), th, word, bool(row["zero_corrected"])) + check_group_imbalance({a: n_a, "その他": n_b}, th)
    inp = NarrationInput(
        screen="keyness", language="ja",
        metrics={"freq_a": int(row["freq_a"]), "freq_b": int(row["freq_b"]), "n_a": len(ta), "n_b": len(tb),
                 "pmw_a": round(float(row["pmw_a"]), 1), "pmw_b": round(float(row["pmw_b"]), 1),
                 "log_ratio": round(float(row["log_ratio"]), 2), "g2": round(float(row["g2"]), 1), "p": float(row["p"]),
                 "odds_ratio": round(float(row["odds_ratio"]), 2), "zero_corrected": bool(row["zero_corrected"])},
        flags=flags, placeholders={"WORD": str(row["label"]), "GROUP_A": a, "GROUP_B": "それ以外の作者"},
        settings={"group_column": "author"},
    )
    return inp, f"特徴語: 『{row['label']}』 {a} vs その他（フラグ: {[f.code for f in flags] or 'なし'}）"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-api", action="store_true")
    ap.add_argument("--show-prompt", action="store_true", help="API に送る内容（数値とフラグのみ）も表示する")
    args = ap.parse_args(argv)
    cfg = load_config()
    th = thresholds(cfg)
    use_api = not args.no_api
    print(f"API: {'使用' if use_api and api_available() else '未使用（定型文）'}\n")

    corpus = load_ja()
    samples = [
        sample_collocation(corpus, "先生", None, th, cfg),        # 最上位 logDice の組
        sample_collocation(corpus, "先生", "flagged", th, cfg),   # MI 高・回数少（要用例確認）の組
        sample_frequency(corpus, "俺", th),                       # DP: 3文書なので DP_TOO_FEW_PARTS
        sample_keyness(corpus, "俺", "夏目漱石", th),             # 漱石 vs 芥川
        sample_keyness(corpus, "下人", "芥川龍之介", th),         # 0 補正が入る例
    ]
    for i, (inp, title) in enumerate(samples, 1):
        print("=" * 78)
        print(f"サンプル {i}: {title}")
        print("=" * 78)
        if args.show_prompt:
            print("--- API に送る内容 ---")
            print(build_user_message(inp))
            print("--- 出力 ---")
        out = narrate(inp, cfg, use_api=use_api)
        print(f"[source={out.source}] {out.note}")
        print(out.text)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
