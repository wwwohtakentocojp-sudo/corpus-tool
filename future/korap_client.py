"""【雛形・v1 では未実装】KorAP 経由で DeReKo を検索するクライアント。

注意: DeReKo のデータは再配布禁止。このモジュールを実装する場合も、
取得した用例をローカルに保存する範囲と利用規約の整合を必ず確認すること。
"""
from __future__ import annotations


class KorapClient:
    def __init__(self, base_url: str = "https://korap.ids-mannheim.de", token: str | None = None):
        self.base_url = base_url
        self.token = token

    def search(self, query: str, query_language: str = "poliqarp", count: int = 25):  # pragma: no cover
        raise NotImplementedError("v1 では未実装です")
