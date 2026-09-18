"""言語の自動判定（初期値の提案にのみ使う。最終的な選択は利用者が行う）。

外部ライブラリを使わず、文字種と頻出語で判定する。
"""
from __future__ import annotations

import re

_JA_CHARS = re.compile(r"[぀-ヿ一-鿿]")
_EN_HINTS = {"the", "and", "of", "to", "is", "in", "that", "it", "with", "for"}
_DE_HINTS = {"der", "die", "und", "das", "ist", "nicht", "ein", "eine", "mit", "sich", "den", "zu"}


def detect_language(text: str) -> str:
    sample = text[:20000]
    if not sample.strip():
        return "ja"
    ja_ratio = len(_JA_CHARS.findall(sample)) / max(1, len(sample))
    if ja_ratio > 0.05:
        return "ja"
    words = re.findall(r"[a-zäöüß]+", sample.lower())
    if not words:
        return "ja"
    en = sum(1 for w in words if w in _EN_HINTS)
    de = sum(1 for w in words if w in _DE_HINTS)
    return "de" if de > en else "en"
