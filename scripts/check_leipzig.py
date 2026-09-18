"""Leipzig の頻度リストと本ツールの頻度集計を突き合わせる健全性確認。

トークン化の方法が違うため完全一致はしない。「桁と順位が概ね合っているか」を見る。
統計計算の正しさそのものは tests/ の手計算テストで担保する。

使い方:  uv run python scripts/check_leipzig.py [--top 30]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=30)
    args = ap.parse_args(argv)

    de_dir = ROOT / "samples" / "de"
    words_files = sorted(de_dir.glob("*-words.txt"))
    if not words_files:
        print("samples/de に Leipzig の頻度リストがありません。scripts/download_samples.py --lang de を実行してください。")
        return 1
    words_file = words_files[0]
    text_file = de_dir / words_file.name.replace("-words.txt", ".txt")

    import pandas as pd

    from corpus.models import Document
    from corpus.pipeline import build_corpus
    from corpus.settings import AnalysisSettings
    from stats.frequency import frequency_table

    # Leipzig: 番号<TAB>語<TAB>頻度
    ref = pd.read_csv(words_file, sep="\t", header=None, names=["id", "word", "freq"], quoting=3, dtype={"word": str})
    ref = ref.dropna(subset=["word"]).set_index("word")["freq"]

    text = text_file.read_text(encoding="utf-8")
    corpus = build_corpus([Document(0, text_file.stem, text)], AnalysisSettings(language="de", unit="surface"))
    ours = frequency_table(corpus.tokens, unit="surface", include_function_words=True).set_index("word")["freq"]

    top = ref.sort_values(ascending=False).head(args.top)
    rows = []
    for w, f in top.items():
        o = int(ours.get(w, 0))
        rows.append({"word": w, "leipzig": int(f), "ours": o, "ratio": round(o / f, 3) if f else None})
    df = pd.DataFrame(rows)
    print(df.to_string(index=False))
    ok = df["ratio"].between(0.8, 1.25).mean()
    print(f"\n上位 {args.top} 語のうち、頻度が ±20% 以内に収まる割合: {ok:.0%}")
    print("（トークン化の違いによる差は正常です。桁が違う語があれば読み込みや前処理を疑ってください）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
