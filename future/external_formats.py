"""【雛形・v1 では未実装】既存コーパスの検索結果エクスポート専用モード。

中納言（BCCWJ 等）・DWDS の検索結果 CSV を、本ツールの Document 列に変換する。
v1 では汎用 CSV 読み込み（列選択方式）で代替する。

実装時の方針:
  - 各フォーマットは detect(df) -> bool と convert(df) -> list[Document] を持つ
  - 列名の対応表は YAML に外出しし、フォーマット改定に追従しやすくする
"""
from __future__ import annotations

import pandas as pd

from corpus.models import Document


class ExternalFormat:
    name: str = ""

    def detect(self, df: pd.DataFrame) -> bool:  # pragma: no cover - 雛形
        raise NotImplementedError

    def convert(self, df: pd.DataFrame) -> list[Document]:  # pragma: no cover - 雛形
        raise NotImplementedError


class ChunagonFormat(ExternalFormat):
    """中納言の検索結果（前文脈・キー・後文脈 形式）。"""
    name = "中納言"


class DWDSFormat(ExternalFormat):
    """DWDS の KWIC エクスポート。"""
    name = "DWDS"


FORMATS: list[ExternalFormat] = [ChunagonFormat(), DWDSFormat()]
