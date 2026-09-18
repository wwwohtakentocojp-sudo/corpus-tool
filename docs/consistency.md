# 用語辞書（glossary.yaml）と判定ルール（rules.py）の対応表

作成日: 2026-09-18（Phase 2 完了時点、コミット 8740d20）
目的: 辞書に書かれた注意と、実装されたフラグの条件がずれていないかの棚卸し。
この文書は現状の記録であり、修正は行っていない。

凡例（実装状況）
- **実装済み**: 辞書の注意に対応するフラグがあり、条件も辞書の記述と一致する
- **未実装**: フラグが無く、辞書（または画面の常時表示）にしか書かれていない
- **条件が辞書と異なる**: フラグはあるが、条件が辞書の記述と一致しない（差異を記述）
- **フラグ対象外**: 数値の判定ではない注意（前処理の設定・書き方の注意など）。参考として記載

---

## 表1: 用語辞書の caution → 対応するフラグ

### 頻度に関する指標

| 指標 | caution の要点 | 対応するフラグ | 実装状況 |
|---|---|---|---|
| frequency | 大きさの違うデータ同士を生の回数で比べない。pmw を使う | （なし） | 未実装。行単位の判定ではなく、比較の仕方の注意。画面では pmw を常に併記することで代替 |
| frequency | 出現回数が **5回未満** の語について主張しない | LOW_FREQUENCY | 実装済み（`freq < low_freq`、low_freq = 5） |
| pmw | 元の出現回数が **一桁** なら pmw の値を信用しない | LOW_FREQUENCY（部分的） | **条件が辞書と異なる**。辞書は「一桁（9回以下）」、実装は LOW_FREQUENCY の 5回未満のみ。5〜9回の語は pmw が大きく見えても注意が出ない |
| pmw | 元の出現回数も一緒に確認する | （なし） | 未実装（表に freq 列を常に並べることで代替） |
| dispersion_dp | 出現回数が多いのに散らばりが悪い語を「よく使われる語」と呼ばない | DISPERSION_SKEWED | 実装済み（趣旨） |
| dispersion_dp | DP が **0.5 を超えた** 語は、どの文書に出ているか確認する | DISPERSION_SKEWED | **条件が辞書と異なる**。辞書は「DP > 0.5」のみ。実装は「DP > 0.5 **かつ** freq ≥ dp_min_freq(10) **かつ** 文書数 ≥ dp_min_parts(10)」。後2つの条件は辞書に書かれていない |
| dispersion_dp | （辞書に記述なし） | DP_TOO_FEW_PARTS | 辞書に該当する記述が無い。文書数が少ないと DP が信頼できないことは辞書のどこにも書かれていない |
| ttr | 長さの違う文章を TTR で比べない。標準化TTR を使う | （なし） | 未実装（フラグではなく、基本統計画面で caution を常時表示。文書長の差が大きいときに限って出す判定は無い） |
| ttr_standardized | 区切り幅（既定 1000語）を論文に明記する | （なし） | フラグ対象外（書き方の注意） |
| ttr_standardized | 1000語に満たない文書は計算できず、その旨を表示する | （なし） | 実装済みだがフラグではない（画面の注記で「—」の説明を出す） |

### 共起（コロケーション）に関する指標

| 指標 | caution の要点 | 対応するフラグ | 実装状況 |
|---|---|---|---|
| cooccurrence_frequency | 共起頻度だけで結びつきが強いと判断しない。よく使われる語は必ず上位に来る | T_ONLY_FUNCTION_WORD / BOTH_HIGH_FREQUENCY | 実装済み（趣旨。「共起頻度が高いだけ」を直接見るフラグは無いが、上記2つが同じ状況を捉える） |
| cooccurrence_frequency | （what の記述）「既定では前後5語以内」 | — | **辞書の記述が実装と異なる**。日本語・ドイツ語の既定は「同一文内」、英語のみ「前後5語」。辞書は固定ウィンドウ前提で書かれている |
| mi_score | 出現回数が少ない語を過大評価する | LOW_COOCCURRENCE | 実装済み（趣旨） |
| mi_score | 共起 **20回未満** の組み合わせは、MI が高くても用例を全て確認する | LOW_COOCCURRENCE（段階A） | **条件が辞書と異なる（意図的）**。辞書は回数のみの条件。実装は「回数 < 20 **かつ** logDice・MI・G² のいずれかが目安以上」で強い警告。どれも目安未満なら段階B（表の注意列に「回数少」のみ、用例確認は促さない）。段階分けは 2026-09-18 の指示による |
| mi_score | よく使われる語同士では MI が低く出る。MI が低い = 重要でない、ではない | （なし） | 未実装（情報。フラグ化の必要性は低い） |
| mi_score | （range）0 前後が偶然と同じ、**3以上で結びつきあり、5以上で強い** | mi_meaningful(3.0) / mi_high(5.0) | 実装済み（水準判定と mi_note に使用）。数値は二重記載（後述） |
| t_score | よく使われる語を過大評価する。機能語が上位に来たら除外するか読み飛ばす | T_ONLY_FUNCTION_WORD / FUNCTION_WORD_NOISE | **条件が辞書と異なる**。T_ONLY_FUNCTION_WORD は「t > 2 かつ MI < 3」で、機能語かどうかは見ていない（内容語でも立つ）。FUNCTION_WORD_NOISE は機能語を見るが、機能語除外の設定では該当行が表から消えるため、**実質的に一度も表示されない**（下記「発見事項」参照） |
| t_score | （range）絶対値 **2以上** で意味のある組み合わせ | t_high(2.0) | 実装済み。数値は二重記載 |
| log_dice | 迷ったらまず logDice を見る | （なし） | フラグ対象外。表の初期ソートを logDice 降順にして対応 |
| log_dice | 両方とも非常によく使われる語どうしでは logDice も高く出る。両方の出現回数が **際立って多い** 場合は発見として扱わない | BOTH_HIGH_FREQUENCY | 実装済み。辞書の「際立って多い」を実装では「異なり語の頻度上位 1%（high_freq_top_ratio）」と定義。辞書には 1% という基準は書かれていない |
| log_dice | 万能ではない。最終的に KWIC で用例を確認する | （なし） | フラグ対象外（コロケーション画面の各行に KWIC ボタン） |
| log_dice | （range）**7以上** で結びつきが強い | log_dice_strong(7.0) | 実装済み。数値は二重記載 |
| log_likelihood | データが大きいほどほぼ全ての語で大きくなる。「差があるか」だけに使い、大きさは log ratio で見る | EFFECT_SIZE_TOO_SMALL（特徴語のみ） | 実装済み（趣旨。特徴語画面）。コロケーション画面には「G² が大きいだけ」を注意するフラグは無い |
| log_likelihood | G² が小さいことは「差がない」証明ではなく「判断がつかない」 | NOT_DISTINGUISHABLE | **条件が辞書と異なる（適用範囲）**。コロケーションでは実装済み（G² < 6.63）。特徴語画面では G² < min_g2(6.63) の語を **足切りで表から外す** ため、この注意が当てはまる語は利用者に見えず、フラグも立たない |
| log_likelihood | （range）**6.63 以上で p<0.01、10.83 以上で p<0.001** | g2_significant(6.63) / keyness.min_g2(6.63) | 実装済み。数値は三重記載（後述） |

### 2群比較に関する指標

| 指標 | caution の要点 | 対応するフラグ | 実装状況 |
|---|---|---|---|
| p_value | 大きなデータではほぼ全て小さくなる。p値だけで判断しない | EFFECT_SIZE_TOO_SMALL | 実装済み（趣旨。特徴語画面の常時バナーでも表示） |
| p_value | 「p < 0.05 なら有意」は慣習 | （なし） | フラグ対象外。0.05 は config に無く、辞書にのみ記載 |
| p_value | p値が大きいことは「差がない」証明ではない | NOT_DISTINGUISHABLE（コロケーションのみ） | log_likelihood と同じ。特徴語画面では足切りにより該当語が見えない |
| log_ratio | 本当に見るべきは p値ではなくこれ | （なし） | フラグ対象外（特徴語画面の常時バナー、表の初期ソート） |
| log_ratio | 絶対値が **1未満（2倍未満）** の差は発見として扱わない | EFFECT_SIZE_TOO_SMALL | 実装済み（`abs(log_ratio) < log_ratio_min`、1.0）。数値は二重記載 |
| log_ratio | 片方の群で 0 回だと補正値が使われ、その旨が表示される | ZERO_CORRECTED | 実装済み |
| odds_ratio | log ratio と同じ内容。どちらか片方を報告 | （なし） | フラグ対象外 |
| odds_ratio | 片方の出現回数が 0 だと計算できない | ZERO_CORRECTED | 実装済み（0 補正時は算出せず「片方が0回のため算出しません」と表示） |

### 多変量解析に関する指標（Phase 3 で実装予定）

| 指標 | caution の要点 | 対応するフラグ | 実装状況 |
|---|---|---|---|
| correspondence_axis | 軸に決まった意味は無い。近い = 関係あり、であって因果ではない | （なし） | 未実装（Phase 3。フラグ対象外の見込み） |
| correspondence_axis | 寄与率の合計が **50% を下回る** 場合は解釈に慎重に | （なし） | **未実装**（Phase 3 でフラグ化が必要。閾値 50% は config に無い） |
| network_centrality | 中心にあること = 重要、ではない。機能語や意味の広い語が中心に来る | （なし） | 未実装（ネットワーク画面で caution の先頭段落を常時表示して代替） |
| network_centrality | 設定次第で見た目が変わる。設定値を明記する | （なし） | フラグ対象外（画面に設定値を表示） |

### 言語処理に関する用語（フラグ対象外。参考）

| 指標 | caution の要点 | 対応する仕組み |
|---|---|---|
| token_type | 両方を報告する | 読み込み画面・基本統計で両方表示 |
| lemma | まとめるかどうかで結果が変わる。ドイツ語は手法差がある | 集計単位の切替、ドイツ語 lemma_mode（both で差異一覧） |
| lemma_key | 表示名が同じ行は別の語 | 頻度画面の注記と「集計キーを表示」 |
| function_words | 文体・文法研究では機能語を含める | サイドバーのトグル |
| short_long_unit | UniDic 短単位で集計と明記 | 日本語の language_warnings |
| compound_splitting | 両方の集計を表示 | ドイツ語の2タブ集計 |
| separable_verbs | 既定で再結合、OFF 可 | ドイツ語の設定と language_warnings |

---

## 表2: フラグ → 発火条件と根拠

| フラグ名 | 発火条件（閾値含む） | config.yaml のキー名 | 対応する辞書の記述 | 表示先 |
|---|---|---|---|---|
| CORPUS_TOO_SMALL | 総語数 < 10,000 | corpus_min_tokens | **なし**（辞書に「データ量が少ないと特徴語・共起は信用できない」という記述は無い） | 読み込み画面のバナー。解説本文には出ない（explainer に文言はあるが、渡す画面が無い） |
| GROUP_IMBALANCE | 文書数の最大/最小 > 3.0 | group_imbalance_ratio | **なし** | 読み込み画面・特徴語画面のバナー、特徴語の解説本文 |
| DP_TOO_FEW_PARTS | 分割数（文書数またはグループ数） < 10 | dp_min_parts | **なし** | 頻度画面のバナー（1件のみ）、解説本文。立っている間は DISPERSION_SKEWED を抑止 |
| DISPERSION_SKEWED | DP > 0.5 かつ freq ≥ 10 かつ DP_TOO_FEW_PARTS が立っていない | dp_skew, dp_min_freq（＋ dp_min_parts） | dispersion_dp の caution（DP > 0.5 のみ） | 頻度画面の注意列「⚠ 偏り」、バナー（上位10語）、解説本文 |
| LOW_FREQUENCY | freq < 5 | low_freq | frequency の caution（5回未満） | 頻度画面の注意列「△ 低頻度」、解説本文 |
| LOW_COOCCURRENCE | 共起 < 20 かつ（logDice ≥ 7.0 または MI ≥ 3.0 または G² ≥ 6.63）。MI > 5.0 なら追記文 | low_cooccur_threshold, log_dice_strong, mi_meaningful, g2_significant, mi_high | mi_score の caution（20回未満は用例確認） | コロケーション画面の注意列「⚠ 回数少・要用例」、バナー（KWIC ボタン付き）、解説本文 |
| LOW_COOCCURRENCE_MINOR | 共起 < 20 で、上に該当しない | low_cooccur_threshold（＋上記3閾値） | **なし**（辞書は回数のみで用例確認を求めるので、段階B は辞書より弱い） | コロケーション画面の注意列「回数少」のみ。解説には出ない |
| NOT_DISTINGUISHABLE | G² < 6.63 | g2_significant | log_likelihood / p_value の caution（小さい = 差がない証明ではない） | コロケーション画面の注意列「？ 判断つかず」、解説本文。特徴語画面には適用されない |
| BOTH_HIGH_FREQUENCY | 中心語と共起語の頻度がともに異なり語の上位 1% 以内 | high_freq_top_ratio | log_dice の caution（際立って多い場合） | コロケーション画面の注意列「△ 双方が高頻度」、展開欄、解説本文 |
| T_ONLY_FUNCTION_WORD | t > 2.0 かつ MI < 3.0 | t_high, mi_low | t_score の caution（趣旨） | コロケーション画面の注意列「△ 高頻度語」、展開欄、解説本文 |
| FUNCTION_WORD_NOISE | 共起語が機能語 かつ 機能語を含めない設定 | （閾値なし） | t_score / function_words の caution | **実質なし**。条件を満たす行は表示前に除外されるため、注意列にも解説にも現れない |
| EFFECT_SIZE_TOO_SMALL | \|log ratio\| < 1.0 | log_ratio_min | log_ratio の caution（絶対値1未満） | 特徴語画面の注意列「△ 差が小さい」、件数の注記、解説本文 |
| ZERO_CORRECTED | 片方の群で出現 0 回（0.5 補正） | （閾値なし。補正量 0.5 はコード内固定） | log_ratio / odds_ratio の caution | 特徴語画面の注意列「（0 補正）」、解説本文 |

---

## 発見事項

### A. 「未実装」または「条件が辞書と異なる」の一覧と、どちらを正とすべきかの提案

| # | 項目 | 差異 | 提案 |
|---|---|---|---|
| A1 | pmw: 元の回数が一桁なら信用しない | 辞書は 9回以下、実装（LOW_FREQUENCY）は 5回未満 | **辞書を実装に合わせる**。閾値を2つ持つと利用者が混乱する。「出現回数が 5回未満」に統一し、pmw の caution も「元の出現回数が少ない（目安 5回未満）」と書き換える。別案として pmw 専用フラグ（freq < 10）を足す手もあるが、LOW_FREQUENCY と重なるので推奨しない |
| A2 | dispersion_dp: DP > 0.5 の条件 | 実装は freq ≥ 10 と文書数 ≥ 10 を追加条件にしている | **実装を正とし、辞書に追記する**。両条件とも DP 警告の氾濫（111件）を防ぐために意図して入れたもの。辞書の caution に「出現回数が 10回未満の語や、文書数が 10 未満のデータでは判定しない」旨を書く |
| A3 | dispersion_dp: 文書数が少ないと DP が信頼できない | DP_TOO_FEW_PARTS があるが辞書に記述が無い | **辞書に追記する**（A2 と同じ箇所） |
| A4 | mi_score: 20回未満は用例確認 | 辞書は回数のみ、実装は段階A/B | **実装を正とし、辞書に追記する**。段階分けはユーザー指示。caution に「指標が目安を超えているのに回数が少ない組み合わせには強い警告を出す。回数が少なく指標も低い組み合わせは表に印だけ付ける」旨を書く |
| A5 | t_score: 機能語が上位に来たら除外 | T_ONLY_FUNCTION_WORD は機能語かどうかを見ない。FUNCTION_WORD_NOISE は表示されない | **2点に分けて判断**。(1) T_ONLY_FUNCTION_WORD の名称が実態（「t が高く MI が低い」）と合っていない。名称を T_HIGH_MI_LOW などに改め、文言も「機能語」と限定しない形にするのが正確。(2) FUNCTION_WORD_NOISE は現状デッドコード。機能語を含める設定のときは立たず、除外設定のときは行が消えるため、いつ立っても表示されない。削除するか、「機能語を含める設定で機能語の行を選んだとき」に出す情報フラグに条件を変えるか、いずれか |
| A6 | cooccurrence_frequency の what:「既定では前後5語以内」 | 日本語・ドイツ語の既定は同一文内 | **辞書を実装に合わせる**。「調べたい語と同じ範囲（既定は日本語・ドイツ語では同一文内、英語では前後5語）に」と書き換える |
| A7 | log_dice: 「際立って多い」 | 実装は上位 1% | **辞書に基準を追記する**。「目安として、異なり語の上位 1% に入る語」と書けば、利用者が注意列の意味を辞書で確認できる |
| A8 | log_likelihood / p_value: 小さい = 判断がつかない（特徴語画面） | 特徴語画面は G² < 6.63 を足切りで非表示。フラグは立たず、利用者は「消えた語がある」ことに気づけない | **実装を補う**。足切りで外した語数を画面に表示し、「これらは差がないのではなく、判断がつかない語」と注記する。フラグ化（表に残して NOT_DISTINGUISHABLE を付ける）も可能だが、行数が増えるため注記のほうが読みやすい |
| A9 | correspondence_axis: 寄与率合計 50% 未満 | 未実装（Phase 3） | Phase 3 でフラグ化する。閾値 ca_min_inertia: 0.5 を config に置く |
| A10 | ttr: 長さの違う文書を比べない | 常時表示のみ。文書長の差が大きいときに限って出す判定は無い | **現状維持でよい**。TTR は常に注意が要る指標なので常時表示が適切。ただし基本統計画面の文書ごとの表に、最長/最短の語数比が大きい（例: 3倍超）ときだけ「この表の TTR 列は比較に使えません」と出す判定を足す案はある。優先度は低い |
| A11 | CORPUS_TOO_SMALL / GROUP_IMBALANCE / DP_TOO_FEW_PARTS / LOW_COOCCURRENCE_MINOR | フラグはあるが辞書に対応する記述が無い | **辞書に追記する**。前者2つは「データ量」に関する項目を辞書に新設する（現在の辞書は指標ごとの構成で、データ量の項目が無い）。DP_TOO_FEW_PARTS は A3。LOW_COOCCURRENCE_MINOR は A4 |
| A12 | CORPUS_TOO_SMALL の解説本文 | explainer に文言はあるが、どの画面も渡していない | 現状は読み込み画面のバナーのみで十分。explainer 側の文言は未使用なので、削除するか、将来「データ全体の読み方」を出す画面ができたときに使う |

### B. 閾値が config.yaml と本文で二重に書かれている箇所

片方だけ変更されるとずれる。数値を文言に埋め込んでいる箇所を列挙する。

| 数値 | config.yaml | 本文に埋め込まれている場所 |
|---|---|---|
| 5（低頻度） | thresholds.low_freq | glossary frequency.caution「5回未満」 |
| 0.5（DP） | thresholds.dp_skew | glossary dispersion_dp.caution「0.5 を超えた」、同 range「0.5 を超えたら」 |
| 10（DP の最低文書数） | thresholds.dp_min_parts | explainer NEXT_STEPS「文書数が 10 以上になってから」 |
| 20（共起回数） | thresholds.low_cooccur_threshold | glossary mi_score.caution「20回未満」 |
| 3 / 5（MI の水準） | thresholds.mi_meaningful / mi_high | glossary mi_score.range「3以上で結びつきあり、5以上で強い」 |
| 3（MI 低） | thresholds.mi_low | （mi_meaningful と同じ値だが別キー。用途が違うため2キーになっている） |
| 2（Tスコア） | thresholds.t_high | glossary t_score.range「絶対値が2以上」 |
| 7（logDice） | thresholds.log_dice_strong、network.min_log_dice | glossary log_dice.range「7以上」 |
| 6.63（G²） | thresholds.g2_significant、keyness.min_g2 | glossary log_likelihood.range「6.63以上でp<0.01」、特徴語画面の help 文「6.63 は p<0.01」 |
| 1（log ratio） | thresholds.log_ratio_min | glossary log_ratio.caution「絶対値が1未満」、同 range「絶対値1以上」、explainer JUDGMENTS「目安の 1（2倍）」、explainer NEXT_STEPS「絶対値が 1 以上」、explainer 水準文「目安の 1（2倍）以上」、特徴語画面の常時バナー「目安は絶対値 1 以上」 |
| 1000（標準化TTR の区切り） | basic_stats.sttr_window | glossary ttr_standardized.what / caution「1000語」（3箇所） |
| 5（固定ウィンドウ） | collocation.default_window、kwic.default_window | glossary cooccurrence_frequency.what「前後5語以内」 |
| 0.05（p値） | （config に無い） | glossary p_value.caution / range |
| 50%（対応分析の寄与率） | （config に無い） | glossary correspondence_axis.caution |
| 0.5（0 補正の加算量） | （config に無い。コード内固定） | glossary log_ratio.caution は「補正した値」とだけ記述。flags.py / explainer.py の文言に「0.5」を埋め込み |

同じ役割の閾値が config 内で2キーに分かれている箇所も2つある。
- thresholds.log_dice_strong と network.min_log_dice（どちらも 7.0）
- thresholds.g2_significant と keyness.min_g2（どちらも 6.63）

対処案としては、(1) glossary.yaml の本文から数値を除いて「目安の値は画面の注意列や設定ファイル参照」とする、(2) explainer と glossary の本文を config の値で埋めるテンプレートにする、の2つがある。(2) のほうが利用者に数値が見えて親切だが、辞書が「固定テキスト」でなくなる。判断をお願いしたい。
