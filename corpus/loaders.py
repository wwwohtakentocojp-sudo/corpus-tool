"""ファイル読み込み。Phase 0 は .txt の複数ファイルのみ。

文字コードは UTF-8(BOM) → UTF-8 → CP932 → EUC-JP の順に試し、
最後の手段として chardet に頼る。
"""
from __future__ import annotations

from dataclasses import dataclass

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
