# サンプルデータ

## デモ用サンプル（`samples/demo/`。git で追跡する）

公開デモ版と、ローカル版の「サンプルデータで試す」で使う、加工済みのサンプルです。
`scripts/make_demo_samples.py` で `samples/{ja,en,de}/` から生成します。
いずれも著作権切れ、または再配布を許すライセンスのデータです。

### 日本語（`demo/ja/`）: 青空文庫

| ファイル | 作品 | 底本 | 青空文庫での入力・校正 |
|---|---|---|---|
| 夏目漱石_こころ.txt | 夏目漱石『こころ』（初出: 朝日新聞、1914年） | 『こころ』集英社文庫 | 入力 j.utiyama、校正 伊藤時也 |
| 夏目漱石_坊っちゃん.txt | 夏目漱石『坊っちゃん』（1906年） | 『ちくま日本文学全集 夏目漱石』筑摩書房 | 入力 真先芳秋、校正 柳沢成雄 |
| 芥川龍之介_羅生門.txt | 芥川龍之介『羅生門』（初出: 帝国文学、1915年） | 『芥川龍之介全集1』ちくま文庫、筑摩書房 | 入力 平山誠、野口英司 |

- 出典: 青空文庫 https://www.aozora.gr.jp/
- ライセンス: 著作権の消滅した作品。青空文庫の「著作権の切れた作品」として公開されているものを、
  Shift_JIS から UTF-8 に変換し、ルビ（《》）・編集注記（［＃］）・凡例・底本情報を除去して収録。
  改変の内容は上記のとおり。
- 青空文庫の利用について: https://www.aozora.gr.jp/guide/kijyunn.html

### 英語（`demo/en/`）: Project Gutenberg

| ファイル | 作品 | Gutenberg 番号 |
|---|---|---|
| Austen_Pride_and_Prejudice.txt | Jane Austen, *Pride and Prejudice* (1813) | #1342 |
| Carroll_Alice_in_Wonderland.txt | Lewis Carroll, *Alice's Adventures in Wonderland* (1865) | #11 |
| Shelley_Frankenstein.txt | Mary Shelley, *Frankenstein; or, The Modern Prometheus* (1818) | #84 |

- 出典: Project Gutenberg https://www.gutenberg.org/
- ライセンス: 米国で著作権が消滅した作品（パブリックドメイン）。Project Gutenberg のヘッダとフッタ
  （Project Gutenberg License の本文）を除去した本文のみを収録。
  Project Gutenberg の商標は使用していません。詳細: https://www.gutenberg.org/policy/permission.html

### ドイツ語（`demo/de/`）: Leipzig Corpora Collection

| ファイル | 内容 |
|---|---|
| deu_news_2023_1000.txt | コーパス `deu_news_2023_10K`（ドイツ語ニュース、2023年）の文ファイルから先頭 1,000 文。1行1文 |

- 出典: Leipzig Corpora Collection, Universität Leipzig https://wortschatz.uni-leipzig.de/en/download
- ライセンス: CC BY 4.0 https://creativecommons.org/licenses/by/4.0/
- 引用: D. Goldhahn, T. Eckart & U. Quasthoff (2012): *Building Large Monolingual Dictionaries at the
  Leipzig Corpora Collection: From 100 to 200 Languages.* Proceedings of the 8th International Language
  Resources and Evaluation (LREC'12).
- 改変: 文番号の列を除去し、先頭 1,000 文のみを収録。

## ローカル版の完全版サンプル（`samples/ja/`, `samples/en/`, `samples/de/`。git には含めない）

次のスクリプトで取得します。上記と同じ出典から、加工前のファイル（青空文庫は注記付き、
Leipzig は 1 万文と頻度リスト）を保存します。

```
uv run python scripts/download_samples.py
```

Leipzig の頻度リストは、本ツールの頻度集計が桁として妥当かを確かめる基準データです:

```
uv run python scripts/check_leipzig.py
```
