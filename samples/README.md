# サンプルデータ

このフォルダの中身は `scripts/download_samples.py` が自動で用意します（git には含めません）。
公開デモ版では、初回アクセス時に自動で取得されます。

- `ja/` … 青空文庫の著作権切れ作品（UTF-8 に変換済み。ルビや注記は残してあり、読み込み時に除去できます）
- `en/` … Project Gutenberg の著作権切れ作品
- `de/` … Leipzig Corpora Collection のドイツ語ニュース文と頻度リスト（CC BY。統計計算の健全性確認にも使う）

実行方法（プロジェクトのフォルダで）:

```
uv run python scripts/download_samples.py
```
