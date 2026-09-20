"""ファイル読み込み。

対応形式:
  - .txt（複数ファイル、zip、フォルダのパス）
  - .pdf（論文など。文字の取り出しと、行末ハイフン・改行の整形）
  - CSV / Excel（1行 = 1文書。本文列とグループ列を利用者が選ぶ）

文字コードは UTF-8(BOM) → UTF-8 → CP932 → EUC-JP の順に試し、
最後の手段として chardet に頼る。
"""
from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from corpus.models import Document

TEXT_EXTENSIONS = (".txt", ".pdf")

_TRY_ORDER = ["utf-8", "cp932", "euc_jp"]
_BOM = b"\xef\xbb\xbf"


@dataclass
class DecodedText:
    text: str
    encoding: str


def decode_bytes(data: bytes) -> DecodedText:
    if data.startswith(_BOM):
        return DecodedText(text=data[len(_BOM):].decode("utf-8", errors="replace"), encoding="utf-8-sig")
    for enc in _TRY_ORDER:
        try:
            return DecodedText(text=data.decode(enc), encoding=enc)
        except UnicodeDecodeError:
            continue
    try:
        import chardet

        guess = chardet.detect(data)
        enc = guess.get("encoding") or "utf-8"
        return DecodedText(text=data.decode(enc, errors="replace"), encoding=f"{enc}（推定）")
    except Exception:
        return DecodedText(text=data.decode("utf-8", errors="replace"), encoding="utf-8（強制）")


def read_txt_bytes(name: str, data: bytes) -> tuple[str, str, str]:
    """(文書名, 本文, 文字コード) を返す。"""
    d = decode_bytes(data)
    stem = name.rsplit(".", 1)[0] if "." in name else name
    return stem, d.text, d.encoding


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------
_JA_CHARS = re.compile(r"[぀-ヿ一-鿿]")
_PAGE_NUMBER_LINE = re.compile(r"^\s*(?:[-–—]\s*)?\d{1,4}(?:\s*[-–—])?\s*$")


def clean_pdf_text(text: str) -> str:
    """PDF から取り出した文字列を、分析しやすい形に整える。

    - ページ番号だけの行を落とす
    - 欧文: 行末の「-」で分かれた単語をつなぐ（"Sprach-\\nwissenschaft" → "Sprachwissenschaft"）
    - 段落内の改行を、日本語なら詰めて、欧文なら空白にして1行にする
    - 空行（段落の区切り）は残す
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n\n")
    lines = [ln for ln in text.split("\n") if not _PAGE_NUMBER_LINE.match(ln)]
    text = "\n".join(ln.rstrip() for ln in lines)
    # 3つ以上の連続改行は段落区切り1つに
    text = re.sub(r"\n{3,}", "\n\n", text)
    paragraphs = []
    for para in text.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        is_ja = len(_JA_CHARS.findall(para)) > len(para) * 0.05
        if is_ja:
            para = re.sub(r"\n+", "", para)
        else:
            # 行末ハイフンによる分綴をつなぐ（次行が小文字で始まる場合のみ。固有名詞の複合 "Nord-\nOst" は保つ）
            para = re.sub(r"-\n(?=[a-zäöüßàâçéèêëîïôûùüÿ])", "", para)
            para = re.sub(r"\n+", " ", para)
            para = re.sub(r"[ \t]{2,}", " ", para)
        paragraphs.append(para)
    return "\n\n".join(paragraphs)


def read_pdf_bytes(name: str, data: bytes) -> tuple[str, str, str]:
    """(文書名, 本文, 種別) を返す。文字が取り出せない（画像のみの）PDF は本文が空になる。"""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001 - 壊れたページは飛ばす
            pages.append("")
    text = clean_pdf_text("\n\n".join(pages))
    stem = name.rsplit(".", 1)[0] if "." in name else name
    return stem, text, f"PDF（{len(reader.pages)} ページ）"


def read_text_file_bytes(name: str, data: bytes) -> tuple[str, str, str]:
    """拡張子で .txt / .pdf を振り分ける。"""
    if name.lower().endswith(".pdf"):
        return read_pdf_bytes(name, data)
    return read_txt_bytes(name, data)


# ---------------------------------------------------------------------------
# zip / フォルダ
# ---------------------------------------------------------------------------
def read_zip_txt(data: bytes) -> list[tuple[str, str, str]]:
    """zip 内の .txt / .pdf をすべて読む。(名前, 本文, 文字コード) のリスト。"""
    out = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in sorted(zf.infolist(), key=lambda i: i.filename):
            if info.is_dir() or not info.filename.lower().endswith(TEXT_EXTENSIONS):
                continue
            if "__MACOSX" in info.filename:
                continue
            name = Path(info.filename).name
            out.append(read_text_file_bytes(name, zf.read(info)))
    return out


def read_folder_txt(folder: str | Path, recursive: bool = True) -> list[tuple[str, str, str]]:
    p = Path(folder)
    if not p.is_dir():
        raise FileNotFoundError(f"フォルダが見つかりません: {folder}")
    files = sorted(f for f in (p.rglob("*") if recursive else p.glob("*")) if f.is_file() and f.suffix.lower() in TEXT_EXTENSIONS)
    return [read_text_file_bytes(f.name, f.read_bytes()) for f in files]


# ---------------------------------------------------------------------------
# CSV / Excel
# ---------------------------------------------------------------------------
def read_table(name: str, data: bytes) -> pd.DataFrame:
    """CSV / TSV / Excel をそのまま DataFrame にする（列の解釈は UI 側）。"""
    lower = name.lower()
    if lower.endswith((".xlsx", ".xlsm", ".xls")):
        return pd.read_excel(io.BytesIO(data), dtype=str)
    d = decode_bytes(data)
    sep = "\t" if lower.endswith(".tsv") else None
    return pd.read_csv(io.StringIO(d.text), sep=sep, engine="python", dtype=str)


def guess_text_column(df: pd.DataFrame) -> str | None:
    """本文らしい列（平均文字数が最も長い文字列列）を提案する。"""
    best, best_len = None, -1.0
    for c in df.columns:
        s = df[c].dropna().astype(str)
        if s.empty:
            continue
        m = float(s.str.len().mean())
        if m > best_len:
            best, best_len = c, m
    return best


def guess_group_columns(df: pd.DataFrame, text_col: str | None, max_unique: int = 50) -> list[str]:
    """グループ列らしい列（異なり値が少ない列）を提案する。"""
    out = []
    for c in df.columns:
        if c == text_col:
            continue
        n = df[c].nunique(dropna=True)
        if 1 < n <= max_unique and n < len(df):
            out.append(c)
    return out


def table_to_documents(df: pd.DataFrame, text_col: str, group_cols: list[str],
                       name_col: str | None = None) -> list[Document]:
    docs: list[Document] = []
    for i, row in enumerate(df.itertuples(index=False)):
        r = row._asdict() if hasattr(row, "_asdict") else dict(zip(df.columns, row))
        text = r.get(text_col)
        if text is None or (isinstance(text, float) and pd.isna(text)):
            text = ""
        meta: dict[str, Any] = {}
        for g in group_cols:
            v = r.get(g)
            meta[g] = "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)
        name = str(r.get(name_col)) if name_col and r.get(name_col) is not None else f"行{i + 1}"
        docs.append(Document(doc_id=i, name=name, text=str(text), meta=meta))
    return docs
