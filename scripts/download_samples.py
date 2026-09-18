"""サンプルデータのダウンロード。

  日本語:   青空文庫（著作権切れ作品）
  英語:     Project Gutenberg（著作権切れ作品）
  ドイツ語: Leipzig Corpora Collection（文と頻度リスト。統計計算の健全性確認にも使う）

使い方:  uv run python scripts/download_samples.py [--lang ja|en|de|all] [--force]
"""
from __future__ import annotations

import argparse
import io
import re
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples"
UA = {"User-Agent": "corpus-tool-sample-downloader"}

# 青空文庫: (保存名, zip の URL)
AOZORA = [
    ("夏目漱石_こころ", "https://www.aozora.gr.jp/cards/000148/files/773_ruby_5968.zip"),
    ("夏目漱石_坊っちゃん", "https://www.aozora.gr.jp/cards/000148/files/752_ruby_2438.zip"),
    ("芥川龍之介_羅生門", "https://www.aozora.gr.jp/cards/000879/files/127_ruby_150.zip"),
]

# Project Gutenberg: (保存名, 作品ID)
GUTENBERG = [
    ("Austen_Pride_and_Prejudice", 1342),
    ("Carroll_Alice_in_Wonderland", 11),
    ("Shelley_Frankenstein", 84),
]

# Leipzig Corpora Collection: 候補を順に試す（公開名が変わることがあるため）
LEIPZIG_CANDIDATES = [
    "deu_news_2023_10K",
    "deu_news_2022_10K",
    "deu_news_2021_10K",
    "deu_wikipedia_2021_10K",
    "deu_news_2020_10K",
]
LEIPZIG_BASE = "https://downloads.wortschatz-leipzig.de/corpora/{name}.tar.gz"


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


# ---------------------------------------------------------------------------
def download_aozora(force: bool = False) -> None:
    out_dir = SAMPLES / "ja"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, url in AOZORA:
        dest = out_dir / f"{name}.txt"
        if dest.exists() and not force:
            print(f"  済: {dest.name}")
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
        except Exception as e:  # noqa: BLE001
            print(f" 失敗: {e}")


# ---------------------------------------------------------------------------
_GB_START = re.compile(r"\*\*\* ?START OF (THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*", re.IGNORECASE)
_GB_END = re.compile(r"\*\*\* ?END OF (THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*", re.IGNORECASE)


def strip_gutenberg(text: str) -> str:
    m = _GB_START.search(text)
    if m:
        text = text[m.end():]
    m = _GB_END.search(text)
    if m:
        text = text[: m.start()]
    return text.strip()


def download_gutenberg(force: bool = False) -> None:
    out_dir = SAMPLES / "en"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, gid in GUTENBERG:
        dest = out_dir / f"{name}.txt"
        if dest.exists() and not force:
            print(f"  済: {dest.name}")
            continue
        print(f"  取得中: {name} ...", end="", flush=True)
        try:
            data = None
            for url in (f"https://www.gutenberg.org/cache/epub/{gid}/pg{gid}.txt",
                        f"https://www.gutenberg.org/files/{gid}/{gid}-0.txt"):
                try:
                    data = _fetch(url)
                    break
                except Exception:  # noqa: BLE001
                    continue
            if data is None:
                print(" 失敗（取得できません）")
                continue
            text = strip_gutenberg(data.decode("utf-8", errors="replace"))
            dest.write_text(text, encoding="utf-8")
            print(f" 保存 ({len(text):,} 文字)")
        except Exception as e:  # noqa: BLE001
            print(f" 失敗: {e}")


# ---------------------------------------------------------------------------
def download_leipzig(force: bool = False) -> None:
    """文ファイル → samples/de/<name>.txt、頻度リスト → samples/de/<name>-words.txt"""
    out_dir = SAMPLES / "de"
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = list(out_dir.glob("*-words.txt"))
    if existing and not force:
        print(f"  済: {existing[0].name}")
        return
    for name in LEIPZIG_CANDIDATES:
        url = LEIPZIG_BASE.format(name=name)
        print(f"  取得中: {name} ...", end="", flush=True)
        try:
            data = _fetch(url)
        except Exception as e:  # noqa: BLE001
            print(f" 見つかりません ({e})")
            continue
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            members = {Path(m.name).name: m for m in tf.getmembers() if m.isfile()}
            sent = next((m for n, m in members.items() if n.endswith("-sentences.txt")), None)
            words = next((m for n, m in members.items() if n.endswith("-words.txt")), None)
            if sent is None or words is None:
                print(" 失敗（想定のファイルがありません）")
                continue
            # 文ファイルは「番号<TAB>文」形式。文だけを取り出して1行1文で保存
            lines = tf.extractfile(sent).read().decode("utf-8", errors="replace").splitlines()
            sentences = [l.split("\t", 1)[1] if "\t" in l else l for l in lines]
            (out_dir / f"{name}.txt").write_text("\n".join(sentences), encoding="utf-8")
            (out_dir / f"{name}-words.txt").write_bytes(tf.extractfile(words).read())
        print(f" 保存 ({len(sentences):,} 文)")
        return
    print("  Leipzig のデータを取得できませんでした。https://wortschatz.uni-leipzig.de/en/download から手動で入手し samples/de に置いてください。")


# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="all", choices=["ja", "en", "de", "all"])
    ap.add_argument("--force", action="store_true", help="既にあるファイルも取り直す")
    args = ap.parse_args(argv)

    if args.lang in ("ja", "all"):
        print("日本語: 青空文庫")
        download_aozora(force=args.force)
    if args.lang in ("en", "all"):
        print("英語: Project Gutenberg")
        download_gutenberg(force=args.force)
    if args.lang in ("de", "all"):
        print("ドイツ語: Leipzig Corpora Collection")
        download_leipzig(force=args.force)
    print(f"保存先: {SAMPLES}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
