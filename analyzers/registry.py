"""言語コード → 解析器。新しい言語を追加するときはここに1行足すだけにする。"""
from __future__ import annotations

from typing import Any

from analyzers.base import BaseAnalyzer


def _build(code: str, config: dict[str, Any] | None) -> BaseAnalyzer:
    if code == "ja":
        from analyzers.japanese import JapaneseAnalyzer

        return JapaneseAnalyzer(config)
    if code == "en":
        from analyzers.english import EnglishAnalyzer

        return EnglishAnalyzer(config)
    if code == "de":
        from analyzers.german import GermanAnalyzer

        return GermanAnalyzer(config)
    raise KeyError(f"未対応の言語コードです: {code}")


AVAILABLE_LANGUAGES: dict[str, str] = {
    "ja": "日本語",
    "en": "英語",
    "de": "ドイツ語",
}


def get_analyzer(code: str, config: dict[str, Any] | None = None) -> BaseAnalyzer:
    if code not in AVAILABLE_LANGUAGES:
        raise KeyError(f"未対応の言語コードです: {code}")
    return _build(code, config)
