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


def tooltip(key: str) -> str:
    """"?" アイコン（help=）用の短い説明。what と caution の先頭部分。"""
    e = entry(key)
    what = str(e.get("what", "")).strip()
    caution = str(e.get("caution", "")).strip()
    text = what
    if caution:
        text += "\n\n注意: " + caution
    return text


def full_text(key: str) -> str:
    """展開表示用: label / what / high / low / caution / range / example を Markdown で。"""
    e = entry(key)
    parts = [f"**{e.get('label', key)}**", ""]
    if e.get("what"):
        parts += ["**何を測っているか**", str(e["what"]).strip(), ""]
    if e.get("high"):
        parts += ["**値が高いとき**", str(e["high"]).strip(), ""]
    if e.get("low"):
        parts += ["**値が低いとき**", str(e["low"]).strip(), ""]
    if e.get("caution"):
        parts += ["**注意（必ず読んでください）**", str(e["caution"]).strip(), ""]
    if e.get("range"):
        parts += ["**値の範囲と目安**", str(e["range"]).strip(), ""]
    if e.get("example"):
        parts += ["**例**", str(e["example"]).strip(), ""]
    return "\n\n".join(p for p in parts if p != "" or True).replace("\n\n\n\n", "\n\n")
