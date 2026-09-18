"""デモ版に同梱するサンプル（samples/demo/）を、ローカルのサンプルから作る。

  uv run python scripts/download_samples.py      # 先に元データを取得
  uv run python scripts/make_demo_samples.py

加工内容:
  ja: 青空文庫の注記（ルビ・［＃］・底本情報）を除去した本文
  en: Project Gutenberg のヘッダ・フッタを除いた本文（download_samples.py が既に除去済み）
  de: Leipzig の文ファイルから先頭 N 文（既定 1000）

samples/demo/ は git で追跡する（デモ版は初回アクセス時の外部取得を行わない）。
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from corpus.cleaners import clean_aozora  # noqa: E402

SRC = ROOT / "samples"
DST = ROOT / "samples" / "demo"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--de-sentences", type=int, default=1000)
    args = ap.parse_args(argv)

    for lang in ("ja", "en", "de"):
        (DST / lang).mkdir(parents=True, exist_ok=True)

    for p in sorted((SRC / "ja").glob("*.txt")):
        text = clean_aozora(p.read_text(encoding="utf-8"))
        (DST / "ja" / p.name).write_text(text, encoding="utf-8")
        print(f"ja: {p.name} ({len(text):,} 文字)")

    for p in sorted((SRC / "en").glob("*.txt")):
        shutil.copyfile(p, DST / "en" / p.name)
        print(f"en: {p.name} ({p.stat().st_size:,} bytes)")

    for p in sorted((SRC / "de").glob("*.txt")):
        if p.name.endswith("-words.txt"):
            continue
        lines = p.read_text(encoding="utf-8").splitlines()[: args.de_sentences]
        name = p.stem.replace("10K", f"{args.de_sentences}") + ".txt"
        (DST / "de" / name).write_text("\n".join(lines), encoding="utf-8")
        print(f"de: {name} ({len(lines):,} 文)")
    print(f"保存先: {DST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
