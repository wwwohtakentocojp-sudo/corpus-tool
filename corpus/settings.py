"""分析設定。

全画面で同じ設定オブジェクトを使い回し、Phase 3 の「分析設定の記録ファイル」
（再現性のための YAML）はこれをそのまま書き出す。
言語固有のオプションは language_options に辞書として持ち、
その中身の解釈は analyzers/ 側に任せる（このファイルは言語を知らない）。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import yaml


@dataclass
class AnalysisSettings:
    language: str = "ja"
    # 集計単位: "lemma"（見出し語）か "surface"（表層形）
    unit: str = "lemma"
    # 機能語（助詞・記号など）を集計に含めるか
    include_function_words: bool = False
    # 標準化TTRの区切り幅
    sttr_window: int = 1000
    # KWIC の前後語数
    kwic_window: int = 5
    # 言語固有オプション（analyzers/ が解釈する）
    language_options: dict[str, Any] = field(default_factory=dict)
    # 読み込み時の整形（青空文庫の注記除去など）
    cleaning: dict[str, Any] = field(default_factory=dict)

    def to_yaml(self) -> str:
        return yaml.safe_dump(asdict(self), allow_unicode=True, sort_keys=False)

    @classmethod
    def from_yaml(cls, text: str) -> "AnalysisSettings":
        data = yaml.safe_load(text) or {}
        return cls(**data)

    def tokenization_key(self) -> tuple:
        """トークン化結果のキャッシュキー。集計時の表示オプションは含めない。"""
        return (
            self.language,
            tuple(sorted(self.language_options.items())),
            tuple(sorted(self.cleaning.items())),
        )
