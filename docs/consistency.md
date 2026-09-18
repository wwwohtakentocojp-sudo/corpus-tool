# 用語辞書（glossary.yaml）と判定ルール（rules.py）の対応表

最終更新: 2026-09-18（整合性修正後。Phase 3 着手前）
目的: 辞書に書かれた注意と、実装されたフラグの条件がずれていないかの棚卸しと、その修正記録。

凡例（実装状況）
- **実装済み**: 辞書の注意に対応するフラグがあり、条件も辞書の記述と一致する
- **未実装**: フラグが無く、辞書（または画面の常時表示）にしか書かれていない
- **フラグ対象外**: 数値の判定ではない注意（前処理の設定・書き方の注意など）。参考として記載
- 「条件が辞書と異なる」項目は、今回の修正で全て解消した（末尾の修正記録を参照）

---

## 数値の扱い（テンプレート方式）

閾値の数値は glossary.yaml と explainer.py の本文に直接書かず、`{変数名}` で書く。
値は config.yaml から埋める（`interpretations/glossary.py` の `template_variables`）。
config に無い変数を参照すると、起動時（`app.py` の `glossary.load_glossary()`）に
`GlossaryTemplateError` で止まる。全変数が解決されることは `tests/test_glossary.py` で検証している。
使える変数の一覧は glossary.yaml の先頭コメントにある。

同じ役割で2キーに分かれていた閾値は1キーに統合した。
- `network.min_log_dice` → `thresholds.log_dice_strong`
- `keyness.min_g2` → `thresholds.g2_significant`

本文に直接書いてよい数値（config の閾値ではないもの）:
10.83（p<0.001 相当の統計定数）、0.05（p値の慣習）、0.5（0 補正の加算量。コード内固定）、
50%（対応分析の寄与率。Phase 3 で config 化予定）。

---

## 表1: 用語辞書の caution → 対応するフラグ

### データ量（新設）

| 指標 | caution の要点 | 対応するフラグ | 実装状況 |
|---|---|---|---|
| data_size | 総語数が {corpus_min_tokens} 語未満では特徴語・共起は信用できない | CORPUS_TOO_SMALL | 実装済み |
| data_size | 文書数比が {group_imbalance_ratio} 倍超なら偏り | GROUP_IMBALANCE | 実装済み |
| data_size | 文書数 {dp_min_parts} 未満では DP の判定は信頼できない | DP_TOO_FEW_PARTS | 実装済み |

### 頻度に関する指標

| 指標 | caution の要点 | 対応するフラグ | 実装状況 |
|---|---|---|---|
| frequency | 大きさの違うデータ同士を生の回数で比べない。pmw を使う | （なし） | 未実装。行単位の判定ではなく比較の仕方の注意。pmw を常に併記して代替 |
| frequency | 出現回数が {low_freq} 回未満の語について主張しない | LOW_FREQUENCY | 実装済み |
| pmw | 元の出現回数が {low_freq} 回未満なら pmw を信用しない | LOW_FREQUENCY | 実装済み（A1: 辞書を「一桁」から {low_freq} に修正） |
| dispersion_dp | DP が {dp_skew} を超えた語は、どの文書に出ているか確認する。ただし回数 {dp_min_freq} 未満の語と文書数 {dp_min_parts} 未満のデータでは判定しない | DISPERSION_SKEWED / DP_TOO_FEW_PARTS | 実装済み（A2, A3: 辞書に追加条件を追記） |
| ttr | 長さの違う文章を TTR で比べない | （なし） | 未実装（常時表示で代替。A10: 現状維持） |
| ttr_standardized | 区切り幅（{sttr_window} 語）を論文に明記 | （なし） | フラグ対象外 |
| ttr_standardized | {sttr_window} 語に満たない文書は計算できず、その旨を表示 | （なし） | 実装済みだがフラグではない（画面の注記） |

### 共起（コロケーション）に関する指標

| 指標 | caution の要点 | 対応するフラグ | 実装状況 |
|---|---|---|---|
| cooccurrence_frequency | （what）範囲は設定で選ぶ。日本語・ドイツ語は同一文内、英語は前後 {default_window} 語が既定 | — | 実装と一致（A6: 辞書を修正） |
| cooccurrence_frequency | 共起頻度だけで判断しない。よく使われる語は必ず上位に来る | T_HIGH_MI_LOW / BOTH_HIGH_FREQUENCY | 実装済み（趣旨） |
| mi_score | 共起 {low_cooccur_threshold} 回未満は用例を全て確認。指標が目安を超えている組は強い警告、超えていない組は表の印だけ | LOW_COOCCURRENCE / LOW_COOCCURRENCE_MINOR | 実装済み（A4: 段階の説明を辞書に追記） |
| mi_score | よく使われる語同士では MI が低く出る。低い = 重要でない、ではない | （なし） | 未実装（情報。フラグ化の必要性は低い） |
| mi_score | （range）{mi_meaningful} 以上で結びつきあり、{mi_high} 以上で強い | mi_meaningful / mi_high | 実装済み（水準判定と mi_note） |
| t_score | Tスコア > {t_high} かつ MI < {mi_low} の組に「よく使われる語が隣にあるだけ」の印。機能語に限らず意味の広い内容語でも起こる | T_HIGH_MI_LOW | 実装済み（A5: 旧 T_ONLY_FUNCTION_WORD を改名し、辞書の「機能語が上位に来たら」を書き直し。FUNCTION_WORD_NOISE は削除） |
| log_dice | 迷ったらまず logDice を見る | （なし） | フラグ対象外。表の初期ソートで対応 |
| log_dice | 両方が異なり語の頻度上位 {high_freq_top_percent}% なら発見として扱わない | BOTH_HIGH_FREQUENCY | 実装済み（A7: 辞書に基準を追記） |
| log_dice | 最終的に KWIC で用例を確認 | （なし） | フラグ対象外（各行に KWIC ボタン） |
| log_likelihood | データが大きいほど大きくなる。「差があるか」だけに使い、大きさは log ratio で見る | EFFECT_SIZE_TOO_SMALL（特徴語） | 実装済み（趣旨） |
| log_likelihood | G² < {g2_significant} は「差がない」証明ではなく「判断がつかない」。特徴語画面では既定で非表示だが件数を常時表示し、表示に切り替えられる | NOT_DISTINGUISHABLE（コロケーション・特徴語） | 実装済み（A8: 特徴語画面の足切りを設定化し、非表示件数を常時表示。表示時は行にフラグ） |

### 2群比較に関する指標

| 指標 | caution の要点 | 対応するフラグ | 実装状況 |
|---|---|---|---|
| p_value | 大きなデータではほぼ全て小さくなる。p値だけで判断しない | EFFECT_SIZE_TOO_SMALL | 実装済み（趣旨。特徴語画面の常時バナー） |
| p_value | 「p < 0.05 なら有意」は慣習 | （なし） | フラグ対象外 |
| p_value | p値が大きいことは「差がない」証明ではない | NOT_DISTINGUISHABLE | 実装済み（A8） |
| log_ratio | 本当に見るべきは p値ではなくこれ | （なし） | フラグ対象外（常時バナー、初期ソート） |
| log_ratio | 絶対値 {log_ratio_min} 未満（{log_ratio_times} 倍未満）は発見として扱わない | EFFECT_SIZE_TOO_SMALL | 実装済み |
| log_ratio | 片方の群で 0 回なら 0.5 補正値。「0 補正」と表示 | ZERO_CORRECTED | 実装済み |
| odds_ratio | 片方が 0 なら算出せず「片方が0回のため算出しません」と表示 | ZERO_CORRECTED | 実装済み |

### 多変量解析に関する指標（Phase 3 で実装予定）

| 指標 | caution の要点 | 対応するフラグ | 実装状況 |
|---|---|---|---|
| correspondence_axis | 軸に決まった意味は無い。近い = 関係あり、であって因果ではない | （なし） | 未実装（Phase 3。フラグ対象外の見込み） |
| correspondence_axis | 寄与率の合計が 50% を下回る場合は解釈に慎重に | （Phase 3 で追加） | **未実装**（A9: Phase 3 でフラグ化し、閾値を config に置く） |
| network_centrality | 中心にあること = 重要、ではない | （なし） | 未実装（画面で caution の先頭段落を常時表示） |
| network_centrality | 設定値を明記する | （なし） | フラグ対象外（画面に設定値を表示） |

### 言語処理に関する用語（フラグ対象外。参考）

| 指標 | caution の要点 | 対応する仕組み |
|---|---|---|
| token_type | 両方を報告する | 読み込み画面・基本統計で両方表示 |
| lemma | まとめるかどうかで結果が変わる。ドイツ語は手法差がある | 集計単位の切替、ドイツ語 lemma_mode |
| lemma_key | 表示名が同じ行は別の語 | 頻度画面の注記と「集計キーを表示」 |
| function_words | 文体・文法研究では機能語を含める | サイドバーのトグル |
| short_long_unit | UniDic 短単位で集計と明記 | 日本語の language_warnings |
| compound_splitting | 両方の集計を表示 | ドイツ語の2タブ集計 |
| separable_verbs | 既定で再結合、OFF 可 | ドイツ語の設定と language_warnings |

---

## 表2: フラグ → 発火条件と根拠

| フラグ名 | 発火条件 | config.yaml のキー名 | 対応する辞書の記述 | 表示先 |
|---|---|---|---|---|
| CORPUS_TOO_SMALL | 総語数 < corpus_min_tokens | thresholds.corpus_min_tokens | data_size | 読み込み画面のバナーのみ（A12: explainer の未使用文言は削除） |
| GROUP_IMBALANCE | 文書数の最大/最小 > group_imbalance_ratio | thresholds.group_imbalance_ratio | data_size | 読み込み画面・特徴語画面のバナー、特徴語の解説本文 |
| DP_TOO_FEW_PARTS | 分割数 < dp_min_parts | thresholds.dp_min_parts | data_size, dispersion_dp | 頻度画面のバナー（1件のみ）、解説本文。立っている間は DISPERSION_SKEWED を抑止 |
| DISPERSION_SKEWED | DP > dp_skew かつ freq ≥ dp_min_freq かつ DP_TOO_FEW_PARTS が無い | thresholds.dp_skew, dp_min_freq（＋dp_min_parts） | dispersion_dp | 頻度画面の注意列「⚠ 偏り」、バナー（上位10語）、解説本文 |
| LOW_FREQUENCY | freq < low_freq | thresholds.low_freq | frequency, pmw | 頻度画面の注意列「△ 低頻度」、解説本文 |
| LOW_COOCCURRENCE | 共起 < low_cooccur_threshold かつ（logDice ≥ log_dice_strong または MI ≥ mi_meaningful または G² ≥ g2_significant）。MI > mi_high なら追記文 | thresholds.low_cooccur_threshold, log_dice_strong, mi_meaningful, g2_significant, mi_high | mi_score | コロケーション画面の注意列「⚠ 回数少・要用例」、バナー（KWIC ボタン付き）、解説本文 |
| LOW_COOCCURRENCE_MINOR | 共起 < low_cooccur_threshold で上に該当しない | 同上 | mi_score | コロケーション画面の注意列「回数少」のみ。解説には出ない |
| NOT_DISTINGUISHABLE | G² < g2_significant | thresholds.g2_significant | log_likelihood, p_value | コロケーション画面の注意列「？ 判断つかず」と解説本文。特徴語画面では keyness.hide_not_distinguishable が false のとき注意列と解説本文（true のときは非表示件数を常時表示） |
| BOTH_HIGH_FREQUENCY | 中心語と共起語の頻度がともに異なり語の上位 high_freq_top_ratio 以内 | thresholds.high_freq_top_ratio | log_dice | コロケーション画面の注意列「△ 双方が高頻度」、展開欄、解説本文 |
| T_HIGH_MI_LOW | t > t_high かつ MI < mi_low | thresholds.t_high, mi_low | t_score | コロケーション画面の注意列「△ 高頻度語が隣」、展開欄、解説本文 |
| EFFECT_SIZE_TOO_SMALL | \|log ratio\| < log_ratio_min | thresholds.log_ratio_min | log_ratio, p_value | 特徴語画面の注意列「△ 差が小さい」、件数の注記、解説本文 |
| ZERO_CORRECTED | 片方の群で出現 0 回（0.5 補正） | （閾値なし。0.5 はコード内固定） | log_ratio, odds_ratio | 特徴語画面の注意列「（0 補正）」、解説本文 |

---

## 修正記録（2026-09-18）

| # | 項目 | 対応 |
|---|---|---|
| A1 | pmw の「一桁」 | 辞書を「{low_freq} 回未満」に統一 |
| A2 | DP の追加条件（freq ≥ 10、文書数 ≥ 10） | 辞書に追記 |
| A3 | DP_TOO_FEW_PARTS の辞書記述 | dispersion_dp と data_size に追記 |
| A4 | 共起回数の段階A/B | 辞書に追記 |
| A5 | T_ONLY_FUNCTION_WORD | T_HIGH_MI_LOW に改名。文言から「機能語」限定を外す。FUNCTION_WORD_NOISE は削除（表示前に行が除外されるデッドコードだった）。辞書 t_score の caution を書き直し |
| A6 | 共起頻度の what「前後5語」 | 言語別の既定を記述 |
| A7 | logDice「際立って多い」 | 上位 {high_freq_top_percent}% の基準を追記 |
| A8 | 特徴語の G² 足切り | keyness.hide_not_distinguishable（既定 true）を追加。ON 時は非表示件数と「差がない語ではなく判断がつかない語」を常時表示。OFF 時は該当行に NOT_DISTINGUISHABLE。旧 keyness.min_g2 の数値入力は廃止 |
| A9 | 対応分析の寄与率 50% | Phase 3 で対応 |
| A10 | TTR の常時表示 | 現状維持 |
| A11 | データ量の辞書項目 | data_size を新設し、読み込み画面と特徴語画面の「?」に追加 |
| A12 | CORPUS_TOO_SMALL の未使用文言 | explainer から削除 |
| B | 数値の二重記載 | テンプレート方式に移行。閾値キーを統合（上記「数値の扱い」） |

Phase 3 で対応分析を追加するときは、correspondence_axis の 50% を config の閾値（例: thresholds.ca_min_inertia）に置き換え、この表に行を追加すること。
