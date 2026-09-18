"""第1層: 用語辞書の読み込みとアクセス。AI は使わない。"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

GLOSSARY_PATH = Path(__file__).resolve().parent / "glossary.yaml"

# 全指標キー（一つも省略しないことを tests で検証する）
REQUIRED_KEYS = [
    "frequency", "pmw", "dispersion_dp", "ttr", "ttr_standardized",
    "mi_score", "t_score", "log_dice", "log_likelihood",
    "p_value", "log_ratio", "odds_ratio",
    "correspondence_axis", "network_centrality",
]


@lru_cache(maxsize=1)
def load_glossary(path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    p = Path(path) if path else GLOSSARY_PATH
    with open(p, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def entry(key: str) -> dict[str, Any]:
    g = load_glossary()
    if key not in g:
        raise KeyError(f"用語辞書に {key} がありません")
    return g[key]


def label(key: str) -> str:
    return str(entry(key).get("label", key))


def join_lines(text: str) -> str:
    """YAML の複数行文字列を1行にする。日本語なので改行は空白を入れずに連結する。
    段落の区切り（空行）は残す。"""
    paras = str(text).strip().split("\n\n")
    return "\n\n".join("".join(line.strip() for line in p.splitlines()) for p in paras)


def caution_head(key: str) -> str:
    """caution の最初の段落を1行で。"""
    return join_lines(entry(key).get("caution", "")).split("\n\n")[0]


def tooltip(key: str) -> str:
    """"?" アイコン（help=）用の短い説明。what と caution の先頭部分。"""
    e = entry(key)
    what = join_lines(e.get("what", ""))
    caution = join_lines(e.get("caution", ""))
    text = what
    if caution:
        text += "\n\n注意: " + caution
    return text


def full_text(key: str) -> str:
    """展開表示用: label / what / high / low / caution / range / example を Markdown で。"""
    e = entry(key)
    parts = [f"**{e.get('label', key)}**"]
    for field, title in (("what", "何を測っているか"), ("high", "値が高いとき"), ("low", "値が低いとき"),
                         ("caution", "注意（必ず読んでください）"), ("range", "値の範囲と目安"), ("example", "例")):
        if e.get(field):
            parts += [f"**{title}**", join_lines(e[field])]
    return "\n\n".join(parts)
