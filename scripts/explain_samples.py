"""解説文（explainer.py）の出力サンプルを実データで生成する。

  uv run python scripts/explain_samples.py

青空文庫3作品（日本語）から、頻度・コロケーション・特徴語の実際の数値とフラグを取り、
explainer に渡した結果をプレーンテキストで出力する。
"""
from __future__ import annotations

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
from interpretations.explainer import ExplainInput, explain  # noqa: E402
from interpretations.rules import (  # noqa: E402
    check_collocation_row,
    check_dispersion,
    check_dp_reliability,
    check_group_imbalance,
    check_keyness_row,
    check_low_frequency,
    high_frequency_cutoff,
)
from stats.collocation import collocation_table  # noqa: E402
from stats.frequency import frequency_table  # noqa: E402
from stats.keyness import keyness_table, split_by_group  # noqa: E402


def load_ja() -> Corpus:
    docs = []
    for i, p in enumerate(sorted((ROOT / "samples" / "ja").glob("*.txt"))):
        name, text, _ = read_txt_bytes(p.name, p.read_bytes())
        docs.append(Document(i, name, clean_aozora(text), meta={"author": name.split("_")[0]}))
    return build_corpus(docs, AnalysisSettings(language="ja"), load_config())


def sample_collocation(corpus: Corpus, node: str, pick: str | None, th) -> tuple[ExplainInput, str]:
    tbl = collocation_table(corpus.tokens, node, "lemma", "sentence", 5, 2)
    tbl = tbl[~tbl["is_function"]]
    cutoff = high_frequency_cutoff(corpus.tokens["lemma"].value_counts().to_numpy(), th)

    def flags_of(r):
        return check_collocation_row(r["mi"], r["t"], int(r["cooccur"]), bool(r["is_function"]), False, th,
                                     int(r["freq_node"]), int(r["freq_collocate"]), cutoff, float(r["g2"]))

    if pick == "flagged":
        row = next(r for _, r in tbl.iterrows() if any(f.code == "MI_HIGH_LOW_FREQ" for f in flags_of(r)))
    elif pick == "disagree":
        # logDice は目安以上だが MI が偶然に近い（指標が食い違う）組
        row = next(r for _, r in tbl.iterrows() if r["log_dice"] >= th["log_dice_strong"] and r["mi"] < th["mi_meaningful"]
                   and not any(f.code in ("BOTH_HIGH_FREQUENCY", "T_ONLY_FUNCTION_WORD") for f in flags_of(r)))
    elif pick == "clean":
        # フラグ無しかつ 3 指標すべてが目安以上
        cands = [r for _, r in tbl.iterrows() if not flags_of(r) and r["log_dice"] >= th["log_dice_strong"]
                 and r["mi"] >= th["mi_meaningful"] and r["g2"] >= th["g2_significant"]]
        if not cands:
            raise LookupError(f"『{node}』には、フラグ無しで3指標すべてが目安以上の共起語がありません")
        row = cands[0]
    elif pick:
        row = tbl[tbl["label"] == pick].iloc[0]
    else:
        row = tbl.iloc[0]
    flags = flags_of(row)
    inp = ExplainInput(
        screen="collocation",
        metrics={"cooccur": int(row["cooccur"]), "freq_node": int(row["freq_node"]), "freq_collocate": int(row["freq_collocate"]),
                 "mi": float(row["mi"]), "t": float(row["t"]), "log_dice": float(row["log_dice"]),
                 "g2": float(row["g2"]), "p": float(row["p"]), "n_total": corpus.n_tokens},
        flags=flags, words={"WORD": node, "COLLOCATE": str(row["label"])}, settings={"window_label": "同一文内"},
    )
    return inp, f"コロケーション（同一文内）: 『{node}』×『{row['label']}』 / フラグ: {[f.code for f in flags] or 'なし'}"


def sample_frequency(corpus: Corpus, word: str, th) -> tuple[ExplainInput, str]:
    ft = frequency_table(corpus.tokens, "lemma", False).set_index("word")
    row = ft.loc[word]
    n_parts = corpus.n_documents
    flags = check_dp_reliability(n_parts, th) + check_low_frequency(word, int(row["freq"]), th)
    if not check_dp_reliability(n_parts, th):
        flags += check_dispersion(word, int(row["freq"]), float(row["dp"]), th)
    inp = ExplainInput(
        screen="frequency",
        metrics={"freq": int(row["freq"]), "pmw": float(row["pmw"]), "dp": float(row["dp"]), "n_parts": n_parts, "n_total": corpus.n_tokens},
        flags=flags, words={"WORD": str(row["label"])},
    )
    return inp, f"頻度（散らばりの単位: 文書）: 『{row['label']}』 / フラグ: {[f.code for f in flags] or 'なし'}"


def sample_keyness(corpus: Corpus, word: str, a: str, th) -> tuple[ExplainInput, str]:
    ta, tb = split_by_group(corpus.tokens, corpus.documents, "author", a, None)
    kt = keyness_table(ta, tb, "lemma", False).set_index("word")
    row = kt.loc[word]
    sizes = group_sizes(corpus, "author")
    n_a = int(sizes.loc[sizes["author"] == a, "n_documents"].sum())
    n_b = int(sizes.loc[sizes["author"] != a, "n_documents"].sum())
    flags = check_keyness_row(float(row["log_ratio"]), th, word, bool(row["zero_corrected"])) + check_group_imbalance({a: n_a, "それ以外の作者": n_b}, th)
    inp = ExplainInput(
        screen="keyness",
        metrics={"freq_a": int(row["freq_a"]), "freq_b": int(row["freq_b"]), "n_a": len(ta), "n_b": len(tb),
                 "pmw_a": float(row["pmw_a"]), "pmw_b": float(row["pmw_b"]), "log_ratio": float(row["log_ratio"]),
                 "g2": float(row["g2"]), "p": float(row["p"]), "odds_ratio": float(row["odds_ratio"])},
        flags=flags, words={"WORD": str(row["label"]), "GROUP_A": a, "GROUP_B": "それ以外の作者"},
    )
    return inp, f"特徴語（作者: A = {a}、B = それ以外の作者）: 『{row['label']}』 / フラグ: {[f.code for f in flags] or 'なし'}"


def main() -> int:
    cfg = load_config()
    th = thresholds(cfg)
    corpus = load_ja()
    samples = [
        sample_collocation(corpus, "先生", None, th),
        sample_collocation(corpus, "先生", "flagged", th),
        sample_frequency(corpus, "俺", th),
        sample_keyness(corpus, "俺", "夏目漱石", th),
        sample_keyness(corpus, "下人", "芥川龍之介", th),
        sample_collocation(corpus, "先生", "disagree", th),  # 指標が食い違う組（NOT_DISTINGUISHABLE が立つ想定）
    ]
    # サンプル 7: フラグ無しで 3 指標すべてが目安以上の組を、いくつかの中心語から探す
    found = None
    for node in ["先生", "奥さん", "手紙", "赤シャツ", "山嵐", "下人", "老婆", "母", "父", "叔父", "友達", "病気", "死ぬ"]:
        try:
            found = sample_collocation(corpus, node, "clean", th)
            break
        except (LookupError, StopIteration, IndexError):
            continue
    if found:
        samples.append(found)
    else:
        print("サンプル 7: フラグ無しで 3 指標すべてが目安以上の組み合わせは、探索した中心語の範囲では見つかりませんでした。\n")
    for i, (inp, title) in enumerate(samples, 1):
        print("=" * 78)
        print(f"サンプル {i}: {title}")
        print("=" * 78)
        print(explain(inp, th))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
