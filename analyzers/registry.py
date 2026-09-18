"""言語コード → 解析器。新しい言語を追加するときはここに1行足すだけにする。"""
from __future__ import annotations

from typing import Any

from analyzers.base import BaseAnalyzer


def _build(code: str, config: dict[str, Any] | None) -> BaseAnalyzer:
    if code == "ja":
        from analyzers.japanese import JapaneseAnalyzer

        return JapaneseAnalyzer(config)
    # Phase 1 で追加: "en" -> EnglishAnalyzer, "de" -> GermanAnalyzer
    raise KeyError(f"未対応の言語コードです: {code}")


AVAILABLE_LANGUAGES: dict[str, str] = {
    "ja": "日本語",
    # "en": "英語",      # Phase 1
    # "de": "ドイツ語",  # Phase 1
}


def get_analyzer(code: str, config: dict[str, Any] | None = None) -> BaseAnalyzer:
    if code not in AVAILABLE_LANGUAGES:
        raise KeyError(f"未対応の言語コードです: {code}")
    return _build(code, config)
