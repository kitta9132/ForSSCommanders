# B46：0.3.38 独立取得・通常区間の確認

2026-11-04、build13357625、mod `0.3.38-independent-gun-reload`（source `ae3c9e8`）。ATMなし、heavy diagnostics OFF、core0.2秒、profilerと自艦depth／Battery／WaveHit／gun独立設定ON。[計画](VALIDATION_PLAN_0.3.38.ja.md)の限定試験。録画なし。

## ユーザー報告と証拠範囲

- 移動後07:45魚雷発射、07:35ping発射、07:28までに命中確認、07:00には30mへ潜航したはず、その後退出。
- 最低FPS約50以上、カクつきなし。ユーザー報告であり自動FPS計測や旧版との対照比較ではない。
- private B46は50,233,263byte、meta1＋active state1,333＋inactive state1＝1,335 records。battleIdは1種、meta.versionは0.3.38。active ts688.827161893～960.081928848、終了ts960.166588549、active範囲約271.255秒。
- game残時間とstate.tsの換算は確定しない。録画がないため、ユーザーの操作時刻とraw変化の厳密な同時性は未検証。

## 群別周期・非due

| 群 | sample数 | 非due数 | 実sample間隔（秒、min／median／max） |
| --- | ---: | ---: | --- |
| core state | 1,333 | — | 0.200000／0.203123／0.224460 |
| 共通HP | 543 | 790 | 0.400710／0.412346／0.630501 |
| avatar比較 | 272 | 1,061 | 0.810343／1.017188／1.034394 |
| damage | 272 | 1,061 | 同上 |

HP平均間隔0.500098秒（約1.9996Hz）、比較／damage平均1.000195秒（約0.9998Hz）。期限をtickへ量子化する設計と整合し、HPの全遷移捕捉や厳密な0.5秒周期を保証するものではない。

- HP非due790 state全てでships health/maxHealth/aliveとself health/maxHealthを省略。damage非due1,061 state全てでdamageキー省略。比較とdamageのsampling status／時刻は全state一致。
- 終了frameはdamageを周期外でsampled出力。今回は直前の定期sampleと台帳一致したため、「最終定期sample後の新イベントを実戦で捕捉した」証明ではない（offline回帰で確認済み）。
- avatarは全activeでcomplete・2行。API shipsは2行1,153 state／1行180 state。private player補完lookupは全activeで0。観測範囲差をunknownや過去rowで埋めない。
- heavy weaponHubとidentityCandidatesは全activeでdisabled。独立raw取得を確定ID joinへ昇格しない。

## collector区間計測（FPSそのものではない）

performance availableは53個の異なる集計窓（その他stateはnotSampled）。phaseごとのtotal/countを合算した加重平均で、平均の単純平均ではない。起動直後dropの調査はしない。通常区間の参考として、最初のactiveから30秒以降に報告された48窓、各主要phase1,200回を集計した。窓が境界をまたぐ可能性があり、厳密な30秒切断ではない。

| phase | 平均ms | 最大ms |
| --- | ---: | ---: |
| state_cycle_total | 3.76299 | 7.35850 |
| snapshot_build_total | 2.65841 | 5.68470 |
| submit | 1.08149 | 2.16860 |
| avatar | 0.50307 | 0.90210 |
| self | 0.70632 | 1.81090 |
| ships | 0.30905 | 0.76770 |
| torpedoes | 0.14198 | 0.65750 |
| armament_systems | 0.25746 | 0.62990 |
| submarine_sampling | 0.13957 | 0.45910 |
| gun_sampling | 0.48239 | 1.44800 |

全53窓のcycleは平均3.75732ms・最大7.35850ms。sourceはtime.clock、Windows上のbasisは既存契約のassumed、writerMode=syncEncodeWrite。今回追加の独立phaseが実機で計上された。phaseには入れ子があり合計して総時間を作らない。構成・艦数が違う過去戦からFPS改善率を作らない。

## 魚雷距離群の到達点

今回sample魚雷は計1,018行、同時最大6本。全activeでmembershipComplete=true、high最大6／low最大0。分類contextは初期200 stateがunknown、その後1,133 stateがavailable。マップ較正由来の分類であり、公式map境界の保証ではない。low群が存在しないため、**遠距離2Hzの実機動作・多数魚雷FPSは今回未検証**。このためだけに同条件の再戦や大量魚雷試験を即要求しない。

## 記録状態・撤収

先行確認時のB46は0byteだったが、記録プロセス完了後に上記1,335 recordsを実確認した。先行値を記録障害・欠損原因の証明にはしない。「保存された時系列に欠測が一切ない」という無条件の保証もしない。回収済み全activeの隣接ts最大間隔は0.224460秒。

ゲーム停止確認後、Python9＋設定例の10 source hash一致を確認。config／meta／stateを含むcollector13ファイルをhash照合してPnFMods外へ退避し、ゲームload pathから除去した。記録・ゲームログ・個人設定はprivate保全のみでコミットしない。

独立各probe・初回性能の詳細は別途集計結果を追記する。現時点で実用情報全項目やFPS課題を解決済みとは扱わない。
