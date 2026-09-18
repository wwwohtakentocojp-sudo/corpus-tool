"""ドイツ語の正書法まわりの正規化と、新旧表記の混在検出。

すべて個別に ON/OFF でき、既定はすべて OFF（通時研究の妨げになるため）。
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

_TABLE_PATH = Path(__file__).resolve().parent / "data" / "orthography_1996.tsv"

_UMLAUT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue"})


@lru_cache(maxsize=1)
def load_1996_table() -> dict[str, str]:
    table: dict[str, str] = {}
    with open(_TABLE_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            old, new = line.split("\t")
            if old != new:
                table[old] = new
    return table


def _with_capitalized(table: dict[str, str]) -> dict[str, str]:
    """小文字始まりの語は、文頭で大文字化された形にも対応する。"""
    out = dict(table)
    for old, new in table.items():
        if old[0].islower():
            out[old[0].upper() + old[1:]] = new[0].upper() + new[1:]
    return out


@lru_cache(maxsize=1)
def _pattern_1996() -> tuple[re.Pattern, dict[str, str]]:
    table = _with_capitalized(load_1996_table())
    # 長い語から先に。単語境界で囲む（ß や ü も \w に含まれる）
    keys = sorted(table.keys(), key=len, reverse=True)
    pat = re.compile(r"(?<!\w)(" + "|".join(re.escape(k) for k in keys) + r")(?!\w)")
    return pat, table


def normalize_1996(text: str) -> str:
    """1996年改革前の表記を新表記に統一する（対応表に基づく）。"""
    pat, table = _pattern_1996()
    return pat.sub(lambda m: table[m.group(1)], text)


def normalize_ss(text: str) -> str:
    """ß → ss（スイス正書法に合わせる）。"""
    return text.replace("ß", "ss").replace("ẞ", "SS")


def normalize_umlaut(text: str) -> str:
    """ä/ö/ü → ae/oe/ue。"""
    return text.translate(_UMLAUT)


def detect_orthography_mix(text: str) -> dict[str, int]:
    """新旧表記の混在を検出する。対応表の旧表記と新表記それぞれの出現回数を返す。"""
    table = _with_capitalized(load_1996_table())
    olds = set(table.keys())
    news = set(table.values())
    words = re.findall(r"[A-Za-zÄÖÜäöüß]+", text)
    n_old = sum(1 for w in words if w in olds)
    n_new = sum(1 for w in words if w in news)
    return {"old": n_old, "new": n_new}


def is_mixed(counts: dict[str, int], min_each: int = 3) -> bool:
    return counts["old"] >= min_each and counts["new"] >= min_each
