# B35：0.3.24 player共有の6対6確認

2026-11-03。ユーザー報告：minFPS約75、カクつきなし。試験後クライアント停止を確認し、mod13ファイルをhash照合してロード対象外へ保全退避。他mod変更なし。

## 記録確認

私有JSONLを逐次解析。版0.3.24-player-read-sharing、meta1、roster12隻。active196、inactive終端1、active約39.87秒。12艦184 state、6艦9、8艦2、10艦1。

更新間隔平均0.20446秒、中央値0.20442秒、最小0.20009秒、最大0.21831秒。全2,288艦行にmap nx/nyとplayerIdあり。players sampleStatusは全196 activeでcomplete、indexHits合計2,288、ships内vehicleLookups0。直接getPosition available1,176、none1,112。拡張fallback sampledShips0。

profiler available7窓、notSampled189。time.clock / basis assumed、syncEncodeWrite。下記は記録時計上の値でCPU使用率・FPSへ換算しない。inclusive区間を加算しない。

| 区間 | sample数 | 平均ms | 最大ms |
|---|---:|---:|---:|
| ships | 175 | 0.583 | 0.954 |
| avatar | 175 | 2.132 | 3.229 |
| self | 176 | 0.676 | 2.004 |
| armament_systems | 175 | 0.408 | 0.936 |
| torpedoes | 175 | 0.020 | 0.068 |
| snapshot_build_total | 175 | 3.932 | 5.785 |
| submit | 175 | 0.869 | 1.127 |
| state_cycle_total | 175 | 4.823 | 6.924 |

## B33との比較と次工程

B33は0.3.23・6対6・5HzでminFPS約45、ごく軽微なカクつき。ships平均7.438ms、cycle11.898ms。B35は同じ艦数・設定周期でplayer共有の実利用を確認し、ships0.583ms、cycle4.823msとなった。player一覧index作成の費用もavatar/cycleに含まれる。区間短縮と体感改善は整合するが、別戦闘・描画条件、modなし基準なしのため、FPS因果・改善率の一般化は行わない。

1対1（B34）・6対6（B35）を通過したため、次の段階として0.3.24・同じ5Hz/core-only設定の24隻を短時間だけ確認する計画。従来のB28悪化を踏まえ、カクつき出現または大幅なFPS低下で即中止し、通常戦へは進まない。24隻の性能は現時点で未確認、魚雷多数時・診断ONも未検証。
