"""サンプルデータのダウンロード。

Phase 0: 青空文庫（日本語）のみ。
Phase 1 で Project Gutenberg（英語）と Leipzig Corpora Collection（ドイツ語）を追加する。

使い方:  uv run python scripts/download_samples.py [--lang ja]
"""
from __future__ import annotations

import argparse
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples"

# 青空文庫: (保存名, zip の URL)。いずれも著作権切れ作品。
AOZORA = [
    ("夏目漱石_こころ", "https://www.aozora.gr.jp/cards/000148/files/773_ruby_5968.zip"),
    ("夏目漱石_坊っちゃん", "https://www.aozora.gr.jp/cards/000148/files/752_ruby_2438.zip"),
    ("芥川龍之介_羅生門", "https://www.aozora.gr.jp/cards/000879/files/127_ruby_150.zip"),
]


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "corpus-tool-sample-downloader"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def download_aozora(force: bool = False) -> list[Path]:
    out_dir = SAMPLES / "ja"
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for name, url in AOZORA:
        dest = out_dir / f"{name}.txt"
        if dest.exists() and not force:
            print(f"  済: {dest.name}")
            saved.append(dest)
            continue
        print(f"  取得中: {name} ...", end="", flush=True)
        try:
            data = _fetch(url)
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                txt_names = [n for n in zf.namelist() if n.lower().endswith(".txt")]
                if not txt_names:
                    print(" 失敗（zip に txt がありません）")
                    continue
                raw = zf.read(txt_names[0])
            text = raw.decode("cp932", errors="replace")
            dest.write_text(text, encoding="utf-8")
            print(f" 保存 ({len(text):,} 文字)")
            saved.append(dest)
        except Exception as e:  # noqa: BLE001
            print(f" 失敗: {e}")
    return saved


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="ja", choices=["ja", "en", "de", "all"])
    ap.add_argument("--force", action="store_true", help="既にあるファイルも取り直す")
    args = ap.parse_args(argv)

    if args.lang in ("ja", "all"):
        print("日本語: 青空文庫")
        download_aozora(force=args.force)
    if args.lang in ("en", "de"):
        print(f"{args.lang} のサンプルは Phase 1 で追加します。")
    print(f"保存先: {SAMPLES}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
