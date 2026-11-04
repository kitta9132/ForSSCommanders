# B44：多数魚雷の区間計測

2026-11-04。ユーザー報告：7:30退出、minFPS40～50、目立つカクつきなし。0.3.30のcore5Hz、profiler ON、heavy/depth/state samplerとATMはOFF。終了後クライアント停止確認・collector13ファイルhash照合退避済み。

## 記録

私有JSONLを逐次解析。meta2件roster12、active743、inactive2、範囲約151.76秒。shipsは6件419 state、12件303、ほか7～10件。魚雷同時最大63本、owner同時最大11、全9,671魚雷行でworld/map positionを保持。平均更新間隔0.20453秒、最大0.22068秒。

profiler available29窓、notSampled714。writerMode syncEncodeWrite、time.clock/basis assumed。以下は記録時計上の値でCPU使用率・FPSへ換算しない。inclusive区間は合計として加算しない。

| 区間 | sample数 | 平均ms | 最大ms |
|---|---:|---:|---:|
| ships | 725 | 1.636 | 3.472 |
| avatar | 725 | 2.167 | 5.935 |
| torpedoes | 725 | 0.441 | 2.310 |
| submit | 725 | 1.186 | 2.327 |
| snapshot_build_total | 725 | 5.612 | 11.346 |
| state_cycle_total | 725 | 6.825 | 12.423 |

## 増加の内訳

最初の窓は魚雷0本・ships平均0.662ms、cycle5.163ms。魚雷がまだ0本の後続窓でもships平均が約1.96msまで増え、avatarはおおむね2.1～2.3ms。魚雷だけが原因とは限らず、較正sample蓄積等のsource内経路を再生で調べる必要がある。

魚雷が増えた終盤の最後のcomplete窓（出力ts643.0633）は魚雷平均61.6本・最大63本・owner11。torpedoes平均2.056ms／最大2.310ms、submit平均1.894ms／最大2.190ms、ships平均1.977ms、avatar平均2.047ms、cycle平均9.319ms／最大10.333ms。魚雷初期0本窓のtorpedoes約0.025～0.034ms、submit約0.93～1.09msに対し増加を観測した。

窓の魚雷数は対応するstate区間を集計したもので、profilerのphase完了と出力の境界差があり、個々の魚雷への厳密な時間帰属ではない。216本を観測したB43へ直線外挿して時間を確定しない。描画・他game処理・recorderはcollector phase外であり、報告minFPSとの因果は未確定。

## 次工程

### 0.3.31のoffline結果

direct world位置と同rowのmapPositionRawの組を4,458件再生、各stateの抽出件数はdiag.mapSamplesと743/743件一致。旧走査は早期return込み714,861比較（平均160.36/候補）、重複2,783件。reservoirはstate221で256件に達し523 state満杯、入替489回。

幅0.008のbucketから±3セル（49セル）を検索し、候補を元slot順に並べて従来の距離・境界判定を行う。新走査は厳密比較40,168回（94.38%減）、bucket参照218,442回、比較候補49,889件。削減率は距離比較のみで、全処理やFPSの改善率ではない。入替時に旧slotと空bucketを除き、clear/drift reset時にindexも消去する。保持するのは既存numeric較正sampleの索引だけで生位置cacheは追加しない。

新旧snapshot・sample・RNGは743/743 state一致。ホストPython3.14再生中央値0.518→0.122秒は実機性能ではない。通常のPython3.14再生では記録の係数・RMSE・holdout RMSEと710 stateで異なるが、旧実装でも同差が出る。独立照合では`sum`を逐次加算、残差の`hypot`を二乗和の`sqrt`相当にすると記録の全743 snapshotと完全一致した。再生ランタイムの演算差で説明でき、最適化による差は検出されなかった。入力順・4,458点の抽出数も一致し、JSON精度不足や出力丸めを原因とする必要はない。

通常3.14再生との差はscale最大6.82e-13（相対5.69e-16）、train RMSE最大1.21e-15、holdout RMSE最大1.46e-14。status/sampleCount/spansは全state一致。異なるruntimeでも無条件にbit単位で一致する保証にはしない。比較元は`4eb5922`の旧実装。既存B44測定値は0.3.30のもので、0.3.31のFPSは未検証。

親の独立検証：全pytest 427 passed・1 skipped、Python3.11 checker成功（9 moduleのPython2 grammarとcollector integration）。サブエージェント報告の428 passedとは区別し、今回の親の結果を採用する。

追加でPython3.11全pytestも428 passed。ホスト3.11の固定入力miss queryを各10,000回・5反復の中央値で比較すると、reservoir1件は旧0.681→新5.194μs、25件は13.152→5.206μs、256件は136.955→5.974μs。小reservoirでは49 bucket参照の固定費で遅くなる。これは限定的な合成入力で、B44全体再生・実機速度とは別の結果。全条件で高速化したとは主張しない。

較正replayと数値差の調査は完了。B31の小reservoirとは異なりB44では走査増加を確認し、意味・coverageを維持する最適化を0.3.31へ統合した。ゲーム内の処理時間・FPS効果は未確認で、即時の高負荷再試験は求めない。魚雷切捨てやframeを超えた古いowner/positionの再利用はしない。
