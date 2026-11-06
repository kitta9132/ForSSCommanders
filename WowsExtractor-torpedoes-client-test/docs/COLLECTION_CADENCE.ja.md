# 現行の収集頻度表

対象：0.3.39-own-torpedo-cadence。標準設定`state_interval=0.2`のcore tickを基準にする。以下はゲームからの採取・計算の目安で、厳密なHzや全遷移捕捉を保証しない。設定によってcoreが遅ければ、各群もそれより速く採取できない。

collectionは既定OFF。専用opt-in／heavy diagnostics／profilerも既定OFFであり、表の周期を記載しただけで有効になるわけではない。[出力契約](OUTPUT_SPEC.ja.md)／[設定](INSTALL.ja.md)を参照。過去の[B31頻度調査](RESEARCH_COLLECTION_CADENCE_B31.ja.md)は現況表ではない。

## 魚雷

| 対象・処理 | 標準周期 | 条件・注意 |
| --- | --- | --- |
| 全魚雷の列挙・最小ID・membership | core、約5Hz | 遠距離非dueでも一覧の識別を観測。完全性／不明IDを別に示す |
| 自艦発射と確認できた魚雷の詳細 | HIGH、目標5Hz | 距離に関係なくhigh。ownerの`isPlayer`が厳密bool Trueである観測を使い、ownerIdのnamespace推測で補わない |
| その他の魚雷・半径L/3以内／境界上 | HIGH、目標5Hz | Lはマップ短辺の較正由来world長。物理kmの保証ではない |
| その他の魚雷・半径L/3より外 | LOW、平均約2Hz | 0.5秒期限をcore tickへ量子化するため約0.4／0.6秒等に変動 |
| 新規・距離判定不能・分類context喪失 | 暫定／安全側HIGH | 所有者不明を自艦と断定する意味ではない |
| 距離による枠再分類 | 約5秒ごと | 自艦例外以外のfar→near昇格は次回分類まで待つ場合がある |
| owner詳細・motion・地図変換 | 各魚雷の今回sampleと同周期 | low非dueでは省略し、前回の位置／owner／派生値を現在値としてコピーしない |
| 魚雷UI深度の専用probe | 既定1Hz・最小間隔1秒 | `torpedo_depth_sampling_enabled`必須。固定候補のraw、意味・単位は未確定 |
| ATM等の誘導／被発見候補probe | 既定1Hz・最小間隔1秒 | `torpedo_state_sampling_enabled`必須。第三者由来値と供給元unknownを区別、最大64候補 |

L/5は記録試算だけで、**現行半径はL/3を維持**する。自艦HIGH例外は情報量削減ではなく、自艦魚雷の遠方詳細取得を増やす変更であり、FPS改善策と呼ばない。所有者不明はunknownを維持し、距離ルールに従う。low非dueでは所有者を再取得せず、後のdue sampleでTrueと確認できた時点でhighへ昇格する。coreを0.1秒にしてもHIGH期限は0.2秒のまま。

## 艦・自艦・診断など

| 情報群 | 標準周期 | 条件・注意 |
| --- | --- | --- |
| 自艦・API艦の位置、yaw、visibility、必要ID | core、約5Hz | 遠距離艦1Hz化は未実装。観測範囲外の艦を合成しない |
| avatar列挙・識別候補・map位置 | core、約5Hz | API艦一覧とは別の観測源。未確認namespaceを確定joinしない |
| 共通HP・生存値（self／ships／avatar） | 平均約2Hz | 0.5秒期限。非dueは省略／notSampled、古いHPを現在値として補完しない |
| avatarのAPI範囲比較・candidate比較・coverage集計 | 約1Hz | 必要ID・位置の5HzやHP2Hzは別枠。較正診断の1Hz化とは別 |
| 自艦depthの専用取得 | core、約5Hz | `self_depth_sampling_enabled`必須 |
| WaveHitの専用取得 | core、約5Hz | `wave_hit_sampling_enabled`必須。TTL・対象ID namespaceの確定ではない |
| Batteryの専用取得 | 約1Hz | `battery_sampling_enabled`必須、comparison共通期限。depth／WaveHitを遅くしない |
| gun reload raw／progressの専用取得 | core、約5Hz | `gun_reload_sampling_enabled`必須。modifier getEntity探索を省く。装填残数・物理管IDの確定ではない |
| module HP／故障候補／critTimer | core、約5Hz | `torpedoArmament.modules`。1Hz化は未実装、装填進捗と別 |
| 自艦消耗品・radar／hydro／locator等 | core、約5Hz | `selfSystems`。短期状態の取り逃しを伴う1Hz化は未実装 |
| damageイベント受付・台帳更新 | イベント発生時 | ポーリングの1Hz制限はかけない |
| damage snapshot生成・出力 | 約1Hz | comparison共通期限。終了frameは周期を無視して最新台帳を試行 |
| 初回魚雷弾薬／TTX候補 | 1戦1回 | 初回の対象外・欠測も固定。周期再取得・スキル補正値取得は行わない |
| 較正observe／drift判定・診断辞書 | core、約5Hzで評価 | fitは必要条件成立時。診断だけ1Hz化する案は未実装 |
| heavy diagnostics | 既定約1Hz | `diagnostics_enabled`必須、`diagnostics_interval`で変更可。専用ON群の周期を上書きしない |
| profiler | 各計測対象の実行時／集計出力は約5秒窓 | `profiler_enabled`必須。ゲームframe timeやCPU使用率とは別 |
| state.json出力 | core、約5Hz | 同じファイルでも各情報群が毎回揃うわけではない |

専用depth／Battery／WaveHit／gun設定がOFFでもheavy diagnosticsがONなら、その群は従来のheavy due経路で観測する場合がある。両方OFFでは採取しない。collection無効時は通常の採取tickを開始しない。

`sampleTs`、`sampling.status`、rawの取得状態を併読する。sampledは採取試行であり成功保証ではなく、非due・欠測・正常な空一覧・消失を区別する。履歴保持・表示補間は外部アプリ側の責務である。
